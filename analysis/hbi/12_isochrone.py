# -*- coding: utf-8 -*-
"""
12_isochrone.py ─ [v5] 시설 주변 "몇 분 안에 걸어서 올 수 있는 범위"(등시선)를 평지·고령자·휠체어로 비교

[실행]  python 12_isochrone.py      (run_all.py 가 끝난 뒤 한 줄 따로. 02·03 결과를 읽기만 함)
[준비]  external/iso_points.csv 에 점마다 한 줄 (메모장·엑셀로 열어 입력)
          name(이름), lon, lat(경위도), minutes(분, "5;10;15" 처럼 ; 로 여러 개), note(메모)
[하는 일]
  1. 점을 가장 가까운 길 노드에 연결 (SNAP_WARN_M 보다 멀면 경고 → 좌표 확인).
     [v6.1a] SNAP_SKIP_M 보다 멀면 길 자료 범위 밖으로 보고 그 점은 건너뜀 (자료 가장자리 노드에서 잘못 계산하지 않게)
  2. 길 네트워크(work/network.npz)에서 모든 노드 → 그 점까지 "걸어오는" 시간을 세 방식으로 계산 (집 → 시설 방향)
       flat  : 평지 가정 (고령자 속도, 경사 무시)
       elder : 고령자, 경사 반영 (lib/model.py 의 elder_time, 03_hbi.py 와 같은 식)
       wheel : 휠체어 (lib/model.py 의 wheel_time, 계단은 못 지나감)
  3. 제한 시간 안에 양 끝이 모두 닿는 링크 → 25m 버퍼 → 합침 → 10m 단순화 = 도달 범위 면 하나 (방식 × 분마다)
  4. 도달 범위 안 주거 건물 수를 세고 (MIN_COUNT 개 미만이면 빈 칸), 면적을 평지와 비교
  JS로 치면: 지도 앱의 "걸어서 10분 권역"을 경사가 있는 경우와 없는 경우로 두 번 그려 겹쳐 보는 것
[결과] (output/ → 반출 대상)
  isochrone_<점이름>.gpkg   : 시설 주변 도보 도달 범위를 나타낸 면 도형(길 중심선 25m 버퍼, 10m 단순화). 건물·필지 단위 정보 없음
                              열: name, mode(flat/elder/wheel), minutes, area_km2
  isochrone_summary.csv     : name, mode, minutes, area_km2, ratio_to_flat(평지 면적 대비), n_res_bld(범위 안 주거 건물 수)
  map_isochrone_<점이름>.png : matplotlib 이 있을 때만. 분마다 한 칸, 세 방식을 색으로 겹쳐 그림
[결과 보는 법]
  - ratio_to_flat 이 1 보다 작을수록 경사 때문에 같은 시간에 갈 수 있는 범위가 줄어든 것
  - 화면에 "!! 검사" 가 나오면 계산이 이상한 것 (경사 반영 범위가 평지보다 넓거나, 경사가 있는데 면적이 평지와 같음)
  - 휠체어는 계단을 못 지나가서 모양 자체가 달라질 수 있음
"""
import os, re, numpy as np
np.seterr(invalid="ignore", divide="ignore")
from osgeo import ogr
import config as C
from lib.qio import log, read_csv, write_csv, transform_xy, transformer, TARGET
from lib.qgraph import NearestIndex, Graph
from lib.netload import load
from lib.bload import load_buildings, usable
from lib.model import elder_time, wheel_time, directed
from lib.deps import HAS_MPL

# ── 이 스크립트만의 설정 (config.py 는 바꾸지 않음) ─────────────
BUFFER_M = 25          # 도달한 길 중심선 양쪽으로 몇 m 까지 면으로 칠지
SIMPLIFY_M = 10        # 면 테두리 단순화 (m). 반출 도형을 가볍게, 건물 윤곽이 드러나지 않게
SNAP_WARN_M = 60       # 점이 가장 가까운 길에서 이보다 멀면 경고
SNAP_SKIP_M = C.OUT_OF_DATA_M   # [v6.1a] 이보다 멀면 길 자료 범위 밖 → 그 점은 건너뜀 (결과 파일에 줄을 만들지 않음)
SLOPE_CHECK = 0.01     # 도달 범위 안 링크의 평균 경사(절댓값)가 이보다 크면 "경사가 있는 곳" 으로 보고 면적 검사
MODES = [("flat", "평지 가정"), ("elder", "고령자 경사 반영"), ("wheel", "휠체어")]
COLORS = {"flat": "#9aa5ad", "elder": "#e8743b", "wheel": "#2f6fb0"}

os.makedirs(C.OUTPUT, exist_ok=True)
pts = read_csv(os.path.join(C.EXTERNAL, "iso_points.csv"))
if not pts:
    raise SystemExit("external/iso_points.csv 가 없거나 비어 있습니다 → 건너뜀")

