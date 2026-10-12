# -*- coding: utf-8 -*-
"""
tools/check_survey_sources_gwanak.py ─ 관악 실측 기록지(docs/관악_실측기록지.html)의 후보 좌표를 원본 공개 자료에서 다시 읽어 대조

[실행]  ~/.evenly_envs/qpy tools/check_survey_sources_gwanak.py      (GDAL 이 있는 파이썬. data_public/raw 원본이 있어야 함 — git 에는 없음)
[하는 일] 기록지 1쪽의 후보 좌표 8쌍(위도, 경도)과 2쪽 입력 예시(od_pairs 5줄: ①~④ + 봉천 선정지 계단 검증 줄, interventions 1줄, 경도·위도)를
        HTML 에서 읽고, docs/관악_실측_후보좌표.md 의 출처 행을 원본에서 다시 읽어 소수 5자리로 같은지 봄. 정류소 번호(ARS)도 행에서 확인.
        ① 은 연속수치지형도 폭 3.4m 계단 길(DKRKXH·DKRE3H) 양 끝, ③ 은 교량 링크 × 하천변 산책로 링크의 교점(EPSG:5186).
        [v6.2] analysis/hbi/external/od_pairs.csv 의 관악 줄 좌표가 기록지와 같은지도 봄.
        [10/11] ① 계단 길이 이어지는지(a = 갈림길, b = 폭만 바뀌는 점), 2쪽 직선거리(약 31·437·375·219), interventions 줄이 vertical 인지,
        PDF(docs/관악_실측기록지.pdf) 글자에 같은 좌표·줄이 있는지, 인쇄본(~/Downloads/2차방문_인쇄/3_관악_실측기록지.pdf)이 레포 PDF 와 같은지도 봄. 다르면 종료 코드 1
"""
import csv, hashlib, html, json, math, os, re, subprocess, sys, zipfile  # noqa: F401
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
ly = ds.GetLayer(0)
sref = ly.GetSpatialRef().Clone(); sref.SetAxisMappingStrategy(osr.OAMS_TRADITIONAL_GIS_ORDER)


def vertex(ufid, k, width=None, native=False):
    """도로중심선 UFID 의 k 번째 꼭짓점 (경위도, native 면 원래 좌표). width 를 주면 도로폭(RVWD)도 확인"""
    ly.SetAttributeFilter(f"UFID = '{ufid}'")
    ft = ly.GetNextFeature(); assert ft is not None, f"UFID {ufid} 없음"
    ly.SetAttributeFilter(None)
    if width is not None:
        assert abs(ft.GetField("RVWD") - width) < 1e-6, (ufid, ft.GetField("RVWD"))
    g = ft.GetGeometryRef().Clone()
    if not native:
        g.Transform(osr.CoordinateTransformation(sref, s4326))
    g = g if g.GetGeometryCount() == 0 else g.GetGeometryRef(0)
    q = g.GetPoint(k if k >= 0 else g.GetPointCount() + k)
    return q[0], q[1]


def lines_at(xy, tol=0.01):
    """원래 좌표 xy 에서 끝점이 닿는 도로중심선 UFID 목록 (끝점 기준 갈림길 차수)"""
    ly.SetSpatialFilterRect(xy[0] - 1, xy[1] - 1, xy[0] + 1, xy[1] + 1)
    out = []
    for ft in ly:
        g = ft.GetGeometryRef(); g = g if g.GetGeometryCount() == 0 else g.GetGeometryRef(0)
        for q in (g.GetPoint(0), g.GetPoint(g.GetPointCount() - 1)):
            if math.hypot(q[0] - xy[0], q[1] - xy[1]) < tol:
                out.append(ft.GetField("UFID"))
    ly.SetSpatialFilter(None)
    return out


