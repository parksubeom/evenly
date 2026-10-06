# -*- coding: utf-8 -*-
"""
setup.py ─ [v6] 대화형 준비 도우미: 자료 최상위 폴더 하나만 알려 주면 나머지를 찾아 config.py·mapping.txt 를 채움

[실행]  python setup.py 자료폴더          예) python setup.py E:\제공자료
        (명령창에서 폴더 이름 앞 몇 글자를 치고 Tab 을 누르면 이름이 채워집니다. 폴더를 빼고 치면 물어봄)
        질문에는 Enter 만 눌러도 추천값으로 진행합니다.
[하는 일]
  1. 하위 폴더를 전부 훑어 shp / DEM(img·tif) / csv / zip / dxf 를 셈
  2. zip 이 있으면 목록을 보이고 풀지 물음 → hbi/work/unzipped/ 에 풂 (받은 자료 폴더는 건드리지 않음, 한글 파일 이름 처리)
     dxf 만 있으면 "수치지형도 shp(LX-002)가 필요합니다" 안내
  3. 판별: 수치지형도 레이어(파일 이름 코드 N3A_… · 한글 이름 · 도형 종류), DEM(칸 크기 5m/1m), 필지(19자리 번호 칸, 서울만), CSV(구분자 자동)
  4. 수치지형도가 여러 하위 폴더로 나뉘어 있으면 대상 구·옆 구와 겹치는 폴더만 쓰자고 표로 제안 → mapping 의 map_folders
     (폴더를 옮기거나 지우지 않음. 읽을 폴더만 적어 둠)
  5. AREA_BBOX 자동 결정: 고른 자료가 대상 범위(대상 구·옆 구 + 1km)보다 크게 넓으면 그 범위로, 아니면 None
  6. 칸 매핑: 대소문자 무시, 별칭 사전(lib/mapping.py), 값 모양 검사(표본 수백 개, 값은 화면·파일에 남기지 않음)
  7. 건물 용도 방식 추천 (용도 칸이 없으면 register: 건축물대장, 대장이 없으면 all)
  8. mapping.txt 저장, config.py 의 경로·AREA_BBOX·인코딩 줄 채움 (처음 원본은 config.py.bak)
[다음]  python check.py → python run_all.py
"""
import os, re, sys, glob, zipfile, collections, shutil
import config as C
from lib.conout import Tee, safe_console, ask
from lib import mapping as M
from lib.qio import open_vector, layer_srs, transformer, transform_xy, iter_layer
from lib import area
from osgeo import gdal, ogr
gdal.UseExceptions(); ogr.UseExceptions()
gdal.PushErrorHandler("CPLQuietErrorHandler")      # 인코딩을 시험해 보는 동안 나오는 GDAL 경고 글자는 숨김 (판정은 표본으로 함)
safe_console()

UNZIP = os.path.join(C.WORK, "unzipped")
# [v6] 안심구역 PC 의 자료 위치는 매번 같음 → 기본값. 하위 폴더는 화요일(10/6) 반출 runlog·schema 에 찍힌 실제 이름으로 채움 (None = 아직 모름 → 자동 탐색)
DEFAULT_ROOT = r"C:\Users\user\Desktop\박수범"
DEFAULT_SUBDIRS = {"수치지형도": "수치지형도2", "필지": "국토정보필지_서울특별시", "DEM 5m": None, "DEM 1m": None, "상호제공": None}
#   [v6.1] 필지 폴더 이름은 1차 반출 runlog 로 확인 (안에 AL_…_LAND_INFO_BASE_MAP_202606). DEM·상호제공 폴더 이름은 담당자 메모가 오면 채움
SKIP_DIRS = {"hbi", "hbi6", "hbi_geopandas"}      # 우리 코드 폴더(결과·풀린 zip 포함)는 자료로 훑지 않음
QUIET = False                                      # 기본 경로에 자료가 다 있으면 질문 없이 진행
VEC, RAS, TAB = (".shp",), (".img", ".tif", ".tiff", ".asc"), (".csv",)
GEOM = {"sidewalk_cl": "line", "road_cl": "line", "stairs": "poly", "building": "poly", "bus_stop": "point",
        "bridge": "poly", "tunnel": "poly", "overpass": "any", "station": "any"}
