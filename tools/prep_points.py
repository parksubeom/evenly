# -*- coding: utf-8 -*-
"""
tools/prep_points.py ─ [안심구역 밖] 아무 점 CSV → name, lon, lat (범용 변환기)

[실행]  python3 tools/prep_points.py 원본.csv 출력.csv [EPSG:xxxx] [--seoul] [--drop 열=값 ...]
        예) 역사 좌표 → 공개 대조군 목적지:  python3 tools/prep_points.py 역사마스터.csv data_public/stations.csv
        좌표가 미터 단위(X·Y)면 세 번째 인자로 좌표계를 적습니다 (예: EPSG:5186, EPSG:5179, EPSG:5174)
[하는 일] 이름 열·경도/위도(또는 X/Y) 열을 자동으로 찾고, 미터 좌표면 경위도로 바꿔 name, lon, lat 만 남김
          (osgeo 가 있으면 osgeo, 없으면 pyproj). 좌표가 비었거나 숫자가 아닌 행은 뺌
          --seoul : 서울 행정동 경계(analysis/hbi/external/dong_boundary.geojson) 안의 점만 남김
          --drop 열=값 : 그 열이 그 값인 행을 뺌 (여러 번 가능). 예) 버스정류소의 --drop 정류소타입=한강선착장 (한강버스 배 선착장)
          원본이 .xlsx 면 첫 시트를 읽음 (표준 라이브러리만, 첫 줄 = 열 이름)
        예) 서울시 버스정류소 위치정보(xlsx, X좌표·Y좌표 = WGS84 경위도) → analysis/hbi/external/bus_stops.csv:
            python3 tools/prep_points.py "data_public/raw/서울시버스정류소위치정보(20260902).xlsx" analysis/hbi/external/bus_stops.csv --seoul --drop 정류소타입=한강선착장
[결과] 출력.csv (utf-8-sig) + 화면에 "읽음 → 좌표 있음 (→ 서울 안)" 행 수
"""
import csv, json, os, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

NAME = ["역사명", "역명", "정류장명", "정류소명", "시설명", "사업장명", "약국명", "기관명", "명칭", "이름", "name", "station_nm", "bldg_nm"]
LON = ["경도", "lon", "longitude", "lng", "x좌표(경도)"]
LAT = ["위도", "lat", "latitude", "y좌표(위도)"]
XC = ["x", "x좌표", "좌표정보(x)", "xcoord", "좌표x"]
YC = ["y", "y좌표", "좌표정보(y)", "ycoord", "좌표y"]


def read_xlsx(p):
    """xlsx 첫 시트 → [{열 이름: 값}] (openpyxl 없이 zip 안의 xml 을 읽음)"""
    import re, zipfile, xml.etree.ElementTree as ET
    M = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
    R = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}"
    z = zipfile.ZipFile(p)
    ss = []
    if "xl/sharedStrings.xml" in z.namelist():
        ss = ["".join(x.text or "" for x in si.iter(M + "t")) for si in ET.fromstring(z.read("xl/sharedStrings.xml")).findall(M + "si")]
    wb = ET.fromstring(z.read("xl/workbook.xml"))
    rid = {r.get("Id"): r.get("Target") for r in ET.fromstring(z.read("xl/_rels/workbook.xml.rels"))}
    sh = next(wb.iter(M + "sheet"))
    tgt = rid[sh.get(R + "id")].lstrip("/")
    tgt = tgt if tgt.startswith("xl/") else "xl/" + tgt
    rows = []
    for row in ET.fromstring(z.read(tgt)).iter(M + "row"):
        d = {}
        for c in row.iter(M + "c"):
            col = re.match(r"[A-Z]+", c.get("r")).group(0)
            v = c.find(M + "v")
            if v is None:
                isv = c.find(M + "is")
                d[col] = "".join(t.text or "" for t in isv.iter(M + "t")) if isv is not None else ""
            else:
                d[col] = ss[int(v.text)] if c.get("t") == "s" else v.text
        rows.append(d)
    if not rows:
        return []
    head = rows[0]
    print(f"xlsx: 시트 {sh.get('name')}, 열 {list(head.values())}, 행 {len(rows) - 1:,}")
    return [{head[k]: r.get(k, "") for k in head} for r in rows[1:]]


def read_any(p):
    if p.lower().endswith(".xlsx"):
        return read_xlsx(p)
    for enc in ("utf-8-sig", "cp949", "euc-kr"):
        try:
            with open(p, encoding=enc, newline="") as f:
                return list(csv.DictReader(f))
        except UnicodeDecodeError:
            continue
    raise SystemExit(f"인코딩을 알 수 없음: {p}")


def pick(cols, cands):
    norm = {c.replace(" ", "").lower(): c for c in cols}
    return next((norm[k.replace(" ", "").lower()] for k in cands if k.replace(" ", "").lower() in norm), None)


