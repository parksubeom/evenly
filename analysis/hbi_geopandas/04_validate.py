# -*- coding: utf-8 -*-
"""
[4일차] 검증과 데이터 기여도 분석
 1) 서울시 2025 선정지 재현 (external/sites.csv)
 2) 특정 구간 경로 재현·현장 실측 비교 (external/od_pairs.csv)
 3) 기여도: DEM 제외 / 계단 제외 / 큰 격자 집계 / DEM 1m 비교
 결과: output/validation_*.csv (집계·요약 통계만)
"""
import os, pickle, numpy as np, pandas as pd, geopandas as gpd
from scipy.stats import spearmanr, pearsonr
from scipy.spatial import cKDTree
import config as C
from lib.io_utils import log, load_points_csv
from lib.model import route

os.makedirs(C.OUTPUT, exist_ok=True)
b = gpd.read_file(os.path.join(C.WORK, "buildings_hbi.gpkg"))
net = pickle.load(open(os.path.join(C.WORK, "network.pkl"), "rb"))
nodes, e, s = net["nodes"], net["edges"], net["slope"]["dem5"]
T = "medical" if "medical_hbi" in b else [c[:-4] for c in b.columns if c.endswith("_hbi")][0]
H = f"{T}_hbi"
log(f"기준 목적지: {T}")

def grid_mean(df, size):
    gx = np.floor(df.geometry.x / size).astype(int); gy = np.floor(df.geometry.y / size).astype(int)
    g = df.assign(gx=gx, gy=gy).groupby(["gx", "gy"])
    t = g[H].agg(["mean", "count"]).reset_index()
    return t[t["count"] >= C.MIN_COUNT], gx, gy

# 1) 선정지 재현
cells, _, _ = grid_mean(b.dropna(subset=[H]), C.GRID)
cells["pct"] = cells["mean"].rank(pct=True)
sp = os.path.join(C.EXTERNAL, "sites.csv")
sites = load_points_csv(sp) if os.path.exists(sp) else []
if len(sites) == 0:
    log("external/sites.csv 좌표가 비어 있음 → 선정지 검증 건너뜀")
else:
    rows = []
    for _, r in sites.iterrows():
        rad = r.get("radius_m", 300) if pd.notna(r.get("radius_m", np.nan)) else 300
        near = b[b.distance(r.geometry) <= rad].dropna(subset=[H])
        m = near[H].mean() if len(near) else np.nan
        pct = (cells["mean"] < m).mean() if np.isfinite(m) else np.nan
        rows.append(dict(name=r["name"], n_bld=len(near), hbi_mean=round(m, 3) if np.isfinite(m) else None,
                         share_high=round((near[H] >= C.HBI_BANDS[1]).mean(), 3) if len(near) else None,
                         percentile=round(pct, 3) if np.isfinite(pct) else None,
                         top10=bool(pct >= 0.9) if np.isfinite(pct) else None))
    vs = pd.DataFrame(rows); vs.to_csv(os.path.join(C.OUTPUT, "validation_sites.csv"), index=False, encoding="utf-8-sig")
    log("선정지 재현:\n" + vs.to_string(index=False))
    # 선정지보다 HBI가 높은데 선정지 반경 500m 밖인 격자
    thr = vs.hbi_mean.dropna().min()
    if np.isfinite(thr):
        cx = (cells.gx + 0.5) * C.GRID; cy = (cells.gy + 0.5) * C.GRID
        d, _ = cKDTree(np.c_[sites.geometry.x, sites.geometry.y]).query(np.c_[cx, cy])
        cand = cells[(cells["mean"] > thr) & (d > 500)].sort_values("mean", ascending=False)
        pd.DataFrame({"cell_x": ((cand.gx + 0.5) * C.GRID).values, "cell_y": ((cand.gy + 0.5) * C.GRID).values,
                      "hbi_mean": cand["mean"].round(3).values, "n_bld": cand["count"].values}).head(30) \
            .to_csv(os.path.join(C.OUTPUT, "validation_new_candidates.csv"), index=False, encoding="utf-8-sig")
        log(f"선정지 최저 HBI({thr:.2f})보다 높은 비선정 격자: {len(cand)}개")

# 2) 구간 재현 / 실측 비교
op = os.path.join(C.EXTERNAL, "od_pairs.csv")
if os.path.exists(op):
    od = pd.read_csv(op, encoding="utf-8-sig").dropna(subset=["o_lon", "o_lat", "d_lon", "d_lat"]).reset_index(drop=True)
