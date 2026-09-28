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
import os, sys, numpy as np
import config as C
from lib.qio import log, DEM
from lib.qnetwork import build_edges, edge_slope

os.makedirs(C.WORK, exist_ok=True)
nodes, giant, e = build_edges()

log("DEM 5m 고도 추출")
z5 = DEM(C.DATA_ROOT_DEM).sample(nodes[:, 0], nodes[:, 1])   # nodes[:, 0] = 모든 노드의 x
log(f"  노드 고도 결측 {np.isnan(z5).mean():.1%}")
s5, bad = edge_slope(z5, e)
a = np.abs(s5)
log(f"  경사: 중앙값 {np.median(a):.3f}, 90% {np.percentile(a, 90):.3f}, 절단 {bad.mean():.2%}")

# 저장할 내용. 링크 정보(e)는 "e_" 를 앞에 붙여 한 파일에 같이 저장
save = dict(nodes=nodes, giant=giant, z5=z5, s5=s5, **{f"e_{k}": v for k, v in e.items()})
if "--dem1m" in sys.argv and C.DATA_ROOT_DEM1M:     # sys.argv = 실행할 때 붙인 옵션 목록 (JS의 process.argv)
    log("DEM 1m 고도 추출 (비교용)")
    z1 = DEM(C.DATA_ROOT_DEM1M).sample(nodes[:, 0], nodes[:, 1])
    save["z1"] = z1
    save["s1"] = edge_slope(z1, e)[0]
np.savez_compressed(os.path.join(C.WORK, "network.npz"), **save)
log(f"완료 → work/network.npz (노드 {len(nodes):,}, 링크 {len(e['u']):,})")
