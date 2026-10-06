# -*- coding: utf-8 -*-
"""
14_dong_context.py ─ [v5] 행정동별 "동네 성격" 변수 (외출 지수와 HBI 를 비교할 때 상권·시설 효과를 통제하려고)

[실행]  python 14_dong_context.py      (run_all.py 가 끝난 뒤 한 줄 따로. 02·03(·10)의 결과를 읽기만 함)
[하는 일]
  1. 수치지형도 건물을 모두 읽어 행정동별로 셈: 건물 수, 용도별 수·연면적 비율, 평균 층수
       용도 분류는 아래 USE_CLASS 표 (건물 용도 BPRP_SE 코드, 수치지형도 데이터정의서 별표)
  2. 역(정거장)·버스정류장 수, 보행 링크 밀도 (행정동 안 링크 길이 km ÷ 행정동 면적 km²)
  3. [SKT 경로가 config.POINT_DATA 에 있을 때만] SKT 50m 셀을 10_points_join.py 와 같은 규칙으로 읽어서
       - 모든 셀 합계 (skt_all_sum) : 10 의 행정동 합과 같아야 함 (화면에서 대조 = 가드)
       - "주거 칸" 합계 (skt_res_sum): 셀 중심 25m 안에 주거 건물이 있고, 근린생활·상업 건물이 없는 셀만
     → 상점가를 지나가는 사람을 빼고 "집 근처에서 움직이는 사람" 만 보려는 것
  JS로 치면: 건물 배열을 행정동별로 groupBy 해서 용도별 count·sum 을 구하고, 셀도 조건으로 filter 한 뒤 합치는 것
[결과] (output/ → 반출 대상. 기획서 19장 통제 변수)
  dong_context.csv : 행정동(건물 MIN_COUNT 개 이상)마다
      adm_cd, n_bld_all, n_share_<용도>, w_share_<용도>(연면적 비율), mean_floors, n_station, n_bus_stop, link_km_per_km2,
      skt_res_sum, skt_all_sum, n_cells_res, n_cells_all (SKT 가 없으면 빈 칸)
  개별 건물·셀 좌표는 저장하지 않습니다.
[결과 보는 법]
  - n_share_·w_share_ 는 각각 더하면 1.0
  - 화면의 "SKT 대조" 가 "같음" 이 아니면 10 과 읽는 규칙이 어긋난 것 → 멈추고 확인
  - 링크 밀도는 받은 지도 범위 밖으로 걸친 동에서 작게 나옴 (동 면적 전체로 나누므로)
"""
import os, numpy as np
np.seterr(invalid="ignore", divide="ignore")
from osgeo import ogr
import config as C
from lib.qio import log, read_csv, write_csv, find_files, iter_layer, transform_xy, transformer, read_any
from lib.qgraph import NearestIndex
from lib.qnetwork import points_in_polygons
from lib.netload import load
from lib.bload import load_buildings, usable
from lib.battr import iter_buildings

# ── 이 스크립트만의 설정 (config.py 는 바꾸지 않음) ─────────────
# 건물 용도 코드 → 분류 (수치지형도 데이터정의서 별표, BPRP_SE "용도 구분코드")
#   BDU001 주거용단독주택, BDU002 주거용공동주택, BDU003 제1종근린생활시설, BDU004 제2종근린생활시설,
#   BDU007 판매시설, BDU009 의료시설, BDU011 노유자(노인및어린이)시설, 그 밖의 BDU0xx·BDU999 = 기타
USE_CLASS = {
    "주거": ["BDU001", "BDU002"],
    "근린상업": ["BDU003", "BDU004", "BDU007"],
    "의료": ["BDU009"],
    "노유자": ["BDU011"],
}
ORDER = ["주거", "근린상업", "의료", "노유자", "기타"]
LOOKUP = {c: k for k, cs in USE_CLASS.items() for c in cs}
RES_CELL_M = 25        # SKT 셀 중심에서 이 거리 안에 주거 건물이 있고 근린·상업 건물이 없으면 "주거 칸"

os.makedirs(C.OUTPUT, exist_ok=True)


def fnum(v):
    try:
        return float(str(v).replace(",", "").strip())
    except ValueError:
        return np.nan


