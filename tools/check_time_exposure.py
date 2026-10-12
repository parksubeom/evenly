# -*- coding: utf-8 -*-
"""
tools/check_time_exposure.py ─ 반출 결과의 시간 값(HBI·왕복 분·단축 분)이 1~4채 몫을 드러내는지 전수 검사 (10/12, 리허설·시험용)

[실행]  ~/.evenly_envs/qpy tools/check_time_exposure.py <hbi6 폴더>     (run_all --modes … 를 돌린 폴더. check_area_exposure.py 와 같은 자료)
[하는 일] work/<방식>/buildings_hbi.csv 로 공개된 시간 값마다 실제 건물 집합을 다시 만들고
        05 grid_hbi(hbi_mean·hbi_median·elder_min·flat_min·add_min_med)·dong_hbi(hbi_mean)·summary 의 중앙값·분위수,
        09 intervention_summary(mean_saved_min·saved_p95_min(예전 max_saved_min)·sum_saved_bld_min·hbi_before·hbi_after)·
        intervention_grid(mean_saved_min) (집합은 work/<방식>/intervention_sets.npz)
        ① 값이 실제 값과 같은지 (집합을 바로 만들었는지)  ② 1~4채 값 그대로 (단독)  ③ 최대·최소 칸 (늘 한 건물 값)
        ④ 순서 통계(중앙값·분위수)가 100채 미만 집합에서 나옴 (9/28 기준 '5건 미만 제외' 안이지만 한 건물 값과 같아짐 → 수만 셈)
        ⑤ 더하는 값(평균 × 건물 수 = 합)끼리: 같은 양(HBI_목적지, 09 단축_목적지)의 공개 집합 B 에서 서로 겹치지 않는 공개 부분집합
           몇 개를 빼면 1~4채가 남는가 (방식끼리 포함: 같은 건물의 HBI 는 방식이 달라도 같음). 09 의 단축 분은 시나리오마다 달라질 수
           있지만 보수적으로 같은 양으로 봄
[결과]  화면에 칸마다 개수. ②③⑤ 가 0 이어야 함. ④ 는 수만 (기준 판단용)
"""
import csv, os, re, sys
import numpy as np
from osgeo import ogr, osr
ogr.UseExceptions()
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "analysis", "hbi"))
from lib.expose import removal_leak

H6 = sys.argv[1]; MINC = 5; QMIN = 100; GRID = 250
MODES = [m for m in ("layer", "register", "all", "gisbld") if os.path.exists(f"{H6}/work/{m}/buildings_hbi.csv") and os.path.exists(f"{H6}/output/{m}/summary.csv")]
if not MODES:
    raise SystemExit(f"{H6}/work/<방식>/buildings_hbi.csv 와 output/<방식>/summary.csv 가 있는 방식이 없음")


