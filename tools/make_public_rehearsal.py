# -*- coding: utf-8 -*-
"""
tools/make_public_rehearsal.py ─ 공개데이터로 "관악구 대역 리허설" 자료 만들기  ※ 안심구역 반입 안 함, 결과는 실제 결과가 아님

[왜] 안심구역 1차 반출 구조(관악 1:5,000 11도엽, 한글 칸, 정의서 코드, CP949)를 공개데이터로 흉내 내어,
     v6.1 번들이 실제와 비슷한 크기·모양의 자료에서 끝까지 도는지, 결과 분포가 말이 되는지 미리 봄
[출처] (모두 data_public/raw/, 원본은 바꾸지 않음)
  - 길: 연속수치지형도 도로중심선 _001·_008 (국토지리정보원, 설계서 Ver 5.1.1 칸)
  - 건물: GIS건물통합정보 서울 (`건물통합정보.shp` = 이름만 .shp 인 zip, AL_D010_11_20260909)
  - 계단: 오픈스트리트맵 highway=steps (© OpenStreetMap contributors, ODbL). 받은 응답은 osm_steps_gwanak.json 에 저장해 다시 씀
  - 역: 서울시 역사마스터 정보.csv
  - 높이: 등고선(--contour)을 주면 5m·1m 격자로 보간, 없으면 공개 지형 AWS terrarium z15(약 30m)를 5m 격자로 (경사가 실제보다 완만함)
  - 필지: LX맵 필지 서울 (LX_MAP_SEOUL_202608.zip 안의 구별 zip 을 그대로 복사)
  - 건축물대장: analysis/hbi/external/building_register.csv (공개 표제부 8개 구 요약본)
[대응표] 공개 값 → 정의서 코드는 리허설용으로만 (docs/리허설_코드대응.md). 대응이 없는 값은 비워 둠 (추정해 채우지 않음)
[실행] (QGIS 파이썬) python tools/make_public_rehearsal.py [--out data_public/rehearsal/박수범] [--style code|name] [--contour <등고선 zip·shp>]
       python tools/make_public_rehearsal.py --selftest-contour   (30m 지형으로 등고선을 만들어 다시 격자로 → 보간 오차 확인)
[결과] <out>/ (안심구역 바탕화면 폴더 모양)
  수치지형도2/37612xxx_2024_공개대역/ N3L_A0020000·N3A_B0010000·N3A_C0390000·N3P_A0131122 .shp (한글 칸, CP949, 도엽 경계에서 잘림)
  수치표고모델_5m/, 수치표고모델_1m/ (1m 은 봉천동 선정지 둘레 2km, 경로 시험용), 국토정보필지_서울특별시/*.zip,
  building_register.csv, hbi_code_bundle_v6.1.txt, 공개대역_README.txt, rehearsal_meta.json
"""
import argparse, csv, json, math, os, re, shutil, sys, unicodedata, urllib.parse, urllib.request, zipfile
import numpy as np
from osgeo import gdal, ogr, osr
gdal.UseExceptions(); ogr.UseExceptions(); osr.UseExceptions()

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW = os.path.join(ROOT, "data_public", "raw")
sys.path.insert(0, os.path.join(ROOT, "analysis", "hbi"))
sys.path.insert(0, os.path.join(ROOT, "tools"))
from lib import codebook as K                       # noqa: E402  정의서 별표 2 코드표
import public_baseline as PB                        # noqa: E402  공개 지형 타일 (받기·이상값 메우기)

GWANAK_SHEETS = ["007", "008", "009", "010", "017", "018", "019", "020", "028", "029", "030"]   # docs/1차방문_반출결과.md
BONGCHEON = (126.94017, 37.48075)                   # external/sites.csv 의 관악구 봉천동 선정지

# ── 대응표 (docs/리허설_코드대응.md 와 같아야 함) ─────────────────────────────
# 연속수치지형도 도로구분 RDDV (Ver 5.1.1) → 정의서 ROAD_SE. 이름이 같은 것만. RDD000 미분류는 정의서에 없어 비움
ROAD_SE = {"RDD001": "RDC001", "RDD002": "RDC002", "RDD003": "RDC003", "RDD004": "RDC004", "RDD005": "RDC005",
           "RDD006": "RDC006", "RDD007": "RDC007", "RDD008": "RDC010", "RDD009": "RDC014"}
RDD_NAME = {"RDD000": "미분류", "RDD001": "고속국도", "RDD002": "일반국도", "RDD003": "지방도", "RDD004": "특별시도", "RDD005": "광역시도",
            "RDD006": "시도", "RDD007": "군도", "RDD008": "면리간도로", "RDD009": "소로"}       # 설계서 Ver 5.1.1 표
