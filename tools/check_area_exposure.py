# -*- coding: utf-8 -*-
"""
tools/check_area_exposure.py ─ 반출 결과의 연면적 칸이 1~4채 몫을 드러내는지 전수 검사 (v6.2, 리허설·시험용. 안심구역에서 돌리는 것이 아님)

[실행]  ~/.evenly_envs/qpy tools/check_area_exposure.py <hbi6 폴더>     (GDAL 있는 파이썬. run_all --modes auto,register,all 을 돌린 폴더)
[하는 일] work/<방식>/buildings_hbi.csv 로 공개된 연면적 값마다 실제 건물 집합을 다시 만들고 (05 summary·grid_hbi·dong_hbi,
        [10/12] 09 intervention_summary·intervention_dong 은 work/<방식>/intervention_sets.npz 의 집합)
        ① 값이 실제 합과 같은지 ② 1~4채 그대로인 값 ③ 같은 단위(summary·격자 칸·동) 안 포함관계 쌍의 차가 1~4채인지
        (목적지끼리·방식끼리, register 는 연면적 원천이 달라 제외) ④ summary − 공개된 동 합 이 1~4채인지 를 셈. 모두 0 이어야 함
[출처] 10/8 scratchpad t62/leak62c.py (05 만) → 10/12 09 를 더해 레포로 옮김
"""
import csv, sys, re, numpy as np
from osgeo import ogr, osr
ogr.UseExceptions()
H6 = sys.argv[1]; MINC = 5; GRID = 250; HI = 1.8
import os as _os
MODES = [m for m in ("layer", "register", "all", "gisbld") if _os.path.exists(f"{H6}/work/{m}/buildings_hbi.csv") and _os.path.exists(f"{H6}/output/{m}/summary.csv")]   # [10/12] 돌린 방식만
if not MODES:
    raise SystemExit(f"{H6}/work/<방식>/buildings_hbi.csv 와 output/<방식>/summary.csv 가 있는 방식이 없음 (run_all --modes 로 돌린 폴더를 주세요)")
def rd(p):
    with open(p, encoding="utf-8-sig") as f: return list(csv.DictReader(f))
fl = lambda s: float(s) if s not in ("", "nan", None) else np.nan
# 건물 (방식마다), 키 = 좌표
B = {}
for m in MODES:
    R = rd(f"{H6}/work/{m}/buildings_hbi.csv")
    B[m] = {"key": [f"{float(r['x']):.2f},{float(r['y']):.2f}" for r in R], "x": np.array([float(r["x"]) for r in R]), "y": np.array([float(r["y"]) for r in R]),
            "w": np.array([float(r["weight"]) for r in R]), "edge": np.array([float(r["edge"] or 0) for r in R]), "rows": R}
# 행정동 소속 (모든 키 합집합)
allk = {}
for m in MODES:
    for k, x, y in zip(B[m]["key"], B[m]["x"], B[m]["y"]): allk[k] = (x, y)
ds = ogr.Open(f"{H6}/external/dong_boundary.geojson"); lyr = ds.GetLayer()
src = lyr.GetSpatialRef(); dst = osr.SpatialReference(); dst.ImportFromEPSG(5186)
for s_ in (src, dst): s_.SetAxisMappingStrategy(osr.OAMS_TRADITIONAL_GIS_ORDER)
ct = osr.CoordinateTransformation(src, dst)
keys = list(allk); XY = np.array([allk[k] for k in keys]); dong_of = {}
pt = ogr.Geometry(ogr.wkbPoint)
for f in lyr:
    g = f.GetGeometryRef().Clone(); g.Transform(ct); e = g.GetEnvelope(); code = str(f.GetField("adm_cd"))
    for i in np.where((XY[:, 0] >= e[0]) & (XY[:, 0] <= e[1]) & (XY[:, 1] >= e[2]) & (XY[:, 1] <= e[3]))[0]:
        if keys[i] in dong_of: continue
        pt.SetPoint_2D(0, XY[i, 0], XY[i, 1])
        if g.Contains(pt): dong_of[keys[i]] = code
W = {m: dict(zip(B[m]["key"], B[m]["w"])) for m in MODES}
BADK = {}
PUB = []   # (단위, 이름, 방식, 집합, 값)
bad_val = 0
def add(unit, name, m, S, val):
    global bad_val
    if val in ("", None): return
    if abs(float(val) - round(sum(W[m][k] for k in S))) > 1:
        bad_val += 1; BADK[(unit[0], name.split(':')[-1], m)] = BADK.get((unit[0], name.split(':')[-1], m), 0) + 1
    PUB.append((unit, name, m, frozenset(S), float(val)))
