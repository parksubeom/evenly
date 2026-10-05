# -*- coding: utf-8 -*-
"""
lib/mapping.py ─ [v6] mapping.txt 읽기: 자료마다 다른 "칸 이름·레이어 이름·폴더·대상 구" 를 코드 수정 없이 맞추는 곳

[mapping.txt 모양]  한 줄에 하나,  키 = 값  # 설명
    bld_use = BPRP_SE            # 건물 용도 칸
    parcel_id = pnu              # 필지 고유번호 칸 (대소문자는 상관없음)
    target_gu = 종로구,중구,관악구,광진구,강서구
    값이 ? 이면 "못 찾음" (그 칸을 쓰는 단계가 약해지거나 건너뜀)
  setup.py 가 자동으로 만들고, 사람은 메모장으로 몇 줄만 고칩니다. 파일이 없으면 아래 DEFAULTS(= v5 와 같은 값)를 씁니다.
  JS로 치면 .env 파일을 읽어 process.env 기본값 위에 덮어쓰는 dotenv 와 같습니다.

[config.py 와의 관계]  config.py 맨 끝에서 apply(globals()) 를 불러, 아래 값으로 config 의
    LAYERS, COL, FIELD, TARGET_GU, NEIGHBOR_GU, MAP_FOLDERS, BUILDING_ATTR_MODE, REGISTER, AREA_REASON 을 채웁니다.
  이 파일은 config 를 import 하지 않습니다 (서로 부르면 순환 import).
"""
import os

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MAPPING_FILE = os.path.join(HERE, "mapping.txt")

# 키: (기본값, 한국어 설명, 무리). 기본값은 v5 config 와 같음 → mapping.txt 가 없으면 v5 와 똑같이 동작
DEFAULTS = {
    # ── 범위 ──
    "target_gu": ("종로구,중구,관악구,광진구,강서구", "결과(격자·행정동·요약)를 낼 구. 비우면 자료 전체", "범위"),
    "neighbor_gu": ("성북구,성동구,동대문구", "옆 구: 길·목적지를 잇는 데만 씀 (결과에는 안 들어감)", "범위"),
    "map_folders": ("", "수치지형도에서 읽을 하위 폴더 (; 로 구분, 비우면 전부). setup.py 가 정함", "범위"),
    "area_reason": ("", "AREA_BBOX 를 정한 이유 (setup.py 가 적음, 설명용)", "범위"),
    # ── 건물 ──
    "building_attr_mode": ("layer", "건물 용도·층수를 어디서: layer(건물 칸) / register(건축물대장) / all(모든 건물을 집) / stop", "건물"),
    "bld_use": ("BPRP_SE", "건물 레이어의 용도 칸", "건물"),
    "bld_kind": ("BULD_SE", "건물 레이어의 종류 칸", "건물"),
    "bld_floor": ("BFLR_CO", "건물 레이어의 층수 칸", "건물"),
    "bld_ufid": ("UFID", "건물 레이어의 고유번호(UFID) 칸 (참고용: 필지 ufid 와 같은 체계인지)", "건물"),
    "stair_kind": ("ARSFCKD_SE", "계단 레이어의 구조 칸 (계단·스탠드 구분)", "레이어 칸"),
    "bus_kind": ("PTRFCKD_SE", "정류장 레이어의 종류 칸", "레이어 칸"),
    # ── 필지 ──
    "parcel_id": ("PNU", "필지 고유번호(19자리) 칸", "필지"),
    "parcel_bldrgst": ("BLDRGST_PK", "필지의 건축물대장 번호 칸 (없으면 ?)", "필지"),
    "parcel_emd_cd": ("EMD_CD", "필지의 법정 읍면동 코드 칸 (없으면 고유번호 앞 10자리로 대신)", "필지"),
    "parcel_ufid": ("UFID", "필지의 공간객체등록번호(UFID) 칸 (참고용)", "필지"),
    "jimok": ("JIMOK", "필지의 지목 칸", "필지"),
    "sgg_nm": ("SGG_NM", "필지의 시군구 이름 칸", "필지"),
    "emd_nm": ("EMD_NM", "필지의 법정동 이름 칸", "필지"),
    # ── 건축물대장 (building_attr_mode = register 일 때) ──
    "register_join": ("auto", "필지 ↔ 대장 연결: auto(연결률 높은 쪽, 같으면 pnu) / pnu(필지번호) / pk(대장번호)", "건축물대장"),
    "register_file": ("external/building_register.csv", "건축물대장 가공 파일 (hbi 폴더 기준 또는 전체 주소)", "건축물대장"),
    "reg_pk": ("bldrgst_pk", "대장의 건축물대장 번호 칸", "건축물대장"),
    "reg_pnu": ("pnu", "대장의 필지 고유번호 칸", "건축물대장"),
    "reg_use_cd": ("main_use_cd", "대장의 주용도 코드 칸 (비어 있으면 이름으로)", "건축물대장"),
    "reg_use_nm": ("main_use_nm", "대장의 주용도 이름 칸", "건축물대장"),
    "reg_floor": ("grnd_flr", "대장의 지상층수 칸", "건축물대장"),
    "reg_area": ("tot_area", "대장의 연면적 칸", "건축물대장"),
    "reg_main": ("main_atch", "대장의 주·부속 구분 칸", "건축물대장"),
    # ── 수치지형도 레이어 (파일 이름에 들어 있는 글자, 쉼표로 여럿) ──
    "layer_sidewalk_cl": ("N3L_A0033328,보도중심선", "보도중심선 (보행 네트워크 1순위)", "레이어"),
    "layer_road_cl": ("N3L_A0020000,도로중심선", "도로중심선 (보행 네트워크 2순위)", "레이어"),
    "layer_stairs": ("N3A_C0390000,계단", "계단 (면)", "레이어"),
    "layer_building": ("N3A_B0010000,건물", "건물 (면)", "레이어"),
    "layer_bus_stop": ("N3P_A0140000,정류장", "버스 정류장 (점)", "레이어"),
    "layer_bridge": ("N3A_A0070000,교량", "교량 (면)", "레이어"),
    "layer_tunnel": ("N3A_A0110020,터널", "터널 (면)", "레이어"),
    "layer_overpass": ("N3A_A0063321,육교", "육교 (점검용)", "레이어"),
    "layer_station": ("N3P_A0131122,정거장", "철도·지하철 정거장 (점)", "레이어"),
}
LAYER_KEYS = ["sidewalk_cl", "road_cl", "stairs", "building", "bus_stop", "bridge", "tunnel", "overpass", "station"]