if os.path.exists(op) and len(od):
    od.to_csv(os.path.join(C.WORK, "_od.csv"), index=False, encoding="utf-8-sig"); op = os.path.join(C.WORK, "_od.csv")
    gi = np.where(nodes["giant"].values)[0] if "giant" in nodes else np.arange(len(nodes))
    tree = cKDTree(nodes[["x", "y"]].values[gi])
    o = load_points_csv(op, "o_lon", "o_lat"); dd = load_points_csv(op, "d_lon", "d_lat")
    _, oi = tree.query(np.c_[o.geometry.x, o.geometry.y]); _, di = tree.query(np.c_[dd.geometry.x, dd.geometry.y])
    oi, di = gi[oi], gi[di]
    rows = []
    for k in range(len(od)):
        te, le = route(len(nodes), e, s, oi[k], di[k], "elder")
        ta, la = route(len(nodes), e, s, oi[k], di[k], "elder", speed=1.1)   # 성인 보행자(실측자) 기준
        tw, lw = route(len(nodes), e, s, oi[k], di[k], "wheel")
        tf, lf = route(len(nodes), e, s, oi[k], di[k], "flat")
        straight = float(np.hypot(o.geometry.x.iloc[k] - dd.geometry.x.iloc[k], o.geometry.y.iloc[k] - dd.geometry.y.iloc[k]))
        rows.append(dict(name=od["name"].iloc[k], straight_m=round(straight), net_m=round(lf) if lf == lf else None,
                         elder_min=round(te / 60, 1) if te == te else None, adult_min=round(ta / 60, 1) if ta == ta else None,
                         wheel_path_m=round(lw) if lw == lw else None, flat_min=round(tf / 60, 1) if tf == tf else None,
                         measured_min=od["measured_min"].iloc[k] if "measured_min" in od else None))
    r = pd.DataFrame(rows); r.to_csv(os.path.join(C.OUTPUT, "validation_routes.csv"), index=False, encoding="utf-8-sig")
    log("구간 재현:\n" + r.to_string(index=False))
    m = r.dropna(subset=["measured_min", "adult_min"])
    if len(m) >= 3:
        rr, p = pearsonr(m.adult_min, m.measured_min)
        log(f"실측 vs 예측(성인 기준) 상관 r={rr:.3f}, p={p:.3f}, n={len(m)}")

# 3) 기여도 분석
ab = []
x = b.dropna(subset=[H, f"{T}_t_flat"])
q = x[f"{T}_t_elder"].quantile(0.9)
top = x[f"{T}_t_elder"] >= q
flat_top = x[f"{T}_t_flat"] >= x[f"{T}_t_flat"].quantile(0.9)
rho = spearmanr(x[f"{T}_t_elder"], x[f"{T}_t_flat"]).correlation
ab.append(dict(scenario="DEM 제외(평지 가정)", metric="경사 반영 상위10% 취약건물 중 평지 기준으로는 상위10%가 아닌 비율",
               value=round((top & ~flat_top).sum() / top.sum(), 3)))
ab.append(dict(scenario="DEM 제외(평지 가정)", metric="경사 반영 vs 평지 소요시간 순위상관(Spearman)", value=round(rho, 3)))
hi = x[H] >= C.HBI_BANDS[1]
ab.append(dict(scenario="DEM 제외(평지 가정)", metric="HBI 1.8 이상 건물 중 평지 기준 소요시간이 중앙값 이하('양호')인 비율",
               value=round((hi & (x[f"{T}_t_flat"] <= x[f"{T}_t_flat"].median())).sum() / max(hi.sum(), 1), 3)))
if f"{T}_t_wheel_stairok" in x:
    w = x[[f"{T}_t_wheel", f"{T}_t_wheel_stairok"]].replace([np.inf], np.nan)
    ratio = (w[f"{T}_t_wheel"] / w[f"{T}_t_wheel_stairok"]).dropna()
    ab.append(dict(scenario="계단 레이어 제외", metric="계단을 통행가능으로 잘못 가정할 때 휠체어 시간 과소추정 비율(평균)",
                   value=round(1 - 1 / ratio.mean(), 3) if len(ratio) else None))
    ab.append(dict(scenario="계단 레이어 제외", metric="휠체어 도달불가 건물 비율(계단 반영 시)",
                   value=round(b[f"{T}_t_wheel"].isna().mean(), 3)))
coarse, gx, gy = grid_mean(x, C.GRID_COARSE)
key = pd.Series(list(zip(gx, gy)), index=x.index)
low = set(map(tuple, coarse[coarse["mean"] < C.HBI_BANDS[0]][["gx", "gy"]].values))
hidden = key[hi].map(lambda k: k in low)
ab.append(dict(scenario=f"{C.GRID_COARSE}m 격자 평균으로 집계", metric="HBI 1.8 이상 건물 중 평균이 1.3 미만인 격자에 가려진 비율",
               value=round(hidden.mean(), 3) if len(hidden) else None))
if f"{T}_hbi_dem1" in x:
    y = x.dropna(subset=[f"{T}_hbi_dem1"])
    ab.append(dict(scenario="DEM 5m vs 1m", metric="HBI 순위상관(Spearman)", value=round(spearmanr(y[H], y[f"{T}_hbi_dem1"]).correlation, 3)))
    ab.append(dict(scenario="DEM 5m vs 1m", metric="HBI 평균 절대차", value=round((y[H] - y[f"{T}_hbi_dem1"]).abs().mean(), 3)))
ab = pd.DataFrame(ab); ab.to_csv(os.path.join(C.OUTPUT, "validation_ablation.csv"), index=False, encoding="utf-8-sig")
log("기여도 분석:\n" + ab.to_string(index=False))
