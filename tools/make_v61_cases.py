# -*- coding: utf-8 -*-
"""
tools/make_v61_cases.py ─ v6.1 시험용 가짜 자료: 1차 반출(10/2) 스키마·로그로 확인한 "실제 모양"을 재현  ※ 안심구역 반입 안 함

[실행]  (QGIS 파이썬으로)  python tools/make_v61_cases.py <만들 폴더>
[근거]  docs/1차방문_반출결과.md (칸 이름·도엽 폴더·DEM·필지 모양). 값은 정의서 별표 2 코드표(lib/codebook.py)에 있는 것만 씀
[만드는 것]  <폴더>/제공자료/  (안심구역 바탕화면 폴더처럼)
   수치지형도2/<도엽 폴더 "376xxxxx_2024_…">/  레이어별 shp. 관악구는 실제처럼 1:5,000 도엽 11장 폴더(경계에서 잘림), 다른 구는 구마다 한 폴더
     - 건물 N3A_B0010000: 한글 칸 [명칭, 구분, 종류, 용도, 주기, 층수(Integer64), 측량방법, UFID]
     - 도로중심선 N3L_A0020000: 한글 칸 [도로번호, 명칭, 도로구분, 시점, 종점, 포장재질, 분리대유무, 차로수, 도로폭, 일방통행, 자동차전용, 기타, UFID]
         300m 격자 길(도로구분 소로, 자동차전용 일반) + 고속국도 대각선 1개(도로구분 고속국도) + 자동차전용 도로 1개(도로구분 특별시도, 자동차전용)
     - 계단 N3A_C0390000 [명칭, 구조, 폭, UFID]: 계단 1, 스텐드 1 (스텐드는 빠져야 함)
     - 정거장 N3P_A0131122 [명칭, UFID]: 종류 칸 없음 → 모두 역으로
     - 인도 N3A_A0033320 [UFID, 폭, 재질]: 가로 길 절반을 따라 폭 3m 띠 (경로 계산에는 안 씀)
     - 정류장 레이어 없음 (1:5,000 에는 없음) → hbi6/external/bus_stops.csv 를 시나리오가 넣음
     값 형식: 구마다 돌아가며 (a) 코드 BDU001  (b) 한글 코드명 주거용단독주택  (c) 소문자 코드 bdu001
     인코딩: 모두 CP949 (dbf 칸 이름 한도 10바이트: UTF-8 이면 "분리대유무" 가 잘림), 구마다 .cpg 없음 / 있음 번갈아
             — 칸 이름까지 한글이라 인코딩이 틀리면 칸을 못 찾음
   국토정보필지_서울특별시/AL_11_D194_LAND_INFO_BASE_MAP_202606/  소문자 칸, UTF-8, .cpg 없음 (CP949 로 읽으면 지목이 깨짐)
   수치표고모델_5m/  구마다 .img 한 장 (언덕 하나, KGD2002 중부원점)
   수치표고모델_1m/  관악구 가운데 2km 만 1m .img (5m 와 같은 언덕)
 <폴더>/bus_stops.csv   서울시 버스정류소 모양 (name, lon, lat)  → 시나리오가 hbi6/external 에 복사
 <폴더>/meta.json       구별 집 수·고속국도 길이 (시험 판정용)
"""
import os, sys, csv, json
import numpy as np
from osgeo import gdal, ogr, osr
gdal.UseExceptions(); ogr.UseExceptions(); osr.UseExceptions()

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.abspath(sys.argv[1] if len(sys.argv) > 1 else "v61cases")
R = os.path.join(OUT, "제공자료")
GU = ["관악구", "종로구", "중구", "광진구", "강서구", "성북구", "성동구", "동대문구"]
S5186 = osr.SpatialReference(); S5186.ImportFromEPSG(5186); S5186.SetAxisMappingStrategy(osr.OAMS_TRADITIONAL_GIS_ORDER)
W84 = osr.SpatialReference(); W84.ImportFromEPSG(4326); W84.SetAxisMappingStrategy(osr.OAMS_TRADITIONAL_GIS_ORDER)
TO84 = osr.CoordinateTransformation(S5186, W84)
TO5186 = osr.CoordinateTransformation(W84, S5186)
rng = np.random.RandomState(61)
box = lambda x0, y0, x1, y1: f"POLYGON(({x0} {y0},{x1} {y0},{x1} {y1},{x0} {y1},{x0} {y0}))"

