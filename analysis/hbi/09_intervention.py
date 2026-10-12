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
     [v6.2] 수직 엘리베이터(vertical)는 대기 + a·b 높이 차 ÷ 속도(오르내리는 속도) + 끝점 걷기. 높이 차는 DEM(DATA_ROOT_DEM)에서
            a·b 두 점을 재서 씀 (사람이 적지 않음). DEM 이 a·b 를 덮지 않으면 그 시설은 건너뜀. 다른 종류는 v6.1 과 같은 식 (높이 차는 적기만)
  3. 시나리오: 시설 하나씩 + "ALL(후보 전체)" (ALL 에는 이미 있는 시설 status=existing 은 넣지 않음)
  4. 목적지(config.INTERVENTION_TARGETS 중 결과에 있는 것)마다 설치 전후 고령자 왕복 시간을 비교
     설치 후 BENEFIT_MIN_S(기본 60초) 이상 줄어든 건물 = 수혜 건물. 데이터 경계 근처 건물은 제외
     [v6.2] 함께 셈: 고령자 30초·60초 이상 단축(SAVED_BANDS_S), 휠체어 왕복 시간이 준 건물의 휠체어 길 길이 감소(m) 분위수
  JS로 치면: 지도 앱 길찾기 그래프에 "지름길 간선" 하나를 추가(push)하고 모든 집의 길찾기를 다시 돌려 before/after 를 비교하는 것
[결과] (output/ → 반출 대상. 기획서 22·23장)
  intervention_summary.csv : 시설·목적지별 수혜 건물 수, 평균 단축(분)·[10/12] 95% 분위 단축(saved_p95_min, 수혜 100채 미만이면 빈 칸.
                             v6.2 앞판까지는 최대 단축 max_saved_min = 늘 한 건물 값), 설치 전후 HBI(수혜 건물 평균, 분모는 설치 전 평지 시간),
                             휠체어로 새로 갈 수 있게 된 건물 수(wheel_newly_reachable), 휠체어 1분 이상 단축 건물 수(wheel_benefit),
                             [v5 추가, 맨 뒤 열] 고립 위험 탈출 n_exit_high(설치 전 HBI ≥ 1.8 → 후 < 1.8 건물 수),
                             weight_exit_high(그 건물 연면적 합, MIN_COUNT 개 미만이면 빈 칸), n_exit_mid(≥ 1.3 → < 1.3 건물 수)
                             [v6.2 추가, 맨 뒤 열] n_saved_30s·n_saved_60s(고령자 왕복 30초·60초 이상 준 건물 수), wheel_cut_n(휠체어 왕복
                             시간이 준 건물 수), wheel_cut_p25_m·p50_m·p75_m(그 건물들의 휠체어 길 길이 감소 m 분위수. 길 길이 = 휠체어가 고르는
                             시간 최소 길, 가는 길·오는 길 평균. 음수 = 설치 후 길이 더 김(설치 전 길이 짧지만 가파른 길). wheel_cut_n 이 WHEEL_CUT_MIN(100) 미만이면 빈 칸), rise_m(시설 a·b 높이 차 m, DEM 5m),
                             pass_s(시설 통과 시간 초). ALL 행의 rise_m·pass_s 는 빈 칸.
                             [10/12] n_benefit_any = 고령자 왕복 30초 이상 단축 또는 휠체어 왕복 1분 이상 단축(새로 도달 포함) 건물 수 (기획서 20장 '1억 원당 수혜')
                             [10/12] 시간 값(평균·95% 분위 단축, 단축 분 합, 설치 전후 HBI, 격자 평균 단축)도 대표 방식에서만 내고, 수혜 1~4채이거나
                             같은 목적지에서 낸 다른 시간 값(05 격자·동 HBI 평균 포함)과 빼서 1~4채가 남으면 빈 칸 (연면적과 같은 검사)
  [v6.2] intervention_wait.csv  : 시설 하나씩 대기시간을 config.WAIT_SENS_S(30·60·90초)로 바꿨을 때 수혜 건물 수 (05 와 같은 기준 목적지만,
                             건물 수만): facility, target, wait_s, pass_s, n_benefit, n_saved_30s, wheel_benefit
                             [v6.2] 연면적 칸(weight_benefit·weight_exit_high, 동 표의 weight_benefit·weight_all·weight_x_saved_min·weight_exit_high)은
                             05 와 같은 목적지(의료)·대표 방식만. 1~4채이거나, 05·09 가 낸 다른 연면적과 빼서(짝 하나, 겹치지 않는 여럿의 합,
                             summary − 동 합, ALL − 시설들) 1~4채가 남으면 빈 칸 (lib/expose.py). v6.1b 까지는 수혜 1~4채여도 냈음
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
from lib.qio import log, read_csv, write_csv, transform_xy, transformer, find_files, iter_layer, DEM
from lib.qgraph import NearestIndex
from lib.netload import load
from lib.bload import load_buildings, usable, targets, rep_mode
from lib.model import run_with_extra
from lib.expose import removal_leak   # [v6.2] 연면적 빼기 노출 검사

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
P = []                                                           # 시설마다 (ax, ay, bx, by) 분석 좌표
for r in rows:
    (ax, bx), (ay, by) = transform_xy(tf, [fnum(r["a_lon"]), fnum(r["b_lon"])], [fnum(r["a_lat"]), fnum(r["b_lat"])])
    P.append((float(ax), float(ay), float(bx), float(by)))


