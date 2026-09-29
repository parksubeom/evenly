# -*- coding: utf-8 -*-
"""
tools/prep_public.py ─ [반입 전, 안심구역 밖에서] 공개 데이터 CSV → external/ 형식(name, lon, lat)으로 정리

[실행]  python tools/prep_public.py pharmacy  원본.csv  [EPSG:xxxx]   → external/pharmacy.csv
        python tools/prep_public.py elevator  원본.csv  [EPSG:xxxx]   → external/subway_elevators.csv
        EPSG 는 좌표가 미터 단위(X·Y)일 때만 적습니다. 예) 지방행정 인허가 데이터 "좌표정보(X)" 는 보통 EPSG:5174
[하는 일]
  1. 열 이름 자동 인식: 이름(약국명·사업장명·역명 …), 경도·위도 또는 X·Y, 주소, 영업상태
  2. 주소 열이 있으면 "서울" 이 들어간 행만, 영업상태 열이 있으면 폐업·휴업 행은 뺌
  3. 미터 좌표면 경위도로 변환 (osgeo, 없으면 pyproj). 서울 범위 밖 점은 뺌
[결과] 화면에 "읽음 → 서울 → 영업 중 → 좌표 있음 → 서울 범위 안" 행 수가 나오고, external/ 에 파일이 생김
       JS로 치면 rows.filter(서울).filter(영업중).map(r => ({name, lon, lat})) 을 CSV 로 저장하는 스크립트입니다.
"""
import csv, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
EXT = os.path.join(HERE, "..", "external")
OUT = {"pharmacy": "pharmacy.csv", "elevator": "subway_elevators.csv"}
NAME = ["약국명", "사업장명", "요양기관명", "기관명", "역명", "역사명", "시설명", "name", "이름", "명칭"]
LON = ["경도", "lon", "longitude", "lng", "x좌표(경도)"]
LAT = ["위도", "lat", "latitude", "y좌표(위도)"]
XC = ["좌표정보(x)", "좌표정보x(epsg5174)", "x", "x좌표", "xcoord", "좌표x"]
YC = ["좌표정보(y)", "좌표정보y(epsg5174)", "y", "y좌표", "ycoord", "좌표y"]
ADDR = ["소재지전체주소", "도로명전체주소", "주소", "도로명주소", "지번주소", "소재지도로명주소", "소재지지번주소"]
STAT = ["영업상태명", "상세영업상태명", "영업상태", "운영상태"]
SEOUL = (126.76, 37.41, 127.19, 37.72)      # 서울 경위도 범위 (서, 남, 동, 북)


def read_any(p):
    """utf-8-sig → cp949 → euc-kr 순서로 읽기"""
    for enc in ("utf-8-sig", "cp949", "euc-kr"):
        try:
            with open(p, encoding=enc, newline="") as f:
                return list(csv.DictReader(f))
        except UnicodeDecodeError:
            continue
    raise SystemExit(f"인코딩을 알 수 없음: {p}")


def pick(cols, cands):
    """열 이름 목록에서 후보와 맞는 첫 열 (대소문자·공백 무시)"""
    norm = {c.replace(" ", "").lower(): c for c in cols}
    for k in cands:
        if k.replace(" ", "").lower() in norm:
            return norm[k.replace(" ", "").lower()]
    return None


def num(v):
    try:
        return float(str(v).replace(",", "").strip())
    except ValueError:
        return None


def to_lonlat(xs, ys, epsg):
    """미터 좌표 → 경위도. osgeo 우선, 안 되면 pyproj"""
    try:
        from osgeo import osr
        osr.UseExceptions()
        s, t = osr.SpatialReference(), osr.SpatialReference()
        s.ImportFromEPSG(int(epsg.split(":")[1])); t.ImportFromEPSG(4326)
        for r in (s, t):
            r.SetAxisMappingStrategy(osr.OAMS_TRADITIONAL_GIS_ORDER)   # (x, y) = (경도, 위도) 순서 고정
        ct = osr.CoordinateTransformation(s, t)
        return [ct.TransformPoint(x, y)[:2] for x, y in zip(xs, ys)], "osgeo"
    except ImportError:
        from pyproj import Transformer
        tr = Transformer.from_crs(epsg, "EPSG:4326", always_xy=True)
        return [tr.transform(x, y) for x, y in zip(xs, ys)], "pyproj"


def main():
    if len(sys.argv) < 3 or sys.argv[1] not in OUT:
        raise SystemExit(__doc__)
    kind, src = sys.argv[1], sys.argv[2]
    epsg = sys.argv[3] if len(sys.argv) > 3 else None
    rows = read_any(src)
    if not rows:
        raise SystemExit("빈 파일")
    cols = list(rows[0].keys())
    cn, clon, clat, cx, cy, ca, cs = (pick(cols, NAME), pick(cols, LON), pick(cols, LAT), pick(cols, XC), pick(cols, YC),
                                      pick(cols, ADDR), pick(cols, STAT))
    print(f"인식한 열: 이름={cn}, 경도={clon}, 위도={clat}, X={cx}, Y={cy}, 주소={ca}, 영업상태={cs}")
    if not cn:
        raise SystemExit(f"이름 열을 찾지 못함. 열 목록: {cols}")
    n0 = len(rows)
    if ca:
        rows = [r for r in rows if "서울" in str(r.get(ca, ""))]
    n1 = len(rows)
    if cs:
        rows = [r for r in rows if not any(w in str(r.get(cs, "")) for w in ("폐업", "휴업", "취소", "말소"))]
    n2 = len(rows)
    if clon and clat:
        pts = [(r[cn], num(r[clon]), num(r[clat])) for r in rows]
        pts = [p for p in pts if p[1] is not None and p[2] is not None]
        how = "경위도 그대로"
    elif cx and cy:
        raw = [(r[cn], num(r[cx]), num(r[cy])) for r in rows]
        raw = [p for p in raw if p[1] is not None and p[2] is not None]
        if raw and 120 < raw[0][1] < 135:                    # X 열인데 값이 경도 크기면 경위도로 봄
            pts, how = raw, "X·Y 가 경위도"
        else:
            if not epsg:
                raise SystemExit("미터 좌표입니다. 세 번째 인자로 좌표계를 적어 주세요. 예) EPSG:5174 (인허가 데이터), EPSG:5186, EPSG:5179")
            ll, how = to_lonlat([p[1] for p in raw], [p[2] for p in raw], epsg)
            pts = [(p[0], a, b_) for p, (a, b_) in zip(raw, ll)]
            how = f"{epsg} → 경위도 ({how})"
    else:
        raise SystemExit(f"좌표 열을 찾지 못함. 열 목록: {cols}")
    n3 = len(pts)
    pts = [p for p in pts if SEOUL[0] <= p[1] <= SEOUL[2] and SEOUL[1] <= p[2] <= SEOUL[3]]
    dst = os.path.abspath(os.path.join(EXT, OUT[kind]))
    with open(dst, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(["name", "lon", "lat"])
        for nm, lon, lat in pts:
            w.writerow([str(nm).strip(), round(lon, 6), round(lat, 6)])
    print(f"읽음 {n0:,} → 서울 {n1:,} → 영업 중 {n2:,} → 좌표 있음 {n3:,} → 서울 범위 안 {len(pts):,}  (좌표: {how})")
    print(f"→ {dst}")


if __name__ == "__main__":
    main()
