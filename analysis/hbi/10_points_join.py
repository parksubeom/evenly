# -*- coding: utf-8 -*-
"""
10_points_join.py ─ [v5, 안심구역 안에서] 점 자료(교통사고 위치 등)를 행정동·250m 격자로 세어 HBI 와 비교

[언제]  안심구역에서 교통사고 위치 같은 "점" 파일(CSV)을 받았을 때 (03_hbi.py 다음)
[준비]  config.py 의 POINT_DATA 에 파일 경로·좌표 열 이름·좌표계·조건을 적습니다.
          filter   = {"열": "값"}     정확히 같은 행만 (값이 리스트면 그중 하나와 같으면 통과)
          contains = {"열": "글자"}   그 글자가 들어 있는 행만
        JS로 치면 rows.filter(r => r[열] === 값).filter(r => r[열].includes(글자)) 입니다.
[실행]  python 10_points_join.py
[하는 일]
  1. CSV 를 utf-8-sig → cp949 → euc-kr 순서로 읽어 봄 (공공데이터는 cp949 가 많음)
  2. 조건(filter·contains)에 맞는 행만 남기고, 좌표를 분석 좌표계로 바꾼 뒤 분석 범위 밖 점은 버림
  3. 행정동·250m 격자마다 점 수를 세고 "주거 건물 100개당 점 수"를 구함 (건물 MIN_COUNT 개 미만 동·격자는 제외)
  4. 동별 평균 HBI 와의 스피어만 순위상관, HBI 하위·상위 25% 동의 평균 비율
[결과] (output/ → 반출 대상. 개별 점 좌표는 내보내지 않고 개수만)
  [v5 값 합계 모드] POINT_DATA 에 value_cols·agg="sum" 을 주면 점 수 대신 값의 합 (SKT 50m 셀 유동인구 등).
       period_col(예: STD_YM) 을 주면 기간 수로 나눠 기간 평균. 이때 n_points·per100_bld 는 "값 합계"·"건물 100개당 값"
  points_<이름>_dong.csv   : adm_cd, n_bld, hbi_mean, n_points, per100_bld
  points_<이름>_grid.csv   : cell_x, cell_y, n_bld, hbi_mean, n_points, per100_bld
  points_summary.csv       : 이름별 행 수 흐름(전체 → 조건 통과 → 좌표 있음 → 범위 안 → 동·격자 합계)과 상관계수
[해석] 상관이 있어도 인과는 아님 (예: 언덕 동네는 원래 길이 좁을 수도 있음). 기획서에는 "보조 근거"로만 씁니다.
"""
import lib.runlog as _RL; _RL.start(globals())   # [v6.2] 기록·멈추면 메모 카드 (무거운 import 보다 먼저. lib/runlog.py)
import os, csv, numpy as np
np.seterr(invalid="ignore", divide="ignore")
import config as C
from lib.qio import log, write_csv, transform_xy, transformer, find_files, iter_layer, read_any as read_table, safe_head
from lib.qgraph import spearman
from lib.bload import load_buildings, usable

os.makedirs(C.OUTPUT, exist_ok=True)
todo = {k: v for k, v in C.POINT_DATA.items() if v.get("path")}
if not todo:
    raise SystemExit("config.POINT_DATA 에 path 가 있는 항목이 없습니다 → 건너뜀")


def fnum(v):
    try:
        return float(str(v).replace(",", "").strip())
    except ValueError:
        return np.nan


b = load_buildings()
X, Y = b["x"], b["y"]
U = usable(b)
T = "medical" if "medical_hbi" in b else [k[:-4] for k in b if k.endswith("_hbi")][0]
H = b[f"{T}_hbi"]
v = np.isfinite(H) & U                                  # 통계에 쓸 건물 (경계 제외)
bx0, bx1, by0, by1 = np.nanmin(X[v]), np.nanmax(X[v]), np.nanmin(Y[v]), np.nanmax(Y[v])   # 분석 범위

