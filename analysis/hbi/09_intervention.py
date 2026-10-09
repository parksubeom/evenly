# -*- coding: utf-8 -*-
"""
09_intervention.py ─ [v5, 2차 방문] "여기에 엘리베이터를 놓으면 몇 집이 몇 분 덜 걷나?" 설치 효과 시뮬레이션

[실행]  python 09_intervention.py      (02_network.py, 03_hbi.py 를 먼저 실행해야 함)
[준비]  external/interventions.csv 에 시설마다 한 줄 (메모장·엑셀로 열어 입력)
          name, type(elevator/monorail/vertical/ramp), a_lon, a_lat(아래 끝), b_lon, b_lat(위 끝),
          wait_s(대기 초, 비우면 종류별 기본값), speed(m/초, 비우면 기본값), status(planned/existing), note
        좌표 4개가 다 채워진 행만 계산합니다. (현장실측 기록지의 시설 양 끝 좌표를 옮겨 적으면 됨)
[하는 일]
  1. 시설 양 끝을 가장 큰 연결망의 가장 가까운 길 노드에 연결 (50m 넘게 떨어져 있으면 경고 → 좌표 확인)
     [v6.1a] 끝점이 OUT_OF_DATA_M(500m) 넘게 떨어진 시설은 길 자료 범위 밖으로 보고 건너뜀 (모두 그렇다면 결과 없이 끝냄)
  2. 시설 통과 시간 = 대기 + 양 끝 직선거리 ÷ 속도 + (끝점까지 걸어가는 거리 합) ÷ 고령자 속도
  3. 시나리오: 시설 하나씩 + "ALL(후보 전체)" (ALL 에는 이미 있는 시설 status=existing 은 넣지 않음)
  4. 목적지(config.INTERVENTION_TARGETS 중 결과에 있는 것)마다 설치 전후 고령자 왕복 시간을 비교
     설치 후 BENEFIT_MIN_S(기본 60초) 이상 줄어든 건물 = 수혜 건물. 데이터 경계 근처 건물은 제외
  JS로 치면: 지도 앱 길찾기 그래프에 "지름길 간선" 하나를 추가(push)하고 모든 집의 길찾기를 다시 돌려 before/after 를 비교하는 것
[결과] (output/ → 반출 대상. 기획서 22·23장)
  intervention_summary.csv : 시설·목적지별 수혜 건물 수, 평균·최대 단축(분), 설치 전후 HBI(수혜 건물 평균, 분모는 설치 전 평지 시간),
                             휠체어로 새로 갈 수 있게 된 건물 수(wheel_newly_reachable), 휠체어 1분 이상 단축 건물 수(wheel_benefit),
                             [v5 추가, 맨 뒤 열] 고립 위험 탈출 n_exit_high(설치 전 HBI ≥ 1.8 → 후 < 1.8 건물 수),
                             weight_exit_high(그 건물 연면적 합, MIN_COUNT 개 미만이면 빈 칸), n_exit_mid(≥ 1.3 → < 1.3 건물 수)
  intervention_grid.csv    : 250m 격자별 수혜 건물 수·평균 단축(분) (수혜 건물 MIN_COUNT 개 이상 격자만)
  intervention_dong.csv    : 행정동별 수혜 건물 수·연면적, 동 전체 주거 연면적, 연면적×단축분 합 (MIN_COUNT 개 이상 동만)
                             → 밖에서 "수혜 고령자·분 = 65세 이상 인구 × weight_x_saved_min ÷ weight_all" 로 환산
                             [v5 추가, 맨 뒤 열] weight_exit_high (그 동에서 HBI 1.8 아래로 내려온 건물 연면적, MIN_COUNT 개 미만이면 빈 칸)
[결과 보는 법] 화면의 "수혜 건물 N동, 평균 M분 단축" 을 보고, N 이 0 이면 끝점 좌표(경고)와 BENEFIT_MIN_S 를 확인
"""
import lib.runlog as _RL; _RL.start(globals())   # [v6.2] 기록·멈추면 메모 카드 (무거운 import 보다 먼저. lib/runlog.py)
import os, numpy as np
np.seterr(invalid="ignore", divide="ignore")      # 0÷0 경고 숨김 (결과는 NaN)
import config as C
from lib.qio import log, read_csv, write_csv, transform_xy, transformer, find_files, iter_layer
from lib.qgraph import NearestIndex
from lib.netload import load
from lib.bload import load_buildings, usable
from lib.model import run_with_extra