def end_heights(root, quiet=False):
    """[v6.2] 시설마다 양 끝 높이 (a, b) (m). 시설 둘레 20m 만 잘라 읽음 (02 와 같은 DEM). DEM 이 두 점을 덮지 않거나
    값이 0 이하(NoData 없이 비어 있는 칸)면 None"""
    out, missing = [], False
    for ax, ay, bx, by in P:
        if not root or missing:
            out.append(None)
            continue
        try:
            d = DEM(root, bbox=[min(ax, bx) - 20, min(ay, by) - 20, max(ax, bx) + 20, max(ay, by) + 20], quiet=True)
            xs, ys = np.array([ax, bx]), np.array([ay, by])
            z, cov = d.sample(xs, ys), d.covers(xs, ys)
            out.append((float(z[0]), float(z[1])) if cov.all() and np.isfinite(z).all() and (z > 0).all() else None)
        except FileNotFoundError as ex:                          # DEM 폴더가 없음 → 다른 종류 시설은 계산
            if not quiet:
                log(f"  !! DEM 을 읽지 못함 ({ex}) → 수직 엘리베이터는 높이 차를 잴 수 없어 건너뜀")
            missing = True
            out.append(None)
        except Exception:                                        # 이 시설 자리가 DEM 밖 (창을 읽지 못함)
            out.append(None)
    return out


