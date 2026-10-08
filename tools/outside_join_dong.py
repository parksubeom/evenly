# -*- coding: utf-8 -*-
"""
tools/outside_join_dong.py ─ [안심구역 밖] 반출 dong_hbi.csv 에 서울시 동별 통계(장애인·독거노인 등)를 "자치구 + 동 이름"으로 붙이기

[실행]
  python3 tools/outside_join_dong.py --dong results/raw_export/dong_hbi.csv \\
      --stat 장애인_동별.csv --label disabled --cols 합계 \\
      --stat 독거노인_동별.csv --label alone65 --cols 합계 --skip 2
  --stat 은 여러 번 쓸 수 있고, 각 --stat 뒤의 --label·--cols·--skip 이 그 파일에 적용됩니다.
  --cols : 붙일 숫자 열 이름(쉼표로 여러 개). --skip : 머리 줄 자동 탐지가 틀릴 때 앞에서 건너뛸 줄 수
[하는 일]
  1. 통계 파일의 머리 줄 찾기: 칸 값이 정확히 "동"·"행정동"·"동별"·"읍면동" 인 첫 줄 (제목에 "동별"이 들어간 줄은 아님)
  2. 구 이름이 첫 행에만 있는 병합 셀 형식이면 아래 행에 구 이름을 채움. 소계·합계 행은 건너뜀
  3. 이름 표준화: 공백 제거, "제3동" → "3동", 가운뎃점·마침표 통일 → dong_hbi.csv 의 "서울특별시 종로구 사직동" 과 맞춤
  4. 열 추가: <label>_<열> = 통계값, <label>_<열>_in_high = 값 × weight_high ÷ weight_all (HBI 1.8 이상 건물 거주 추정)
[결과] results/dong_joined.csv  +  화면 보고(붙은 동 수 / 결과 동 수, 이름이 안 맞은 통계 행, 통계가 안 붙은 결과 동)
       "_in_high" 는 연면적 비율로 나눈 추정치입니다 (실제 거주 위치를 아는 것이 아님).
"""
import csv, os, re, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HEAD_KEYS = {"동", "행정동", "동별", "읍면동"}
GU_KEYS = {"자치구", "구", "구별", "시군구", "자치구별"}
SKIP_WORDS = ("소계", "합계", "계", "총계", "서울시", "서울특별시")


def read_rows(path):
    for enc in ("utf-8-sig", "cp949", "euc-kr"):
        try:
            with open(path, encoding=enc, newline="") as f:
                return [[c.strip() for c in r] for r in csv.reader(f)]
        except UnicodeDecodeError:
            continue
    raise SystemExit(f"인코딩을 알 수 없음: {path}")


def norm(s):
    """동 이름 표준화: 공백 제거, 제N동 → N동, 가운뎃점·마침표·쉼표 통일"""
    s = re.sub(r"\s+", "", str(s))
    s = re.sub(r"제(\d+)", r"\1", s)
    s = re.sub(r"[·ㆍ・.,]", ".", s)
    return s


def num(v):
    s = str(v).replace(",", "").strip()
    if s in ("", "-", "…", "X", "x"):
        return None
    try:
        return float(s)
    except ValueError:
        return None


def find_header(rows, skip):
    """머리 줄 번호. skip 이 있으면 그 줄. 아니면 칸 값이 정확히 HEAD_KEYS 중 하나인 첫 줄"""
    if skip is not None:
        return skip
    for i, r in enumerate(rows):
        if any(c in HEAD_KEYS for c in r):      # 정확히 같은 칸만 (제목 "…동별 현황" 은 통과 못 함)
            return i
    raise SystemExit("머리 줄을 찾지 못했습니다 (\"동\"·\"행정동\"·\"동별\"·\"읍면동\" 칸이 없음) → --skip 으로 머리 줄 번호를 지정하세요")


