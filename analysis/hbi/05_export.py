# -*- coding: utf-8 -*-
"""
05_export.py ─ [5일차] 반출할 결과 만들기 (건물 단위 → 격자·행정동 단위로 묶기)

[실행]  python 05_export.py      (03_hbi.py 다음. 04 와 순서는 상관없음)
[왜 묶나] 개별 건물 결과는 특정 집을 알아볼 수 있어 반출 심사를 통과하기 어렵습니다.
          250m 격자·행정동으로 묶고, 건물이 5개 미만인 격자는 빼서 비식별화합니다.
[결과 파일] (output/ → 이 폴더 전체를 반출 신청)
  summary.csv              : 목적지 종류별 요약 (HBI 중앙값, 1.8 이상 비율 등) → 기획서 16장 숫자
                             [v6.1] + HBI·왕복 추가 시간(분)의 50·75·90·95·99% 분위수 (구간 1.3·1.8 을 다시 볼 때)
                             [v6.2] + 왕복 추가 3·5·10분 이상 건물 비율·수·연면적 (문턱은 mapping.txt 의 extra_min_bands).
                             연면적은 행정동 표와 같은 목적지(의료)·대표 방식만, 빼기로 5채 미만 몫이 드러나면 빈 칸
  grid_hbi.csv             : 250m 격자별 표 (격자 중심 좌표, 건물 수, 평균 HBI ...)
                             [v6.2] 맨 뒤에 문턱마다 n_add3m(왕복 추가 3분 이상 건물 수)·share_add3m(비율). 격자에는 연면적을 내지 않음 (weight 칸도 빈 칸)
  grid_hbi_<종류>.gpkg     : 같은 내용을 지도 파일로 → QGIS에서 색칠해서 결과 지도 제작
  map_<종류>.png           : matplotlib 이 있으면 자동으로 그린 지도 이미지
  dong_hbi.csv             : 행정동별 표 → 07_join_dong.py 가 SKT·KCB 와 결합. weight_all·weight_high 로 밖에서 고령인구 추정 가능
                             [v6.2] 맨 뒤에 n_add3m·share_add3m·weight_add3m (의료 기준, 연면적은 대표 방식만). weight_high·weight_addNm 은
                             band_weights 로 1~4채 몫이 드러나면 빈 칸 (weight_high 를 가리면 elderly_in_high_est 도 빈 칸)
  (모든 통계에서 데이터 경계 EDGE_BUFFER m 이내 건물은 제외)

[matplotlib 이 없을 때 QGIS로 지도 만들기]
  1. QGIS 에서 output/grid_hbi_medical.gpkg 를 끌어다 놓기
  2. 레이어 우클릭 → 속성 → 심볼 → "단일 심볼"을 "단계 구분"으로, 값 = hbi_mean
  3. 색상표를 초록→노랑→주황→빨강으로, 분류 = 1.0 / 1.3 / 1.8 / 2.2
  4. 프로젝트 → 가져오기/내보내기 → "지도를 이미지로 내보내기" → PNG
"""
import lib.runlog as _RL; _RL.start(globals())   # [v6.2] 기록·멈추면 메모 카드 (무거운 import 보다 먼저. lib/runlog.py)
import os, numpy as np
import config as C
from lib.deps import HAS_MPL
from lib.qio import log, write_csv, write_grid_gpkg, find_files, read_csv, iter_layer
from lib.bload import load_buildings, targets, usable
from lib.mapping import band_tag


def band_weights(n_base, ns, ws, force=()):
    """[v6.2] 문턱별 연면적(ws)을 낼지 정함 → 값 또는 빈 칸. ns = 문턱별 건물 수 (문턱이 커질수록 줄어듦), n_base = 같은 묶음에서
    함께 공개되는 전체 연면적의 건물 수. 몇 채의 연면적이 빼기로 드러나지 않게: 0채면 0, 아니면 그 값의 건물 수가 MIN_COUNT 이상이고
    앞에서 낸 값(처음은 전체 연면적)과의 건물 수 차가 0 이거나 MIN_COUNT 이상일 때만 냄 (예: 전체 − 3분 이상, 3분 이상 − 5분 이상 이
    1~4채가 되지 않게). force = 다른 표와의 빼기 때문에 가려야 하는 순번 (summary − 공개된 동 합)"""
    out, prev = [], n_base
    for i, (n_, w_) in enumerate(zip(ns, ws)):
        if n_ == 0:
            out.append(0)
            continue
        ok = i not in force and n_ >= C.MIN_COUNT and (prev - n_ == 0 or prev - n_ >= C.MIN_COUNT)
        out.append(round(float(w_)) if ok else "")
        if ok:
            prev = n_
    return out


