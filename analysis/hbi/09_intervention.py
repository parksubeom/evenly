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
from lib.model import run_with_extra, route
from lib.expose import publishable as _publishable   # [v6.2] 연면적 빼기 노출 검사 ([v6.3] 함수는 lib/expose.py 로 옮김)

os.makedirs(C.OUTPUT, exist_ok=True)

# ── 0. 시설 목록 읽기 ─────────────────────────────────────
def fnum(v):
    """CSV 칸 → 숫자 (빈 칸이면 None). JS의 v === "" ? null : Number(v) 와 같음"""
    v = (v or "").strip()
    return float(v) if v else None

rows = [r for r in read_csv(os.path.join(C.EXTERNAL, "interventions.csv"))
        if all(fnum(r.get(k)) is not None for k in ("a_lon", "a_lat", "b_lon", "b_lat"))]   # 좌표 4개가 다 있는 행만
if not rows and not C.AUTO_CANDIDATES:                           # [v6.3] 후보 자동(mapping 의 auto_candidates)이면 시설 좌표가 없어도 계속
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
                {"rise": round(rise, 1) if rise is not None else "", "pass": round(float(t), 1), "wait": float(wait), "typ": typ}))

# ── 2. 행정동 준비 (05_export.py 와 같은 방식. [v6.3] 후보 이름에 쓰려고 후보 찾기 앞으로) ─────────────
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
    nk = next((k for k in polys[0][1] if k.upper() in ("ADM_NM", "NAME")), None)
    dname = [str(a.get(nk, "")) if nk else "" for _, a in polys]
    wall = np.array([b["weight"][(which == k) & U].sum() for k in range(len(polys))])   # 동 전체 주거 연면적 (경계 제외)

# ── 2-1. [v6.3] 후보 자동: 고립 위험 집이 가장 많은 격자 K곳(mapping 의 auto_candidates)에 시설을 놓아 봄 ─────────────
#  ① 기준 목적지(DT, 05 행정동 표와 같은 의료)에서 왕복이 RISK_MIN 분 이상 더 걸리는 집(고립 위험)이 많은 격자부터 (05 격자와 같은 건물·칸)
#  ② 그 집들의 고령자 최단 경로(가는 길·오는 길)마다 가파른 링크(계단, 경사 CAND_STEEP 이상)가 이어지는 구간을 잘라 셈
#     (구간이 수평 CAND_MAX_LEN_M 보다 길면 그 안에서 높이 차가 가장 큰 창). 지나는 집이 가장 많은 구간
#     (계단이 든 구간을 먼저, 없으면 경사 구간. 한 끝이 격자 가운데에서 CAND_RADIUS_M 안, 지나는 집 MIN_COUNT 이상, 높이 차 CAND_MIN_RISE_M 이상)
#  ③ 구간의 낮은 끝(a)·높은 끝(b) 을 시설 양 끝으로: 수평 CAND_VERTICAL_MAX_M 이하면 수직(대기 + 높이 차 ÷ 속도),
#     넘으면 경사형 엘리베이터(대기 + 길이 ÷ 속도). 봉천(사람이 넣은 시설)과 같은 식. 높이 = 02 의 노드 높이(DEM 5m)
#  ④ 다른 시설과 같은 계산 (목적지는 DT 만, ALL 에는 넣지 않음). 양 끝 좌표는 반출하지 않음 (work/intervention_candidates_ends.csv 만)
DT = "medical" if "medical_hbi" in b else (targets(b)[0] if targets(b) else None)
REP = rep_mode() == C.BUILDING_ATTR_MODE                         # [v6.2] 연면적·시간 값은 대표 방식만. [v6.3 검토] 후보 자동·건물 수 칸도 대표 방식만
gx = np.floor(X / C.GRID).astype(np.int64)
gy = np.floor(Y / C.GRID).astype(np.int64)
CANDS = []                                                       # 후보마다 정보 (반출 표·화면용)
if C.AUTO_CANDIDATES > 0 and DT in dest and C.RISK_MIN and not REP:
    log(f"  후보 자동: 대표 방식({rep_mode() or '정할 수 없음'})에서만 함 (방식끼리 같은 칸의 수를 빼서 몇 채가 드러나지 않게) → 이 방식은 건너뜀")