src["② d"] = vertex("A0020000000DKO4XY", 0)
# ① 봉천 선정지 계단 = 폭 3.4m 계단 길 (DKRKXH 3.58m + DKRE3H 27.49m): 아래 끝 = 대각선 길과 만나는 점, 위 끝 = 폭 6m 위 길(DKRNXK)과 만나는 점
src["① a"] = vertex("A0020000000DKRKXH", 0, 3.4)
src["① b"] = vertex("A0020000000DKRE3H", -1, 3.4)
assert (r5(src["① b"][0]), r5(src["① b"][1])) == tuple(map(r5, vertex("A0020000000DKRNXK", 0, 6.0))), "① b 가 DKRNXK 시작점이 아님"
# 계단 길이 이어지는지: DKRKXH 끝 = DKRE3H 시작, a 는 갈림길(선 3개 이상), b 는 폭만 바뀌는 점(DKRE3H·DKRNXK 두 선)
n_a, n_m, n_b = vertex("A0020000000DKRKXH", 0, native=True), vertex("A0020000000DKRKXH", -1, native=True), vertex("A0020000000DKRE3H", -1, native=True)
assert math.hypot(n_m[0] - vertex("A0020000000DKRE3H", 0, native=True)[0], n_m[1] - vertex("A0020000000DKRE3H", 0, native=True)[1]) < 0.01, "DKRKXH 끝 ≠ DKRE3H 시작"
TOPO = (len(lines_at(n_a)), sorted(lines_at(n_b)))

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
if len(od) != 5 or not od[4][0].startswith("봉천 선정지 계단"):
    bad.append(f"2쪽 od 예시가 다섯 줄(①~④ + 봉천 선정지 계단)이 아님: {[r[0] for r in od]}")
elif od[4][1:5] != od[0][1:5] or len(od[4]) != 7 or od[4][5] != "":
    bad.append(f"2쪽 봉천 선정지 계단 줄이 ① 과 좌표가 다르거나 잰 분이 비어 있지 않음: {od[4]}")
for i, rr in enumerate(od[:4]):
    k = ORDER[2 * i][0]
    want = (r5(src[k + " a" if k == "①" else k + " o"][0]), r5(src[k + " a" if k == "①" else k + " o"][1]),
            r5(src[k + " b" if k == "①" else k + " d"][0]), r5(src[k + " b" if k == "①" else k + " d"][1]))
    if len(rr) != 7 or tuple(map(float, rr[1:5])) != want:
        bad.append(f"2쪽 od 예시 {rr[0]}: {rr[1:5]} / 원본 {want} / 칸 {len(rr)}")
if len(iv) != 10 or iv[1] != "vertical" or tuple(map(float, iv[2:6])) != (r5(src["① a"][0]), r5(src["① a"][1]), r5(src["① b"][0]), r5(src["① b"][1])):
    bad.append(f"2쪽 interventions 예시: {iv}")
for n, (ars, name) in ARS.items():
    b = BUS.get(n) or []
    if (ars and (len(b) < 3 or b[1] != ars)) or (len(b) < 3 or b[2] != name):
        bad.append(f"버스정류소 xlsx {n}행: {b}")
# [v6.2] 다음 번들의 od_pairs.csv 관악 줄 = 기록지 예시와 같은 이름·좌표, 잰 분은 빈 칸
REPO = list(csv.reader(open(os.path.join(R, "analysis", "hbi", "external", "od_pairs.csv"), encoding="utf-8-sig")))
byname = {r[0]: r for r in REPO[1:] if r}
for rr in od:
    rp = byname.get(rr[0])
    if rp is None or rp[1:5] != rr[1:5] or rp[5] != "":
        bad.append(f"analysis/hbi/external/od_pairs.csv 의 '{rr[0]}' 줄: {rp}")
# [v6.2, 10/12] 다음 번들의 interventions.csv 봉천 줄 = 기록지 2쪽 interventions 예시와 같은 이름·종류·좌표·상태
IVR = {r[0]: r for r in list(csv.reader(open(os.path.join(R, "analysis", "hbi", "external", "interventions.csv"), encoding="utf-8-sig")))[1:] if r}
rp = IVR.get(iv[0])
if rp is None or rp[1:6] != iv[1:6] or rp[8] != iv[8]:
    bad.append(f"analysis/hbi/external/interventions.csv 의 '{iv[0]}' 줄: {rp}")
