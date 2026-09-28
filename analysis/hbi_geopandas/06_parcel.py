# -*- coding: utf-8 -*-
"""
[2회차, 국토정보필지 승인 후] 건물 단위 HBI를 필지에 결합
 - 네트워크를 다시 계산하지 않고 work/buildings_hbi.gpkg를 필지와 공간 조인
 - 지목(JIMOK)이 '대'인 필지로 주거지 재검증
 결과: work/parcel_hbi.gpkg (반출 대상 아님), output/parcel_summary.csv (요약만)
"""
import os, pandas as pd, geopandas as gpd
import config as C
from lib.io_utils import log, find_files, read_one
if not C.DATA_ROOT_PARCEL:
    raise SystemExit("config.DATA_ROOT_PARCEL 을 설정하세요")
b = gpd.read_file(os.path.join(C.WORK, "buildings_hbi.gpkg"))
files = find_files(C.DATA_ROOT_PARCEL, [""], ".shp")
bb = b.total_bounds
parts = []
for f in files:
    g = read_one(f)                                  # 필요 시 시도별 파일만 지정
    g = (g if g.crs else g.set_crs(C.DEFAULT_CRS)).to_crs(C.TARGET_CRS).cx[bb[0]:bb[2], bb[1]:bb[3]]
    keep = [c for c in ["PNU", "EMD_CD", "EMD_NM", "JIMOK", "PAREA"] if c in g.columns]
    parts.append(g[keep + ["geometry"]])            # 소유·공시지가 등은 사용하지 않음
p = gpd.GeoDataFrame(pd.concat(parts, ignore_index=True), crs=C.TARGET_CRS)
log(f"필지 {len(p):,}개")
T = "medical" if "medical_hbi" in b else [c[:-4] for c in b.columns if c.endswith("_hbi")][0]; H = f"{T}_hbi"
j = gpd.sjoin(b[[H, "weight", "geometry"]], p, predicate="within")
agg = j.groupby("PNU").agg(hbi=(H, "max"), n_bld=(H, "size"), weight=("weight", "sum")).reset_index()
pp = p.merge(agg, on="PNU", how="inner")
pp.to_file(os.path.join(C.WORK, "parcel_hbi.gpkg"), driver="GPKG")
dae = pp[pp.JIMOK.astype(str).str.contains("대")] if "JIMOK" in pp else pp
rows = [dict(metric="HBI 산출 필지 수", value=len(pp)), dict(metric="그중 지목 '대' 필지 수", value=len(dae)),
        dict(metric="'대' 필지 HBI 1.8 이상 비율", value=round((dae.hbi >= C.HBI_BANDS[1]).mean(), 3))]
if "EMD_CD" in pp:
    e = dae.groupby("EMD_CD").agg(n=("hbi", "size"), hbi_mean=("hbi", "mean"),
                                   share_high=("hbi", lambda v: (v >= C.HBI_BANDS[1]).mean())).reset_index()
    e[e.n >= C.MIN_COUNT].round(3).to_csv(os.path.join(C.OUTPUT, "parcel_by_legal_dong.csv"), index=False, encoding="utf-8-sig")
pd.DataFrame(rows).to_csv(os.path.join(C.OUTPUT, "parcel_summary.csv"), index=False, encoding="utf-8-sig")
log(pd.DataFrame(rows).to_string(index=False))