os.makedirs(C.OUTPUT, exist_ok=True)

# ── 0. 시설 목록 읽기 ─────────────────────────────────────
def fnum(v):
    """CSV 칸 → 숫자 (빈 칸이면 None). JS의 v === "" ? null : Number(v) 와 같음"""
    v = (v or "").strip()
    return float(v) if v else None

rows = [r for r in read_csv(os.path.join(C.EXTERNAL, "interventions.csv"))
        if all(fnum(r.get(k)) is not None for k in ("a_lon", "a_lat", "b_lon", "b_lat"))]   # 좌표 4개가 다 있는 행만
if not rows:
    raise SystemExit("external/interventions.csv 에 양 끝 좌표(a_lon, a_lat, b_lon, b_lat)가 모두 채워진 행이 없습니다 → 건너뜀")

net = load()
nodes, e, s = net["nodes"], net["e"], net["s5"]
N = len(nodes)
b = load_buildings()
dest = dict(np.load(os.path.join(C.WORK, "dest_nodes.npz")))     # 03_hbi.py 가 저장한 목적지 노드
U = usable(b)                                                    # 데이터 경계 근처 건물 제외
node = b["node"].astype(int)
tg = [t for t in C.INTERVENTION_TARGETS if t in dest and f"{t}_t_elder" in b]
if not tg:
    raise SystemExit(f"비교할 목적지가 없습니다 (INTERVENTION_TARGETS={C.INTERVENTION_TARGETS}, 결과에 있는 목적지={list(dest)})")

# ── 1. 시설 양 끝 → 길 노드 연결, 시설 통과 시간 ───────────
gi = np.where(net["giant"])[0]                                   # 남긴 연결망 노드만 (작은 섬에 붙으면 효과가 0)
idx = NearestIndex(nodes[gi])
tf = transformer("EPSG:4326")                                    # 경위도 → 분석 좌표계
fac = []                                                         # [(이름, 상태, (노드a, 노드b, 시간초)), ...]
out_of_data = []                                                 # [v6.1a] 길 자료 범위 밖이라 건너뛴 시설 이름
for r in rows:
    typ = (r.get("type") or "elevator").strip().lower()
    base = C.FACILITY.get(typ, C.FACILITY["elevator"])
    wait = fnum(r.get("wait_s"))
    speed = fnum(r.get("speed"))
    wait = base["wait_s"] if wait is None else wait              # 비우면 종류별 기본값 (JS의 wait ?? base.wait_s)
    speed = base["speed"] if speed is None else speed
    (ax, bx), (ay, by) = transform_xy(tf, [fnum(r["a_lon"]), fnum(r["b_lon"])], [fnum(r["a_lat"]), fnum(r["b_lat"])])
    d, i = idx.query(np.array([[ax, ay], [bx, by]]))             # 양 끝에서 가장 가까운 노드까지 거리
    if not (d[0] <= C.OUT_OF_DATA_M and d[1] <= C.OUT_OF_DATA_M):  # [v6.1a] 길 자료 범위 밖 (가장자리 노드로 잘못 계산하지 않게)
        far = max(d[0], d[1])
        log(f"  !! {r['name']}: 끝점이 가장 가까운 길에서 {f'{far:.0f}m' if np.isfinite(far) else '5km 넘게'} 떨어져 있음 → 길 자료 범위 밖으로 보고 건너뜀 (이 시설은 결과 없음)")
        out_of_data.append(r["name"])
        continue
    na, nb_ = gi[i[0]], gi[i[1]]
    for tag, dd in (("a(아래)", d[0]), ("b(위)", d[1])):
        if dd > C.INTERVENTION_SNAP_WARN:
            log(f"  !! {r['name']}: 끝점 {tag} 가 길에서 {dd:.0f}m 떨어져 있음 → 좌표 확인 (그대로 계산은 함)")
    straight = float(np.hypot(bx - ax, by - ay))                 # 시설 길이 = 양 끝 직선거리
    t = wait + straight / speed + (d[0] + d[1]) / C.ELDER_SPEED
    fac.append((r["name"], (r.get("status") or "planned").strip().lower(), (int(na), int(nb_), float(t))))
    log(f"  시설 {r['name']} [{typ}, {r.get('status')}] 길이 {straight:.0f}m, 통과 {t / 60:.1f}분 (대기 {wait:g}초, {speed:g}m/s)")