for m in MODES:
    R = B[m]["rows"]; keyl = B[m]["key"]; edge = B[m]["edge"]
    tg = sorted({c[:-4] for c in R[0] if c.endswith("_hbi") and not c.endswith("_dem1_hbi")})
    S = {(r["target"], r["metric"]): r["value"] for r in rd(f"{H6}/output/{m}/summary.csv")}
    G = rd(f"{H6}/output/{m}/grid_hbi.csv"); D = rd(f"{H6}/output/{m}/dong_hbi.csv")
    gmap = {(r["target"], round(float(r["cell_x"]), 2), round(float(r["cell_y"]), 2)): r for r in G}
    for t in tg:
        H = np.array([fl(r[f"{t}_hbi"]) for r in R]); add_ = (np.array([fl(r[f"{t}_t_elder"]) for r in R]) - np.array([fl(r[f"{t}_t_flat"]) for r in R])) / 60
        v = np.isfinite(H) & (edge < 0.5)
        sv = {keyl[i] for i in np.where(v)[0]}
        add(("summary",), f"{t}:total", m, sv, S.get((t, "분석 건물 연면적 합(㎡)")))
        add(("summary",), f"{t}:high", m, {keyl[i] for i in np.where(v & (H >= HI))[0]}, S.get((t, f"HBI {HI} 이상 건물의 연면적 합(㎡, 고령인구 배분용)")))
        bands = sorted({float(mm.group(1)) for (tt, k) in S if tt == t for mm in [re.match(r"왕복 추가 ([0-9.]+)분 이상 건물의 연면적 합", k)] if mm})
        for bnd in bands:
            add(("summary",), f"{t}:add{bnd:g}", m, {keyl[i] for i in np.where(v & (add_ >= bnd))[0]}, S.get((t, f"왕복 추가 {bnd:g}분 이상 건물의 연면적 합(㎡)")))
        gx, gy = np.floor(B[m]["x"] / GRID).astype(int), np.floor(B[m]["y"] / GRID).astype(int)
        cells = {}
        for i in np.where(v)[0]: cells.setdefault((gx[i], gy[i]), set()).add(keyl[i])
        for (a, c), ss in cells.items():
            r = gmap.get((t, round((a + 0.5) * GRID, 2), round((c + 0.5) * GRID, 2)))
            if r is None: continue
            add(("grid", a, c), f"{t}:weight", m, ss, r["weight"])
            for col in r:
                if col.startswith("weight_add"): add(("grid", a, c), f"{t}:{col}", m, ss, r[col])   # 있으면 안 됨
        if t == ("medical" if "medical" in tg else tg[0]):
            U = edge < 0.5
            # [v6.3] 05 독거노인 추정 (동 × 고립 위험 격자 안 집): 값은 사람 수지만 연면적 비율이 드러나므로 공개 연면적 집합으로 넣음
            #        고립 위험 격자 = 격자 분석 건물 5채 이상 중 집 절반 이상이 왕복 risk_min 분 이상 (lib/bload.risk_cell_mask 와 같음)
            meta_ = {r["key"]: r["value"] for r in rd(f"{H6}/output/{m}/run_meta.csv")} if _os.path.exists(f"{H6}/output/{m}/run_meta.csv") else {}
            rmin = fl(meta_.get("risk_min", "")) if meta_.get("risk_min") else np.nan
            rc_cells = set()
            if np.isfinite(rmin):
                cnt_, rsk_ = {}, {}
                for i in np.where(v)[0]:
                    kc = (gx[i], gy[i]); cnt_[kc] = cnt_.get(kc, 0) + 1; rsk_[kc] = rsk_.get(kc, 0) + (add_[i] >= rmin)
                rc_cells = {kc for kc, n_ in cnt_.items() if n_ >= MINC and rsk_[kc] / n_ >= 0.5}
            for r in D:
                code = r["adm_cd"]; inU = {keyl[i] for i in np.where(U)[0] if dong_of.get(keyl[i]) == code}
                inv = {k for k in sv if dong_of.get(k) == code}
                add(("dong", code), "all", m, inU, r["weight_all"])
                add(("dong", code), "high", m, {keyl[i] for i in np.where(v & (H >= HI))[0] if dong_of.get(keyl[i]) == code}, r["weight_high"])
                if r.get("alone65_riskcell_est") not in ("", None):          # [v6.3]
                    S_ = {keyl[i] for i in np.where(U)[0] if dong_of.get(keyl[i]) == code and (gx[i], gy[i]) in rc_cells}
                    PUB.append((("dong", code), "add_alone_riskcell", m, frozenset(S_), round(sum(W[m][k] for k in S_))))
                for col in r:
                    mm = re.match(r"weight_add([0-9_]+)m$", col)
                    if mm:
                        bnd = float(mm.group(1).replace("_", "."))
                        add(("dong", code), f"add{bnd:g}", m, {keyl[i] for i in np.where(v & (add_ >= bnd))[0] if dong_of.get(keyl[i]) == code}, r[col])
            # [v6.3] 05 종류별 집당 배분 어르신: 고립 위험 연면적을 낸 동들의 그 종류 고립 위험 집 (연면적 비율이 드러나는 집합)
            if np.isfinite(rmin) and "htype" in R[0]:
                tagc = f"weight_add{rmin:g}m".replace(".", "_")
                pubc = {r["adm_cd"] for r in D if r.get(tagc) not in ("", None)}
                ht_ = np.array([int(fl(r["htype"]) or 0) if r["htype"] not in ("", None) else 0 for r in R])
                for lab, codes_ in (("단독·다가구", (1, 2)), ("공동주택", (3, 4, 5))):
                    val_ = next((vv for (tt, k), vv in S.items() if tt == t and f"{lab} 집당 배분 어르신" in k), "")
                    if val_ in ("", None):
                        continue
                    S_ = {keyl[i] for i in np.where(v & (add_ >= rmin) & np.isin(ht_, codes_))[0] if dong_of.get(keyl[i]) in pubc}
                    PUB.append((("summary",), f"add_type_{lab}", m, frozenset(S_), round(sum(W[m][k] for k in S_))))
