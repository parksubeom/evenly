# -*- coding: utf-8 -*-
"""
08_sensitivity.py ─ [선택, 4일차 이후] 민감도 분석: "설정값을 바꿔도 결론이 유지되나?"

[왜] 본선 질의응답에서 "보행속도나 내리막 가정을 바꾸면요?" 라는 질문에 숫자로 답하기 위해
[실행] python 08_sensitivity.py      (02, 03 을 먼저 실행. 네트워크는 다시 만들지 않음)
[하는 일] config.SENSITIVITY 의 시나리오마다 설정을 잠시 바꿔 의료시설 기준 HBI 를 다시 계산하고,
          기본 결과와 비교: HBI 중앙값, 1.8 이상 비율, 순위상관(1에 가까울수록 "누가 취약한가"는 그대로),
          상위 10% 취약 건물이 얼마나 겹치는지
[결과] output/sensitivity.csv
[참고] 보행속도를 바꾸면 시간은 달라지지만 HBI(비율)는 거의 그대로입니다 → "지표가 속도 가정에 강건하다"
"""
import os, numpy as np
np.seterr(invalid="ignore", divide="ignore")
import config as C
from lib.qio import log, write_csv
from lib.netload import load
from lib.bload import load_buildings, usable
from lib.qnetwork import edge_slope
from lib.qgraph import spearman
from lib.model import run_scenario

net = load(); b = load_buildings(); U = usable(b)
dest = dict(np.load(os.path.join(C.WORK, "dest_nodes.npz")))
T = "medical" if "medical" in dest else list(dest)[0]
node = b["node"].astype(int); ok = (node >= 0) & U
base = b[f"{T}_hbi"]
hi = C.HBI_BANDS[1]
def stats(h):
    v = ok & np.isfinite(h)
    return float(np.nanmedian(h[v])), float(np.mean(h[v] >= hi)), v
bm, bs, bv = stats(base)
rows = [["기본값", round(bm, 3), round(bs, 3), 1.0, 1.0]]
top0 = bv & (base >= np.nanquantile(base[bv], 0.9))
for name, change in C.SENSITIVITY.items():
    if "SEG_LEN" in change:
        log(f"{name}: 링크 길이 변경은 02 단계부터 다시 돌려야 해서 건너뜀 (config.SEG_LEN 을 바꿔 02·03 재실행)")
        continue
    old = {k: getattr(C, k) for k in change}
    for k, v in change.items(): setattr(C, k, v)          # 설정 임시 변경
    try:
        s = edge_slope(net["z5"], net["e"])[0]             # SLOPE_CLIP 등이 바뀌었을 수 있어 경사 재계산
        r = run_scenario(len(net["nodes"]), net["e"], s, dest[T])
        h = np.full(len(node), np.nan)
        h[ok] = (r["t_elder"][node[ok]] / np.where(r["t_flat"][node[ok]] == 0, np.nan, r["t_flat"][node[ok]]))
        h[ok & (r["t_flat"][np.maximum(node, 0)] == 0)] = 1.0
        m, sh, v = stats(h)
        both = v & bv
        topn = v & (h >= np.nanquantile(h[v], 0.9))
        overlap = (top0 & topn).sum() / max(top0.sum(), 1)
        rows.append([name, round(m, 3), round(sh, 3), round(spearman(base[both], h[both]), 3), round(overlap, 3)])
        log(f"{name}: 중앙값 {m:.3f}, 1.8 이상 {sh:.1%}, 순위상관 {rows[-1][3]}, 상위10% 일치 {overlap:.1%}")
    finally:
        for k, v in old.items(): setattr(C, k, v)          # 원래대로 복구
write_csv(os.path.join(C.OUTPUT, "sensitivity.csv"),
          ["scenario", "hbi_median", f"share_ge_{hi}", "rank_corr_vs_base", "top10_overlap"], rows)
log("완료 → output/sensitivity.csv")
