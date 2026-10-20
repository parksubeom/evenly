# -*- coding: utf-8 -*-
"""
tools/make_process_figs.py ─ [10/20] 기획서 11장(분석 다섯 단계)·28장(부록 2 전처리) 과정 그림을 공개 자료로

[왜] 반출은 끝났고 안심구역 자료로는 과정 그림을 만들 수 없어서, 같은 코드(v6.2 #ddc743)를 공개 자료로 돌린
     관악 리허설의 중간 파일로 같은 봉천 일대를 그림. 그림에는 결과 숫자를 넣지 않음 (결과 장과 섞이지 않게).
     기획서 출처 줄: "과정 예시: 공개 자료로 그림 (분석은 LX 자료)"
[실행]  (QGIS 파이썬) python tools/make_process_figs.py [--win 750] [--grid-run gwanak_v62all08] [--contours data_public/raw/contour_gwanak.gpkg]
        --contours : [10/20] 연속수치지형도 등고선(tools/extract_contours.py 결과)으로 높이를 다시 만들어 ③ 경사 색·④ 경로·⑤ 격자를 다시 계산하고
                     모든 지도 칸에 등고선 배경을 깜. 28장 터널 단면도 등고선 높이. 창 안에 등고선이 빠진 곳(공개 지형 기복이 있는데
                     등고선이 없는 100m 칸)이 3% 넘으면 멈춤 (덜 받아진 묶음으로 그림이 틀리지 않게). --allow-gaps 는 시험용 (--out 과 함께)
        --out      : 그림을 둘 폴더 (기본 deck/v6_source)
[읽는 것] (모두 공개 자료, 실제 반출 results/raw_export 는 읽지 않음)
  - data_public/rehearsal/박수범/수치지형도2/*/N3L_A0020000(길)·N3A_C0390000(계단 면) : 연속수치지형도 도로중심선 + OSM 계단 (make_public_rehearsal.py)
  - data_public/rehearsal/박수범/hbi6/work/network.npz, work/all/dest_nodes.npz : 그 자료로 02_network 가 만든 30m 보행망·경사·약국 노드
  - results/public_rehearsal/<grid-run>/all/grid_hbi_pharmacy.gpkg : 공개 자료 보행망 250m 격자 (색만, 숫자 없음)
  - data_public/raw/osm_bridges_gwanak.json : 28장 다리·터널 칸 (OSM bridge·tunnel 길, 없으면 받음)
  - 경로 계산은 같은 번들의 lib/model.py (elder_time) 를 그대로 불러 씀 (분석 코드는 고치지 않음)
[결과] deck/v6_source/proc11_1~5.png (11장 다섯 칸, 같은 범위·같은 축척), proc28_1~4.png (28장 전처리 네 칸),
       deck/v6_source/proc_figs_meta.json (범위·고른 예시·출처. 기획서에는 쓰지 않음)
"""
import argparse, glob, json, math, os, sys, urllib.parse, urllib.request
import numpy as np
from osgeo import gdal, ogr, osr
gdal.UseExceptions(); ogr.UseExceptions(); osr.UseExceptions()
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.collections import LineCollection, PatchCollection
from matplotlib.patches import Polygon as MPoly, Rectangle, Circle

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REH = os.path.join(ROOT, "data_public", "rehearsal", "박수범")
H6 = os.path.join(REH, "hbi6")
OUT = os.path.join(ROOT, "deck", "v6_source")
RAW = os.path.join(ROOT, "data_public", "raw")
sys.path.insert(0, os.path.join(ROOT, "tools"))
from evenly_common import PUBLIC_REHEARSAL, source_of   # noqa: E402

# 기획서 색 (build_v6.js 의 C 와 같음)
INK, TEXT, MUTED, LINE, SOFT, ACC, ACCD, TEAL = "#1C2321", "#2B2F2E", "#6B7370", "#DADFDC", "#F3F4F3", "#E4572E", "#B8401F", "#2F7D6D"
YEL = "#E3B23C"
SLOPE_BINS = [(0.03, TEAL), (1 / 12, YEL), (9.9, ACC)]   # 경사 |s|: 3% 미만 초록 · 1/12(휠체어 한계)까지 노랑 · 넘으면 빨강
SITE_NAME = "봉천동 비안어린이공원 인근"                  # tools/field_fix_v62.py 후보 좌표 표의 선정지 줄 (계단 양 끝 a·b)
PX = 1.64                                                # 11장 한 칸 그림 크기 (인치, build_v6.js 와 같게)
CBG = None                                               # [10/20] 등고선 배경 (contour_bg 가 채움)
CBG_28 = True                                            # 28장 지도 칸에도 등고선 배경 (--bg-only 면 끔: 11장 배경·28장 단면에만)
CONT_C, CONT_C25 = "#E3DED4", "#CEC6B6"                  # 등고선 색 (주곡선 · 25m 계곡선)


def srs(code):
    s = osr.SpatialReference(); s.ImportFromEPSG(code); s.SetAxisMappingStrategy(osr.OAMS_TRADITIONAL_GIS_ORDER)
    return s


S5186 = srs(5186)


def to5186_ll(lon, lat):
    x, y, _ = osr.CoordinateTransformation(srs(4326), S5186).TransformPoint(lon, lat)
    return x, y


def read_layer(code, win, pad=60):
    """수치지형도2 (공개 대역) 전 도엽에서 code 레이어의 도형을 5186 으로, 창(win) 둘레 pad m 안만"""
    x0, x1, y0, y1 = win[0] - pad, win[1] + pad, win[2] - pad, win[3] + pad
    box = ogr.CreateGeometryFromWkt(f"POLYGON(({x0} {y0},{x1} {y0},{x1} {y1},{x0} {y1},{x0} {y0}))", S5186)
    out = []
    for p in sorted(glob.glob(os.path.join(REH, "수치지형도2", "*", code + ".shp"))):
        ds = ogr.Open(p)
        lyr = ds.GetLayer(0)
        sr = lyr.GetSpatialRef()
        sr.SetAxisMappingStrategy(osr.OAMS_TRADITIONAL_GIS_ORDER)
        ct = osr.CoordinateTransformation(sr, S5186)
        b2 = box.Clone(); b2.TransformTo(sr)
        lyr.SetSpatialFilter(b2)
        for f in lyr:
            g = f.GetGeometryRef().Clone()
            g.Transform(ct)
            if g.Intersects(box):
                out.append(g)
    return out


def line_parts(g):
    t = ogr.GT_Flatten(g.GetGeometryType())
    if t == ogr.wkbLineString:
        return [np.array(g.GetPoints())[:, :2]]
    return sum((line_parts(g.GetGeometryRef(i)) for i in range(g.GetGeometryCount())), [])


