# -*- coding: utf-8 -*-
"""
lib/qgraph.py ─ 길찾기 계산 엔진

[이 파일이 하는 일]
 1) NearestIndex : "이 점에서 가장 가까운 교차점은?" 을 빠르게 찾기
 2) Graph        : 길 네트워크에서 "가장 빨리 가는 경로의 시간" 계산 (다익스트라 알고리즘)
 3) components   : 서로 이어진 길 덩어리 찾기 (끊긴 섬 같은 길 제거용)
 4) spearman     : 두 순위가 얼마나 비슷한지(순위 상관계수) 계산 — 검증에 사용

[용어]
 - 노드(node) : 길의 교차점·꺾이는 점. 번호(0, 1, 2, ...)로 부릅니다.
 - 간선(edge) : 노드 u 에서 노드 v 로 가는 한 구간. 비용 w(여기선 걸리는 시간, 초)를 가짐.
 - 방향 그래프 : u→v 와 v→u 의 비용이 다를 수 있음 (오르막 vs 내리막!)

scipy 가 있으면 scipy 의 빠른 구현을 쓰고, 없으면 아래에 직접 짠 파이썬 코드로 같은 계산을 합니다.
"""
import heapq                       # 우선순위 큐 (다익스트라에 필요). 파이썬 기본 내장
import numpy as np
from lib.deps import HAS_SCIPY


# ═══════════════════ 1. 최근접 점 탐색 ═══════════════════
class NearestIndex:
    """점 목록(xy)을 미리 정리해 두고, 다른 점에서 가장 가까운 점을 빨리 찾습니다.

    사용법:
        idx = NearestIndex(노드좌표배열)            # [[x,y], [x,y], ...]
        거리들, 번호들 = idx.query(찾을점배열, 60)    # 60m 안에 없으면 거리=inf, 번호=-1
    """
    def __init__(self, xy, cell=50.0):
        self.xy = np.asarray(xy, float)
        if HAS_SCIPY:                                  # scipy 가 있으면 KD-트리(빠른 공간 색인) 사용
            from scipy.spatial import cKDTree
            self.tree = cKDTree(self.xy)
            return
        # scipy 가 없을 때: 지도를 50m 칸으로 나누고, 칸마다 들어 있는 점 번호를 적어 둠 (버킷)
        self.tree = None
        self.cell = cell
        k = np.floor(self.xy / cell).astype(np.int64)   # 각 점이 몇 번째 칸인지
        self.buckets = {}                               # {(칸x, 칸y): [점번호, ...]}
        for i, (a, b) in enumerate(map(tuple, k)):
            self.buckets.setdefault((a, b), []).append(i)

    def query(self, pts, maxd=np.inf):
        """각 점마다 가장 가까운 점의 (거리 배열, 번호 배열). maxd 보다 멀면 (inf, -1)"""
        pts = np.atleast_2d(np.asarray(pts, float))
        if self.tree is not None:
            d, i = self.tree.query(pts, distance_upper_bound=maxd if np.isfinite(maxd) else np.inf)
            i = np.where(np.isfinite(d), i, -1)
            return d, i
        D = np.full(len(pts), np.inf)                   # 결과 거리 (처음엔 무한대)
        I = np.full(len(pts), -1)                       # 결과 번호 (처음엔 없음)
        for n, p in enumerate(pts):
            ca, cb = np.floor(p / self.cell).astype(np.int64)   # 찾을 점이 속한 칸
            ring = 0                                    # 0이면 자기 칸, 1이면 바로 옆 칸들, 2면 그 바깥 ...
            while True:
                cand = []                               # 이번 고리(ring)에 있는 후보 점들
                for a in range(ca - ring, ca + ring + 1):
                    for b in range(cb - ring, cb + ring + 1):
                        if max(abs(a - ca), abs(b - cb)) == ring:
                            cand += self.buckets.get((a, b), [])
                if cand:
                    c = np.array(cand)
                    d = np.hypot(*(self.xy[c] - p).T)   # 후보들까지 거리 (hypot = 피타고라스 √(dx²+dy²))
                    j = d.argmin()                      # 가장 가까운 후보의 위치
                    if d[j] < D[n]:
                        D[n], I[n] = d[j], c[j]
                # 이미 찾은 거리보다 더 먼 고리까지 봤으면 끝 / 너무 멀리까지 가면 끝
                if (np.isfinite(D[n]) and ring * self.cell >= D[n] + self.cell) or ring * self.cell > min(maxd, 5000) + self.cell:
                    break
                ring += 1
        bad = D > maxd
        D[bad] = np.inf
        I[bad] = -1
        return D, I

    def within(self, p, r):
        """점 p 에서 반경 r 안에 있는 점 번호 목록"""
        if self.tree is not None:
            return self.tree.query_ball_point(p, r)
        ca, cb = np.floor(np.asarray(p) / self.cell).astype(np.int64)
        k = int(np.ceil(r / self.cell))
        cand = [i for a in range(ca - k, ca + k + 1) for b in range(cb - k, cb + k + 1) for i in self.buckets.get((a, b), [])]
        if not cand:
            return []
        c = np.array(cand)
        d = np.hypot(*(self.xy[c] - np.asarray(p)).T)
        return list(c[d <= r])