NAMES = {"sidewalk_cl": "보도중심선", "road_cl": "도로중심선", "stairs": "계단", "building": "건물", "bus_stop": "버스정류장",
         "bridge": "교량", "tunnel": "터널", "overpass": "육교", "station": "정거장(역)"}
GRADE = {"building": "분석 불가", "sidewalk_cl": "결과 약화", "road_cl": "결과 약화", "stairs": "결과 약화", "bus_stop": "결과 약화",
         "station": "결과 약화", "bridge": "괜찮음", "tunnel": "괜찮음", "overpass": "괜찮음"}
# 상호제공 CSV 알아보기: config 의 항목 → 머리줄에 이 칸들이 다 있으면 그 파일 (대소문자 무시)
CSV_SIGNS = [("JOIN_DATA", "KCB_60세이상_월200만원이하비율", ["EMD_CD", "C1_CNT", "AGE_CD"]),
             ("POINT_DATA", "SKT_60대이상유동인구", ["X_COORD", "Y_COORD", "MAN_FLOW_POP_CNT_60GU"]),
             ("POINT_DATA", "SKT_낮시간유동인구", ["X_COORD", "Y_COORD", "TMST_09"]),
             ("LEGAL_DONG_DATA", "교통사고_고령보행자", ["sigungu_nm", "bjd_nm", "accident_type_lv1"])]


def hr(t):
    print(f"\n=== {t} ===")


# ───────────────────────── 1. 훑기 ─────────────────────────
def scan(roots, skip=True):
    files = collections.defaultdict(list)
    for root in roots:
        for p in glob.glob(os.path.join(root, "**", "*"), recursive=True):
            parts = set(os.path.relpath(p, root).replace("\\", "/").split("/")[:-1])
            if skip and parts & SKIP_DIRS:
                continue
            if os.path.isfile(p):
                files[os.path.splitext(p)[1].lower()].append(p)
    return files


def q(prompt, default=""):
    """질문. QUIET(기본 경로에 자료가 다 있음)이면 묻지 않고 추천값"""
    if QUIET:
        print(f"{prompt}{default or 'Enter'}  (기본 경로라 묻지 않음)")
        return default
    return ask(prompt, default)


def defaults_ok(root):
    """기본 하위 폴더가 모두 알려져 있고(None 없음) 있으며 비어 있지 않으면 True"""
    if any(v is None for v in DEFAULT_SUBDIRS.values()):
        return False
    return all(os.path.isdir(os.path.join(root, v)) and any(os.scandir(os.path.join(root, v))) for v in DEFAULT_SUBDIRS.values())


def zip_names(zf):
    """zip 안 파일 이름 (UTF-8 표시가 없으면 CP949 로 다시 읽음: 윈도 탐색기로 만든 한글 zip)"""
    out = []
    for i in zf.infolist():
        n = i.filename
        if not (i.flag_bits & 0x800):
            try:
                n = n.encode("cp437").decode("cp949")
            except (UnicodeEncodeError, UnicodeDecodeError):
                pass
        out.append((i, n))
    return out


def unzip(z):
    dst = os.path.join(UNZIP, os.path.splitext(os.path.basename(z))[0])
    with zipfile.ZipFile(z) as zf:
        for info, name in zip_names(zf):
            if info.is_dir():
                continue
            target = os.path.normpath(os.path.join(dst, name))
            if not target.startswith(os.path.normpath(dst)):          # zip 안의 ../ 경로는 무시
                continue
            os.makedirs(os.path.dirname(target), exist_ok=True)
            with zf.open(info) as src, open(target, "wb") as out:
                shutil.copyfileobj(src, out)
    return dst


# ───────────────────────── 2. 판별 ─────────────────────────
def geom_kind(lyr):
    t = ogr.GT_Flatten(lyr.GetGeomType())
    if t in (ogr.wkbPoint, ogr.wkbMultiPoint): return "point"
    if t in (ogr.wkbLineString, ogr.wkbMultiLineString): return "line"
    if t in (ogr.wkbPolygon, ogr.wkbMultiPolygon): return "poly"
    return "any"


