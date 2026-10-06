# -*- coding: utf-8 -*-
"""
lib/rcheck.py ─ [v6] 결과 점검표: run_all 이 끝나면 핵심 집계를 기대 범위와 비교해 [초록]·[노랑]·[빨강] 으로 보임

[왜]  안에서 한 번 돌리고 결과를 받기까지 5~7일. 반출하기 전에 "쓸 수 있는 결과인가" 를 그 자리에서 판단해야 함.
[기대 범위의 근거]  docs/결과점검_기준.md 에 자세히. 요약:
  주거 비율      : 서울시 건축물대장 표제부 주용도 — 서울 72.7%, 대상 8개 구 70.9% (단독·공동·다가구주택)
  대장 연결률    : gisbld·register 를 고르는 기준과 같은 80% (setup·check 의 자동 선택 기준)
  노드 비율      : 02 화면의 기준 "90% 이상이면 정상"
  길 연결        : 03 화면의 기준 "95% 이상이면 정상" (집에서 60m 안에 길)
  경계 제외      : 자료가 5개 구뿐이면 대상 구 면적의 최대 약 55% 가 자료 가장자리 500m 안 (구 경계로 잰 상한),
                   옆 구·수도권까지 있으면 거의 0%
  HBI 중앙값     : 공개 도보 네트워크 + 공개 지형으로 같은 모델을 돌린 대조군(250m 격자 1,587칸, 역 기준) 중앙값 1.17, 10~90% 1.09~1.35
  고위험(≥1.8)   : 같은 대조군 0.4%. 건물 단위는 격자 평균보다 퍼지므로 넉넉히
  선정지 백분위  : 서울시가 언덕 때문에 고른 곳이라 높게 나와야 맞음. 낮으면 노랑(데이터·좌표 확인), 계산 자체가 안 되면 빨강
[저장]  output/result_check.txt (집계·비율만, 값 없음)
"""
import os, csv, json
import numpy as np
import config as C

G, Y, R = "[초록]", "[노랑]", "[빨강]"

# 지표: (이름, 초록 범위, 노랑 범위) — 범위 밖이면 빨강. None = 그쪽 한계 없음
RANGES = {
    "주거 비율": ((0.55, 0.85), (0.35, 0.97)),
    "대장 연결률": ((0.80, None), (0.50, None)),
    "노드 비율": ((0.90, None), (0.70, None)),
    "길 연결": ((0.95, None), (0.80, None)),
    "경계 제외": ((None, 0.25), (None, 0.60)),
    "HBI 중앙값": ((1.03, 1.40), (1.00, 1.80)),
    "고위험 비율": ((None, 0.15), (None, 0.35)),
}
# 빨강일 때: (원인 후보, 고칠 곳, 다시 돌릴 단계)
FIX = {
    "주거 비율": ("건물 용도를 못 붙였거나 용도 코드가 다름", "mapping.txt 의 building_attr_mode, bld_use (config 의 RESIDENTIAL_USE)", "03"),
    "대장 연결률": ("필지·대장 번호 체계가 다르거나 필지 칸 이름이 틀림", "mapping.txt 의 parcel_id, register_join, reg_pnu (안 되면 building_attr_mode = gisbld 또는 all)", "03"),
    "노드 비율": ("길 폴더가 빠졌거나 길이 조각나 있음", "mapping.txt 의 map_folders, layer_road_cl·layer_sidewalk_cl (python setup.py 다시)", "02"),
    "길 연결": ("집 가까이에 길이 없음: 길 레이어가 빠졌거나 좌표계가 어긋남", "mapping.txt 의 layer_road_cl·map_folders, config 의 DEFAULT_CRS", "02"),
    "경계 제외": ("자료 가장자리 집이 너무 많음: 옆 구 자료가 빠짐", "mapping.txt 의 map_folders 에 옆 구 폴더 넣기 (python setup.py 다시), AREA_BBOX", "02"),
    "HBI 중앙값": ("경사가 이상함: DEM 이 안 맞거나 좌표계가 어긋남", "config 의 DATA_ROOT_DEM, DEFAULT_CRS (python check.py 의 DEM 줄)", "02"),
    "고위험 비율": ("경사가 지나치게 큼: DEM 단위·좌표계 확인", "config 의 DATA_ROOT_DEM, DEFAULT_CRS", "02"),
    "목적지": ("의료시설 결과가 없음: 건물 용도가 비었거나 약국 파일이 없음", "mapping.txt 의 building_attr_mode, external/pharmacy.csv", "03"),
    "선정지": ("선정지 5곳 중 계산된 곳이 없음: 대상 구 범위·좌표 확인", "mapping.txt 의 target_gu, config 의 AREA_BBOX, external/sites.csv", "04"),
}


def grade(name, v):
    if v is None or (isinstance(v, float) and not np.isfinite(v)):
        return R
    (g0, g1), (y0, y1) = RANGES[name]
    inside = lambda lo, hi: (lo is None or v >= lo) and (hi is None or v <= hi)
    return G if inside(g0, g1) else (Y if inside(y0, y1) else R)


