# -*- coding: utf-8 -*-
"""
lib/area.py ─ [v6] 구(자치구) 경계로 "어디를 계산하고 어디를 결과에 넣을지" 정하기

[쓰는 곳]
  setup.py  : 수치지형도 하위 폴더 중 대상 구·옆 구와 겹치는 폴더 고르기, AREA_BBOX 자동 결정
  check.py  : 대상 구가 모두 자료 범위 안에 있나, DEM 이 대상 범위를 덮나
  03_hbi.py : 출발점(집) 중 대상 구 안의 건물만 남기기 (옆 구 건물은 목적지·길로만)
[구 경계] external/dong_boundary.geojson (행정동 426개, 칸 sggnm = 구 이름. 없으면 adm_nm 의 두 번째 낱말)
"""
import os
import numpy as np
from osgeo import ogr
import config as C
from lib.qio import iter_layer, find_files

MARGIN = 1000          # 대상 범위 = (대상 구 + 옆 구) 를 감싸는 네모 + 1km
EXCEED_M = 2000        # 자료 범위가 대상 범위보다 한 변이라도 이만큼(2km) 넘게 크면 AREA_BBOX 로 좁힘


def boundary_file():
    bd = find_files(C.EXTERNAL, ["dong_boundary"], ".geojson") + find_files(C.EXTERNAL, ["dong_boundary"], ".shp")
    return bd[0] if bd else None


def dong_polys():
    """[(도형(분석 좌표계), 구 이름, 행정동 코드)] — 행정동 경계"""
    f = boundary_file()
    if not f:
        return []
    out = []
    for g, a in iter_layer(files=[f], bbox=False):
        up = {k.upper(): v for k, v in a.items()}
        gu = up.get("SGGNM") or up.get("SGG_NM") or ""
        if not gu and up.get("ADM_NM"):
            parts = str(up["ADM_NM"]).split()
            gu = parts[1] if len(parts) > 1 else ""
        code = str(up.get("ADM_CD") or up.get("ADM_DR_CD") or up.get("CODE") or "")
        out.append((g, str(gu), code))
    return out


def gu_polys(names=None):
    """{구 이름: 합친 도형}. names 가 있으면 그 구만"""
    out = {}
    for g, gu, _ in dong_polys():
        if names is not None and gu not in names:
            continue
        out[gu] = g.Clone() if gu not in out else out[gu].Union(g)
    return out


def bbox_of(geoms, margin=0.0):
    env = [g.GetEnvelope() for g in geoms]          # (x0, x1, y0, y1)
    if not env:
        return None
    return [min(e[0] for e in env) - margin, min(e[2] for e in env) - margin,
            max(e[1] for e in env) + margin, max(e[3] for e in env) + margin]


def target_range():
    """대상 범위 [x0, y0, x1, y1] = 대상 구 + 옆 구 를 감싸는 네모 + MARGIN. 대상 구가 비면 None"""
    if not C.TARGET_GU:
        return None
    gp = gu_polys(set(C.TARGET_GU) | set(C.NEIGHBOR_GU))
    return bbox_of(list(gp.values()), MARGIN) if gp else None


def rect(b):
    r = ogr.Geometry(ogr.wkbLinearRing)
    for x, y in [(b[0], b[1]), (b[2], b[1]), (b[2], b[3]), (b[0], b[3]), (b[0], b[1])]:
        r.AddPoint_2D(float(x), float(y))
    p = ogr.Geometry(ogr.wkbPolygon)
    p.AddGeometry(r)
    return p


def rects_union(bs):
    u = None
    for b in bs:
        u = rect(b) if u is None else u.Union(rect(b))
    return u


def overlap_gu(b, gp):
    """네모 범위 b 와 겹치는 구 이름 목록 (gp = gu_polys())"""
    r = rect(b)
    return [gu for gu, g in gp.items() if r.Intersects(g) and r.Intersection(g).GetArea() > 1.0]


def cover_share(gu_geom, envs):
    """구 면적 중 자료 범위(네모들의 합집합) 안에 드는 비율 0~1"""
    u = rects_union(envs)
    if u is None or gu_geom.GetArea() <= 0:
        return 0.0
    return float(gu_geom.Intersection(u).GetArea() / gu_geom.GetArea())


def decide_bbox(data_env, tr):
    """자료 범위 data_env 와 대상 범위 tr 로 AREA_BBOX 결정 → (값, 이유)"""
    if tr is None:
        return None, "대상 구가 비어 있어 자료 전체를 계산"
    if data_env is None:
        return None, "자료 범위를 읽지 못해 전체를 계산"
    over = max(tr[0] - data_env[0], tr[1] - data_env[1], data_env[2] - tr[2], data_env[3] - tr[3])
    if over >= EXCEED_M:
        b = [int(np.floor(tr[0] / 100) * 100), int(np.floor(tr[1] / 100) * 100), int(np.ceil(tr[2] / 100) * 100), int(np.ceil(tr[3] / 100) * 100)]
        return b, f"자료가 대상 범위(대상 구·옆 구 + {MARGIN // 1000}km)보다 최대 {over / 1000:.1f}km 넓어 대상 범위로 좁힘"
    return None, "자료가 대상 범위 안쪽(넘는 폭 2km 미만)이라 좁히지 않음"


def gu_of_points(xs, ys):
    """점마다 구 이름 배열 ('' = 어느 행정동에도 안 듦)"""
    from lib.qnetwork import points_in_polygons
    polys = dong_polys()
    out = np.full(len(xs), "", dtype=object)
    if not polys or len(xs) == 0:
        return out
    x0, x1, y0, y1 = np.min(xs), np.max(xs), np.min(ys), np.max(ys)
    polys = [p for p in polys if not (p[0].GetEnvelope()[1] < x0 or p[0].GetEnvelope()[0] > x1 or
                                      p[0].GetEnvelope()[3] < y0 or p[0].GetEnvelope()[2] > y1)]
    _, which = points_in_polygons(np.asarray(xs, float), np.asarray(ys, float), [(g, None) for g, _, _ in polys])
    ok = which >= 0
    out[ok] = np.array([polys[k][1] for k in which[ok]], dtype=object)
    return out


def in_target(xs, ys):
    """대상 구 안의 점이면 True. 대상 구가 비어 있으면 모두 True (v5 와 같음)"""
    if not C.TARGET_GU:
        return np.ones(len(xs), bool)
    if not boundary_file():
        from lib.qio import log
        log("  !! external/dong_boundary.geojson 이 없어 대상 구로 거르지 못함 → 자료 전체를 결과에 넣음")
        return np.ones(len(xs), bool)
    g = gu_of_points(xs, ys)
    return np.isin(g, list(C.TARGET_GU))