# ── 1. 건물 (전체 용도) ────────────────────────────────────
BX, BY, BC, BF, BW = [], [], [], [], []
for g, a in iter_buildings():                    # [v6] 용도·층수는 mapping 의 building_attr_mode 대로 (03 과 같은 lib/battr.py)
    p = g.PointOnSurface()
    if p is None:
        continue
    use = a["use"]
    kind = a["kind"]
    cls = LOOKUP.get(use, "기타")
    if cls == "기타" and not use.startswith("BDU") and kind in C.RESIDENTIAL_KIND:   # 03_hbi.py 와 같은 규칙: 용도가 비고 종류가 주택이면 주거
        cls = "주거"
    try:
        fl = min(max(float(a["floor"] or 1), 1), 60)
    except (TypeError, ValueError):
        fl = 1.0
    BX.append(p.GetX()); BY.append(p.GetY()); BC.append(cls); BF.append(fl); BW.append(fl * g.GetArea())
BX, BY, BF, BW = map(lambda x: np.array(x, float), (BX, BY, BF, BW))
BC = np.array(BC)
log(f"건물 {len(BX):,}개: " + ", ".join(f"{k} {int((BC == k).sum()):,}" for k in ORDER))

# ── 2. 행정동 경계 (10_points_join.py 와 같은 방식) ─────────────
b = load_buildings()
v = np.isfinite(b["medical_hbi"] if "medical_hbi" in b else b[[k for k in b if k.endswith("_hbi")][0]]) & usable(b)
bx0, bx1, by0, by1 = np.nanmin(b["x"][v]), np.nanmax(b["x"][v]), np.nanmin(b["y"][v]), np.nanmax(b["y"][v])   # 분석 범위 (10 과 같음)
bd = find_files(C.EXTERNAL, ["dong_boundary"], ".geojson") + find_files(C.EXTERNAL, ["dong_boundary"], ".shp")
if not bd:
    raise SystemExit("external/dong_boundary 가 없습니다 → 건너뜀")
polys = [(g, a) for g, a in iter_layer(files=bd[:1], bbox=None)]
ck_ = next(k for k in polys[0][1] if k.upper() in ("ADM_CD", "ADM_DR_CD", "ADSTRD_CD", "CODE"))
polys = [p for p in polys if not (p[0].GetEnvelope()[1] < bx0 or p[0].GetEnvelope()[0] > bx1 or
                                  p[0].GetEnvelope()[3] < by0 or p[0].GetEnvelope()[2] > by1)]
if C.TARGET_GU:                                  # [v6] 결과는 대상 구의 행정동만 (옆 구는 길·목적지로만 씀)
    gk_ = next((k for k in polys[0][1] if k.upper() in ("SGGNM", "SGG_NM")), None) if polys else None
    an_ = next((k for k in polys[0][1] if k.upper() == "ADM_NM"), None) if polys else None
    gu_ = lambda a: str(a.get(gk_) or "") if gk_ else (str(a.get(an_) or "").split()[1:2] or [""])[0]
    polys = [p for p in polys if gu_(p[1]) in C.TARGET_GU]
dcode = [str(a[ck_]) for _, a in polys]
_, bwhich = points_in_polygons(BX, BY, polys)

# 역·정류장, 링크
def points_of(key):
    xs, ys = [], []
    for g, _ in iter_layer(key):
        p = g if g.GetGeometryName() == "POINT" else g.PointOnSurface()
        if p is not None:
            xs.append(p.GetX()); ys.append(p.GetY())
    return np.array(xs, float), np.array(ys, float)
sx, sy = points_of("station")
ux, uy = points_of("bus_stop")
_, swhich = points_in_polygons(sx, sy, polys) if len(sx) else (None, np.array([], int))
_, uwhich = points_in_polygons(ux, uy, polys) if len(ux) else (None, np.array([], int))
net = load()
e = net["e"]
_, lwhich = points_in_polygons(e["xm"], e["ym"], polys)          # 링크 가운데점이 든 동
log(f"역 {len(sx):,}개, 버스정류장 {len(ux):,}개, 링크 {len(e['xm']):,}개")

