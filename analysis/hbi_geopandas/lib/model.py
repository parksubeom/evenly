# -*- coding: utf-8 -*-
"""경사 비용 모델과 최단시간 계산 (scipy 희소행렬 Dijkstra, 다중 목적지 일괄)"""
import numpy as np, pandas as pd
from scipy.sparse import csr_matrix
from scipy.sparse.csgraph import dijkstra
import config as C

def tobler(s):
    return 6.0 * np.exp(-3.5 * np.abs(s + 0.05))
FLAT = tobler(0.0)

def elder_time(length, s, stair):
    s = np.where(stair, np.sign(s + 1e-9) * np.maximum(np.abs(s), 0.25), s)  # 계단은 최소 25% 경사로 간주
    up = FLAT / tobler(np.abs(s))                      # 같은 경사를 오를 때의 시간 배수
    down = 1 + C.DOWNHILL_WEIGHT * (up - 1)             # 내리막은 오르막 부담의 일부
    if C.DOWNHILL_WEIGHT == 0:
        down = FLAT / tobler(s)                          # Tobler 원식 (완만한 내리막은 더 빠름)
    factor = np.where(s >= 0, FLAT / tobler(s), down)
    t = length / C.ELDER_SPEED * factor
    t = np.where(stair, t * C.STAIR_FACTOR, t)
    return t

def wheel_time(length, s, stair, stairs_passable=False):
    up = np.maximum(s, 0)
    t = length / (C.WHEEL_SPEED * np.maximum(0.4, 1 - 5 * up))
    t = np.where(np.abs(s) > C.WHEEL_LIMIT, t * C.WHEEL_STEEP_PENALTY, t)
    if not stairs_passable:
        t = np.where(stair, np.inf, t)
    return t

def directed(e, s):
    """무방향 링크 → 정·역방향 (역방향은 경사 부호 반전)"""
    u = np.concatenate([e.u.values, e.v.values]); v = np.concatenate([e.v.values, e.u.values])
    L = np.concatenate([e.length.values] * 2); st = np.concatenate([e.is_stair.values] * 2)
    ss = np.concatenate([s, -s])
    return u, v, L, ss, st

def graph(u, v, w, n):
    ok = np.isfinite(w)
    df = pd.DataFrame({"u": u[ok], "v": v[ok], "w": np.maximum(w[ok], 1e-6)}).groupby(["u", "v"], as_index=False).w.min()
    return csr_matrix((df.w.values, (df.u.values, df.v.values)), shape=(n, n))

def nearest_cost(G, dests):
    """모든 노드 → 가장 가까운 목적지까지 비용(go)과 목적지 → 노드 비용(back)"""
    dests = np.unique(dests)
    back = dijkstra(G, directed=True, indices=dests, min_only=True)
    go = dijkstra(G.T.tocsr(), directed=True, indices=dests, min_only=True)
    return go, back

def run_scenario(nodes_n, e, s, dests, stairs_passable_wheel=False):
    """한 목적지 집합에 대해 노드별 고령자·휠체어 왕복시간과 평지기준 시간 계산"""
    u, v, L, ss, st = directed(e, s)
    res = {}
    Ge = graph(u, v, elder_time(L, ss, st), nodes_n)
    Gf = graph(u, v, L / C.ELDER_SPEED, nodes_n)
    Gw = graph(u, v, wheel_time(L, ss, st, stairs_passable_wheel), nodes_n)
    Gwf = graph(u, v, L / C.WHEEL_SPEED, nodes_n)
    go, back = nearest_cost(Ge, dests); res["t_elder"] = go + back; res["t_elder_back"] = back
    fgo, fback = nearest_cost(Gf, dests); res["t_flat"] = fgo + fback; res["t_flat_back"] = fback
    wgo, wback = nearest_cost(Gw, dests); res["t_wheel"] = wgo + wback
    wfgo, wfback = nearest_cost(Gwf, dests); res["t_wheel_flat"] = wfgo + wfback
    res["dist_net"] = (fgo + fback) / 2 * C.ELDER_SPEED
    return res

def route(nodes_n, e, s, o, d, mode="elder", speed=None, stairs_passable=False):
    """두 노드 간 최단시간 경로의 시간(초)과 경로 길이(m)"""
    u, v, L, ss, st = directed(e, s)
    if mode == "elder":
        w = elder_time(L, ss, st)
        if speed: w = w * C.ELDER_SPEED / speed
    elif mode == "wheel":
        w = wheel_time(L, ss, st, stairs_passable)
    else:
        w = L / (speed or C.ELDER_SPEED)
    G = graph(u, v, w, nodes_n)
    Lg = graph(u, v, L, nodes_n).todok()
    dist, pred = dijkstra(G, directed=True, indices=o, return_predecessors=True)
    if not np.isfinite(dist[d]): return np.nan, np.nan
    length, cur = 0.0, d
    while cur != o:
        p = pred[cur]; length += Lg[p, cur]; cur = p
    return float(dist[d]), float(length)