if not fac:                                                      # [v6.1a] 좌표가 찬 시설이 모두 범위 밖 → 실패로 멈추지 않고 결과 없이 끝냄
    log(f"좌표가 채워진 시설 {len(out_of_data)}곳이 모두 길 자료 범위 밖 → 09 결과 없음 (그 구 자료를 받은 뒤 다시)")
    raise SystemExit(0)
if out_of_data:
    log(f"  길 자료 범위 밖이라 건너뛴 시설 {len(out_of_data)}곳: {', '.join(out_of_data)}")
scen = [(n, [x]) for n, _, x in fac]                             # 시나리오 = 시설 하나씩
cand = [x for n, st, x in fac if st != "existing"]               # ALL 에는 이미 있는 시설 제외
if cand:
    scen.append(("ALL(후보 전체)", cand))

# ── 2. 행정동 준비 (05_export.py 와 같은 방식) ─────────────
bd = find_files(C.EXTERNAL, ["dong_boundary"], ".geojson") + find_files(C.EXTERNAL, ["dong_boundary"], ".shp")
X, Y = b["x"], b["y"]
which, dcode = None, []
if bd:
    from lib.qnetwork import points_in_polygons
    polys = [(g, a) for g, a in iter_layer(files=bd[:1], bbox=None)]
    ck = next(k for k in polys[0][1] if k.upper() in ("ADM_CD", "ADM_DR_CD", "ADSTRD_CD", "CODE"))
    bx0, bx1, by0, by1 = np.nanmin(X), np.nanmax(X), np.nanmin(Y), np.nanmax(Y)
    polys = [p for p in polys if not (p[0].GetEnvelope()[1] < bx0 or p[0].GetEnvelope()[0] > bx1 or
                                      p[0].GetEnvelope()[3] < by0 or p[0].GetEnvelope()[2] > by1)]
    _, which = points_in_polygons(X, Y, polys)                   # 건물마다 몇 번째 동인지 (-1 = 없음)
    dcode = [str(a[ck]) for _, a in polys]
    wall = np.array([b["weight"][(which == k) & U].sum() for k in range(len(polys))])   # 동 전체 주거 연면적 (경계 제외)

