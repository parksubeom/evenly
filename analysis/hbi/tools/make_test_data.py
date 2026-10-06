# -*- coding: utf-8 -*-
"""
tools/make_test_data.py ─ 가짜(가상) 테스트 데이터 만들기  ※ 안심구역에서는 쓸 일 없음

[언제 쓰나] 안심구역에 가기 전, 내 PC(QGIS 설치)에서 코드가 끝까지 도는지 연습할 때
[실행]  python tools/make_test_data.py
[결과]  testdata/ 폴더에 진짜 데이터와 같은 형식의 작은 가짜 데이터가 생김
         - testdata/map/37612006/N3L_A0020000.shp ... (도로중심선·보도중심선·건물·계단·정류장·교량)
         - testdata/dem/tile0.img, tile1.img (가운데가 볼록한 언덕 모양 DEM)
         - testdata/parcel/LX_서울_필지.shp (가상 필지, 06_parcel.py 연습용 → DATA_ROOT_PARCEL = r"testdata/parcel")
         - [v6.1] testdata/parcel_1st/*.zip (1차 방문 모양: 소문자 칸, .cpg 없음, 서울·경기 zip — setup.py 연습용)
[다음]  config.py 에서
           DATA_ROOT_MAP = r"testdata/map"
           DATA_ROOT_DEM = r"testdata/dem"
         로 바꾸고  python run_all.py  → 마지막에 "완료 → output/" 이 나오면 성공
         (연습이 끝나면 경로를 원래대로 되돌리는 것 잊지 마세요)
"""
import os, csv, numpy as np
from osgeo import gdal, ogr, osr
gdal.UseExceptions(); ogr.UseExceptions(); osr.UseExceptions()
BASE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "testdata")
srs = osr.SpatialReference(); srs.ImportFromEPSG(5186)
X0, Y0, W = 200000, 545000, 2000
r = np.random.RandomState(0)
z = lambda x, y: 30 + 70 * np.exp(-(((x - X0 - 1300) ** 2 + (y - Y0 - 1200) ** 2) / (2 * 400 ** 2)))
os.makedirs(f"{BASE}/dem", exist_ok=True)
for i, ox in enumerate([X0, X0 + 1000]):
    xs = ox + np.arange(200) * 5 + 2.5; ys = Y0 + W - np.arange(400) * 5 - 2.5
    XX, YY = np.meshgrid(xs, ys)
    d = gdal.GetDriverByName("HFA").Create(f"{BASE}/dem/tile{i}.img", 200, 400, 1, gdal.GDT_Float32)
    d.SetGeoTransform((ox, 5, 0, Y0 + W, 0, -5)); d.SetProjection(srs.ExportToWkt())
    d.GetRasterBand(1).WriteArray(z(XX, YY).astype("float32")); d.GetRasterBand(1).SetNoDataValue(-9999); d = None
def shp(path, gtype, fields, feats, prj=True, enc="UTF-8", cpg=True):
    drv = ogr.GetDriverByName("ESRI Shapefile")
    if os.path.exists(path): drv.DeleteDataSource(path)
    ds = drv.CreateDataSource(path); lyr = ds.CreateLayer("l", srs if prj else None, gtype, options=[f"ENCODING={enc}"])
    for f in fields: lyr.CreateField(ogr.FieldDefn(f, ogr.OFTString))
    for wkt, at in feats:
        ft = ogr.Feature(lyr.GetLayerDefn())
        for k, v in at.items(): ft.SetField(k, str(v))
        ft.SetGeometry(ogr.CreateGeometryFromWkt(wkt)); lyr.CreateFeature(ft)
    ds = None
    if not cpg and os.path.exists(os.path.splitext(path)[0] + ".cpg"):
        os.remove(os.path.splitext(path)[0] + ".cpg")      # 실제 필지 데이터처럼 .cpg 없는 상황 재현
