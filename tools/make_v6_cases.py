# -*- coding: utf-8 -*-
"""
tools/make_v6_cases.py ─ v6 시험용 가짜 자료: 1차 방문(10/2)에서 실제로 겪은 모양을 재현  ※ 안심구역 반입 안 함

[실행]  (QGIS 파이썬으로)  python tools/make_v6_cases.py <만들 폴더>
[만드는 것]  <폴더>/tiles/  구마다 한 하위 폴더 (수도권 shp 처럼 레이어별 shp 하나씩). 실제 구 경계(analysis/hbi/external/dong_boundary.geojson)
             범위에 놓아 대상 구 판정·폴더 선택·AREA_BBOX 결정을 시험할 수 있게 함
               - 길: 도로중심선 300m 격자 (보도중심선·정류장·정거장·터널은 1차 방문처럼 없음)
               - 건물: 칸 두 벌 ufid/ (UFID 하나뿐, 1차 방문 모양)  std/ (BPRP_SE·BULD_SE·BFLR_CO)
               - 계단·교량 조금, 인코딩은 구마다 CP949(.cpg 없음)·UTF-8(.cpg 있음) 번갈아
             <폴더>/dem/   구마다 DEM 5m 한 장 (언덕 하나)
             <폴더>/parcel_lower/서울/구이름.shp  필지 칸 소문자 (pnu, sido_cd, sgg_cd, emd_cd, jimok, sgg_nm, emd_nm, bldrgst_pk, owner_nm, jiga)
             <폴더>/parcel_korean/서울/…        필지 칸 한글 (고유번호, 지목, 시군구명, 읍면동명), CP949·.cpg 없음
             <폴더>/parcel_gyeonggi/경기/…      서울 밖 필지 (고유번호 앞 41)
             <폴더>/building_register.csv      tools/prep_building_register.py 출력과 같은 8열. 필지 절반은 대장번호(bldrgst_pk)로, 절반은 pnu 로만 연결
             <폴더>/dxf_only/                  dxf 만 있는 폴더
"""
import os, sys, csv, json
import numpy as np
from osgeo import gdal, ogr, osr
gdal.UseExceptions(); ogr.UseExceptions(); osr.UseExceptions()

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.abspath(sys.argv[1] if len(sys.argv) > 1 else "v6cases")
GU = ["종로구", "중구", "관악구", "광진구", "강서구", "성북구", "성동구", "동대문구", "노원구", "경기남부", "은평구"]   # 경기남부 = 서울 밖 먼 폴더 (자동 선택에서 빠져야 함)
S5186 = osr.SpatialReference(); S5186.ImportFromEPSG(5186); S5186.SetAxisMappingStrategy(osr.OAMS_TRADITIONAL_GIS_ORDER)
rng = np.random.RandomState(7)


def gu_geoms():
    ds = ogr.Open(os.path.join(ROOT, "analysis", "hbi", "external", "dong_boundary.geojson"))
    lyr = ds.GetLayer(0)
    src = lyr.GetSpatialRef(); src.SetAxisMappingStrategy(osr.OAMS_TRADITIONAL_GIS_ORDER)
    ct = osr.CoordinateTransformation(src, S5186)
    out, code = {}, {}
    for f in lyr:
        g = f.GetGeometryRef().Clone(); g.Transform(ct)
        gu = f.GetField("sggnm")
        out[gu] = g if gu not in out else out[gu].Union(g)
        code[gu] = str(f.GetField("ADM_CD"))[:5]
    out["경기남부"] = ogr.CreateGeometryFromWkt("POLYGON((190000 505000,197000 505000,197000 511000,190000 511000,190000 505000))")
    code["경기남부"] = "41111"
    return out, code


def shp(path, gtype, fields, feats, enc="UTF-8", cpg=True, prj=True):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    drv = ogr.GetDriverByName("ESRI Shapefile")
    if os.path.exists(path):
        drv.DeleteDataSource(path)
    ds = drv.CreateDataSource(path)
    lyr = ds.CreateLayer("l", S5186 if prj else None, gtype, options=[f"ENCODING={enc}"])
    for f in fields:
        lyr.CreateField(ogr.FieldDefn(f, ogr.OFTString))
    for wkt, at in feats:
        ft = ogr.Feature(lyr.GetLayerDefn())
        for k, v in at.items():
            ft.SetField(k, str(v))
        ft.SetGeometry(ogr.CreateGeometryFromWkt(wkt))
        lyr.CreateFeature(ft)
    ds = None
    if not cpg and os.path.exists(os.path.splitext(path)[0] + ".cpg"):
        os.remove(os.path.splitext(path)[0] + ".cpg")


box = lambda x0, y0, x1, y1: f"POLYGON(({x0} {y0},{x1} {y0},{x1} {y1},{x0} {y1},{x0} {y0}))"


