# -*- coding: utf-8 -*-
"""
lib/qnetwork.py ─ 수치지형도로 "걸어 다닐 수 있는 길 네트워크"를 만드는 파일

[전체 흐름]  (02_network.py 가 build_edges() 를 호출)
 ① 보도중심선 + 도로중심선의 선들을 모두 읽음
    [v6.1] 도로중심선 중 걸을 수 없는 길(도로구분 고속국도, 자동차전용 도로)은 표시해 둠 (mapping.txt 의 walk_exclude_*)
 ② 선끼리 교차하는 모든 지점에서 선을 자름 (노딩) → 교차로마다 노드가 생김
    [v6.1] 잘린 조각 중 걸을 수 없는 길 위의 조각은 ⑤ 다음에 뺌 (뺀 것과 안 뺀 것 두 네트워크를 같은 노드로 만들어 04 가 비교)
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
from collections import Counter
import numpy as np
from osgeo import ogr
import config as C
from lib.qio import log, iter_layer, value_shape
from lib.qgraph import NearestIndex, components
from lib import codebook as K

ROAD = "N3L_A0020000"                                   # 정의서의 도로중심선 레이어 코드
WALK_FIELDS = {"road_kind": "ROAD_SE", "road_mtrwy": "MTRWY_SE"}   # mapping 키 → 정의서 필드 코드 (도로구분, 자동차전용)
LAST = {}                                               # [v6.1] 마지막 build_edges 의 덧붙은 결과 (02 가 저장): walkall, walk


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


def polygons(key, fields=None):
    """config.LAYERS[key] 레이어에서 면(폴리곤) 도형만 골라 [(도형, 속성), ...] 로 반환. [v6] fields = 읽을 칸 (대소문자 무시)"""
    out = []
    for g, a in iter_layer(key, fields=fields):
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


def walk_rule():
    """[v6.1] 걸을 수 없는 길 기준 → {mapping 키: (실제 칸 이름, 정의서 필드 코드, 뺄 코드 집합)}.
    칸 이름이 없거나(?) 뺄 값이 비어 있으면 그 키는 빠짐 → 아무것도 안 빼면 v5 와 같은 네트워크"""
    out = {}
    for k, fc in WALK_FIELDS.items():
        col = C.COL.get(k)
        ex = {K.to_code(ROAD, fc, v) for v in getattr(C, "WALK_EXCLUDE", {}).get(k, [])} - {""}
        if col and ex:
            out[k] = (col, fc, ex)
    return out


def _midpoints(segs):
    """선 조각마다 길이의 절반 지점 좌표 [[x, y], ...]"""
    out = np.empty((len(segs), 2))
    for i, a in enumerate(segs):
        d = np.r_[0, np.cumsum(np.hypot(*np.diff(a, axis=0).T))]
        out[i] = np.interp(d[-1] / 2, d, a[:, 0]), np.interp(d[-1] / 2, d, a[:, 1])
    return out


def on_lines(pts, xl, q=1.0, tol=0.05):
    """[v6.1] 점들(pts)이 선 목록 xl 위(tol = 5cm 안)에 있는지 (True/False 배열).
    ① 선을 q(1m) 간격 점으로 찍어 q 칸 번호(주변 9칸 포함)로 후보를 빠르게 고르고 (numpy)
    ② 후보 점만 그 칸을 지나는 선까지 실제 거리로 확인 (OGR). 노딩된 조각은 원래 선 위에 있으므로 거리가 거의 0"""
    pts = np.asarray(pts, float).reshape(-1, 2)
    out = np.zeros(len(pts), bool)
    if not xl or not len(pts):
        return out
    P, ids = [], []
    for j, a in enumerate(xl):
        d = np.r_[0, np.cumsum(np.hypot(*np.diff(a, axis=0).T))]
        t = np.r_[np.arange(0, d[-1], q), d[-1]]
        P.append(np.c_[np.interp(t, d, a[:, 0]), np.interp(t, d, a[:, 1])])
        ids.append(np.full(len(t), j, np.int32))
    P = np.floor(np.concatenate(P) / q).astype(np.int64)
    S = 10**8                                           # (칸x, 칸y) → 숫자 하나 (칸y < 1억)
    kk = np.concatenate([(P[:, 0] + dx) * S + (P[:, 1] + dy) for dx in (-1, 0, 1) for dy in (-1, 0, 1)])
    ii = np.tile(np.concatenate(ids), 9)
    order = np.argsort(kk, kind="stable")
    kk, ii = kk[order], ii[order]
    k = np.floor(pts / q).astype(np.int64)
    key = k[:, 0] * S + k[:, 1]
    lo, hi = np.searchsorted(kk, key, "left"), np.searchsorted(kk, key, "right")
    geo = {}
    for i in np.where(hi > lo)[0]:
        p = ogr.Geometry(ogr.wkbPoint)
        p.AddPoint_2D(float(pts[i, 0]), float(pts[i, 1]))
        for j in np.unique(ii[lo[i]:hi[i]]):
            if j not in geo:
                ls = ogr.Geometry(ogr.wkbLineString)
                for x, y in xl[j]:
                    ls.AddPoint_2D(float(x), float(y))
                geo[j] = ls
            if geo[j].Distance(p) <= tol:
                out[i] = True
                break
    return out


def build_edges():
    log("보행 네트워크 구축")

    # ① 선 읽기 ─────────────────────────────────────────
    lines, excl = [], []                                # excl[i] = i번째 선이 걸을 수 없는 길인지 [v6.1]
    rule = walk_rule()
    seen = {k: Counter() for k in rule}                 # 칸별 값 개수 (화면에 보여 값 형식을 확인하게)
    for key in ("sidewalk_cl", "road_cl"):
        n0 = len(lines)
        flds = [c for c, _, _ in rule.values()] if key == "road_cl" else []
        for g, a in iter_layer(key, fields=flds):
            arrs = _line_arrays(g)
            x = False
            for k, (col, fc, ex) in (rule.items() if key == "road_cl" else ()):
                v = K.to_code(ROAD, fc, a.get(col))     # 코드(RDC001)든 코드명(고속국도)이든 코드로 맞춤
                seen[k][v] += 1
                x = x or v in ex
            lines += arrs
            excl += [x] * len(arrs)
        nk = len(lines) - n0
        log(f"  {key}: 선 {nk:,}개")                    # {숫자:,} 는 천 단위 콤마 (1,234)
    if not lines:
        raise RuntimeError("보도중심선/도로중심선이 없습니다. config.LAYERS 확인")
    for k, (col, fc, ex) in rule.items():
        known = K.codes(ROAD, fc)
        nm = K.field_names(ROAD).get(fc, fc)
        if not any(v for v in seen[k]):
            log(f"  {nm} 칸({col})이 비었거나 없음 → 이 기준으로는 빼지 않음")
            continue
        cnt = Counter()
        odd = Counter()
        for v, n in seen[k].items():
            if v in known:
                cnt[f"{v} {known[v]}"] += n
            elif not v:
                cnt["(빈 값)"] += n
            else:
                cnt["(정의서에 없는 값)"] += n
                odd[value_shape(v)] += n                # 값 대신 글자 모양만 (예: Y → A)
        log(f"  {nm}({col}) 값: " + ", ".join(f"{t} {n:,}" for t, n in cnt.most_common(8)) + f"  ← 뺄 값 {', '.join(sorted(ex))}")
        if odd:
            log(f"  ▲ {nm} 칸에 정의서 코드·코드명이 아닌 값이 있음 (글자 모양: " + ", ".join(f"'{sh}' {n:,}" for sh, n in odd.most_common(4))
                + f") → 걸을 수 없는 값이면 mapping.txt 의 walk_exclude_{k[5:]} 줄에 그 값을 쉼표로 더하고 python run_all.py --from 02")
    nx = int(np.sum(excl))
    if rule:
        log(f"  걸을 수 없는 길(뺄 선): 도로중심선 선 {nk:,}개 중 {nx:,}개 ({nx / max(nk, 1):.1%})")

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
    # ②-1 [v6.1] 걸을 수 없는 길 위의 조각: 노딩으로 잘린 조각의 가운데 점이 뺄 선 위(5cm 안)에 있으면 뺄 조각.
    #      노딩이 모든 교차점에서 자르므로 한 조각은 선 하나에서만 나옴 (뺄 선과 건널목처럼 만나는 길은 교차점에서 갈라짐)
    xl = [a for a, x in zip(lines, excl) if x]
    seg_x = on_lines(_midpoints(segs), xl) if xl else np.zeros(len(segs), bool)

    # ③ 30m 조각으로 나누기 ─────────────────────────────
    #    각 선을 따라 누적 거리를 구하고, 같은 간격의 지점을 보간(np.interp)해서 조각의 시작·끝·중간점을 구함
    X0, Y0, X1, Y1, XM, YM, LEN, WALK = [], [], [], [], [], [], [], []
    for a, sx in zip(segs, seg_x):
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
        WALK += [not sx] * n
    X0, Y0, X1, Y1, XM, YM, LEN = map(np.array, (X0, Y0, X1, Y1, XM, YM, LEN))
    WALK = np.array(WALK, bool)
    m = len(LEN)
    log(f"  링크 {m:,}개 (평균 {LEN.mean():.1f}m)")
    is_stair = np.zeros(m, bool)
    flat = np.zeros(m, bool)

    # ④ 계단·교량·터널 표시 ─────────────────────────────
    sk = C.COL["stair_kind"]
    stairs = polygons("stairs", [sk] if sk else [])            # [v6] 구조 칸 이름은 mapping 의 stair_kind (대소문자 무시)
    # 구조 코드가 "계단"(PGS001)이거나 비어 있는 것만 사용 (스탠드 등 제외). [v6.1] 값이 코드명("계단")이어도 코드로 맞춰 비교
    stairs = [(g, a) for g, a in stairs if K.to_code("N3A_C0390000", "ARSFCKD_SE", a.get(sk, C.STAIR_CODE) or C.STAIR_CODE)
              in (C.STAIR_CODE, "NONE", "")]
    crossed, crossed_w = set(), set()                 # 길이 지나가는 계단 번호 모음 (전체 / 걸을 수 있는 길만 [v6.1])
    if stairs:
        ins, which = points_in_polygons(XM, YM, stairs)   # 링크 중간점이 계단 안에 있으면 계단 링크
        is_stair |= ins                                   # |= 는 "기존 값 OR 새 값" (배열 원소별)
        crossed = set(which[ins].tolist())
        crossed_w = set(which[ins & WALK].tolist())
        log(f"  계단 {len(stairs):,}개 중 네트워크가 지나는 계단 {len(crossed):,}개, 계단 링크 {ins.sum():,}개")
    for key in ("bridge", "tunnel"):
        ps = polygons(key, [])
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
    walk = WALK[keep]
    LAST.clear()
    if walk.all():                                  # 뺄 길이 없음 → v5 와 똑같은 과정
        giant, e = _finish(nodes_xy, e, stairs, crossed)
        LAST["walk"] = {"lines": nx, "links": 0, "rule": bool(rule)}
        return nodes_xy, giant, e

    # [v6.1] 뺄 길이 있음: 걸을 수 있는 길만으로 ⑥~⑧ (= 결과에 쓰는 네트워크) + 비교용으로 v5 방식(빼지 않음)도 ⑥~⑧
    ew = {k: v[walk] for k, v in e.items()}
    use = np.zeros(len(nodes_xy), bool)
    use[ew["u"]] = True
    use[ew["v"]] = True                              # 걸을 수 있는 길이 닿는 노드만 계단·끊김 연결에 씀
    log(f"  걸을 수 없는 길 링크 {int((~walk).sum()):,}개를 뺌 (전체 {len(walk):,}개의 {(~walk).mean():.1%}, "
        f"선 {nx:,}개) — 비교용으로 빼지 않은 네트워크(v5 방식)도 함께 만듦")
    ga, ea = _finish(nodes_xy, e, stairs, crossed, quiet=True)
    giant, e = _finish(nodes_xy, ew, stairs, crossed_w, sub=np.where(use)[0])
    log(f"  남긴 링크: 빼기 전(v5 방식) {len(ea['u']):,}개 (노드 비율 {ga.mean():.1%}) → 뺀 뒤 {len(e['u']):,}개 (노드 비율 {giant[use].mean():.1%})")
    LAST["walkall"] = {"giant": ga, "e": ea}
    LAST["node_use"] = use
    LAST["walk"] = {"lines": nx, "links": int((~walk).sum()), "rule": True}
    return nodes_xy, giant, e


def _finish(nodes_xy, e, stairs, crossed, sub=None, quiet=False):
    """⑥~⑧ (계단 연결, 끊긴 끝 연결, 큰 덩어리만 남기기). 반환: (giant, e)
    sub   : [v6.1] 계단·끊김 연결에 쓸 노드 번호 (None 이면 전부 = v5 와 같음)
    quiet : 화면에 안 적음 (비교용 네트워크)"""
    say = (lambda *_: None) if quiet else log
    e = dict(e)

    def add(extra):
        """링크 목록(extra: 딕셔너리 리스트)을 e 뒤에 이어 붙임"""
        for k in e:
            e[k] = np.r_[e[k], np.array([x[k] for x in extra], dtype=e[k].dtype)]

    # ⑥ 길이 안 지나는 계단 → 계단의 긴 방향 양 끝을 가까운 노드와 연결 ──────
    if sub is None:
        idx, back = NearestIndex(nodes_xy), None
    else:                                          # 색인은 쓸 노드만, 찾은 번호는 전체 노드 번호로 되돌림
        idx, back = NearestIndex(nodes_xy[sub]), np.asarray(sub)
    full = (lambda i: i) if back is None else (lambda i: int(back[i]) if i >= 0 else -1)
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
        ia, ib = full(ia), full(ib)
        if ia >= 0 and ib >= 0 and ia != ib:          # 양 끝 모두 가까운 노드가 있고 서로 다른 노드면 연결
            extra.append(dict(u=ia, v=ib, length=float(np.linalg.norm(a_ - b_) + da + db), is_stair=True, flat=False,
                              xm=float(c[0]), ym=float(c[1]), kind=1))
    if extra:
        add(extra)
    say(f"  계단 연결 링크 추가 {len(extra):,}개")

    # ⑦ 막다른 점을 다른 길 덩어리에 연결 ─────────────────
    n = len(nodes_xy)
    lab = components(e["u"], e["v"], n)                  # 노드별 덩어리 번호
    deg = np.bincount(np.r_[e["u"], e["v"]], minlength=n) # 노드별 연결된 링크 수 (1 = 막다른 점)
    extra = []
    for i in np.where(deg == 1)[0]:
        for j in idx.within(nodes_xy[i], C.BRIDGE_TOL):   # 10m 안의 다른 노드들 중
            j = full(j)
            if lab[j] != lab[i]:                          # 다른 덩어리에 속한 첫 노드와 연결
                d = float(np.hypot(*(nodes_xy[i] - nodes_xy[j])))
                extra.append(dict(u=int(i), v=int(j), length=max(d, 0.5), is_stair=False, flat=False,
                                  xm=float(nodes_xy[i][0] + nodes_xy[j][0]) / 2, ym=float(nodes_xy[i][1] + nodes_xy[j][1]) / 2, kind=2))
                break
    if extra:
        add(extra)

    # ⑧ 큰 덩어리만 남기기 ─────────────────────────────
    #    [v5] 대상 구들이 서로 떨어져 있으면(예: 종로·중 / 관악 / 광진 / 강서) 구마다 큰 덩어리가 하나씩 생김.
    #    v4 는 "가장 큰 덩어리 하나"만 남겨 나머지 구가 통째로 빠졌음 → 가장 큰 것의 KEEP_NET_SHARE(5%) 이상인 덩어리는 모두 남김.
    #    그보다 작은 조각(주차장 안 길, 끊긴 골목 등)은 예전처럼 버림
    lab = components(e["u"], e["v"], n)
    cnt = np.bincount(lab)
    big = np.where(cnt >= C.KEEP_NET_SHARE * cnt.max())[0]   # 남길 덩어리 번호들
    giant = np.isin(lab, big)                                # (이름은 v4 와 같게 giant: "남기는 노드" 표시)
    share = giant.mean() if sub is None else giant[sub].mean()   # [v6.1] 노드 비율은 쓸 수 있는 노드 중에서
    say(f"  끊긴 끝점 연결 {len(extra):,}개 → 남긴 연결망 {len(big)}개 (노드 수 {sorted(cnt[big].tolist(), reverse=True)}), "
        f"노드 비율 {share:.1%}  (90% 이상이면 정상. 떨어진 구 수만큼 연결망이 나오는 것이 정상)")
    keep = giant[e["u"]]
    e = {k: v[keep] for k, v in e.items()}
    return giant, e


def edge_slope(z, e):
    """노드 높이 배열 z → 링크별 경사 s = (끝 높이 - 시작 높이) ÷ 길이
    반환: (경사 배열, 비정상 경사였는지 배열). 교량·터널은 0, ±40% 초과는 잘라냄"""
    dz = z[e["v"]] - z[e["u"]]
    s = np.where(np.isnan(dz), 0.0, dz) / np.maximum(e["length"], 0.5)   # 높이 값이 없으면 경사 0
    s = np.where(e["flat"], 0.0, s)
    bad = np.abs(s) > C.SLOPE_CLIP
    return np.clip(s, -C.SLOPE_CLIP, C.SLOPE_CLIP), bad