def poly_rings(g):
    t = ogr.GT_Flatten(g.GetGeometryType())
    if t == ogr.wkbPolygon:
        return [np.array(g.GetGeometryRef(0).GetPoints())[:, :2]]
    return sum((poly_rings(g.GetGeometryRef(i)) for i in range(g.GetGeometryCount())), [])


# ── [10/20] 연속수치지형도 등고선 ──────────────────────────────────────────
S5179 = None


def contour_lines(src, win5186, pad=30):
    """등고선(5179) 중 창(5186) 둘레만 → [(5186 점 배열, 높이)]"""
    global S5179
    S5179 = S5179 or srs(5179)
    c = [osr.CoordinateTransformation(S5186, S5179).TransformPoint(x, y)[:2] for x in (win5186[0] - pad, win5186[1] + pad) for y in (win5186[2] - pad, win5186[3] + pad)]
    ds = ogr.Open(src); lyr = ds.GetLayer(0)
    lyr.SetSpatialFilterRect(min(p[0] for p in c), min(p[1] for p in c), max(p[0] for p in c), max(p[1] for p in c))
    ct = osr.CoordinateTransformation(S5179, S5186)
    out = []
    for f in lyr:
        g = f.GetGeometryRef().Clone(); g.Transform(ct)
        z = f.GetField("CONT")
        out += [(xy, z) for xy in line_parts(g) if len(xy) >= 2]
    return out


def draw_contours(ax, win):
    """모든 지도 칸 맨 아래 옅은 등고선 (5m 주곡선, 25m 마다 조금 진하게). 등고선 모드가 아니면 아무것도 안 함"""
    if not CBG:
        return
    lines = contour_lines(CBG, win)
    thin = [xy for xy, z in lines if z is None or abs(z / 25 - round(z / 25)) > 1e-6]
    bold = [xy for xy, z in lines if z is not None and abs(z / 25 - round(z / 25)) <= 1e-6]
    ax.add_collection(LineCollection(thin, colors=CONT_C, linewidths=0.45, zorder=0.5))
    ax.add_collection(LineCollection(bold, colors=CONT_C25, linewidths=0.7, zorder=0.6))


class ContourDEM:
    """등고선 → 5m 격자 (make_public_rehearsal.dem_from_contours 와 같은 방법: 선을 높이로 그리고 빈 칸을 주변 값으로 메움)"""
    def __init__(self, src, win5186, pad=2000.0, res=5.0):
        global S5179
        S5179 = S5179 or srs(5179)
        c = [osr.CoordinateTransformation(S5186, S5179).TransformPoint(x, y)[:2] for x in (win5186[0] - pad, win5186[1] + pad) for y in (win5186[2] - pad, win5186[3] + pad)]
        self.bb = (min(p[0] for p in c), min(p[1] for p in c), max(p[0] for p in c), max(p[1] for p in c))
        # make_public_rehearsal.dem_from_contours 와 같은 방법 (그 모듈은 analysis/hbi 의 lib 를 불러 번들 lib 와 섞이므로 여기 옮겨 씀)
        x0, y1 = math.floor(self.bb[0] / res) * res, math.ceil(self.bb[3] / res) * res
        nx, ny = int(math.ceil((self.bb[2] - x0) / res)), int(math.ceil((y1 - self.bb[1]) / res))
        ds = gdal.OpenEx(src, gdal.OF_VECTOR); lyr = ds.GetLayer(0)
        r = gdal.GetDriverByName("MEM").Create("", nx, ny, 1, gdal.GDT_Float32)
        r.SetGeoTransform((x0, res, 0, y1, 0, -res)); r.SetProjection(S5179.ExportToWkt())
        bd = r.GetRasterBand(1); bd.SetNoDataValue(-9999); bd.Fill(-9999)
        gdal.RasterizeLayer(r, [1], lyr, options=["ATTRIBUTE=CONT", "ALL_TOUCHED=TRUE"])
        gdal.FillNodata(bd, None, maxSearchDist=max(nx, ny), smoothingIterations=0)
        self.Z, self.x0, self.y1, self.fld = bd.ReadAsArray().astype(float), x0, y1, "CONT"
        self.res = res
        self.ct = osr.CoordinateTransformation(S5186, S5179)

    def sample(self, x5186, y5186):
        P = np.asarray(self.ct.TransformPoints(np.c_[x5186, y5186].tolist()))[:, :2] if len(x5186) else np.zeros((0, 2))
        c = (P[:, 0] - self.x0) / self.res - 0.5; r = (self.y1 - P[:, 1]) / self.res - 0.5
        ok = (c >= 0) & (r >= 0) & (c < self.Z.shape[1] - 1) & (r < self.Z.shape[0] - 1)
        z = np.full(len(P), np.nan)
        j, i = np.floor(c[ok]).astype(int), np.floor(r[ok]).astype(int)
        fx, fy = c[ok] - j, r[ok] - i
        Z = self.Z
        z[ok] = (Z[i, j] * (1 - fx) * (1 - fy) + Z[i, j + 1] * fx * (1 - fy) + Z[i + 1, j] * (1 - fx) * fy + Z[i + 1, j + 1] * fx * fy)
        return z


def contour_gaps(src, win5186, cell=100.0, relief_min=8.0):
    """창 안 100m 칸 중 공개 지형(리허설 5m 격자) 기복이 relief_min 넘는데 등고선 점이 하나도 없는 칸의 비율 (덜 받아진 묶음 찾기)"""
    dem = gdal.Open(glob.glob(os.path.join(REH, "수치표고모델_5m", "*.img"))[0])
    gt = dem.GetGeoTransform(); T = dem.GetRasterBand(1).ReadAsArray().astype(float); T[T < -1000] = np.nan
    lines = contour_lines(src, win5186, pad=0)
    ct = osr.CoordinateTransformation(S5186, srs(5179))
    nx = ny = int(round((win5186[1] - win5186[0]) / cell))
    cnt = np.zeros((ny, nx)); rel = np.zeros((ny, nx))
    for xy, _ in lines:
        j = ((xy[:, 0] - win5186[0]) / cell).astype(int); i = ((xy[:, 1] - win5186[2]) / cell).astype(int)
        ok = (i >= 0) & (i < ny) & (j >= 0) & (j < nx)
        np.add.at(cnt, (i[ok], j[ok]), 1)
    for i in range(ny):
        for j in range(nx):
            xs = win5186[0] + (j + np.array([0.1, 0.5, 0.9])) * cell; ys = win5186[2] + (i + np.array([0.1, 0.5, 0.9])) * cell
            P = np.asarray(ct.TransformPoints([(x, y) for x in xs for y in ys]))[:, :2]
            cc = ((P[:, 0] - gt[0]) / gt[1]).astype(int); rr = ((P[:, 1] - gt[3]) / gt[5]).astype(int)
            v = T[np.clip(rr, 0, T.shape[0] - 1), np.clip(cc, 0, T.shape[1] - 1)]
            rel[i, j] = np.nanmax(v) - np.nanmin(v)
    need = rel > relief_min
    return float((need & (cnt == 0)).sum() / max(1, need.sum())), int((need & (cnt == 0)).sum()), int(need.sum())