def layer_of(path, kind):
    """파일 이름 → 수치지형도 레이어 key (config.LAYERS 의 코드·한글 이름, 코드는 _ 없이도). 도형 종류가 안 맞으면 None"""
    nm = os.path.basename(path).upper().replace("_", "")
    for k, keys in C.LAYERS.items():
        for key in keys:
            if key and key.upper().replace("_", "") in nm:
                g = GEOM.get(k, "any")
                if g == "any" or kind in (g, "any"):
                    return k
    return None


def sample(path, enc=None, n=300):
    """(칸 이름 목록, {칸: [표본 값]}) — 값은 판별에만 쓰고 화면·파일에 내보내지 않음"""
    ds = open_vector(path, enc)
    lyr = ds.GetLayer(0)
    d = lyr.GetLayerDefn()
    names = [d.GetFieldDefn(i).GetName() for i in range(d.GetFieldCount())]
    vals = {k: [] for k in names}
    for i, f in enumerate(lyr):
        if i >= n:
            break
        for k in names:
            if not any(x in k.upper() for x in M.FORBIDDEN_FIELD_PARTS):
                vals[k].append(f.GetField(k))
    return names, vals, geom_kind(lyr), lyr


def share(vals, pat):
    v = [str(x).strip() for x in vals if x not in (None, "")]
    return (sum(1 for x in v if re.fullmatch(pat, x, re.I)) / len(v)) if v else 0.0     # [v6] 대소문자 무시 (bdu001 = BDU001)


def is_parcel(names, vals):
    return any(share(vals[k], r"\d{19}") > 0.9 for k in names)


def extent(path):
    ds = open_vector(path)
    lyr = ds.GetLayer(0)
    if lyr.GetFeatureCount() == 0:
        return None
    s, _ = layer_srs(lyr)
    x0, x1, y0, y1 = lyr.GetExtent()
    xs, ys = transform_xy(transformer(s), [x0, x1, x0, x1], [y0, y0, y1, y1])
    return (min(xs), min(ys), max(xs), max(ys))


def union_env(envs):
    envs = [e for e in envs if e]
    return [min(e[0] for e in envs), min(e[1] for e in envs), max(e[2] for e in envs), max(e[3] for e in envs)] if envs else None


def common_dir(paths):
    return os.path.commonpath([os.path.dirname(p) for p in paths]) if paths else None


# ───────────────────────── 3. 칸 찾기 ─────────────────────────
SHAPES = {"parcel_id": r"\d{19}", "parcel_emd_cd": r"\d{8}|\d{10}", "bld_floor": r"-?\d+(\.0+)?", "stair_kind": r"PGS\d{3}|[가-힣 ]{2,10}",
          "road_kind": r"RDC\d{3}|[가-힣 ]{2,12}",          # [v6.1] 코드든 한글 코드명이든 (자동차전용 칸은 형식을 몰라 검사 안 함)
          "bld_use": r"BDU\d{3}|[가-힣 ]{2,20}", "bld_kind": r"BDC\d{3}|[가-힣 ]{2,20}", "jimok": r"[가-힣]{1,4}",
          "sgg_nm": r"[가-힣 ]{2,12}", "emd_nm": r"[가-힣0-9 ]{2,12}", "parcel_bldrgst": r"[0-9A-Za-z\-]{6,40}"}


def find_field(key, names, vals, prev=None):
    """별칭 사전으로 칸 찾기 + 값 모양 검사 → (칸 이름 또는 None, 모양 일치 비율). prev = mapping.txt 에 이미 적힌 이름 (있으면 먼저)"""
    up = {n.upper(): n for n in names}
    for a in ([prev] if prev and prev != "?" else []) + M.ALIASES.get(key, []):
        n = up.get(a.upper())
        if n:
            sh = share(vals.get(n, []), SHAPES[key]) if key in SHAPES else 1.0
            if sh >= 0.5 or not any(v not in (None, "") for v in vals.get(n, [])):
                return n, sh
    if key == "parcel_id":                         # 이름이 달라도 19자리 번호 칸이면 고유번호
        for n in names:
            if share(vals.get(n, []), r"\d{19}") > 0.9:
                return n, 1.0
    return None, 0.0


