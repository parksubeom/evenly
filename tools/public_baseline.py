# -*- coding: utf-8 -*-
"""
tools/public_baseline.py ─ [안심구역 밖] 공개데이터만으로 같은 모델을 돌린 "대조군" → LX 결과와 비교

[왜]  "LX 미개방데이터가 정말 필요한가?" 에 답하기 위해, 누구나 받을 수 있는 공개 도보 네트워크 + 공개 지형으로
      똑같은 계산을 해 보고 LX 결과(반출 grid_hbi.csv)와 얼마나 다른지 봅니다. (기획서 18장 "공개데이터 대조군")
[실행]
  python3 tools/public_baseline.py --network 도보네트워크.csv --stations 역.csv \\
      [--lx-grid results/raw_export/grid_hbi.csv] [--target station] [--bbox 127.00,37.57,127.03,37.59] [--backend auto]
  --network  : 서울시 자치구별 도보 네트워크 CSV (WGS84). LINESTRING WKT 가 든 열을 자동으로 찾음
  --stations : name, lon, lat (역 좌표. tools/prep_points.py 로 만들 수 있음)
  --backend  : auto(기본) / osgeo / pyproj. auto 는 osgeo 로 실제 변환·이미지 읽기를 한 번 해 보고 실패하면 pyproj + Pillow
[모델]  analysis/hbi/lib 의 model.run_scenario·qgraph 를 **그대로** 불러 씀 (수정하지 않음). 링크 30m 분할,
        노드는 analysis 와 같게 1m 반올림(--snap round, 기본). --snap tol 은 1m 허용거리 비교용
[지형]  AWS Terrain Tiles terrarium z15 (약 30m급 공개 표고). 캐시: data_public/raw/terrain_cache
        높이 = R×256 + G + B/256 − 32768
[결과]  results/public_baseline/
  grid_public_<target>.csv : 250m 격자 cell_x, cell_y(EPSG:5186 중심), n_nodes, hbi_mean, elder_min, flat_min (노드 3개 이상 격자)
  compare_<target>.csv     : metric, value — 공통 격자 수, 순위상관, LX 상위10% 중 공개도 상위10% 비율,
                             LX HBI 1.3 이상 격자 수와 그중 공개데이터로 1.3 미만(놓침) 비율, 평균 절대차, 중앙값, 비고
"""
import argparse, csv, io, math, os, re, sys, urllib.request
import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "analysis", "hbi"))          # config·lib 를 그대로 불러오기 위해
import config as C                                                   # noqa: E402  (ELDER_SPEED 등 모델 설정)
from lib.model import run_scenario                                   # noqa: E402
from lib.qgraph import NearestIndex, spearman, components            # noqa: E402

CACHE = os.path.join(ROOT, "data_public", "raw", "terrain_cache")
TILE = "https://s3.amazonaws.com/elevation-tiles-prod/terrarium/{z}/{x}/{y}.png"
Z = 15
SEG, SNAP, GRID, MIN_NODES = 30.0, 1.0, 250, 3
BAD_LOW = -20.0          # 이보다 낮은 타일 픽셀은 이상값으로 봄
KEEP_SHARE = 0.05        # 가장 큰 연결망의 5% 이상인 연결망은 모두 남김 (떨어진 구가 여럿일 때)
FIXED = [0, 0]           # [이상값 픽셀 수, 전체 픽셀 수]
NOTE = ("LX = 건물 평균, 공개 = 길 노드 평균, 공개 지형 약 30m급, 2020 네트워크, "
        "계단 미사용(공개 도보 네트워크에는 계단 구분이 없음: 링크 유형 코드는 통행 주체만 구분)")


# ── 좌표·이미지 백엔드 ──────────────────────────────────────
class Osgeo:
    name = "osgeo"

    def __init__(self):
        from osgeo import gdal, osr, gdal_array  # noqa: F401  gdal_array 가 없으면 여기서 실패
        gdal.UseExceptions(); osr.UseExceptions()
        self.gdal = gdal
        a, b = osr.SpatialReference(), osr.SpatialReference()
        a.ImportFromEPSG(4326); b.ImportFromEPSG(5186)
        for r in (a, b):
            r.SetAxisMappingStrategy(osr.OAMS_TRADITIONAL_GIS_ORDER)
        self.fwd, self.inv = osr.CoordinateTransformation(a, b), osr.CoordinateTransformation(b, a)

    def to_m(self, lon, lat):
        p = np.asarray(self.fwd.TransformPoints(np.c_[lon, lat].tolist()), float)
        return p[:, 0], p[:, 1]

    def to_ll(self, x, y):
        p = np.asarray(self.inv.TransformPoints(np.c_[x, y].tolist()), float)
        return p[:, 0], p[:, 1]

    def decode_png(self, data):
        path = f"/vsimem/tile_{id(data)}.png"
        self.gdal.FileFromMemBuffer(path, data)
        ds = self.gdal.Open(path)
        arr = np.stack([ds.GetRasterBand(i + 1).ReadAsArray() for i in range(3)], -1).astype(float)
        ds = None
        self.gdal.Unlink(path)
        return arr


