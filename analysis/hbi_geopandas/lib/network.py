# -*- coding: utf-8 -*-
"""보행 네트워크 구축: 보도/도로중심선 노딩 → 링크 분할 → 계단·교량 태깅 → DEM 고도"""
import numpy as np, pandas as pd, geopandas as gpd, shapely
from shapely.geometry import LineString
from scipy.spatial import cKDTree
import config as C
from lib.io_utils import log, read_layer

def _lines(g):
    g = g.explode(index_parts=False)
    g = g[g.geom_type == "LineString"]
    return list(g.geometry.values)

def build_edges():
    log("보행 네트워크 구축")
    sw = read_layer("sidewalk_cl"); rd = read_layer("road_cl")
    geoms = _lines(sw) + _lines(rd)
    if not geoms:
        raise RuntimeError("보도중심선/도로중심선 레이어가 없습니다. config.LAYERS 확인")
    log(f"  원본 선 {len(geoms):,}개 → 교차점 노딩 중")
    noded = shapely.union_all(np.array(geoms, dtype=object), grid_size=0.01)
    segs = [s for s in shapely.get_parts(noded) if s.geom_type == "LineString" and s.length > 0.05]
    segs = np.array(segs, dtype=object)
    L = shapely.length(segs)
    n = np.maximum(1, np.ceil(L / C.SEG_LEN)).astype(int)
    idx = np.repeat(np.arange(len(segs)), n)
    k = np.concatenate([np.arange(m) for m in n])
    nn = n[idx]
    d0 = L[idx] * k / nn; d1 = L[idx] * (k + 1) / nn
    p0 = shapely.line_interpolate_point(segs[idx], d0)
    p1 = shapely.line_interpolate_point(segs[idx], d1)
    pm = shapely.line_interpolate_point(segs[idx], (d0 + d1) / 2)
    e = pd.DataFrame({"x0": shapely.get_x(p0), "y0": shapely.get_y(p0),
                      "x1": shapely.get_x(p1), "y1": shapely.get_y(p1),
                      "xm": shapely.get_x(pm), "ym": shapely.get_y(pm),
                      "length": L[idx] / nn})
    e["is_stair"] = False; e["flat"] = False; e["kind"] = "path"
    log(f"  링크 {len(e):,}개 (평균 {e.length.mean():.1f}m)")

    mid = gpd.GeoSeries(gpd.points_from_xy(e.xm, e.ym), crs=C.TARGET_CRS)
    stairs = read_layer("stairs")
    if len(stairs) and C.COL["stair_kind"] in stairs.columns:
        stairs = stairs[stairs[C.COL["stair_kind"]].astype(str).str.upper().isin([C.STAIR_CODE, "", "NAN", "NONE"])]
    stairs = stairs[stairs.geom_type.isin(["Polygon", "MultiPolygon"])].reset_index(drop=True)
    if len(stairs):
        hit = gpd.sjoin(gpd.GeoDataFrame(geometry=mid), stairs[["geometry"]], predicate="within")
        e.loc[hit.index.unique(), "is_stair"] = True
        crossed = set(hit["index_right"].unique())
        log(f"  계단 {len(stairs):,}개 중 네트워크가 지나는 계단 {len(crossed):,}개, 계단 링크 {e.is_stair.sum():,}개")
    for key in ["bridge", "tunnel"]:
        poly = read_layer(key)
        poly = poly[poly.geom_type.isin(["Polygon", "MultiPolygon"])]
        if len(poly):
            hit = gpd.sjoin(gpd.GeoDataFrame(geometry=mid), poly[["geometry"]], predicate="within")
            e.loc[hit.index.unique(), "flat"] = True
    log(f"  교량·터널 구간(경사 0 처리) {e.flat.sum():,}개")

    # 노드 병합
    q = C.SNAP_TOL
    k0 = list(zip(np.round(e.x0 / q).astype(np.int64), np.round(e.y0 / q).astype(np.int64)))
    k1 = list(zip(np.round(e.x1 / q).astype(np.int64), np.round(e.y1 / q).astype(np.int64)))
    codes, uniq = pd.factorize(pd.Series(k0 + k1))
    e["u"] = codes[:len(e)]; e["v"] = codes[len(e):]
    nodes = pd.DataFrame({"x": [a * q for a, b in uniq], "y": [b * q for a, b in uniq]})
    e = e[e.u != e.v].reset_index(drop=True)

    # 네트워크가 지나지 않는 계단 → 계단 양 끝을 가까운 노드와 연결하는 계단 링크 추가
    if len(stairs):
        tree = cKDTree(nodes[["x", "y"]].values)
        add = []
        for i, geom in enumerate(stairs.geometry):
            if i in crossed: continue
            r = geom.minimum_rotated_rectangle
            if r.geom_type != "Polygon": continue
            c = np.array(r.exterior.coords)[:4]
            sides = [np.linalg.norm(c[(j + 1) % 4] - c[j]) for j in range(4)]
            j = int(np.argmin(sides))
            a = (c[j] + c[(j + 1) % 4]) / 2; b = (c[(j + 2) % 4] + c[(j + 3) % 4]) / 2
            da, ia = tree.query(a); db, ib = tree.query(b)
            if da <= C.STAIR_CONNECT_TOL and db <= C.STAIR_CONNECT_TOL and ia != ib:
                add.append(dict(u=ia, v=ib, length=float(np.linalg.norm(a - b) + da + db),
                                is_stair=True, flat=False, kind="stair_link",
                                xm=float((a[0] + b[0]) / 2), ym=float((a[1] + b[1]) / 2)))
        if add:
            e = pd.concat([e, pd.DataFrame(add)], ignore_index=True)
        log(f"  계단 연결 링크 추가 {len(add):,}개")

    # 끊긴 선 끝점(막다른 점)을 다른 연결요소의 가까운 노드와 연결 (보도중심선-도로중심선 접합)
    from scipy.sparse import coo_matrix
    from scipy.sparse.csgraph import connected_components
    def comps(e):
        n = len(nodes)
        A = coo_matrix((np.ones(len(e)), (e.u.values, e.v.values)), shape=(n, n))
        return connected_components(A, directed=False)[1]
    lab = comps(e)
    deg = np.bincount(np.r_[e.u.values, e.v.values], minlength=len(nodes))
    tree = cKDTree(nodes[["x", "y"]].values)
    add = []
    for i in np.where(deg == 1)[0]:
        for j in tree.query_ball_point(nodes.loc[i, ["x", "y"]].values, C.BRIDGE_TOL):
            if lab[j] != lab[i]:
                d = float(np.hypot(*(nodes.loc[i, ["x", "y"]].values - nodes.loc[j, ["x", "y"]].values)))
                add.append(dict(u=i, v=j, length=max(d, 0.5), is_stair=False, flat=False, kind="bridge_link",
                                xm=float(nodes.x[i] + nodes.x[j]) / 2, ym=float(nodes.y[i] + nodes.y[j]) / 2))
                break
    if add:
        e = pd.concat([e, pd.DataFrame(add)], ignore_index=True)
    lab = comps(e)
    big = np.bincount(lab).argmax()
    share = (lab == big).mean()
    log(f"  끊긴 끝점 연결 {len(add):,}개 → 최대 연결망 노드 비율 {share:.1%}")
    keep = lab[e.u.values] == big
    e = e[keep].reset_index(drop=True)
    nodes["giant"] = lab == big
    return nodes, e[["u", "v", "length", "is_stair", "flat", "kind", "xm", "ym"]]

def attach_z(nodes, dem):
    z = dem.sample(nodes.x.values, nodes.y.values)
    miss = np.isnan(z).mean()
    log(f"  노드 고도 추출: 결측 {miss:.1%}")
    return z

def edge_slope(nodes_z, e):
    dz = nodes_z[e.v.values] - nodes_z[e.u.values]
    s = np.where(np.isnan(dz), 0.0, dz) / np.maximum(e.length.values, 0.5)
    s = np.where(e.flat.values, 0.0, s)
    bad = np.abs(s) > C.SLOPE_CLIP
    s = np.clip(s, -C.SLOPE_CLIP, C.SLOPE_CLIP)
    return s, bad