def _csv(p):
    if not os.path.exists(p):
        return []
    with open(p, encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def _num(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


def rows(out=None, work=None, net_work=None):
    """[(등급, 지표, 값 글자, 기대 글자)] 와 빨강 지표 목록"""
    out, work, net_work = out or C.OUTPUT, work or C.WORK, net_work or getattr(C, "WORK_NET", C.WORK)
    R_ = []
    try:
        st = json.load(open(os.path.join(work, "battr_stats.json"), encoding="utf-8"))
    except (OSError, ValueError):
        st = {}
    mode = st.get("mode", C.BUILDING_ATTR_MODE)
    nb, nres = st.get("n_bld_read") or st.get("n_bld"), st.get("n_res_all")
    if mode != "all" and nb:
        v = nres / nb if nres is not None else None
        R_.append(("주거 비율", v, f"{v:.1%} ({nres:,}/{nb:,})" if v is not None else "-"))
    if mode in ("register", "gisbld"):
        v = st.get("link_rate")
        R_.append(("대장 연결률", v, f"{v:.1%} ({'건물 겹침' if mode == 'gisbld' else st.get('join_used', '')})" if v is not None else "-"))
    try:
        z = np.load(os.path.join(net_work, "network.npz"))
        v = float(z["giant"].mean())
        R_.append(("노드 비율", v, f"{v:.1%}"))
    except (OSError, KeyError, ValueError):
        R_.append(("노드 비율", None, "network.npz 없음"))
    b = _csv(os.path.join(work, "buildings_hbi.csv"))
    if b:
        node = np.array([_num(r.get("node")) if r.get("node") != "" else -1 for r in b], float)
        edge = np.array([_num(r.get("edge")) or 0.0 for r in b], float)
        R_.append(("길 연결", float(np.mean(node >= 0)), f"{np.mean(node >= 0):.1%} (집 {len(b):,}채)"))
        R_.append(("경계 제외", float(np.mean(edge > 0.5)), f"{np.mean(edge > 0.5):.1%}"))
    summ = _csv(os.path.join(out, "summary.csv"))
    tg = {}
    for r in summ:
        tg.setdefault(r["target"], {})[r["metric"]] = r["value"]
    for t in [t for t in tg if t != "meta"]:
        m = tg[t]
        med = next((_num(v) for k, v in m.items() if k.startswith("HBI 중앙값")), None)
        hi = next((_num(v) for k, v in m.items() if k.startswith(f"HBI {C.HBI_BANDS[1]} 이상 비율")), None)
        n = _num(m.get("분석 건물 수"))
        R_.append((f"HBI 중앙값", med, f"{t}: {med}" if med is not None else f"{t}: -", t))
        R_.append((f"고위험 비율", hi, f"{t}: {hi:.1%} (건물 {int(n or 0):,})" if hi is not None else f"{t}: -", t))
    return R_, tg, mode


def report(out=None, work=None, net_work=None):
    out = out or C.OUTPUT
    R_, tg, mode = rows(out, work, net_work)
    L, reds = [f"=== 결과 점검표 (방식 {mode}) — {G} 기대 범위 / {Y} 확인 필요 / {R} 다시 돌리기 ==="], []
    for item in R_:
        name, v, txt = item[0], item[1], item[2]
        gr = grade(name, v)
        (g0, g1), _ = RANGES[name]
        exp = (f"{g0:.0%}" if g0 is not None and g0 < 1 else (f"{g0}" if g0 is not None else "")) + "~" + \
              (f"{g1:.0%}" if g1 is not None and g1 < 1 else (f"{g1}" if g1 is not None else ""))
        L.append(f"  {gr} {name}: {txt}   (기대 {exp})")
        if gr == R:
            reds.append(name)
    # 목적지: 의료(medical) 결과가 있어야 핵심 결과가 나옴. 나머지는 없으면 노랑
    have = [t for t in tg if t != "meta"]
    for t in ("medical", "bus", "station", "station_ev", "pharmacy", "elderly"):
        if t in have:
            L.append(f"  {G} 목적지 {t}: 분석 건물 {int(_num(tg[t].get('분석 건물 수')) or 0):,}")
        else:
            gr = R if t == "medical" else Y
            L.append(f"  {gr} 목적지 {t}: 결과 없음" + (" (핵심 목적지)" if t == "medical" else " (레이어·파일이 없으면 정상)"))
            if gr == R:
                reds.append("목적지")
    sites = _csv(os.path.join(out, "validation_sites.csv"))
    pct = [(_num(r.get("percentile_circle")) or _num(r.get("percentile")), r.get("name", "")) for r in sites]
    got = [(p, n) for p, n in pct if p is not None]
    if not sites:
        L.append(f"  {Y} 선정지: validation_sites.csv 없음 (04 결과 확인)")
    elif not got:
        L.append(f"  {R} 선정지: {len(sites)}곳 모두 계산 안 됨"); reds.append("선정지")
    else:
        high = sum(1 for p, _ in got if p >= 0.7)
        gr = G if high >= max(1, len(got) // 2 + 1) else Y
        L.append(f"  {gr} 선정지 백분위: 계산 {len(got)}/{len(sites)}곳, 70% 이상 {high}곳 ("
                 + ", ".join(f"{n.split()[-1] if n else '?'} {p:.0%}" for p, n in got) + ")")
    if reds:
        L.append(f"\n{R} 다시 돌리기 전에 고칠 것:")
        for k in dict.fromkeys(reds):
            why, todo, step = FIX[k]
            L.append(f"  - {k}: {why}\n      → {todo}\n      → 고친 뒤: python run_all.py --from {step}")
        first = min(FIX[k][2] for k in dict.fromkeys(reds))
        L.append(f"  여러 개면 모두 고친 뒤 한 번에: python run_all.py --from {first}")
    else:
        L.append(f"\n빨강 없음 → 이 결과로 반출 가능 (노랑은 메모)")
    txt = "\n".join(L)
    os.makedirs(out, exist_ok=True)
    with open(os.path.join(out, "result_check.txt"), "w", encoding="utf-8-sig") as f:
        f.write(txt + "\n")
    return txt, reds