# [10/12] 09 결과: work/<방식>/intervention_sets.npz 의 건물 집합 + output/<방식>/intervention_*.csv 의 공개 값
import os
NIV = 0
for m in MODES:
    p = f"{H6}/work/{m}/intervention_sets.npz"
    if not os.path.exists(p): continue
    z = np.load(p, allow_pickle=False)
    keys9 = [f"{float(x):.2f},{float(y):.2f}" for x, y in zip(z["x"], z["y"])]
    names = list(z["names"])
    U9 = {k for k, e_ in zip(B[m]["key"], B[m]["edge"]) if e_ < 0.5}
    SS = rd(f"{H6}/output/{m}/intervention_summary.csv"); DD = rd(f"{H6}/output/{m}/intervention_dong.csv")
    rk = [x.split("|") for x in z["rowkey"]] if "rowkey" in z.files else [(str(names.index(r["facility"])), r["target"]) for r in SS]
    dk = [x.split("|") for x in z["drowkey"]] if "drowkey" in z.files else [(str(names.index(r["facility"])), r["target"], "") for r in DD]
    assert len(rk) == len(SS) and len(dk) == len(DD), (p, len(rk), len(SS), len(dk), len(DD))
    for r, key in zip(SS, rk):
        si = int(key[0]); T = key[1]; assert T == r["target"] and names[si] == r["facility"]
        for col, kk in (("weight_benefit", "ben"), ("weight_exit_high", "ex_hi")):
            S_ = {keys9[i] for i in np.where(z[f"s{si}_{T}_{kk}"])[0]}
            add(("summary",), f"iv:{si}:{T}:{kk}", m, S_, r[col]); NIV += r[col] not in ("", None)
    for r, key in zip(DD, dk):
        si = int(key[0]); T = key[1]; code = r["adm_cd"]; assert T == r["target"] and names[si] == r["facility"]
        for col, kk in (("weight_benefit", "ben"), ("weight_exit_high", "ex_hi")):
            S_ = {keys9[i] for i in np.where(z[f"s{si}_{T}_{kk}"])[0] if dong_of.get(keys9[i]) == code}
            add(("dong", code), f"iv:{si}:{T}:{kk}", m, S_, r[col]); NIV += r[col] not in ("", None)
        add(("dong", code), "all", m, {k for k in U9 if dong_of.get(k) == code}, r["weight_all"]); NIV += r["weight_all"] not in ("", None)
