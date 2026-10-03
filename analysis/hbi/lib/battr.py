# -*- coding: utf-8 -*-
"""
lib/battr.py ─ [v6] 건물마다 "용도·종류·층수" 를 어디서 가져올지 (mapping.txt 의 building_attr_mode)

[왜] 1차 방문(10/2)에서 받은 건물 레이어(N3A_B0010000)에 UFID 칸 하나뿐이라 용도·층수가 없었음
     → 03 이 "주거 0개" 로 멈춤. v6 는 용도 칸이 없으면 다른 길로 용도를 붙입니다.
[방식]
  layer    : 건물 레이어의 칸 (bld_use·bld_kind·bld_floor). v5 와 똑같음
  register : 건물 → (건물 안쪽 대표점이 들어가는) 필지 → 건축물대장
               ① 필지에 건축물대장 번호 칸(parcel_bldrgst)이 있고 대장에 그 번호가 있으면 그 행
               ② 없으면 필지 고유번호(pnu) 로 대장 행들
             한 필지에 대장 행이 여럿이면: 주건축물 행 우선, 그중 연면적이 가장 큰 행의 용도. 층수는 행들 중 최대
             연결률(용도가 붙은 건물 비율)을 화면에 찍고 work/battr_stats.json 에 저장
  all      : 모든 건물을 집으로 봄 (용도 미구분). 의료·노유자 "건물" 목적지는 없음 (약국 등 다른 목적지만)
  stop     : 멈춤
[돌려주는 모양]  for g, a in iter_buildings():   a = {"use": 용도 코드(대문자), "kind": 종류 코드, "floor": 층수(원래 값)}
  → 03·14 는 v5 와 같은 규칙(config.RESIDENTIAL_USE 등)으로 집·의료·노유자를 가름. 대장 용도는 아래 REG_TO_USE 로
    수치지형도 용도 코드(데이터정의서 별표 BPRP_SE)에 맞춰 바꿈
[읽는 필지 칸] 고유번호·건축물대장 번호뿐 (소유·공시지가는 읽지 않음)
"""
import os, json, collections
import numpy as np
from osgeo import ogr
import config as C
from lib.qio import log, iter_layer, find_files, read_any

# 건축물대장 주용도 → 수치지형도 건물 용도 코드 (BPRP_SE, 데이터정의서 별표: BDU001 주거용단독주택, BDU002 주거용공동주택,
#   BDU003 제1종근린생활시설, BDU004 제2종근린생활시설, BDU007 판매시설, BDU009 의료시설, BDU011 노유자시설)
#   names: 대장의 주용도 이름 (건축법 시행령 별표1 용도 이름. 다가구주택은 단독주택의 한 종류)
#   codes: 대장의 주용도 코드 앞 두 자리 (같은 별표1 순번: 01 단독주택, 02 공동주택, 03·04 근린생활, 07 판매, 09 의료, 11 노유자)
REG_TO_USE = [
    ("BDU001", ["단독주택", "다가구주택", "다중주택"], ["01"]),
    ("BDU002", ["공동주택", "아파트", "연립주택", "다세대주택"], ["02"]),
    ("BDU003", ["제1종근린생활시설"], ["03"]),
    ("BDU004", ["제2종근린생활시설"], ["04"]),
    ("BDU007", ["판매시설"], ["07"]),
    ("BDU009", ["의료시설"], ["09"]),
    ("BDU011", ["노유자시설"], ["11"]),
]
REG_OTHER = "기타"        # 위에 없는 용도 (집도 목적지도 아님)
MAIN_WORDS = ("주", "주건축물", "1", "MAIN")
STATS_FILE = os.path.join(C.WORK, "battr_stats.json")


def mode():
    m = getattr(C, "BUILDING_ATTR_MODE", "layer") or "layer"
    if m not in ("layer", "register", "all", "stop"):
        raise SystemExit(f"mapping.txt 의 building_attr_mode = {m} 는 쓸 수 없습니다 (layer / register / all / stop 중 하나)")
    return m


def reg_use_code(nm, cd):
    nm, cd = (nm or "").strip(), (cd or "").strip()
    for code, names, prefixes in REG_TO_USE:
        if nm and nm in names:
            return code
    for code, names, prefixes in REG_TO_USE:
        if cd and cd[:2] in prefixes:
            return code
    return REG_OTHER


def _num(v):
    try:
        return float(str(v).replace(",", "").strip())
    except (TypeError, ValueError):
        return None