# 자동차전용 흉내 (공개판에 칸이 없음): 도로구분 고속국도이거나 명칭에 "고속국도" 가 들어가면 MWI002, 나머지 MWI001
def mtrwy_of(rddv, name):
    return "MWI002" if rddv == "RDD001" or "고속국도" in (name or "") else "MWI001"
# GIS건물통합정보 용도명 A9 (건축물대장 주용도) → 정의서 BPRP_SE: **이름으로** 맞춤 (번호 nn000 은 27 까지만 BDU0nn 과 순서가 같고,
#   29000 장례식장처럼 뒤는 어긋남). 핵심 글자(공백·점·"시설"·"관련"·"및"·"주거용"·괄호 안 글자를 뺀 것)가 **같을 때만** 같은 것으로 봄.
#   이름이 바뀐 분류는 아래 동의어로만. Z3000 근린생활시설·Z6000 판매및영업시설·Z8000 교육연구및복지시설 같은 옛 분류는 대응 없음 → 비움
USE_SYNONYM = {"분뇨.쓰레기처리시설": "BDU022",    # 건축법 개정으로 자원순환관련시설
               "동.식물 관련시설": "BDU021",        # 동물및식물관련시설
               "장례식장": "BDU028"}                # 장례시설


def _core(t):
    return re.sub(r"\([^)]*\)|[\s.·]|시설|관련|및|주거용", "", t or "")


def bdu_of(a9):
    a9 = (a9 or "").strip()
    if not a9:
        return ""
    if a9 in USE_SYNONYM:
        return USE_SYNONYM[a9]
    c = _core(a9)
    hit = [k for k, v in K.codes("N3A_B0010000", "BPRP_SE").items() if k != "BDU999" and c and c == _core(v)]   # 핵심 글자가 같을 때만
    return hit[0] if len(hit) == 1 else ""


# 종류 BULD_SE: GIS 에는 종류 칸이 없음 → 용도명이 단독주택인 것만 BDC001 일반주택, 나머지는 비움 (공동주택은 연립·아파트를 가를 수 없음)
def bdc_of(a9):
    return "BDC001" if (a9 or "").strip() == "단독주택" else ""
STAIR = "PGS001"                                    # OSM highway=steps → 정의서 계단 구조 PGS001 계단


def nfc_path(name):
    """맥 파일 이름(NFD)을 NFC 이름으로 찾기"""
    for f in os.listdir(RAW):
        if unicodedata.normalize("NFC", f) == unicodedata.normalize("NFC", name):
            return os.path.join(RAW, f)
    raise SystemExit(f"data_public/raw 에 없음: {name}")


def srs(epsg):
    s = osr.SpatialReference(); s.ImportFromEPSG(epsg); s.SetAxisMappingStrategy(osr.OAMS_TRADITIONAL_GIS_ORDER)
    return s


S5179, S5186, S4326 = srs(5179), srs(5186), srs(4326)
LL2M = osr.CoordinateTransformation(S4326, S5179)
M2LL = osr.CoordinateTransformation(S5179, S4326)