def rep_mode():
    """[v6.2] 연면적 칸(왕복 추가 문턱)을 낼 방식 하나. --modes 로 여러 방식을 함께 내면 방식끼리 빼서 몇 채 몫이 드러날 수 있어서
    check 가 고른 방식(없으면 --modes 의 첫 방식)에만 냄. 방식 하나로 돌렸으면 그 방식"""
    if os.path.normpath(C.OUTPUT) == os.path.normpath(os.path.join(C.BASE, "output")):
        return C.BUILDING_ATTR_MODE
    try:
        modes = [m.strip().lower() for m in open(os.path.join(C.WORK_NET, "last_modes.txt"), encoding="utf-8").read().split(",") if m.strip()]
    except OSError:
        modes = []
    ch = (C.MAPPING.get("building_attr_chosen") or "").strip().lower()
    modes = [ch if m == "auto" else m for m in modes]
    return ch if ch in modes else (modes[0] if modes else C.BUILDING_ATTR_MODE)


REP = rep_mode() == C.BUILDING_ATTR_MODE

os.makedirs(C.OUTPUT, exist_ok=True)
b = load_buildings()
X, Y = b["x"], b["y"]
lo, hi = C.HBI_BANDS                              # 1.3, 1.8
U = usable(b)                                     # 데이터 경계 근처 건물은 모든 통계에서 제외
gx = np.floor(X / C.GRID).astype(np.int64)        # 건물별 격자 번호
gy = np.floor(Y / C.GRID).astype(np.int64)
summary, grid_rows = [], []
DT = "medical" if "medical_hbi" in b else (targets(b)[0] if targets(b) else None)   # 행정동 표의 목적지 (연면적 칸도 이 목적지만)
SUMW = {}                                         # [v6.2] DT 의 summary 연면적 줄: 동 집계 뒤 빼기 검사로 다시 정함
V_DT = (np.isfinite(b[f"{DT}_hbi"]) & U) if DT else None