# 칸 별칭 사전: setup.py 가 실제 칸 이름을 찾을 때 씀 (대소문자 무시). 첫 번째 = 정의서(LX·국토지리정보원) 이름
ALIASES = {
    "bld_use": ["BPRP_SE", "BLDG_USE", "BULD_USE", "USE_SE", "용도", "건물용도", "주용도"],
    "bld_kind": ["BULD_SE", "BLDG_SE", "BLDG_KND", "종류", "건물종류"],
    "bld_ufid": ["UFID", "UFID_CD", "고유식별자"],
    "parcel_ufid": ["UFID", "UFID_CD", "공간객체등록번호"],
    "bld_floor": ["BFLR_CO", "GRO_FLO_CO", "FLR_CO", "FLOORS", "층수", "지상층수"],
    "stair_kind": ["ARSFCKD_SE", "STR_SE", "구조"],
    "bus_kind": ["PTRFCKD_SE", "BUS_SE", "종류"],
    "parcel_id": ["PNU", "PARCEL_ID", "고유번호", "필지고유번호"],
    "parcel_bldrgst": ["BLDRGST_PK", "MGM_BLDRGST_PK", "BLD_RGST_PK", "건축물대장PK", "관리건축물대장PK"],
    "parcel_emd_cd": ["EMD_CD", "LDONG_CD", "BJD_CD", "LEGAL_DONG_CD", "읍면동코드", "법정동코드"],
    "jimok": ["JIMOK", "LNDCGR_NM", "LNDCGR", "JIMOK_NM", "지목", "지목명"],
    "sgg_nm": ["SGG_NM", "SIGUNGU_NM", "SGG_NAME", "시군구명", "시군구"],
    "emd_nm": ["EMD_NM", "LDONG_NM", "BJD_NM", "EMD_NAME", "읍면동명", "법정동명"],
    "reg_pk": ["bldrgst_pk", "MGM_BLDRGST_PK", "관리건축물대장PK", "건축물대장일련번호"],
    "reg_pnu": ["pnu", "PNU", "고유번호"],
    "reg_use_cd": ["main_use_cd", "MAIN_PURPS_CD", "주용도코드"],
    "reg_use_nm": ["main_use_nm", "MAIN_PURPS_CD_NM", "주용도코드명", "주용도"],
    "reg_floor": ["grnd_flr", "GRND_FLR_CNT", "지상층수"],
    "reg_area": ["tot_area", "TOTAREA", "연면적"],
    "reg_main": ["main_atch", "MAIN_ATCH_GB_CD_NM", "주부속구분코드명"],
}

# 읽지 않을 칸 (필지의 소유·공시지가). 이름에 이 글자가 들어가면 어떤 경우에도 요청하지 않음
FORBIDDEN_FIELD_PARTS = ["OWNER", "OWN_", "JIGA", "소유", "공시지가", "PBLNTF"]