def compound_headers(rows):
    """서울시 통계 시스템 형식: 앞의 여러 줄이 모두 "동별(1)" 로 시작하는 머리 줄 → 열마다 이름을 이어 붙임
    예) ["2025", "합계", "지체", "계"] → "합계_지체_계" (연도·같은 말 반복은 뺌). 반환: (머리 줄 수, 이름 목록) 또는 None"""
    k = 0
    while k < len(rows) and rows[k] and str(rows[k][0]).startswith("동별("):
        k += 1
    if k == 0:
        return None
    names = []
    for j in range(len(rows[0])):
        toks = []
        for i in range(k):
            t = re.sub(r"\s+", "", rows[i][j]) if j < len(rows[i]) else ""
            if not t or re.fullmatch(r"\d{4}", t) or (toks and toks[-1] == t):
                continue
            toks.append(t)
        names.append("_".join(toks))
    return k, names


def match_col(want, names, data_cols):
    """요청한 열(예: "지체", "합계")과 맞는 실제 열 번호. 토큰이 모두 들어 있는 열 중
    계·소계(총계) 토큰이 있는 것 → 토큰 수가 적은 것 → 왼쪽 것 순으로 고름"""
    w = [t for t in re.split(r"[_·,]", re.sub(r"\s+", "", want)) if t]
    cand = [j for j in data_cols if all(t in names[j].split("_") for t in w)]
    if not cand:
        return None
    return sorted(cand, key=lambda j: (not any(t in ("계", "소계") for t in names[j].split("_")[len(w):] + names[j].split("_")),
                                       len(names[j].split("_")), j))[0]


def parse_long(rows, cols, path):
    """서울시 통계 '세로' 형식: 동별 | 장애유형별 | 성별 | 항목 | 단위 | 2025 년 (한 줄 = 동 하나 × 분류 하나)
    구 이름 행 다음에 그 구의 동 행이 이어짐 (구 열이 따로 없음) → 앞의 구 행을 기억해 두고 동에 붙임"""
    head = rows[0]
    vi = max(i for i, c in enumerate(head) if re.search(r"\d{4}", c))          # 값 열 (예: "2025 년")
    dims = [i for i in range(1, vi) if head[i] not in ("항목", "단위")]        # 분류 열 (장애유형별, 성별 …)
    gus = set()
    for r in rows[1:]:
        if r and r[0].endswith("구") and r[0] not in ("합계",):
            gus.add(r[0])
    table, gu = {}, None
    for r in rows[1:]:
        if len(r) <= vi or not r[0]:
            continue
        if r[0] in gus:
            gu = r[0]
            continue
        if gu is None or r[0] in SKIP_WORDS or r[0] == "기타":
            continue
        key = "_".join(re.sub(r"\s+", "", r[i]) for i in dims)
        table.setdefault((gu, r[0]), {})[key] = num(r[vi])
    names = sorted({k for v in table.values() for k in v})
    pick_ = []
    for c in cols:
        w = [t for t in re.split(r"[_·,]", re.sub(r"\s+", "", c)) if t]
        cand = [n for n in names if all(t in n.split("_") for t in w)]
        if not cand:
            raise SystemExit(f"{os.path.basename(path)}: 분류 '{c}' 없음. 있는 분류: {names[:40]}")
        cand.sort(key=lambda n: (not any(t in ("계", "소계", "합계") for t in n.split("_") if t not in w), len(n.split("_")), n))
        pick_.append(cand[0])
    print(f"  {os.path.basename(path)}: 세로 형식, 분류 열 {[head[i] for i in dims]}, 값 열 '{head[vi]}', 분류 조합 {len(names)}개, "
          f"고른 분류: " + ", ".join(f"{c} → '{n}'" for c, n in zip(cols, pick_)))
    return {(norm(g), norm(d)): {"gu": g, "dong": d, "vals": [v.get(n) for n in pick_]} for (g, d), v in table.items()}


