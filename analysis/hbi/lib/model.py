# -*- coding: utf-8 -*-
"""
lib/model.py ─ "경사가 있으면 얼마나 더 오래 걸리나"를 계산하는 모델

[핵심 아이디어]
 길을 30m 조각(링크)으로 나누고, 조각마다
     걸리는 시간 = 길이 ÷ 속도 × 경사 배수
 를 계산합니다. 경사 배수는 평지면 1.0, 가파를수록 커집니다.

[Tobler 보행함수]
 등산·보행 연구에서 널리 쓰는 공식: 속도(km/h) = 6 × e^(-3.5 × |경사 + 0.05|)
 경사(s)는 "높이 차 ÷ 수평 거리". 10% 오르막이면 s = 0.10, 내리막이면 음수.
 평지(s=0)에서 약 5.0km/h, 12% 오르막에서 약 3.3km/h → 평지보다 1.5배 오래 걸림

[배열 계산에 대해]
 아래 함수들의 인자(length, s, stair)는 숫자 하나가 아니라 "배열"입니다.
 numpy 덕분에 반복문 없이 수십만 개 링크를 한 줄로 계산합니다.
   예) length / 0.8  → 모든 링크 길이를 한꺼번에 0.8로 나눈 새 배열
"""
import numpy as np
import config as C
from lib.qgraph import Graph


def tobler(s):
    """경사 s(배열) → 보행속도 km/h (배열)"""
    return 6.0 * np.exp(-3.5 * np.abs(s + 0.05))

FLAT = tobler(0.0)   # 평지 속도 (약 5.04 km/h). 이것과 비교해서 "몇 배 느린지"를 구함


def elder_time(length, s, stair):
    """고령자가 각 링크를 지나는 데 걸리는 시간(초).
    length: 링크 길이(m), s: 진행 방향 경사, stair: 계단이면 True"""
    # 계단은 DEM(5m 격자)이 실제보다 완만하게 잡는 경우가 많아, 최소 25% 경사로 간주
    #   np.sign(s) = 부호(+1/-1). 1e-9 를 더한 건 s=0 일 때 부호가 0이 되지 않게 하려는 것
    s = np.where(stair, np.sign(s + 1e-9) * np.maximum(np.abs(s), 0.25), s)
    up = FLAT / tobler(np.abs(s))                # 같은 경사를 "오를 때" 몇 배 느린지
    down = 1 + C.DOWNHILL_WEIGHT * (up - 1)      # 내리막은 오르막 부담의 일부(기본 50%)만큼 느림
    if C.DOWNHILL_WEIGHT == 0:
        down = FLAT / tobler(s)                   # 0으로 설정하면 Tobler 원래 공식(완만한 내리막은 더 빠름)
    factor = np.where(s >= 0, FLAT / tobler(s), down)   # 오르막이면 오르막 배수, 내리막이면 내리막 배수
    t = length / C.ELDER_SPEED * factor           # 시간 = 거리 ÷ 평지속도 × 배수
    t = np.where(stair, t * C.STAIR_FACTOR, t)    # 계단이면 추가로 1.2배
    return t


def wheel_time(length, s, stair, stairs_passable=False):
    """휠체어가 각 링크를 지나는 시간(초). 계단은 통과 불가(무한대)"""
    up = np.maximum(s, 0)                          # 오르막 경사만 (내리막은 0으로)
    t = length / (C.WHEEL_SPEED * np.maximum(0.4, 1 - 5 * up))       # 오르막일수록 느려짐 (최저 40% 속도)
    t = np.where(np.abs(s) > C.WHEEL_LIMIT, t * C.WHEEL_STEEP_PENALTY, t)   # 8.3% 넘으면 10배 (사실상 회피)
    if not stairs_passable:                        # stairs_passable=True 는 "계단 정보가 없다면?" 비교 실험용
        t = np.where(stair, np.inf, t)             # 계단 = 무한대 = 못 지나감
    return t


def directed(e, s):
    """링크 하나(u–v)를 양방향 간선 두 개로 만듦: u→v 는 경사 s, v→u 는 경사 -s (오르막↔내리막)
    e: 링크 정보 딕셔너리 {"u": 배열, "v": 배열, "length": 배열, "is_stair": 배열}
    np.concatenate([A, B]) = 배열 이어붙이기 (JS의 [...A, ...B])"""
    u = np.concatenate([e["u"], e["v"]])
    v = np.concatenate([e["v"], e["u"]])
    L = np.concatenate([e["length"]] * 2)
    st = np.concatenate([e["is_stair"]] * 2)
    return u, v, L, np.concatenate([s, -s]), st