def read_raw(path=MAPPING_FILE):
    """mapping.txt 에 실제로 적힌 줄만 {키: 값}. 파일이 없으면 {}"""
    vals = {}
    if os.path.exists(path):
        # 메모장 저장 형식 네 가지를 모두 읽음: UTF-8, UTF-8(BOM), ANSI(=CP949), 유니코드(=UTF-16, 앞에 FF FE 표시)
        raw = open(path, "rb").read()
        encs = ("utf-16",) if raw[:2] in (b"\xff\xfe", b"\xfe\xff") else ("utf-8-sig", "cp949")
        for enc in encs:
            try:
                lines = raw.decode(enc).splitlines()
                break
            except UnicodeDecodeError:
                continue
        else:                                   # 조용히 기본값으로 넘어가지 않고 멈춤 (고친 줄이 무시되면 안 되므로)
            raise SystemExit("mapping.txt 의 글자 형식을 읽지 못했습니다 → 메모장에서 파일 → 다른 이름으로 저장 → 인코딩 UTF-8 → 같은 이름으로 저장")
        for ln in lines:
            s = ln.split("#", 1)[0].strip()
            if "=" not in s:
                continue
            k, v = (x.strip() for x in s.split("=", 1))
            if k:
                vals[k] = v
    return vals


def read(path=MAPPING_FILE):
    """mapping.txt → {키: 값(문자열)}. 없는 키는 DEFAULTS. '?' 는 None (못 찾음)"""
    vals = {k: v[0] for k, v in DEFAULTS.items()}
    vals.update(read_raw(path))
    return {k: (None if v == "?" else v) for k, v in vals.items()}


def split_list(v, sep=","):
    return [x.strip() for x in (v or "").split(sep) if x.strip()]


def apply(g):
    """config.py 의 globals() 에 mapping 값을 덮어씀. 기본값만 있으면 v5 와 같은 결과"""
    m, raw = read(), read_raw()
    g["MAPPING"] = m
    # LAYERS·COL 은 config.py 위쪽에도 있음: mapping.txt 에 그 줄이 있을 때만 덮어씀 (config 를 고쳐 쓰던 v5 방식도 그대로 됨)
    lay, col = dict(g.get("LAYERS", {})), dict(g.get("COL", {}))
    for k in LAYER_KEYS:
        if f"layer_{k}" in raw or k not in lay:
            lay[k] = split_list(m.get(f"layer_{k}"))
    for k in ("bld_use", "bld_kind", "bld_floor", "bld_ufid", "stair_kind", "bus_kind"):
        if k in raw or k not in col:
            col[k] = m.get(k)
    g["LAYERS"], g["COL"] = lay, col
    g["REGISTER_JOIN"] = (m.get("register_join") or "auto").strip().lower()
    g["FIELD"] = {k: m.get(k) for k in ("parcel_id", "parcel_bldrgst", "parcel_ufid", "parcel_emd_cd", "jimok", "sgg_nm", "emd_nm",
                                        "reg_pk", "reg_pnu", "reg_use_cd", "reg_use_nm", "reg_floor", "reg_area", "reg_main")}
    g["TARGET_GU"] = split_list(m.get("target_gu"))
    g["NEIGHBOR_GU"] = split_list(m.get("neighbor_gu"))
    g["MAP_FOLDERS"] = split_list(m.get("map_folders"), ";")
    g["AREA_REASON"] = m.get("area_reason") or ""
    g["BUILDING_ATTR_MODE"] = (m.get("building_attr_mode") or "layer").strip().lower()
    rf = m.get("register_file") or ""
    g["REGISTER_FILE"] = rf if (not rf or os.path.isabs(rf)) else os.path.join(HERE, rf)


def write(vals, path=MAPPING_FILE, notes=None, header=""):
    """{키: 값} → mapping.txt (무리별, `키 = 값  # 설명`). notes = {키: 덧붙일 설명} (못 찾은 키의 영향 등)"""
    notes = notes or {}
    out = ["# mapping.txt ─ 자료의 칸·레이어 이름과 범위 (setup.py 가 만듦. 고칠 때는 = 오른쪽만, ? 는 못 찾음)",
           "#  저장할 때 인코딩은 UTF-8 그대로. 고친 뒤 python check.py 로 확인"]
    if header:
        out += ["#  " + h for h in header.splitlines()]
    group = None
    for k, (dv, desc, grp) in DEFAULTS.items():
        if grp != group:
            out += ["", f"# ── {grp} ──"]
            group = grp
        v = vals.get(k, dv)
        v = "?" if v is None else v
        note = f" ← {notes[k]}" if k in notes else ""
        out.append(f"{k} = {v}  # {desc}{note}")
    extra = [k for k in vals if k not in DEFAULTS]
    if extra:
        out += ["", "# ── 그 밖 ──"] + [f"{k} = {vals[k]}" for k in extra]
    with open(path, "w", encoding="utf-8-sig") as f:      # BOM 붙은 UTF-8: 옛 메모장에서도 한글이 바로 보임
        f.write("\n".join(out) + "\n")
