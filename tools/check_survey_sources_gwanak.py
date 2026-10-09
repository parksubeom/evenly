# -*- coding: utf-8 -*-
"""
tools/check_survey_sources_gwanak.py ─ 관악 실측 기록지(docs/관악_실측기록지.html)의 후보 좌표를 원본 공개 자료에서 다시 읽어 대조

[실행]  ~/.evenly_envs/qpy tools/check_survey_sources_gwanak.py      (GDAL 이 있는 파이썬. data_public/raw 원본이 있어야 함 — git 에는 없음)
[하는 일] 기록지 1쪽의 후보 좌표 8쌍(위도, 경도)과 2쪽 입력 예시(od_pairs 4줄·interventions 1줄, 경도·위도)를 HTML 에서 읽고,
        docs/관악_실측_후보좌표.md 의 출처 행을 원본에서 다시 읽어 소수 5자리로 같은지 봄. 정류소 번호(ARS)도 행에서 확인.
        ③ 은 교량 링크 × 하천변 산책로 링크의 교점을 EPSG:5186 에서 계산. 다르면 종료 코드 1
"""
import csv, html, json, os, re, sys, zipfile
import xml.etree.ElementTree as ET
from osgeo import gdal, ogr, osr

gdal.UseExceptions(); ogr.UseExceptions(); osr.UseExceptions()
R = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW = os.path.join(R, "data_public", "raw")
r5 = lambda v: round(float(v) + 0.0, 5)
s4326 = osr.SpatialReference(); s4326.ImportFromEPSG(4326); s4326.SetAxisMappingStrategy(osr.OAMS_TRADITIONAL_GIS_ORDER)
s5186 = osr.SpatialReference(); s5186.ImportFromEPSG(5186); s5186.SetAxisMappingStrategy(osr.OAMS_TRADITIONAL_GIS_ORDER)
TO5186 = osr.CoordinateTransformation(s4326, s5186); TO4326 = osr.CoordinateTransformation(s5186, s4326)


def lines(path, encs=("utf-8-sig", "cp949")):
    for enc in encs:
        try:
            return open(path, encoding=enc).read().split("\n")
        except UnicodeDecodeError:
            continue
    raise SystemExit(f"인코딩을 모름: {path}")


def pt(s):
    m = re.search(r"POINT\s*\(([\d.]+) ([\d.]+)\)", s)
    return float(m.group(1)), float(m.group(2))


# ── 원본에서 다시 읽기 ─────────────────────────────────────────
src = {}
osm = json.load(open(os.path.join(RAW, "osm_steps_gwanak.json"), encoding="utf-8"))["elements"]
w = osm[28]
assert w["type"] == "way" and w["id"] == 195921558 and w.get("tags", {}).get("name") == "장군봉5길", "OSM elements[28] 가 way 195921558 장군봉5길 이 아님"
nodes = {e["id"]: (e["lon"], e["lat"]) for e in osm if e["type"] == "node"}
geo = w.get("geometry") or []
end = lambda k, nid: nodes.get(nid) or (geo[k]["lon"], geo[k]["lat"])
src["① a"], src["① b"] = end(0, w["nodes"][0]), end(-1, w["nodes"][-1])

WN = lines(os.path.join(RAW, "서울시 자치구별 도보 네트워크 공간정보.csv"))
WH = next(csv.reader([WN[0]]))
row = lambda n: dict(zip(WH, next(csv.reader([WN[n - 1]]))))
r = row(384646); assert r["노드 ID"] == "116039"; src["② o"] = pt(r["노드 WKT"])
r = row(389528); assert r["노드 ID"] == "18372"; src["④ d"] = pt(r["노드 WKT"])


def link(n):
    g = ogr.CreateGeometryFromWkt(row(n)["링크 WKT"]); g.Transform(TO5186); return g


path = link(392710)                                           # 하천변 산책로 링크 153504
for key, n in (("③ o", 392364), ("③ d", 392148)):            # 교량 링크 79060 · 184384
    x = path.Intersection(link(n))
    assert not x.IsEmpty(), f"{key}: 교점 없음"
    c = x.Centroid(); c.Transform(TO4326); src[key] = (c.GetX(), c.GetY())

