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
             (①·② 중 무엇을 쓸지는 mapping 의 register_join = auto | pnu | pk. auto 는 두 연결률을 재서 높은 쪽, 같으면 pnu.
              두 번호 체계는 섞지 않음. 참고로 건물 UFID 와 필지 ufid 의 일치율도 잼)
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
from lib import codebook as K

BLD = "N3A_B0010000"                                    # 정의서의 건물 레이어 코드


def norm_use(v):
    """[v6.1] 건물 용도 값 → 정의서 코드 (BDU001 이든 bdu001 이든 "주거용단독주택" 이든 BDU001). 표에 없으면 대문자 그대로"""
    return K.to_code(BLD, "BPRP_SE", v)


def norm_kind(v):
    """[v6.1] 건물 종류 값 → 정의서 코드 (예: "아파트" → BDC003)"""
    return K.to_code(BLD, "BULD_SE", v)

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
LAST_STATS = {}


MODES = ("layer", "register", "gisbld", "all", "stop", "auto")
GIS_MIN_OVERLAP = 0.3     # gisbld: LX 건물 면적의 30% 이상 겹치는 GIS 건물이 있어야 연결 (조각 겹침으로 남의 용도를 붙이지 않게)


def mode():
    m = getattr(C, "BUILDING_ATTR_MODE", "layer") or "layer"
    if m not in MODES:
        raise SystemExit(f"mapping.txt 의 building_attr_mode = {m} 는 쓸 수 없습니다 ({' / '.join(MODES)} 중 하나)")
    if m == "auto":                       # [v6] check.py 가 표본으로 재서 고른 방식 (mapping 의 building_attr_chosen)
        c = (getattr(C, "MAPPING", {}).get("building_attr_chosen") or "").strip().lower()
        if c not in ("layer", "register", "gisbld", "all"):
            raise SystemExit("building_attr_mode = auto 인데 아직 고른 방식이 없습니다 → python check.py 를 먼저 (연결률을 재서 고름)")
        return c
    return m


def gis_path():
    """GIS건물통합정보 가공 파일 (tools/prep_gis_building.py 결과): mapping 의 gis_file → hbi 바깥(작업 폴더)의 같은 이름"""
    p = getattr(C, "GIS_FILE", None)
    if not p:
        return None
    cand = [p, os.path.join(os.path.dirname(C.BASE), os.path.basename(p))]
    return next((x for x in cand if os.path.exists(x)), None)