print(f"09 공개 연면적 값 {NIV}개 (방식 {[m for m in MODES if os.path.exists(f'{H6}/work/{m}/intervention_sets.npz')]})")
# A·C·D: 같은 단위 안 포함관계 쌍
by = {}
for p in PUB: by.setdefault(p[0], []).append(p)
expo = {"new": [], "old": []}
def is_new(p): return p[1].split(":")[-1].startswith("add") or p[1].startswith("add") or p[1].startswith("iv:")
for unit, L in by.items():
    for i in range(len(L)):
        Si = L[i][3]
        if 0 < len(Si) < MINC: expo["new" if is_new(L[i]) else "old"].append((unit, "단독", L[i][1], L[i][2], len(Si)))
        for j in range(i + 1, len(L)):
            Sj = L[j][3]
            if Si == Sj: continue
            small, big = (Si, Sj) if len(Si) <= len(Sj) else (Sj, Si)
            if L[i][2] != L[j][2] and "register" in (L[i][2], L[j][2]):   # register 는 연면적 원천이 달라 같은 건물 값이 다름 → 빼도 그 채 값이 아님
                continue
            if small <= big and 0 < len(big) - len(small) < MINC:
                kind = "new" if (is_new(L[i]) or is_new(L[j])) else "old"
                expo[kind].append((unit, L[i][1], L[i][2], L[j][1], L[j][2], len(big) - len(small)))
# B: summary − 공개된 동 합 (high, add)
part = []
for m in MODES:
    for (unit, name, mm_, S_, val) in [p for p in PUB if p[0] == ("summary",) and p[2] == m]:
        if ":" not in name:                                            # [v6.3] 종류별 배분 집합 (summary 줄, 동으로 나누지 않음)
            continue
        q = name if name.startswith("iv:") else name.split(":")[1]
        if q not in ("high",) and not q.startswith("add") and not q.startswith("iv:"): continue
        dsets = [p[3] for p in PUB if p[0][0] == "dong" and p[2] == m and p[1] == q]
        if not dsets: continue
        resid = S_ - frozenset().union(*dsets)
        if 0 < len(resid) < MINC: part.append((m, name, len(resid)))
# [10/12] E: 공개 집합 B 에서 서로 겹치지 않는 공개 부분집합 몇 개를 빼면 1~4채가 남는가 (단위·표를 가리지 않음, 같은 방식 안)
combo = []
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "analysis", "hbi"))
from lib.expose import removal_leak                    # 09 와 같은 함수 (묶음별로 정확히 셈)
for m in MODES:
    sets = sorted({p[3] for p in PUB if p[2] == m and len(p[3])}, key=len)
    ids = {k: i for i, k in enumerate(sorted(set().union(*sets)))} if sets else {}
    arr = [np.array(sorted(ids[k] for k in q)) for q in sets]
    for bi, Bs in enumerate(sets):
        subs = [arr[qi] for qi in range(bi) if len(sets[qi]) < len(Bs) and sets[qi] <= Bs]
        if subs and removal_leak(len(Bs), subs, MINC):
            combo.append((m, len(Bs), sorted(len(q) for q in subs)[:12]))
print(f"공개 연면적 값 {len(PUB)}개, 값이 실제 합과 다름 {bad_val}", dict(sorted(BADK.items())[:12]))
print(f"[겹치지 않는 공개 부분집합 합 빼기 (10/12)] {len(combo)}건 {combo[:5]}")
print(f"[새 칸이 낀 노출] {len(expo['new'])}건")
for e in expo["new"][:8]: print("   ", e)
print("   단독(1~4채 그대로):", [e for e in expo["new"] if e[1] == "단독"][:4])
print(f"[summary − 공개 동 합] {len(part)}건 {part[:5]}")
oc = {}
for e in expo["old"]:
    k = ("방식끼리" if e[1] != "단독" and e[2] != e[4] else ("목적지끼리" if e[1] != "단독" and e[1].split(':')[0] != e[3].split(':')[0] else ("단독" if e[1] == "단독" else "같은 줄")), e[0][0])
    oc[k] = oc.get(k, 0) + 1
print(f"[v6 부터 있던 칸끼리 노출] {len(expo['old'])}건: {oc}")
for e in [e for e in expo["old"] if e[0][0] == "dong" or e[1] == "단독"][:6]: print("   ", e)