# ── 3. SKT (10_points_join.py 와 같은 입력·같은 합산 규칙) ───────
skt = None
cands = [(k, c) for k, c in C.POINT_DATA.items() if c.get("path") and "SKT" in k.upper() and c.get("agg") == "sum" and c.get("value_cols")]
cands.sort(key=lambda kc: ("60" not in kc[0], kc[0]))            # 60대 이상 자료 우선
if cands:
    name, cfg = cands[0]
    rows, enc, sep = read_any(cfg["path"], cfg.get("sep"))
    for col, val in (cfg.get("filter") or {}).items():
        ok = set(str(x).strip().upper() for x in (val if isinstance(val, (list, tuple)) else [val]))   # [v6] 10 과 같게 대소문자 무시
        rows = [r for r in rows if str(r.get(col, "")).strip().upper() in ok]
    for col, txt in (cfg.get("contains") or {}).items():
        rows = [r for r in rows if str(txt).upper() in str(r.get(col, "")).upper()]
    xy = np.array([(fnum(r.get(cfg["x_col"])), fnum(r.get(cfg["y_col"]))) for r in rows], float).reshape(-1, 2)
    val = np.array([np.nansum([fnum(r.get(c)) for c in cfg["value_cols"]]) for r in rows], float)
    pc = cfg.get("period_col")
    val = val / max(len({r.get(pc) for r in rows}) if pc else 1, 1)
    okm = np.isfinite(xy).all(axis=1)
    xy, val = xy[okm], val[okm]
    px, py = transform_xy(transformer(cfg.get("crs") or "EPSG:4326"), xy[:, 0], xy[:, 1]) if len(xy) else (np.array([]), np.array([]))
    inb = (px >= bx0) & (px <= bx1) & (py >= by0) & (py <= by1)
    px, py, val = px[inb], py[inb], val[inb]
    _, pwhich = points_in_polygons(px, py, polys)
    res_i, com_i = np.where(BC == "주거")[0], np.where(BC == "근린상업")[0]
    # [v6] 찾는 거리를 RES_CELL_M 의 2배로 묶음 (판정에는 25m 안만 씀 → 결과 같음. scipy 없을 때 먼 셀에서 수 km 를 뒤지던 것을 막음)
    near = lambda ids: (NearestIndex(np.c_[BX[ids], BY[ids]]).query(np.c_[px, py], RES_CELL_M * 2)[0] if len(ids) else np.full(len(px), np.inf))
    is_res = (near(res_i) <= RES_CELL_M) & ~(near(com_i) <= RES_CELL_M)
    skt = (name, pwhich, val, is_res)
    log(f"SKT {name}: 범위 안 셀 {len(px):,}개 중 주거 칸 {int(is_res.sum()):,}개 (셀 중심 {RES_CELL_M}m 안 주거 있음·근린상업 없음)")
else:
    log("config.POINT_DATA 에 SKT 경로가 없어 SKT 열은 빈 칸")

# ── 4. 행정동별로 모으기 ────────────────────────────────────
out, check = [], []
for k, code in enumerate(dcode):
    m = bwhich == k
    n = int(m.sum())
    if n < C.MIN_COUNT:
        continue
    area_km2 = polys[k][0].GetArea() / 1e6
    ns = [round(float((BC[m] == c).sum()) / n, 4) for c in ORDER]
    wt = BW[m].sum()
    ws = [round(float(BW[m][BC[m] == c].sum() / wt), 4) if wt > 0 else "" for c in ORDER]
    link_km = float(e["length"][lwhich == k].sum()) / 1000
    row = [code, n] + ns + ws + [round(float(BF[m].mean()), 2), int((swhich == k).sum()), int((uwhich == k).sum()),
                                  round(link_km / area_km2, 2) if area_km2 > 0 else ""]
    if skt:
        _, pw, val, isr = skt
        pm = pw == k
        row += [round(float(val[pm & isr].sum()), 2), round(float(val[pm].sum()), 2), int((pm & isr).sum()), int(pm.sum())]
        check.append((code, float(val[pm].sum())))
    else:
        row += ["", "", "", ""]
    out.append(row)
head = (["adm_cd", "n_bld_all"] + [f"n_share_{c}" for c in ORDER] + [f"w_share_{c}" for c in ORDER]
        + ["mean_floors", "n_station", "n_bus_stop", "link_km_per_km2", "skt_res_sum", "skt_all_sum", "n_cells_res", "n_cells_all"])
write_csv(os.path.join(C.OUTPUT, "dong_context.csv"), head, out)

# ── 5. 가드: skt_all_sum 이 10 의 행정동 합과 같은가 ────────────
if skt:
    ten = {r["adm_cd"]: fnum(r.get("n_points")) for r in (read_csv(os.path.join(C.OUTPUT, f"points_{skt[0]}_dong.csv")) or [])}
    if not ten:
        log(f"  SKT 대조: output/points_{skt[0]}_dong.csv 가 없어 대조 못 함 (10_points_join.py 먼저)")
    else:
        common = [(c, s) for c, s in check if c in ten]
        bad = [(c, s, ten[c]) for c, s in common if abs(round(s, 2) - ten[c]) > 0.011]
        log(f"  SKT 대조: 10 과 같은 행정동 {len(common)}곳 중 " + ("모두 같음" if not bad else f"!! {len(bad)}곳 다름 {bad[:3]} → 읽는 규칙 확인"))
log(f"완료 → output/dong_context.csv ({len(out)}행, 건물·셀 좌표는 저장하지 않음)")