Z5 = end_heights(C.DATA_ROOT_DEM)
Z1 = end_heights(C.DATA_ROOT_DEM1M, quiet=True) if C.DATA_ROOT_DEM1M else [None] * len(P)   # 참고로만 화면에
fac = []                                                         # [(이름, 상태, (노드a, 노드b, 시간초, 길이m), {"rise": 높이차, "pass": 통과초}), ...]
out_of_data = []                                                 # [v6.1a] 길 자료 범위 밖이라 건너뛴 시설 이름
no_height = []                                                   # [v6.2] DEM 이 덮지 않아 높이 차를 못 잰 수직 엘리베이터
for r, (ax, ay, bx, by), z5, z1 in zip(rows, P, Z5, Z1):
    typ = (r.get("type") or "elevator").strip().lower()
    base = C.FACILITY.get(typ, C.FACILITY["elevator"])
    wait = fnum(r.get("wait_s"))
    speed = fnum(r.get("speed"))
    wait = base["wait_s"] if wait is None else wait              # 비우면 종류별 기본값 (JS의 wait ?? base.wait_s)
    speed = base["speed"] if speed is None else speed
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
    walk = float(d[0] + d[1])                                    # 끝점 ↔ 길 노드 걷는 거리 합
    rise = abs(z5[1] - z5[0]) if z5 else None                    # [v6.2] a·b 높이 차 (DEM 5m)
    if typ == "vertical":                                        # [v6.2] 수직 엘리베이터 = 대기 + 높이 차 ÷ 오르내리는 속도 + 끝점 걷기
        if rise is None:
            log(f"  !! {r['name']}: DEM 이 a·b 를 덮지 않아 높이 차를 잴 수 없음 → 수직 엘리베이터 시간을 계산할 수 없어 건너뜀 (좌표·DEM 폴더 확인)")
            no_height.append(r["name"])
            continue
        if z5[0] > z5[1] + 0.5:
            log(f"  !! {r['name']}: a(아래 끝)가 b(위 끝)보다 {z5[0] - z5[1]:.1f}m 높음 → a·b 가 바뀌었는지 확인 (시간은 높이 차 크기로 계산)")
        if rise < 1.0:
            log(f"  !! {r['name']}: 높이 차 {rise:.1f}m → a·b 가 같은 높이이거나 DEM 이 평평하게 잡음. 좌표 확인")
        if straight > 50:
            log(f"  !! {r['name']}: 수직 엘리베이터 a·b 직선 {straight:.0f}m → a·b 사이를 수평으로 가는 시간은 넣지 않음 (높이 차만). 데크가 길면 시간이 짧게 잡힘, 경사형(elevator)인지 확인")
        if speed > 3:
            log(f"  !! {r['name']}: speed {speed:g}m/s 는 수직 엘리베이터가 오르내리는 속도로는 큼 (v6.1 까지는 '직선거리 ÷ speed' 였음) → 비우면 기본 {base['speed']:g}m/s")
        t = wait + rise / speed + walk / C.ELDER_SPEED
        ref = f", DEM 1m 로는 {abs(z1[1] - z1[0]):.1f}m (참고)" if z1 else ""
        log(f"  시설 {r['name']} [{typ}, {r.get('status')}] 높이 차 {rise:.1f}m (a {z5[0]:.1f}m → b {z5[1]:.1f}m, DEM 5m{ref}), "
            f"통과 {t / 60:.1f}분 = 대기 {wait:g}초 + 높이 {rise:.1f}m ÷ {speed:g}m/s + 끝점 걷기 {walk:.1f}m ÷ {C.ELDER_SPEED:g}m/s (a·b 직선 {straight:.0f}m)")
    else:
        t = wait + straight / speed + walk / C.ELDER_SPEED
        log(f"  시설 {r['name']} [{typ}, {r.get('status')}] 길이 {straight:.0f}m, 통과 {t / 60:.1f}분 (대기 {wait:g}초, {speed:g}m/s)"
            + (f", 높이 차 {rise:.1f}m (DEM 5m, 참고)" if rise is not None else ""))
    fac.append((r["name"], (r.get("status") or "planned").strip().lower(), (int(na), int(nb_), float(t), straight + walk),
                {"rise": round(rise, 1) if rise is not None else "", "pass": round(float(t), 1), "wait": float(wait)}))

if not fac:                                                      # [v6.1a] 좌표가 찬 시설이 모두 범위 밖 → 실패로 멈추지 않고 결과 없이 끝냄
    if no_height:                                                # [v6.2]
        log(f"좌표가 채워진 시설 {len(out_of_data) + len(no_height)}곳을 모두 건너뜀 (길 자료 범위 밖 {len(out_of_data)}곳, "
            f"높이 차를 잴 수 없는 수직 엘리베이터 {len(no_height)}곳) → 09 결과 없음")
    else:
        log(f"좌표가 채워진 시설 {len(out_of_data)}곳이 모두 길 자료 범위 밖 → 09 결과 없음 (그 구 자료를 받은 뒤 다시)")
    raise SystemExit(0)
if out_of_data:
    log(f"  길 자료 범위 밖이라 건너뛴 시설 {len(out_of_data)}곳: {', '.join(out_of_data)}")
