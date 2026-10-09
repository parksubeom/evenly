# -*- coding: utf-8 -*-
"""
11_legal_dong_join.py ─ [v5, 안심구역 안에서] 좌표 없이 "법정동 이름" 만 있는 사건 자료(교통사고 등)를 법정동별로 세어 HBI 와 비교

[언제]  한국도로교통공단 교통사고 데이터처럼 위치가 시도·시군구·법정동 이름으로만 있는 파일을 받았을 때
        (좌표가 있는 점 자료는 10_points_join.py). 06_parcel.py 를 먼저 돌려야 HBI 와 붙일 수 있음
[준비]  config.py 의 LEGAL_DONG_DATA 에 파일 경로·열 이름·조건을 적습니다.
          sgg_col, dong_col : 시군구·법정동 이름 열 (교통사고: sigungu_nm, bjd_nm)
          filter   = {"열": "값" 또는 [값, …]}  정확히 같은 행만
          contains = {"열": "글자"}             그 글자가 들어 있는 행만
        JS로 치면 rows.filter(…).reduce((m, r) => m[r.시군구 + r.법정동]++, {}) 로 동별 건수를 세는 것
[하는 일]
  1. CSV 를 읽고(인코딩·구분자 자동) 조건에 맞는 행만 남김
  2. (시군구, 법정동 이름) 별 건수를 셈 (이름은 공백 제거·"제N동"→"N동" 으로 맞춤)
  3. output/parcel_by_legal_dong.csv (06 결과: 법정동별 필지 HBI, sgg_nm·emd_nm) 와 이름으로 붙임
  4. 필지 MIN_COUNT 개 이상 법정동만: 필지 100개당 건수, HBI 평균과의 스피어만 순위상관, HBI 하위·상위 25% 법정동 평균
[결과] (output/ → 반출 대상. 행 단위 사건은 내보내지 않고 법정동별 건수만)
  legal_<이름>.csv    : emd_cd, sgg_nm, emd_nm, n_parcel, hbi_mean, n_events, per100_parcel
  legal_summary.csv   : 전체 행 → 조건 통과 → 법정동 이름 있음 → 붙은 법정동 건수 합계, 상관계수
[해석] 상관이지 인과가 아님. 교통사고는 2020~2024 5년치 합이라 동별 "5년 누적 건수" 입니다.
"""
import lib.runlog as _RL; _RL.start(globals())   # [v6.2] 기록·멈추면 메모 카드 (무거운 import 보다 먼저. lib/runlog.py)
import os, re, numpy as np
np.seterr(invalid="ignore", divide="ignore")
import config as C
from lib.qio import log, write_csv, read_csv, read_any as read_table
from lib.qgraph import spearman

os.makedirs(C.OUTPUT, exist_ok=True)
todo = {k: v for k, v in C.LEGAL_DONG_DATA.items() if v.get("path")}
if not todo:
    raise SystemExit("config.LEGAL_DONG_DATA 에 path 가 있는 항목이 없습니다 → 건너뜀")


def norm(s):
    """이름 맞추기: 공백 제거, "제3동" → "3동", 가운뎃점·마침표 통일"""
    s = re.sub(r"\s+", "", str(s))
    s = re.sub(r"제(\d+)", r"\1", s)
    return re.sub(r"[·ㆍ・.,]", ".", s)


pl = read_csv(os.path.join(C.OUTPUT, "parcel_by_legal_dong.csv"))
named = [r for r in pl if (r.get("emd_nm") or "").strip()]
if not pl:
    log("  !! output/parcel_by_legal_dong.csv 가 없습니다 (06_parcel.py 먼저) → 법정동별 건수만 저장하고 HBI 와는 붙이지 않음")
elif not named:
    log("  !! parcel_by_legal_dong.csv 에 법정동 이름(emd_nm)이 없습니다 (필지에 SGG_NM·EMD_NM 필드 필요) → 건수만 저장")
pmap = {(norm(r["sgg_nm"]), norm(r["emd_nm"])): r for r in named}

summary = []
for name, cfg in todo.items():
    rows, enc, sep = read_table(cfg["path"], cfg.get("sep"))
    n0 = len(rows)
    for col, val in (cfg.get("filter") or {}).items():
        ok = set(str(x).strip().upper() for x in (val if isinstance(val, (list, tuple)) else [val]))   # [v6] 대소문자 무시
        rows = [r for r in rows if str(r.get(col, "")).strip().upper() in ok]
    for col, txt in (cfg.get("contains") or {}).items():
        rows = [r for r in rows if str(txt).upper() in str(r.get(col, "")).upper()]   # [v6] 대소문자 무시
    n1 = len(rows)
    cnt = {}
    for r in rows:
        k = (norm(r.get(cfg["sgg_col"], "")), norm(r.get(cfg["dong_col"], "")))
        if k[0] and k[1]:
            cnt[k] = cnt.get(k, 0) + 1
    n2 = sum(cnt.values())
    log(f"{name}: 인코딩 {enc}, 구분자 '{sep}', 전체 {n0:,} → 조건 통과 {n1:,} → 법정동 이름 있음 {n2:,} (법정동 {len(cnt)}곳)")
    out, hit_ev = [], 0
    for k, r in pmap.items():
        npar = int(float(r["n"]))
        if npar < C.MIN_COUNT:
            continue
        ne = cnt.get(k, 0)
        hit_ev += ne
        out.append([r["emd_cd"], r["sgg_nm"], r["emd_nm"], npar, r["hbi_mean"], ne, round(ne / npar * 100, 3)])
    if not pmap:                                      # 06 결과가 없으면 건수만 (법정동 이름별)
        out = [["", g, d, "", "", n, ""] for (g, d), n in sorted(cnt.items())]
    write_csv(os.path.join(C.OUTPUT, f"legal_{name}.csv"), ["emd_cd", "sgg_nm", "emd_nm", "n_parcel", "hbi_mean", "n_events", "per100_parcel"], out)
    rho = lo = hi = np.nan
    if pmap and len(out) >= 5:
        hh = np.array([float(r[4]) for r in out]); rate = np.array([r[6] for r in out], float)
        rho = spearman(hh, rate)
        q1, q3 = np.quantile(hh, [0.25, 0.75])
        lo, hi = float(rate[hh <= q1].mean()), float(rate[hh >= q3].mean())
    f = lambda x: round(float(x), 3) if np.isfinite(x) else ""
    summary += [[name, "전체 행 수", n0], [name, "조건 통과", n1], [name, "법정동 이름 있음(건수)", n2], [name, "법정동 수(건수 있는 곳)", len(cnt)],
                [name, f"붙은 법정동(필지 {C.MIN_COUNT}개 이상) 수", len(out) if pmap else 0], [name, "붙은 법정동 건수 합계", hit_ev if pmap else ""],
                [name, "법정동 HBI 평균 vs 필지 100개당 건수: 스피어만", f(rho)],
                [name, "HBI 하위 25% 법정동 평균(필지 100개당)", f(lo)], [name, "HBI 상위 25% 법정동 평균(필지 100개당)", f(hi)]]
    log(f"  붙은 법정동 {len(out) if pmap else 0}곳, 건수 합계 {hit_ev if pmap else '-'} / 이름 있는 건수 {n2} "
        f"(차이 = 분석 범위·필지 {C.MIN_COUNT}개 미만 법정동 밖의 사고), 스피어만 {f(rho)}")
write_csv(os.path.join(C.OUTPUT, "legal_summary.csv"), ["data", "metric", "value"], summary)
log("완료 → output/legal_*.csv, legal_summary.csv (행 단위 사건은 저장하지 않음)")