def run_scenario(n, e, s, dests, stairs_passable_wheel=False):
    """목적지 집합(dests: 노드 번호 배열)에 대해, 모든 노드에서의 왕복 시간을 4가지 방식으로 계산.

    반환 딕셔너리 (각 값은 길이 n 배열, 단위 초):
      t_elder      : 고령자, 경사 반영, 왕복 (집→가장 가까운 목적지→집)
      t_flat       : 고령자, 평지라고 가정, 왕복       ← HBI = t_elder ÷ t_flat
      t_wheel      : 휠체어, 경사·계단 반영, 왕복
      t_wheel_flat : 휠체어, 평지 가정, 왕복
      t_elder_back, t_flat_back : 귀갓길(목적지→집) 편도만
      dist_net     : 네트워크 상 편도 거리(m)
    """
    u, v, L, ss, st = directed(e, s)
    res = {}
    for name, w in [("elder", elder_time(L, ss, st)),
                    ("flat", L / C.ELDER_SPEED),
                    ("wheel", wheel_time(L, ss, st, stairs_passable_wheel)),
                    ("wheel_flat", L / C.WHEEL_SPEED)]:
        G = Graph(u, v, w, n)
        go = G.dijkstra(dests, reverse=True)   # 각 노드(집) → 가장 가까운 목적지
        back = G.dijkstra(dests)               # 가장 가까운 목적지 → 각 노드(집) = 귀갓길
        res[f"t_{name}"] = go + back           # f"..." 는 JS의 `템플릿 ${문자열}` 과 같음
        if name in ("elder", "flat"):
            res[f"t_{name}_back"] = back
    res["dist_net"] = res["t_flat"] / 2 * C.ELDER_SPEED
    return res



def run_with_extra(n, e, s, dests, extra):
    """[v5] 이동편의시설(엘리베이터 등)을 설치했다고 치고 다시 계산 (09_intervention.py 가 사용).

    extra: [(노드a, 노드b, 고정시간초), ...]  ← 시설 하나 = a↔b 를 잇는 지름길 간선 (양방향)
      JS로 치면 기존 간선 배열에 [...edges, {u:a, v:b, w:t}, {u:b, v:a, w:t}] 를 덧붙이는 것과 같습니다.
      시설 시간은 경사와 무관한 고정값이라 고령자·휠체어 그래프 모두에 같은 시간으로 넣습니다 (휠체어도 이용 가능).
    반환 (각 값은 길이 n 배열, 초): t_elder, t_wheel (왕복), t_elder_back (귀갓길 편도)
      평지 가정 시간(t_flat)은 설치 전 값을 그대로 분모로 씁니다 → HBI 설치 후 = t_elder(후) ÷ t_flat(전)
    """
    u, v, L, ss, st = directed(e, s)
    xa = np.array([a for a, b, t in extra] + [b for a, b, t in extra], np.int64)   # 정방향 + 역방향
    xb = np.array([b for a, b, t in extra] + [a for a, b, t in extra], np.int64)
    xt = np.array([t for a, b, t in extra] * 2, float)
    res = {}
    for name, w in [("elder", elder_time(L, ss, st)), ("wheel", wheel_time(L, ss, st))]:
        G = Graph(np.concatenate([u, xa]), np.concatenate([v, xb]), np.concatenate([w, xt]), n)
        go = G.dijkstra(dests, reverse=True)       # 집 → 가장 가까운 목적지
        back = G.dijkstra(dests)                   # 목적지 → 집 (귀갓길)
        res[f"t_{name}"] = go + back
        if name == "elder":
            res["t_elder_back"] = back
    return res

def route(n, e, s, o, d, mode="elder", speed=None, stairs_passable=False):
    """특정 두 노드(o→d) 사이 최단시간 경로의 (시간 초, 실제 경로 길이 m). 검증용.
    mode: "elder"(고령자) / "wheel"(휠체어) / "flat"(평지 가정)
    speed: 고령자 대신 다른 속도로 계산할 때 (예: 1.1 = 성인, 현장실측과 비교용)"""
    u, v, L, ss, st = directed(e, s)
    if mode == "elder":
        w = elder_time(L, ss, st) * (C.ELDER_SPEED / speed if speed else 1)
    elif mode == "wheel":
        w = wheel_time(L, ss, st, stairs_passable)
    else:
        w = L / (speed or C.ELDER_SPEED)
    G = Graph(u, v, w, n)
    p, t = G.path(o, d)
    if not p:
        return np.nan, np.nan
    lg = Graph(u, v, L, n)                              # 같은 간선의 "길이"를 찾기 위한 표
    key = dict(zip(lg.u.astype(np.int64) * n + lg.v, lg.w))
    return float(t), float(sum(key[a * n + b] for a, b in zip(p[:-1], p[1:])))   # 경로의 구간 길이 합
