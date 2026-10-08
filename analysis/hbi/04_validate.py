# -*- coding: utf-8 -*-
"""
04_validate.py ─ [4일차] "이 모델 믿을 만한가?" 검증 + "LX 데이터가 얼마나 중요한가?" 기여도 분석

[실행]  python 04_validate.py      (03_hbi.py 다음)
[하는 일과 결과 파일]  (모두 output/ 에 저장 → 반출 대상. 기획서 17·18장에 들어갈 숫자들)
  1) 선정지 재현  → validation_sites.csv
     서울시가 2025년에 고른 5곳(external/sites.csv) 주변 300m 의 평균 HBI 가
     전체 격자 중 상위 몇 %인지(percentile). 0.9 이상 = 상위 10% 안 = 모델이 전문가 판단을 재현
     [v5] percentile_circle: 모든 250m 격자 중심에 "같은 반경 원"을 그려 그 평균들과 비교한 백분위 (같은 기준끼리 비교)
     → validation_new_candidates.csv : 선정지보다 HBI 가 높은데 선정 안 된 곳 (= 공모가 놓친 곳)
  2) 구간 재현    → validation_routes.csv  ([v6.1a] 끝점이 길에서 OUT_OF_DATA_M(500m) 넘게 먼 구간은 길 자료 범위 밖으로 보고 건너뜀)
     external/od_pairs.csv 의 출발·도착 사이 경로 길이·시간. 대현산배수지공원 휠체어 우회(서울시 발표 약 770m)
     와 비교하고, 현장실측 시간(measured_min)이 있으면 성인 속도 예측(adult_min)과 상관계수 계산
     [v5] 실측 3구간 이상이면 상관계수를 validation_measured.csv (n, r_adult_pred_vs_measured) 로도 저장
  3) 기여도       → validation_ablation.csv
     데이터를 하나씩 뺐을 때 결과가 얼마나 달라지는지 (DEM 제외 / 계단 제외 / 큰 격자로 집계 / DEM 1m)
     [v6.1] 걸을 수 없는 길을 뺀 효과 (빼지 않은 v5 방식 네트워크와 HBI 비교), DEM 5m vs 1m 중앙값·고위험 비율
"""
import os, numpy as np
import config as C
from lib.qio import log, csv_points, read_csv, write_csv
from lib.qgraph import NearestIndex, spearman
from lib.netload import load
from lib.bload import load_buildings, targets, usable
from lib.model import route

os.makedirs(C.OUTPUT, exist_ok=True)
b = load_buildings()
net = load()
nodes, e, s = net["nodes"], net["e"], net["s5"]
T = "medical" if "medical_hbi" in b else targets(b)[0]    # 기준 목적지: 의료시설 (없으면 첫 번째 종류)
H = b[f"{T}_hbi"]
X, Y = b["x"], b["y"]
log(f"기준 목적지: {T}")


def grid(size, mask):
    """건물들을 size m 격자로 묶어 격자별 평균 HBI.
    반환: (격자x번호, 격자y번호, 평균, 개수) ← 건물 MIN_COUNT 개 이상 격자만, 그리고 (건물별 격자키, 전체 격자 평균 사전)"""
    gx = np.floor(X / size).astype(np.int64)
    gy = np.floor(Y / size).astype(np.int64)
    key = gx * 10**7 + gy                                   # (gx, gy) 를 숫자 하나로 합친 격자 키
    u, inv = np.unique(key[mask], return_inverse=True)      # 격자별로 묶기 (SQL의 GROUP BY 와 비슷)
    cnt = np.bincount(inv)                                  # 격자별 건물 수
    mean = np.bincount(inv, H[mask]) / cnt                  # 격자별 HBI 합 ÷ 수 = 평균
    keep = cnt >= C.MIN_COUNT
    return u[keep] // 10**7, u[keep] % 10**7, mean[keep], cnt[keep], key, dict(zip(u, mean))

U = usable(b)                                               # 데이터 경계 근처 건물 제외 (config.EDGE_BUFFER)
valid = np.isfinite(H) & U                                  # HBI 가 계산된 + 경계가 아닌 건물만
cgx, cgy, cmean, ccnt, _, _ = grid(C.GRID, valid)

# ── 1) 선정지 재현 ─────────────────────────────────────────
rows, sx, sy = csv_points(os.path.join(C.EXTERNAL, "sites.csv"))
if not rows:
    log("sites.csv 좌표 없음 → 선정지 검증 건너뜀")
