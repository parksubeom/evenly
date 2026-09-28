# -*- coding: utf-8 -*-
"""
lib/qnetwork.py ─ 수치지형도로 "걸어 다닐 수 있는 길 네트워크"를 만드는 파일

[전체 흐름]  (02_network.py 가 build_edges() 를 호출)
 ① 보도중심선 + 도로중심선의 선들을 모두 읽음
 ② 선끼리 교차하는 모든 지점에서 선을 자름 (노딩) → 교차로마다 노드가 생김
 ③ 각 선을 30m 이하 조각(링크)으로 다시 자름 → 조각마다 경사를 따로 계산하기 위해
 ④ 계단 폴리곤 안에 있는 링크 = 계단으로 표시. 교량·터널 안의 링크 = 경사 0 표시
 ⑤ 1m 안의 끝점들은 같은 노드로 합침 → 노드 번호 부여
 ⑥ 길이 안 지나가는 계단은 계단 양 끝을 가까운 노드와 이어 "계단 링크"를 추가
 ⑦ 끊긴 선 끝(막다른 점)을 10m 안의 다른 길 덩어리와 이어 줌 (보도↔도로 연결)
 ⑧ 가장 큰 연결 덩어리만 남김 (고립된 작은 조각 제거)

[결과 형태]
 nodes_xy : 노드 좌표 배열 [[x, y], ...]
 giant    : 노드가 가장 큰 덩어리에 속하는지 True/False 배열
 e        : 링크 정보 딕셔너리. 모든 값은 같은 길이의 배열이고, i번째 원소들이 i번째 링크 정보
            {"u": 시작노드, "v": 끝노드, "length": 길이(m), "is_stair": 계단 여부,
             "flat": 교량·터널 여부, "xm","ym": 링크 중간점 좌표, "kind": 0 일반 / 1 계단연결 / 2 끊김연결}
"""
import numpy as np
from osgeo import ogr
import config as C
from lib.qio import log, iter_layer
from lib.qgraph import NearestIndex, components


def _line_arrays(g):
    """도형 g 안의 모든 선을 [[x,y],[x,y],...] 배열 목록으로. (여러 선이 묶인 멀티라인도 풀어서)"""
    t = ogr.GT_Flatten(g.GetGeometryType())
    if t == ogr.wkbLineString:
        return [np.array(g.GetPoints())[:, :2]] if g.GetPointCount() >= 2 else []
    if t in (ogr.wkbMultiLineString, ogr.wkbGeometryCollection):
        out = []
        for i in range(g.GetGeometryCount()):
            out += _line_arrays(g.GetGeometryRef(i))    # 재귀 호출로 안쪽 선들도 꺼냄
        return out
    return []                                            # 점·면 등 선이 아닌 도형은 무시


def polygons(key):
    """config.LAYERS[key] 레이어에서 면(폴리곤) 도형만 골라 [(도형, 속성), ...] 로 반환"""
    out = []
    for g, a in iter_layer(key):
        if ogr.GT_Flatten(g.GetGeometryType()) in (ogr.wkbPolygon, ogr.wkbMultiPolygon):
            out.append((g, a))
    return out


def points_in_polygons(px, py, polys):
    """점들(px, py 배열)이 폴리곤들 중 어디에 들어가는지.
    반환: (들어감 여부 True/False 배열, 들어간 폴리곤 번호 배열(-1=없음))
    속도를 위해 먼저 폴리곤의 네모 범위(envelope)로 후보를 추린 뒤, 후보만 정확히 검사합니다."""
    inside = np.zeros(len(px), bool)
    which = np.full(len(px), -1)
    for k, (g, _) in enumerate(polys):
        x0, x1, y0, y1 = g.GetEnvelope()
        cand = np.where((px >= x0) & (px <= x1) & (py >= y0) & (py <= y1) & ~inside)[0]   # ~ 는 NOT
        for i in cand:
            pt = ogr.Geometry(ogr.wkbPoint)
            pt.AddPoint_2D(float(px[i]), float(py[i]))
            if g.Contains(pt):
                inside[i] = True
                which[i] = k
    return inside, which