# 값 형식 세 가지 (정의서 코드 ↔ 코드명, lib/codebook.py 와 같은 글자)
USE = {"BDU001": "주거용단독주택", "BDU002": "주거용공동주택", "BDU003": "제1종근린생활시설", "BDU009": "의료시설", "BDU011": "노유자(노인및어린이)시설"}
KIND = {"BDC001": "일반주택", "BDC003": "아파트"}
ROADK = {"RDC014": "소로", "RDC001": "고속국도", "RDC004": "특별시도"}
MTRWY = {"MWI001": "일반", "MWI002": "자동차전용"}
STAIR = {"PGS001": "계단", "PGS002": "스텐드"}


def val(code, table, style):
    return {"code": code, "name": table[code], "lower": code.lower()}[style]


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
    return out, code


def shp(path, gtype, fields, feats, enc="UTF-8", cpg=True):
    """fields = [(이름, ogr 형식)]"""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    drv = ogr.GetDriverByName("ESRI Shapefile")
    if os.path.exists(path):
        drv.DeleteDataSource(path)
    ds = drv.CreateDataSource(path)
    lyr = ds.CreateLayer("l", S5186, gtype, options=[f"ENCODING={enc}"])
    for n, t in fields:
        lyr.CreateField(ogr.FieldDefn(n, t))
    for wkt, at in feats:
        ft = ogr.Feature(lyr.GetLayerDefn())
        for k, v in at.items():
            if v is not None and v != "":
                ft.SetField(k, v)
        ft.SetGeometry(ogr.CreateGeometryFromWkt(wkt))
        lyr.CreateFeature(ft)
    ds = None
    if not cpg and os.path.exists(os.path.splitext(path)[0] + ".cpg"):
        os.remove(os.path.splitext(path)[0] + ".cpg")


def dem(path, x0, y1, nx, ny, res, cx, cy):
    xs = x0 + np.arange(nx) * res + res / 2
    ys = y1 - np.arange(ny) * res - res / 2
    XX, YY = np.meshgrid(xs, ys)
    z = 30 + 60 * np.exp(-(((XX - cx) ** 2 + (YY - cy) ** 2) / (2 * 900 ** 2)))
    os.makedirs(os.path.dirname(path), exist_ok=True)
    r = gdal.GetDriverByName("HFA").Create(path, nx, ny, 1, gdal.GDT_Float32)
    r.SetGeoTransform((x0, res, 0, y1, 0, -res)); r.SetProjection(S5186.ExportToWkt())
    r.GetRasterBand(1).WriteArray(z.astype("float32")); r.GetRasterBand(1).SetNoDataValue(-9999); r = None


# 관악구: 실제처럼 1:5,000 도엽 11장 폴더로 나눔 (docs/1차방문_반출결과.md 의 도엽 번호, 37612 = 위 37°30′·왼쪽 126°45′, 1.5′ 칸 10×10)
GWANAK_SHEETS = ["007", "008", "009", "010", "017", "018", "019", "020", "028", "029", "030"]