if C.AUTO_CANDIDATES > 0 and DT in dest and C.RISK_MIN and REP:
    from lib.model import directed, elder_time
    from lib.qgraph import Graph
    addT = (b[f"{DT}_t_elder"] - b[f"{DT}_t_flat"]) / 60
    vT = U & np.isfinite(b[f"{DT}_hbi"])
    riskT = vT & (addT >= C.RISK_MIN) & (node >= 0)
    ckey = gx * 10**7 + gy
    ku, kc = np.unique(ckey[vT], return_counts=True)
    kr = dict(zip(*np.unique(ckey[riskT], return_counts=True)))
    cells = sorted(((int(kr.get(k, 0)), int(c), int(k)) for k, c in zip(ku, kc) if c >= C.MIN_COUNT and kr.get(k, 0) >= C.MIN_COUNT),
                   key=lambda t: (-t[0], -t[0] / t[1]))[:C.AUTO_CANDIDATES * C.CAND_SEARCH]
    uu, vv, LL, ss_, st_ = directed(e, s)
    Ge = Graph(uu, vv, elder_time(LL, ss_, st_), N)
    _, pgo = Ge.dijkstra_pred(dest[DT], reverse=True)            # pgo[x] = x 에서 목적지 쪽으로 다음 노드 (가는 길)
    _, pbk = Ge.dijkstra_pred(dest[DT])                          # pbk[x] = 목적지에서 x 로 오는 길의 바로 앞 노드 (오는 길)
    eu, ev = e["u"].astype(np.int64), e["v"].astype(np.int64)
    pkey = np.minimum(eu, ev) * N + np.maximum(eu, ev)           # 링크 = 노드 쌍 (방향 없음)
    stp = e["is_stair"].astype(bool)
    sel = stp | (np.abs(s) >= C.CAND_STEEP)
    STEEP = {}                                                   # 노드 쌍 → 계단인가 (가파른 링크만)
    for q, isst in zip(pkey[sel].tolist(), stp[sel].tolist()):
        STEEP[q] = STEEP.get(q, False) or isst
    z5 = net["z5"]
    fac_nodes = [(x[0], x[1]) for _, _, x, _ in fac]

    def add_run(seq, h, runs):
        """경로의 이어진 가파른 구간 seq (노드 순서) 를 셈. 수평 길이가 CAND_MAX_LEN_M 를 넘으면 그 안에서 높이 차가 가장 큰 창
        (길이 상한 안)만 씀. 구간 이름 = (낮은 끝 노드, 높은 끝 노드)"""
        xy = nodes[seq]
        d = np.r_[0, np.cumsum(np.hypot(*np.diff(xy, axis=0).T))]   # 구간 처음부터 수평 거리
        zz = z5[seq]
        if not np.isfinite(zz).all():
            return
        lo_, hi_ = 0, len(seq) - 1
        if d[-1] > C.CAND_MAX_LEN_M:                             # 창: 시작점 i 마다 상한 안에서 가장 먼 j
            bestw, j = (-1.0, 0, 0), 0
            for i_ in range(len(seq)):
                j = max(j, i_)
                while j + 1 < len(seq) and d[j + 1] - d[i_] <= C.CAND_MAX_LEN_M:
                    j += 1
                if j > i_ and abs(zz[j] - zz[i_]) > bestw[0]:
                    bestw = (abs(zz[j] - zz[i_]), i_, j)
            if bestw[0] < 0:
                return
            lo_, hi_ = bestw[1], bestw[2]
        sub = seq[lo_:hi_ + 1]
        a_, b_ = (sub[0], sub[-1]) if z5[sub[0]] <= z5[sub[-1]] else (sub[-1], sub[0])
        rr = runs.setdefault((a_, b_), {"h": set(), "st": False, "nodes": set(sub)})
        rr["h"].add(h)
        rr["st"] = rr["st"] or any(STEEP.get(min(x0, x1) * N + max(x0, x1), False) for x0, x1 in zip(sub[:-1], sub[1:]))
    used_nodes = set()
    cand_mids = [(nodes[f0] + nodes[f1]) / 2 for f0, f1 in fac_nodes]   # 사람이 넣은 시설·앞 후보의 가운데점
    for nr, nc, k in cells:
        if len(CANDS) >= C.AUTO_CANDIDATES:
            break
        cx, cy = (k // 10**7 + 0.5) * C.GRID, (k % 10**7 + 0.5) * C.GRID
        runs = {}                                                # 구간 (낮은 끝, 높은 끝) → {"h": 지나는 집, "st": 계단이 든가, "len": 수평 길이}
        for h in np.flatnonzero(riskT & (ckey == k)).tolist():
            for P_ in (pgo, pbk):                                # 가는 길·오는 길의 노드 순서
                path, x = [int(node[h])], int(node[h])
                while P_[x] >= 0 and len(path) <= N:
                    x = int(P_[x])
                    path.append(x)
                cur = [path[0]]                                  # 이어지는 가파른 링크를 한 구간으로 (끊기면 새 구간)
                for x0, x1 in zip(path[:-1], path[1:]):
                    q = min(x0, x1) * N + max(x0, x1)
                    if q in STEEP:
                        cur.append(x1)
                        continue
                    if len(cur) > 1:
                        add_run(cur, h, runs)
                    cur = [x1]
                if len(cur) > 1:
                    add_run(cur, h, runs)
        best = None
        for (na_, nb2), rr in runs.items():
            nh_ = len(rr["h"])
            rise = float(z5[nb2] - z5[na_])
            near = min(np.hypot(*(nodes[na_] - (cx, cy))), np.hypot(*(nodes[nb2] - (cx, cy))))
            if nh_ < C.MIN_COUNT or near > C.CAND_RADIUS_M or rise < C.CAND_MIN_RISE_M or rr["nodes"] & used_nodes:
                continue
            if any(min(np.hypot(*(nodes[na_] - nodes[f0])), np.hypot(*(nodes[nb2] - nodes[f1]))) < 30 for f0, f1 in fac_nodes):
                continue                                         # 사람이 넣은 시설(봉천 등)과 같은 자리
            mid = (nodes[na_] + nodes[nb2]) / 2
            if any(np.hypot(*(mid - m0)) < C.CAND_MIN_GAP_M for m0 in cand_mids):
                continue                                         # [v6.3 검토] 앞 후보와 같은 길의 이웃 구간 (수혜 집이 겹침)
            score = (rr["st"], nh_, rise)                        # 계단이 든 구간 먼저, 지나는 집이 많은 순, 높이 차 큰 순
            if best is None or score > best[0]:
                best = (score, na_, nb2, rise, rr["nodes"], nh_)
        if best is None:
            log(f"  후보 격자 ({cx:.0f}, {cy:.0f}) 고립 위험 집 {nr}채: 지나는 가파른 구간이 없거나 앞 후보·사람이 넣은 시설과 같은 구간 → 다음 격자")
            continue
        (isst, nh, _), na_, nb2, rise, nds, _ = best
        nds = np.array(sorted(nds), np.int64)
        straight = float(np.hypot(*(nodes[nb2] - nodes[na_])))
        typ = "vertical" if straight <= C.CAND_VERTICAL_MAX_M else "elevator"
        base = C.FACILITY[typ]
        t = base["wait_s"] + (rise / base["speed"] if typ == "vertical" else straight / base["speed"])
        tw, lw = route(N, e, s, na_, nb2, mode="wheel")         # 지금 휠체어로 아래 끝 → 위 끝 (시간 최소 길의 길이)
        used_nodes |= set(nds.tolist())
        cand_mids.append((nodes[na_] + nodes[nb2]) / 2)
        nm = f"후보{len(CANDS) + 1}"
        kd = -1
        if which is not None:
            _, wc = points_in_polygons(np.array([cx]), np.array([cy]), polys)
            kd = int(wc[0])
        CANDS.append(dict(name=nm, cx=cx, cy=cy, n_bld=nc, n_risk=nr, stair=bool(isst), houses=nh, typ=typ, rise=rise, straight=straight,
                          t=t, wheel_now=(lw if np.isfinite(lw) else None), a=na_, b=nb2, dong=kd))
        fac.append((nm, "candidate", (na_, nb2, float(t), straight), {"rise": int(round(rise)), "pass": int(round(t, -1)), "wait": float(base["wait_s"]), "typ": typ}))
        # [v6.3 검토] 반출 칸은 높이 1m·길이 10m·통과 10초 단위 (0.1 단위면 공개 길·지형으로 양 끝 노드를 좁힐 수 있어서). 화면(work/logs)은 그대로
        log(f"  {nm}: 격자 ({cx:.0f}, {cy:.0f}){' ' + dname[kd] if kd >= 0 else ''} 고립 위험 집 {nr}채 → 그 집들의 길이 가장 많이 지나는 "
            f"{'계단' if isst else '경사'} 구간 (지나는 집 {nh}채), 높이 차 {rise:.1f}m · 수평 {straight:.0f}m → "
            f"{'수직' if typ == 'vertical' else '경사형'} 엘리베이터 통과 {t / 60:.1f}분, 지금 휠체어 길 "
            + (f"{lw:.0f}m" if np.isfinite(lw) else "없음 (계단만)"))
    if CANDS:
        from lib.qio import srs_from, TARGET
        from osgeo import osr as _osr
        dst = srs_from("EPSG:4326")
        dst.SetAxisMappingStrategy(_osr.OAMS_TRADITIONAL_GIS_ORDER)
        back = transformer(TARGET, dst)
        ends = []
        for c in CANDS:
            lon, lat = transform_xy(back, [nodes[c["a"], 0], nodes[c["b"], 0]], [nodes[c["a"], 1], nodes[c["b"], 1]])
            ends.append([c["name"], c["typ"], round(float(lon[0]), 6), round(float(lat[0]), 6), round(float(lon[1]), 6), round(float(lat[1]), 6),
                         round(c["rise"], 1), round(c["straight"], 1)])
        write_csv(os.path.join(C.WORK, "intervention_candidates_ends.csv"),          # 반출하지 않음 (work): 시설 양 끝 경위도
                  ["name", "type", "a_lon", "a_lat", "b_lon", "b_lat", "rise_m", "straight_m"], ends)
    log(f"  후보 자동: 고립 위험 집이 많은 격자 {len(cells)}곳을 보고 후보 {len(CANDS)}곳 (mapping 의 auto_candidates = {C.AUTO_CANDIDATES}, "
        f"고립 위험 = 왕복 {C.RISK_MIN:g}분 이상 더). 양 끝 좌표는 work 에만")

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
cand = [x for n, st, x, _ in fac if st not in ("existing", "candidate")]   # ALL 에는 이미 있는 시설·[v6.3] 자동 후보 제외
if cand:
    scen.append(("ALL(후보 전체)", cand))

# ── 3. 계산 ───────────────────────────────────────────────
summ, grows, drows = [], [], []
ok0 = U & (node >= 0)
REP = rep_mode() == C.BUILDING_ATTR_MODE                         # [v6.2] 연면적은 대표 방식만 (05 와 같음)
if not rep_mode():                                               # [10/12] 정할 수 없으면 연면적·시간 값을 비움
    log("!! 대표 방식을 정할 수 없어 연면적·시간 값 칸을 비웁니다 → python check.py 뒤 python run_all.py --modes auto,all")
# DT (위 2-1): [v6.2] 연면적은 05 행정동 표와 같은 목적지만
n_single = len(fac)                                              # scen 앞쪽 n_single 개 = 시설 하나씩, 그 뒤 = ALL
in_all = [st not in ("existing", "candidate") for _, st, _, _ in fac]   # 시설 i 가 ALL 에 들어가는지
is_cand = [st == "candidate" for _, st, _, _ in fac]             # [v6.3] 자동 후보 (목적지는 DT 만)
pre_w = {}                                                       # [v6.2] 목적지별 설치 전 휠체어 (왕복 시간, 길 길이) — 시나리오마다 같음
R = []                                                           # 시나리오·목적지별 계산값 (연면적 가림은 모두 계산한 뒤)
f = lambda v, d=3: round(v, d) if np.isfinite(v) else ""
for si, (name, extra) in enumerate(scen):
    for T in tg:
        if si < n_single and is_cand[si] and T != DT:            # [v6.3] 자동 후보는 기준 목적지만 (시간을 아끼려고)
            continue
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
        R.append(dict(si=si, name=name, T=T, ben=ben, ex_hi=ex_hi, saved=saved, nb=nb, n_hi=int(ex_hi.sum()), n_any=n_any,
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
    for fname, st_, (na, nb_, t0, ln), info in fac:
        if st_ == "candidate":                                   # [v6.3] 자동 후보는 대기시간 비교 안 함
            continue
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
    from lib.bload import risk_cell_mask
    rc5 = risk_cell_mask(b, DT, U)                               # [v6.3] 05 독거노인 추정의 '고립 위험 격자 안 집' (연면적 비율이 드러나는 집합)
    if which is not None:
        for k, code in enumerate(dcode):
            ink, r5 = which == k, dg5.get(code, {})
            if have5 and not r5:                                 # 05 동 표에 없는 동 (분석 건물 5채 미만)
                continue
            dfam = [(U & ink, r5.get("weight_all")), (anaT & hiT & ink, r5.get("weight_high"))] + \
                   [(anaT & (add5 >= mb) & ink, r5.get(f"weight_{band_tag(mb)}")) for mb in C.MIN_BANDS] + \
                   [(U & ink & rc5, r5.get("alone65_riskcell_est") if have5 else "x")]   # [v6.3] 파일이 없으면 보수적으로 넣음
            POOL += [np.flatnonzero(m) for m, v in dfam if pub5(v)]
        # [v6.3] 05 의 종류별 집당 배분 어르신 (단독·다가구 / 공동주택): 연면적을 낸 동들의 그 종류 고립 위험 집 (연면적 비율이 드러나는 집합)
        if C.RISK_MIN and "htype" in b and C.RISK_MIN in C.MIN_BANDS:
            ht9 = np.nan_to_num(b["htype"]).astype(int)
            tagR = f"weight_{band_tag(C.RISK_MIN)}"
            pubk = np.isin(which, [k for k, code in enumerate(dcode) if (not have5) or dg5.get(code, {}).get(tagR) not in ("", None)])
            for lab, sel in (("단독·다가구", np.isin(ht9, [1, 2])), ("공동주택", np.isin(ht9, [3, 4, 5]))):
                key_ = next((k_ for k_ in sm5 if f"{lab} 집당 배분 어르신" in k_), None)
                if (not have5) or (key_ and sm5[key_] not in ("", None)):
                    POOL.append(np.flatnonzero(anaT & (add5 >= C.RISK_MIN) & pubk & sel))
    POOL = [q for q in POOL if len(q)]


NB = len(X)


def publishable(S, pool=None):
    """S 의 값을 내도 되는가: 0채면 됨, 1~4채면 안 됨, pool(기본 = 연면적 POOL)의 공개 집합과 빼서 1~4채가 남으면 안 됨 (lib/expose.py)"""
    return _publishable(S, POOL if pool is None else pool, NB, MC)


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
POOL_T = {}                                                      # HBI 값(설치 전 HBI)의 공개 집합: 목적지마다 (목적지가 다르면 HBI 가 다른 양)
POOL_SV = []                                                     # [10/12 검토] 단축 값의 공개 집합: 목적지를 합쳐 하나 (같은 건물의 단축 시간은 목적지가 달라도
                                                                 #   같은 경우가 많아 목적지끼리 빼면 몇 채 몫이 나옴, 독립 검토가 4채 4.7분 재현)
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
tb_single = False                                                # [10/12 검토] ③ 시설 하나 줄을 5채 이상인데 가렸으면 ALL 도 (빼기로 되살리지 않게)
tb_cells = set()                                                 # 시설 하나에서 5채 이상인데 가린 격자 칸 (cx, cy) → ALL 의 같은 칸도
for it in R:
    T, S = it["T"], np.flatnonzero(it["ben"])
    is_all = it["si"] >= n_single
    ok_t = REP and not (is_all and tb_single) and publishable(S, POOL_SV) and publishable(S, POOL_T[T])
    if ok_t and len(S):
        POOL_SV.append(S)
        POOL_T[T].append(S)
    if not ok_t:
        tblank += any(it["row"][c] not in ("", None) for c in T_COLS)
        for c in T_COLS:
            it["row"][c] = ""
        if not is_all and len(S) >= MC and in_all[it["si"]]:
            tb_single = True
    for cx, cy, cn, cm, cS in it.get("cells", []):              # 격자 평균 단축: summary 를 낸 뒤 칸마다 (단축 값이라 POOL_SV)
        okc = REP and not (is_all and (cx, cy) in tb_cells) and publishable(cS, POOL_SV)
        if okc:
            POOL_SV.append(cS)
        elif not is_all and len(cS) >= MC and in_all[it["si"]]:
            tb_cells.add((cx, cy))
        grows.append([it["name"], T, cx, cy, cn, cm if okc else ""])
if tblank:
    log(f"  시간 값 가림: summary {tblank}줄의 평균·분위 단축·HBI 칸을 비움 "
        + ("(수혜 1~4채이거나 다른 시간 값과 빼면 1~4채 몫이 남음)" if REP else f"(대표 방식 {rep_mode() or '(정할 수 없음)'} 에서만 냄)"))
# ── 6. [10/12 판정] 시설 단위 건물 수 1~4 → "5채 미만" (0 은 그대로). ALL 줄은 시설 하나 줄을 가린 칸이면 빈 칸
#  (ALL − 다른 시설들로 가린 수가 되살아나지 않게. ALL 도 1~4 면 "5채 미만")
CNT_COLS = (2, 9, 10, 11, 13, 14, 15, 16, 22)                   # n_benefit, wheel_newly_reachable, wheel_benefit, n_exit_high, n_exit_mid,
                                                                 # n_saved_30s, n_saved_60s, wheel_cut_n, n_benefit_any
small = lambda v: isinstance(v, (int, np.integer)) and 0 < int(v) < MC
masked_single = set()                                            # (목적지, 칸) 시설 하나 줄에서 가린 것
cblank = 0
for it in R:
    is_all = it["si"] >= n_single
    for c in CNT_COLS:
        v = it["row"][c]
        if small(v):
            it["row"][c] = C.SMALL_LABEL
            cblank += 1
            if not is_all and in_all[it["si"]]:
                masked_single.add((it["T"], c))
        elif is_all and (it["T"], c) in masked_single and v not in ("", None, 0):
            it["row"][c] = ""
            cblank += 1
for w_ in wrows:                                                 # 대기시간 비교 (시설 하나씩): n_benefit, n_saved_30s, wheel_benefit
    for c in (4, 5, 6):
        if small(w_[c]):
            w_[c] = C.SMALL_LABEL
            cblank += 1
if cblank:
    log(f"  건물 수 가림: {cblank}칸을 '{C.SMALL_LABEL}' 또는 빈 칸으로 (시설 단위 건물 수 1~4)")
if not REP:                                                      # [v6.3 검토] 대표 방식 밖: 건물 수 칸도 비움 (방식끼리 같은 시설·칸의 수를 빼면 1~4채가 드러남)
    for it in R:
        for c in CNT_COLS:
            it["row"][c] = ""
    for w_ in wrows:
        w_[4] = w_[5] = w_[6] = ""
    for g_ in grows:
        g_[4] = ""
    for d_ in drows:
        d_[3] = ""
    log(f"  대표 방식({rep_mode() or '정할 수 없음'})이 아니라 건물 수 칸을 비움 (시설 높이·통과만)")
np.savez_compressed(os.path.join(C.WORK, "intervention_sets.npz"), x=X, y=Y, names=np.array([n for n, _ in scen]),   # [v6.2] 노출 검사용 (work, 반출 안 함)
                    rowkey=np.array([f"{it['si']}|{it['T']}" for it in R]),                                           # summary 줄 순서
                    drowkey=np.array([f"{it['si']}|{it['T']}|{k}" for it in R for k in it.get("dkeys", [])]),         # 동 표 줄 순서 (k = 동 번호)
                    dcode=np.array(dcode, dtype=str), which=which if which is not None else np.full(len(X), -1),
                    **{f"s{it['si']}_{it['T']}_{k}": it[k] for it in R for k in ("ben", "ex_hi")})

# ── 7. [v6.3] 후보·선정지 비교표 (격자 단위, 시설 양 끝 좌표 없음) ─────────────
#  자동 후보와 사람이 넣은 시설(봉천 등)을 같은 표에: 격자 가운데·동, 격자 고립 위험 집 수(05 격자 표와 같은 값), 시설 종류·높이 차·길이·통과,
#  지금 휠체어 길(아래 끝 → 위 끝), 기준 목적지(DT)의 수혜(고령자 30초 또는 휠체어 1분, 새 도달 포함)·휠체어 수혜·평균 단축 (summary 와 같은 가림),
#  1억 원당 수혜 (수혜 ÷ facility_cost_eok, 수혜 1~4채면 빈 칸), 가장 가까운 기존 이동편의시설까지(50m 단위), 처방 (mapping 의 cand_* 규칙)
EXIST = []                                                        # 기존 이동편의시설 (분석 좌표)
for r_ in read_csv(os.path.join(C.EXTERNAL, "existing_facilities.csv")):
    if str(r_.get("status", "")).strip().lower().startswith("existing") and fnum(r_.get("lon")) is not None and fnum(r_.get("lat")) is not None:
        EXIST.append((fnum(r_["lon"]), fnum(r_["lat"])))
for r_ in rows:
    if str(r_.get("status", "")).strip().lower() == "existing":
        EXIST.append((fnum(r_["a_lon"]), fnum(r_["a_lat"])))
EX = np.array(transform_xy(tf, [p_[0] for p_ in EXIST], [p_[1] for p_ in EXIST])).T if EXIST else np.zeros((0, 2))
ckey_all = gx * 10**7 + gy
vD = (U & np.isfinite(b[f"{DT}_hbi"])) if DT else np.zeros(len(X), bool)
addD = ((b[f"{DT}_t_elder"] - b[f"{DT}_t_flat"]) / 60) if DT else None
RR = C.CAND_RULE


def prescribe(per100m, near_m):
    """[10/13 판정] 500m 안 기존 시설 → 연계 / 1억 원당 수혜 ≥ cand_min_per100m(기본 5) → 시설 검토 / 그 밖 → 정비 + 방문돌봄 (고립 위험 집 수 조건 없음)"""
    if near_m is not None and near_m <= RR["radius_m"]:
        return "기존 시설 연계"
    if per100m is not None and per100m >= RR["min_per100m"]:
        return "시설 검토"
    return "난간·쉼터·계단 정비 + 방문돌봄"


crows = []
if DT and (CANDS or any(not c_ for c_ in is_cand)):
    for si, (fname, st_, (na, nb_, t_, ln_), info) in enumerate(fac):
        it = next((x for x in R if x["si"] == si and x["T"] == DT), None)
        if it is None:
            continue
        c = next((x for x in CANDS if x["name"] == fname), None)
        if c:
            cx, cy, kd, typ = c["cx"], c["cy"], c["dong"], c["typ"]
            wn = c["wheel_now"]
        else:                                                    # 사람이 넣은 시설: 양 끝 노드 가운데가 든 격자
            mx_, my_ = (nodes[na] + nodes[nb_]) / 2
            cx, cy = (np.floor(mx_ / C.GRID) + 0.5) * C.GRID, (np.floor(my_ / C.GRID) + 0.5) * C.GRID
            kd = -1
            if which is not None:
                _, wc = points_in_polygons(np.array([cx]), np.array([cy]), polys)
                kd = int(wc[0])
            typ = info.get("typ", "")
            tw_, lw_ = route(N, e, s, na, nb_, mode="wheel")
            wn = lw_ if np.isfinite(lw_) else None
        kk = int(np.floor(cx / C.GRID)) * 10**7 + int(np.floor(cy / C.GRID))
        incell = vD & (ckey_all == kk)
        nbc = int(incell.sum())
        nrk = int((incell & (addD >= C.RISK_MIN)).sum()) if (nbc >= C.MIN_COUNT and C.RISK_MIN and REP) else ""
        n_any = it["n_any"]
        per = round(n_any / RR["cost_eok"], 2) if (n_any >= C.MIN_COUNT and REP) else None
        near = float(np.min(np.hypot(EX[:, 0] - cx, EX[:, 1] - cy))) if len(EX) else None
        row = it["row"]
        crows.append(["후보" if c else ("이미 있는 시설" if st_ == "existing" else "선정지·입력 시설"), fname,
                      dcode[kd] if kd >= 0 else "", dname[kd] if kd >= 0 else "", cx, cy, nbc if nbc >= C.MIN_COUNT else "", nrk,
                      typ, info["rise"], (int(round(ln_, -1)) if c else round(ln_)), info["pass"], round(wn / 10) * 10 if wn is not None else "없음",
                      row[22], row[14], row[10], row[4], per if per is not None else ("0" if (n_any == 0 and REP) else ""),
                      int(round(near / 50) * 50) if near is not None and near <= 3000 else "", prescribe(per, near) if REP else ""])
    log(f"  후보·선정지 비교표: {len(crows)}줄 (처방 규칙: 1억 원당 수혜 {RR['min_per100m']:g}동 이상 → 시설 검토, "
        f"{RR['radius_m']:g}m 안 기존 시설 → 연계, 그 밖 → 난간·쉼터·계단 정비 + 방문돌봄. 시설 1곳 {RR['cost_eok']:g}억 원 가정)")
    for r_ in crows:
        log(f"    {r_[1]}: {r_[3] or '동 모름'}, 고립 위험 {r_[7]}채, {r_[8]} 높이 {r_[9]}m, 수혜 {r_[13]} (고령자 30초 {r_[14]} · 휠체어 1분 {r_[15]}), 1억 원당 {r_[17] or '-'} → {r_[19] or '-'}")
write_csv(os.path.join(C.OUTPUT, "intervention_candidates.csv"),
          ["kind", "facility", "adm_cd", "adm_nm", "cell_x", "cell_y", "n_bld_cell", f"n_risk_{C.RISK_MIN:g}m" if C.RISK_MIN else "n_risk",
           "facility_type", "rise_m", "length_m", "pass_s", "wheel_now_m", "n_benefit_any", "n_saved_30s", "wheel_benefit", "mean_saved_min",
           "per100m", "existing_m", "prescription"], crows)

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
log(f"완료 → output/intervention_summary.csv ({len(summ)}행), intervention_grid.csv ({len(grows)}행), intervention_dong.csv ({len(drows)}행), "
    f"intervention_candidates.csv ({len(crows)}행)")