class Pyproj:
    name = "pyproj"

    def __init__(self):
        from pyproj import Transformer
        from PIL import Image
        self.Image = Image
        self.fwd = Transformer.from_crs("EPSG:4326", "EPSG:5186", always_xy=True)
        self.inv = Transformer.from_crs("EPSG:5186", "EPSG:4326", always_xy=True)

    def to_m(self, lon, lat):
        x, y = self.fwd.transform(np.asarray(lon, float), np.asarray(lat, float))
        return np.asarray(x, float), np.asarray(y, float)

    def to_ll(self, x, y):
        a, b = self.inv.transform(np.asarray(x, float), np.asarray(y, float))
        return np.asarray(a, float), np.asarray(b, float)

    def decode_png(self, data):
        return np.asarray(self.Image.open(io.BytesIO(data)).convert("RGB"), float)


def pick_backend(want):
    """실제로 서울시청 좌표를 한 번 변환하고, 작은 PNG 를 한 번 읽어 봐서 통과한 백엔드를 씀"""
    order = {"auto": [Osgeo, Pyproj], "osgeo": [Osgeo], "pyproj": [Pyproj]}[want]
    errs = []
    for cls in order:
        try:
            b = cls()
            x, y = b.to_m([126.978], [37.5665])
            assert abs(x[0] - 198056) < 5 and abs(y[0] - 551885) < 5, f"변환 결과 이상: {x[0]:.1f}, {y[0]:.1f}"
            png = tiny_png()
            px = b.decode_png(png)
            assert px.shape[:2] == (1, 1) and tuple(px[0, 0, :3]) == (128.0, 0.0, 0.0), f"PNG 읽기 이상: {px[0, 0]}"
            return b
        except Exception as ex:                   # 실패하면 다음 백엔드로
            errs.append(f"{cls.name}: {ex}")
    raise SystemExit("좌표 변환·이미지 읽기 백엔드를 쓸 수 없음 → " + " / ".join(errs))


def tiny_png():
    """1×1 RGB(128,0,0) PNG 를 표준 라이브러리로 만들기 (백엔드 점검용)"""
    import struct, zlib
    raw = b"\x00" + bytes([128, 0, 0])
    chunk = lambda t, d: struct.pack(">I", len(d)) + t + d + struct.pack(">I", zlib.crc32(t + d) & 0xFFFFFFFF)
    return b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", 1, 1, 8, 2, 0, 0, 0)) + chunk(b"IDAT", zlib.compress(raw)) + chunk(b"IEND", b"")


# ── 지형 타일 ───────────────────────────────────────────────
def tile_xy(lon, lat):
    """경위도 → z15 타일 안 전역 픽셀 좌표 (웹 메르카토르)"""
    n = 2 ** Z * 256
    x = (np.asarray(lon) + 180) / 360 * n
    lr = np.radians(np.asarray(lat))
    y = (1 - np.arcsinh(np.tan(lr)) / math.pi) / 2 * n
    return x, y


def get_tile(backend, tx, ty):
    os.makedirs(CACHE, exist_ok=True)
    p = os.path.join(CACHE, f"{Z}_{tx}_{ty}.png")
    if not os.path.exists(p):
        with urllib.request.urlopen(TILE.format(z=Z, x=tx, y=ty), timeout=30) as r:
            data = r.read()
        with open(p, "wb") as f:
            f.write(data)
    rgb = backend.decode_png(open(p, "rb").read())
    h = rgb[..., 0] * 256 + rgb[..., 1] + rgb[..., 2] / 256 - 32768          # terrarium 디코드
    # 공개 타일의 이상값(강·호수 주변 -수백~-2천 m 튀는 픽셀) → 주변 정상값 평균으로 메움 (서울 실제 고도 약 0~836m)
    bad = h < BAD_LOW
    FIXED[0] += int(bad.sum()); FIXED[1] += h.size
    for _ in range(64):
        if not bad.any():
            break
        v = np.where(bad, 0.0, h); w = (~bad).astype(float)
        pv, pw = np.pad(v, 1), np.pad(w, 1)
        sv = sum(pv[1 + dy:pv.shape[0] - 1 + dy, 1 + dx:pv.shape[1] - 1 + dx] for dy in (-1, 0, 1) for dx in (-1, 0, 1))
        sw = sum(pw[1 + dy:pw.shape[0] - 1 + dy, 1 + dx:pw.shape[1] - 1 + dx] for dy in (-1, 0, 1) for dx in (-1, 0, 1))
        fill = bad & (sw > 0)
        h = np.where(fill, sv / np.maximum(sw, 1), h)
        bad = bad & ~fill
    return h