def parse_stat(path, cols, skip):
    rows = read_rows(path)
    if skip is None and rows and rows[0] and rows[0][0].replace(" ", "") == "동별" and any(re.search(r"\d{4}", c) for c in rows[0]):
        return parse_long(rows, cols, path)
    ch = compound_headers(rows) if skip is None else None
    if ch:                                       # ── 서울시 통계 시스템 형식 (동별(1)·(2)·(3), 여러 줄 머리)
        k, names = ch
        lab = [j for j, c in enumerate(rows[0]) if str(c).startswith("동별(")]
        data_cols = [j for j in range(len(names)) if j not in lab]
        di, gi = lab[-1], (lab[-2] if len(lab) >= 2 else None)
        if len(lab) < 3:
            print(f"  !! {os.path.basename(path)}: 행 쪽 열이 {[rows[0][j] for j in lab]} 뿐 → 동 단위 열(동별(3))이 없는 구 단위 통계로 보임")
        ci = []
        for c in cols:
            j = match_col(c, names, data_cols)
            if j is None:
                raise SystemExit(f"{os.path.basename(path)}: 열 '{c}' 을 찾지 못함. 열 이름: {[names[j] for j in data_cols]}")
            ci.append(j)
        print(f"  {os.path.basename(path)}: 머리 줄 {k}줄, 실제 열 이름 {len(data_cols)}개, 고른 열: " + ", ".join(f"{c} → '{names[j]}'" for c, j in zip(cols, ci)))
        start, head = k, rows[0]
    else:                                        # ── 일반 형식 (머리 줄 한 줄, 또는 두 줄)
        h = find_header(rows, skip)
        head = rows[h]
        names = head[:]
        if not all(c in names for c in cols) and h + 1 < len(rows):
            names = [b if b else a for a, b in zip(head, rows[h + 1] + [""] * (len(head) - len(rows[h + 1])))]
            start = h + 2
        else:
            start = h + 1
        miss = [c for c in cols if c not in names]
        if miss:
            raise SystemExit(f"{os.path.basename(path)}: 열 {miss} 없음. 머리 줄: {names}")
        di = next(i for i, c in enumerate(head) if c in HEAD_KEYS)
        gi = next((i for i, c in enumerate(head) if c in GU_KEYS), None)
        ci = [names.index(c) for c in cols]
    out, gu = {}, ""
    for r in rows[start:]:
        if len(r) <= max([di] + ci):
            continue
        if gi is not None and r[gi]:
            gu = r[gi]                           # 병합 셀: 구 이름이 첫 행에만 있으면 기억해 두고 아래 행에 채움
        dong = r[di]
        # 소계·합계 행 건너뜀 ("계" 는 정확히 같을 때만: "계동" 같은 동 이름을 지우지 않도록)
        if not dong or dong in SKIP_WORDS or dong == "기타" or any(dong.startswith(w) for w in ("소계", "합계", "총계")) or not gu or gu in SKIP_WORDS:
            continue
        out[(norm(gu), norm(dong))] = {"gu": gu, "dong": dong, "vals": [num(r[i]) for i in ci]}
    return out


def parse_args(argv):
    """--stat 마다 뒤따르는 --label/--cols/--skip 을 그 파일에 묶음 (argparse 의 append 는 짝을 보장하지 않아서 직접 처리)"""
    opt = {"dong": None, "out": os.path.join(ROOT, "results", "dong_joined.csv")}
    groups, i = [], 0
    while i < len(argv):
        k = argv[i]
        v = argv[i + 1] if i + 1 < len(argv) else None
        if k in ("-h", "--help"):
            raise SystemExit(__doc__)
        if v is None:
            raise SystemExit(f"{k} 뒤에 값이 없습니다")
        if k == "--stat":
            groups.append({"path": v, "label": None, "cols": None, "skip": None})
        elif k in ("--label", "--cols", "--skip"):
            if not groups:
                raise SystemExit(f"{k} 는 --stat 뒤에 적으세요")
            groups[-1][k[2:]] = int(v) if k == "--skip" else v
        elif k in ("--dong", "--out"):
            opt[k[2:]] = v
        else:
            raise SystemExit(f"모르는 옵션: {k}")
        i += 2
    if not opt["dong"] or not groups or any(g["label"] is None or g["cols"] is None for g in groups):
        raise SystemExit("--dong 과, --stat 마다 --label·--cols 가 필요합니다\n" + __doc__)
    return opt, groups