# 행정동 (05_export.py 와 같은 방식)
bd = find_files(C.EXTERNAL, ["dong_boundary"], ".geojson") + find_files(C.EXTERNAL, ["dong_boundary"], ".shp")
polys, dcode = [], []
if bd:
    from lib.qnetwork import points_in_polygons
    polys = [(g, a) for g, a in iter_layer(files=bd[:1], bbox=None)]
    ck = next(k for k in polys[0][1] if k.upper() in ("ADM_CD", "ADM_DR_CD", "ADSTRD_CD", "CODE"))
    polys = [p for p in polys if not (p[0].GetEnvelope()[1] < bx0 or p[0].GetEnvelope()[0] > bx1 or
                                      p[0].GetEnvelope()[3] < by0 or p[0].GetEnvelope()[2] > by1)]
    dcode = [str(a[ck]) for _, a in polys]
    _, bwhich = points_in_polygons(X, Y, polys)          # 건물마다 몇 번째 동인지

summary = []
for name, cfg in todo.items():
    rows, enc, sep = read_table(cfg["path"], cfg.get("sep"))   # [v5] 인코딩·구분자(쉼표·| ·탭) 자동
    n0 = len(rows)
    vcols = cfg.get("value_cols") or []                        # [v5] 값 합계 모드 (SKT 유동인구처럼 점=셀, 값을 더함)
    summing = cfg.get("agg") == "sum" and bool(vcols)
    for col, val in (cfg.get("filter") or {}).items():   # 정확히 일치 (리스트면 그중 하나)
        ok = set(str(x).strip().upper() for x in (val if isinstance(val, (list, tuple)) else [val]))   # [v6] 대소문자 무시
        rows = [r for r in rows if str(r.get(col, "")).strip().upper() in ok]
    for col, txt in (cfg.get("contains") or {}).items(): # 글자 포함
        rows = [r for r in rows if str(txt).upper() in str(r.get(col, "")).upper()]   # [v6] 대소문자 무시
    n1 = len(rows)
    xy = np.array([(fnum(r.get(cfg["x_col"])), fnum(r.get(cfg["y_col"]))) for r in rows], float).reshape(-1, 2)
    if summing:
        miss = [c for c in vcols if rows and c not in rows[0]]
        if miss:
            raise SystemExit(f"{name}: 값 열 {miss} 가 파일에 없습니다. 열: {safe_head(rows[0])[0]}")   # [v6.2] 머리줄 없으면 모양만
        val = np.array([np.nansum([fnum(r.get(c)) for c in vcols]) for r in rows], float)
        pc = cfg.get("period_col")
        nper = len({r.get(pc) for r in rows}) if pc else 1          # 기간(예: 12개월) 수 → 합 ÷ 기간 = 기간 평균
        val = val / max(nper, 1)
        if pc:
            log(f"  값 합계 모드: {'+'.join(vcols)}, '{pc}' {nper}개 기간 평균")
    else:
        val = np.ones(len(xy))
    okm = np.isfinite(xy).all(axis=1)
    xy, val = xy[okm], val[okm]                          # 좌표가 빈 행 제외
    n2 = len(xy)
    px, py = transform_xy(transformer(cfg.get("crs") or "EPSG:4326"), xy[:, 0], xy[:, 1]) if n2 else (np.array([]), np.array([]))
    inb = (px >= bx0) & (px <= bx1) & (py >= by0) & (py <= by1)   # 분석 범위 안
    px, py, val = px[inb], py[inb], val[inb]
    n3 = len(px)
    vsum = float(val.sum())                              # 범위 안 점들의 값 합계 (개수 모드면 = 점 수)
    log(f"{name}: 인코딩 {enc}, 구분자 '{sep}', 전체 {n0:,} → 조건 통과 {n1:,} → 좌표 있음 {n2:,} → 범위 안 {n3:,}"
        + (f" (값 합계 {vsum:,.1f})" if summing else ""))

    # 격자별
    kb = np.floor(X[v] / C.GRID).astype(np.int64) * 10**7 + np.floor(Y[v] / C.GRID).astype(np.int64)
    kp = np.floor(px / C.GRID).astype(np.int64) * 10**7 + np.floor(py / C.GRID).astype(np.int64)
    ub, inv = np.unique(kb, return_inverse=True)
    cnt = np.bincount(inv)
    hm = np.bincount(inv, H[v]) / cnt
    up, pinv = np.unique(kp, return_inverse=True)
    pmap = dict(zip(up, np.bincount(pinv.ravel(), val) if len(kp) else []))   # 격자별 점 수(또는 값 합)
    grows = []
    for k in np.where(cnt >= C.MIN_COUNT)[0]:
        n = float(pmap.get(ub[k], 0))
        grows.append([(ub[k] // 10**7 + 0.5) * C.GRID, (ub[k] % 10**7 + 0.5) * C.GRID, int(cnt[k]), round(float(hm[k]), 3),
                      round(n, 2) if summing else int(n), round(n / cnt[k] * 100, 3)])
    write_csv(os.path.join(C.OUTPUT, f"points_{name}_grid.csv"), ["cell_x", "cell_y", "n_bld", "hbi_mean", "n_points", "per100_bld"], grows)

    # 행정동별
    drows = []
    if polys:
        _, pwhich = points_in_polygons(px, py, polys)
        for k, code in enumerate(dcode):
            m = v & (bwhich == k)
            if m.sum() < C.MIN_COUNT:
                continue
            n = float(val[pwhich == k].sum()) if summing else int((pwhich == k).sum())
            drows.append([code, int(m.sum()), round(float(H[m].mean()), 3), round(n, 2) if summing else n, round(n / m.sum() * 100, 3)])
    write_csv(os.path.join(C.OUTPUT, f"points_{name}_dong.csv"), ["adm_cd", "n_bld", "hbi_mean", "n_points", "per100_bld"], drows)

    # 상관과 4분위 비교 (동 기준)
    ng, nd = sum(r[4] for r in grows), sum(r[3] for r in drows)
    rho = lo = hi = np.nan
    if len(drows) >= 5:
        hh = np.array([r[2] for r in drows]); rate = np.array([r[4] for r in drows])
        rho = spearman(hh, rate)
        q1, q3 = np.quantile(hh, [0.25, 0.75])
        lo, hi = float(rate[hh <= q1].mean()), float(rate[hh >= q3].mean())
    f = lambda x: round(float(x), 3) if np.isfinite(x) else ""
    unit = "값 합계" if summing else "점 수"
    summary += [[name, "전체 행 수", n0], [name, "조건 통과", n1], [name, "좌표 있음", n2], [name, "분석 범위 안", n3],
                [name, f"분석 범위 안 {unit}", round(vsum, 2)],
                [name, f"격자 합계(건물 {C.MIN_COUNT}개 이상 격자, {unit})", round(ng, 2)], [name, f"행정동 합계(건물 {C.MIN_COUNT}개 이상 동, {unit})", round(nd, 2)],
                [name, "동별 HBI 평균 vs 건물 100개당 점 수: 스피어만", f(rho)],
                [name, "HBI 하위 25% 동 평균(건물 100개당)", f(lo)], [name, "HBI 상위 25% 동 평균(건물 100개당)", f(hi)]]
    log(f"  격자 합계 {ng:,}, 동 합계 {nd:,} (범위 안 {n3:,} 중 차이 = 건물 {C.MIN_COUNT}개 미만 격자·동이나 동 경계 밖 점), 스피어만 {f(rho)}")

write_csv(os.path.join(C.OUTPUT, "points_summary.csv"), ["data", "metric", "value"], summary)
log("완료 → output/points_*_dong.csv, points_*_grid.csv, points_summary.csv (개별 점 좌표는 저장하지 않음)")