# ── 3. 계산 ───────────────────────────────────────────────
summ, grows, drows = [], [], []
gx = np.floor(X / C.GRID).astype(np.int64)
gy = np.floor(Y / C.GRID).astype(np.int64)
ok0 = U & (node >= 0)
for name, extra in scen:
    for T in tg:
        te0, tfl = b[f"{T}_t_elder"], b[f"{T}_t_flat"]          # 설치 전 고령자 왕복, 평지 가정 왕복 (초)
        tw0 = b[f"{T}_t_wheel"]
        r = run_with_extra(N, e, s, dest[T], extra)              # 설치 후 (lib/model.py)
        te1 = np.full(len(node), np.nan); tw1 = np.full(len(node), np.nan)
        te1[ok0] = r["t_elder"][node[ok0]]
        tw1[ok0] = r["t_wheel"][node[ok0]]
        ok = ok0 & np.isfinite(te0) & np.isfinite(te1)
        saved = np.where(ok, te0 - te1, 0.0)                     # 줄어든 시간 (초)
        ben = ok & (saved >= C.BENEFIT_MIN_S)                    # 수혜 건물
        w0 = np.where(np.isfinite(tw0), tw0, np.inf)
        w1 = np.where(np.isfinite(tw1), tw1, np.inf)
        newly = ok0 & ~np.isfinite(w0) & np.isfinite(w1)         # 휠체어로 전에는 못 가다가 이제 갈 수 있게 된 건물
        wben = ok0 & (newly | (np.isfinite(w0) & (w0 - w1 >= C.BENEFIT_MIN_S)))
        nb = int(ben.sum())
        hb = float(np.mean(te0[ben] / tfl[ben])) if nb else np.nan    # 수혜 건물 평균 HBI (분모 = 설치 전 평지 시간)
        ha = float(np.mean(te1[ben] / tfl[ben])) if nb else np.nan
        # [v5 추가] 고립 위험 탈출: 설치 전 HBI ≥ 1.8 → 설치 후 < 1.8 (분모는 설치 전 평지 시간), 1.3 도 같은 방식
        h0, h1 = np.where(ok, te0 / tfl, np.nan), np.where(ok, te1 / tfl, np.nan)
        ex_hi = ok & (h0 >= C.HBI_BANDS[1]) & (h1 < C.HBI_BANDS[1])
        ex_mid = ok & (h0 >= C.HBI_BANDS[0]) & (h1 < C.HBI_BANDS[0])
        n_hi = int(ex_hi.sum())
        f = lambda v, d=3: round(v, d) if np.isfinite(v) else ""
        summ.append([name, T, nb, round(float(b["weight"][ben].sum())), f(float(np.mean(saved[ben])) / 60 if nb else np.nan, 2),
                     f(float(np.max(saved[ben])) / 60 if nb else np.nan, 2), round(float(saved[ben].sum()) / 60, 1),
                     f(hb), f(ha), int(newly.sum()), int(wben.sum()),
                     n_hi, round(float(b["weight"][ex_hi].sum())) if n_hi >= C.MIN_COUNT else "", int(ex_mid.sum())])
        log(f"  {name} · {T}: 수혜 건물 {nb:,}동, 평균 {np.mean(saved[ben]) / 60 if nb else 0:.1f}분 단축, 휠체어 새로 도달 {int(newly.sum())}동")
        # 격자별 (수혜 건물 MIN_COUNT 이상)
        if nb:
            key = gx[ben] * 10**7 + gy[ben]
            u, inv = np.unique(key, return_inverse=True)
            cnt = np.bincount(inv)
            ms = np.bincount(inv, saved[ben]) / cnt / 60
            for k in np.where(cnt >= C.MIN_COUNT)[0]:
                grows.append([name, T, (u[k] // 10**7 + 0.5) * C.GRID, (u[k] % 10**7 + 0.5) * C.GRID, int(cnt[k]), round(float(ms[k]), 2)])
        # 행정동별 (수혜 건물 MIN_COUNT 이상)
        if which is not None:
            for k, code in enumerate(dcode):
                m = ben & (which == k)
                if m.sum() >= C.MIN_COUNT:
                    mx = ex_hi & (which == k)
                    drows.append([name, T, code, int(m.sum()), round(float(b["weight"][m].sum())), round(float(wall[k])),
                                  round(float((b["weight"][m] * saved[m] / 60).sum()), 1),
                                  round(float(b["weight"][mx].sum())) if mx.sum() >= C.MIN_COUNT else ""])

write_csv(os.path.join(C.OUTPUT, "intervention_summary.csv"),
          ["facility", "target", "n_benefit", "weight_benefit", "mean_saved_min", "max_saved_min", "sum_saved_bld_min",
           "hbi_before", "hbi_after", "wheel_newly_reachable", "wheel_benefit",
           "n_exit_high", "weight_exit_high", "n_exit_mid"], summ)
write_csv(os.path.join(C.OUTPUT, "intervention_grid.csv"), ["facility", "target", "cell_x", "cell_y", "n_benefit", "mean_saved_min"], grows)
write_csv(os.path.join(C.OUTPUT, "intervention_dong.csv"),
          ["facility", "target", "adm_cd", "n_benefit", "weight_benefit", "weight_all", "weight_x_saved_min", "weight_exit_high"], drows)
if not bd:
    log("  external/dong_boundary.geojson 없음 → intervention_dong.csv 는 머리 줄만")
log(f"완료 → output/intervention_summary.csv ({len(summ)}행), intervention_grid.csv ({len(grows)}행), intervention_dong.csv ({len(drows)}행)")