# ═══════════════════ 2. 그래프와 최단경로 ═══════════════════
class Graph:
    """방향 그래프. u[i] → v[i] 로 가는 비용이 w[i] 인 간선들의 모음. n = 노드 개수.

    같은 u→v 간선이 여러 개면 비용이 가장 작은 것 하나만 남깁니다.
    w 가 무한대(np.inf)인 간선은 "지나갈 수 없음"으로 보고 버립니다 (예: 휠체어의 계단).
    """
    def __init__(self, u, v, w, n):
        ok = np.isfinite(w)                               # 무한대가 아닌 간선만
        u, v, w = u[ok], v[ok], np.maximum(w[ok], 1e-6)   # 비용 0 은 계산에 문제가 있어 아주 작은 값으로
        key = u.astype(np.int64) * n + v                  # (u,v) 쌍을 숫자 하나로 표현
        order = np.lexsort((w, key))                      # key 순 → 같은 key 안에서는 w 작은 순으로 정렬
        key, u, v, w = key[order], u[order], v[order], w[order]
        first = np.r_[True, key[1:] != key[:-1]]          # 같은 key 중 첫 번째(=가장 작은 w)만 True
        self.u, self.v, self.w, self.n = u[first], v[first], w[first], n

    def _csr(self, rev=False):
        """"노드별로 나가는 간선 목록"을 빠르게 꺼낼 수 있는 압축 형태(CSR)로 변환.
        ptr[x] ~ ptr[x+1] 사이 칸에 노드 x 에서 나가는 간선들의 (도착 노드, 비용)이 들어 있음.
        rev=True 면 간선 방향을 뒤집어서 만듦"""
        a, b = (self.v, self.u) if rev else (self.u, self.v)
        o = np.argsort(a, kind="stable")
        ptr = np.zeros(self.n + 1, np.int64)
        np.add.at(ptr, a + 1, 1)
        ptr = np.cumsum(ptr)
        return ptr, b[o], self.w[o]

    def dijkstra(self, sources, reverse=False):
        """다익스트라 알고리즘: 출발점 여러 곳(sources) 중 "가장 가까운 한 곳"에서 모든 노드까지의 최소 비용.

        결과: 길이 n 인 배열. dist[x] = x 까지 걸리는 최소 시간(초). 못 가면 inf.
        reverse=False : 출발점 → 각 노드   (예: 약국 → 집 = 귀갓길)
        reverse=True  : 각 노드 → 출발점   (예: 집 → 약국 = 가는 길)

        [다익스트라 원리] 출발점에서 가까운 노드부터 하나씩 확정해 나가며,
        확정된 노드에서 이웃 노드로 가는 비용을 갱신합니다. 내비게이션 길찾기의 기본 알고리즘입니다.
        """
        sources = np.unique(np.asarray(sources, np.int64))
        if HAS_SCIPY:
            from scipy.sparse import csr_matrix
            from scipy.sparse.csgraph import dijkstra
            a, b = (self.v, self.u) if reverse else (self.u, self.v)
            M = csr_matrix((self.w, (a, b)), shape=(self.n, self.n))
            return dijkstra(M, directed=True, indices=sources, min_only=True)   # min_only: 가장 가까운 출발점 기준
        ptr, nb, wt = self._csr(reverse)
        dist = np.full(self.n, np.inf)          # 처음엔 모두 무한대
        dist[sources] = 0.0                     # 출발점은 0
        h = [(0.0, int(s)) for s in sources]    # 우선순위 큐: (지금까지 비용, 노드)
        heapq.heapify(h)
        while h:
            d, x = heapq.heappop(h)             # 비용이 가장 작은 노드를 꺼냄
            if d > dist[x]:
                continue                        # 이미 더 짧은 길로 확정된 노드면 건너뜀
            for k in range(ptr[x], ptr[x + 1]): # x 에서 나가는 간선들
                y = nb[k]
                nd = d + wt[k]
                if nd < dist[y]:                # 더 빠른 길을 찾았으면 갱신
                    dist[y] = nd
                    heapq.heappush(h, (nd, int(y)))
        return dist

    def path(self, o, d):
        """노드 o → 노드 d 최단경로. (지나가는 노드 번호 목록, 총 비용). 못 가면 ([], inf)"""
        ptr, nb, wt = self._csr(False)
        dist = np.full(self.n, np.inf)
        prev = np.full(self.n, -1)              # prev[y] = y 에 도착하기 직전 노드 (경로 역추적용)
        dist[o] = 0
        h = [(0.0, int(o))]
        while h:
            dd, x = heapq.heappop(h)
            if x == d:
                break                           # 목적지 도착하면 중단
            if dd > dist[x]:
                continue
            for k in range(ptr[x], ptr[x + 1]):
                y = nb[k]
                nd = dd + wt[k]
                if nd < dist[y]:
                    dist[y] = nd
                    prev[y] = x
                    heapq.heappush(h, (nd, int(y)))
        if not np.isfinite(dist[d]):
            return [], np.inf
        p = [d]
        while p[-1] != o:                       # 목적지에서 prev 를 따라 거꾸로 출발점까지
            p.append(prev[p[-1]])
        return p[::-1], dist[d]                 # [::-1] = 뒤집기 (JS의 arr.reverse())


