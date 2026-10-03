# -*- coding: utf-8 -*-
"""
06_parcel.py ─ [2회차, 국토정보필지가 승인된 뒤] 건물 결과를 필지에 붙이기

[실행]  config.py 의 DATA_ROOT_PARCEL 에 필지 폴더 경로를 넣고 → python 06_parcel.py
[하는 일] 네트워크를 다시 계산하지 않고, 이미 계산된 건물별 HBI(work/buildings_hbi.csv)를
          건물이 서 있는 필지에 붙입니다. 한 필지에 건물이 여럿이면 가장 높은 HBI 를 씁니다.
          지목이 "대"(대지)인 필지만 따로 골라 주거지 결과를 다시 확인합니다.
          ※ 필지의 소유·공시지가 정보는 읽지 않습니다 (PNU, 읍면동코드, 지목만 사용)
[결과] output/parcel_summary.csv, output/parcel_by_legal_dong.csv (법정동별 요약)
       [v5] parcel_by_legal_dong.csv 에 sgg_nm·emd_nm(시군구·법정동 이름, 필지의 SGG_NM·EMD_NM) 열 추가
"""
import os, numpy as np
from osgeo import ogr
import config as C
from lib.qio import log, find_files, iter_layer, write_csv
from lib.bload import load_buildings, targets, usable

if not C.DATA_ROOT_PARCEL:
    raise SystemExit("config.DATA_ROOT_PARCEL 을 설정하세요")
b = load_buildings()
X, Y = b["x"], b["y"]
T = "medical" if "medical_hbi" in b else targets(b)[0]
H = b[f"{T}_hbi"].copy()
H[~usable(b)] = np.nan                     # 데이터 경계 근처 건물 제외
bbox = [np.nanmin(X) - 50, np.nanmin(Y) - 50, np.nanmax(X) + 50, np.nanmax(Y) + 50]   # 건물이 있는 범위의 필지만 읽음
files = find_files(C.DATA_ROOT_PARCEL, [""], ".shp")
# [v5] SGG_NM(시군구명)·EMD_NM(법정 읍면동명) 도 읽음 → 11_legal_dong_join.py 가 교통사고(법정동 이름) 와 붙일 때 씀
# [v6] 칸 이름은 mapping.txt (parcel_id·parcel_emd_cd·jimok·sgg_nm·emd_nm, 대소문자 무시). 아래 F_* 는 그 이름
F_ID, F_EMD, F_JI, F_SGG, F_EMDNM = (C.FIELD[k] for k in ("parcel_id", "parcel_emd_cd", "jimok", "sgg_nm", "emd_nm"))
if not F_ID:
    raise SystemExit("mapping.txt 의 parcel_id(필지 고유번호 칸) 가 ? 입니다 → python setup.py 또는 mapping.txt 고치기")
parcels = [(g, a) for g, a in iter_layer(files=files, fields=[F_ID, F_EMD, F_JI, F_SGG, F_EMDNM], bbox=bbox, encoding=C.PARCEL_ENCODING)]
if parcels and F_ID not in parcels[0][1]:
    raise SystemExit(f"필지에 고유번호 칸 {F_ID} 가 없습니다 → mapping.txt 의 parcel_id 를 실제 칸 이름으로 (python setup.py 가 찾아 줌)")
log(f"필지 {len(parcels):,}개")

# 건물 점들을 100m 칸에 나눠 담아 두고(버킷), 필지마다 겹치는 칸의 건물만 검사 → 빠름
cell = 100.0
bucket = {}
for i, (x, y) in enumerate(zip(X, Y)):
    bucket.setdefault((int(x // cell), int(y // cell)), []).append(i)
pmax, pemd, pji = {}, {}, {}           # 필지번호(PNU) → 최대 HBI / 읍면동코드 / 지목
emd_name = {}                          # [v5] 읍면동코드 → (시군구명, 법정동명)
for g, a in parcels:
    x0, x1, y0, y1 = g.GetEnvelope()
    idx = []
    for cx in range(int(x0 // cell), int(x1 // cell) + 1):
        for cy in range(int(y0 // cell), int(y1 // cell) + 1):
            idx += bucket.get((cx, cy), [])
    vals = []
    for i in idx:
        pt = ogr.Geometry(ogr.wkbPoint)
        pt.AddPoint_2D(float(X[i]), float(Y[i]))
        if np.isfinite(H[i]) and g.Contains(pt):     # 건물 점이 이 필지 안에 있으면
            vals.append(H[i])
    if vals:
        pid = a[F_ID]
        ecd = a.get(F_EMD) if F_EMD in a else str(pid or "")[:10]      # [v6] 읍면동 코드 칸이 없으면 고유번호 앞 10자리(법정동 코드)
        pmax[pid] = max(vals)
        pemd[pid] = ecd
        pji[pid] = str(a.get(F_JI) or "")
        if a.get(F_EMDNM):
            emd_name.setdefault(ecd, (str(a.get(F_SGG) or ""), str(a.get(F_EMDNM) or "")))

dae = [k for k in pmax if "대" in pji[k]]            # 지목에 "대" 가 들어간 필지
if pmax and not dae:
    log(f"  ! 지목 '대' 필지가 0개입니다. 지목 예시: {list(set(pji.values()))[:5]} → 글자가 깨졌다면 config.PARCEL_ENCODING 을 바꿔 보세요")
hv = np.array([pmax[k] for k in dae]) if dae else np.array([])
rows = [["HBI 산출 필지 수", len(pmax)], ["그중 지목 '대' 필지 수", len(dae)],
        ["'대' 필지 HBI 1.8 이상 비율", round(float(np.mean(hv >= C.HBI_BANDS[1])), 3) if len(hv) else ""]]
write_csv(os.path.join(C.OUTPUT, "parcel_summary.csv"), ["metric", "value"], rows)
emd = {}
for k in dae:
    emd.setdefault(pemd[k], []).append(pmax[k])
write_csv(os.path.join(C.OUTPUT, "parcel_by_legal_dong.csv"), ["emd_cd", "n", "hbi_mean", "share_high", "sgg_nm", "emd_nm"],
          [[k, len(v), round(float(np.mean(v)), 3), round(float(np.mean(np.array(v) >= C.HBI_BANDS[1])), 3)] + list(emd_name.get(k, ("", "")))
           for k, v in emd.items() if len(v) >= C.MIN_COUNT])
if not emd_name:
    log(f"  필지에 {F_SGG}·{F_EMDNM} 필드가 없어 법정동 이름 칸은 비움 (11_legal_dong_join.py 는 이름이 있어야 결합 가능, mapping.txt 의 sgg_nm·emd_nm)")
log(rows)