def panel(win, size=PX, dpi=400):
    fig = plt.figure(figsize=(size, size), dpi=dpi)
    ax = fig.add_axes([0, 0, 1, 1])
    ax.set_xlim(win[0], win[1]); ax.set_ylim(win[2], win[3]); ax.set_aspect("equal")
    ax.axis("off")
    ax.add_patch(Rectangle((win[0], win[2]), win[1] - win[0], win[3] - win[2], fill=False, ec=LINE, lw=0.8, zorder=50))
    draw_contours(ax, win)
    return fig, ax


def save(fig, name):
    p = os.path.join(OUT, name)
    fig.savefig(p, dpi=fig.dpi, facecolor="white")
    plt.close(fig)
    return p


def edge_segs(N, u, v, sel):
    return np.stack([N[u[sel]], N[v[sel]]], axis=1)


def in_win(N, u, v, win, pad=40):
    x0, x1, y0, y1 = win[0] - pad, win[1] + pad, win[2] - pad, win[3] + pad
    a, b = N[u], N[v]
    ok = lambda p: (p[:, 0] >= x0) & (p[:, 0] <= x1) & (p[:, 1] >= y0) & (p[:, 1] <= y1)
    return ok(a) | ok(b)


def slope_color(s):
    a = np.abs(s)
    return [next(c for t, c in SLOPE_BINS if x < t) for x in a]


def scale_bar(ax, win, m=100):
    """오른쪽 아래 100m 막대 (숫자 없이 길이만, 칸마다 같은 축척임을 보이게)"""
    x1, y0 = win[1] - 0.06 * (win[1] - win[0]), win[2] + 0.05 * (win[3] - win[2])
    ax.plot([x1 - m, x1], [y0, y0], color=INK, lw=1.4, solid_capstyle="butt", zorder=60)


# ── 경로 (같은 번들 lib/model.py) ─────────────────────────────────────────
def load_model():
    sys.path.insert(0, H6)
    import config as C                                   # noqa: F401  (번들 그대로: 0.8m/s 등)
    from lib import model as M
    return M


def paths_to(N, e, s, src, giant):
    """목적지 src 에서 모든 노드로 가는 경로를 거꾸로 (집 → src). 고령자 경사 반영 / 평지 가정 두 가지의 (시간, 앞 노드)"""
    from scipy.sparse import csr_matrix
    from scipy.sparse.csgraph import dijkstra
    M = load_model()
    u, v, L, ss, st = M.directed(e, s)
    n = len(N)
    out = {}
    for name, w in (("elder", M.elder_time(L, ss, st)), ("flat", L / M.C.ELDER_SPEED)):
        ok = np.isfinite(w) & giant[u] & giant[v]
        # 집 → 약국 경로 = 뒤집은 그래프에서 약국 → 집
        A = csr_matrix((w[ok], (v[ok], u[ok])), shape=(n, n))
        A.sum_duplicates()
        d, pred = dijkstra(A, directed=True, indices=src, return_predecessors=True)
        out[name] = (d, pred)
    return out


def walk(pred, o):
    p = [o]
    while pred[p[-1]] >= 0:
        p.append(pred[p[-1]])
    return p          # o → … → 목적지


# ── 28장 전처리 네 칸 (전 → 후, 정사각 두 칸) ────────────────────────────
P28 = (2.1, 0.92)                                        # 28장 한 칸 그림 크기 (인치, build_v6.js 와 같게)


def pair(win=None, size=P28, dpi=400):
    fig = plt.figure(figsize=size, dpi=dpi)
    w = size[1] / size[0]
    axs = [fig.add_axes([0, 0, w, 1]), fig.add_axes([1 - w, 0, w, 1])]
    for ax in axs:
        ax.axis("off")
        if win:
            ax.set_xlim(win[0], win[1]); ax.set_ylim(win[2], win[3]); ax.set_aspect("equal")
            ax.add_patch(Rectangle((win[0], win[2]), win[1] - win[0], win[3] - win[2], fill=False, ec=LINE, lw=0.8, zorder=50))
            if CBG_28:
                draw_contours(ax, win)
    c = 0.5                                               # 가운데 화살표 (글자 없이)
    fig.add_artist(MPoly([[c - 0.012, 0.40], [c + 0.016, 0.5], [c - 0.012, 0.60]], closed=True, transform=fig.transFigure, color=MUTED))
    return fig, axs


def mini_win(x, y, h):
    return (x - h, x + h, y - h, y + h)


def ends_xy(lines):
    return np.array([p[i] for p in lines for i in (0, -1)])


def fig_cross(N, e, deg, giant):
    """교차점 분할: 공개 도로중심선에서 끝점이 아닌 곳에서 서로 지나가는 두 선 (관악, 선정지에서 가장 가까운 곳, 양쪽 다 걸을 수 있는 길) → 보행망 노드"""
    from shapely.geometry import LineString
    from shapely.strtree import STRtree
    from evenly_common import load_dongs, dong_of
    big = (N[giant, 0].min(), N[giant, 0].max(), N[giant, 1].min(), N[giant, 1].max())
    roads, attrs = [], []
    for p in sorted(glob.glob(os.path.join(REH, "수치지형도2", "*", "N3L_A0020000.shp"))):
        ds = ogr.Open(p); lyr = ds.GetLayer(0)
        sr = lyr.GetSpatialRef(); sr.SetAxisMappingStrategy(osr.OAMS_TRADITIONAL_GIS_ORDER)
        ct = osr.CoordinateTransformation(sr, S5186)
        dfn = lyr.GetLayerDefn(); nm = {dfn.GetFieldDefn(i).GetName() for i in range(dfn.GetFieldCount())}
        for f in lyr:
            g = f.GetGeometryRef().Clone(); g.Transform(ct)
            mw = f.GetField("자동차전용") if "자동차전용" in nm else None
            wd = f.GetField("도로폭") if "도로폭" in nm else None
            for part in line_parts(g):
                if len(part) >= 2:
                    roads.append(LineString(part)); attrs.append((mw, wd))
    tree = STRtree(roads)
    dongs = load_dongs(["관악구"])
    hits = []
    for i, g in enumerate(roads):
        for j in tree.query(g):
            if j <= i or not g.crosses(roads[j]):
                continue
            (m1, w1), (m2, w2) = attrs[i], attrs[j]
            if "MWI002" in (m1, m2) or w1 is None or w2 is None or max(w1, w2) > 10:   # 자동차전용·넓은 길(고가 가능)·폭 모름은 뺌 → 골목끼리 평면 교차
                continue
            it = g.intersection(roads[j])
            for q in ([it] if it.geom_type == "Point" else [q for q in getattr(it, "geoms", []) if q.geom_type == "Point"]):
                ends = [g.coords[0], g.coords[-1], roads[j].coords[0], roads[j].coords[-1]]
                if min(math.dist((q.x, q.y), x) for x in ends) > 3 and dong_of(q.x, q.y, dongs):   # 끝점에서 3m 넘게 떨어진 교차
                    def dirv(ln):
                        t = ln.project(q)
                        a_, b_ = ln.interpolate(max(0, t - 3)), ln.interpolate(min(ln.length, t + 3))
                        return np.array([b_.x - a_.x, b_.y - a_.y])
                    d1, d2 = dirv(g), dirv(roads[j])
                    ang = math.degrees(math.acos(abs(np.dot(d1, d2)) / (np.linalg.norm(d1) * np.linalg.norm(d2) + 1e-9)))
                    if ang >= 45:                                                                   # 그림에서 교차가 보이게
                        hits.append((q.x, q.y, i, int(j)))
    return roads, hits