def sheet_polys():
    """{도엽 폴더 이름: 도엽 네모(5186)}. 이웃 도엽은 같은 모서리 점을 써서 틈이 없음"""
    out = {}
    st = 1.5 / 60
    for i, sh in enumerate(GWANAK_SHEETS):
        n = int(sh) - 1
        top, left = 37.5 - (n // 10) * st, 126.75 + (n % 10) * st
        ring = ogr.Geometry(ogr.wkbLinearRing)
        for lon, lat in [(left, top), (left + st, top), (left + st, top - st), (left, top - st), (left, top)]:
            x, y, _ = TO5186.TransformPoint(lon, lat)
            ring.AddPoint_2D(x, y)
        g = ogr.Geometry(ogr.wkbPolygon); g.AddGeometry(ring)
        out[f"37612{sh}_2024_{357077400 + i:014d}" if sh != "008" else "37612008_2024_00000357077318"] = g
    return out


def clip(feats, poly, gtype):
    """도엽 네모로 자른 (wkt, 속성) 목록. 점은 안에 든 것만"""
    out = []
    for wkt, at in feats:
        g = ogr.CreateGeometryFromWkt(wkt)
        if gtype == ogr.wkbPoint:
            if poly.Contains(g):
                out.append((wkt, at))
            continue
        if not g.Intersects(poly):
            continue
        c = g.Intersection(poly)
        if c is None or c.IsEmpty():
            continue
        t = ogr.GT_Flatten(c.GetGeometryType())
        if t == ogr.wkbGeometryCollection:                  # 선·면만 골라 묶음
            want = (ogr.wkbLineString,) if gtype == ogr.wkbLineString else (ogr.wkbPolygon,)
            m = ogr.Geometry(ogr.wkbMultiLineString if gtype == ogr.wkbLineString else ogr.wkbMultiPolygon)
            for k in range(c.GetGeometryCount()):
                if ogr.GT_Flatten(c.GetGeometryRef(k).GetGeometryType()) in want:
                    m.AddGeometry(c.GetGeometryRef(k))
            if m.GetGeometryCount() == 0:
                continue
            c = m
        elif gtype == ogr.wkbLineString and t not in (ogr.wkbLineString, ogr.wkbMultiLineString):
            continue
        elif gtype == ogr.wkbPolygon and t not in (ogr.wkbPolygon, ogr.wkbMultiPolygon):
            continue
        out.append((c.ExportToWkt(), at))
    return out


S, I, I64, F = ogr.OFTString, ogr.OFTInteger, ogr.OFTInteger64, ogr.OFTReal
BLD_F = [("명칭", S), ("구분", S), ("종류", S), ("용도", S), ("주기", S), ("층수", I64), ("측량방법", S), ("UFID", S)]
ROAD_F = [("도로번호", S), ("명칭", S), ("도로구분", S), ("시점", S), ("종점", S), ("포장재질", S), ("분리대유무", S),
          ("차로수", I), ("도로폭", F), ("일방통행", S), ("자동차전용", S), ("기타", S), ("UFID", S)]


def main():
    G, CODE = gu_geoms()
    global SHEETS
    SHEETS = sheet_polys()
    meta, stops, parcels = {}, [], []
    for gi, gu in enumerate(GU):
        g = G[gu]
        x0, x1, y0, y1 = g.GetEnvelope()
        x0, y0, x1, y1 = np.floor(x0 / 100) * 100, np.floor(y0 / 100) * 100, np.ceil(x1 / 100) * 100, np.ceil(y1 / 100) * 100
        style = ("code", "name", "lower")[gi % 3]
        enc, cpg = "CP949", gi % 2 == 1                # 한글 칸 이름 "분리대유무" 는 CP949 로 10바이트 (dbf 칸 이름 한도) → 실제 자료도 CP949
        folder = f"376{12 + gi:02d}{gi + 1:03d}_2024_{357077318 + gi:014d}"
        d = os.path.join(R, "수치지형도2", folder)

        def put(fname, gtype, fields, feats):
            if gu != "관악구":
                shp(f"{d}/{fname}", gtype, fields, feats, enc, cpg)
                return
            for k, (sf, poly) in enumerate(SHEETS.items()):
                cf = clip(feats, poly, gtype)
                if cf:
                    shp(f"{R}/수치지형도2/{sf}/{fname}", gtype, fields, cf, enc, k % 2 == 1)
        # 길: 300m 격자 (소로·일반) + 고속국도 대각선 + 자동차전용 도로(격자 사이 가로)
        grid = lambda: {"도로구분": val("RDC014", ROADK, style), "자동차전용": val("MWI001", MTRWY, style), "차로수": 2, "도로폭": 6.0, "UFID": ""}
        roads = [(f"LINESTRING({x0} {y},{x1} {y})", dict(grid(), 명칭=f"가상{gi}로")) for y in np.arange(y0, y1 + 1, 300)]
        roads += [(f"LINESTRING({x} {y0},{x} {y1})", dict(grid(), 명칭=f"가상{gi}길")) for x in np.arange(x0, x1 + 1, 300)]
        ex_a = f"LINESTRING({x0 + 50} {y0 + 50},{x1 - 50} {y1 - 50})"
        ym = y0 + 150 + 300 * int((y1 - y0) / 600)            # 가운데쯤 격자 두 줄 사이
        ex_b = f"LINESTRING({x0} {ym},{x1} {ym})"
        roads.append((ex_a, {"도로구분": val("RDC001", ROADK, style), "자동차전용": val("MWI002", MTRWY, style), "명칭": "가상고속국도", "차로수": 6, "도로폭": 30.0}))
        roads.append((ex_b, {"도로구분": val("RDC004", ROADK, style), "자동차전용": val("MWI002", MTRWY, style), "명칭": "가상도시고속도로", "차로수": 4, "도로폭": 20.0}))
        put("N3L_A0020000.shp", ogr.wkbLineString, ROAD_F, roads)
        ex_len = ogr.CreateGeometryFromWkt(ex_a).Length() + ogr.CreateGeometryFromWkt(ex_b).Length()
        # 인도(보도) 면: 가로 길 절반을 따라 길 가운데선에서 4~7m 떨어진 폭 3m 띠
        side = [(box(x0, y + 4, x1, y + 7), {"UFID": "", "폭": 3.0, "재질": ""}) for y in np.arange(y0, y1 + 1, 600)]
        put("N3A_A0033320.shp", ogr.wkbPolygon, [("UFID", S), ("폭", F), ("재질", S)], side)
        # 건물: 동네 4곳 × 40채, 가로 길에서 15~45m
        gx, gy = np.arange(x0, x1 + 1, 300), np.arange(y0, y1 + 1, 300)
        cand = [(x, y) for x in gx for y in gy if x0 + 600 < x < x1 - 600 and y0 + 600 < y < y1 - 600]
        rng.shuffle(cand)
        centers = []
        if gu == "관악구":                                  # 동네 하나는 봉천동 선정지(external/sites.csv) 옆 격자 교차점 → 04 선정지 백분위가 계산되게
            sx_, sy_, _ = TO5186.TransformPoint(126.94017, 37.48075)
            centers.append((x0 + np.round((sx_ - x0) / 300) * 300, y0 + np.round((sy_ - y0) / 300) * 300))
        for cx_, cy_ in cand:
            p = ogr.Geometry(ogr.wkbPoint); p.AddPoint_2D(cx_, cy_)
            if g.Contains(p):
                centers.append((cx_, cy_))
            if len(centers) == 4:
                break
        pts = [(cx_ + rng.uniform(-110, 110), cy_ + rng.choice([-1, 1]) * rng.uniform(15, 45)) for cx_, cy_ in centers for _ in range(40)]
        use = rng.choice(list(USE), size=len(pts), p=[.5, .3, .12, .04, .04])
        flo = rng.randint(1, 8, size=len(pts))
        blds = [(box(x - 6, y - 6, x + 6, y + 6), {"명칭": "", "구분": "", "종류": val("BDC001" if u == "BDU001" else ("BDC003" if u == "BDU002" else "BDC001"), KIND, style),
                                                    "용도": val(u, USE, style), "주기": "", "층수": int(f), "측량방법": "", "UFID": f"B{gi:02d}{i:05d}"})
                for i, ((x, y), u, f) in enumerate(zip(pts, use, flo))]
        put("N3A_B0010000.shp", ogr.wkbPolygon, BLD_F, blds)
        cx, cy = g.PointOnSurface().GetX(), g.PointOnSurface().GetY()
        # 계단 1 (길을 가로지름) + 스텐드 1 (빠져야 함)
        sx = x0 + np.round((cx - x0) / 300) * 300          # 세로 길 위
        stairs = [(box(sx - 2, cy + 40, sx + 2, cy + 120), {"명칭": "", "구조": val("PGS001", STAIR, style), "폭": 4.0, "UFID": ""}),
                  (box(sx + 100, cy + 40, sx + 130, cy + 60), {"명칭": "", "구조": val("PGS002", STAIR, style), "폭": 30.0, "UFID": ""})]
        put("N3A_C0390000.shp", ogr.wkbPolygon, [("명칭", S), ("구조", S), ("폭", F), ("UFID", S)], stairs)
        # 정거장: 종류 칸 없음
        put("N3P_A0131122.shp", ogr.wkbPoint, [("명칭", S), ("UFID", S)],
            [(f"POINT({sx} {y0 + np.round((cy - y0) / 300) * 300 + 5})", {"명칭": f"가상{gi}역", "UFID": ""})])
        # 버스정류소 (공개 파일 모양): 동네마다 2곳, 길 위
        for k, (cx_, cy_) in enumerate(centers):
            for dx in (-150, 150):
                lon, lat, _ = TO84.TransformPoint(float(cx_ + dx), float(cy_))
                stops.append([f"가상{gi}-{k}{dx > 0:d} 정류소", round(lon, 7), round(lat, 7)])
        # DEM 5m (구 범위 + 200m), 관악구만 1m (가운데 2km)
        dem(f"{R}/수치표고모델_5m/dem5_{gi + 1:02d}.img", x0 - 200, y1 + 200, int((x1 - x0 + 400) / 5), int((y1 - y0 + 400) / 5), 5, cx, cy)
        if gu == "관악구":
            dem(f"{R}/수치표고모델_1m/dem1_{gi + 1:02d}.img", cx - 1000, cy + 1000, 2000, 2000, 1, cx, cy)
        # 필지: 건물마다 30m 네모 (19자리 고유번호), 소문자 칸
        for i, ((x, y), u, f) in enumerate(zip(pts, use, flo)):
            pnu = f"{CODE[gu]}10100{1}{i + 1:04d}{gi:04d}"
            parcels.append((box(x - 15, y - 15, x + 15, y + 15),
                            {"pnu": pnu, "sgg_cd": CODE[gu], "emd_cd": CODE[gu] + "10100", "jimok": "대" if i % 9 else "도",
                             "sgg_nm": gu, "emd_nm": f"가상{gi}동", "bldrgst_pk": "", "owner_nm": "OWNER-SHOULD-NOT-BE-READ", "jiga": "999999"}))
        meta[gu] = dict(folder=folder if gu != "관악구" else list(SHEETS)[0], folders=[folder] if gu != "관악구" else list(SHEETS), style=style, enc=enc, n_bld=len(pts), n_res=int(np.isin(use, ["BDU001", "BDU002"]).sum()),
                        ex_len_m=round(ex_len))
    pf = [(n, S) for n in ("pnu", "sgg_cd", "emd_cd", "jimok", "sgg_nm", "emd_nm", "bldrgst_pk", "owner_nm", "jiga")]
    shp(f"{R}/국토정보필지_서울특별시/AL_11_D194_LAND_INFO_BASE_MAP_202606/AL_11_D194_LAND_INFO_BASE_MAP_202606.shp",
        ogr.wkbPolygon, pf, parcels, "UTF-8", False)
    with open(f"{OUT}/bus_stops.csv", "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f); w.writerow(["name", "lon", "lat"]); w.writerows(stops)
    json.dump(meta, open(f"{OUT}/meta.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("완료:", OUT, {g: (m["folder"], m["style"], m["enc"]) for g, m in meta.items()})


if __name__ == "__main__":
    main()