def sheet_polys():
    """{폴더 이름: 도엽 네모(EPSG:5179)}. 1:50,000 37612 (위 37°30′, 왼쪽 126°45′) 안 1.5′ 칸 10×10, 북서부터 001"""
    out, st = {}, 1.5 / 60
    for sh in GWANAK_SHEETS:
        n = int(sh) - 1
        top, left = 37.5 - (n // 10) * st, 126.75 + (n % 10) * st
        ring = ogr.Geometry(ogr.wkbLinearRing)
        for lon, lat in [(left, top), (left + st, top), (left + st, top - st), (left, top - st), (left, top)]:
            x, y, _ = LL2M.TransformPoint(lon, lat)
            ring.AddPoint_2D(x, y)
        g = ogr.Geometry(ogr.wkbPolygon); g.AddGeometry(ring)
        out[f"37612{sh}_2024_공개대역"] = g
    return out


def sheet_lonlat():
    """관악 11도엽을 감싸는 경위도 (아래 위도, 위 위도, 왼쪽 경도, 오른쪽 경도)"""
    st = 1.5 / 60
    tops = [37.5 - ((int(s) - 1) // 10) * st for s in GWANAK_SHEETS]
    lefts = [126.75 + ((int(s) - 1) % 10) * st for s in GWANAK_SHEETS]
    return min(tops) - st, max(tops), min(lefts), max(lefts) + st


def clip(feats, poly, gtype):
    """도엽 네모로 자른 (도형, 속성) 목록. 점은 안에 든 것만"""
    out = []
    px0, px1, py0, py1 = poly.GetEnvelope()
    for g, at in feats:
        x0, x1, y0, y1 = g.GetEnvelope()
        if x1 < px0 or x0 > px1 or y1 < py0 or y0 > py1:
            continue
        if gtype == ogr.wkbPoint:
            if poly.Contains(g):
                out.append((g, at))
            continue
        if not g.Intersects(poly):
            continue
        c = g.Intersection(poly)
        if c is None or c.IsEmpty():
            continue
        t = ogr.GT_Flatten(c.GetGeometryType())
        want = (ogr.wkbLineString, ogr.wkbMultiLineString) if gtype == ogr.wkbLineString else (ogr.wkbPolygon, ogr.wkbMultiPolygon)
        if t == ogr.wkbGeometryCollection:
            m = ogr.Geometry(ogr.wkbMultiLineString if gtype == ogr.wkbLineString else ogr.wkbMultiPolygon)
            for k in range(c.GetGeometryCount()):
                if ogr.GT_Flatten(c.GetGeometryRef(k).GetGeometryType()) in want[:1]:
                    m.AddGeometry(c.GetGeometryRef(k))
            if m.GetGeometryCount() == 0:
                continue
            c = m
        elif t not in want:
            continue
        out.append((c, at))
    return out


def shp(path, gtype, fields, feats, cpg):
    """CP949 shp 쓰기. fields = [(이름, ogr 형식, 폭)]. cpg=False 면 .cpg 를 지움 (1차 자료처럼 인코딩 표시가 없는 파일)"""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    drv = ogr.GetDriverByName("ESRI Shapefile")
    if os.path.exists(path):
        drv.DeleteDataSource(path)
    ds = drv.CreateDataSource(path)
    lyr = ds.CreateLayer("l", S5179, gtype, options=["ENCODING=CP949"])
    for n, t, w in fields:
        fd = ogr.FieldDefn(n, t)
        if w:
            fd.SetWidth(w)
        if t == ogr.OFTReal:
            fd.SetPrecision(2)                      # 소수 둘째 자리까지 (안 주면 dbf 에 N(w,0) 으로 써져 정수로 반올림됨)
        lyr.CreateField(fd)
    for g, at in feats:
        ft = ogr.Feature(lyr.GetLayerDefn())
        for k, v in at.items():
            if v is not None and v != "":
                ft.SetField(k, v)
        ft.SetGeometry(g)
        lyr.CreateFeature(ft)
    ds = None
    if not cpg and os.path.exists(os.path.splitext(path)[0] + ".cpg"):
        os.remove(os.path.splitext(path)[0] + ".cpg")


def name_style(layer, field, code, style):
    """style=name 이면 코드 대신 정의서 코드명 (예: BDU001 → 주거용단독주택)"""
    if style == "code" or not code:
        return code
    return K.codes(layer, field).get(code, code)


# ── 길 ────────────────────────────────────────────────────────────
ROAD_F = [("도로번호", ogr.OFTString, 30), ("명칭", ogr.OFTString, 100), ("도로구분", ogr.OFTString, 20), ("시점", ogr.OFTString, 50),
          ("종점", ogr.OFTString, 50), ("포장재질", ogr.OFTString, 20), ("분리대유무", ogr.OFTString, 20), ("차로수", ogr.OFTInteger, 5),
          ("도로폭", ogr.OFTReal, 13), ("일방통행", ogr.OFTString, 20), ("자동차전용", ogr.OFTString, 20), ("기타", ogr.OFTString, 50),
          ("UFID", ogr.OFTString, 34)]


def read_roads(bb, style, meta):
    feats, kinds, mt = [], {}, {"MWI001": 0, "MWI002": 0}
    for k in ("001", "008"):
        p = "/vsizip/" + nfc_path(f"(연속수치지형도)도로중심선_{k}.zip") + f"/N3L_A0020000_{k}.shp"
        ds = gdal.OpenEx(p, gdal.OF_VECTOR, open_options=["ENCODING=CP949"])
        lyr = ds.GetLayer(0)
        lyr.SetSpatialFilterRect(*bb)
        for f in lyr:
            rddv, name = f.GetField("RDDV"), f.GetField("NAME")
            se, mw = ROAD_SE.get(rddv, ""), mtrwy_of(rddv, name)
            kinds[rddv] = kinds.get(rddv, 0) + 1
            mt[mw] += 1
            feats.append((f.GetGeometryRef().Clone(), {
                "도로번호": f.GetField("RDNU"), "명칭": name, "도로구분": name_style("N3L_A0020000", "ROAD_SE", se, style),
                "시점": f.GetField("STPT"), "종점": f.GetField("EDPT"), "차로수": f.GetField("RDLN"), "도로폭": f.GetField("RVWD"),
                "자동차전용": name_style("N3L_A0020000", "MTRWY_SE", mw, style), "기타": f.GetField("REST"), "UFID": f.GetField("UFID")}))
        ds = None
    meta["roads"] = {"read": len(feats), "RDDV": kinds, "MTRWY": mt}
    return feats


# ── 건물 ──────────────────────────────────────────────────────────
BLD_F = [("명칭", ogr.OFTString, 100), ("구분", ogr.OFTString, 20), ("종류", ogr.OFTString, 20), ("용도", ogr.OFTString, 40),
         ("주기", ogr.OFTString, 50), ("층수", ogr.OFTInteger64, 10), ("측량방법", ogr.OFTString, 20), ("UFID", ogr.OFTString, 34)]


def read_buildings(bb, style, meta):
    p = "/vsizip/{" + nfc_path("건물통합정보.shp") + "}/AL_D010_11_20260909.shp"
    ds = gdal.OpenEx(p, gdal.OF_VECTOR, open_options=["ENCODING=CP949"])
    lyr = ds.GetLayer(0)
    to = osr.CoordinateTransformation(S5179, S5186)
    (ax, ay, _), (bx, by, _) = to.TransformPoint(bb[0], bb[1]), to.TransformPoint(bb[2], bb[3])
    lyr.SetSpatialFilterRect(min(ax, bx) - 200, min(ay, by) - 200, max(ax, bx) + 200, max(ay, by) + 200)
    back = osr.CoordinateTransformation(S5186, S5179)
    feats, n_use, n_none, pairs, gw = [], {}, 0, {}, 0
    for f in lyr:
        a8, a9 = f.GetField("A8"), f.GetField("A9")
        use = bdu_of(a9)
        key = f"{a8} {a9} → {use or '(대응 없음, 비움)'}"
        if a9:
            pairs[key] = pairs.get(key, 0) + 1
        else:
            n_none += 1
        if use:
            n_use[use] = n_use.get(use, 0) + 1
        if f.GetField("A23") == "11620":
            gw += 1
        g = f.GetGeometryRef().Clone(); g.Transform(back)
        fl = f.GetField("A26")
        feats.append((g, {"종류": name_style("N3A_B0010000", "BULD_SE", bdc_of(a9), style), "용도": name_style("N3A_B0010000", "BPRP_SE", use, style),
                          "층수": int(fl) if fl not in (None, "") else None, "UFID": f.GetField("A21")}))
    ds = None
    meta["buildings"] = {"read": len(feats), "gwanak_A23_11620": gw, "use_codes": n_use, "no_use": n_none, "use_pairs": dict(sorted(pairs.items()))}
    return feats


# ── 계단 (오픈스트리트맵) ─────────────────────────────────────────
def read_stairs(bb, meta, refresh=False):
    cache = os.path.join(RAW, "osm_steps_gwanak.json")
    lat0, lat1, lon0, lon1 = sheet_lonlat()            # 도엽 경위도 그대로 (5179 네모의 두 모서리만 바꾸면 서쪽 가장자리 약 18m 가 빠짐)
    lat0, lon0, lat1, lon1 = lat0 - 0.0005, lon0 - 0.0005, lat1 + 0.0005, lon1 + 0.0005
    if refresh or not os.path.exists(cache) or json.load(open(cache, encoding="utf-8")).get("_query_bbox") != [lat0, lon0, lat1, lon1]:
        q = f'[out:json][timeout:120];way["highway"="steps"]({lat0},{lon0},{lat1},{lon1});out geom;'
        req = urllib.request.Request("https://overpass-api.de/api/interpreter", data=urllib.parse.urlencode({"data": q}).encode(),
                                     headers={"User-Agent": "evenly-rehearsal/1.0"})
        with urllib.request.urlopen(req, timeout=180) as r:
            data = json.loads(r.read().decode("utf-8"))
        data["_query_bbox"] = [lat0, lon0, lat1, lon1]
        json.dump(data, open(cache, "w", encoding="utf-8"), ensure_ascii=False)
    data = json.load(open(cache, encoding="utf-8"))
    feats, widths = [], 0
    for e in data.get("elements", []):
        pts = e.get("geometry") or []
        if e.get("type") != "way" or len(pts) < 2:
            continue
        ls = ogr.Geometry(ogr.wkbLineString)
        for pnt in pts:
            x, y, _ = LL2M.TransformPoint(pnt["lon"], pnt["lat"])
            ls.AddPoint_2D(x, y)
        w = None
        try:
            w = float(str(e.get("tags", {}).get("width", "")).replace("m", "").strip())
            widths += 1
        except ValueError:
            w = None
        poly = ls.Buffer((w or 3.0) / 2, 4)            # 선 → 면 (폭이 없으면 3m 로 봄, 수치지형도 계단은 면)
        feats.append((poly, {"구조": STAIR, "폭": w}))
    meta["stairs"] = {"osm_ways": len(feats), "with_width": widths, "osm_timestamp": data.get("osm3s", {}).get("timestamp_osm_base"),
                      "source": "© OpenStreetMap contributors (ODbL)"}
    return feats


# ── 역 ────────────────────────────────────────────────────────────
def read_stations(meta):
    p = nfc_path("서울시 역사마스터 정보.csv")
    for enc in ("utf-8-sig", "cp949"):
        try:
            rows = list(csv.DictReader(open(p, encoding=enc)))
            break
        except UnicodeDecodeError:
            continue
    feats = []
    for r in rows:
        try:
            lat, lon = float(r["위도"]), float(r["경도"])
        except (KeyError, ValueError):
            continue
        x, y, _ = LL2M.TransformPoint(lon, lat)
        g = ogr.Geometry(ogr.wkbPoint); g.AddPoint_2D(x, y)
        feats.append((g, {"명칭": r.get("역사명")}))
    meta["stations"] = {"read": len(feats)}
    return feats


# ── 높이 ──────────────────────────────────────────────────────────
def terrarium(lon, lat):
    """경위도 배열 → 공개 지형 높이 (z15 타일 모자이크에서 쌍선형). public_baseline 의 타일 받기·이상값 메우기를 그대로 씀"""
    be = PB.Osgeo()
    px, py = PB.tile_xy(lon, lat)
    px, py = px - 0.5, py - 0.5
    tx0, ty0 = int(np.floor(px.min() / 256)), int(np.floor(py.min() / 256))
    tx1, ty1 = int(np.floor((px.max() + 1) / 256)), int(np.floor((py.max() + 1) / 256))
    mos = np.zeros(((ty1 - ty0 + 1) * 256, (tx1 - tx0 + 1) * 256))
    for tx in range(tx0, tx1 + 1):
        for ty in range(ty0, ty1 + 1):
            mos[(ty - ty0) * 256:(ty - ty0 + 1) * 256, (tx - tx0) * 256:(tx - tx0 + 1) * 256] = PB.get_tile(be, tx, ty)
    gx, gy = px - tx0 * 256, py - ty0 * 256
    x0, y0 = np.floor(gx).astype(int), np.floor(gy).astype(int)
    dx, dy = gx - x0, gy - y0
    v = lambda yy, xx: mos[np.clip(yy, 0, mos.shape[0] - 1), np.clip(xx, 0, mos.shape[1] - 1)]
    return (v(y0, x0) * (1 - dx) * (1 - dy) + v(y0, x0 + 1) * dx * (1 - dy) + v(y0 + 1, x0) * (1 - dx) * dy + v(y0 + 1, x0 + 1) * dx * dy)


def grid_cells(bb, res):
    x0, y1 = math.floor(bb[0] / res) * res, math.ceil(bb[3] / res) * res
    nx, ny = int(math.ceil((bb[2] - x0) / res)), int(math.ceil((y1 - bb[1]) / res))
    return x0, y1, nx, ny


def write_img(path, arr, x0, y1, res):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    r = gdal.GetDriverByName("HFA").Create(path, arr.shape[1], arr.shape[0], 1, gdal.GDT_Float32)
    r.SetGeoTransform((x0, res, 0, y1, 0, -res)); r.SetProjection(S5179.ExportToWkt())
    b = r.GetRasterBand(1); b.WriteArray(arr.astype("float32")); b.SetNoDataValue(-9999); r = None


def dem_from_terrain(bb, res):
    x0, y1, nx, ny = grid_cells(bb, res)
    xs = x0 + (np.arange(nx) + 0.5) * res
    ys = y1 - (np.arange(ny) + 0.5) * res
    out = np.empty((ny, nx))
    for i in range(0, ny, 400):                       # 줄 묶음으로 (메모리)
        XX, YY = np.meshgrid(xs, ys[i:i + 400])
        ll = np.asarray(M2LL.TransformPoints(np.c_[XX.ravel(), YY.ravel()].tolist()))
        out[i:i + 400] = terrarium(ll[:, 0], ll[:, 1]).reshape(XX.shape)
    return out, x0, y1


def dem_from_contours(src, bb, res):
    """등고선(선, 높이 칸) → 격자: 선을 높이 값으로 그리고 빈 칸을 주변 값으로 메움 (GDAL FillNodata, 거리 가중)"""
    ds = gdal.OpenEx(src, gdal.OF_VECTOR)
    lyr = ds.GetLayer(0)
    d = lyr.GetLayerDefn()
    num = [d.GetFieldDefn(i).GetName() for i in range(d.GetFieldCount()) if d.GetFieldDefn(i).GetType() in (ogr.OFTReal, ogr.OFTInteger, ogr.OFTInteger64)]
    # 높이 칸 고르기: (1) 이름이 높이처럼 생긴 칸 먼저 (2) 값이 0~900m 이고 여러 선에 되풀이되는 숫자 칸 (번호 칸은 값이 모두 달라 빠짐)
    pref = sorted(num, key=lambda n: 0 if re.search(r"ELEV|HEIG|CONT|ALT|HGT|높이|표고|등고", n, re.I) else 1)
    fld = None
    for n in pref:
        vals = [f.GetField(n) for _, f in zip(range(3000), lyr)]
        lyr.ResetReading()
        v = [x for x in vals if x is not None]
        if not v or not (0 <= min(v) and max(v) <= 900) or len(set(v)) < 3:
            continue
        if re.search(r"ELEV|HEIG|CONT|ALT|HGT|높이|표고|등고", n, re.I) or len(set(v)) / len(v) < 0.5:
            fld = n
            break
    if not fld:
        raise SystemExit(f"등고선 높이 칸을 찾지 못함. 숫자 칸: {num}")
    x0, y1, nx, ny = grid_cells(bb, res)
    r = gdal.GetDriverByName("MEM").Create("", nx, ny, 1, gdal.GDT_Float32)
    r.SetGeoTransform((x0, res, 0, y1, 0, -res)); r.SetProjection(S5179.ExportToWkt())
    b = r.GetRasterBand(1); b.SetNoDataValue(-9999); b.Fill(-9999)
    gdal.RasterizeLayer(r, [1], lyr, options=[f"ATTRIBUTE={fld}", "ALL_TOUCHED=TRUE"])
    gdal.FillNodata(b, None, maxSearchDist=max(nx, ny), smoothingIterations=0)
    return b.ReadAsArray().astype(float), x0, y1, fld


def selftest_contour():
    """30m 지형으로 5m 격자 → 5m 간격 등고선 → 다시 5m 격자: 보간 오차 (등고선을 받았을 때 방법이 쓸 만한지)"""
    bb = (948500.0, 1938500.0, 950500.0, 1940500.0)
    ref, x0, y1 = dem_from_terrain(bb, 5.0)
    r = gdal.GetDriverByName("MEM").Create("", ref.shape[1], ref.shape[0], 1, gdal.GDT_Float32)
    r.SetGeoTransform((x0, 5.0, 0, y1, 0, -5.0)); r.SetProjection(S5179.ExportToWkt()); r.GetRasterBand(1).WriteArray(ref)
    mem = ogr.GetDriverByName("Memory").CreateDataSource("c")
    cl = mem.CreateLayer("c", S5179, ogr.wkbLineString); cl.CreateField(ogr.FieldDefn("ID", ogr.OFTInteger)); cl.CreateField(ogr.FieldDefn("ELEV", ogr.OFTReal))
    gdal.ContourGenerate(r.GetRasterBand(1), 5.0, 0.0, [], 0, 0, cl, 0, 1)
    tmp = "/vsimem/contour.gpkg"
    gdal.VectorTranslate(tmp, mem, format="GPKG")
    out, _, _, fld = dem_from_contours(tmp, bb, 5.0)
    e = out - ref
    print(f"등고선 보간 자체 시험 (2km 창, 5m 간격 등고선 {cl.GetFeatureCount()}개, 높이 칸 {fld}): "
          f"평균 절대 오차 {np.mean(np.abs(e)):.2f}m, 95% {np.percentile(np.abs(e), 95):.2f}m, 최대 {np.abs(e).max():.2f}m")


# ── 필지 ──────────────────────────────────────────────────────────
def gu_in(bb):
    """도엽 네모에 걸치는 서울 구 → {구 이름: 시군구 코드 5자리}"""
    ds = ogr.Open(os.path.join(ROOT, "analysis", "hbi", "external", "dong_boundary.geojson"))
    lyr = ds.GetLayer(0)
    s = lyr.GetSpatialRef(); s.SetAxisMappingStrategy(osr.OAMS_TRADITIONAL_GIS_ORDER)
    ct = osr.CoordinateTransformation(s, S5179)
    box = ogr.CreateGeometryFromWkt(f"POLYGON(({bb[0]} {bb[1]},{bb[2]} {bb[1]},{bb[2]} {bb[3]},{bb[0]} {bb[3]},{bb[0]} {bb[1]}))")
    out = {}
    for f in lyr:
        g = f.GetGeometryRef().Clone(); g.Transform(ct)
        if g.Intersects(box):
            out[f.GetField("sggnm")] = str(f.GetField("ADM_CD"))[:5]
    return out


def copy_parcels(out_dir, gus, meta):
    """LX맵 필지 서울 zip 에서 도엽에 걸치는 구의 zip 만 그대로 꺼냄. 관악구 시군구 코드는 11620 (행정동 코드 앞 5자리와 다를 수 있어 이름표로 맞춤)"""
    SGG = {"종로구": "11110", "중구": "11140", "용산구": "11170", "성동구": "11200", "광진구": "11215", "동대문구": "11230", "중랑구": "11260",
           "성북구": "11290", "강북구": "11305", "도봉구": "11320", "노원구": "11350", "은평구": "11380", "서대문구": "11410", "마포구": "11440",
           "양천구": "11470", "강서구": "11500", "구로구": "11530", "금천구": "11545", "영등포구": "11560", "동작구": "11590", "관악구": "11620",
           "서초구": "11650", "강남구": "11680", "송파구": "11710", "강동구": "11740"}
    z = zipfile.ZipFile(nfc_path("LX_MAP_SEOUL_202608.zip"))
    dst = os.path.join(out_dir, "국토정보필지_서울특별시")
    os.makedirs(dst, exist_ok=True)
    got = []
    for gu in gus:
        n = f"AL_{SGG[gu]}_LAND_INFO_BASE_MAP_202608.zip"
        if n in z.namelist():
            with z.open(n) as a, open(os.path.join(dst, n), "wb") as b:
                shutil.copyfileobj(a, b)
            got.append(n)
    meta["parcels"] = {"zips": got}


# ── 묶기 ──────────────────────────────────────────────────────────
def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", default=os.path.join(ROOT, "data_public", "rehearsal", "박수범"))
    ap.add_argument("--style", choices=["code", "name"], default="code", help="값 형식: code (BDU001) / name (주거용단독주택)")
    ap.add_argument("--contour", help="등고선 파일 (zip 이면 /vsizip/ 경로로). 없으면 공개 30m 지형")
    ap.add_argument("--refresh-osm", action="store_true")
    ap.add_argument("--selftest-contour", action="store_true")
    a = ap.parse_args()
    if a.selftest_contour:
        selftest_contour()
        return
    out = os.path.abspath(a.out)
    if os.path.exists(out):                         # 지난 리허설 자료만 지움 (다른 폴더를 잘못 주면 멈춤)
        if not os.path.exists(os.path.join(out, "공개대역_README.txt")):
            raise SystemExit(f"--out 이 비어 있지 않고 공개 대역 자료 폴더도 아닙니다 (공개대역_README.txt 없음): {out}")
        shutil.rmtree(out)
    os.makedirs(out)
    sheets = sheet_polys()
    env = [g.GetEnvelope() for g in sheets.values()]
    bb = (min(e[0] for e in env), min(e[2] for e in env), max(e[1] for e in env), max(e[3] for e in env))
    meta = {"style": a.style, "sheets": list(sheets), "bbox_5179": [round(v) for v in bb]}
    layers = [("N3L_A0020000.shp", ogr.wkbLineString, ROAD_F, read_roads(bb, a.style, meta)),
              ("N3A_B0010000.shp", ogr.wkbPolygon, BLD_F, read_buildings(bb, a.style, meta)),
              ("N3A_C0390000.shp", ogr.wkbPolygon, [("명칭", ogr.OFTString, 100), ("구조", ogr.OFTString, 20), ("폭", ogr.OFTReal, 7), ("UFID", ogr.OFTString, 34)],
               [(g, {"구조": name_style("N3A_C0390000", "ARSFCKD_SE", at["구조"], a.style), "폭": at["폭"]}) for g, at in read_stairs(bb, meta, a.refresh_osm)]),
              ("N3P_A0131122.shp", ogr.wkbPoint, [("명칭", ogr.OFTString, 100), ("UFID", ogr.OFTString, 34)], read_stations(meta))]
    written, wc = {}, {}
    for fname, gt, fields, feats in layers:
        for k, (sf, poly) in enumerate(sheets.items()):
            cf = clip(feats, poly, gt)
            if cf:
                shp(os.path.join(out, "수치지형도2", sf, fname), gt, fields, cf, cpg=(k % 2 == 1))   # 도엽마다 .cpg 있음·없음 번갈아
                written[fname] = written.get(fname, 0) + len(cf)
                for _, at in cf:                     # 실제로 써진 조각 기준 코드 수 (보고서 숫자는 이것으로)
                    for col in ("도로구분", "자동차전용", "용도", "구조"):
                        if col in at:
                            key = f"{fname[:-4]}.{col}"
                            v = at[col] or "(빈 값)"
                            wc.setdefault(key, {})[v] = wc.setdefault(key, {}).get(v, 0) + 1
    meta["written_per_layer"] = written
    meta["written_codes"] = wc
    meta["note"] = ("roads.read·buildings.read·MTRWY 는 도엽을 감싼 네모 안에서 읽은 수 (자르기 전). 도엽 안 실제 수는 written_per_layer·written_codes. "
                    "건물(GIS건물통합정보)·역(역사마스터)은 서울만이라 도엽의 경기(과천·안양) 쪽에는 건물이 없음. 빈 레이어는 파일을 만들지 않음")
    # 높이
    dbb = (bb[0] - 200, bb[1] - 200, bb[2] + 200, bb[3] + 200)
    if a.contour:
        z5, x0, y1, fld = dem_from_contours(a.contour, dbb, 5.0)
        meta["dem"] = {"source": f"등고선 {os.path.basename(a.contour)} (높이 칸 {fld}) → 5m 보간"}
    else:
        z5, x0, y1 = dem_from_terrain(dbb, 5.0)
        meta["dem"] = {"source": "공개 지형 AWS terrarium z15 (약 30m) → 5m 쌍선형. 경사가 실제(5m DEM)보다 완만하게 나올 것으로 봄 "
                                 "(10/8 리허설에서는 HBI 가 1차 실제보다 높게 나옴: 결과 보고 참고). 물가 픽셀에 실제보다 꺼진 값이 남을 수 있음 (관악 안 16.8~619m 는 정상)"}
    write_img(os.path.join(out, "수치표고모델_5m", "dem5_gwanak.img"), z5, x0, y1, 5.0)
    bx, by, _ = LL2M.TransformPoint(*BONGCHEON)
    b1 = (bx - 1000, by - 1000, bx + 1000, by + 1000)
    if a.contour:
        z1, x1_, y11, _ = dem_from_contours(a.contour, b1, 1.0)
    else:
        z1, x1_, y11 = dem_from_terrain(b1, 1.0)
    write_img(os.path.join(out, "수치표고모델_1m", "dem1_bongcheon.img"), z1, x1_, y11, 1.0)
    meta["dem"]["1m"] = "봉천동 선정지 둘레 2km 만 (1m 경로 시험용. 같은 원천이라 5m 와 다른 정보는 없음)"
    gus = gu_in(bb)
    meta["gu_in_sheets"] = gus
    copy_parcels(out, gus, meta)
    shutil.copy(os.path.join(ROOT, "analysis", "hbi", "external", "building_register.csv"), os.path.join(out, "building_register.csv"))
    shutil.copy(os.path.join(ROOT, "deliverables", "hbi_code_bundle_v6.1.txt"), os.path.join(out, "hbi_code_bundle_v6.1.txt"))
    open(os.path.join(out, "공개대역_README.txt"), "w", encoding="utf-8-sig").write(
        "이 폴더는 공개데이터로 만든 '관악구 대역 리허설' 자료입니다. 안심구역 자료가 아니며, 이 자료로 낸 결과는 실제 결과가 아닙니다.\n"
        "만든 도구: tools/make_public_rehearsal.py, 대응표: docs/리허설_코드대응.md\n"
        "계단: © OpenStreetMap contributors (ODbL)\n")
    json.dump(meta, open(os.path.join(out, "rehearsal_meta.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(json.dumps({k: meta[k] for k in ("roads", "buildings", "stairs", "stations", "written_per_layer", "dem", "parcels", "gu_in_sheets")},
                     ensure_ascii=False, indent=1))
    print("완료:", out)


if __name__ == "__main__":
    main()
