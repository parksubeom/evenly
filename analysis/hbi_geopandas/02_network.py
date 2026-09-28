# -*- coding: utf-8 -*-
"""
[2일차] 보행 네트워크 구축 + DEM 경사 산출
 결과: work/network.pkl (노드, 링크, 노드 고도, 링크 경사)
 옵션: python 02_network.py --dem1m  → DEM 1m 고도도 추가 계산 (비교 분석용)
"""
import os, sys, pickle, numpy as np
import config as C
from lib.io_utils import log, DEM
from lib.network import build_edges, attach_z, edge_slope

os.makedirs(C.WORK, exist_ok=True)
nodes, e = build_edges()
log("DEM 5m 고도 추출")
z5 = attach_z(nodes, DEM(C.DATA_ROOT_DEM))
s5, bad = edge_slope(z5, e)
log(f"  경사 분포: 중앙값 {np.median(np.abs(s5)):.3f}, 90% {np.percentile(np.abs(s5), 90):.3f}, 절단 {bad.mean():.2%}")
net = {"nodes": nodes, "edges": e, "z": {"dem5": z5}, "slope": {"dem5": s5}}
if "--dem1m" in sys.argv and C.DATA_ROOT_DEM1M:
    log("DEM 1m 고도 추출 (비교용)")
    z1 = attach_z(nodes, DEM(C.DATA_ROOT_DEM1M))
    net["z"]["dem1"] = z1; net["slope"]["dem1"], _ = edge_slope(z1, e)
with open(os.path.join(C.WORK, "network.pkl"), "wb") as f:
    pickle.dump(net, f)
log(f"완료 → work/network.pkl  (노드 {len(nodes):,}, 링크 {len(e):,})")
