# -*- coding: utf-8 -*-
"""
tools/prep_public.py ─ [반입 전, 안심구역 밖에서] 공개 데이터 CSV → external/ 형식(name, lon, lat)으로 정리

[실행]
  python tools/prep_public.py pharmacy 건강_약국_서울특별시.csv [EPSG:5174]
      → external/pharmacy.csv
  python tools/prep_public.py elevator "서울시 지하철역 엘리베이터 위치정보.csv" [--check-stations 역사마스터.csv]
      → external/subway_elevators.csv  (노드 유형 코드 1 = 지하철 출입구 행만)
[하는 일]
  1. 열 이름 자동 인식: 이름(약국명·사업장명·지하철역명 …), 경도·위도 / X·Y / WKT "POINT(경도 위도)", 주소, 영업상태
     엘리베이터 파일처럼 "노드링크 유형" 열이 있으면 NODE 행만 씀
  2. 주소 열이 있으면 "서울" 이 들어간 행만, 영업상태 열이 있으면 폐업·휴업 행은 뺌
  3. 미터 좌표면 경위도로 변환 (osgeo, 없으면 pyproj). 서울 범위 밖 점은 뺌
  4. [좌표계 검증] 주소 열이 있으면 변환한 점이 들어가는 행정동(external/dong_boundary.geojson)의 구와
     주소의 구가 같은 비율을 계산. 후보 좌표계를 나란히 비교해 가장 잘 맞는 것을 쓰고, 99% 미만이면 저장하지 않음
     (좌표계가 어긋나면 점이 수백 m 밀려 옆 구로 들어가기 때문)
  5. [엘리베이터 검증] --check-stations 를 주면 같은 역 이름의 역사 좌표와의 거리 분포, 500m 넘게 떨어진 엘리베이터 목록
[결과] 화면에 단계별 행 수와 검증 결과, external/ 에 파일 (utf-8-sig, name, lon, lat)
       JS로 치면 rows.filter(서울).filter(영업중).map(r => ({name, lon, lat})) 를 CSV 로 저장하고, 결과를 지도 경계로 교차검증하는 스크립트
"""
import csv, json, math, os, re, sys

HERE = os.path.dirname(os.path.abspath(__file__))
EXT = os.path.join(HERE, "..", "external")
OUT = {"pharmacy": "pharmacy.csv", "elevator": "subway_elevators.csv"}
NAME = ["지하철역명", "약국명", "사업장명", "요양기관명", "기관명", "역명", "역사명", "시설명", "name", "이름", "명칭"]
LON = ["경도", "lon", "longitude", "lng", "x좌표(경도)"]
LAT = ["위도", "lat", "latitude", "y좌표(위도)"]
XC = ["좌표정보(x)", "좌표정보x(epsg5174)", "x", "x좌표", "xcoord", "좌표x"]
YC = ["좌표정보(y)", "좌표정보y(epsg5174)", "y", "y좌표", "ycoord", "좌표y"]
WKT = ["노드 wkt", "노드wkt", "wkt", "geometry", "geom"]
ADDR = ["도로명주소", "지번주소", "소재지전체주소", "도로명전체주소", "주소", "소재지도로명주소", "소재지지번주소"]
STAT = ["영업상태명", "상세영업상태명", "영업상태", "운영상태"]
SEOUL = (126.76, 37.41, 127.19, 37.72)      # 서울 경위도 범위 (서, 남, 동, 북)
# 미터 좌표 후보 (검증에서 나란히 비교). 인허가 데이터는 보통 "보정계수 없는 Bessel 중부원점 TM" = EPSG:5174
BESSEL_TOWGS84 = "+towgs84=-115.80,474.99,674.11,1.16,-2.31,-1.63,6.43"
CANDS = {
    "EPSG:5174": "EPSG:5174",
    "EPSG:5174 + towgs84": "+proj=tmerc +lat_0=38 +lon_0=127.0028902777778 +k=1 +x_0=200000 +y_0=500000 +ellps=bessel " + BESSEL_TOWGS84 + " +units=m +no_defs",
    "EPSG:2097": "EPSG:2097",
    "EPSG:5181": "EPSG:5181",
    "EPSG:5186": "EPSG:5186",
}


