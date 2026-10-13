# -*- coding: utf-8 -*-
"""
lib/expose.py ─ [v6.2] 연면적 "빼기" 노출 검사 (09_intervention.py 가 씀. 레포의 tools/check_area_exposure.py 도 같은 함수로 검사)

[문제] 공개한 연면적 값마다 그 값을 이루는 건물 집합이 있음. 큰 집합 B 의 값에서, B 안에 든 다른 공개 값 몇 개
       (서로 겹치지 않는 것)를 빼면 남는 건물이 1~4채일 때 그 몇 채의 연면적이 드러남.
       예) ALL(후보 전체) 수혜 연면적 − 시설 ①·③ 의 수혜 연면적 = 가려 둔 시설 ② 의 4채
[방법] "서로 겹치지 않게 고른 집합들의 건물 수 합" 으로 만들 수 있는 값을 모두 구해, B 에서 빼서 1~4채가 남는 값이 있는지 봄.
       겹치는 집합끼리 묶음을 만들고 (묶음끼리는 합을 참/거짓 배열로 더함), 묶음 안에서는 이웃이 가장 많은 집합 하나를
       "고른다/안 고른다" 로 나눈 뒤 다시 묶음을 나눔 (동끼리는 겹치지 않아 동 단위로 작게 풀림). 정확한 계산이고,
       나눈 횟수가 budget 을 넘으면 보수적으로 "드러남" 으로 봄
       JS 로 치면 knapsack 의 reachable[] 배열을, 겹치는 물건끼리는 하나만 담게 하면서 채우는 것과 같음
"""
import numpy as np


def removal_leak(nB, subs, mc, budget=50000):
    """nB: 큰 집합의 건물 수, subs: 그 안에 든 공개 집합들 (건물 번호 배열, 각각 B 의 부분집합), mc: 최소 건물 수 (MIN_COUNT)
    → 서로 겹치지 않는 subs 몇 개를 빼서 1 ~ mc-1 채가 남을 수 있으면 True"""
    subs = list({tuple(np.unique(np.asarray(q, np.int64)).tolist()) for q in subs if 0 < len(q) < nB})   # 같은 집합은 하나로
    if not subs:
        return False
    sz = [len(q) for q in subs]
    el = np.concatenate([np.array(q, np.int64) for q in subs])
    if nB - len(np.unique(el)) >= mc:                  # 모두 빼도 mc 채 이상 남으면 어떤 조합도 안전
        return False
    # 겹침 이웃 (같은 건물을 가진 집합끼리)
    owner = np.concatenate([np.full(n, i) for i, n in enumerate(sz)])
    o = np.argsort(el, kind="stable")
    el, owner = el[o], owner[o]
    adj = [set() for _ in subs]
    start = np.r_[0, np.flatnonzero(el[1:] != el[:-1]) + 1, len(el)]
    for a, c in zip(start[:-1], start[1:]):
        if c - a > 1:
            grp = set(owner[a:c].tolist())
            for i in grp:
                adj[i] |= grp - {i}
    calls = [0]

    def shift_or(r, s):
        out = np.zeros_like(r)
        if s <= nB:
            out[s:] = r[:nB + 1 - s]
        return out

    def comps(ids):
        seen, out = set(), []
        for i in ids:
            if i in seen:
                continue
            st, cur = [i], []
            seen.add(i)
            while st:
                x = st.pop()
                cur.append(x)
                for y in adj[x]:
                    if y in ids and y not in seen:
                        seen.add(y)
                        st.append(y)
            out.append(frozenset(cur))
        return out

    def reach_of(ids):
        """ids 안에서 겹치지 않게 골라 만들 수 있는 건물 수 합 (참/거짓 배열)"""
        r = np.zeros(nB + 1, bool)
        r[0] = True
        for cp in comps(ids):
            cr = comp_reach(cp)
            new = np.zeros_like(r)
            for t in np.flatnonzero(cr):
                new |= shift_or(r, int(t))
            r = new
        return r

    memo = {}

    def comp_reach(cp):
        if cp in memo:
            return memo[cp]
        calls[0] += 1
        if calls[0] > budget:
            raise OverflowError
        r = np.zeros(nB + 1, bool)
        r[0] = True
        if len(cp) == 1:
            (i,) = cp
            if sz[i] <= nB:
                r[sz[i]] = True
        else:
            x = max(cp, key=lambda i: len(adj[i] & cp))     # 이웃이 가장 많은 집합으로 나눔
            r = reach_of(cp - {x}) | shift_or(reach_of(cp - {x} - adj[x]), sz[x])
        memo[cp] = r
        return r
    try:
        r = reach_of(frozenset(range(len(subs))))
    except (OverflowError, RecursionError):
        return True
    return bool(r[max(1, nB - mc + 1):nB].any())


def publishable(S, pool, nb, mc, strict=False):
    """[v6.3] 집합 S(건물 번호 배열)의 값을 내도 되는가 (09 안에 있던 것을 05 도 쓰게 옮김. 계산은 같음)
    pool: 이미 공개한(또는 공개할 수 있는) 값의 건물 집합들, nb: 건물 전체 수, mc: MIN_COUNT
      0채면 됨, 1 ~ mc-1 채면 안 됨, S 에서 S 안의 공개 집합 몇 개를 빼거나, S 를 품는 공개 집합에서 S 와 다른 공개 집합을 빼서
      1 ~ mc-1 채가 남으면 안 됨. [v6.3] strict = 겹치지만 서로 포함하지 않는 공개 집합과 양쪽 차이가 모두 1 ~ mc-1 채여도 안 됨 (05 의 새 비율 값)"""
    n = len(S)
    if n == 0:
        return True
    if n < mc:
        return False

    def mask_of(Q):
        m = np.zeros(nb, bool)
        m[Q] = True
        return m
    Sm, subs, sups = mask_of(S), [], []
    for q in pool:
        k = int(Sm[q].sum())
        if k == len(q) and len(q) < n:
            subs.append(q)
        elif k == n and len(q) > n:
            sups.append(q)
        elif strict and 0 < k and 0 < n - k < mc and 0 < len(q) - k < mc:
            return False                         # [v6.3 검토] 겹치지만 포함하지 않는 집합: 양쪽 차이가 모두 1~4채면 W(S) − W(q) = W(S\q) − W(q\S) 로 몇 채 몫의 경계가 좁게 나옴
    if removal_leak(n, subs, mc):
        return False
    for P in sups:
        Pm = mask_of(P)
        if removal_leak(len(P), [q for q in pool if len(q) < len(P) and int(Pm[q].sum()) == len(q)] + [S], mc):
            return False
    return True