zp = os.path.join(RAW, "(연속수치지형도)도로중심선_001.zip")   # 국토지리정보원 공개 연속수치지형도 원본
ds = gdal.OpenEx(f"/vsizip/{zp}/N3L_A0020000_001.shp", gdal.OF_VECTOR)
ly = ds.GetLayer(0); ly.SetAttributeFilter("UFID = 'A0020000000DKO4XY'")
ft = ly.GetNextFeature(); assert ft is not None, "UFID A0020000000DKO4XY 없음"
g = ft.GetGeometryRef().Clone(); s = ly.GetSpatialRef().Clone(); s.SetAxisMappingStrategy(osr.OAMS_TRADITIONAL_GIS_ORDER)
g.Transform(osr.CoordinateTransformation(s, s4326))
q = g.GetPoint(0) if g.GetGeometryCount() == 0 else g.GetGeometryRef(0).GetPoint(0)
src["② d"] = (q[0], q[1])

EL = lines(os.path.join(RAW, "서울시 지하철역 엘리베이터 위치정보.csv"), ("cp949", "utf-8-sig"))
EH = next(csv.reader([EL[0]]))
er = dict(zip(EH, next(csv.reader([EL[395]]))))
assert er.get("지하철역명") == "낙성대", er
src["④ o"] = pt(next(v for v in er.values() if "POINT" in str(v)))

z = zipfile.ZipFile(os.path.join(RAW, "서울시버스정류소위치정보(20260902).xlsx"))
ns = {"m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
ss = ["".join(t.itertext()) for t in ET.fromstring(z.read("xl/sharedStrings.xml")).findall("m:si", ns)] if "xl/sharedStrings.xml" in z.namelist() else []


def cells(rw):
    out = []
    for c in rw.findall("m:c", ns):
        v, isx = c.find("m:v", ns), c.find("m:is", ns)
        out.append(ss[int(v.text)] if c.get("t") == "s" and v is not None else ("".join(isx.itertext()) if isx is not None else (v.text if v is not None else "")))
    return out


BUS = {int(rw.get("r")): cells(rw) for rw in ET.fromstring(z.read("xl/worksheets/sheet1.xml")).find("m:sheetData", ns).findall("m:row", ns)}
ARS = {8701: ("21189", "쑥고개"), 8805: (None, "봉림교"), 8806: (None, "봉림교"), 8907: ("21546", "현대홈타운아파트"), 8945: ("21587", "현대홈타운아파트")}

# ── 기록지에서 읽기 ───────────────────────────────────────────
H = open(os.path.join(R, "docs", "관악_실측기록지.html"), encoding="utf-8").read()
p1 = [(float(lon), float(lat)) for lat, lon in re.findall(r"<b>(37\.\d{5}), (126\.\d{5})</b>", H)]
blocks = [html.unescape(b) for b in re.findall(r'<div class="c">(.*?)</div>', H, re.S)]
od = [next(csv.reader([x])) for x in blocks[0].split("\n") if x.strip()]
iv = next(csv.reader([blocks[1].strip()]))
ORDER = ["① a", "① b", "② o", "② d", "③ o", "③ d", "④ o", "④ d"]
bad = []
if len(p1) != 8:
    bad.append(f"1쪽 좌표가 {len(p1)}쌍 (8쌍이어야 함)")
for k, (lon, lat) in zip(ORDER, p1):
    if (r5(src[k][0]), r5(src[k][1])) != (lon, lat):
        bad.append(f"1쪽 {k}: 기록지 {lon}, {lat} / 원본 {src[k]}")
for i, rr in enumerate(od):
    k = ORDER[2 * i][0]
    want = (r5(src[k + " a" if k == "①" else k + " o"][0]), r5(src[k + " a" if k == "①" else k + " o"][1]),
            r5(src[k + " b" if k == "①" else k + " d"][0]), r5(src[k + " b" if k == "①" else k + " d"][1]))
    if len(rr) != 7 or tuple(map(float, rr[1:5])) != want:
        bad.append(f"2쪽 od 예시 {rr[0]}: {rr[1:5]} / 원본 {want} / 칸 {len(rr)}")
if len(iv) != 10 or tuple(map(float, iv[2:6])) != (r5(src["① a"][0]), r5(src["① a"][1]), r5(src["① b"][0]), r5(src["① b"][1])):
    bad.append(f"2쪽 interventions 예시: {iv}")
for n, (ars, name) in ARS.items():
    b = BUS.get(n) or []
    if (ars and (len(b) < 3 or b[1] != ars)) or (len(b) < 3 or b[2] != name):
        bad.append(f"버스정류소 xlsx {n}행: {b}")
for k in ORDER:
    print(f"{k}: 원본 {src[k][0]:.7f}, {src[k][1]:.7f} → {r5(src[k][0])}, {r5(src[k][1])}")
print("다름:", bad if bad else "없음 (1쪽 8쌍·2쪽 예시 5줄·정류소 5행 모두 원본과 같음)")
sys.exit(1 if bad else 0)