def read_any(p):
    """utf-8-sig → cp949 → euc-kr 순서로 읽기"""
    for enc in ("utf-8-sig", "cp949", "euc-kr"):
        try:
            with open(p, encoding=enc, newline="") as f:
                return list(csv.DictReader(f)), enc
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


def to_lonlat(xs, ys, crs):
    """미터 좌표 → 경위도. osgeo 우선, 안 되면 pyproj. crs 는 "EPSG:xxxx" 또는 proj 문자열"""
    try:
        from osgeo import osr
        osr.UseExceptions()
        s, t = osr.SpatialReference(), osr.SpatialReference()
        if crs.upper().startswith("EPSG:"):
            s.ImportFromEPSG(int(crs.split(":")[1]))
        else:
            s.ImportFromProj4(crs)
        t.ImportFromEPSG(4326)
        for r in (s, t):
            r.SetAxisMappingStrategy(osr.OAMS_TRADITIONAL_GIS_ORDER)   # (x, y) = (경도, 위도) 순서 고정
        ct = osr.CoordinateTransformation(s, t)
        return [tuple(ct.TransformPoint(x, y)[:2]) for x, y in zip(xs, ys)], "osgeo"
    except ImportError:
        from pyproj import Transformer
        tr = Transformer.from_crs(crs, "EPSG:4326", always_xy=True)
        return [tr.transform(x, y) for x, y in zip(xs, ys)], "pyproj"


# ── 검증용: 행정동 경계(경위도)로 점이 속한 구 찾기 (표준 라이브러리만) ─────────
def load_gu_polys():
    p = os.path.join(EXT, "dong_boundary.geojson")
    if not os.path.exists(p):
        return None
    gj = json.load(open(p, encoding="utf-8"))
    out = []
    for ft in gj["features"]:
        g = ft["geometry"]
        polys = g["coordinates"] if g["type"] == "MultiPolygon" else [g["coordinates"]]
        rings = [ring for poly in polys for ring in poly]
        xs = [x for r in rings for x, _ in r]; ys = [y for r in rings for _, y in r]
        out.append((ft["properties"].get("sggnm", ""), rings, (min(xs), min(ys), max(xs), max(ys))))
    return out


def gu_of(lon, lat, polys):
    for gu, rings, (x0, y0, x1, y1) in polys:
        if not (x0 <= lon <= x1 and y0 <= lat <= y1):
            continue
        inside = False
        for r in rings:                       # 짝홀 규칙 점-다각형 판정
            j = len(r) - 1
            for i in range(len(r)):
                (xi, yi), (xj, yj) = r[i], r[j]
                if (yi > lat) != (yj > lat) and lon < (xj - xi) * (lat - yi) / (yj - yi + 1e-15) + xi:
                    inside = not inside
                j = i
        if inside:
            return gu
    return None


def addr_gu(a):
    m = re.search(r"서울(?:특별시)?\s+(\S+구)", str(a))
    return m.group(1) if m else None


def gu_match(pts, polys):
    """pts = [(이름, 경도, 위도, 주소구), ...] → (일치 수, 비교 수)"""
    ok = n = 0
    for _, lon, lat, g in pts:
        if not g:
            continue
        n += 1
        ok += gu_of(lon, lat, polys) == g
    return ok, n