def elevation(backend, lon, lat):
    """노드 경위도 → 높이(m). 전역 픽셀 좌표에서 쌍선형 보간"""
    px, py = tile_xy(lon, lat)
    px, py = px - 0.5, py - 0.5
    x0, y0 = np.floor(px).astype(np.int64), np.floor(py).astype(np.int64)
    need = set()                                   # 노드가 실제로 있는 타일만 (+ 보간용 오른쪽·아래 이웃)
    for a, b in zip(x0 // 256, y0 // 256):
        need.add((int(a), int(b)))
    for a, b in zip((x0 + 1) // 256, (y0 + 1) // 256):
        need.add((int(a), int(b)))
    tiles = {k: get_tile(backend, *k) for k in sorted(need)}

    def at(xx, yy):
        out = np.empty(len(xx))
        for i, (a, b) in enumerate(zip(xx, yy)):
            out[i] = tiles[(a // 256, b // 256)][b % 256, a % 256]
        return out
    dx, dy = px - x0, py - y0
    return (at(x0, y0) * (1 - dx) * (1 - dy) + at(x0 + 1, y0) * dx * (1 - dy) +
            at(x0, y0 + 1) * (1 - dx) * dy + at(x0 + 1, y0 + 1) * dx * dy), len(tiles)


# ── 네트워크 ────────────────────────────────────────────────
def read_any(p):
    for enc in ("utf-8-sig", "cp949", "euc-kr"):
        try:
            with open(p, encoding=enc, newline="") as f:
                return list(csv.DictReader(f))
        except UnicodeDecodeError:
            continue
    raise SystemExit(f"인코딩을 알 수 없음: {p}")


def lines_from_csv(path, bbox, gus=None):
    rows = read_any(path)
    if gus:
        gc = next((c for c in rows[0] if c.replace(" ", "") in ("시군구명", "자치구", "구명")), None)
        if not gc:
            raise SystemExit(f"--gu 를 쓰려면 시군구명 열이 필요합니다. 열: {list(rows[0])}")
        rows = [r for r in rows if r.get(gc, "").strip() in gus]
    tc = next((c for c in rows[0] if c.replace(" ", "") == "링크유형코드"), None)
    if tc:                                         # 링크 유형 코드 첫 자리 = 보행자 통행 가능 (유형코드표: 1xxx = 보행자 포함)
        before = sum(1 for r in rows if str(r.get("노드링크 유형", "LINK")).strip().upper() == "LINK")
        rows = [r for r in rows if str(r.get("노드링크 유형", "LINK")).strip().upper() != "LINK" or str(r.get(tc, "")).strip().zfill(4)[0] == "1"]
        after = sum(1 for r in rows if str(r.get("노드링크 유형", "LINK")).strip().upper() == "LINK")
        print(f"  링크 유형 코드: 보행자 통행 불가 링크 {before - after}개 제외 ({before:,} → {after:,})")
    col = next((c for c in rows[0] if any(str(r.get(c, "")).upper().lstrip().startswith(("LINESTRING", "MULTILINESTRING")) for r in rows[:200])), None)
    if not col:
        raise SystemExit(f"LINESTRING WKT 열을 찾지 못함. 열: {list(rows[0])}")
    out = []
    for r in rows:
        w = str(r.get(col, "")).strip()
        if not w.upper().startswith(("LINESTRING", "MULTILINESTRING")):
            continue                               # 노드(POINT) 행 등은 건너뜀
        for part in re.findall(r"\(([^()]+)\)", w):
            pts = [tuple(map(float, p.split()[:2])) for p in part.split(",") if p.strip()]
            if len(pts) < 2:
                continue
            if bbox and not any(bbox[0] <= x <= bbox[2] and bbox[1] <= y <= bbox[3] for x, y in pts):
                continue
            out.append(pts)
    return col, len(rows), out


def build(backend, lines, snap="round"):
    """선 → 30m 이하 조각 → (노드 xy, 링크 u·v·길이)
    snap="round" : analysis/hbi/lib/qnetwork.py 와 같은 규칙 (좌표를 1m 단위로 반올림해 같으면 같은 노드, 노드 좌표 = 반올림 값)
    snap="tol"   : 1m 허용거리 (이웃 칸까지 보고 1m 안이면 같은 노드). 비교 조건을 맞추려고 기본은 round"""
    allpts = np.array([p for ln in lines for p in ln], float)
    X, Y = backend.to_m(allpts[:, 0], allpts[:, 1])
    ids, nxy, U, V, L = {}, [], [], [], []

    def nid_round(x, y):
        k = (int(np.round(x / SNAP)), int(np.round(y / SNAP)))
        if k not in ids:
            ids[k] = len(nxy); nxy.append((k[0] * SNAP, k[1] * SNAP))
        return ids[k]

    def nid_tol(x, y):
        """1m(SNAP) 안에 이미 노드가 있으면 그 노드, 없으면 새 노드. 1m 칸과 이웃 8칸을 같이 봄
        (반올림만 하면 0.4m 떨어진 두 점이 칸 경계를 사이에 두고 다른 노드가 될 수 있어서)"""
        kx, ky = int(math.floor(x / SNAP)), int(math.floor(y / SNAP))
        for ax in (kx - 1, kx, kx + 1):
            for ay in (ky - 1, ky, ky + 1):
                for n in ids.get((ax, ay), ()):
                    if math.hypot(nxy[n][0] - x, nxy[n][1] - y) <= SNAP:
                        return n
        ids.setdefault((kx, ky), []).append(len(nxy)); nxy.append((x, y))
        return len(nxy) - 1
    nid = nid_round if snap == "round" else nid_tol
    i = 0
    for ln in lines:
        xs, ys = X[i:i + len(ln)], Y[i:i + len(ln)]
        i += len(ln)
        for (x0, y0, x1, y1) in zip(xs[:-1], ys[:-1], xs[1:], ys[1:]):
            d = math.hypot(x1 - x0, y1 - y0)
            if d < 1e-6:
                continue
            k = max(1, int(math.ceil(d / SEG)))
            prev = nid(x0, y0)
            for j in range(1, k + 1):
                cur = nid(x0 + (x1 - x0) * j / k, y0 + (y1 - y0) * j / k)
                if cur != prev:
                    U.append(prev); V.append(cur); L.append(d / k)
                prev = cur
    return np.array(nxy, float), np.array(U, np.int64), np.array(V, np.int64), np.array(L, float)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--network", required=True)
    ap.add_argument("--stations", required=True)
    ap.add_argument("--lx-grid")
    ap.add_argument("--target", default="station")
    ap.add_argument("--bbox", help="lon0,lat0,lon1,lat1")
    ap.add_argument("--gu", help="시군구명 열로 거를 구 (쉼표). 예) 종로구,중구,관악구,광진구,강서구")
    ap.add_argument("--backend", default="auto", choices=["auto", "osgeo", "pyproj"])
    ap.add_argument("--snap", default="round", choices=["round", "tol"], help="노드 합치기 규칙 (기본 round = analysis 와 같음)")
    ap.add_argument("--out", default=os.path.join(ROOT, "results", "public_baseline"))
    a = ap.parse_args()
    bbox = [float(v) for v in a.bbox.split(",")] if a.bbox else None
    B = pick_backend(a.backend)
    print(f"백엔드: {B.name}, 노드 합치기: {a.snap}")

    import time
    t0 = time.time()
    gus = [g.strip() for g in a.gu.split(",")] if a.gu else None
    col, nrows, lines = lines_from_csv(a.network, bbox, gus)
    print(f"네트워크: {nrows:,}행 중 선 {len(lines):,}개 (WKT 열 '{col}')")
    nxy, U, V, L = build(B, lines, a.snap)
    lon, lat = B.to_ll(nxy[:, 0], nxy[:, 1])
    z, nt = elevation(B, lon, lat)
    s = (z[V] - z[U]) / L                                       # 링크 경사 (u → v 방향)
    s = np.clip(s, -C.SLOPE_CLIP, C.SLOPE_CLIP)
    e = {"u": U, "v": V, "length": L, "is_stair": np.zeros(len(U), bool)}
    comp = components(U, V, len(nxy))
    cnt = np.bincount(comp)
    keep = np.where(cnt >= KEEP_SHARE * cnt.max())[0]                # 떨어진 구마다 하나씩 생기는 큰 연결망을 모두 남김
    giant = np.isin(comp, keep)
    print(f"연결망: {int((cnt > 0).sum())}개 중 가장 큰 것의 {KEEP_SHARE:.0%} 이상 {len(keep)}개 남김 (크기 {sorted(cnt[keep].tolist(), reverse=True)}), 이상 고도 픽셀 {FIXED[0]:,}/{FIXED[1]:,} 메움")
    print(f"노드 {len(nxy):,}, 링크 {len(U):,}, 남긴 연결망 노드 {giant.mean():.1%}, 지형 타일 {nt}장, 고도 {z.min():.0f}~{z.max():.0f}m")

    st = read_any(a.stations)
    sx, sy = B.to_m([float(r["lon"]) for r in st], [float(r["lat"]) for r in st])
    gi = np.where(giant)[0]
    d, j = NearestIndex(nxy[gi]).query(np.c_[sx, sy], 300)
    dests = gi[j[j >= 0]]
    print(f"목적지({a.target}) {len(st)}곳 중 연결 {len(dests)}곳 (300m 안)")
    if not len(dests):
        raise SystemExit("목적지를 네트워크에 연결하지 못했습니다 (bbox·좌표 확인)")
    r = run_scenario(len(nxy), e, s, dests)                     # analysis/hbi/lib/model.py 그대로
    te, tf = r["t_elder"], r["t_flat"]
    h = np.where(tf == 0, 1.0, te / tf)
    ok = giant & np.isfinite(h)

    gx = np.floor(nxy[:, 0] / GRID).astype(np.int64); gy = np.floor(nxy[:, 1] / GRID).astype(np.int64)
    key = gx[ok] * 10**7 + gy[ok]
    u, inv = np.unique(key, return_inverse=True)
    cnt = np.bincount(inv)
    hm = np.bincount(inv, h[ok]) / cnt
    rows, pub = [], {}
    for k in np.where(cnt >= MIN_NODES)[0]:
        cx, cy = (u[k] // 10**7 + 0.5) * GRID, (u[k] % 10**7 + 0.5) * GRID
        m = inv == k
        rows.append([cx, cy, int(cnt[k]), round(float(hm[k]), 3), round(float(np.median(te[ok][m])) / 60, 1), round(float(np.median(tf[ok][m])) / 60, 1)])
        pub[(round(cx), round(cy))] = float(hm[k])
    os.makedirs(a.out, exist_ok=True)
    with open(os.path.join(a.out, f"grid_public_{a.target}.csv"), "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f); w.writerow(["cell_x", "cell_y", "n_nodes", "hbi_mean", "elder_min", "flat_min"]); w.writerows(rows)
    print(f"→ grid_public_{a.target}.csv (격자 {len(rows)}개, 노드 {MIN_NODES}개 이상), 걸린 시간 {time.time() - t0:.0f}초")

    if a.lx_grid:
        lx = {(round(float(g["cell_x"])), round(float(g["cell_y"]))): float(g["hbi_mean"])
              for g in read_any(a.lx_grid) if g.get("target") == a.target and g.get("hbi_mean")}
        com = sorted(set(lx) & set(pub))
        cmp = [["공통 격자 수", len(com)]]
        if len(com) >= 3:
            A = np.array([lx[k] for k in com]); P = np.array([pub[k] for k in com])
            topA, topP = A >= np.quantile(A, 0.9), P >= np.quantile(P, 0.9)
            hi = A >= 1.3
            cmp += [["순위상관(스피어만, LX vs 공개)", round(float(spearman(A, P)), 3)],
                    ["LX 상위10% 중 공개도 상위10% 비율", round(float((topA & topP).sum() / max(topA.sum(), 1)), 3)],
                    ["LX HBI 1.3 이상 격자 수", int(hi.sum())],
                    ["그중 공개데이터로 1.3 미만(놓침) 비율", round(float((hi & (P < 1.3)).sum() / hi.sum()), 3) if hi.any() else ""],
                    ["평균 절대차", round(float(np.mean(np.abs(A - P))), 3)],
                    ["중앙값 LX", round(float(np.median(A)), 3)], ["중앙값 공개", round(float(np.median(P)), 3)]]
        cmp.append(["비고", NOTE])
        with open(os.path.join(a.out, f"compare_{a.target}.csv"), "w", encoding="utf-8-sig", newline="") as f:
            w = csv.writer(f); w.writerow(["metric", "value"]); w.writerows(cmp)
        for m in cmp:
            print(f"  {m[0]}: {m[1]}")
        print(f"→ compare_{a.target}.csv")


if __name__ == "__main__":
    main()