def main():
    opt, groups = parse_args(sys.argv[1:])
    with open(opt["dong"], encoding="utf-8-sig", newline="") as f:
        dong = list(csv.DictReader(f))
    head = list(dong[0].keys())
    gus = set()
    for d in dong:
        parts = d["adm_nm"].split()                # "서울특별시 종로구 사직동"
        d["_key"] = (norm(parts[-2]), norm(parts[-1])) if len(parts) >= 2 else ("", norm(d["adm_nm"]))
        gus.add(d["_key"][0])
    for g in groups:
        path, label, cols, skip = g["path"], g["label"], g["cols"], g["skip"]
        cols = [c.strip() for c in cols.split(",") if c.strip()]
        st = parse_stat(path, cols, skip)
        hit = 0
        for d in dong:
            s = st.get(d["_key"])
            wa, wh = num(d.get("weight_all")), num(d.get("weight_high"))
            for c, v in zip(cols, (s["vals"] if s else [None] * len(cols))):
                cc = re.sub(r"\s+", "", c)            # 열 이름에는 공백을 넣지 않음 ("심한 장애" → "심한장애")
                d[f"{label}_{cc}"] = "" if v is None else v
                d[f"{label}_{cc}_in_high"] = round(v * wh / wa, 1) if (v is not None and wa and wh is not None) else ""
            hit += s is not None
        head += [label + "_" + "".join(c.split()) + sfx for c in cols for sfx in ("", "_in_high")]
        used = {d["_key"] for d in dong}
        unmatched = [f"{v['gu']} {v['dong']}" for k, v in st.items() if k[0] in gus and k not in used]
        nostat = [d["adm_nm"] for d in dong if d["_key"] not in st]
        print(f"[{label}] {os.path.basename(path)}: 붙은 동 {hit} / 결과 동 {len(dong)}")
        print(f"  분석 대상 구인데 이름이 안 맞은 통계 행 {len(unmatched)}개: {', '.join(unmatched) if unmatched else '-'}")
        print(f"  통계가 안 붙은 결과 동 {len(nostat)}개: {', '.join(nostat) if nostat else '-'}")
    out = opt["out"]
    # [v6.1] 출처: 입력 dong_hbi.csv 폴더(와 그 부모)의 _source.txt. 실제가 아니면 기본 출력(results/dong_joined.csv) 대신 입력 옆에 씀
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from evenly_common import source_of, RAW_EXPORT
    dd = os.path.dirname(os.path.abspath(opt["dong"]))
    kind = source_of(dd) or source_of(os.path.dirname(dd))
    in_raw = os.path.realpath(opt["dong"]).startswith(os.path.realpath(RAW_EXPORT) + os.sep)
    prov = kind or ("real" if in_raw else "unknown")
    if prov != "real" and os.path.abspath(out) == os.path.join(ROOT, "results", "dong_joined.csv"):
        out = os.path.join(dd, "dong_joined.csv")
        print(f"(입력 출처 {prov}: 실제 반출이 아니라 results/dong_joined.csv 대신 입력 옆에 씀)")
    os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
    with open(out, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=head, extrasaction="ignore")
        w.writeheader()
        w.writerows(dong)
    with open(os.path.splitext(out)[0] + "_source.txt", "w", encoding="utf-8") as f:   # 기획서 실제 빌드가 확인함
        f.write(f"{prov}\n{os.path.abspath(opt['dong'])}\n")
    print(f"→ {os.path.abspath(out)} (출처 {prov})")


if __name__ == "__main__":
    main()