else:
    # [v5] 같은 기준끼리 비교하기: 모든 250m 격자 중심에서 "선정지와 같은 반경" 원 안 건물 평균 HBI 를 구해 분포로 씀
    #   (v4 의 percentile 은 "선정지 반경 300m 건물 평균" 을 "250m 격자 평균" 분포와 비교 → 기준이 달랐음. 기존 열은 그대로 둠)
    rad0 = float(rows[0].get("radius_m") or 300)               # sites.csv 첫 행 반경 (기본 300m)
    vi = np.where(valid)[0]                                     # 유효 건물 번호들
    bidx = NearestIndex(np.c_[X[vi], Y[vi]])                    # 유효 건물 좌표 색인 (반경 검색용)
    allkeys = np.unique(np.floor(X[vi] / C.GRID).astype(np.int64) * 10**7 + np.floor(Y[vi] / C.GRID).astype(np.int64))
    circ = []                                                   # 격자 중심마다 원 평균 HBI
    for k in allkeys:
        cx0, cy0 = (k // 10**7 + 0.5) * C.GRID, (k % 10**7 + 0.5) * C.GRID
        j = bidx.within((cx0, cy0), rad0)                       # 반경 안 유효 건물 (bidx 기준 번호)
        if len(j) >= C.MIN_COUNT:                               # 건물이 너무 적은 원은 분포에서 뺌
            circ.append(float(np.mean(H[vi[np.asarray(j, int)]])))
    circ = np.array(circ)
    log(f"  같은 반경({rad0:g}m) 원 분포: 격자 중심 {len(allkeys):,}개 중 {len(circ):,}개 사용 (건물 {C.MIN_COUNT}개 미만 제외)")
    fmt = lambda v, d=3: round(float(v), d) if np.isfinite(v) else ""   # NaN 은 "nan" 글자 대신 빈 칸
    res, site_h = [], []
    for r, x, y in zip(rows, sx, sy):
        rad = float(r.get("radius_m") or 300)
        m = valid & (np.hypot(X - x, Y - y) <= rad)         # 선정지 반경 안의 건물
        hm = float(np.mean(H[m])) if m.any() else np.nan
        pct = float(np.mean(cmean < hm)) if np.isfinite(hm) else np.nan   # 이 값보다 낮은 격자의 비율 = 백분위 (v4 방식)
        pc = float(np.mean(circ < hm)) if np.isfinite(hm) and len(circ) else np.nan   # 같은 반경 원 분포 안 백분위 (v5)
        site_h.append(hm)
        res.append([r["name"], int(m.sum()), fmt(hm),
                    round(float(np.mean(H[m] >= C.HBI_BANDS[1])), 3) if m.any() else "",
                    fmt(pct), (pct >= 0.9) if np.isfinite(pct) else "",
                    fmt(pc), (pc >= 0.9) if np.isfinite(pc) else ""])
    write_csv(os.path.join(C.OUTPUT, "validation_sites.csv"),
              ["name", "n_bld", "hbi_mean", "share_high", "percentile", "top10", "percentile_circle", "top10_circle"], res)
    log("선정지 재현:")
    for r in res:
        print("   ", r)
    # 선정지 중 가장 낮은 HBI 보다 높고, 모든 선정지에서 500m 넘게 떨어진 격자 = 새 후보
    fin = [h for h in site_h if np.isfinite(h)]                 # 빈 칸(선정지 주변 건물 없음)은 건너뜀
    thr = min(fin) if fin else np.nan
    if np.isfinite(thr):
        cx, cy = (cgx + 0.5) * C.GRID, (cgy + 0.5) * C.GRID     # 격자 중심 좌표
        d, _ = NearestIndex(np.c_[sx, sy]).query(np.c_[cx, cy])
        sel = np.where((cmean > thr) & (d > 500))[0]
        sel = sel[np.argsort(-cmean[sel])][:30]                   # HBI 높은 순 상위 30개
        write_csv(os.path.join(C.OUTPUT, "validation_new_candidates.csv"), ["cell_x", "cell_y", "hbi_mean", "n_bld"],
                  [[cx[i], cy[i], round(cmean[i], 3), int(ccnt[i])] for i in sel])
        log(f"선정지 최저 HBI({thr:.2f})보다 높은 비선정 격자: {int(((cmean > thr) & (d > 500)).sum())}개")

# ── 2) 구간 재현 / 실측 비교 ───────────────────────────────
rows = [r for r in read_csv(os.path.join(C.EXTERNAL, "od_pairs.csv"))
        if all((r.get(k) or "").strip() for k in ("o_lon", "o_lat", "d_lon", "d_lat"))]   # 좌표 4개가 다 있는 행만
if rows:
    from lib.qio import transform_xy, transformer
    tf = transformer("EPSG:4326")
    ox, oy = transform_xy(tf, [float(r["o_lon"]) for r in rows], [float(r["o_lat"]) for r in rows])
    dx, dy = transform_xy(tf, [float(r["d_lon"]) for r in rows], [float(r["d_lat"]) for r in rows])
    gi = np.where(net["giant"])[0]
    idx = NearestIndex(nodes[gi])
    od_, oi_ = idx.query(np.c_[ox, oy])                   # 출발점에서 가장 가까운 노드 (거리, 번호)
    dd_, di_ = idx.query(np.c_[dx, dy])                   # 도착점에서 가장 가까운 노드
    oi, di = gi[oi_], gi[di_]
    res = []
    N = len(nodes)
    for k, r in enumerate(rows):
        if not (od_[k] <= C.OUT_OF_DATA_M and dd_[k] <= C.OUT_OF_DATA_M):   # [v6.1a] 길 자료 범위 밖 (가장자리 노드에 붙여 0분이 되지 않게)
            far = max(od_[k], dd_[k])
            log(f"  !! 구간 {r['name']}: 끝점이 가장 가까운 길에서 {f'{far:.0f}m' if np.isfinite(far) else '5km 넘게'} 떨어져 있음 → 길 자료 범위 밖으로 보고 건너뜀")
            continue
        te, le = route(N, e, s, oi[k], di[k], "elder")                 # 고령자
        ta, _ = route(N, e, s, oi[k], di[k], "elder", speed=1.1)       # 성인(1.1m/s) — 팀 실측과 비교용
        tw, lw = route(N, e, s, oi[k], di[k], "wheel")                 # 휠체어 (계단 회피)
        tf_, lf = route(N, e, s, oi[k], di[k], "flat")                 # 평지 가정 (최단거리와 같음)
        f = lambda v, d=1: round(v, d) if v == v else ""               # NaN 이면 빈 칸 (NaN != NaN 인 성질 이용)
        res.append([r["name"], round(float(np.hypot(ox[k] - dx[k], oy[k] - dy[k]))), f(lf, 0), f(te / 60), f(ta / 60),
                    f(lw, 0), f(tf_ / 60), r.get("measured_min", "")])
    write_csv(os.path.join(C.OUTPUT, "validation_routes.csv"),
              ["name", "straight_m", "net_m", "elder_min", "adult_min", "wheel_path_m", "flat_min", "measured_min"], res)
    # 열 뜻: straight_m 직선거리 / net_m 길 따라 최단거리 / wheel_path_m 휠체어 실제 경로 길이 / *_min 분
    log("구간 재현:")
    for r in res:
        print("   ", r)
    m = [(float(r[4]), float(r[7])) for r in res if r[4] != "" and str(r[7]).strip()]
    if len(m) >= 3:                                        # 실측이 3개 이상이면 상관계수
        a = np.array(m)
        rr = float(np.corrcoef(a[:, 0], a[:, 1])[0, 1])
        log(f"실측 vs 예측(성인 기준) 상관 r={rr:.3f}, n={len(a)}")
        # [v5] 로그뿐 아니라 파일로도 저장 (반출 대상, 기획서 17장)
        write_csv(os.path.join(C.OUTPUT, "validation_measured.csv"), ["n", "r_adult_pred_vs_measured"], [[len(a), round(rr, 3)]])

# ── 3) 기여도 분석 ─────────────────────────────────────────
ab = []
te, tf = b[f"{T}_t_elder"], b[f"{T}_t_flat"]
v = valid & np.isfinite(tf)
# DEM 제외: 평지 기준 순위와 경사 반영 순위를 비교
top = v & (te >= np.nanquantile(te[v], 0.9))       # 경사 반영 시 가장 오래 걸리는 상위 10%
ftop = v & (tf >= np.nanquantile(tf[v], 0.9))      # 평지 기준 상위 10%
ab.append(["DEM 제외(평지 가정)", "경사 반영 상위10% 취약건물 중 평지 기준으로는 상위10%가 아닌 비율",
           round((top & ~ftop).sum() / max(top.sum(), 1), 3)])
ab.append(["DEM 제외(평지 가정)", "경사 반영 vs 평지 소요시간 순위상관(Spearman)", round(spearman(te[v], tf[v]), 3)])
hi = v & (H >= C.HBI_BANDS[1])
ab.append(["DEM 제외(평지 가정)", "HBI 1.8 이상 건물 중 평지 기준 소요시간이 중앙값 이하('양호')인 비율",
           round((hi & (tf <= np.nanmedian(tf[v]))).sum() / max(hi.sum(), 1), 3)])
# 계단 제외: 계단을 지날 수 있다고 잘못 가정하면 휠체어 시간을 얼마나 과소평가하나
if f"{T}_t_wheel_stairok" in b:
    w, w2 = b[f"{T}_t_wheel"], b[f"{T}_t_wheel_stairok"]
    mm = np.isfinite(w) & np.isfinite(w2) & (w2 > 0)
    ab.append(["계단 레이어 제외", "계단을 통행가능으로 잘못 가정할 때 휠체어 시간 과소추정 비율(평균)",
               round(1 - 1 / np.mean(w[mm] / w2[mm]), 3) if mm.any() else ""])
    ab.append(["계단 레이어 제외", "휠체어 도달불가 건물 비율(계단 반영 시)", round(float(np.mean(~np.isfinite(w[U]))), 3)])
# 큰 격자 집계: 500m 로 뭉뚱그리면 고위험 건물이 평균에 묻히는 비율
_, _, _, _, key, means = grid(C.GRID_COARSE, v)
hid = [means.get(k, np.nan) < C.HBI_BANDS[0] for k in key[hi]]
ab.append([f"{C.GRID_COARSE}m 격자 평균으로 집계", "HBI 1.8 이상 건물 중 평균이 1.3 미만인 격자에 가려진 비율",
           round(float(np.mean(hid)), 3) if hid else ""])
# DEM 해상도: 5m 와 1m 결과가 얼마나 같은가
if f"{T}_hbi_dem1" in b:
    h1 = b[f"{T}_hbi_dem1"]
    mm = v & np.isfinite(h1)
    ab.append(["DEM 5m vs 1m", "비교한 집 수 (DEM 1m 범위 안)", int(mm.sum())])   # [v6.1]
    if mm.sum() >= C.MIN_COUNT:                      # [v6.1] 비교할 집이 너무 적으면 수만 (개별 값에 가까워지지 않게)
        ab.append(["DEM 5m vs 1m", "HBI 순위상관(Spearman)", round(spearman(H[mm], h1[mm]), 3)])
        ab.append(["DEM 5m vs 1m", "HBI 평균 절대차", round(float(np.mean(np.abs(H[mm] - h1[mm]))), 3)])
        ab.append(["DEM 5m vs 1m", "HBI 중앙값 (5m)", round(float(np.median(H[mm])), 3)])
        ab.append(["DEM 5m vs 1m", "HBI 중앙값 (1m)", round(float(np.median(h1[mm])), 3)])
        ab.append(["DEM 5m vs 1m", f"HBI {C.HBI_BANDS[1]} 이상 비율 (5m)", round(float(np.mean(H[mm] >= C.HBI_BANDS[1])), 3)])
        ab.append(["DEM 5m vs 1m", f"HBI {C.HBI_BANDS[1]} 이상 비율 (1m)", round(float(np.mean(h1[mm] >= C.HBI_BANDS[1])), 3)])
# [v6.1] 걸을 수 없는 길(고속국도·자동차전용) 빼기: 빼지 않은 네트워크(v5 방식)와 비교
nl, nk = net["walk_excl"]
sc = "걸을 수 없는 길 빼기 (v5 방식과 비교)"
if nl:
    ab += [[sc, "뺀 도로중심선 선 수", int(nl)], [sc, "뺀 링크 수", int(nk)]]
if f"{T}_hbi_walkall" in b:
    hw = b[f"{T}_hbi_walkall"]
    mm = v & np.isfinite(hw)
    ab.append([sc, "비교한 집 수", int(mm.sum())])
    if mm.sum() >= C.MIN_COUNT:                      # 비교할 집이 너무 적으면 수만
        ab += [[sc, "HBI 순위상관(Spearman)", round(spearman(H[mm], hw[mm]), 3)],
               [sc, "HBI 평균 절대차", round(float(np.mean(np.abs(H[mm] - hw[mm]))), 3)],
               [sc, "HBI 중앙값 (뺀 뒤)", round(float(np.median(H[mm])), 3)],
               [sc, "HBI 중앙값 (빼기 전)", round(float(np.median(hw[mm])), 3)],
               [sc, f"HBI {C.HBI_BANDS[1]} 이상 비율 (뺀 뒤)", round(float(np.mean(H[mm] >= C.HBI_BANDS[1])), 3)],
               [sc, f"HBI {C.HBI_BANDS[1]} 이상 비율 (빼기 전)", round(float(np.mean(hw[mm] >= C.HBI_BANDS[1])), 3)],
               [sc, "HBI 가 0.1 넘게 달라진 집 비율", round(float(np.mean(np.abs(H[mm] - hw[mm]) > 0.1)), 3)]]
write_csv(os.path.join(C.OUTPUT, "validation_ablation.csv"), ["scenario", "metric", "value"], ab)
log("기여도 분석:")
for r in ab:
    print("   ", r)
