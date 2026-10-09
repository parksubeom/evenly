# -*- coding: utf-8 -*-
"""
07_join_dong.py ─ [안심구역 안에서] 상호제공데이터(SKT 유동인구, KCB 소득)를 행정동별 결과와 결합

[언제] 05_export.py 로 output/dong_hbi.csv 가 만들어진 뒤, 안심구역에서 SKT·KCB 파일을 받았을 때
[준비] config.py 맨 아래 JOIN_DATA 에 파일 경로·코드 열·값 열 이름을 적습니다.
       [v5] 구분자(쉼표·| ·탭)는 자동 인식(또는 "sep"), filter 값은 목록·"__LATEST__"(가장 늦은 값), 분모 여러 열은 "base_cols"
       SKT 유동인구는 행정동 코드가 없는 50m 셀 자료라 07 이 아니라 10_points_join.py 의 값 합계 모드로 붙입니다
       파일을 메모장이나 엑셀로 열어 첫 줄(열 이름)을 보고 그대로 옮겨 적으면 됩니다.
[실행] python 07_join_dong.py
[하는 일]
  1. 파일을 읽고(filter 조건이 있으면 그 행만), 행정동별로 value_cols 를 합산 (base_col 이 있으면 비율로)
  2. 행정동 코드 형식이 달라도 맞춰 봄: 행안부 10자리 / 앞 8자리 / 통계청 8자리 / 통계청 7자리 중 가장 많이 맞는 방식 선택
  3. HBI 평균·고위험 비율과의 상관계수(피어슨·스피어만), HBI 4분위 그룹별 평균 계산
[결과] output/join_<이름>.csv (행정동별 결합표), output/join_summary.csv (상관계수·그룹 비교)
[해석] 가설 "HBI 가 높은 동일수록 고령자 유동인구가 적다" → 상관계수가 음수(-)면 가설을 지지.
       결과가 가설과 다르게 나와도 그대로 보고하면 됩니다 (그 자체가 인사이트).
"""
import lib.runlog as _RL; _RL.start(globals())   # [v6.2] 기록·멈추면 메모 카드 (무거운 import 보다 먼저. lib/runlog.py)
import os, csv, numpy as np
np.seterr(invalid="ignore", divide="ignore")
import config as C
from lib.qio import log, read_csv, write_csv, read_any as read_table
from lib.qgraph import spearman

dong = read_csv(os.path.join(C.OUTPUT, "dong_hbi.csv"))
if not dong:
    raise SystemExit("output/dong_hbi.csv 가 없습니다. 05_export.py 를 먼저 실행하세요 (external/dong_boundary.geojson 필요)")

def num(v):
    try:
        return float(str(v).replace(",", ""))
    except ValueError:
        return np.nan

# 행정동 결과의 코드를 여러 형식으로 준비 (행안부 10자리 ADM_CD, 통계청 8자리 ADM_CD_STAT)
keyers = {
    "행안부10": lambda r: r["adm_cd"],
    "행안부8": lambda r: r["adm_cd"][:8],
    "통계청8": lambda r: r.get("adm_cd_stat", ""),
    "통계청7": lambda r: r.get("adm_cd_stat", "")[:7],
}
summary = []
for name, cfg in C.JOIN_DATA.items():
    if not cfg.get("path"):
        log(f"{name}: path 가 None → 건너뜀")
        continue
    rows, enc, sep = read_table(cfg["path"], cfg.get("sep"))       # [v5] 인코딩·구분자(쉼표·| ·탭) 자동
    log(f"{name}: {len(rows):,}행 읽음 (인코딩 {enc}, 구분자 '{sep}')")
    n0 = len(rows)
    for k, val in (cfg.get("filter") or {}).items():
        if val == "__LATEST__":                                   # [v5] 그 열의 가장 늦은 값만 (예: 기준시점)
            val = max(str(r.get(k, "")).strip() for r in rows)
            log(f"  filter {k} = 가장 늦은 값 '{val}'")
        ok = set(str(x).strip().upper() for x in (val if isinstance(val, (list, tuple)) else [val]))   # [v5] 목록이면 그중 하나, [v6] 대소문자 무시
        rows = [r for r in rows if str(r.get(k, "")).strip().upper() in ok]
    log(f"  조건 통과 {len(rows):,}/{n0:,}행")
    agg, base = {}, {}
    for r in rows:                                          # 행정동별 합산
        code = "".join(ch for ch in str(r.get(cfg["code_col"], "")) if ch.isdigit())
        if not code:
            continue
        agg[code] = agg.get(code, 0.0) + np.nansum([num(r.get(c)) for c in cfg["value_cols"]])
        bcols = cfg.get("base_cols") or ([cfg["base_col"]] if cfg.get("base_col") else [])   # [v5] 분모 열 여러 개(합)
        if bcols:
            base[code] = base.get(code, 0.0) + np.nansum([num(r.get(c)) for c in bcols])
    if cfg.get("base_cols") or cfg.get("base_col"):
        log(f"  비율 = {'+'.join(cfg['value_cols'])} 합 ÷ {'+'.join(cfg.get('base_cols') or [cfg['base_col']])} 합 (행정동별)")
        agg = {k: (v / base[k] if base.get(k) else np.nan) for k, v in agg.items()}
    best = max(keyers, key=lambda k: sum(keyers[k](d) in agg for d in dong))   # 가장 많이 맞는 코드 방식
    matched = [(d, agg[keyers[best](d)]) for d in dong if keyers[best](d) in agg]
    log(f"  코드 방식 '{best}' 로 {len(matched)}/{len(dong)}개 행정동 결합")
    if len(matched) < 5:
        log("  ! 결합된 동이 너무 적습니다. code_col 이름과 코드 형식을 확인하세요"); continue
    hbi = np.array([float(d["hbi_mean"]) for d, _ in matched])
    sh = np.array([float(d["share_high"]) for d, _ in matched])
    val = np.array([v for _, v in matched], float)
    write_csv(os.path.join(C.OUTPUT, f"join_{name}.csv"), ["adm_cd", "adm_nm", "hbi_mean", "share_high", name],
              [[d["adm_cd"], d["adm_nm"], d["hbi_mean"], d["share_high"], round(v, 4)] for d, v in matched])
    ok = np.isfinite(val)
    pr = float(np.corrcoef(hbi[ok], val[ok])[0, 1]); sr = spearman(hbi[ok], val[ok])
    summary += [[name, "결합 행정동 수", int(ok.sum())],
                [name, "HBI 평균 vs 값: 피어슨 상관", round(pr, 3)],
                [name, "HBI 평균 vs 값: 스피어만 순위상관", round(sr, 3)],
                [name, "고위험 비율 vs 값: 스피어만 순위상관", round(spearman(sh[ok], val[ok]), 3)]]
    q = np.quantile(hbi[ok], [0.25, 0.5, 0.75])             # HBI 4분위로 나눠 그룹 평균 비교
    grp = np.digitize(hbi[ok], q)
    for gname, gi in [("HBI 하위 25% 동", 0), ("25~50%", 1), ("50~75%", 2), ("HBI 상위 25% 동", 3)]:
        m = grp == gi
        summary.append([name, f"{gname} 평균값", round(float(np.mean(val[ok][m])), 4) if m.any() else ""])
write_csv(os.path.join(C.OUTPUT, "join_summary.csv"), ["data", "metric", "value"], summary)
log("결과:")
for r in summary:
    print("   ", r)
