# -*- coding: utf-8 -*-
"""
02_network.py ─ [2일차] 보행 네트워크 만들기 + DEM 으로 경사 계산

[실행]  python 02_network.py          (DEM 1m 비교도 하려면: python 02_network.py --dem1m)
[하는 일]
  1. 수치지형도로 길 네트워크를 만듦 (자세한 과정은 lib/qnetwork.py 맨 위 설명)
  2. 모든 노드(교차점·30m 간격 점)의 높이를 DEM 에서 읽음
  3. 링크마다 경사 = 높이차 ÷ 길이 계산
[결과] work/network.npz  (다음 단계들이 불러 씀)
[화면에서 확인할 것]
  - "최대 연결망 노드 비율" 90% 이상  (낮으면 config.BRIDGE_TOL 을 15로)
  - "노드 고도 결측" 5% 이하         (높으면 DEM 범위가 수치지형도와 안 맞는 것 → DEM 경로·좌표계 확인)
  - "경사 중앙값" 0.01~0.08 정도      (0.3 이상이면 좌표계가 어긋났을 가능성)
"""
import lib.runlog as _RL; _RL.start(globals())   # [v6.2] 기록·멈추면 메모 카드 (무거운 import 보다 먼저. lib/runlog.py)
import os, sys, numpy as np
import config as C
from lib.qio import log, DEM
from lib.qnetwork import build_edges, edge_slope, LAST as NET

os.makedirs(C.WORK_NET, exist_ok=True)
nodes, giant, e = build_edges()

log("DEM 5m 고도 추출")
d5 = DEM(C.DATA_ROOT_DEM)
z5 = d5.sample(nodes[:, 0], nodes[:, 1])   # nodes[:, 0] = 모든 노드의 x
log(f"  노드 고도 결측 {np.isnan(z5).mean():.1%}")
# [v6.1] sample 은 DEM 범위 밖 노드를 가장자리 값으로 채움 (그래서 위 결측은 0% 로 나오기 쉬움) → 범위 밖 노드 비율을 따로 보임 (값은 그대로)
out5 = ~d5.covers(nodes[giant, 0], nodes[giant, 1])
log(f"  DEM 5m 범위 밖 노드 {out5.mean():.1%}" + ("  ← 0% 가 아니면 그곳 경사가 평지에 가깝게 계산됨: DEM 폴더에 대상 구 도엽이 다 있는지 확인" if out5.any() else ""))
s5, bad = edge_slope(z5, e)
a = np.abs(s5)
log(f"  경사: 중앙값 {np.median(a):.3f}, 90% {np.percentile(a, 90):.3f}, 절단 {bad.mean():.2%}")

# 저장할 내용. 링크 정보(e)는 "e_" 를 앞에 붙여 한 파일에 같이 저장
save = dict(nodes=nodes, giant=giant, z5=z5, s5=s5, **{f"e_{k}": v for k, v in e.items()})
# [v6.1] 걸을 수 없는 길을 뺐으면: 비교용 "빼지 않은 네트워크"(v5 방식, 같은 노드)를 x_ 를 붙여 함께 저장 → 03·04 가 HBI 변화를 봄
wa = NET.get("walkall")
if wa:
    save.update(xgiant=wa["giant"], xs5=edge_slope(z5, wa["e"])[0], node_use=NET["node_use"], **{f"x_{k}": v for k, v in wa["e"].items()})
w = NET.get("walk") or {}
save["walk_excl"] = np.array([w.get("lines", 0), w.get("links", 0)])   # 뺀 선 수, 뺀 링크 수 (04 가 적음)
if C.DATA_ROOT_DEM1M and ("--dem1m" in sys.argv or getattr(C, "DEM1M_AUTO", False)):   # sys.argv = 실행할 때 붙인 옵션 목록
    log("DEM 1m 고도 추출 (비교용)")
    d1 = DEM(C.DATA_ROOT_DEM1M)
    z1 = d1.sample(nodes[:, 0], nodes[:, 1])
    c1 = d1.covers(nodes[:, 0], nodes[:, 1])         # [v6.1] 1m 범위 안 노드 (sample 은 범위 밖을 가장자리 값으로 채움)
    s1 = edge_slope(z1, e)[0]
    in1 = c1[e["u"]] & c1[e["v"]]
    s1 = np.where(in1, s1, s5)                        # 1m 가 없는 링크는 5m 경사 (비교는 1m 범위 안 집만: 03·04·08)
    log(f"  1m 범위 안: 노드 {c1[giant].mean():.1%}, 링크 {in1.mean():.1%} (범위 밖 링크는 5m 경사로 채움)")
    save["z1"] = z1
    save["s1"] = s1
    save["c1"] = c1
np.savez_compressed(os.path.join(C.WORK_NET, "network.npz"), **save)   # [v6] 방식이 여럿이어도 한 번만
log(f"완료 → work/network.npz (노드 {len(nodes):,}, 링크 {len(e['u']):,})")