# ═══════════════════ 3. 연결된 덩어리 찾기 ═══════════════════
def components(u, v, n):
    """간선(u[i]–v[i])으로 이어진 노드끼리 같은 번호를 붙여 줌. 결과: 길이 n 배열 (덩어리 번호)
    가장 큰 덩어리 = 도시의 주 보행망. 여기에 안 붙은 작은 조각은 나중에 버립니다."""
    if HAS_SCIPY:
        from scipy.sparse import coo_matrix
        from scipy.sparse.csgraph import connected_components
        return connected_components(coo_matrix((np.ones(len(u)), (u, v)), shape=(n, n)), directed=False)[1]
    # scipy 가 없을 때: Union-Find(합치기-찾기) 방식. 각 노드의 "대표"를 따라가 같은 대표면 같은 덩어리
    parent = np.arange(n)
    def find(x):
        r = x
        while parent[r] != r:
            r = parent[r]
        while parent[x] != r:                   # 경로 압축: 다음 번엔 바로 대표로 가도록
            parent[x], x = r, parent[x]
        return r
    for a, b in zip(u, v):
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[ra] = rb
    return np.array([find(i) for i in range(n)])


# ═══════════════════ 4. 순위 상관 ═══════════════════
def rankdata(x):
    """값 배열 → 순위 배열 (0부터). 같은 값은 평균 순위"""
    x = np.asarray(x, float)
    o = np.argsort(x, kind="mergesort")
    r = np.empty(len(x))
    r[o] = np.arange(len(x))
    xs = x[o]
    i = 0
    while i < len(xs):
        j = i
        while j + 1 < len(xs) and xs[j + 1] == xs[i]:
            j += 1
        if j > i:
            r[o[i:j + 1]] = (i + j) / 2
        i = j + 1
    return r


def spearman(a, b):
    """스피어만 순위상관계수: 두 기준으로 매긴 순위가 얼마나 같은지. 1=완전히 같음, 0=무관
    예) "평지 기준 순위"와 "경사 반영 순위"가 0.7 이면 → 순위가 꽤 많이 바뀐다는 뜻"""
    a, b = np.asarray(a, float), np.asarray(b, float)
    ok = np.isfinite(a) & np.isfinite(b)
    if ok.sum() < 3:
        return np.nan
    return float(np.corrcoef(rankdata(a[ok]), rankdata(b[ok]))[0, 1])