def draw_cross(N, e, deg, roads, hits, site):
    """전: 교차하는 두 선(진하게)은 끝점에만 노드(점), 교차점엔 노드 없음 / 후: 교차점에서 잘려(조각마다 색) 노드(주황 원)가 생김.
    후 그림은 원본 선을 교차점에서 자른 모양 (② 노딩, 30m 조각 전). 보행망에도 그 노드가 있는 곳만 고름"""
    from shapely.geometry import box as sbox, Point
    from shapely.ops import substring
    hits.sort(key=lambda p: math.dist(p[:2], site))
    def kept(p):                                        # 보행망에도 두 선이 다 남아 교차점 노드의 링크가 넷 이상
        c = int(np.argmin(np.hypot(N[:, 0] - p[0], N[:, 1] - p[1])))
        return math.dist(N[c], p[:2]) < 1.0 and deg[c] >= 4
    hx, hy, i0, j0 = next(p for p in hits if kept(p))
    here = [p for p in hits if math.dist(p[:2], (hx, hy)) < 30]          # 창 안의 교차 모두 (한 선이 두 선을 지나기도 함)
    cx, cy = np.mean([p[0] for p in here]), np.mean([p[1] for p in here])
    win = mini_win(cx, cy, 26)
    bb = sbox(win[0] - 5, win[2] - 5, win[1] + 5, win[3] + 5)
    ids = sorted({k for p in here for k in p[2:]})
    other = [np.array(r.coords) for k, r in enumerate(roads) if k not in ids and r.intersects(bb)]
    two = [roads[k] for k in ids]
    fig, (a1, a2) = pair(win)
    for ax in (a1, a2):
        ax.add_collection(LineCollection(other, colors=LINE, linewidths=1.2, capstyle="round"))
    a1.add_collection(LineCollection([np.array(t.coords) for t in two], colors=INK, linewidths=1.6, capstyle="round", zorder=3))
    E = np.array([t.coords[k] for t in two for k in (0, -1)])
    a1.scatter(E[:, 0], E[:, 1], s=9, c=INK, linewidths=0, zorder=4)
    pieces = []
    for k, t in zip(ids, two):
        cut = sorted([0.0, t.length] + [t.project(Point(p[0], p[1])) for p in here if k in p[2:]])
        pieces += [substring(t, a_, b_) for a_, b_ in zip(cut[:-1], cut[1:]) if b_ - a_ > 0.01]
    a2.add_collection(LineCollection([np.array(p_.coords) for p_ in pieces], colors=[(INK, MUTED)[n % 2] for n in range(len(pieces))],
                                     linewidths=1.6, capstyle="butt", zorder=3))
    a2.scatter(E[:, 0], E[:, 1], s=9, c=INK, linewidths=0, zorder=4)
    hx_ = [p[0] for p in here]; hy_ = [p[1] for p in here]
    a2.scatter(hx_, hy_, s=48, facecolors="none", edgecolors=ACC, linewidths=1.4, zorder=5)
    a2.scatter(hx_, hy_, s=9, c=ACC, linewidths=0, zorder=6)
    save(fig, "proc28_1.png")
    return {"crossings": [[round(p[0], 1), round(p[1], 1)] for p in here], "dist_from_site_m": round(math.dist((hx, hy), site)),
            "candidates": [[round(p[0]), round(p[1]), round(math.dist(p[:2], site)), bool(kept(p))] for p in hits[:8]]}


def LineStringDist(p, line):
    """점 p 와 꺾은선 line(배열) 사이 거리 (m)"""
    a, b = line[:-1], line[1:]
    ab = b - a
    t = np.clip(((p - a) * ab).sum(1) / np.maximum((ab * ab).sum(1), 1e-9), 0, 1)
    q = a + ab * t[:, None]
    return float(np.min(np.hypot(*(q - p).T)))


def draw_gap(N, e, site):
    """끊긴 끝점 10m 연결: 02_network 가 만든 끊김연결 링크(kind 2) 중 선정지에서 가장 가까운 것
    (4m 넘고, 막다른 끝의 길 방향을 45° 안에서 이어 가는 것 — 그림에서 '끊긴 길을 잇는다'가 보이게)"""
    u, v, k = e["u"], e["v"], e["kind"]
    dg = np.bincount(np.concatenate([u[k != 2], v[k != 2]]), minlength=len(N))
    good = []
    for i in np.where((k == 2) & (e["length"] >= 4))[0]:
        end = u[i] if dg[u[i]] == 1 else (v[i] if dg[v[i]] == 1 else None)
        if end is None:
            continue
        oth = v[i] if end == u[i] else u[i]
        j = np.where(((u == end) | (v == end)) & (k != 2))[0]
        if len(j) != 1:
            continue
        nb = v[j[0]] if u[j[0]] == end else u[j[0]]
        d1, d2 = N[end] - N[nb], N[oth] - N[end]
        ang = math.degrees(math.acos(np.clip(np.dot(d1, d2) / (np.linalg.norm(d1) * np.linalg.norm(d2) + 1e-9), -1, 1)))
        if ang <= 45:
            good.append((math.dist((N[u[i]] + N[v[i]]) / 2, site), int(i)))
    i = min(good)[1]
    m = (N[e["u"][i]] + N[e["v"][i]]) / 2
    win = mini_win(m[0], m[1], 22)
    raw = sum((line_parts(g) for g in read_layer("N3L_A0020000", win, pad=8)), [])
    fig, (a1, a2) = pair(win)
    a1.add_collection(LineCollection(raw, colors=MUTED, linewidths=1.4, capstyle="round"))
    a1.scatter(*N[[e["u"][i], e["v"][i]]].T, s=9, c=INK, linewidths=0, zorder=4)     # 끊긴 끝점과 이어질 곳 (전에는 떨어져 있음)
    sel = in_win(N, e["u"], e["v"], win, 8) & (e["kind"] != 2)
    a2.add_collection(LineCollection(edge_segs(N, e["u"], e["v"], sel), colors=MUTED, linewidths=1.4, capstyle="round"))
    a2.plot(*N[[e["u"][i], e["v"][i]]].T, color=ACC, lw=1.8, ls=(0, (2.2, 1.4)), zorder=5)
    a2.scatter(*N[[e["u"][i], e["v"][i]]].T, s=8, c=INK, linewidths=0, zorder=6)
    save(fig, "proc28_2.png")
    return {"edge": i, "length_m": round(float(e["length"][i]), 1), "dist_from_site_m": round(float(math.dist(m, site)))}


