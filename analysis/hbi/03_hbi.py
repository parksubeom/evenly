# -*- coding: utf-8 -*-
"""
03_hbi.py ─ [3일차] 집집마다 "언덕 부담 지수(HBI)" 계산

[실행]  python 03_hbi.py      (02_network.py 를 먼저 실행해야 함)
[HBI 란]
  HBI = 경사를 반영한 왕복 시간 ÷ 평지라고 가정한 왕복 시간   (같은 사람, 같은 목적지)
  1.0 = 평지와 같음,  1.5 = 체감상 1.5배 멂,  1.8 이상 = 고립 위험
[하는 일]
  1. 건물 레이어에서 주거용 건물(집) = 출발점, 의료시설·노유자시설 = 목적지를 골라냄
  2. 정류장·정거장(지하철역) 레이어 = 목적지, external/pharmacy.csv 의 약국 = 목적지
  2-1. 데이터 경계 근처 건물 표시 (edge 열 = 1). 04·05·06 은 이 건물들을 통계에서 뺍니다
  3. 각 건물을 가장 가까운 길 노드에 연결 (60m 넘으면 제외)
  4. 목적지 종류마다: 모든 집 → 가장 가까운 목적지 왕복 시간을 고령자/평지/휠체어로 계산
[결과] work/buildings_hbi.csv, work/buildings_hbi.gpkg  ← 건물 단위라 반출하지 않음 (QGIS에서 열어 확인만)
[결과 열 이름 읽는 법]  (medical 자리에 bus, elderly, pharmacy 가 올 수 있음)
  medical_hbi          : 의료시설 기준 HBI (왕복)
  medical_home_ratio   : 귀갓길(의료시설→집) 편도만의 배수
  medical_t_elder      : 고령자 왕복 시간(초), medical_t_flat : 평지 가정 왕복 시간(초)
  medical_wheel_ratio  : 휠체어 기준 배수 (계단 회피 포함)
"""
import os, csv, numpy as np
np.seterr(invalid="ignore", divide="ignore")    # 0÷0 같은 계산 경고 메시지 숨김 (결과는 NaN 으로 처리됨)
import config as C
from lib.qio import log, iter_layer, csv_points, write_points_gpkg, coverage_envelopes
from lib.qedge import edge_flags
from lib.qgraph import NearestIndex
from lib.netload import load
from lib.model import run_scenario

net = load()
nodes, e = net["nodes"], net["e"]
gi = np.where(net["giant"])[0]           # 가장 큰 연결망에 속한 노드 번호들
idx = NearestIndex(nodes[gi])            # 그 노드들에만 연결하도록 색인

def snap(xs, ys, maxd):
    """좌표 → 가장 가까운 연결망 노드 번호 (maxd m 넘으면 -1)"""
    d, i = idx.query(np.c_[xs, ys], maxd)
    return np.where(i >= 0, gi[np.maximum(i, 0)], -1), d

# 1. 건물 읽기 ─────────────────────────────────────────────
log("건물 레이어 읽기")
cu, ck, cf = C.COL["bld_use"], C.COL["bld_kind"], C.COL["bld_floor"]
H = {"x": [], "y": [], "floors": [], "area": []}    # 집(출발점) 정보
MED, ELD = [], []                                   # 의료시설, 노유자시설 좌표
nb = 0
for g, a in iter_layer("building", fields=[cu, ck, cf]):
    nb += 1
    use = str(a.get(cu) or "").upper()              # 용도 코드 (없으면 빈 문자열)
    kind = str(a.get(ck) or "").upper()             # 종류 코드
    p = g.PointOnSurface()                          # 건물 안쪽에 있는 대표점 (중심이 건물 밖에 찍히는 ㄷ자 건물 대비)
    if p is None:
        continue
    x, y = p.GetX(), p.GetY()
    if use in C.MEDICAL_USE:
        MED.append((x, y))
    if use in C.ELDERLY_USE:
        ELD.append((x, y))
    # 주거용이거나, 용도 칸이 비어 있는데 종류가 주택이면 → 집
    if use in C.RESIDENTIAL_USE or (not use.startswith("BDU") and kind in C.RESIDENTIAL_KIND):
        try:
            fl = float(a.get(cf) or 1)              # 층수 (비어 있으면 1층)
        except ValueError:
            fl = 1
        H["x"].append(x); H["y"].append(y)
        H["floors"].append(min(max(fl, 1), 60))     # 1~60층 범위로 제한
        H["area"].append(g.GetArea())               # 바닥 면적 (m²)
H = {k: np.array(v, float) for k, v in H.items()}   # 리스트 → numpy 배열
H["weight"] = H["floors"] * H["area"]               # 연면적 ≈ 거주 규모 (고령인구 배분에 사용)
H["node"], H["snap_d"] = snap(H["x"], H["y"], C.ORIGIN_SNAP_MAX)
log(f"  건물 {nb:,}개 중 주거 {len(H['x']):,}개 (네트워크 연결 {(H['node'] >= 0).mean():.1%})  ← 95% 이상이면 정상")
# 경계 효과: 데이터 가장자리 EDGE_BUFFER(m) 안쪽 건물 표시 (계산은 하되, 04·05 통계에서 제외)
H["edge"] = edge_flags(H["x"], H["y"], coverage_envelopes()).astype(float)
log(f"  데이터 경계 {C.EDGE_BUFFER}m 이내 건물 {int(H['edge'].sum()):,}개 → 통계에서 제외 예정 ({H['edge'].mean():.1%})")