net = load()
nodes, e, s = net["nodes"], net["e"], net["s5"]
N = len(nodes)
u, v, L, ss, st = directed(e, s)                                  # 양방향 간선 (오르막·내리막 구분)
W = {"flat": L / C.ELDER_SPEED,                                   # 평지 가정: 거리 ÷ 고령자 속도 (경사 무시)
     "elder": elder_time(L, ss, st),                              # 고령자 경사 반영
     "wheel": wheel_time(L, ss, st)}                              # 휠체어 (계단 = 무한대)
G = {m: Graph(u, v, W[m], N) for m, _ in MODES}
b = load_buildings()
bx, by = b["x"][usable(b)], b["y"][usable(b)]                     # 데이터 경계 근처 건물은 세지 않음
gi = np.where(net["giant"])[0]
idx = NearestIndex(nodes[gi])
tf = transformer("EPSG:4326")


def reach_polygon(t, limit_s):
    """노드별 도착 시간 t(초) → 제한 시간 안에 양 끝이 모두 닿는 링크를 버퍼로 합친 면 (없으면 None)"""
    ok = (t[e["u"]] <= limit_s) & (t[e["v"]] <= limit_s)
    if not ok.any():
        return None, ok
    ml = ogr.Geometry(ogr.wkbMultiLineString)
    for a, c in zip(e["u"][ok], e["v"][ok]):
        ln = ogr.Geometry(ogr.wkbLineString)
        ln.AddPoint_2D(float(nodes[a, 0]), float(nodes[a, 1]))
        ln.AddPoint_2D(float(nodes[c, 0]), float(nodes[c, 1]))
        ml.AddGeometry(ln)
    # [v6] QGIS 3.32(GDAL 3.7)의 GEOS 가 같은 자료에서도 가끔 "NaN/Inf" 오류로 멈춤 (v5 시험에서 재현, 12번 돌리면 한 번꼴)
    #      → 같은 계산을 다시 하면 지나가므로 5번까지 다시 함 (결과는 같음). 그래도 안 되면 오류를 그대로 냄
    for k in range(5):
        try:
            return ml.Buffer(BUFFER_M).SimplifyPreserveTopology(SIMPLIFY_M), ok
        except RuntimeError:
            if k == 4:
                raise


def count_inside(poly):
    """면 안의 주거 건물 수 (먼저 사각 범위로 거른 뒤 하나씩 확인)"""
    x0, x1, y0, y1 = poly.GetEnvelope()
    cand = np.where((bx >= x0) & (bx <= x1) & (by >= y0) & (by <= y1))[0]
    n = 0
    for i in cand:
        p = ogr.Geometry(ogr.wkbPoint)
        p.AddPoint_2D(float(bx[i]), float(by[i]))
        n += poly.Contains(p)
    return n


def safe(name):
    return re.sub(r"[\\/:*?\"<>|\s]+", "_", name.strip())