def hangul_share(path, enc, fields):
    try:
        _, vals, _, _ = sample(path, enc, 300)
    except Exception:
        return 0.0, 1.0
    v = [str(x) for k in fields for x in vals.get(k, []) if x not in (None, "")]
    if not v:
        return 0.0, 0.0
    han = sum(1 for x in v if re.search("[가-힣]", x)) / len(v)
    bad = sum(1 for x in v if "\ufffd" in x or "??" in x) / len(v)
    return han, bad


def pick_encoding(path, fields, current):
    """.cpg 가 있으면 그대로. 없으면 UTF-8·CP949 로 표본을 읽어 한글이 더 바르게 읽히는 쪽"""
    if os.path.exists(os.path.splitext(path)[0] + ".cpg") or not fields:
        return current, "파일에 .cpg(인코딩 표시)가 있거나 한글 칸이 없어 그대로"
    best = max(("UTF-8", "CP949"), key=lambda e: (lambda h, b: h - b)(*hangul_share(path, e, fields)))
    return best, "한글 표본을 두 인코딩으로 읽어 깨지지 않는 쪽"


# ───────────────────────── 4. config.py 고치기 ─────────────────────────
def py_str(p):
    return "None" if p is None else 'r"' + p.replace('"', '\\"') + '"'


def set_line(txt, name, value):
    """config.py 의 `이름 = 값   # 주석` 줄에서 값만 바꿈 (주석은 그대로)"""
    pat = re.compile(rf"^({re.escape(name)}\s*=\s*)(.*?)(\s+#.*)?$", re.M)
    if not pat.search(txt):
        return txt, False
    return pat.sub(lambda m: m.group(1) + value + (m.group(3) or ""), txt, count=1), True


def set_path(txt, key, p):
    pat = re.compile(rf'("{re.escape(key)}"\s*:\s*\{{\s*"path"\s*:\s*)(None|r?"[^"]*")')
    return pat.sub(lambda m: m.group(1) + py_str(p), txt, count=1)


def write_config(vals):
    cp = os.path.join(C.BASE, "config.py")
    bak = cp + ".bak"
    if not os.path.exists(bak):
        shutil.copyfile(cp, bak)
    txt = open(cp, encoding="utf-8").read()
    for name in ("DATA_ROOT_MAP", "DATA_ROOT_DEM", "DATA_ROOT_DEM1M", "DATA_ROOT_PARCEL"):
        if name in vals:
            txt, _ = set_line(txt, name, py_str(vals[name]))
    if "AREA_BBOX" in vals:
        txt, _ = set_line(txt, "AREA_BBOX", str(vals["AREA_BBOX"]) if vals["AREA_BBOX"] else "None")
    for name in ("SHP_ENCODING", "PARCEL_ENCODING"):
        if vals.get(name):
            txt, _ = set_line(txt, name, f'"{vals[name]}"')
    for key, p in vals.get("paths", {}).items():
        txt = set_path(txt, key, p)
    open(cp, "w", encoding="utf-8").write(txt)
    return bak