def rd(p):
    if not os.path.exists(p):
        return []
    with open(p, encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


fl = lambda s: float(s) if s not in ("", "nan", None) else np.nan
pub = lambda s: s not in ("", None, "nan")
B = {}
for m in MODES:
    R = rd(f"{H6}/work/{m}/buildings_hbi.csv")
    B[m] = {"key": [f"{float(r['x']):.2f},{float(r['y']):.2f}" for r in R], "x": np.array([float(r["x"]) for r in R]),
            "y": np.array([float(r["y"]) for r in R]), "edge": np.array([float(r["edge"] or 0) for r in R]), "rows": R}
# 행정동 소속
allk = {}
for m in MODES:
    for k, x, y in zip(B[m]["key"], B[m]["x"], B[m]["y"]):
        allk[k] = (x, y)
dong_of = {}
if os.path.exists(f"{H6}/external/dong_boundary.geojson"):
    ds = ogr.Open(f"{H6}/external/dong_boundary.geojson"); lyr = ds.GetLayer()
    src = lyr.GetSpatialRef(); dst = osr.SpatialReference(); dst.ImportFromEPSG(5186)
    for s_ in (src, dst):
        s_.SetAxisMappingStrategy(osr.OAMS_TRADITIONAL_GIS_ORDER)
    ct = osr.CoordinateTransformation(src, dst)
    keys = list(allk); XY = np.array([allk[k] for k in keys]); pt = ogr.Geometry(ogr.wkbPoint)
    for f in lyr:
        g = f.GetGeometryRef().Clone(); g.Transform(ct); e = g.GetEnvelope(); code = str(f.GetField("adm_cd"))
        for i in np.where((XY[:, 0] >= e[0]) & (XY[:, 0] <= e[1]) & (XY[:, 1] >= e[2]) & (XY[:, 1] <= e[3]))[0]:
            if keys[i] in dong_of:
                continue
            pt.SetPoint_2D(0, XY[i, 0], XY[i, 1])
            if g.Contains(pt):
                dong_of[keys[i]] = code

ADD = {}        # 더하는 값: 양(family) → [(이름, 방식, 집합)]
CNT = {"값": 0, "값 다름": 0, "단독": [], "최대": [], "순서 100채 미만": {}, "순서 1~4채": []}


def chk(name, m, S, shown, true, kind, fam=None, tol=0.011):
    """공개 값 하나: kind = 'add'(평균·합) / 'ord'(중앙값·분위수) / 'max'"""
    if not pub(shown):
        return
    CNT["값"] += 1
    lim = -tol if tol < 0 else tol * max(1.0, abs(true or 0))    # tol 이 음수면 절대 허용치 (소수 첫째 자리로 반올림한 분)
    if true is not None and np.isfinite(true) and abs(float(shown) - true) > lim:
        CNT["값 다름"] += 1
        if CNT["값 다름"] <= 5:
            print("   값 다름:", name, m, shown, round(true, 3), len(S))
    n = len(S)
    if 0 < n < MINC:
        (CNT["순서 1~4채"] if kind == "ord" else CNT["단독"]).append((name, m, n))
    if kind == "max":
        CNT["최대"].append((name, m, n))
    if kind == "ord" and n < QMIN:
        k = name.split("|")[0]
        CNT["순서 100채 미만"][k] = CNT["순서 100채 미만"].get(k, 0) + 1
    if kind == "add" and fam and n:
        ADD.setdefault(fam, []).append((name, m, frozenset(S)))


for m in MODES:
    R = B[m]["rows"]; keyl = B[m]["key"]; edge = B[m]["edge"]
    tg = sorted({c[:-4] for c in R[0] if c.endswith("_hbi") and not c.endswith("_dem1_hbi")})
    gx, gy = np.floor(B[m]["x"] / GRID).astype(int), np.floor(B[m]["y"] / GRID).astype(int)
    G = rd(f"{H6}/output/{m}/grid_hbi.csv"); D = rd(f"{H6}/output/{m}/dong_hbi.csv"); SM = rd(f"{H6}/output/{m}/summary.csv")
    gmap = {(r["target"], round(float(r["cell_x"]), 2), round(float(r["cell_y"]), 2)): r for r in G}
    DT = "medical" if "medical" in tg else tg[0]
    for t in tg:
        H = np.array([fl(r[f"{t}_hbi"]) for r in R])
        te = np.array([fl(r[f"{t}_t_elder"]) for r in R]) / 60; tf = np.array([fl(r[f"{t}_t_flat"]) for r in R]) / 60
        v = np.isfinite(H) & (edge < 0.5)
        cells = {}
        for i in np.where(v)[0]:
            cells.setdefault((gx[i], gy[i]), []).append(i)
        for (a, c), ii in cells.items():
            r = gmap.get((t, round((a + 0.5) * GRID, 2), round((c + 0.5) * GRID, 2)))
            if r is None:
                continue
            ii = np.array(ii); S = {keyl[i] for i in ii}
            chk(f"grid hbi_mean|{t}", m, S, r["hbi_mean"], float(np.mean(H[ii])), "add", ("hbi", t))
            chk(f"grid hbi_median|{t}", m, S, r["hbi_median"], float(np.median(H[ii])), "ord")
            chk(f"grid elder_min(중앙값)|{t}", m, S, r["elder_min"], float(np.nanmedian(te[ii])), "ord", tol=-0.051)
            chk(f"grid flat_min(중앙값)|{t}", m, S, r["flat_min"], float(np.nanmedian(tf[ii])), "ord", tol=-0.051)
            if "add_min_med" in r:
                chk(f"grid add_min_med|{t}", m, S, r["add_min_med"], float(np.nanmedian(te[ii] - tf[ii])), "ord", tol=-0.051)
        # summary 의 중앙값·분위수 (분석 건물 전체)
        nv = int(v.sum())
        for r in SM:
            if r.get("target") == t and re.search(r"중앙값|분위수", r.get("metric", "")):
                chk(f"summary {r['metric']}|{t}", m, {keyl[i] for i in np.where(v)[0]}, r["value"], None, "ord")
        if t == DT and D:
            for r in D:
                code = r["adm_cd"]
                S = {keyl[i] for i in np.where(v)[0] if dong_of.get(keyl[i]) == code}
                if not S:
                    continue
                ii = [i for i in np.where(v)[0] if dong_of.get(keyl[i]) == code]
                chk(f"dong hbi_mean|{t}", m, S, r["hbi_mean"], float(np.mean(H[ii])), "add", ("hbi", t))
    # [10/12 검토] 10 의 points_*_grid·dong hbi_mean (목적지 = 10 이 쓰는 기준 목적지, 05 와 같은 칸 집합)
    import glob as _g
    T10 = DT
    H10 = np.array([fl(r[f"{T10}_hbi"]) for r in R]); v10 = np.isfinite(H10) & (edge < 0.5)
    for pf in sorted(_g.glob(f"{H6}/output/{m}/points_*_grid.csv")):
        cells10 = {}
        for i in np.where(v10)[0]:
            cells10.setdefault((round((gx[i] + 0.5) * GRID, 2), round((gy[i] + 0.5) * GRID, 2)), []).append(i)
        for r in rd(pf):
            ii = cells10.get((round(float(r["cell_x"]), 2), round(float(r["cell_y"]), 2)), [])
            chk(f"10 {os.path.basename(pf)} hbi_mean|{T10}", m, {keyl[i] for i in ii}, r.get("hbi_mean"),
                float(np.mean(H10[ii])) if ii else None, "add", ("hbi", T10))
    for r in rd(f"{H6}/output/{m}/validation_sites.csv"):         # 04 선정지 원: 1~4채인데 값이 있으면 단독 (집합은 원이라 빼기는 안 봄)
        n_ = int(float(r.get("n_bld") or 0))
        if 0 < n_ < MINC and pub(r.get("hbi_mean")):
            CNT["단독"].append(("04 validation_sites hbi_mean", m, n_))
    # 09
    p = f"{H6}/work/{m}/intervention_sets.npz"
    SS = rd(f"{H6}/output/{m}/intervention_summary.csv"); IG = rd(f"{H6}/output/{m}/intervention_grid.csv")
    if not os.path.exists(p) or not SS:
        continue
    z = np.load(p, allow_pickle=False)
    keys9 = [f"{float(x):.2f},{float(y):.2f}" for x, y in zip(z["x"], z["y"])]
    names = list(z["names"])
    rk = [x.split("|") for x in z["rowkey"]]
    assert len(rk) == len(SS), (p, len(rk), len(SS))
    gx9, gy9 = np.floor(z["x"] / GRID).astype(int), np.floor(z["y"] / GRID).astype(int)
    igmap = {}
    for r in IG:
        igmap.setdefault((r["facility"], r["target"]), {})[(round(float(r["cell_x"]), 2), round(float(r["cell_y"]), 2))] = r
    for r, key in zip(SS, rk):
        si, T = int(key[0]), key[1]
        ben = np.where(z[f"s{si}_{T}_ben"])[0]; S = {keys9[i] for i in ben}
        fam = ("sv", "모든 목적지")                     # [10/12 검토] 단축 값은 목적지를 합쳐 한 양 (같은 건물의 단축이 목적지끼리 같은 경우가 많음)
        for col in ("mean_saved_min", "sum_saved_bld_min"):
            chk(f"09 {col}|{T}", m, S, r.get(col), None, "add", fam)
        chk(f"09 hbi_after|{T}", m, S, r.get("hbi_after"), None, "add", ("hbia", T))
        chk(f"09 hbi_before|{T}", m, S, r.get("hbi_before"), None, "add", ("hbi", T))
        if "max_saved_min" in r:
            chk(f"09 max_saved_min|{T}", m, S, r.get("max_saved_min"), None, "max")
        chk(f"09 saved_p95_min|{T}", m, S, r.get("saved_p95_min"), None, "ord")
        cells = {}
        for i in ben:
            cells.setdefault((round((gx9[i] + 0.5) * GRID, 2), round((gy9[i] + 0.5) * GRID, 2)), set()).add(keys9[i])
        for ck, rr in igmap.get((r["facility"], T), {}).items():
            Sc = cells.get(ck, set())
            if int(rr["n_benefit"]) != len(Sc):
                CNT["값 다름"] += 1
            chk(f"09 grid mean_saved_min|{T}", m, Sc, rr.get("mean_saved_min"), None, "add", fam)   # 단축 값 (목적지 합친 양)

print(f"방식 {MODES}: 공개 시간 값 {CNT['값']}개, 다시 계산한 값과 다름 {CNT['값 다름']}")
print(f"② 1~4채 값 그대로: {len(CNT['단독'])}건 {CNT['단독'][:6]}")
print(f"③ 최대 칸: {len(CNT['최대'])}건 {CNT['최대'][:4]}")
print(f"④ 순서 통계 1~4채: {len(CNT['순서 1~4채'])}건, 100채 미만 집합: {sum(CNT['순서 100채 미만'].values())}개 {dict(sorted(CNT['순서 100채 미만'].items()))}")
# ⑤ 더하는 값끼리 빼기 (같은 양, 방식끼리 포함)
tot, leaks = 0, {}
same = 0                                                         # 같은 방식 안의 집합만으로도 새는 것
for fam, L in ADD.items():
    sets = sorted({s for _, _, s in L}, key=len)
    who = {}
    for nm, m, s in L:
        who.setdefault(s, set()).add((nm.split("|")[0], m))
    modes_of = {s: {mm for _, mm in w} for s, w in who.items()}
    ids = {k: i for i, k in enumerate(sorted(set().union(*sets)))}
    arr = [np.array(sorted(ids[k] for k in q)) for q in sets]
    for bi, Bs in enumerate(sets):
        subs = [arr[qi] for qi in range(bi) if len(sets[qi]) < len(Bs) and sets[qi] <= Bs]
        if subs and removal_leak(len(Bs), subs, MINC):
            tot += 1
            sm = [arr[qi] for qi in range(bi) if len(sets[qi]) < len(Bs) and sets[qi] <= Bs and modes_of[sets[qi]] & modes_of[Bs]]
            same += bool(sm) and removal_leak(len(Bs), sm, MINC)
            k = (fam[0], fam[1], tuple(sorted({w for w, _ in who[Bs]})), tuple(sorted({mm for _, mm in who[Bs]})))
            leaks[k] = leaks.get(k, 0) + 1
print(f"⑤ 더하는 값끼리 빼면 1~4채 몫: {tot}건 (그중 같은 방식 안의 집합만으로도 새는 것 {same}건, 나머지는 방식끼리)")
for k, n in sorted(leaks.items(), key=lambda x: -x[1])[:15]:
    print(f"    {n:4d}  양={k[0]}·{k[1]}  큰 집합의 칸={'/'.join(k[2])}  방식={'/'.join(k[3])}")