if TOPO[0] < 3 or TOPO[1] != ["A0020000000DKRE3H", "A0020000000DKRNXK"]:
    bad.append(f"① 계단 길 끝: a 에 닿는 선 {TOPO[0]}개 (3개 이상이어야 갈림길), b 에 닿는 선 {TOPO[1]}")
# 2쪽 '둘째 값(직선 m)' 안내: 봉천·① 약 31 · ② 약 437 · ③ 약 375 · ④ 약 219 (5자리 좌표 EPSG:5186 직선, ±1m)
m = re.search(r"봉천·① 약 (\d+) · ② 약 (\d+) · ③ 약 (\d+) · ④ 약 (\d+)", H)
if not m:
    bad.append("2쪽 직선거리 안내 문구를 찾지 못함")
else:
    for want, rr in zip(map(int, m.groups()), od[:4]):
        p, q = TO5186.TransformPoint(float(rr[1]), float(rr[2])), TO5186.TransformPoint(float(rr[3]), float(rr[4]))
        L = math.hypot(p[0] - q[0], p[1] - q[1])
        if abs(L - want) > 1.0:
            bad.append(f"2쪽 직선거리 {rr[0]}: 안내 {want} / 계산 {L:.1f}")
# 같은 이름 줄이 두 번 있거나, 칸이 7개가 아니거나, 검증 줄 메모가 기록지와 다르면
names = [r[0] for r in REPO[1:] if r]
if len(names) != len(set(names)) or any(len(r) != 7 for r in REPO if r):
    bad.append(f"od_pairs.csv 이름 겹침 또는 칸 수: {[r for r in REPO if r and len(r) != 7]} / {sorted(set(n for n in names if names.count(n) > 1))}")
if byname.get(od[4][0], [""] * 7)[6] != od[4][6] or od[4][6] != "서울시 발표: 계단을 피해 200m 이상 우회":
    bad.append(f"검증 줄 메모: 기록지 '{od[4][6]}' / od_pairs.csv '{byname.get(od[4][0], [''] * 7)[6]}'")
# PDF 글자: 1쪽 좌표 8쌍과 2쪽 예시 6줄이 그대로 들어 있는지 (빈칸 무시), 인쇄본이 레포 PDF 와 같은지
PDF = os.path.join(R, "docs", "관악_실측기록지.pdf")
txt = re.sub(r"\s+", "", subprocess.run(["pdftotext", PDF, "-"], capture_output=True, text=True, check=True).stdout)
miss = [f"{lat}, {lon}" for lon, lat in p1 if f"{lat:.5f},{lon:.5f}" not in txt]
miss += [",".join(r)[:30] for r in od + [iv] if re.sub(r"\s+", "", ",".join(r)) not in txt]
if miss:
    bad.append(f"PDF 글자에 없음 (HTML 을 고친 뒤 PDF 를 다시 만들지 않았을 수 있음): {miss}")
sha = lambda f: hashlib.sha256(open(f, "rb").read()).hexdigest()
PRN = os.path.expanduser("~/Downloads/2차방문_인쇄/3_관악_실측기록지.pdf")
if os.path.exists(PRN) and sha(PRN) != sha(PDF):
    bad.append(f"인쇄본이 레포 PDF 와 다름: {PRN} {sha(PRN)[:8]}… / 레포 {sha(PDF)[:8]}…")
print(f"① 계단 길: a 에 닿는 선 {TOPO[0]}개, b 에 닿는 선 {TOPO[1]}. PDF SHA-256 {sha(PDF)[:16]}…, 인쇄본 {'같음' if os.path.exists(PRN) and sha(PRN) == sha(PDF) else ('다름' if os.path.exists(PRN) else '없음')}")
for k in ORDER:
    print(f"{k}: 원본 {src[k][0]:.7f}, {src[k][1]:.7f} → {r5(src[k][0])}, {r5(src[k][1])}")
print("다름:", bad if bad else "없음 (1쪽 8쌍·2쪽 예시 6줄·정류소 5행이 원본과 같고, v6.2 od_pairs.csv 관악 5줄이 기록지와 같고, PDF 글자도 같음)")
sys.exit(1 if bad else 0)