def draw_stair(N, e, site):
    """계단: 선정지 계단 면(공개 대역 = OSM 계단을 넓힌 면) → 면 안의 링크 = 계단 + 계단연결(kind 1)"""
    win = mini_win(site[0], site[1], 34)
    raw = sum((line_parts(g) for g in read_layer("N3L_A0020000", win, pad=8)), [])
    stp = sum((poly_rings(g) for g in read_layer("N3A_C0390000", win, pad=8)), [])
    fig, (a1, a2) = pair(win)
    a1.add_collection(LineCollection(raw, colors=MUTED, linewidths=1.4, capstyle="round"))
    a1.add_collection(PatchCollection([MPoly(r) for r in stp], facecolor=ACC, edgecolor=ACC, alpha=0.45, linewidths=0.5, zorder=3))
    sel = in_win(N, e["u"], e["v"], win, 8)
    a2.add_collection(LineCollection(edge_segs(N, e["u"], e["v"], sel & ~e["is_stair"] & (e["kind"] != 1)), colors=MUTED, linewidths=1.4, capstyle="round"))
    a2.add_collection(LineCollection(edge_segs(N, e["u"], e["v"], sel & e["is_stair"] & (e["kind"] != 1)), colors=ACC, linewidths=2.4, capstyle="butt", zorder=4))
    a2.add_collection(LineCollection(edge_segs(N, e["u"], e["v"], sel & (e["kind"] == 1)), colors=ACC, linewidths=1.6, linestyles=[(0, (2.2, 1.4))], zorder=4))
    save(fig, "proc28_3.png")
    return {"n_stair_links": int((sel & e["is_stair"]).sum()), "n_stair_connect": int((sel & (e["kind"] == 1)).sum())}


def draw_tunnel(cdem=None):
    """다리·터널: OSM 터널(관악구, 걸을 수 있는 길) 중 터널 위 언덕이 가장 높은 것 → 공개 지형 5m 높이 단면.
    전 = 땅 높이(DEM)를 그대로 따르면 언덕을 넘음 / 후 = 터널 안은 경사 0 (양쪽 입구를 곧게)"""
    from evenly_common import load_dongs, dong_of, to5186
    cache = os.path.join(RAW, "osm_bridges_gwanak.json")
    if not os.path.exists(cache):
        st = json.load(open(os.path.join(RAW, "osm_steps_gwanak.json"), encoding="utf-8"))
        lat0, lon0, lat1, lon1 = st["_query_bbox"]
        q = (f'[out:json][timeout:120];(way["highway"]["bridge"]({lat0},{lon0},{lat1},{lon1});'
             f'way["highway"]["tunnel"]({lat0},{lon0},{lat1},{lon1}););out geom tags;')
        req = urllib.request.Request("https://overpass-api.de/api/interpreter", data=urllib.parse.urlencode({"data": q}).encode(),
                                     headers={"User-Agent": "evenly-figs/1.0"})
        with urllib.request.urlopen(req, timeout=180) as r:
            data = json.loads(r.read().decode("utf-8"))
        data.update(_query_bbox=[lat0, lon0, lat1, lon1], _query=q, _license="© OpenStreetMap contributors (ODbL)")
        json.dump(data, open(cache, "w", encoding="utf-8"), ensure_ascii=False)
    data = json.load(open(cache, encoding="utf-8"))
    dem = glob.glob(os.path.join(REH, "수치표고모델_5m", "*.img"))[0]
    ds = gdal.Open(dem)
    gt = ds.GetGeoTransform(); Z = ds.GetRasterBand(1).ReadAsArray().astype(float)
    sr = osr.SpatialReference(wkt=ds.GetProjection()); sr.SetAxisMappingStrategy(osr.OAMS_TRADITIONAL_GIS_ORDER)
    ct = osr.CoordinateTransformation(srs(4326), sr)

    def zat(x, y):
        c, r = (x - gt[0]) / gt[1], (y - gt[3]) / gt[5]
        i, j = int(r), int(c)
        return Z[i, j] if 0 <= i < Z.shape[0] and 0 <= j < Z.shape[1] and Z[i, j] > -1000 else np.nan
    dongs = load_dongs(["관악구"])
    WALK = {"footway", "pedestrian", "path", "living_street", "residential", "unclassified", "service", "tertiary", "secondary", "primary", "cycleway"}
    best = None
    for w in data["elements"]:
        t = w.get("tags", {})
        if w["type"] != "way" or t.get("highway") not in WALK or t.get("tunnel") in (None, "no"):
            continue
        ll = [(p["lon"], p["lat"]) for p in w["geometry"]]
        mid = np.mean(ll, axis=0)
        if not dong_of(*to5186(*mid), dongs):
            continue
        P = np.array([ct.TransformPoint(lo, la)[:2] for lo, la in ll])
        seg = np.hypot(*np.diff(P, axis=0).T); L = seg.sum()
        if not 60 <= L <= 450:
            continue
        cum = np.concatenate([[0], np.cumsum(seg)]); ts = np.linspace(0, L, max(30, int(L / 2)))
        xs_, ys_ = np.interp(ts, cum, P[:, 0]), np.interp(ts, cum, P[:, 1])
        if cdem is not None:                                       # [10/20] 등고선 높이 (5179 → 5186 로 바꿔 표본)
            q = np.asarray(osr.CoordinateTransformation(sr, S5186).TransformPoints(np.c_[xs_, ys_].tolist()))[:, :2]
            zs = cdem.sample(q[:, 0], q[:, 1])
        else:
            zs = np.array([zat(x, y) for x, y in zip(xs_, ys_)])
        if np.isnan(zs).any():
            continue
        hill = zs.max() - max(zs[0], zs[-1]) - abs(zs[0] - zs[-1])
        if best is None or hill > best[0]:
            best = (hill, w["id"], t.get("name"), ts, zs)
    hill, wid, name, ts, zs = best
    fig = plt.figure(figsize=P28, dpi=400)
    wf = P28[1] / P28[0]
    axs = [fig.add_axes([0, 0, wf, 1]), fig.add_axes([1 - wf, 0, wf, 1])]
    lo, hi = zs.min() - (zs.max() - zs.min()) * 0.9, zs.max() + (zs.max() - zs.min()) * 0.25
    pad = (ts[-1]) * 0.06
    for k, ax in enumerate(axs):
        ax.axis("off")
        ax.set_xlim(-pad, ts[-1] + pad); ax.set_ylim(lo, hi)
        ax.fill_between(ts, lo, zs, color=SOFT, zorder=1)
        ax.plot(ts, zs, color=LINE, lw=1.0, zorder=2)
        ax.add_patch(Rectangle((-pad, lo), ts[-1] + 2 * pad, hi - lo, fill=False, ec=LINE, lw=0.8, zorder=50))
        if k == 0:
            ax.plot(ts, zs, color=ACC, lw=1.8, ls=(0, (2.2, 1.4)), zorder=3)          # 땅 높이를 그대로 따르면
        else:
            ax.plot([ts[0], ts[-1]], [zs[0], zs[-1]], color=TEAL, lw=2.0, zorder=3)     # 터널 안 = 경사 0 (입구끼리 곧게)
        ax.scatter([ts[0], ts[-1]], [zs[0], zs[-1]], s=8, c=INK, zorder=4, linewidths=0)
    fig.add_artist(MPoly([[0.5 - 0.012, 0.40], [0.5 + 0.016, 0.5], [0.5 - 0.012, 0.60]], closed=True, transform=fig.transFigure, color=MUTED))
    save(fig, "proc28_4.png")
    return {"osm_way": wid, "name": name, "length_m": round(float(ts[-1])),
            "_설명": ("등고선 5m 격자" if cdem is not None else "공개 지형 5m") + " 단면, 세로는 과장 (축 숫자 없음)"}