if no_height:
    log(f"  높이 차를 잴 수 없어 건너뛴 수직 엘리베이터 {len(no_height)}곳: {', '.join(no_height)}")
scen = [(n, [x]) for n, _, x, _ in fac]                          # 시나리오 = 시설 하나씩
cand = [x for n, st, x, _ in fac if st != "existing"]            # ALL 에는 이미 있는 시설 제외
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
REP = rep_mode() == C.BUILDING_ATTR_MODE                         # [v6.2] 연면적은 대표 방식만 (05 와 같음)
DT = "medical" if "medical_hbi" in b else (targets(b)[0] if targets(b) else None)   # [v6.2] 연면적은 05 행정동 표와 같은 목적지만
n_single = len(fac)                                              # scen 앞쪽 n_single 개 = 시설 하나씩, 그 뒤 = ALL
in_all = [st != "existing" for _, st, _, _ in fac]               # 시설 i 가 ALL 에 들어가는지
pre_w = {}                                                       # [v6.2] 목적지별 설치 전 휠체어 (왕복 시간, 길 길이) — 시나리오마다 같음
R = []                                                           # 시나리오·목적지별 계산값 (연면적 가림은 모두 계산한 뒤)
f = lambda v, d=3: round(v, d) if np.isfinite(v) else ""
for si, (name, extra) in enumerate(scen):
    for T in tg:
        te0, tfl = b[f"{T}_t_elder"], b[f"{T}_t_flat"]          # 설치 전 고령자 왕복, 평지 가정 왕복 (초)
        tw0 = b[f"{T}_t_wheel"]
        r = run_with_extra(N, e, s, dest[T], extra, wheel_dist=True)   # 설치 후 (lib/model.py)
        te1 = np.full(len(node), np.nan); tw1 = np.full(len(node), np.nan); dw1 = np.full(len(node), np.nan)
        te1[ok0] = r["t_elder"][node[ok0]]
        tw1[ok0] = r["t_wheel"][node[ok0]]
        dw1[ok0] = r["d_wheel"][node[ok0]]
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
        # [v6.2] 고령자 단축 문턱별 건물 수
        nsv = [int((ok & (saved >= k)).sum()) for k in C.SAVED_BANDS_S]
        n_any = int(((ok & (saved >= C.ANY_ELDER_S)) | wben).sum())   # [10/12] 고령자 30초 이상 또는 휠체어 1분 이상(새 도달 포함)
        # [v6.2] 휠체어 길 길이 감소: 휠체어 왕복 시간이 준 건물의 (설치 전 길 길이 − 설치 후), 가는 길·오는 길 평균 (m)
        if T not in pre_w:
            r0 = run_with_extra(N, e, s, dest[T], [], wheel_dist=True, modes=("wheel",))
            pre_w[T] = (r0["t_wheel"], r0["d_wheel"])
        tw0b = np.full(len(node), np.nan); dw0 = np.full(len(node), np.nan)
        tw0b[ok0] = pre_w[T][0][node[ok0]]
        dw0[ok0] = pre_w[T][1][node[ok0]]
        cutm = ok0 & np.isfinite(tw0b) & np.isfinite(tw1) & (tw0b - tw1 > 1e-6)
        ncut = int(cutm.sum())
        cq = [round(float(np.percentile((dw0 - dw1)[cutm], q))) for q in C.WHEEL_CUT_Q] if ncut >= C.WHEEL_CUT_MIN else [""] * len(C.WHEEL_CUT_Q)
        info = fac[si][3] if si < n_single else {"rise": "", "pass": ""}
        R.append(dict(si=si, name=name, T=T, ben=ben, ex_hi=ex_hi, saved=saved, nb=nb, n_hi=int(ex_hi.sum()),
                      row=[name, T, nb, None, f(float(np.mean(saved[ben])) / 60 if nb else np.nan, 2),
                           f(float(np.percentile(saved[ben], 95)) / 60 if nb >= C.QUANT_MIN else np.nan, 2), round(float(saved[ben].sum()) / 60, 1),
                           f(hb), f(ha), int(newly.sum()), int(wben.sum()), int(ex_hi.sum()), None, int(ex_mid.sum())]
                          + nsv + [ncut] + cq + [info["rise"], info["pass"], n_any]))
        log(f"  {name} · {T}: 수혜 건물 {nb:,}동, 평균 {np.mean(saved[ben]) / 60 if nb else 0:.1f}분 단축, 휠체어 새로 도달 {int(newly.sum())}동"
            f" · 고령자 {'·'.join(f'{k:g}' for k in C.SAVED_BANDS_S)}초 이상 {'·'.join(str(x) for x in nsv)}동"
            f" · 휠체어 시간이 준 건물 {ncut}동" + (f" (길 길이 감소 중앙값 {cq[len(cq) // 2]}m)" if ncut >= C.WHEEL_CUT_MIN else "")
            + f" · 고령자 {C.ANY_ELDER_S:g}초 또는 휠체어 1분 이상 {n_any}동")
        # 격자별 (수혜 건물 MIN_COUNT 이상, 연면적 없음). [10/12] 평균 단축은 아래 5 에서 가림을 정한 뒤 씀
        if nb:
            bi = np.flatnonzero(ben)
            key = gx[bi] * 10**7 + gy[bi]
            u, inv = np.unique(key, return_inverse=True)
            cnt = np.bincount(inv)
            ms = np.bincount(inv, saved[bi]) / cnt / 60
            R[-1]["cells"] = [((u[k] // 10**7 + 0.5) * C.GRID, (u[k] % 10**7 + 0.5) * C.GRID, int(cnt[k]), round(float(ms[k]), 2), bi[inv == k])
                              for k in np.where(cnt >= C.MIN_COUNT)[0]]

# ── 3-1. [v6.2] 대기시간 비교: 시설 하나씩, 기준 목적지(DT)만, 대기 = WAIT_SENS_S 로 바꿔 수혜 건물 수 ─
wrows = []
DTw = "medical" if "medical_hbi" in b else (targets(b)[0] if targets(b) else None)
if DTw in tg and getattr(C, "WAIT_SENS_S", None):
    te0, tw0 = b[f"{DTw}_t_elder"], b[f"{DTw}_t_wheel"]
    w0 = np.where(np.isfinite(tw0), tw0, np.inf)
    for fname, _, (na, nb_, t0, ln), info in fac:
        for ws in C.WAIT_SENS_S:
            t1 = t0 - info["wait"] + ws
            r = run_with_extra(N, e, s, dest[DTw], [(na, nb_, t1, ln)])
            te1 = np.full(len(node), np.nan); tw1 = np.full(len(node), np.nan)
            te1[ok0] = r["t_elder"][node[ok0]]; tw1[ok0] = r["t_wheel"][node[ok0]]
            okw = ok0 & np.isfinite(te0) & np.isfinite(te1)
            sv = np.where(okw, te0 - te1, 0.0)
            w1 = np.where(np.isfinite(tw1), tw1, np.inf)
            wb = ok0 & ((~np.isfinite(w0) & np.isfinite(w1)) | (np.isfinite(w0) & (w0 - w1 >= C.BENEFIT_MIN_S)))
            wrows.append([fname, DTw, ws, round(float(t1), 1), int((okw & (sv >= C.BENEFIT_MIN_S)).sum()), int((okw & (sv >= 30)).sum()), int(wb.sum())])
        log(f"  대기시간 비교 {fname} · {DTw}: " + ", ".join(f"{r_[2]:g}초 → 수혜 {r_[4]}동·휠체어 {r_[6]}동" for r_ in wrows[-len(C.WAIT_SENS_S):]))

# ── 4. [v6.2] 연면적 가림 ─────────────────────────────────
#  연면적은 DT·REP 만 (05 와 같은 목적지·대표 방식). 값마다 그 건물 집합 S 를 두고, 이미 공개한 집합과 05 가 낼 수 있는 집합
#  (summary·동의 분석 건물·HBI 1.8 이상·왕복 추가 문턱, 동 전체)을 모아 둔 POOL 과 견줌:
#   ① 0채면 0, 1~4채면 빈 칸  ② S 를 품는 집합 P 에서, 또는 S 에서, 서로 겹치지 않는 공개 부분집합 몇 개를 빼면 1~4채가 남으면 빈 칸
#      (짝 하나 빼기, summary − 공개된 동 합, ALL − 시설 하나씩의 합 모두 여기에 들어감)
#   ③ 가렸지만 5채 이상인 동·시설 줄이 있으면, 그것을 품는 summary·ALL 줄도 빈 칸 (빼기로 가린 값을 되살리지 않게)
MC = C.MIN_COUNT
hiT = (np.where(np.isfinite(b[f"{DT}_hbi"]), b[f"{DT}_hbi"], -1) >= C.HBI_BANDS[1]) if DT else None   # 05 의 'HBI 1.8 이상' 집합
anaT = (U & np.isfinite(b[f"{DT}_hbi"])) if DT else None                                               # 05 의 분석 건물
POOL = []                                                        # 정렬된 건물 번호 배열들
if REP and DT:
    #  05 가 실제로 낸 연면적 값만 (output 의 summary.csv·dong_hbi.csv 에서 빈 칸이 아닌 것). 파일이 없으면 낼 수 있는 것을 모두 넣음 (보수적)
    from lib.mapping import band_tag
    add5 = (b[f"{DT}_t_elder"] - b[f"{DT}_t_flat"]) / 60          # 05 의 왕복 추가 시간(분)
    sm5 = {r["metric"]: r["value"] for r in read_csv(os.path.join(C.OUTPUT, "summary.csv")) if r.get("target") == DT}
    dg5 = {r["adm_cd"]: r for r in read_csv(os.path.join(C.OUTPUT, "dong_hbi.csv"))}
    have5 = bool(sm5)
    pub5 = lambda v: (not have5) or (v not in ("", None))
    fam = [(anaT, sm5.get("분석 건물 연면적 합(㎡)")), (anaT & hiT, sm5.get(f"HBI {C.HBI_BANDS[1]} 이상 건물의 연면적 합(㎡, 고령인구 배분용)"))] + \
          [(anaT & (add5 >= mb), sm5.get(f"왕복 추가 {mb:g}분 이상 건물의 연면적 합(㎡)")) for mb in C.MIN_BANDS]
    POOL += [np.flatnonzero(m) for m, v in fam if pub5(v)]
    if which is not None:
        for k, code in enumerate(dcode):
            ink, r5 = which == k, dg5.get(code, {})
            if have5 and not r5:                                 # 05 동 표에 없는 동 (분석 건물 5채 미만)
                continue
            dfam = [(U & ink, r5.get("weight_all")), (anaT & hiT & ink, r5.get("weight_high"))] + \
                   [(anaT & (add5 >= mb) & ink, r5.get(f"weight_{band_tag(mb)}")) for mb in C.MIN_BANDS]
            POOL += [np.flatnonzero(m) for m, v in dfam if pub5(v)]
    POOL = [q for q in POOL if len(q)]


NB = len(X)


def mask_of(S):
    """건물 번호 배열 → 참/거짓 표시 배열 (교집합 크기를 q 길이만큼만 세려고)"""
    m = np.zeros(NB, bool)
    m[S] = True
    return m


def leak_big(nB, subs):
    """크기 nB 인 집합에서 서로 겹치지 않는 부분집합(subs) 몇 개를 빼면 1~4채가 남는가 (lib/expose.py)"""
    return removal_leak(nB, subs, MC)


def publishable(S, pool=None):
    """S 의 값을 내도 되는가: 0채면 됨, 1~4채면 안 됨, pool(기본 = 연면적 POOL)의 공개 집합과 빼서 1~4채가 남으면 안 됨"""
    pool = POOL if pool is None else pool
    n = len(S)
    if n == 0:
        return True
    if n < MC:
        return False
    Sm, subs, sups = mask_of(S), [], []
    for q in pool:
        k = int(Sm[q].sum())
        if k == len(q) and len(q) < n:
            subs.append(q)
        elif k == n and len(q) > n:
            sups.append(q)
    if leak_big(n, subs):
        return False
    for P in sups:
        Pm = mask_of(P)
        if leak_big(len(P), [q for q in pool if len(q) < len(P) and int(Pm[q].sum()) == len(q)] + [S]):
            return False
    return True


wsum = lambda m: round(float(b["weight"][m].sum()))
blanked = set()                                                  # 가렸지만 5채 이상인 줄: (시나리오, 목적지, 종류, 동 번호 또는 None)
singles_in_all = [sj for sj in range(n_single) if in_all[sj]]
for it in R:                                                     # scen 순서 = 시설 하나씩 먼저, ALL 마지막. 줄마다 동 → summary
    si, T, ben, ex_hi = it["si"], it["T"], it["ben"], it["ex_hi"]
    W = REP and T == DT
    is_all = si >= n_single

    def decide(m, kind, k, need_min):
        """집합 m 의 연면적을 낼지. need_min = 5채 미만이면 0 이어도 빈 칸 (탈출 연면적은 v5 부터 그렇게 냄)"""
        S = np.flatnonzero(m)
        if not W or (need_min and len(S) < MC):
            return False
        ok = not (is_all and any((sj, T, kind, k) in blanked for sj in singles_in_all))                  # ③ 시설 하나를 가렸으면 ALL 도
        ok = ok and not (k is None and any(key[:3] == (si, T, kind) and key[3] is not None for key in blanked))   # ③ 동 줄을 가렸으면 summary 도
        ok = ok and publishable(S)
        if ok and len(S):
            POOL.append(S)
        elif not ok and len(S) >= MC:
            blanked.add((si, T, kind, k))                        # ③ 으로 가린 줄도 넣어 위로 전파 (동 → summary, 시설 → ALL)
        return ok
    if which is not None:
        for k, code in enumerate(dcode):
            m = ben & (which == k)
            if m.sum() < MC:
                continue
            mx = ex_hi & (which == k)
            okw, okx = decide(m, "ben", k, False), decide(mx, "ex", k, True)
            drows.append([it["name"], T, code, int(m.sum()), wsum(m) if okw else "", round(float(wall[k])) if W else "",
                          round(float((b["weight"][m] * it["saved"][m] / 60).sum()), 1) if okw else "", wsum(mx) if okx else ""])
            it.setdefault("dkeys", []).append(k)
    okw, okx = decide(ben, "ben", None, False), decide(ex_hi, "ex", None, True)
    it["row"][3] = wsum(ben) if okw else ""
    it["row"][12] = wsum(ex_hi) if okx else ""
    summ.append(it["row"])
# ── 5. [10/12] 시간 값 가림 ─────────────────────────────────
#  시간 값(평균·95% 분위 단축, 단축 분 합, 설치 전후 HBI, 격자 평균 단축)은 대표 방식에서만 냄 (방식끼리 수혜 집합 차가 몇 채일 수 있어서,
#  연면적과 같은 이유). 목적지마다 POOL_T 에 이미 낸 시간 값의 건물 집합을 모으고 (HBI 는 05 격자·행정동 HBI 평균 집합도),
#  줄마다 수혜 집합 S 를 연면적과 같은 검사(publishable)로 봄. 시설 하나씩 → ALL 순서, 줄마다 summary → 격자
T_COLS = (4, 5, 6, 7, 8)                                         # mean_saved_min, saved_p95_min, sum_saved_bld_min, hbi_before, hbi_after
POOL_T = {}
for T in tg:
    pt = []
    if REP:
        vT = U & np.isfinite(b[f"{T}_hbi"])                      # 05 격자 집합 (경계 제외 + HBI 있음, 건물 MIN_COUNT 이상 칸)
        ia = np.flatnonzero(vT)
        ku, kinv = np.unique(gx[ia] * 10**7 + gy[ia], return_inverse=True)
        pt += [ia[kinv == k] for k in np.where(np.bincount(kinv) >= MC)[0]]
        if T == DT and which is not None:                        # 05 행정동 HBI 평균 집합
            pt += [q for q in (np.flatnonzero(vT & (which == k)) for k in range(len(dcode))) if len(q) >= MC]
    POOL_T[T] = pt
tblank = 0
for it in R:
    T, S = it["T"], np.flatnonzero(it["ben"])
    ok_t = REP and publishable(S, POOL_T[T])
    if ok_t and len(S):
        POOL_T[T].append(S)
    if not ok_t:
        tblank += any(it["row"][c] not in ("", None) for c in T_COLS)
        for c in T_COLS:
            it["row"][c] = ""
    for cx, cy, cn, cm, cS in it.get("cells", []):              # 격자 평균 단축: summary 를 낸 뒤 칸마다 (큰 칸부터가 아니라 순서대로, 보수적)
        okc = REP and publishable(cS, POOL_T[T])
        if okc:
            POOL_T[T].append(cS)
        grows.append([it["name"], T, cx, cy, cn, cm if okc else ""])
if tblank:
    log(f"  시간 값 가림: summary {tblank}줄의 평균·분위 단축·HBI 칸을 비움 "
        + ("(수혜 1~4채이거나 다른 시간 값과 빼면 1~4채 몫이 남음)" if REP else f"(대표 방식 {rep_mode()} 에서만 냄)"))
np.savez_compressed(os.path.join(C.WORK, "intervention_sets.npz"), x=X, y=Y, names=np.array([n for n, _ in scen]),   # [v6.2] 노출 검사용 (work, 반출 안 함)
                    rowkey=np.array([f"{it['si']}|{it['T']}" for it in R]),                                           # summary 줄 순서
                    drowkey=np.array([f"{it['si']}|{it['T']}|{k}" for it in R for k in it.get("dkeys", [])]),         # 동 표 줄 순서 (k = 동 번호)
                    dcode=np.array(dcode, dtype=str), which=which if which is not None else np.full(len(X), -1),
                    **{f"s{it['si']}_{it['T']}_{k}": it[k] for it in R for k in ("ben", "ex_hi")})

write_csv(os.path.join(C.OUTPUT, "intervention_summary.csv"),
          ["facility", "target", "n_benefit", "weight_benefit", "mean_saved_min", "saved_p95_min", "sum_saved_bld_min",
           "hbi_before", "hbi_after", "wheel_newly_reachable", "wheel_benefit",
           "n_exit_high", "weight_exit_high", "n_exit_mid"]
          + [f"n_saved_{k:g}s" for k in C.SAVED_BANDS_S] + ["wheel_cut_n"] + [f"wheel_cut_p{q:g}_m" for q in C.WHEEL_CUT_Q]
          + ["rise_m", "pass_s", "n_benefit_any"], summ)
write_csv(os.path.join(C.OUTPUT, "intervention_wait.csv"), ["facility", "target", "wait_s", "pass_s", "n_benefit", "n_saved_30s", "wheel_benefit"], wrows)
write_csv(os.path.join(C.OUTPUT, "intervention_grid.csv"), ["facility", "target", "cell_x", "cell_y", "n_benefit", "mean_saved_min"], grows)
write_csv(os.path.join(C.OUTPUT, "intervention_dong.csv"),
          ["facility", "target", "adm_cd", "n_benefit", "weight_benefit", "weight_all", "weight_x_saved_min", "weight_exit_high"], drows)
if not bd:
    log("  external/dong_boundary.geojson 없음 → intervention_dong.csv 는 머리 줄만")
log(f"완료 → output/intervention_summary.csv ({len(summ)}행), intervention_grid.csv ({len(grows)}행), intervention_dong.csv ({len(drows)}행)")