# ───────────────────────── 본문 ─────────────────────────
def main():
    global QUIET
    root = sys.argv[1] if len(sys.argv) > 1 and not sys.argv[1].startswith("-") else ""
    if not root and os.path.isdir(DEFAULT_ROOT):
        root = ask(f"자료 폴더 = {DEFAULT_ROOT}  (Enter = 이 기본값 사용, 다르면 주소 입력): ", DEFAULT_ROOT)
    elif not root:
        print(f"기본 자료 폴더({DEFAULT_ROOT})가 없습니다. 자료 최상위 폴더 주소를 넣으세요."
              " (편한 방법: Enter 로 끝내고 명령창에 python setup.py 를 친 뒤, 띄우고 폴더 앞글자 + Tab)")
        root = ask("자료 폴더: ")
    root = root.strip().strip('"')
    if not root or not os.path.isdir(root):
        raise SystemExit(f"폴더가 없습니다: {root!r} → 주소를 확인하고 python setup.py 폴더 를 다시")
    root = os.path.abspath(root)
    old = M.read_raw()
    vals = dict(old)                      # mapping.txt 에 사람이 적은 값(대상 구 등)은 그대로 둠
    cfg = {}

    hr("1. 폴더 훑기")
    if os.path.normcase(os.path.abspath(root)) == os.path.normcase(os.path.abspath(DEFAULT_ROOT)) and defaults_ok(root):
        QUIET = True
        print("  기본 경로에 자료가 그대로 있습니다 → 질문 없이 진행 (확인 표만 보임)")
        for k, v in DEFAULT_SUBDIRS.items():
            print(f"    {k:<8} {os.path.join(root, v)}")
        files = scan([os.path.join(root, v) for v in DEFAULT_SUBDIRS.values()])
    else:
        if os.path.normcase(os.path.abspath(root)) == os.path.normcase(os.path.abspath(DEFAULT_ROOT)):
            print("  기본 하위 폴더가 없거나 달라졌습니다 → 자동 탐색")
        files = scan([root])
    print(f"  {root}")
    print("  " + ", ".join(f"{k} {len(v)}개" for k, v in sorted(files.items(), key=lambda kv: -len(kv[1])) if k in VEC + RAS + TAB + (".zip", ".dxf", ".xlsx", ".txt")))

    zips = files.get(".zip", [])
    if zips:
        hr("2. zip 파일")
        for i, z in enumerate(zips, 1):
            try:
                with zipfile.ZipFile(z) as zf:
                    nm = zip_names(zf)
                    kinds = collections.Counter(os.path.splitext(n)[1].lower() for _, n in nm)
                print(f"  {i}. {os.path.relpath(z, root)} ({os.path.getsize(z) / 1e6:,.1f}MB, 안에 {', '.join(f'{k} {v}' for k, v in kinds.most_common())})")   # [v6.1] 확장자 모두 (4개만 보이던 것)
            except zipfile.BadZipFile:
                print(f"  {i}. {os.path.relpath(z, root)}: 열 수 없는 zip (건너뜀)")
        a = q(f"  풀까요? 받은 폴더는 그대로 두고 {os.path.basename(C.BASE)}\\work\\unzipped 에 풉니다 (y/n, Enter = y): ", "y").lower()
        if a.startswith("y"):
            for z in zips:
                try:
                    print(f"  풀기: {os.path.basename(z)} → work/unzipped/{os.path.splitext(os.path.basename(z))[0]}")
                    unzip(z)
                except zipfile.BadZipFile:
                    pass
            more = scan([UNZIP])
            for k, v in more.items():
                files[k] += v

    hr("3. 자료 판별")
    maps, parcels, other = collections.defaultdict(list), [], []
    for p in files.get(".shp", []):
        try:
            names, vv, kind, _ = sample(p, None, 120)
        except Exception:
            other.append(p); continue
        k = layer_of(p, kind)
        if k:
            maps[k].append(p)
        elif is_parcel(names, vv):
            parcels.append((p, names, vv))
        else:
            other.append(p)
    if not maps and files.get(".dxf"):
        print(f"  !! 수치지형도가 dxf 로만 있습니다 ({len(files['.dxf'])}개). 이 코드는 수치지형도 shp(LX-002 형식)가 필요합니다 → 담당자에게 shp 판을 요청")
    for k in C.LAYERS:
        print(f"  [{'있음' if maps.get(k) else '없음'}] {NAMES[k]}({k}): 파일 {len(maps.get(k, []))}개" + ("" if maps.get(k) else f"  → {GRADE[k]}"))
    map_files = [p for v in maps.values() for p in v]
    map_root = common_dir(map_files)
    if map_root:
        cfg["DATA_ROOT_MAP"] = map_root

    # DEM
    dem = collections.defaultdict(list)
    for p in [p for e in RAS for p in files.get(e, [])]:
        try:
            d = gdal.Open(p)
            r = abs(d.GetGeoTransform()[1])
            d = None
        except Exception:
            continue
        dem["5m" if 3 <= r <= 7 else ("1m" if 0.5 <= r < 3 else "기타")].append(p)
    print(f"  DEM: 5m {len(dem['5m'])}개, 1m {len(dem['1m'])}개" + (f", 그 밖 해상도 {len(dem['기타'])}개 (안 씀)" if dem["기타"] else ""))
    if dem["5m"]:
        cfg["DATA_ROOT_DEM"] = common_dir(dem["5m"])
    if dem["1m"]:
        cfg["DATA_ROOT_DEM1M"] = common_dir(dem["1m"])

    # 필지: 19자리 번호 칸이 있는 shp. 서울(고유번호 앞 11)만
    seoul = []
    for p, names, vv in parcels:
        pid, _ = find_field("parcel_id", names, vv)
        pre = collections.Counter(str(x)[:2] for x in vv.get(pid, []) if x)
        if pre.most_common(1) and pre.most_common(1)[0][0] == "11" or "서울" in p:
            seoul.append((p, names, vv))
    print(f"  필지: shp {len(parcels)}개 중 서울 {len(seoul)}개")
    if seoul:
        cfg["DATA_ROOT_PARCEL"] = common_dir([p for p, _, _ in seoul])
        sp = {p for p, _, _ in seoul}
        if any(p not in sp and not os.path.relpath(p, cfg["DATA_ROOT_PARCEL"]).startswith("..") for p, _, _ in parcels):
            print("    (서울 밖 필지가 같은 폴더 안에 섞여 있음 → 분석 범위 밖이라 읽혀도 결과에는 영향 없음)")

    hr("4. 읽을 수치지형도 폴더와 분석 범위")
    tgt, nb = M.split_list(vals.get("target_gu", M.DEFAULTS["target_gu"][0])), M.split_list(vals.get("neighbor_gu", M.DEFAULTS["neighbor_gu"][0]))
    C.TARGET_GU, C.NEIGHBOR_GU = tgt, nb
    print(f"  대상 구: {','.join(tgt) or '전체'} / 옆 구: {','.join(nb) or '없음'}  (바꾸려면 mapping.txt 의 target_gu·neighbor_gu)")
    gp = area.gu_polys(set(tgt) | set(nb)) if (tgt and area.boundary_file()) else {}
    groups = collections.OrderedDict()
    if map_root:
        for p in sorted(map_files):
            rel = os.path.relpath(p, map_root).replace("\\", "/")
            g = rel.split("/")[0] if "/" in rel else "."
            groups.setdefault(g, []).append(p)
    sel = list(groups)
    genv = {}
    for g, fs in groups.items():
        key = [p for p in fs if p in maps.get("building", []) + maps.get("road_cl", []) + maps.get("sidewalk_cl", [])] or fs
        genv[g] = union_env([extent(p) for p in key])
    if len(groups) > 1:
        print(f"  수치지형도가 하위 폴더 {len(groups)}개로 나뉘어 있습니다. 대상 구·옆 구와 겹치는 폴더만 쓰자고 제안합니다:")
        use = {g: bool(gp and genv[g] and area.overlap_gu(genv[g], gp)) if gp else True for g in groups}
        while True:
            print(f"   {'번호':>4}  {'쓰기':^4}  폴더  →  겹치는 구")
            for i, g in enumerate(groups, 1):
                ov = area.overlap_gu(genv[g], gp) if (gp and genv[g]) else []
                print(f"   {i:>4}  {'○' if use[g] else '×':^4}  {g}  →  {', '.join(ov) or '없음'}")
            a = q("  Enter = 이대로 / 번호(예: 3 7) = ○·× 바꾸기: ")
            if not a:
                break
            for t in re.findall(r"\d+", a):
                if 1 <= int(t) <= len(groups):
                    g = list(groups)[int(t) - 1]
                    use[g] = not use[g]
        sel = [g for g in groups if use[g]]
        vals["map_folders"] = ";".join(sel)
        print(f"  → 쓸 폴더 {len(sel)}개 (map_folders 에 저장, 폴더는 옮기거나 지우지 않음)")
    else:
        vals["map_folders"] = ""
    C.MAP_FOLDERS = M.split_list(vals["map_folders"], ";")
    data_env = union_env([genv[g] for g in sel])
    tr = area.bbox_of(list(gp.values()), area.MARGIN) if gp else None
    bb, why = area.decide_bbox(data_env, tr)
    cfg["AREA_BBOX"] = bb
    vals["area_reason"] = why
    print(f"  AREA_BBOX = {bb}  ← {why}")
    if dem["5m"] and gp:
        try:
            vrt = gdal.BuildVRT("/vsimem/s.vrt", dem["5m"]); gt = vrt.GetGeoTransform()
            de = (gt[0], gt[3] + gt[5] * vrt.RasterYSize, gt[0] + gt[1] * vrt.RasterXSize, gt[3]); vrt = None; gdal.Unlink("/vsimem/s.vrt")
            bad = [g for g in tgt if g in gp and area.cover_share(gp[g], [de]) < 0.95]
            print("  DEM: 대상 구를 " + ("모두 덮음" if not bad else f"다 덮지 못함 → {', '.join(bad)} (경사 0 으로 계산되는 곳이 생김, 담당자에게 DEM 범위 확인)"))
        except Exception:
            pass

    hr("5. 칸 이름 맞추기 (값은 표시하지 않음)")
    notes, table = {}, []
    impact = {"bld_use": "용도 칸 없음 → 건물 용도 방식 register·all", "bld_kind": "용도가 빈 건물의 주택 판정에만 씀 (영향 작음)",
              "bld_floor": "층수 없으면 1층으로 봄 (고령인구 배분 가중치만 영향)", "stair_kind": "계단·스탠드 구분 안 함 (모두 계단)",
              "bus_kind": "안 씀", "parcel_id": "06·register 멈춤", "parcel_bldrgst": "대장 연결은 필지번호로만",
              "road_kind": "고속국도를 네트워크에서 빼지 않음 (v5 와 같음)", "road_mtrwy": "자동차전용 도로를 네트워크에서 빼지 않음 (v5 와 같음)",
              "bld_ufid": "참고용 UFID 일치율만 못 잼", "parcel_ufid": "참고용 UFID 일치율만 못 잼",
              "parcel_emd_cd": "고유번호 앞 10자리로 대신", "jimok": "06 '대' 필지·13 설치 부지 계산 안 됨",
              "sgg_nm": "11 교통사고 결합 안 됨", "emd_nm": "11 교통사고 결합 안 됨"}
    lay_keys = [("building", ["bld_use", "bld_kind", "bld_floor", "bld_ufid"]), ("stairs", ["stair_kind"]), ("bus_stop", ["bus_kind"]),
                ("road_cl", ["road_kind", "road_mtrwy"])]
    enc_map = C.SHP_ENCODING
    for lk, keys in lay_keys:
        if not maps.get(lk):
            continue
        names, vv, _, _ = sample(maps[lk][0], None, 300)
        if lk == "building":
            print(f"  건물 칸: {names}")
        for k in keys:
            n, sh = find_field(k, names, vv, old.get(k))
            vals[k] = n or "?"
            if not n:
                notes[k] = impact[k]
            table.append((k, n or "?", f"{sh:.0%}" if n else "-", M.DEFAULTS[k][1]))
    if seoul:
        p, names, vv = seoul[0]
        enc, why = pick_encoding(p, [n for n in names if any(isinstance(v, str) and re.search("[^\x00-\x7f]", v or "") for v in vv[n])] or
                                 [n for n in names if n.upper() in ("JIMOK", "지목", "SGG_NM", "EMD_NM")], C.PARCEL_ENCODING)
        cfg["PARCEL_ENCODING"] = enc
        names, vv, _, _ = sample(p, enc, 300)
        print(f"  필지 칸: {[n for n in names if not any(x in n.upper() for x in M.FORBIDDEN_FIELD_PARTS)]} (소유·공시지가 칸은 읽지 않음), 인코딩 {enc}")
        for k in ("parcel_id", "parcel_bldrgst", "parcel_ufid", "parcel_emd_cd", "jimok", "sgg_nm", "emd_nm"):
            n, sh = find_field(k, names, vv, old.get(k))
            vals[k] = n or "?"
            if not n:
                notes[k] = impact[k]
            table.append((k, n or "?", f"{sh:.0%}" if n else "-", M.DEFAULTS[k][1]))
    # 수치지형도 인코딩: .cpg(인코딩 표시)가 없는 파일만 영향을 받으므로, 그런 파일 중 한글이 든 칸이 있는 파일로 판정
    nocpg = [p for p in map_files if not os.path.exists(os.path.splitext(p)[0] + ".cpg")]
    for p in nocpg[:30]:
        names, vv, _, _ = sample(p, None, 100)
        txt = [n for n in names if any(isinstance(v, str) and re.search("[^\x00-\x7f]", v) for v in vv[n])]
        if txt:
            cfg["SHP_ENCODING"], why = pick_encoding(p, txt, C.SHP_ENCODING)
            print(f"  수치지형도 인코딩: {cfg['SHP_ENCODING']} (.cpg 없는 파일 {len(nocpg)}개 중 한글 칸 표본으로 판정)")
            break
    else:
        print(f"  수치지형도 인코딩: {C.SHP_ENCODING} 그대로 (.cpg 없는 파일에 한글 칸이 없거나 모두 .cpg 있음)")
    print(f"   {'키':<16} {'찾은 칸':<14} {'모양 일치':>8}  설명")
    for k, n, sh, d in table:
        print(f"   {k:<16} {n:<14} {sh:>8}  {d}" + (f"  ← {notes[k]}" if k in notes else ""))
    for lk in C.LAYERS:                         # 레이어 이름: 찾은 그대로 (기본 코드)
        if not maps.get(lk):
            notes[f"layer_{lk}"] = f"파일을 못 찾음 ({GRADE[lk]}). 실제 파일 이름의 글자를 쉼표로 추가"

    hr("6. 건물 용도 방식")
    from lib.battr import register_path
    reg = register_path()
    reg_ok = reg is not None
    none_txt = "없음 (external\\building_register.csv 또는 작업 폴더에 같은 이름)"
    print(f"  건축물대장: {os.path.relpath(reg, os.path.dirname(C.BASE)) if reg_ok else none_txt}")
    from lib.battr import gis_path
    gis = gis_path()
    print(f"  GIS건물통합정보: {os.path.relpath(gis, os.path.dirname(C.BASE)) if gis else '없음 (external' + chr(92) + 'gis_building.gpkg)'}")
    has_use = vals.get("bld_use") not in (None, "?")
    can = [m for m, ok in (("layer", has_use), ("register", reg_ok and bool(seoul)), ("gisbld", gis is not None), ("all", True)) if ok]
    print(f"  쓸 수 있는 방식: {' → '.join(can)}  (이 순서로 check.py 가 표본 연결률을 재서 처음으로 80% 를 넘는 방식을 고름)")
    print("  고를 수 있는 값: auto(추천, check 가 고름) / layer / register / gisbld / all / stop")
    a = q("  Enter = auto, 직접 정하려면 입력: ", "auto").lower()
    vals["building_attr_mode"] = a if a in ("auto", "layer", "register", "gisbld", "all", "stop") else "auto"
    vals["building_attr_chosen"] = ""

    hr("7. 상호제공 CSV")
    paths = {}
    for p in files.get(".csv", []) + files.get(".txt", []):
        try:
            with open(p, "rb") as f:
                head = f.readline()
        except OSError:
            continue
        for enc in ("utf-8-sig", "cp949"):
            try:
                h = head.decode(enc); break
            except UnicodeDecodeError:
                h = ""
        cols = {c.strip().upper() for c in re.split(r"[,|\t]", h)}
        for grp, key, need in CSV_SIGNS:
            if key not in paths and all(n.upper() in cols for n in need):
                paths[key] = p
    for grp, key, need in CSV_SIGNS:
        print(f"  {key}: {os.path.relpath(paths[key], root) if key in paths else '없음 (못 받았으면 그대로)'}")
    if paths:
        a = q("  위 파일 경로를 config.py 에 넣을까요? (y/n, Enter = y): ", "y").lower()
        if a.startswith("y"):
            cfg["paths"] = paths

    hr("8. 저장")
    hdr = f"자료 폴더: {root}"
    M.write(vals, notes=notes, header=hdr)
    bak = write_config(cfg)
    print(f"  mapping.txt 저장 (칸 {sum(1 for k in vals if vals[k] == '?')}개는 ? = 못 찾음)")
    print(f"  config.py 고침 (처음 원본: {os.path.basename(bak)})")
    for k in ("DATA_ROOT_MAP", "DATA_ROOT_DEM", "DATA_ROOT_DEM1M", "DATA_ROOT_PARCEL", "AREA_BBOX", "SHP_ENCODING", "PARCEL_ENCODING"):
        if k in cfg:
            print(f"    {k} = {cfg[k]}")
    print("\n다음: python check.py")


if __name__ == "__main__":
    with Tee(os.path.join(C.OUTPUT, "setup_report.txt")):
        main()
