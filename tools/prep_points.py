# -*- coding: utf-8 -*-
"""
tools/prep_points.py ─ [안심구역 밖] 아무 점 CSV → name, lon, lat (범용 변환기)

[실행]  python3 tools/prep_points.py 원본.csv 출력.csv [EPSG:xxxx]
        예) 역사 좌표 → 공개 대조군 목적지:  python3 tools/prep_points.py 역사마스터.csv data_public/stations.csv
        좌표가 미터 단위(X·Y)면 세 번째 인자로 좌표계를 적습니다 (예: EPSG:5186, EPSG:5179, EPSG:5174)
[하는 일] 이름 열·경도/위도(또는 X/Y) 열을 자동으로 찾고, 미터 좌표면 경위도로 바꿔 name, lon, lat 만 남김
          (osgeo 가 있으면 osgeo, 없으면 pyproj). 좌표가 비었거나 숫자가 아닌 행은 뺌
[결과] 출력.csv (utf-8-sig) + 화면에 "읽음 → 좌표 있음" 행 수
"""
import csv, sys

NAME = ["역사명", "역명", "정류장명", "시설명", "사업장명", "약국명", "기관명", "명칭", "이름", "name", "station_nm", "bldg_nm"]
LON = ["경도", "lon", "longitude", "lng", "x좌표(경도)"]
LAT = ["위도", "lat", "latitude", "y좌표(위도)"]
XC = ["x", "x좌표", "좌표정보(x)", "xcoord", "좌표x"]
YC = ["y", "y좌표", "좌표정보(y)", "ycoord", "좌표y"]


def read_any(p):
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


def main():
    if len(sys.argv) < 3:
        raise SystemExit(__doc__)
    src, dst = sys.argv[1], sys.argv[2]
    epsg = sys.argv[3] if len(sys.argv) > 3 else None
    rows = read_any(src)
    if not rows:
        raise SystemExit("빈 파일")
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
    with open(dst, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(["name", "lon", "lat"])
        w.writerows([[str(n).strip(), round(x, 6), round(y, 6)] for n, x, y in pts])
    print(f"읽음 {len(rows):,} → 좌표 있음 {len(pts):,} → {dst}")


if __name__ == "__main__":
    main()
