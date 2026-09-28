# -*- coding: utf-8 -*-
"""
[5일차] 반출용 집계 결과 생성
 - output/grid_hbi.csv   : 250m 격자 집계 (건물 MIN_COUNT개 미만 격자 제외)
 - output/summary.csv    : 전체 요약 통계
 - output/dong_hbi.csv   : 행정동 집계 (external/dong_boundary.shp 있을 때) → SKT·KCB 연계용
 - output/map_*.png      : 격자 지도 이미지
 개별 건물 단위 결과(work/)는 반출하지 않습니다.
"""
import os, numpy as np, pandas as pd, geopandas as gpd
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.colors import LinearSegmentedColormap
import config as C
from lib.io_utils import log, find_files

os.makedirs(C.OUTPUT, exist_ok=True)
b = gpd.read_file(os.path.join(C.WORK, "buildings_hbi.gpkg"))
targets = [c[:-4] for c in b.columns if c.endswith("_hbi")]
lo, hi = C.HBI_BANDS

# 한글 폰트
_names = [x.name for x in matplotlib.font_manager.fontManager.ttflist]
for f in ["Malgun Gothic", "NanumGothic", "AppleGothic", "Noto Sans CJK KR", "Noto Sans CJK JP", "CJK"]:
    hit = [n for n in _names if f in n]
    if hit:
        plt.rcParams["font.family"] = hit[0]; break
plt.rcParams["axes.unicode_minus"] = False
cmap = LinearSegmentedColormap.from_list("hbi", ["#7FA88E", "#F2D16B", "#E8743B", "#B23A2A"])

b["gx"] = np.floor(b.geometry.x / C.GRID).astype(int); b["gy"] = np.floor(b.geometry.y / C.GRID).astype(int)
rows = []; summary = []
for T in targets:
    H = f"{T}_hbi"; x = b.dropna(subset=[H])
    summary += [dict(target=T, metric="분석 건물 수", value=len(x)),
                dict(target=T, metric="HBI 중앙값", value=round(x[H].median(), 3)),
                dict(target=T, metric=f"HBI {lo}~{hi} 비율", value=round(((x[H] >= lo) & (x[H] < hi)).mean(), 3)),
                dict(target=T, metric=f"HBI {hi} 이상 비율", value=round((x[H] >= hi).mean(), 3)),
                dict(target=T, metric=f"HBI {hi} 이상 건물 수", value=int((x[H] >= hi).sum())),
                dict(target=T, metric="귀갓길(목적지→집) 편도 배수 중앙값", value=round(x[f"{T}_home_ratio"].median(), 3)),
                dict(target=T, metric="고령자 왕복 중앙값(분)", value=round(x[f"{T}_t_elder"].median() / 60, 1)),
                dict(target=T, metric="휠체어 도달불가 비율", value=round(b[f"{T}_t_wheel"].isna().mean(), 3))]
    g = x.groupby(["gx", "gy"]).agg(n_bld=(H, "size"), weight=("weight", "sum"), hbi_mean=(H, "mean"),
                                    hbi_median=(H, "median"), share_high=(H, lambda v: (v >= hi).mean()),
                                    elder_min=(f"{T}_t_elder", lambda v: v.median() / 60),
                                    wheel_ratio=(f"{T}_wheel_ratio", "median")).reset_index()
    g = g[g.n_bld >= C.MIN_COUNT]; g["target"] = T
    rows.append(g)
    fig, ax = plt.subplots(figsize=(8, 8), dpi=150)
    from matplotlib.collections import PatchCollection
    from matplotlib.patches import Rectangle
    pc = PatchCollection([Rectangle((gx * C.GRID, gy * C.GRID), C.GRID, C.GRID) for gx, gy in zip(g.gx, g.gy)],
                         cmap=cmap, edgecolor="white", linewidth=0.3)
    pc.set_array(g.hbi_mean.values); pc.set_clim(1, 2.2); sc = ax.add_collection(pc)
    ax.set_xlim(g.gx.min() * C.GRID, (g.gx.max() + 1) * C.GRID); ax.set_ylim(g.gy.min() * C.GRID, (g.gy.max() + 1) * C.GRID)
    ax.set_aspect("equal"); ax.set_xticks([]); ax.set_yticks([])
    plt.colorbar(sc, ax=ax, shrink=0.6, label="언덕 부담 지수 (HBI)")
    ax.set_title(f"{C.GRID}m 격자 평균 HBI · 목적지: {T}")
    fig.savefig(os.path.join(C.OUTPUT, f"map_{T}.png"), bbox_inches="tight"); plt.close(fig)

grid = pd.concat(rows)
grid["cell_x"] = (grid.gx + 0.5) * C.GRID; grid["cell_y"] = (grid.gy + 0.5) * C.GRID
grid.drop(columns=["gx", "gy"]).round(3).to_csv(os.path.join(C.OUTPUT, "grid_hbi.csv"), index=False, encoding="utf-8-sig")
pd.DataFrame(summary).to_csv(os.path.join(C.OUTPUT, "summary.csv"), index=False, encoding="utf-8-sig")
log("summary:\n" + pd.DataFrame(summary).to_string(index=False))

# 행정동 집계 (+ 고령인구 배분)
bd = find_files(C.EXTERNAL, ["dong_boundary"], ".shp") + find_files(C.EXTERNAL, ["dong_boundary"], ".geojson")
if bd:
    dong = gpd.read_file(bd[0]).to_crs(C.TARGET_CRS)
    code = [c for c in dong.columns if c.upper() in ("ADM_CD", "ADM_DR_CD", "ADSTRD_CD", "CODE")][0]
    j = gpd.sjoin(b, dong[[code, "geometry"]], predicate="within")
    T = "medical" if "medical" in targets else targets[0]; H = f"{T}_hbi"
    d = j.groupby(code).agg(n_bld=(H, "size"), hbi_mean=(H, "mean"), share_high=(H, lambda v: (v >= hi).mean()),
                            weight_high=("weight", lambda v: v[j.loc[v.index, H] >= hi].sum()),
                            weight_all=("weight", "sum")).reset_index()
    pp = os.path.join(C.EXTERNAL, "elderly_pop.csv")
    if os.path.exists(pp):
        pop = pd.read_csv(pp, encoding="utf-8-sig", dtype={"adm_cd": str})
        d[code] = d[code].astype(str)
        d = d.merge(pop, left_on=code, right_on="adm_cd", how="left")
        d["elderly_in_high"] = (d["pop65"] * d["weight_high"] / d["weight_all"]).round()
        log(f"HBI {hi} 이상 건물 거주 고령인구 추정: 약 {int(d.elderly_in_high.sum()):,}명")
    d = d[d.n_bld >= C.MIN_COUNT]
    d.round(3).to_csv(os.path.join(C.OUTPUT, "dong_hbi.csv"), index=False, encoding="utf-8-sig")
    log("→ output/dong_hbi.csv (SKT 유동인구·KCB 소득과 행정동 코드로 결합)")
log("완료 → output/ (반출 신청 대상)")