def _gisbld(blds, quiet=False):
    """LX 건물마다 겹치는 면적이 가장 큰 GIS 건물의 용도·층수 (겹침이 건물 면적의 GIS_MIN_OVERLAP 미만이면 연결 안 함)"""
    p = gis_path()
    if not p:
        raise SystemExit(f"GIS건물통합정보 파일이 없습니다: {getattr(C, 'GIS_FILE', '')} → tools/prep_gis_building.py 결과를 external 에 넣거나 building_attr_mode 를 바꾸기")
    F = C.FIELD
    X = np.array([b[1] for b in blds]); Y = np.array([b[2] for b in blds])
    bbox = [float(X.min()) - 100, float(Y.min()) - 100, float(X.max()) + 100, float(Y.max()) + 100]
    want = [w for w in (F.get("gis_use_cd"), F.get("gis_use_nm"), F.get("gis_floor")) if w]
    cell = 50.0
    gis, bucket = [], collections.defaultdict(list)
    for g, a in iter_layer(files=[p], fields=want, bbox=bbox):
        k = len(gis)
        gis.append((g.Clone(), a))
        x0, x1, y0, y1 = g.GetEnvelope()
        for cx in range(int(x0 // cell), int(x1 // cell) + 1):
            for cy in range(int(y0 // cell), int(y1 // cell) + 1):
                bucket[(cx, cy)].append(k)
    out, st, ov = [], collections.Counter(), []
    for g, x, y, _ in blds:
        x0, x1, y0, y1 = g.GetEnvelope()
        cand = {k for cx in range(int(x0 // cell), int(x1 // cell) + 1) for cy in range(int(y0 // cell), int(y1 // cell) + 1)
                for k in bucket.get((cx, cy), ())}
        best, area = None, 0.0
        for k in cand:
            gg = gis[k][0]
            if not g.Intersects(gg):
                continue
            try:
                ia = g.Intersection(gg).GetArea()
            except RuntimeError:
                continue
            if ia > area:
                best, area = k, ia
        a0 = g.GetArea() or 1.0
        if best is None:
            out.append(("", None)); st["겹침 없음"] += 1; continue
        r = area / a0
        if r < GIS_MIN_OVERLAP:
            out.append(("", None)); st["겹침 작음"] += 1; continue
        a = gis[best][1]
        fl = _num(a.get(F.get("gis_floor"))) if F.get("gis_floor") else None
        out.append((reg_use_code(str(a.get(F.get("gis_use_nm")) or "") if F.get("gis_use_nm") else "",
                                 str(a.get(F.get("gis_use_cd")) or "") if F.get("gis_use_cd") else ""), fl))
        st["연결"] += 1; ov.append(min(r, 1.0))
    n = len(blds)
    stats = dict(mode="gisbld", n_bld=n, n_gis_read=len(gis), linked=st["연결"], link_rate=round(st["연결"] / n, 4) if n else 0.0,
                 overlap_mean=round(float(np.mean(ov)), 4) if ov else None, no_overlap=st["겹침 없음"], small_overlap=st["겹침 작음"],
                 gis_file=os.path.basename(p))
    if not quiet:
        log(f"  GIS건물통합정보 {os.path.basename(p)}: 건물 {len(gis):,}개 읽음 → LX 건물 연결 {st['연결']:,}/{n:,} ({stats['link_rate']:.1%}), "
            f"평균 겹침률 {stats['overlap_mean'] or 0:.0%}, 겹침 없음 {st['겹침 없음']:,}, 겹침 {GIS_MIN_OVERLAP:.0%} 미만 {st['겹침 작음']:,}")
    return out, stats


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


def register_path():
    """건축물대장 파일 찾기: mapping 의 register_file → 같은 이름 .txt → hbi 바깥(작업 폴더)의 같은 이름. 없으면 None
    (메일로 반입한 파일이 작업 폴더에 그대로 있어도 옮기지 않고 찾게)"""
    p = C.REGISTER_FILE
    if not p:
        return None
    base = os.path.basename(p)
    cand = [p, os.path.splitext(p)[0] + ".txt",
            os.path.join(os.path.dirname(C.BASE), base), os.path.join(os.path.dirname(C.BASE), os.path.splitext(base)[0] + ".txt")]
    return next((x for x in cand if os.path.exists(x)), None)


def load_register():
    """건축물대장 → (by_pk {번호: 행번호}, by_pnu {pnu: [행번호]}, rows [(용도코드, 층수, 연면적, 주건축물?)], 정보)"""
    p = register_path()
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


def _register(blds, quiet=False):
    """blds = [(g, x, y, 원래 칸)] → 같은 순서로 (용도, 층수) 목록 + 통계"""
    if not C.DATA_ROOT_PARCEL:
        raise SystemExit("building_attr_mode = register 에는 필지(config.DATA_ROOT_PARCEL)가 필요합니다 → python setup.py 로 필지 폴더를 지정")
    by_pk, by_pnu, R, info = _REG_CACHE.get("reg") or load_register()
    _REG_CACHE["reg"] = (by_pk, by_pnu, R, info)
    F = C.FIELD
    X = np.array([b[1] for b in blds]); Y = np.array([b[2] for b in blds])
    bbox = [float(X.min()) - 50, float(Y.min()) - 50, float(X.max()) + 50, float(Y.max()) + 50]
    files = find_files(C.DATA_ROOT_PARCEL, [""], ".shp")
    want = [F["parcel_id"], F["parcel_bldrgst"], F.get("parcel_ufid")]
    cell = 50.0
    bucket = collections.defaultdict(list)
    for i, (x, y) in enumerate(zip(X, Y)):
        bucket[(int(x // cell), int(y // cell))].append(i)
    parcel_of = [None] * len(blds)          # 건물 i → (pnu, 대장번호)
    pufid = set()                           # 필지 ufid (참고: 건물 UFID 와 같은 체계인지)
    npar = 0
    for g, a in iter_layer(files=files, fields=[w for w in want if w], bbox=bbox, encoding=C.PARCEL_ENCODING):
        npar += 1
        if F.get("parcel_ufid") and a.get(F["parcel_ufid"]):
            pufid.add(str(a[F["parcel_ufid"]]).strip())
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
    # 세 연결률을 모두 잼: (a) pnu, (b) 대장번호(bldrgst_pk), (c) 참고: 건물 UFID 가 필지 ufid 에 있는 비율
    n = len(blds)
    hit_pnu = [p is not None and p[0] in by_pnu for p in parcel_of]
    hit_pk = [p is not None and bool(p[1]) and p[1] in by_pk for p in parcel_of]
    bu = [str((b[3] or {}).get(C.COL.get("bld_ufid")) or "").strip() for b in blds] if C.COL.get("bld_ufid") else []
    rate = lambda h: round(sum(h) / n, 4) if n else 0.0
    r_pnu, r_pk = rate(hit_pnu), rate(hit_pk)
    r_ufid = round(sum(1 for u in bu if u and u in pufid) / n, 4) if (n and bu and pufid) else None
    # 방식 고르기: mapping 의 register_join = auto | pnu | pk. auto 는 연결률이 높은 쪽 (같으면 pnu).
    #   두 번호 체계를 섞지 않음 (필지의 BLDRGST_PK 는 정의서상 총괄표제부 번호라, 표제부 일련번호와 우연히 같은 값이 다른 건물일 수 있음)
    join = (getattr(C, "REGISTER_JOIN", "auto") or "auto").lower()
    if join not in ("auto", "pnu", "pk"):
        raise SystemExit(f"mapping.txt 의 register_join = {join} 는 쓸 수 없습니다 (auto / pnu / pk)")
    use = join if join != "auto" else ("pk" if r_pk > r_pnu else "pnu")
    out, st = [], collections.Counter()
    for i in range(n):
        p = parcel_of[i]
        if p is None:
            out.append(("", None)); st["필지 없음"] += 1
        elif use == "pk" and hit_pk[i]:
            out.append(pick([by_pk[p[1]]], R)); st["연결"] += 1
        elif use == "pnu" and hit_pnu[i]:
            out.append(pick(by_pnu[p[0]], R)); st["연결"] += 1
        else:
            out.append(("", None)); st["필지는 있으나 대장 없음"] += 1
    linked = st["연결"]
    stats = dict(mode="register", register_join=join, join_used=use, n_bld=n, n_parcel_read=npar, linked=linked,
                 link_rate=round(linked / n, 4) if n else 0.0, rate_pnu=r_pnu, rate_pk=r_pk, rate_ufid=r_ufid,
                 no_parcel=st["필지 없음"], no_register=st["필지는 있으나 대장 없음"], register=info)
    if not quiet:
        log(f"  연결률 (a) 필지번호 pnu {r_pnu:.1%}, (b) 대장번호 {r_pk:.1%}, (c) 참고: 건물 UFID = 필지 ufid "
            f"{'칸 없음' if r_ufid is None else f'{r_ufid:.1%}'} → {'자동으로 ' if join == 'auto' else ''}{'필지번호' if use == 'pnu' else '대장번호'}로 연결")
        log(f"  건물 → 필지 → 건축물대장 연결 {linked:,}/{n:,} ({stats['link_rate']:.1%}), 필지 없음 {stats['no_parcel']:,}, "
            f"대장 없음 {stats['no_register']:,}  ← 연결 안 된 건물은 용도 미상(집·목적지 아님)")
    return out, stats


_REG_CACHE = {}       # check.py 가 표본 창마다 부를 때 대장 파일을 한 번만 읽게


def iter_buildings(save=True, quiet=False):
    """건물 레이어를 읽어 (도형, {"use","kind","floor"}) 를 차례로 돌려줌. 방식은 mapping 의 building_attr_mode
    save=False: work/battr_stats.json 을 쓰지 않음 (check.py 표본용). 통계는 LAST_STATS 에"""
    global LAST_STATS
    _save = save_stats if save else (lambda st: None)
    m = mode()
    if m == "stop":
        raise SystemExit("mapping.txt 의 building_attr_mode = stop → 멈춤 (건물 용도를 구할 방법을 정한 뒤 다시)")
    cu, ck, cf = C.COL.get("bld_use"), C.COL.get("bld_kind"), C.COL.get("bld_floor")
    fields = [c for c in (cu, ck, cf) if c]
    if m == "layer":
        n = 0
        for g, a in iter_layer("building", fields=fields):
            n += 1
            yield g, {"use": norm_use(a.get(cu)) if cu else "", "kind": norm_kind(a.get(ck)) if ck else "",
                      "floor": a.get(cf) if cf else None}         # [v6.1] 값이 코드든 한글 코드명이든 코드로
        LAST_STATS = dict(mode="layer", n_bld=n); _save(LAST_STATS)
        return
    if m == "all":
        n = 0
        for g, a in iter_layer("building", fields=[cf] if cf else []):
            n += 1
            yield g, {"use": C.RESIDENTIAL_USE[0], "kind": "", "floor": a.get(cf) if cf else None}
        LAST_STATS = dict(mode="all", n_bld=n); _save(LAST_STATS)
        if not quiet:
            log(f"  건물 용도 방식 all: 건물 {n:,}개를 모두 집으로 봄 (용도 미구분, 의료·노유자 건물 목적지 없음)")
        return
    # register·gisbld: 건물을 먼저 다 읽고(대표점·도형 필요), 필지·대장 또는 GIS 건물을 붙인 뒤 돌려줌
    blds = []
    for g, a in iter_layer("building", fields=[c for c in (cf, C.COL.get("bld_ufid")) if c]):
        p = g.PointOnSurface()
        if p is None:
            continue
        blds.append((g, p.GetX(), p.GetY(), a))
    if not blds:
        LAST_STATS = dict(mode=m, n_bld=0, linked=0, link_rate=0.0); _save(LAST_STATS)
        return
    res, stats = (_gisbld if m == "gisbld" else _register)(blds, quiet)
    LAST_STATS = stats; _save(stats)
    for (g, _, _, a), (use, fl) in zip(blds, res):
        yield g, {"use": use, "kind": "", "floor": fl if fl is not None else (a.get(cf) if cf else None)}