def num(v):
    try:
        return float(str(v).replace(",", "").strip())
    except ValueError:
        return None


def to_lonlat(xs, ys, epsg):
    try:
        from osgeo import osr
        osr.UseExceptions()
        s, t = osr.SpatialReference(), osr.SpatialReference()
        s.ImportFromEPSG(int(epsg.split(":")[1])); t.ImportFromEPSG(4326)
        for r in (s, t):
            r.SetAxisMappingStrategy(osr.OAMS_TRADITIONAL_GIS_ORDER)
        ct = osr.CoordinateTransformation(s, t)
        return [ct.TransformPoint(x, y)[:2] for x, y in zip(xs, ys)]
    except ImportError:
        from pyproj import Transformer
        tr = Transformer.from_crs(epsg, "EPSG:4326", always_xy=True)
        return [tr.transform(x, y) for x, y in zip(xs, ys)]


def in_seoul_fn():
    """서울 행정동 경계 안인지 판정하는 함수 (짝홀 규칙, 표준 라이브러리만)"""
    gj = json.load(open(os.path.join(ROOT, "analysis", "hbi", "external", "dong_boundary.geojson"), encoding="utf-8"))
    polys = []
    for ft in gj["features"]:
        g = ft["geometry"]
        rings = [r for poly in (g["coordinates"] if g["type"] == "MultiPolygon" else [g["coordinates"]]) for r in poly]
        xs = [x for r in rings for x, _ in r]; ys = [y for r in rings for _, y in r]
        polys.append((rings, min(xs), min(ys), max(xs), max(ys)))

    def inside(lon, lat):
        for rings, x0, y0, x1, y1 in polys:
            if not (x0 <= lon <= x1 and y0 <= lat <= y1):
                continue
            c = False
            for r in rings:
                j = len(r) - 1
                for i in range(len(r)):
                    (xi, yi), (xj, yj) = r[i], r[j]
                    if (yi > lat) != (yj > lat) and lon < (xj - xi) * (lat - yi) / (yj - yi + 1e-15) + xi:
                        c = not c
                    j = i
            if c:
                return True
        return False
    return inside


def main():
    argv = sys.argv[1:]
    drops = []
    while "--drop" in argv:                      # --drop 열=값
        i = argv.index("--drop")
        k, _, v = argv[i + 1].partition("=")
        drops.append((k, v))
        del argv[i:i + 2]
    args = [a for a in argv if a != "--seoul"]
    seoul = "--seoul" in argv
    if len(args) < 2:
        raise SystemExit(__doc__)
    src, dst = args[0], args[1]
    epsg = args[2] if len(args) > 2 else None
    rows = read_any(src)
    if not rows:
        raise SystemExit("빈 파일")
    for k, v in drops:
        if rows and k not in rows[0]:
            raise SystemExit(f"--drop 의 열 {k} 이 없음. 열: {list(rows[0])}")
        n0 = len(rows)
        rows = [r for r in rows if str(r.get(k, "")).strip() != v]
        print(f"--drop {k}={v}: {n0 - len(rows):,}행 뺌")
    cols = list(rows[0])
    cn, clon, clat, cx, cy = pick(cols, NAME), pick(cols, LON), pick(cols, LAT), pick(cols, XC), pick(cols, YC)
    print(f"인식한 열: 이름={cn}, 경도={clon}, 위도={clat}, X={cx}, Y={cy}")
    if not cn:
        raise SystemExit(f"이름 열을 찾지 못함. 열: {cols}")
    a, b = (clon, clat) if clon and clat else (cx, cy)
    if not (a and b):
        raise SystemExit(f"좌표 열을 찾지 못함. 열: {cols}")
    pts = [(r[cn], num(r[a]), num(r[b])) for r in rows]
    pts = [p for p in pts if p[1] is not None and p[2] is not None]
    if pts and not (120 < pts[0][1] < 135):                   # 경도 크기가 아니면 미터 좌표
        if not epsg:
            raise SystemExit("미터 좌표입니다. 세 번째 인자로 좌표계를 적어 주세요 (예: EPSG:5186)")
        ll = to_lonlat([p[1] for p in pts], [p[2] for p in pts], epsg)
        pts = [(p[0], x, y) for p, (x, y) in zip(pts, ll)]
    n_all = len(pts)
    if seoul:
        f_in = in_seoul_fn()
        pts = [p for p in pts if f_in(p[1], p[2])]
    with open(dst, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(["name", "lon", "lat"])
        w.writerows([[str(n).strip(), round(x, 6), round(y, 6)] for n, x, y in pts])
    print(f"읽음 {len(rows):,} → 좌표 있음 {n_all:,}" + (f" → 서울 행정동 경계 안 {len(pts):,}" if seoul else "") + f" → {dst}")


if __name__ == "__main__":
    main()