def hav(a, b, c, d):
    """두 경위도 사이 거리(m)"""
    R = 6371000.0
    p1, p2 = math.radians(b), math.radians(d)
    x = math.sin((p2 - p1) / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(math.radians(c - a) / 2) ** 2
    return 2 * R * math.asin(math.sqrt(x))


def station_key(s):
    """역 이름 표준화: 괄호 부분·끝의 '역'·공백 제거"""
    s = re.sub(r"\(.*?\)", "", str(s)).replace(" ", "")
    return s[:-1] if s.endswith("역") and len(s) > 2 else s


def main():
    args = sys.argv[1:]
    chk = None
    if "--check-stations" in args:
        i = args.index("--check-stations"); chk = args[i + 1]; del args[i:i + 2]
    if len(args) < 2 or args[0] not in OUT:
        raise SystemExit(__doc__)
    kind, src = args[0], args[1]
    epsg = args[2] if len(args) > 2 else None
    rows, enc = read_any(src)
    if not rows:
        raise SystemExit("빈 파일")
    cols = list(rows[0].keys())
    cn, clon, clat, cx, cy, cw, ca, cs = (pick(cols, NAME), pick(cols, LON), pick(cols, LAT), pick(cols, XC), pick(cols, YC),
                                          pick(cols, WKT), pick(cols, ADDR), pick(cols, STAT))
    ct = pick(cols, ["노드링크 유형", "노드링크유형"])
    print(f"파일 인코딩 {enc}, 행 {len(rows):,}")
    print(f"인식한 열: 이름={cn}, 경도={clon}, 위도={clat}, X={cx}, Y={cy}, WKT={cw}, 주소={ca}, 영업상태={cs}, 노드링크유형={ct}")
    if not cn:
        raise SystemExit(f"이름 열을 찾지 못함. 열 목록: {cols}")
    steps = [("읽음", len(rows))]
    if ct:
        rows = [r for r in rows if str(r.get(ct, "")).strip().upper() == "NODE"]
        steps.append(("NODE 행", len(rows)))
        tc = pick(cols, ["노드 유형 코드", "노드유형코드"])
        if tc:
            from collections import Counter
            print(f"  '{tc}' 분포: {dict(Counter(r.get(tc, '') for r in rows))}  (0 일반노드, 1 지하철 출입구, 2 버스 정류장, 3 지하보도 출입구)")
            if kind == "elevator":
                # 엘리베이터 목적지(station_ev)는 "지하철 출입구"(코드 1) 노드만 씀. 0·2 는 출입구가 아닌 지점
                rows = [r for r in rows if str(r.get(tc, "")).strip() == "1"]
                steps.append(("노드 유형 1(지하철 출입구)", len(rows)))
    if ca:
        rows = [r for r in rows if "서울" in str(r.get(ca, "")) or not str(r.get(ca, "")).strip()]
        steps.append(("서울(주소 빈 칸 포함)", len(rows)))
    if cs:
        rows = [r for r in rows if not any(w in str(r.get(cs, "")) for w in ("폐업", "휴업", "취소", "말소"))]
        steps.append(("영업 중", len(rows)))
    agu = (lambda r: addr_gu(r.get(ca, "")) or (addr_gu(r.get("지번주소", "")) if "지번주소" in r else None)) if ca else (lambda r: None)
    how = ""
    if cw:                                                    # WKT "POINT(경도 위도)"
        pts = []
        for r in rows:
            m = re.search(r"POINT\s*\(\s*([-\d.]+)\s+([-\d.]+)", str(r.get(cw, "")), re.I)
            if m:
                pts.append((r[cn], float(m.group(1)), float(m.group(2)), agu(r)))
        steps.append(("WKT 좌표 변환 성공", len(pts)))
        how = "WKT POINT(경도 위도)"
    elif clon and clat:
        pts = [(r[cn], num(r[clon]), num(r[clat]), agu(r)) for r in rows]
        pts = [p for p in pts if p[1] is not None and p[2] is not None]
        steps.append(("좌표 있음", len(pts)))
        how = "경위도 그대로"
    elif cx and cy:
        raw = [(r[cn], num(r[cx]), num(r[cy]), agu(r)) for r in rows]
        raw = [p for p in raw if p[1] is not None and p[2] is not None]
        steps.append(("좌표 있음", len(raw)))
        if raw and 120 < raw[0][1] < 135:
            pts, how = raw, "X·Y 가 경위도"
        else:
            polys = load_gu_polys()
            cands = {epsg: CANDS.get(epsg, epsg)} if epsg and not polys else (CANDS if not epsg else {epsg: CANDS.get(epsg, epsg), **CANDS})
            best = None
            print("  [좌표계 검증] 주소의 구 = 변환 점이 들어간 행정동의 구 인 비율")
            for label, crs in cands.items():
                try:
                    ll, be = to_lonlat([p[1] for p in raw], [p[2] for p in raw], crs)
                except Exception as ex:
                    print(f"    {label:22s} 변환 실패: {ex}")
                    continue
                cand = [(p[0], a, b_, p[3]) for p, (a, b_) in zip(raw, ll)]
                if polys:
                    ok, n = gu_match(cand, polys)
                    rate = ok / n if n else 0.0
                    print(f"    {label:22s} {ok:,}/{n:,} = {rate:.2%}  ({be})")
                else:
                    rate = None
                if best is None or (rate is not None and rate > best[0]):
                    best = (rate, label, cand, be)
            if best is None:
                raise SystemExit("좌표 변환에 모두 실패")
            rate, label, pts, be = best
            how = f"{label} → 경위도 ({be})"
            if rate is not None and rate < 0.99:
                raise SystemExit(f"!! 가장 잘 맞는 좌표계({label})도 구 일치율 {rate:.2%} < 99% → 저장하지 않음. 좌표계를 확인하세요")
            steps.append(("변환 성공", len(pts)))
            if rate is not None:
                print(f"  → 사용: {label} (구 일치율 {rate:.2%})")
    else:
        raise SystemExit(f"좌표 열을 찾지 못함. 열 목록: {cols}")
    pts = [p for p in pts if SEOUL[0] <= p[1] <= SEOUL[2] and SEOUL[1] <= p[2] <= SEOUL[3]]
    steps.append(("서울 범위 안", len(pts)))
    print("  " + " → ".join(f"{k} {v:,}" for k, v in steps) + f"  (좌표: {how})")

    if kind == "elevator":
        from collections import defaultdict
        per = defaultdict(int)
        for p in pts:
            per[p[0]] += 1
        print(f"  역 {len(per)}곳, 역당 평균 엘리베이터 {len(pts) / max(1, len(per)):.2f}개")
        if chk:
            srows, _ = read_any(chk)
            sc = list(srows[0].keys())
            sn, slo, sla = pick(sc, ["역사명", "역명", "name"]), pick(sc, LON), pick(sc, LAT)
            st = defaultdict(list)
            for r in srows:
                a, b_ = num(r.get(slo)), num(r.get(sla))
                if a is not None and b_ is not None:
                    st[station_key(r[sn])].append((a, b_))
            ds, far, nomatch = [], [], set()
            for nm, lon, lat, _ in pts:
                c = st.get(station_key(nm))
                if not c:
                    nomatch.add(nm); continue
                d = min(hav(lon, lat, a, b_) for a, b_ in c)      # 같은 이름 역사(호선별)가 여럿이면 가장 가까운 것
                ds.append(d)
                if d > 500:
                    far.append((nm, round(d), lon, lat))
            ds.sort()
            if ds:
                print(f"  [역 거리 검증] 역사 좌표와 매칭 {len(ds)}/{len(pts)} 엘리베이터, 거리 중앙값 {ds[len(ds) // 2]:.0f}m, 최대 {ds[-1]:.0f}m")
            print(f"  이름이 역사마스터에 없는 역 {len(nomatch)}곳: {', '.join(sorted(nomatch)) or '-'}")
            print(f"  500m 넘게 떨어진 엘리베이터 {len(far)}개: " + ("; ".join(f"{n} {d}m ({a:.5f}, {b_:.5f})" for n, d, a, b_ in far) or "-"))

    dst = os.path.abspath(os.path.join(EXT, OUT[kind]))
    with open(dst, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(["name", "lon", "lat"])
        for nm, lon, lat, _ in pts:
            w.writerow([str(nm).strip(), round(lon, 6), round(lat, 6)])
    print(f"→ {dst} ({len(pts):,}행)")


if __name__ == "__main__":
    main()