for T in targets(b):                              # 목적지 종류마다 반복 (medical, bus, elderly ...)
    H = b[f"{T}_hbi"]
    v = np.isfinite(H) & U
    # ── 요약 통계 ──
    summary += [[T, "분석 건물 수", int(v.sum())],
                [T, f"경계 {C.EDGE_BUFFER}m 이내라 제외한 건물 수", int((~U).sum())],
                # v5: 아래 세 중앙값도 경계 제외 건물(v)만으로 계산 (v4 는 경계 포함이었음). 이름 끝 "(경계 제외)" 가 v5 표시
                [T, "HBI 중앙값(경계 제외)", round(float(np.nanmedian(H[v])), 3)],
                [T, f"HBI {lo}~{hi} 비율", round(float(np.mean((H[v] >= lo) & (H[v] < hi))), 3)],
                [T, f"HBI {hi} 이상 비율", round(float(np.mean(H[v] >= hi)), 3)],
                [T, f"HBI {hi} 이상 건물 수", int((H[v] >= hi).sum())],
                [T, "귀갓길(목적지→집) 편도 배수 중앙값(경계 제외)", round(float(np.nanmedian(b[f"{T}_home_ratio"][v])), 3)],
                [T, "고령자 왕복 중앙값(분, 경계 제외)", round(float(np.nanmedian(b[f"{T}_t_elder"][v])) / 60, 1)],
                [T, "휠체어 도달불가 비율", round(float(np.mean(~np.isfinite(b[f"{T}_t_wheel"][U]))), 3)],
                # [v6.2] 연면적은 DT(행정동 표와 같은 목적지)만: 목적지끼리 빼면 몇 채 몫이 드러나므로 (의료·약국은 고위험 집합이 거의 같음).
                #        분석 건물 연면적 합은 분석 건물이 DT 와 똑같은 목적지면 같은 값이라 냄, 다르면 빈 칸
                [T, f"HBI {hi} 이상 건물의 연면적 합(㎡, 고령인구 배분용)", band_weights(int(v.sum()), [int((v & (H >= hi)).sum())], [b["weight"][v & (H >= hi)].sum()])[0] if T == DT else ""],
                [T, "분석 건물 연면적 합(㎡)", round(float(b["weight"][v].sum())) if (T == DT or np.array_equal(v, V_DT)) else ""]]
    # [v6.1] 구간(1.3·1.8)을 다시 볼 때 쓰는 분위수: HBI, 왕복 추가 시간(분) = 경사 반영 왕복 - 평지 가정 왕복 (경계 제외).
    #        건물이 QUANT_MIN 개 미만이면 빈 칸 (몇 채로 분위수를 내면 개별 값에 가까워짐)
    add_min = (b[f"{T}_t_elder"] - b[f"{T}_t_flat"]) / 60
    for q in C.QUANTILES:
        hq = round(float(np.quantile(H[v], q / 100)), 3) if v.sum() >= C.QUANT_MIN else ""
        aq = round(float(np.nanquantile(add_min[v], q / 100)), 1) if v.sum() >= C.QUANT_MIN else ""
        summary += [[T, f"HBI {q}% 분위수(경계 제외)", hq], [T, f"왕복 추가 시간(분) {q}% 분위수(경계 제외)", aq]]
    # [v6.2] 왕복 추가 시간(분) 구간: 문턱(mapping.txt 의 extra_min_bands) 이상인 건물 비율·수·연면적 (경계 제외). HBI 1.3·1.8 구간은 위에 그대로
    #        연면적 줄은 행정동 표와 같은 목적지(DT)·대표 방식(REP)만 (목적지끼리·방식끼리 빼서 몇 채가 드러나지 않게), 나머지는 빈 칸
    ges = [v & (add_min >= mb) for mb in C.MIN_BANDS]
    ns_s, ws_s = [int(ge.sum()) for ge in ges], [b["weight"][ge].sum() for ge in ges]
    sw = band_weights(int(v.sum()), ns_s, ws_s) if (T == DT and REP) else [""] * len(ges)
    for mb, ge, w_ in zip(C.MIN_BANDS, ges, sw):
        summary += [[T, f"왕복 추가 {mb:g}분 이상 비율", round(float(ge.sum() / v.sum()), 3) if v.sum() else ""],
                    [T, f"왕복 추가 {mb:g}분 이상 건물 수", int(ge.sum())],
                    [T, f"왕복 추가 {mb:g}분 이상 건물의 연면적 합(㎡)", w_]]
    if T == DT:
        SUMW = {"n_base": int(v.sum()), "ns": ns_s, "ws": ws_s, "rows": [len(summary) - 3 * (len(C.MIN_BANDS) - j) + 2 for j in range(len(C.MIN_BANDS))],
                "n_high": int((H[v] >= hi).sum()), "high_row": next(i for i, r in enumerate(summary) if r[0] == T and r[1].startswith(f"HBI {hi} 이상 건물의 연면적 합"))}
    # ── 격자별 집계 ──
    key = gx[v] * 10**7 + gy[v]
    u, inv = np.unique(key, return_inverse=True)   # u = 격자 목록, inv = 각 건물이 몇 번째 격자인지
    cnt = np.bincount(inv)                         # 격자별 건물 수
    keep = cnt >= C.MIN_COUNT                      # 비식별 기준 통과한 격자
    mean = np.bincount(inv, H[v]) / cnt
    high = np.bincount(inv, (H[v] >= hi).astype(float)) / cnt      # 1.8 이상 건물 비율
    wt = np.bincount(inv, b["weight"][v])                          # 연면적 합
    med = np.array([np.median(H[v][inv == k]) for k in range(len(u))])
    el = np.array([np.nanmedian(b[f"{T}_t_elder"][v][inv == k]) / 60 for k in range(len(u))])
    fl = np.array([np.nanmedian(b[f"{T}_t_flat"][v][inv == k]) / 60 for k in range(len(u))])   # 평지 가정 왕복(분)
    # [v6.2] 격자별 왕복 추가 문턱 이상 건물 수·비율 (연면적은 격자에 내지 않음: 목적지끼리·방식끼리 빼서 몇 채 몫이 드러날 수 있어서)
    am = add_min[v]
    bn = {mb: np.bincount(inv, (am >= mb).astype(float), minlength=len(u)) for mb in C.MIN_BANDS}
    for k in np.where(keep)[0]:
        extra = []
        for mb in C.MIN_BANDS:
            n_ = int(bn[mb][k])
            extra += [n_, round(n_ / cnt[k], 3)]
        grid_rows.append([T, (u[k] // 10**7 + 0.5) * C.GRID, (u[k] % 10**7 + 0.5) * C.GRID, int(cnt[k]),
                          "", round(mean[k], 3), round(med[k], 3), round(high[k], 3), round(el[k], 1), round(fl[k], 1)] + extra)
        # [v6.2] 격자 연면적(weight)은 빈 칸 (v6.1b 와 같음): layer·all 을 함께 내면 같은 칸 weight 차가 비주거 몇 채 연면적이 됨 (v6.1a 리허설 280칸)
    cells = [(int(a // 10**7), int(a % 10**7)) for a in u[keep]]
    write_grid_gpkg(os.path.join(C.OUTPUT, f"grid_hbi_{T}.gpkg"), f"grid_{T}", cells, C.GRID,
                    {"n_bld": cnt[keep], "hbi_mean": mean[keep], "hbi_median": med[keep],
                     "share_high": high[keep], "elder_min": el[keep], "flat_min": fl[keep],
                     **{f"share_{band_tag(mb)}": bn[mb][keep] / cnt[keep] for mb in C.MIN_BANDS}})   # [v6.2] 지도용은 비율만
    # ── 지도 이미지 (matplotlib 이 있을 때만) ──
    if HAS_MPL and not cells:                      # [v6] 비식별 기준을 넘는 격자가 하나도 없으면 그림만 건너뜀 (v5 는 min() 오류로 멈췄음)
        log(f"  {T}: 건물 {C.MIN_COUNT}개 이상인 격자가 없어 map_{T}.png 는 건너뜀")
    if HAS_MPL and cells:
        import matplotlib
        matplotlib.use("Agg")                      # 화면 없이 파일로만 그리기
        import matplotlib.pyplot as plt
        from matplotlib.collections import PatchCollection
        from matplotlib.patches import Rectangle
        from matplotlib.colors import LinearSegmentedColormap
        names = [x.name for x in matplotlib.font_manager.fontManager.ttflist]
        for fnt in ["Malgun Gothic", "NanumGothic", "AppleGothic", "CJK"]:   # 한글 폰트 찾기
            h_ = [n for n in names if fnt in n]
            if h_:
                plt.rcParams["font.family"] = h_[0]
                break
        plt.rcParams["axes.unicode_minus"] = False
        cmap = LinearSegmentedColormap.from_list("hbi", ["#7FA88E", "#F2D16B", "#E8743B", "#B23A2A"])  # 초록→빨강
        fig, ax = plt.subplots(figsize=(8, 8), dpi=150)
        pc = PatchCollection([Rectangle((a * C.GRID, c * C.GRID), C.GRID, C.GRID) for a, c in cells],
                             cmap=cmap, edgecolor="white", linewidth=0.3)
        pc.set_array(mean[keep])
        pc.set_clim(1, 2.2)                        # 색 범위: HBI 1.0(초록) ~ 2.2(빨강)
        ax.add_collection(pc)
        xs = [a for a, _ in cells]
        ys = [c for _, c in cells]
        ax.set_xlim(min(xs) * C.GRID, (max(xs) + 1) * C.GRID)
        ax.set_ylim(min(ys) * C.GRID, (max(ys) + 1) * C.GRID)
        ax.set_aspect("equal"); ax.set_xticks([]); ax.set_yticks([])
        plt.colorbar(pc, ax=ax, shrink=0.6, label="언덕 부담 지수 (HBI)")
        ax.set_title(f"{C.GRID}m 격자 평균 HBI · 목적지: {T}")
        fig.savefig(os.path.join(C.OUTPUT, f"map_{T}.png"), bbox_inches="tight")
        plt.close(fig)

write_csv(os.path.join(C.OUTPUT, "grid_hbi.csv"),
          ["target", "cell_x", "cell_y", "n_bld", "weight", "hbi_mean", "hbi_median", "share_high", "elder_min", "flat_min"]
          + [f"{p_}_{band_tag(mb)}" for mb in C.MIN_BANDS for p_ in ("n", "share")], grid_rows)
# [v6] 실행 정보: output/run_meta.csv (대상 구, 건물 용도 방식, 연결률, 범위). summary.csv 에는 뜻이 바뀌는 경우에만 meta 행
from lib.battr import load_stats
st = load_stats()
if os.environ.get("HBI_SUBRUN"):                  # [v6] --modes 로 돌린 결과: 어느 방식인지 summary 에 남김 (기획서 파이프라인이 고를 때 씀)
    summary.append(["meta", "건물 용도 방식", C.BUILDING_ATTR_MODE])
if st.get("mode") == "all":
    summary.append(["meta", "건물 용도", "용도 미구분 (모든 건물을 집으로 봄, 의료·노유자 건물 목적지 없음)"])
if C.TARGET_GU and st.get("n_res_all", 0) > st.get("n_res_target", 0):
    summary.append(["meta", "대상 구 (출발점은 이 구의 집만, 옆 구는 길·목적지로만)", ",".join(C.TARGET_GU)])
if getattr(C, "TARGET_NOTE", ""):                 # [v6.1] 자료가 일부 구만 덮어 대상 구를 줄였을 때 (예: 대상 5개 구 중 1개 구만 자료 있음)
    summary.append(["meta", "대상 구 범위", C.TARGET_NOTE])
write_csv(os.path.join(C.OUTPUT, "run_meta.csv"), ["key", "value"], [
    ["target_gu", ",".join(C.TARGET_GU) or "(전체)"], ["neighbor_gu", ",".join(C.NEIGHBOR_GU)],
    ["target_gu_all", ",".join(getattr(C, "TARGET_GU_ALL", []))], ["target_note", getattr(C, "TARGET_NOTE", "")],
    ["building_attr_mode", st.get("mode", C.BUILDING_ATTR_MODE)],
    ["register_link_rate", st.get("link_rate", "")], ["register_join", st.get("register_join", "")], ["register_join_used", st.get("join_used", "")],
    ["register_rate_pnu", st.get("rate_pnu", "")], ["register_rate_pk", st.get("rate_pk", "")],
    ["ufid_match_rate", "" if st.get("rate_ufid") is None else st.get("rate_ufid")],
    ["n_residential_read", st.get("n_res_all", "")], ["n_residential_target", st.get("n_res_target", "")],
    ["area_bbox", C.AREA_BBOX if C.AREA_BBOX else "None"], ["area_reason", C.AREA_REASON], ["map_folders", len(C.MAP_FOLDERS)]])
if not HAS_MPL:
    log("matplotlib 없음 → QGIS에서 output/grid_hbi_*.gpkg 를 열어 hbi_mean 으로 색칠 후 이미지로 내보내기 (파일 맨 위 설명 참고)")

# ── 행정동 집계 ────────────────────────────────────────────
bd = find_files(C.EXTERNAL, ["dong_boundary"], ".geojson") + find_files(C.EXTERNAL, ["dong_boundary"], ".shp")
if bd:
    T = "medical" if "medical_hbi" in b else targets(b)[0]
    H = b[f"{T}_hbi"]
    v = np.isfinite(H) & U
    add_d = (b[f"{T}_t_elder"] - b[f"{T}_t_flat"]) / 60            # [v6.2] 왕복 추가 시간(분)
    polys = [(g, a) for g, a in iter_layer(files=bd[:1], bbox=None)]       # 행정동 경계 폴리곤
    ck = next(k for k in polys[0][1] if k.upper() in ("ADM_CD", "ADM_DR_CD", "ADSTRD_CD", "CODE"))   # 동 코드 열 이름
    nk = next((k for k in polys[0][1] if k.upper() in ("ADM_NM", "NAME")), None)                    # 동 이름 열 이름
    sk = next((k for k in polys[0][1] if k.upper() == "ADM_CD_STAT"), None)                        # 통계청 코드(있으면)
    from lib.qnetwork import points_in_polygons
    # 분석 범위와 겹치는 동만 추림 (서울 426개 중 5개 구 부근만)
    bx0, bx1, by0, by1 = np.nanmin(X), np.nanmax(X), np.nanmin(Y), np.nanmax(Y)
    polys = [p for p in polys if not (p[0].GetEnvelope()[1] < bx0 or p[0].GetEnvelope()[0] > bx1 or
                                      p[0].GetEnvelope()[3] < by0 or p[0].GetEnvelope()[2] > by1)]
    _, which = points_in_polygons(X, Y, polys)     # 건물마다 몇 번째 동에 있는지
    # 고령인구(선택): external/elderly_pop.csv 에 adm_cd, pop65 가 있으면 "HBI 1.8 이상 집에 사는 고령자 수" 추정
    pop = {r["adm_cd"]: float(r["pop65"]) for r in read_csv(os.path.join(C.EXTERNAL, "elderly_pop.csv")) if r.get("pop65")}
    rows, total = [], 0
    pub_high, pub_band = [], [[] for _ in C.MIN_BANDS]      # [v6.2] 연면적을 낸 동의 건물 수 (summary 와 빼기 검사용)
    for k, (g, a) in enumerate(polys):
        m = v & (which == k)
        if m.sum() < C.MIN_COUNT:
            continue
        code = str(a[ck])
        n_all = int(((which == k) & U).sum())                # weight_all 이 덮는 건물 수 (가림 기준)
        wall = b["weight"][(which == k) & U].sum()            # 동 전체 주거 연면적 (경계 제외)
        n_high = int((m & (H >= hi)).sum())
        whigh = b["weight"][m & (H >= hi)].sum()              # 그중 HBI 1.8 이상 건물의 연면적
        wh_pub = band_weights(n_all, [n_high], [whigh])[0]    # [v6.2] 1~4채 몫이 드러나면 빈 칸 (v6.1a 까지는 그대로 냈음)
        est = round(pop[code] * whigh / wall) if code in pop and wall > 0 and wh_pub != "" else ""   # 고령인구 × 연면적 비율 (가렸으면 빈 칸)
        if est != "":
            total += est
        if wh_pub != "":
            pub_high.append(n_high)
        extra = []                                           # [v6.2] 격자와 같은 n·share + 연면적 (대표 방식만, band_weights)
        ges = [m & (add_d >= mb) for mb in C.MIN_BANDS]
        ns = [int(ge.sum()) for ge in ges]
        wb = band_weights(n_all, ns, [b["weight"][ge].sum() for ge in ges]) if REP else [""] * len(ges)
        for j, (n_, w_) in enumerate(zip(ns, wb)):
            extra += [n_, round(float(n_ / m.sum()), 3), w_]
            if w_ != "":
                pub_band[j].append(n_)
        rows.append([code, str(a.get(sk, "")) if sk else "", a.get(nk, "") if nk else "", int(m.sum()), round(float(H[m].mean()), 3),
                     round(float(np.mean(H[m] >= hi)), 3), round(float(wall)), wh_pub, est] + extra)
    write_csv(os.path.join(C.OUTPUT, "dong_hbi.csv"),
              ["adm_cd", "adm_cd_stat", "adm_nm", "n_bld", "hbi_mean", "share_high", "weight_all", "weight_high", "elderly_in_high_est"]
              + [f"{p_}_{band_tag(mb)}" for mb in C.MIN_BANDS for p_ in ("n", "share", "weight")], rows)
    # weight_all/weight_high 를 함께 반출하므로, 고령인구 파일이 없어도 밖에서
    #   고령인구 추정 = pop65 × weight_high ÷ weight_all  로 계산할 수 있습니다
    log(f"→ output/dong_hbi.csv (행정동 {len(rows)}개" + (f", HBI {hi} 이상 거주 고령인구 추정 약 {int(total):,}명)" if pop else ")"))
    # [v6.2] summary 의 DT 연면적 − 공개된 동 연면적 합 = 가린 동(과 5채 미만 동) 몫. 그 건물 수가 1~4 이면 summary 쪽도 가림
    if SUMW:
        hid = SUMW["n_high"] - sum(pub_high)
        if 0 < hid < C.MIN_COUNT:
            summary[SUMW["high_row"]][2] = ""
        if REP:
            force = set()
            for _ in range(len(C.MIN_BANDS) + 1):                 # 하나를 가리면 다음 문턱의 비교 대상이 바뀌므로 바뀌지 않을 때까지
                sw = band_weights(SUMW["n_base"], SUMW["ns"], SUMW["ws"], force)
                new = {j for j in range(len(sw)) if sw[j] not in ("", 0) and 0 < SUMW["ns"][j] - sum(pub_band[j]) < C.MIN_COUNT}
                if new <= force:
                    break
                force |= new
            for j, ri in enumerate(SUMW["rows"]):
                summary[ri][2] = sw[j]
write_csv(os.path.join(C.OUTPUT, "summary.csv"), ["target", "metric", "value"], summary)   # [v6.2] 동 집계 뒤에 씀 (위의 빼기 검사)
log("summary:")
for r in summary:
    print("   ", r)
log("완료 → output/ (반출 신청 대상)")