def grid_from_slopes(N, e, s, giant, site, dests, half=1600.0, cell=250.0, min_bld=5):
    """[10/20] 같은 경사 s 로 약국까지 왕복 HBI 를 다시 계산해 250m 칸 평균 (03_hbi·05_export 와 같은 규칙: 건물 → 60m 안 가장 가까운 연결망 노드,
    HBI = 고령자 경사 반영 왕복 ÷ 평지 가정 왕복, 칸에 건물 5개 이상). 건물 점 = 공개 리허설 all 방식 건물 (work/all/buildings_hbi.gpkg 의 위치만)"""
    M = load_model()
    from lib.qgraph import NearestIndex
    r = M.run_scenario(len(N), e, s, np.asarray(dests))
    hb_node = np.where(r["t_flat"] == 0, 1.0, r["t_elder"] / np.where(r["t_flat"] == 0, 1, r["t_flat"]))
    gi = np.where(giant)[0]
    idx = NearestIndex(N[gi])
    ds = ogr.Open(os.path.join(H6, "work", "all", "buildings_hbi.gpkg")); lyr = ds.GetLayer(0)
    lyr.SetSpatialFilterRect(site[0] - half, site[1] - half, site[0] + half, site[1] + half)
    pts = np.array([f.GetGeometryRef().GetPoint_2D() for f in lyr])
    dd, ii = idx.query(pts, 60.0)
    ok = ii >= 0
    hb = hb_node[gi[ii[ok]]]
    P = pts[ok][np.isfinite(hb)]; hb = hb[np.isfinite(hb)]
    key = np.floor(P / cell).astype(int)
    out = {}
    for (kx, ky), h in zip(map(tuple, key), hb):
        out.setdefault((kx, ky), []).append(h)
    cells = []
    for (kx, ky), hs in out.items():
        if len(hs) >= min_bld:
            x0, y0 = kx * cell, ky * cell
            cells.append((np.array([[x0, y0], [x0 + cell, y0], [x0 + cell, y0 + cell], [x0, y0 + cell], [x0, y0]]), float(np.mean(hs))))
    return cells


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--win", type=float, default=750, help="11장 그림 한 변 (m). 선정지 계단(양 끝 가운데)이 가운데")
    ap.add_argument("--grid-run", default="gwanak_v62all08")
    ap.add_argument("--contours", help="[10/20] 연속수치지형도 등고선 (tools/extract_contours.py 의 contour_gwanak.gpkg)")
    ap.add_argument("--allow-gaps", action="store_true", help="등고선 빠진 곳이 있어도 그림 (시험용, --out 과 함께만)")
    ap.add_argument("--bg-only", action="store_true", help="[10/20] 등고선은 지도 칸 배경과 28장 터널 단면에만 (경사 색·경로·격자는 공개 지형 그대로)")
    ap.add_argument("--out", help="그림 폴더 (기본 deck/v6_source)")
    a = ap.parse_args()
    global OUT, CBG, CBG_28
    if a.out:
        OUT = os.path.abspath(a.out)
    if a.allow_gaps and not a.out:
        raise SystemExit("--allow-gaps 는 시험용 → --out <다른 폴더> 와 함께 (기획서 그림 자리에 빈 곳 있는 등고선 그림을 두지 않게)")
    if not os.path.exists(os.path.join(REH, "공개대역_README.txt")):
        raise SystemExit(f"공개 대역 자료가 아님: {REH}")
    gdir = os.path.join(ROOT, "results", "public_rehearsal", a.grid_run, "all")
    if source_of(gdir) != PUBLIC_REHEARSAL:
        raise SystemExit(f"공개 대역 표지가 없음: {gdir}")
    ver = open(os.path.join(H6, "VERSION"), encoding="utf-8").read().strip()
    os.makedirs(OUT, exist_ok=True)
    meta = {"_source": "과정 예시: 공개 자료로 그림 (분석은 LX 자료)", "bundle": ver,
            "data": {"길": "국토지리정보원 연속수치지형도 도로중심선 (공개 대역 도엽)", "계단": "© OpenStreetMap contributors (ODbL)",
                     "높이": "공개 지형 타일 AWS Terrain Tiles terrarium z15 (약 30m) → 5m 격자", "격자": f"results/public_rehearsal/{a.grid_run} (공개 자료 보행망 계산, 약국)"}}

    # 창: 선정지 계단 양 끝 가운데를 가운데로 (격자선과는 맞추지 않음 → 5칸이 같은 범위·같은 축척)
    import csv
    import field_fix_v62 as FF
    st_row = next(r for r in csv.DictReader(open(FF.CAND_CSV, encoding="utf-8-sig")) if r["name"].startswith(SITE_NAME))
    ax_, ay_ = to5186_ll(float(st_row["a_lon"]), float(st_row["a_lat"]))
    bx_, by_ = to5186_ll(float(st_row["b_lon"]), float(st_row["b_lat"]))
    sx, sy = (ax_ + bx_) / 2, (ay_ + by_) / 2
    hw = a.win / 2
    win = (round(sx - hw), round(sx + hw), round(sy - hw), round(sy + hw))
    meta["win_5186"] = win
    meta["site_5186"] = [round(sx, 1), round(sy, 1)]
    meta["contour"] = bool(a.contours) and not a.bg_only
    meta["contour_bg"] = bool(a.contours) and a.bg_only
    if a.bg_only and not a.contours:
        raise SystemExit("--bg-only 는 --contours 와 함께")

    d = np.load(os.path.join(H6, "work", "network.npz"))
    N, giant = d["nodes"], d["giant"]
    e = {kk[2:]: d[kk] for kk in d.files if kk.startswith("e_")}
    s5, zuse = d["s5"], d["z5"]
    cdem = None
    if a.contours and a.bg_only:                                    # [10/20] 11장 배경·28장 터널 단면만 등고선 (28장 지도 칸 배경은 없음)
        CBG = os.path.abspath(a.contours)
        CBG_28 = False
        cdem = ContourDEM(CBG, win)
        meta["data"]["등고선"] = "연속수치지형도 등고선 (국토지리정보원): 11장 지도 칸 배경, 28장 터널 단면 높이 (경사 색·경로·격자는 공개 지형)"
        rep_p = os.path.join(os.path.dirname(CBG), "contour_gwanak_report.json")
        meta["contour_report"] = json.load(open(rep_p, encoding="utf-8")) if os.path.exists(rep_p) else None
    elif a.contours:
        src = os.path.abspath(a.contours)
        share, ngap, nneed = contour_gaps(src, win)
        meta["contour_gaps_11"] = {"share": round(share, 3), "cells": ngap, "relief_cells": nneed}
        print(f"등고선 빠진 곳 (11장 창, 100m 칸): {ngap}/{nneed} ({share:.0%})", flush=True)
        if share > 0.03 and not a.allow_gaps:
            raise SystemExit(f"!! 11장 창 안에 등고선이 빠진 100m 칸이 {ngap}/{nneed} ({share:.0%}) → 등고선 묶음이 덜 받아졌을 수 있음 "
                             "(data_public/raw/contour_gwanak_report.json). 온전한 zip 을 받아 tools/extract_contours.py 다시")
        CBG = src
        cdem = ContourDEM(src, win)
        load_model()
        from lib.qnetwork import edge_slope                     # 번들 그대로 (교량·터널 0, ±40% 자름)
        near = (np.abs(N[:, 0] - sx) < 1900) & (np.abs(N[:, 1] - sy) < 1900)
        zc = d["z5"].copy()
        zn = cdem.sample(N[near, 0], N[near, 1])
        zc[np.where(near)[0][np.isfinite(zn)]] = zn[np.isfinite(zn)]
        sc_ = edge_slope(zc, e)[0]
        # [10/20] 경사 검사: 주택가는 1:5000 등고선이 건물 사이에서 끊겨 조각만 남아, 메운 높이가 평평해짐 →
        #   창을 동·서로 나눠 링크 |경사| 중앙값이 공개 지형(30m, 원래 완만하게 잡힘)의 절반도 안 되면 멈춤
        mid_ = (N[e["u"]] + N[e["v"]]) / 2
        inw_ = (mid_[:, 0] > win[0]) & (mid_[:, 0] < win[1]) & (mid_[:, 1] > win[2]) & (mid_[:, 1] < win[3])
        chk = {}
        for nm_, m_ in (("서쪽", inw_ & (mid_[:, 0] < sx)), ("동쪽", inw_ & (mid_[:, 0] >= sx))):
            chk[nm_] = (round(float(np.median(np.abs(d["s5"][m_]))), 3), round(float(np.median(np.abs(sc_[m_]))), 3))
        meta["contour_slope_check"] = {k: {"공개지형": v[0], "등고선": v[1]} for k, v in chk.items()}
        print("링크 |경사| 중앙값 (공개 지형 → 등고선):", " · ".join(f"{k} {v[0]} → {v[1]}" for k, v in chk.items()), flush=True)
        flat_ = [k for k, v in chk.items() if v[1] < 0.5 * v[0]]
        if flat_ and not a.allow_gaps:
            raise SystemExit(f"!! {'·'.join(flat_)} 절반에서 등고선 경사가 공개 지형의 절반도 안 됨 → 주택가 등고선이 조각뿐이라 평평하게 메워짐. "
                             "그림을 바꾸지 않음 (표고점을 더하거나 등고선은 배경으로만)")
        s5, zuse = sc_, zc
        rep_p = os.path.join(os.path.dirname(src), "contour_gwanak_report.json")
        meta["data"]["높이"] = f"연속수치지형도 등고선 (국토지리정보원) → 5m 격자 (높이 칸 {cdem.fld}, 선정지 둘레 ±1.9km 노드만, 그 밖은 공개 지형)"
        meta["contour_report"] = json.load(open(rep_p, encoding="utf-8")) if os.path.exists(rep_p) else None
        meta["_source"] = "과정 예시: 공개 자료(연속수치지형도 등고선)로 그림"
    sel = in_win(N, e["u"], e["v"], win) & giant[e["u"]] & giant[e["v"]]

    roads = sum((line_parts(g) for g in read_layer("N3L_A0020000", win)), [])
    stairs = sum((poly_rings(g) for g in read_layer("N3A_C0390000", win)), [])

    # ① 수치지형도 원본: 도로중심선(회색) + 계단 면(주황) + 선정지 동그라미
    fig, ax = panel(win)
    ax.add_collection(LineCollection(roads, colors=MUTED, linewidths=0.55, capstyle="round"))
    ax.add_collection(PatchCollection([MPoly(r) for r in stairs], facecolor=ACC, edgecolor=ACC, linewidths=0.6, zorder=5))
    ax.add_patch(Circle((sx, sy), 45, fill=False, ec=INK, lw=0.9, ls=(0, (2, 1.5)), zorder=6))
    scale_bar(ax, win)
    save(fig, "proc11_1.png")

    # ② 30m 조각 보행망: 링크 + 노드 점
    fig, ax = panel(win)
    ax.add_collection(LineCollection(edge_segs(N, e["u"], e["v"], sel), colors=MUTED, linewidths=0.4))
    used = np.unique(np.concatenate([e["u"][sel], e["v"][sel]]))
    ax.scatter(N[used, 0], N[used, 1], s=1.6, c=TEAL, linewidths=0, zorder=4)
    st_ = sel & e["is_stair"]
    ax.add_collection(LineCollection(edge_segs(N, e["u"], e["v"], st_), colors=ACC, linewidths=1.3, zorder=5))
    scale_bar(ax, win)
    save(fig, "proc11_2.png")

    # ③ 링크 경사 색 (초록 평지 → 노랑 → 빨강 급경사)
    fig, ax = panel(win)
    order = np.argsort(np.abs(s5[sel]))                 # 급한 링크를 위에
    segs = edge_segs(N, e["u"], e["v"], sel)[order]
    ax.add_collection(LineCollection(segs, colors=slope_color(s5[sel][order]), linewidths=0.9, capstyle="round"))
    scale_bar(ax, win)
    save(fig, "proc11_3.png")

    # ④ 경로: 같은 집 → 같은 약국, 평지 가정(회색) vs 경사 반영(주황)
    dn = np.load(os.path.join(H6, "work", "all", "dest_nodes.npz"))
    ph = np.array(dn["pharmacy"])
    inner = lambda p, m=40: win[0] + m <= p[0] <= win[1] - m and win[2] + m <= p[1] <= win[3] - m
    phw = [int(i) for i in ph if inner(N[i])]
    best = None
    for p_ in phw:
        R = paths_to(N, e, s5, p_, giant)
        de, pe = R["elder"]; df, pf = R["flat"]
        cand = np.where(np.isfinite(de) & giant & (np.hypot(N[:, 0] - N[p_, 0], N[:, 1] - N[p_, 1]) > 200))[0]
        for o in cand[:: max(1, len(cand) // 4000)]:
            if not inner(N[o], 60):
                continue
            P1, P2 = walk(pe, o), walk(pf, o)
            if P1[-1] != p_ or P2[-1] != p_ or not all(inner(N[i], 15) for i in P1 + P2):
                continue
            E1 = set(zip(P1[:-1], P1[1:])); E2 = set(zip(P2[:-1], P2[1:]))
            share = len(E1 & E2) / max(1, len(E1 | E2))
            L1 = sum(math.dist(N[i], N[j]) for i, j in E1); L2 = sum(math.dist(N[i], N[j]) for i, j in E2)
            if L2 < 250 or L1 > 2.2 * L2 or zuse[o] < zuse[p_] + 10:   # 집은 약국보다 10m 넘게 높은 곳 (언덕 위 집)
                continue
            score = (1 - share) * min(L2, 600)
            if best is None or score > best[0]:
                best = (score, o, p_, P1, P2, share, L1, L2)
    if best is None:
        raise SystemExit("창 안에서 두 길이 갈리는 예시를 못 찾음 → --win 을 키워 보기")
    _, o, p_, P1, P2, share, L1, L2 = best
    meta["route"] = {"origin_node": int(o), "pharmacy_node": int(p_), "edge_share": round(share, 2), "len_slope_m": round(L1), "len_flat_m": round(L2),
                     "_설명": "기획서 그림에 숫자를 쓰지 않음. 고른 기준: 두 길이 가장 많이 갈리고 둘 다 창 안"}
    fig, ax = panel(win)
    ax.add_collection(LineCollection(edge_segs(N, e["u"], e["v"], sel), colors=LINE, linewidths=0.45))
    ax.plot(N[P2, 0], N[P2, 1], color=MUTED, lw=2.0, solid_capstyle="round", solid_joinstyle="round", zorder=5)
    ax.plot(N[P1, 0], N[P1, 1], color=ACC, lw=2.0, solid_capstyle="round", solid_joinstyle="round", zorder=6)
    ax.scatter([N[o, 0]], [N[o, 1]], s=26, c=INK, zorder=8, linewidths=0)
    ax.scatter([N[p_, 0]], [N[p_, 1]], s=30, c=TEAL, marker="s", zorder=8, linewidths=0)
    scale_bar(ax, win)
    save(fig, "proc11_4.png")

    # ⑤ 250m 격자 색 (공개 자료 보행망, 약국) — 연할수록 부담 적음. 숫자 없음
    cells = []
    if cdem is not None and not a.bg_only:
        cells = grid_from_slopes(N, e, s5, giant, (sx, sy), dn["pharmacy"])
        meta["data"]["격자"] = "같은 등고선 경사로 다시 계산 (번들 lib/model.run_scenario, 약국, 건물 → 60m 안 가장 가까운 노드, 250m 칸 건물 5개 이상)"
    else:
        ds = ogr.Open(os.path.join(gdir, "grid_hbi_pharmacy.gpkg"))
        lyr = ds.GetLayer(0)
        for f in lyr:
            hb = f.GetField("hbi_mean")
            if hb is None:
                continue
            r = poly_rings(f.GetGeometryRef())[0]
            cells.append((r, float(hb)))
    hv = np.array([h for _, h in cells])
    lo, hi = np.percentile(hv, 5), np.percentile(hv, 95)        # 관악 전체 격자 기준 (창 밖 포함) 색 범위
    from matplotlib.colors import LinearSegmentedColormap
    cmap = LinearSegmentedColormap.from_list("burden", [SOFT, "#F2B49F", ACC, ACCD])
    fig, ax = panel(win)
    pc = [MPoly(r) for r, _ in cells]
    cols = [cmap(min(1, max(0, (h - lo) / (hi - lo)))) for _, h in cells]
    ax.add_collection(PatchCollection(pc, facecolor=cols, edgecolor="white", linewidths=1.2, zorder=1))
    ax.add_collection(LineCollection(edge_segs(N, e["u"], e["v"], sel), colors=INK, linewidths=0.25, alpha=0.35, zorder=2))
    scale_bar(ax, win)
    save(fig, "proc11_5.png")
    meta["grid_color"] = "관악 격자 hbi_mean 5~95% 범위로 연한 색 → 진한 주황 (숫자 없음)"

    # ── 28장 전처리 네 칸 ──
    deg = np.bincount(np.concatenate([e["u"], e["v"]]), minlength=len(N))
    roads_all, hits = fig_cross(N, e, deg, giant)
    meta["p28_cross"] = draw_cross(N, e, deg, roads_all, hits, (sx, sy))
    meta["p28_gap"] = draw_gap(N, e, (sx, sy))
    meta["p28_stair"] = draw_stair(N, e, (sx, sy))
    meta["p28_tunnel"] = draw_tunnel(cdem)
    meta["data"]["터널"] = "© OpenStreetMap contributors (ODbL), data_public/raw/osm_bridges_gwanak.json"
    json.dump(meta, open(os.path.join(OUT, "proc_figs_meta.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"→ {os.path.relpath(OUT, ROOT)}/proc11_1~5.png, proc28_1~4.png", json.dumps({k: meta[k] for k in ("route", "p28_cross", "p28_gap", "p28_stair", "p28_tunnel")}, ensure_ascii=False), "창", win)


if __name__ == "__main__":
    main()
