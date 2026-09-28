# -*- coding: utf-8 -*-
"""
tools/evenly_common.py ─ 가짜 결과 생성기·기획서 데이터 변환·데모 빌더가 같이 쓰는 부품 (표준 라이브러리만 사용)

- 경위도(WGS84) → EPSG:5186(중부원점 TM, GRS80) 좌표 변환
- 행정동 경계(analysis/hbi/external/dong_boundary.geojson, 공개 데이터) 읽기
- 점-다각형 포함 판정, utf-8-sig CSV 읽기·쓰기

analysis/ 폴더의 코드는 import 하지 않습니다 (안심구역 반입 코드와 분리).
"""
import csv, json, math, os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DONG_GEOJSON = os.path.join(ROOT, "analysis", "hbi", "external", "dong_boundary.geojson")
SITES_CSV = os.path.join(ROOT, "analysis", "hbi", "external", "sites.csv")
TARGET_GU = ["종로구", "중구", "관악구", "광진구", "강서구"]
TARGET_LABEL = {"medical": "의료시설", "bus": "버스정류장", "elderly": "노유자시설", "station": "지하철역", "pharmacy": "약국"}
FAKE_MARKER = "_FAKE_DATA_README.txt"      # 가짜 결과 폴더에만 있는 표시 파일

# ── EPSG:5186 (Korea 2000 / Central Belt 2010) ─────────────────────────
_A = 6378137.0
_F = 1 / 298.257222101
_E2 = _F * (2 - _F)
_EP2 = _E2 / (1 - _E2)
_LAT0, _LON0, _K0, _FE, _FN = math.radians(38.0), math.radians(127.0), 1.0, 200000.0, 600000.0


def _meridian(phi):
    e2, e4, e6 = _E2, _E2 ** 2, _E2 ** 3
    return _A * ((1 - e2 / 4 - 3 * e4 / 64 - 5 * e6 / 256) * phi
                 - (3 * e2 / 8 + 3 * e4 / 32 + 45 * e6 / 1024) * math.sin(2 * phi)
                 + (15 * e4 / 256 + 45 * e6 / 1024) * math.sin(4 * phi)
                 - (35 * e6 / 3072) * math.sin(6 * phi))


_M0 = _meridian(_LAT0)


def to5186(lon, lat):
    """경위도(도) → EPSG:5186 (x, y) 미터. 횡메르카토르 전개식 (Snyder 1987)."""
    phi, lam = math.radians(lat), math.radians(lon)
    s, c = math.sin(phi), math.cos(phi)
    n = _A / math.sqrt(1 - _E2 * s * s)
    t = math.tan(phi) ** 2
    cc = _EP2 * c * c
    a = (lam - _LON0) * c
    x = _FE + _K0 * n * (a + (1 - t + cc) * a ** 3 / 6 + (5 - 18 * t + t * t + 72 * cc - 58 * _EP2) * a ** 5 / 120)
    y = _FN + _K0 * (_meridian(phi) - _M0 + n * math.tan(phi) * (
        a * a / 2 + (5 - t + 9 * cc + 4 * cc * cc) * a ** 4 / 24 + (61 - 58 * t + t * t + 600 * cc - 330 * _EP2) * a ** 6 / 720))
    return x, y


# ── 행정동 경계 ─────────────────────────────────────────────────────
def load_dongs(gu_filter=None):
    """행정동 목록. 각 원소: {adm_cd, adm_cd_stat, adm_nm, gu, rings:[[(x,y),...], ...](EPSG:5186), bbox}"""
    with open(DONG_GEOJSON, encoding="utf-8") as f:
        gj = json.load(f)
    out = []
    for ft in gj["features"]:
        p = ft["properties"]
        gu = p.get("sggnm", "")
        if gu_filter and gu not in gu_filter:
            continue
        g = ft["geometry"]
        polys = g["coordinates"] if g["type"] == "MultiPolygon" else [g["coordinates"]]
        rings = []
        for poly in polys:
            for ring in poly:          # 외곽 + 구멍. 짝홀 판정이라 구멍도 그대로 처리됨
                rings.append([to5186(x, y) for x, y in ring])
        xs = [x for r in rings for x, _ in r]
        ys = [y for r in rings for _, y in r]
        out.append({"adm_cd": str(p.get("ADM_CD", "")), "adm_cd_stat": str(p.get("ADM_CD_STAT", "")),
                    "adm_nm": p.get("adm_nm", ""), "gu": gu, "rings": rings,
                    "bbox": (min(xs), min(ys), max(xs), max(ys))})
    return out


def point_in_rings(x, y, rings):
    """짝홀(even-odd) 규칙 점-다각형 판정"""
    inside = False
    for r in rings:
        n = len(r)
        j = n - 1
        for i in range(n):
            xi, yi = r[i]
            xj, yj = r[j]
            if (yi > y) != (yj > y) and x < (xj - xi) * (y - yi) / (yj - yi + 1e-12) + xi:
                inside = not inside
            j = i
    return inside


def dong_of(x, y, dongs):
    for d in dongs:
        x0, y0, x1, y1 = d["bbox"]
        if x0 <= x <= x1 and y0 <= y <= y1 and point_in_rings(x, y, d["rings"]):
            return d
    return None


def simplify(ring, tol):
    """Douglas-Peucker 단순화 (데모에 넣을 경계선 용량 줄이기)"""
    if len(ring) < 4:
        return ring

    def dp(pts):
        if len(pts) < 3:
            return pts
        (x0, y0), (x1, y1) = pts[0], pts[-1]
        dx, dy = x1 - x0, y1 - y0
        L = math.hypot(dx, dy) or 1e-9
        best, bi = -1, 0
        for i in range(1, len(pts) - 1):
            d = abs(dy * pts[i][0] - dx * pts[i][1] + x1 * y0 - y1 * x0) / L
            if d > best:
                best, bi = d, i
        if best <= tol:
            return [pts[0], pts[-1]]
        return dp(pts[:bi + 1])[:-1] + dp(pts[bi:])
    return dp(list(ring))


# ── CSV ─────────────────────────────────────────────────────────────
def read_csv(path):
    if not os.path.exists(path):
        return None
    with open(path, encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def write_csv(path, header, rows):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(header)
        w.writerows(rows)


def num(v):
    """CSV 값 → float. 빈칸·True/False·오류는 None"""
    if v is None:
        return None
    s = str(v).strip().replace(",", "")
    if s == "" or s.lower() in ("nan", "none"):
        return None
    try:
        return float(s)
    except ValueError:
        return None


def truthy(v):
    return str(v).strip().lower() in ("true", "1", "yes", "y")


def load_sites():
    """analysis/hbi/external/sites.csv (서울시 2025 선정지 5곳, 공개) → [{name, x, y, radius}]"""
    out = []
    for r in read_csv(SITES_CSV) or []:
        if r.get("lon") and r.get("lat"):
            x, y = to5186(float(r["lon"]), float(r["lat"]))
            out.append({"name": r["name"], "x": x, "y": y, "radius": float(r.get("radius_m") or 300)})
    return out
