# -*- coding: utf-8 -*-
"""
[3일차] 출발점(주거 건물)·목적지 설정 → 언덕 부담 지수(HBI) 산출
 출발점: 수치지형도 건물 중 주거용(단독·공동주택)
 목적지: medical(의료시설+약국), bus(정류장), elderly(노유자시설), pharmacy(약국만)
 결과: work/buildings_hbi.gpkg (건물 단위, 반출 대상 아님)
"""
import os, pickle, numpy as np, pandas as pd, geopandas as gpd
from scipy.spatial import cKDTree
import config as C
from lib.io_utils import log, read_layer, load_points_csv
from lib.model import run_scenario

net = pickle.load(open(os.path.join(C.WORK, "network.pkl"), "rb"))
nodes, e = net["nodes"], net["edges"]
gi = np.where(nodes["giant"].values)[0] if "giant" in nodes else np.arange(len(nodes))
tree = cKDTree(nodes[["x", "y"]].values[gi])   # 최대 연결망 노드에만 연결

def snap(pts, maxd):
    xy = np.c_[pts.geometry.x, pts.geometry.y]
    d, i = tree.query(xy)
    return np.where(d <= maxd, gi[i], -1), d

log("건물 레이어 읽기")
b = read_layer("building")
use = b[C.COL["bld_use"]].astype(str).str.upper() if C.COL["bld_use"] in b else pd.Series("", index=b.index)
kind = b[C.COL["bld_kind"]].astype(str).str.upper() if C.COL["bld_kind"] in b else pd.Series("", index=b.index)
res_mask = use.isin(C.RESIDENTIAL_USE) | (~use.str.startswith("BDU") & kind.isin(C.RESIDENTIAL_KIND))
home = b[res_mask].copy()
home["floors"] = pd.to_numeric(home.get(C.COL["bld_floor"], 1), errors="coerce").fillna(1).clip(1, 60)
home["area"] = home.geometry.area
home["weight"] = home["floors"] * home["area"]          # 거주 규모 대리변수 (연면적 추정)
home["geometry"] = home.geometry.representative_point()
home["node"], home["snap_d"] = snap(home, C.ORIGIN_SNAP_MAX)
log(f"  주거 건물 {len(home):,}개 (네트워크 연결 {(home.node >= 0).mean():.1%})")

dest = {}
med = b[use.isin(C.MEDICAL_USE)].copy(); med["geometry"] = med.geometry.representative_point()
eld = b[use.isin(C.ELDERLY_USE)].copy(); eld["geometry"] = eld.geometry.representative_point()
bus = read_layer("bus_stop")
ph_path = os.path.join(C.EXTERNAL, "pharmacy.csv")
ph = load_points_csv(ph_path) if os.path.exists(ph_path) else gpd.GeoDataFrame(geometry=[], crs=C.TARGET_CRS)
for name, g in [("medical", pd.concat([med[["geometry"]], ph[["geometry"]]])), ("pharmacy", ph),
                ("bus", bus), ("elderly", eld)]:
    if len(g) == 0:
        log(f"  목적지 없음: {name} (건너뜀)"); continue
    n, _ = snap(gpd.GeoDataFrame(geometry=g.geometry.values, crs=C.TARGET_CRS), 100)
    n = n[n >= 0]
    if len(n): dest[name] = n
    log(f"  목적지 {name}: {len(n):,}곳")
if not dest:
    raise RuntimeError("목적지가 하나도 없습니다. 건물 용도 코드나 external/pharmacy.csv 확인")

N = len(nodes)
s = net["slope"]["dem5"]
out = home[["geometry", "floors", "area", "weight", "node", "snap_d"]].copy()
ok = out.node.values >= 0
for name, dn in dest.items():
    log(f"경로 계산: {name}")
    r = run_scenario(N, e, s, dn)
    for k, arr in r.items():
        col = np.full(len(out), np.nan); col[ok] = arr[out.node.values[ok]]
        col[~np.isfinite(col)] = np.nan
        out[f"{name}_{k}"] = col
    out[f"{name}_hbi"] = out[f"{name}_t_elder"] / out[f"{name}_t_flat"]            # 왕복 기준 (기본 지표)
    out[f"{name}_home_ratio"] = out[f"{name}_t_elder_back"] / out[f"{name}_t_flat_back"]  # 귀갓길(목적지→집) 편도
    out[f"{name}_wheel_ratio"] = out[f"{name}_t_wheel"] / out[f"{name}_t_wheel_flat"]
    h = out[f"{name}_hbi"]
    log(f"  HBI 중앙값 {h.median():.2f}, 1.8 이상 {(h >= C.HBI_BANDS[1]).mean():.1%}, 도달불가 {h.isna().mean():.1%}")
    # 기여도 분석용: 휠체어가 계단을 지날 수 있다고 가정한 시나리오
    r2 = run_scenario(N, e, s, dn, stairs_passable_wheel=True)
    col = np.full(len(out), np.nan); col[ok] = r2["t_wheel"][out.node.values[ok]]
    out[f"{name}_t_wheel_stairok"] = np.where(np.isfinite(col), col, np.nan)
    if "dem1" in net["slope"]:
        r3 = run_scenario(N, e, net["slope"]["dem1"], dn)
        col = np.full(len(out), np.nan); col[ok] = r3["t_elder"][out.node.values[ok]]
        out[f"{name}_hbi_dem1"] = col / out[f"{name}_t_flat"]

out = gpd.GeoDataFrame(out, geometry="geometry", crs=C.TARGET_CRS)
out.to_file(os.path.join(C.WORK, "buildings_hbi.gpkg"), driver="GPKG")
with open(os.path.join(C.WORK, "dest_nodes.pkl"), "wb") as f:
    pickle.dump(dest, f)
log("완료 → work/buildings_hbi.gpkg")