def _col(head, want):
    """대장 파일 열 이름 찾기 (대소문자·앞뒤 공백 무시). 없으면 None"""
    if not want:
        return None
    up = {h.strip().upper(): h for h in head}
    return up.get(want.strip().upper())


def save_stats(st):
    os.makedirs(C.WORK, exist_ok=True)
    json.dump(st, open(STATS_FILE, "w", encoding="utf-8"), ensure_ascii=False, indent=1)


def load_stats():
    try:
        return json.load(open(STATS_FILE, encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def load_register():
    """건축물대장 → (by_pk {번호: 행번호}, by_pnu {pnu: [행번호]}, rows [(용도코드, 층수, 연면적, 주건축물?)], 정보)"""
    p = C.REGISTER_FILE
    cand = [p, os.path.splitext(p)[0] + ".txt"] if p else []
    p = next((x for x in cand if x and os.path.exists(x)), None)
    if not p:
        raise SystemExit(f"건축물대장 파일이 없습니다: {C.REGISTER_FILE}\n"
                         "  → external 폴더에 building_register.csv 를 넣거나 mapping.txt 의 register_file 을 고치세요"
                         " (대장이 없으면 building_attr_mode = all)")
    rows, enc, sep = read_any(p)
    head = list(rows[0].keys()) if rows else []
    F = C.FIELD
    cpk, cpnu, ccd, cnm = _col(head, F["reg_pk"]), _col(head, F["reg_pnu"]), _col(head, F["reg_use_cd"]), _col(head, F["reg_use_nm"])
    cfl, car, cmain = _col(head, F["reg_floor"]), _col(head, F["reg_area"]), _col(head, F["reg_main"])
    if not (cpk or cpnu) or not (ccd or cnm):
        raise SystemExit(f"건축물대장 칸을 찾지 못했습니다 (번호 {F['reg_pk']}/{F['reg_pnu']}, 용도 {F['reg_use_cd']}/{F['reg_use_nm']}).\n"
                         f"  파일 칸: {head[:20]}\n  → mapping.txt 의 reg_… 줄을 위 칸 이름으로 고치세요")
    by_pk, by_pnu, R = {}, collections.defaultdict(list), []
    for i, r in enumerate(rows):
        code = reg_use_code(r.get(cnm) if cnm else "", r.get(ccd) if ccd else "")
        R.append((code, _num(r.get(cfl)) if cfl else None, _num(r.get(car)) if car else None,
                  (str(r.get(cmain) or "").strip().upper() in MAIN_WORDS) if cmain else True))
        if cpk and (r.get(cpk) or "").strip():
            by_pk[r[cpk].strip()] = i
        if cpnu and (r.get(cpnu) or "").strip():
            by_pnu[r[cpnu].strip()].append(i)
    info = dict(file=os.path.basename(p), rows=len(rows), encoding=enc, by_pk=bool(cpk), by_pnu=bool(cpnu))
    log(f"  건축물대장 {os.path.basename(p)}: {len(rows):,}행 (인코딩 {enc}), 번호 칸 {'있음' if cpk else '없음'}, 필지번호 칸 {'있음' if cpnu else '없음'}")
    return by_pk, dict(by_pnu), R, info


def pick(idx, R):
    """한 필지(또는 번호)의 대장 행들 → (용도 코드, 층수). 주건축물 우선 → 연면적 최대 행의 용도, 층수는 최대"""
    main = [i for i in idx if R[i][3]] or list(idx)
    best = max(main, key=lambda i: (R[i][2] or 0.0))
    fl = [R[i][1] for i in idx if R[i][1] is not None]
    return R[best][0], (max(fl) if fl else None)


def _register(blds):
    """blds = [(g, x, y, 원래 칸)] → 같은 순서로 (용도, 층수) 목록 + 통계"""
    if not C.DATA_ROOT_PARCEL:
        raise SystemExit("building_attr_mode = register 에는 필지(config.DATA_ROOT_PARCEL)가 필요합니다 → python setup.py 로 필지 폴더를 지정")
    by_pk, by_pnu, R, info = load_register()
    F = C.FIELD
    X = np.array([b[1] for b in blds]); Y = np.array([b[2] for b in blds])
    bbox = [float(X.min()) - 50, float(Y.min()) - 50, float(X.max()) + 50, float(Y.max()) + 50]
    files = find_files(C.DATA_ROOT_PARCEL, [""], ".shp")
    want = [F["parcel_id"], F["parcel_bldrgst"]]
    cell = 50.0
    bucket = collections.defaultdict(list)
    for i, (x, y) in enumerate(zip(X, Y)):
        bucket[(int(x // cell), int(y // cell))].append(i)
    parcel_of = [None] * len(blds)          # 건물 i → (pnu, 대장번호)
    npar = 0
    for g, a in iter_layer(files=files, fields=want, bbox=bbox, encoding=C.PARCEL_ENCODING):
        npar += 1
        x0, x1, y0, y1 = g.GetEnvelope()
        for cx in range(int(x0 // cell), int(x1 // cell) + 1):
            for cy in range(int(y0 // cell), int(y1 // cell) + 1):
                for i in bucket.get((cx, cy), ()):
                    if parcel_of[i] is not None:
                        continue
                    pt = ogr.Geometry(ogr.wkbPoint)
                    pt.AddPoint_2D(float(X[i]), float(Y[i]))
                    if g.Contains(pt):
                        parcel_of[i] = (str(a.get(F["parcel_id"]) or "").strip(), str(a.get(F["parcel_bldrgst"]) or "").strip())
    out, st = [], collections.Counter()
    for i in range(len(blds)):
        p = parcel_of[i]
        if p is None:
            out.append(("", None)); st["필지 없음"] += 1; continue
        pnu, pk = p
        if pk and pk in by_pk:
            out.append(pick([by_pk[pk]], R)); st["대장번호로 연결"] += 1
        elif pnu in by_pnu:
            out.append(pick(by_pnu[pnu], R)); st["필지번호로 연결"] += 1
        else:
            out.append(("", None)); st["필지는 있으나 대장 없음"] += 1
    n = len(blds)
    linked = st["대장번호로 연결"] + st["필지번호로 연결"]
    stats = dict(mode="register", n_bld=n, n_parcel_read=npar, linked=linked, link_rate=round(linked / n, 4) if n else 0.0,
                 by_pk=st["대장번호로 연결"], by_pnu=st["필지번호로 연결"], no_parcel=st["필지 없음"], no_register=st["필지는 있으나 대장 없음"],
                 register=info)
    log(f"  건물 → 필지 → 건축물대장 연결 {linked:,}/{n:,} ({stats['link_rate']:.1%}): 대장번호 {stats['by_pk']:,}, 필지번호 {stats['by_pnu']:,}, "
        f"필지 없음 {stats['no_parcel']:,}, 대장 없음 {stats['no_register']:,}  ← 연결 안 된 건물은 용도 미상(집·목적지 아님)")
    return out, stats


def iter_buildings():
    """건물 레이어를 읽어 (도형, {"use","kind","floor"}) 를 차례로 돌려줌. 방식은 mapping 의 building_attr_mode"""
    m = mode()
    if m == "stop":
        raise SystemExit("mapping.txt 의 building_attr_mode = stop → 멈춤 (건물 용도를 구할 방법을 정한 뒤 다시)")
    cu, ck, cf = C.COL.get("bld_use"), C.COL.get("bld_kind"), C.COL.get("bld_floor")
    fields = [c for c in (cu, ck, cf) if c]
    if m == "layer":
        n = 0
        for g, a in iter_layer("building", fields=fields):
            n += 1
            yield g, {"use": str(a.get(cu) or "").upper() if cu else "", "kind": str(a.get(ck) or "").upper() if ck else "",
                      "floor": a.get(cf) if cf else None}
        save_stats(dict(mode="layer", n_bld=n))
        return
    if m == "all":
        n = 0
        for g, a in iter_layer("building", fields=[cf] if cf else []):
            n += 1
            yield g, {"use": C.RESIDENTIAL_USE[0], "kind": "", "floor": a.get(cf) if cf else None}
        save_stats(dict(mode="all", n_bld=n))
        log(f"  건물 용도 방식 all: 건물 {n:,}개를 모두 집으로 봄 (용도 미구분, 의료·노유자 건물 목적지 없음)")
        return
    # register: 건물을 먼저 다 읽고(대표점 필요), 필지·대장을 붙인 뒤 돌려줌
    blds = []
    for g, a in iter_layer("building", fields=[cf] if cf else []):
        p = g.PointOnSurface()
        if p is None:
            continue
        blds.append((g, p.GetX(), p.GetY(), a))
    if not blds:
        save_stats(dict(mode="register", n_bld=0, linked=0, link_rate=0.0))
        return
    res, stats = _register(blds)
    save_stats(stats)
    for (g, _, _, a), (use, fl) in zip(blds, res):
        yield g, {"use": use, "kind": "", "floor": fl if fl is not None else (a.get(cf) if cf else None)}