summary, fails, skipped = [], 0, []
for r in pts:
    name = (r.get("name") or "").strip()
    try:
        lon, lat = float(r["lon"]), float(r["lat"])
    except (KeyError, TypeError, ValueError):
        log(f"  !! {name or '(이름 없음)'}: lon·lat 이 비어 있어 건너뜀")
        continue
    mins = [int(float(x)) for x in re.split(r"[;,\s]+", r.get("minutes") or "") if x.strip()] or [5, 10, 15]
    (px,), (py,) = transform_xy(tf, [lon], [lat])
    d, i = idx.query(np.array([[px, py]]))
    if not d[0] <= SNAP_SKIP_M:          # scipy 없는 대체 구현은 5km 넘게 먼 점에 거리 inf·번호 -1 을 줌 → 이것도 여기서 건너뜀
        far = f"{d[0]:.0f}m" if np.isfinite(d[0]) else "5km 넘게"
        log(f"  !! {name}: 가장 가까운 길이 {far} 떨어져 있음 → 길 자료 범위 밖으로 보고 건너뜀 (이 점은 결과 없음)")
        skipped.append(name)
        continue
    node = int(gi[i[0]])
    if d[0] > SNAP_WARN_M:
        log(f"  !! {name}: 가장 가까운 길이 {d[0]:.0f}m 떨어져 있음 → 좌표 확인 (그대로 계산은 함)")
    log(f"{name}: 길 노드에 연결 ({d[0]:.0f}m), {'·'.join(map(str, mins))}분")
    T = {m: G[m].dijkstra(np.array([node]), reverse=True) for m, _ in MODES}   # 각 노드 → 이 점까지 걸어오는 시간(초)
    polys = []
    for mi in mins:
        area = {}
        for m, _ in MODES:
            poly, ok = reach_polygon(T[m], mi * 60)
            a = poly.GetArea() / 1e6 if poly is not None else 0.0
            area[m] = a
            n = count_inside(poly) if poly is not None else 0
            polys.append((m, mi, a, poly))
            summary.append([name, m, mi, round(a, 4), None, n if n >= C.MIN_COUNT else ""])
            if m == "flat":
                slope = float(np.nanmean(np.abs(s[ok]))) if ok.any() else 0.0
        for row in summary[-len(MODES):]:
            row[4] = round(row[3] / area["flat"], 3) if area["flat"] > 0 else ""
        # 검사: 고령자 시간은 링크마다 평지 시간 이상이므로 면적도 평지 이하여야 함. 경사가 있는 곳이면 더 작아야 함
        if area["elder"] > area["flat"] * 1.001:
            log(f"  !! 검사: {name} {mi}분 고령자 경사 반영 면적({area['elder']:.3f}km²)이 평지({area['flat']:.3f}km²)보다 넓음 → 계산 확인")
            fails += 1
        elif slope > SLOPE_CHECK and area["flat"] > 0 and area["elder"] >= area["flat"] * 0.999:
            log(f"  !! 검사: {name} {mi}분 경사가 있는데(평균 {slope:.1%}) 고령자 면적이 평지와 같음 → 평지 방식에 경사가 섞였는지 확인")
            fails += 1
        log(f"  {mi}분: 평지 {area['flat']:.3f}km², 고령자 {area['elder']:.3f}km² ({area['elder'] / area['flat']:.0%}), "
            f"휠체어 {area['wheel']:.3f}km² ({area['wheel'] / area['flat']:.0%})" if area["flat"] > 0 else f"  {mi}분: 도달 범위 없음")
    # 도형 저장
    path = os.path.join(C.OUTPUT, f"isochrone_{safe(name)}.gpkg")
    drv = ogr.GetDriverByName("GPKG")
    if os.path.exists(path):
        drv.DeleteDataSource(path)
    ds = drv.CreateDataSource(path)
    lyr = ds.CreateLayer("isochrone", TARGET, ogr.wkbMultiPolygon)
    for k, t_ in (("name", ogr.OFTString), ("mode", ogr.OFTString), ("minutes", ogr.OFTInteger), ("area_km2", ogr.OFTReal)):
        lyr.CreateField(ogr.FieldDefn(k, t_))
    for m, mi, a, poly in sorted(polys, key=lambda x: -x[1]):      # 큰 범위부터 (QGIS 에서 작은 범위가 위에 보이게)
        if poly is None:
            continue
        f = ogr.Feature(lyr.GetLayerDefn())
        f.SetField("name", name); f.SetField("mode", m); f.SetField("minutes", mi); f.SetField("area_km2", round(a, 4))
        f.SetGeometry(ogr.ForceToMultiPolygon(poly))
        lyr.CreateFeature(f)
    ds = None
    # 그림
    if HAS_MPL:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        from matplotlib.patches import Polygon as MPoly, Patch
        from matplotlib import font_manager as fm
        have = {f.name for f in fm.fontManager.ttflist}
        plt.rcParams["font.family"] = next((f for f in ("Malgun Gothic", "Apple SD Gothic Neo", "AppleGothic", "NanumGothic") if f in have), "sans-serif")
        big = [p for m, mi, a, p in polys if p is not None]
        env = [p.GetEnvelope() for p in big]                          # 모든 칸을 같은 축척으로 (가장 큰 범위 기준)
        lim = (min(x[0] for x in env), max(x[1] for x in env), min(x[2] for x in env), max(x[3] for x in env)) if env else None
        fig, axes = plt.subplots(1, len(mins), figsize=(4 * len(mins), 4), squeeze=False)
        for ax, mi in zip(axes[0], mins):
            for m, label in MODES:
                for mm, mii, a, poly in polys:
                    if mm != m or mii != mi or poly is None:
                        continue
                    for k in range(poly.GetGeometryCount() if poly.GetGeometryName() == "MULTIPOLYGON" else 1):
                        pg = poly.GetGeometryRef(k) if poly.GetGeometryName() == "MULTIPOLYGON" else poly
                        ring = np.array(pg.GetGeometryRef(0).GetPoints())[:, :2]
                        ax.add_patch(MPoly(ring, closed=True, facecolor=COLORS[m], edgecolor=COLORS[m], alpha=0.35, lw=1))
            ax.plot(px, py, "k*", ms=10)
            ax.set_title(f"{mi}분"); ax.set_aspect("equal"); ax.set_xticks([]); ax.set_yticks([])
            if lim:
                ax.set_xlim(lim[0] - 50, lim[1] + 50); ax.set_ylim(lim[2] - 50, lim[3] + 50)
        axes[0][-1].legend(handles=[Patch(color=COLORS[m], alpha=0.5, label=f"{m} ({lab})") for m, lab in MODES], loc="lower right", fontsize=8)
        fig.suptitle(f"{name}: 걸어서 올 수 있는 범위 (★ = 시설)"); fig.tight_layout()
        fig.savefig(os.path.join(C.OUTPUT, f"map_isochrone_{safe(name)}.png"), dpi=120); plt.close(fig)

write_csv(os.path.join(C.OUTPUT, "isochrone_summary.csv"), ["name", "mode", "minutes", "area_km2", "ratio_to_flat", "n_res_bld"], summary)
log(f"완료 → output/isochrone_*.gpkg, isochrone_summary.csv ({len(summary)}행)" + (f"  !! 검사 실패 {fails}건" if fails else "")
    + (f", 길 자료 범위 밖이라 건너뜀 {len(skipped)}곳: {', '.join(skipped)}" if skipped else ""))