def main():
    G, CODE = gu_geoms()
    reg = []
    meta = {}
    for gi, gu in enumerate(GU):
        g = G[gu]
        x0, x1, y0, y1 = g.GetEnvelope()
        x0, y0, x1, y1 = np.floor(x0 / 100) * 100, np.floor(y0 / 100) * 100, np.ceil(x1 / 100) * 100, np.ceil(y1 / 100) * 100
        folder = f"NGII_수도권_{gi + 1:02d}"
        enc, cpg = ("CP949", False) if gi % 2 else ("UTF-8", True)
        for variant in ("ufid", "std"):
            d = os.path.join(OUT, "tiles_" + variant, folder)
            roads = [(f"LINESTRING({x0} {y},{x1} {y})", {"RDDV": "RDD001", "NAME": f"가상{gi}로"}) for y in np.arange(y0, y1 + 1, 300)]
            roads += [(f"LINESTRING({x} {y0},{x} {y1})", {"RDDV": "RDD001", "NAME": f"가상{gi}길"}) for x in np.arange(x0, x1 + 1, 300)]
            shp(f"{d}/N3L_A0020000.shp", ogr.wkbLineString, ["RDDV", "NAME"], roads, enc, cpg)   # 한글 칸: 인코딩 판정 시험용
        # 건물: 구 안 무작위 점, 길 격자에서 20~60m 떨어지게 (집 → 길 연결 확인용)
        # 동네 4곳: 구 안쪽(자료 가장자리에서 600m 넘게)의 가로 길 위 점을 중심으로, 길에서 15~45m 떨어진 집 40채씩
        pts, centers = [], []
        gx = np.arange(x0, x1 + 1, 300); gy = np.arange(y0, y1 + 1, 300)
        cand = [(x, y) for x in gx for y in gy if x0 + 600 < x < x1 - 600 and y0 + 600 < y < y1 - 600]
        rng.shuffle(cand)
        for cx_, cy_ in cand:
            p = ogr.Geometry(ogr.wkbPoint); p.AddPoint_2D(cx_, cy_)
            if g.Contains(p):
                centers.append((cx_, cy_))
            if len(centers) == 4:
                break
        for cx_, cy_ in centers:
            for k in range(40):
                pts.append((cx_ + rng.uniform(-110, 110), cy_ + rng.choice([-1, 1]) * rng.uniform(15, 45)))
        use = rng.choice(["BDU001", "BDU002", "BDU003", "BDU009", "BDU011"], size=len(pts), p=[.5, .3, .12, .04, .04])
        flo = rng.randint(1, 8, size=len(pts))
        ufid = [(box(x - 6, y - 6, x + 6, y + 6), {"UFID": f"B{gi:02d}{i:05d}"}) for i, (x, y) in enumerate(pts)]
        std = [(box(x - 6, y - 6, x + 6, y + 6), {"BPRP_SE": u, "BULD_SE": "BDC001", "BFLR_CO": int(f)}) for (x, y), u, f in zip(pts, use, flo)]
        shp(f"{OUT}/tiles_ufid/{folder}/N3A_B0010000.shp", ogr.wkbPolygon, ["UFID"], ufid, enc, cpg)
        shp(f"{OUT}/tiles_std/{folder}/N3A_B0010000.shp", ogr.wkbPolygon, ["BPRP_SE", "BULD_SE", "BFLR_CO"], std, enc, cpg)
        cx, cy = g.PointOnSurface().GetX(), g.PointOnSurface().GetY()
        for variant in ("ufid", "std"):
            d = os.path.join(OUT, "tiles_" + variant, folder)
            shp(f"{d}/N3A_C0390000.shp", ogr.wkbPolygon, ["ARSFCKD_SE"], [(box(cx - 2, cy + 40, cx + 2, cy + 120), {"ARSFCKD_SE": "PGS001"})], enc, cpg)
            shp(f"{d}/N3A_A0070000.shp", ogr.wkbPolygon, [], [(box(cx + 100, cy - 10, cx + 400, cy + 10), {})], enc, cpg)
        # DEM 5m (구 범위 + 200m)
        nx, ny = int((x1 - x0 + 400) / 5), int((y1 - y0 + 400) / 5)
        xs = x0 - 200 + np.arange(nx) * 5 + 2.5; ys = y1 + 200 - np.arange(ny) * 5 - 2.5
        XX, YY = np.meshgrid(xs, ys)
        z = 30 + 60 * np.exp(-(((XX - cx) ** 2 + (YY - cy) ** 2) / (2 * 900 ** 2)))
        os.makedirs(f"{OUT}/dem", exist_ok=True)
        r = gdal.GetDriverByName("HFA").Create(f"{OUT}/dem/dem_{gi + 1:02d}.img", nx, ny, 1, gdal.GDT_Float32)
        r.SetGeoTransform((x0 - 200, 5, 0, y1 + 200, 0, -5)); r.SetProjection(S5186.ExportToWkt())
        r.GetRasterBand(1).WriteArray(z.astype("float32")); r.GetRasterBand(1).SetNoDataValue(-9999); r = None
        # 필지: 건물마다 30m 네모 한 필지 (+ 도로 필지 몇 개)
        low, kor = [], []
        for i, ((x, y), u, f) in enumerate(zip(pts, use, flo)):
            pnu = f"{CODE[gu]}10100{1}{i + 1:04d}{gi:04d}"
            pk = f"{CODE[gu]}-{100000 + i}" if i % 2 == 0 else ""
            geom = box(x - 15, y - 15, x + 15, y + 15)
            jm = "대" if i % 9 else "도"
            low.append((geom, {"pnu": pnu, "sido_cd": "11", "sgg_cd": CODE[gu], "emd_cd": CODE[gu] + "10100", "jimok": jm,
                               "sgg_nm": gu, "emd_nm": f"가상{gi}동", "bldrgst_pk": pk, "owner_nm": "OWNER-SHOULD-NOT-BE-READ", "jiga": "999999",
                               "ufid": f"B{gi:02d}{i:05d}" if i % 4 == 0 else f"P{gi:02d}{i:05d}"}))   # 4곳 중 1곳만 건물 UFID 와 같음 (참고 일치율 시험)
            kor.append((geom, {"고유번호": pnu, "지목": jm, "시군구명": gu, "읍면동명": f"가상{gi}동"}))
            nm = {"BDU001": "단독주택", "BDU002": "공동주택", "BDU003": "제1종근린생활시설", "BDU009": "의료시설", "BDU011": "노유자시설"}[u]
            reg.append([pk or f"N{gi:02d}{i:06d}", pnu, "", nm, "", int(f), 100.0 + 10 * f, "주"])
            if i % 5 == 0:                                   # 부속건축물 (용도가 달라도 주건축물이 우선)
                reg.append([f"A{gi:02d}{i:06d}", pnu, "", "창고시설", "", 1, 9999.0, "부속"])
        pdir = "경기" if gu == "경기남부" else "서울"
        shp(f"{OUT}/parcel_lower/{pdir}/{gu}.shp", ogr.wkbPolygon,
            ["pnu", "sido_cd", "sgg_cd", "emd_cd", "jimok", "sgg_nm", "emd_nm", "bldrgst_pk", "owner_nm", "jiga", "ufid"], low, "UTF-8", False)
        shp(f"{OUT}/parcel_korean/{pdir}/{gu}.shp", ogr.wkbPolygon, ["고유번호", "지목", "시군구명", "읍면동명"], kor, "CP949", False)
        meta[gu] = dict(folder=folder, n_bld=len(pts), n_res=int(np.isin(use, ["BDU001", "BDU002"]).sum()))
    shp(f"{OUT}/parcel_gyeonggi/경기/수원시.shp", ogr.wkbPolygon, ["pnu", "jimok"],
        [(box(300000 + i * 40, 500000, 300030 + i * 40, 500030), {"pnu": f"4111110100{1}{i + 1:04d}0000", "jimok": "대"}) for i in range(30)], "UTF-8", False)
    with open(f"{OUT}/building_register.csv", "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f); w.writerow(["bldrgst_pk", "pnu", "main_use_cd", "main_use_nm", "use_class", "grnd_flr", "tot_area", "main_atch"]); w.writerows(reg)
    os.makedirs(f"{OUT}/dxf_only/도엽", exist_ok=True)
    for n in ("37612006.dxf", "37612007.dxf"):
        open(f"{OUT}/dxf_only/도엽/{n}", "w").write("0\nSECTION\n0\nENDSEC\n0\nEOF\n")
    # 대소문자 시험판: tiles_std 와 내용은 같고, 파일 이름은 소문자·확장자는 대문자(N3A_B0010000.shp → n3a_b0010000.SHP), 코드 값은 소문자(BDU001 → bdu001)
    import glob, shutil
    for src in sorted(glob.glob(f"{OUT}/tiles_std/*/*.shp")):
        d = os.path.join(OUT, "tiles_lowcase", os.path.basename(os.path.dirname(src)))
        os.makedirs(d, exist_ok=True)
        cpg = os.path.exists(os.path.splitext(src)[0] + ".cpg")
        ds = gdal.OpenEx(src, gdal.OF_VECTOR, open_options=[] if cpg else ["ENCODING=CP949"]); lyr = ds.GetLayer(0); defn = lyr.GetLayerDefn()
        names = [defn.GetFieldDefn(i).GetName() for i in range(defn.GetFieldCount())]
        feats = [(f.GetGeometryRef().ExportToWkt(), {k: str(f.GetField(k) or "").lower() if k != "NAME" else f.GetField(k) for k in names}) for f in lyr]
        enc = "UTF-8" if cpg else "CP949"
        stem = os.path.splitext(os.path.basename(src))[0].lower()
        tmp = os.path.join(d, stem + ".shp")
        shp(tmp, lyr.GetGeomType(), names, feats, enc, cpg)
        ds = None
        for f in glob.glob(os.path.join(d, stem + ".*")):
            b_, e_ = os.path.splitext(f)
            os.rename(f, b_ + e_.upper() + ".tmp"); os.rename(b_ + e_.upper() + ".tmp", b_ + e_.upper())
    json.dump(meta, open(f"{OUT}/meta.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("완료:", OUT, {g: m["folder"] for g, m in meta.items()})


if __name__ == "__main__":
    main()