def build_edges():
    log("보행 네트워크 구축")

    # ① 선 읽기 ─────────────────────────────────────────
    lines = []
    for key in ("sidewalk_cl", "road_cl"):
        n0 = len(lines)
        for g, _ in iter_layer(key):
            lines += _line_arrays(g)
        log(f"  {key}: 선 {len(lines) - n0:,}개")        # {숫자:,} 는 천 단위 콤마 (1,234)
    if not lines:
        raise RuntimeError("보도중심선/도로중심선이 없습니다. config.LAYERS 확인")

    # ② 노딩: 모든 선을 하나로 합친 뒤 점 하나와 "합집합" 연산을 하면,
    #    GEOS(QGIS의 도형 엔진)가 선끼리 겹치는 모든 곳에서 선을 잘라 줍니다.
    log(f"  교차점 노딩 중 (선 {len(lines):,}개) - 데이터가 크면 몇 분 걸릴 수 있습니다")
    ml = ogr.Geometry(ogr.wkbMultiLineString)
    for a in lines:
        ls = ogr.Geometry(ogr.wkbLineString)
        for x, y in a:
            ls.AddPoint_2D(float(x), float(y))
        ml.AddGeometry(ls)
    pt = ogr.Geometry(ogr.wkbPoint)
    pt.AddPoint_2D(float(lines[0][0, 0]), float(lines[0][0, 1]))
    noded = ml.Union(pt)
    segs = [a for a in _line_arrays(noded) if len(a) >= 2]

    # ③ 30m 조각으로 나누기 ─────────────────────────────
    #    각 선을 따라 누적 거리를 구하고, 같은 간격의 지점을 보간(np.interp)해서 조각의 시작·끝·중간점을 구함
    X0, Y0, X1, Y1, XM, YM, LEN = [], [], [], [], [], [], []
    for a in segs:
        d = np.r_[0, np.cumsum(np.hypot(*np.diff(a, axis=0).T))]   # 선을 따라 간 누적 거리 [0, 12.3, 30.1, ...]
        L = d[-1]                                                  # 선 전체 길이
        if L < 0.05:
            continue                                               # 5cm 미만 찌꺼기는 버림
        n = max(1, int(np.ceil(L / C.SEG_LEN)))                    # 몇 조각으로 나눌지
        t = np.linspace(0, L, n + 1)                               # 자를 지점들의 누적거리 (등간격)
        tm = (t[:-1] + t[1:]) / 2                                  # 각 조각의 중간 지점
        xs, ys = np.interp(t, d, a[:, 0]), np.interp(t, d, a[:, 1])
        X0 += list(xs[:-1]); Y0 += list(ys[:-1]); X1 += list(xs[1:]); Y1 += list(ys[1:])
        XM += list(np.interp(tm, d, a[:, 0])); YM += list(np.interp(tm, d, a[:, 1])); LEN += [L / n] * n
    X0, Y0, X1, Y1, XM, YM, LEN = map(np.array, (X0, Y0, X1, Y1, XM, YM, LEN))
    m = len(LEN)
    log(f"  링크 {m:,}개 (평균 {LEN.mean():.1f}m)")
    is_stair = np.zeros(m, bool)
    flat = np.zeros(m, bool)

    # ④ 계단·교량·터널 표시 ─────────────────────────────
    stairs = polygons("stairs")
    sk = C.COL["stair_kind"]
    # 구조 코드가 "계단"(PGS001)이거나 비어 있는 것만 사용 (스탠드 등 제외)
    stairs = [(g, a) for g, a in stairs if str(a.get(sk, C.STAIR_CODE) or C.STAIR_CODE).upper() in (C.STAIR_CODE, "NONE", "")]
    crossed = set()                                   # 길이 지나가는 계단 번호 모음
    if stairs:
        ins, which = points_in_polygons(XM, YM, stairs)   # 링크 중간점이 계단 안에 있으면 계단 링크
        is_stair |= ins                                   # |= 는 "기존 값 OR 새 값" (배열 원소별)
        crossed = set(which[ins].tolist())
        log(f"  계단 {len(stairs):,}개 중 네트워크가 지나는 계단 {len(crossed):,}개, 계단 링크 {ins.sum():,}개")
    for key in ("bridge", "tunnel"):
        ps = polygons(key)
        if ps:
            flat |= points_in_polygons(XM, YM, ps)[0]      # 다리 위·터널 안은 DEM 이 땅 높이를 재서 틀리므로 경사 0
    log(f"  교량·터널 구간(경사 0 처리) {flat.sum():,}개")

    # ⑤ 노드 번호 붙이기 ─────────────────────────────────
    #    좌표를 SNAP_TOL(1m) 단위로 반올림 → 같은 값이면 같은 노드. np.unique 가 고유 번호를 매겨 줌
    q = C.SNAP_TOL
    keys = np.r_[np.c_[np.round(X0 / q), np.round(Y0 / q)], np.c_[np.round(X1 / q), np.round(Y1 / q)]].astype(np.int64)
    uniq, inv = np.unique(keys, axis=0, return_inverse=True)
    inv = inv.ravel()
    nodes_xy = uniq.astype(float) * q
    e = {"u": inv[:m], "v": inv[m:], "length": LEN, "is_stair": is_stair, "flat": flat, "xm": XM, "ym": YM,
         "kind": np.zeros(m, np.int8)}
    keep = e["u"] != e["v"]                         # 시작=끝인 0길이 링크 제거
    e = {k: v[keep] for k, v in e.items()}          # 딕셔너리 컴프리헨션 (JS의 Object.fromEntries(...map))

    def add(extra):
        """링크 목록(extra: 딕셔너리 리스트)을 e 뒤에 이어 붙임"""
        for k in e:
            e[k] = np.r_[e[k], np.array([x[k] for x in extra], dtype=e[k].dtype)]

    # ⑥ 길이 안 지나는 계단 → 계단의 긴 방향 양 끝을 가까운 노드와 연결 ──────
    idx = NearestIndex(nodes_xy)
    extra = []
    for k, (g, _) in enumerate(stairs):
        if k in crossed:
            continue
        ring = g.GetGeometryRef(0) if ogr.GT_Flatten(g.GetGeometryType()) == ogr.wkbPolygon else g.GetGeometryRef(0).GetGeometryRef(0)
        P = np.array(ring.GetPoints())[:, :2]          # 계단 테두리 꼭짓점들
        c = P.mean(axis=0)                             # 중심
        U, S, Vt = np.linalg.svd(P - c)                # 주성분 분석: 계단이 가장 길게 뻗은 방향 찾기
        ax = Vt[0]                                     # 긴 방향 단위벡터
        proj = (P - c) @ ax                            # 각 꼭짓점을 긴 방향 축에 투영 (@ = 행렬곱)
        a_, b_ = c + ax * proj.min(), c + ax * proj.max()   # 계단 아래 끝, 위 끝
        (da, db), (ia, ib) = idx.query(np.array([a_, b_]), C.STAIR_CONNECT_TOL)
        if ia >= 0 and ib >= 0 and ia != ib:          # 양 끝 모두 가까운 노드가 있고 서로 다른 노드면 연결
            extra.append(dict(u=ia, v=ib, length=float(np.linalg.norm(a_ - b_) + da + db), is_stair=True, flat=False,
                              xm=float(c[0]), ym=float(c[1]), kind=1))
    if extra:
        add(extra)
    log(f"  계단 연결 링크 추가 {len(extra):,}개")

    # ⑦ 막다른 점을 다른 길 덩어리에 연결 ─────────────────
    n = len(nodes_xy)
    lab = components(e["u"], e["v"], n)                  # 노드별 덩어리 번호
    deg = np.bincount(np.r_[e["u"], e["v"]], minlength=n) # 노드별 연결된 링크 수 (1 = 막다른 점)
    extra = []
    for i in np.where(deg == 1)[0]:
        for j in idx.within(nodes_xy[i], C.BRIDGE_TOL):   # 10m 안의 다른 노드들 중
            if lab[j] != lab[i]:                          # 다른 덩어리에 속한 첫 노드와 연결
                d = float(np.hypot(*(nodes_xy[i] - nodes_xy[j])))
                extra.append(dict(u=int(i), v=int(j), length=max(d, 0.5), is_stair=False, flat=False,
                                  xm=float(nodes_xy[i][0] + nodes_xy[j][0]) / 2, ym=float(nodes_xy[i][1] + nodes_xy[j][1]) / 2, kind=2))
                break
    if extra:
        add(extra)

    # ⑧ 가장 큰 덩어리만 남기기 ─────────────────────────
    lab = components(e["u"], e["v"], n)
    big = np.bincount(lab).argmax()                      # 노드가 가장 많은 덩어리 번호
    giant = lab == big
    log(f"  끊긴 끝점 연결 {len(extra):,}개 → 최대 연결망 노드 비율 {giant.mean():.1%}  (90% 이상이면 정상)")
    keep = giant[e["u"]]
    e = {k: v[keep] for k, v in e.items()}
    return nodes_xy, giant, e


def edge_slope(z, e):
    """노드 높이 배열 z → 링크별 경사 s = (끝 높이 - 시작 높이) ÷ 길이
    반환: (경사 배열, 비정상 경사였는지 배열). 교량·터널은 0, ±40% 초과는 잘라냄"""
    dz = z[e["v"]] - z[e["u"]]
    s = np.where(np.isnan(dz), 0.0, dz) / np.maximum(e["length"], 0.5)   # 높이 값이 없으면 경사 0
    s = np.where(e["flat"], 0.0, s)
    bad = np.abs(s) > C.SLOPE_CLIP
    return np.clip(s, -C.SLOPE_CLIP, C.SLOPE_CLIP), bad