# 2. 목적지 모으기 ─────────────────────────────────────────
bus = [(g.GetX(), g.GetY()) for g, _ in iter_layer("bus_stop") if g.GetGeometryName() == "POINT"]
# 지하철·철도 정거장 (점이면 그대로, 면이면 대표점)
STA = []
for g, _ in iter_layer("station"):
    p = g if g.GetGeometryName() == "POINT" else g.PointOnSurface()
    if p is not None:
        STA.append((p.GetX(), p.GetY()))
_, px, py = csv_points(os.path.join(C.EXTERNAL, "pharmacy.csv"))
PH = list(zip(px, py))
dest = {}                                           # {"medical": 노드번호배열, ...}
for name, pts in [("medical", MED + PH), ("pharmacy", PH), ("bus", bus), ("elderly", ELD), ("station", STA)]:
    if not pts:
        log(f"  목적지 없음: {name} (건너뜀)")
        continue
    a = np.array(pts)
    n, _ = snap(a[:, 0], a[:, 1], 100)              # 목적지는 100m 까지 허용
    n = n[n >= 0]
    if len(n):
        dest[name] = n
    log(f"  목적지 {name}: {len(n):,}곳")
if not dest:
    raise RuntimeError("목적지가 없습니다. 건물 용도코드나 external/pharmacy.csv 확인")
np.savez(os.path.join(C.WORK, "dest_nodes.npz"), **dest)      # 08_sensitivity.py 가 다시 씀

# 3. 목적지 종류별 계산 ────────────────────────────────────
N = len(nodes)
ok = H["node"] >= 0                                 # 길에 연결된 집만 계산
out = dict(H)                                       # 결과 표 (열이름 → 배열)

def put(arr):
    """노드별 결과 배열 → 집별 결과 배열 (각 집이 연결된 노드의 값을 가져옴)"""
    col = np.full(len(ok), np.nan)
    col[ok] = arr[H["node"][ok]]
    col[~np.isfinite(col)] = np.nan                 # 무한대(도달 불가) → NaN
    return col

def ratio(a, b):
    """a ÷ b. 단 b 가 0(목적지 바로 앞 집)이면 1.0"""
    return np.where(b == 0, 1.0, a / b)

for name, dn in dest.items():
    log(f"경로 계산: {name}")
    r = run_scenario(N, e, net["s5"], dn)           # 핵심 계산 (lib/model.py)
    for k, arr in r.items():
        out[f"{name}_{k}"] = put(arr)
    out[f"{name}_hbi"] = ratio(out[f"{name}_t_elder"], out[f"{name}_t_flat"])
    out[f"{name}_home_ratio"] = ratio(out[f"{name}_t_elder_back"], out[f"{name}_t_flat_back"])
    out[f"{name}_wheel_ratio"] = ratio(out[f"{name}_t_wheel"], out[f"{name}_t_wheel_flat"])
    h = out[f"{name}_hbi"]
    log(f"  HBI 중앙값 {np.nanmedian(h):.2f}, 1.8 이상 {np.nanmean(h >= C.HBI_BANDS[1]):.1%}, 도달불가 {np.isnan(h).mean():.1%}")
    # 기여도 분석용 ①: "계단 정보가 없었다면" (휠체어가 계단을 지날 수 있다고 가정)
    out[f"{name}_t_wheel_stairok"] = put(run_scenario(N, e, net["s5"], dn, stairs_passable_wheel=True)["t_wheel"])
    # 기여도 분석용 ②: DEM 1m 로 계산한 HBI (02_network.py --dem1m 을 했을 때만)
    if net["s1"] is not None:
        out[f"{name}_hbi_dem1"] = ratio(put(run_scenario(N, e, net["s1"], dn)["t_elder"]), out[f"{name}_t_flat"])

# 4. 저장 ─────────────────────────────────────────────────
keys = list(out.keys())
with open(os.path.join(C.WORK, "buildings_hbi.csv"), "w", newline="", encoding="utf-8-sig") as f:
    w = csv.writer(f)
    w.writerow(keys)
    for i in range(len(H["x"])):
        w.writerow([f"{out[k][i]:.4f}" if np.isfinite(out[k][i]) else "" for k in keys])
write_points_gpkg(os.path.join(C.WORK, "buildings_hbi.gpkg"), "buildings", H["x"], H["y"],
                  {k: v for k, v in out.items() if k.endswith(("_hbi", "_wheel_ratio", "_home_ratio")) or k == "edge"})
log("완료 → work/buildings_hbi.csv / .gpkg (QGIS에서 열어 확인 가능)")