box = lambda x0, y0, x1, y1: f"POLYGON(({x0} {y0},{x1} {y0},{x1} {y1},{x0} {y1},{x0} {y0}))"
for sheet, (xa, xb) in {"37612006": (0, 1000), "37612007": (1000, 2000)}.items():
    d = f"{BASE}/map/{sheet}"; os.makedirs(d, exist_ok=True)
    roads = [(f"LINESTRING({X0+xa} {Y0+y},{X0+xb} {Y0+y})", {"ROAD_SE": "RDC014"}) for y in range(0, W + 1, 100)]
    roads += [(f"LINESTRING({X0+x} {Y0},{X0+x} {Y0+W})", {"ROAD_SE": "RDC014"}) for x in range(xa, xb + 1, 200)]
    shp(f"{d}/N3L_A0020000.shp", ogr.wkbLineString, ["ROAD_SE"], roads)
    shp(f"{d}/N3L_A0033328.shp", ogr.wkbLineString, [], [(f"LINESTRING({X0+xa} {Y0+y+3},{X0+xb} {Y0+y+3})", {}) for y in range(0, W + 1, 500)], prj=False)
    bl = []
    for k in range(250):
        cx, cy = X0 + r.uniform(xa + 10, xb - 10), Y0 + r.uniform(10, W - 10)
        bl.append((box(cx - 6, cy - 6, cx + 6, cy + 6), {"BPRP_SE": r.choice(["BDU001", "BDU002", "BDU003", "BDU009", "BDU011"], p=[.5, .3, .12, .04, .04]),
                                                          "BULD_SE": "BDC001", "BFLR_CO": r.randint(1, 6)}))
    shp(f"{d}/N3A_B0010000.shp", ogr.wkbPolygon, ["BPRP_SE", "BULD_SE", "BFLR_CO"], bl)
    st = [(box(X0 + x - 2, Y0 + 1105, X0 + x + 2, Y0 + 1195), {"ARSFCKD_SE": "PGS001"}) for x in range(xa + 100, xb, 200)]
    st.append((box(X0 + xa + 197, Y0 + 1310, X0 + xa + 203, Y0 + 1390), {"ARSFCKD_SE": "PGS001"}))
    shp(f"{d}/N3A_C0390000.shp", ogr.wkbPolygon, ["ARSFCKD_SE"], st)
    shp(f"{d}/N3P_A0140000.shp", ogr.wkbPoint, ["PTRFCKD_SE"], [(f"POINT({X0+x} {Y0+50})", {"PTRFCKD_SE": "BTS005"}) for x in range(xa + 100, xb, 400)])
shp(f"{BASE}/map/37612007/N3P_A0131122.shp", ogr.wkbPoint, ["NAME"], [(f"POINT({X0+1500} {Y0+300})", {"NAME": "가상역"})])
shp(f"{BASE}/map/37612006/N3A_A0070000.shp", ogr.wkbPolygon, [], [(box(X0 + 50, Y0 + 1990, X0 + 350, Y0 + 2010), {})])
# 가상 필지: 50m 격자, 지목은 대부분 "대", 일부 "도"(도로)
os.makedirs(f"{BASE}/parcel", exist_ok=True)
pf = []
for i in range(0, W, 50):
    for j in range(0, W, 50):
        pf.append((box(X0 + i, Y0 + j, X0 + i + 50, Y0 + j + 50),
                   # [v6.1] 고유번호 19자리 = 시군구 5 + 법정동 5 + 대지구분 1 + 본번 4 + 부번 4 (v6 까지는 15자리라 setup 이 필지로 못 알아봄)
                   {"PNU": f"11110{'10100' if i < 1000 else '10200'}1{i // 50 + 1:04d}{j // 50:04d}",
                    "EMD_CD": "11110101" if i < 1000 else "11110102", "JIMOK": "대" if (i // 50 + j // 50) % 7 else "도",
                    "SGG_NM": "가상구", "EMD_NM": "가상1동" if i < 1000 else "가상2동"}))   # [v5] 법정동 이름 (11_legal_dong_join 연습용)
shp(f"{BASE}/parcel/LX_서울_필지.shp", ogr.wkbPolygon, ["PNU", "EMD_CD", "JIMOK", "SGG_NM", "EMD_NM"], pf, enc="UTF-8", cpg=False)
# [v6.1] 1차 방문 모양 필지 (testdata/parcel_1st): 칸 이름 소문자, UTF-8 인데 .cpg 없음, 시도별 zip (서울 + 다른 시도)
#   setup.py 연습용: python setup.py 로 testdata 폴더를 고르면 zip 을 풀고 서울 zip 만 필지로 씀
import zipfile, glob
tmp = f"{BASE}/parcel_1st_tmp"
low = [(g, {k.lower(): v for k, v in a.items()}) for g, a in pf]
for sido in ("서울", "경기"):
    os.makedirs(f"{tmp}/{sido}", exist_ok=True)
shp(f"{tmp}/서울/AL_11_D194_LAND_INFO_BASE_MAP_202606.shp", ogr.wkbPolygon, ["pnu", "emd_cd", "jimok", "sgg_nm", "emd_nm"], low, enc="UTF-8", cpg=False)
gg = [(box(X0 + 5000 + i * 40, Y0, X0 + 5030 + i * 40, Y0 + 30), {"pnu": f"4111110100{1}{i + 1:04d}0000", "jimok": "대"}) for i in range(20)]
shp(f"{tmp}/경기/AL_41_D194_LAND_INFO_BASE_MAP_202606.shp", ogr.wkbPolygon, ["pnu", "jimok"], gg, enc="UTF-8", cpg=False)
os.makedirs(f"{BASE}/parcel_1st", exist_ok=True)
for sido, zname in (("서울", "AL_11_D194_LAND_INFO_BASE_MAP_202606.zip"), ("경기", "AL_41_D194_LAND_INFO_BASE_MAP_202606.zip")):
    with zipfile.ZipFile(f"{BASE}/parcel_1st/{zname}", "w", zipfile.ZIP_DEFLATED) as zf:
        for f in sorted(glob.glob(f"{tmp}/{sido}/*")):
            zf.write(f, os.path.basename(f))
import shutil
shutil.rmtree(tmp)
print("완료:", os.path.abspath(BASE))
