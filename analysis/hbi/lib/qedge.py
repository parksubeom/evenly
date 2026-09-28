# -*- coding: utf-8 -*-
"""
lib/qedge.py ─ 경계 효과 처리: 데이터 가장자리 근처 건물 표시

[왜 필요한가]
 우리가 받은 수치지형도는 특정 구(도엽)까지만 있습니다. 경계 근처 집은 실제로 가장 가까운 병원이
 바로 옆 동네(데이터 밖)에 있어도, 데이터 안의 먼 병원까지로 계산돼 시간이 부풀려집니다.
 그래서 "데이터 범위 가장자리에서 EDGE_BUFFER(500m) 안쪽" 건물은 결과 통계에서 뺍니다.

[방법]
 1) 지도를 50m 칸으로 나누고, 도엽 네모 범위(coverage_envelopes)에 들어가는 칸 = 데이터 있음
 2) 각 건물 주변 ±500m 안에 "데이터 없음" 칸이 하나라도 있으면 → 경계 건물(edge=True)
 3) 빠르게 세기 위해 누적합 표(합계 영역 테이블)를 씁니다: 네모 안의 합을 네 칸 덧셈으로 구하는 기법
"""
import numpy as np
import config as C


def edge_flags(xs, ys, envs, cell=50.0):
    """건물 좌표 배열 → 경계 건물 여부(True/False) 배열"""
    xs, ys = np.asarray(xs, float), np.asarray(ys, float)
    if C.EDGE_BUFFER <= 0 or not envs or len(xs) == 0:
        return np.zeros(len(xs), bool)
    r = int(np.ceil(C.EDGE_BUFFER / cell))             # 버퍼가 몇 칸인지
    E = np.array(envs)
    x0, y0 = E[:, 0].min() - (r + 2) * cell, E[:, 1].min() - (r + 2) * cell   # 바깥 여유를 둔 격자 원점
    nx = int(np.ceil((E[:, 2].max() + (r + 2) * cell - x0) / cell))
    ny = int(np.ceil((E[:, 3].max() + (r + 2) * cell - y0) / cell))
    cov = np.zeros((ny, nx), bool)                     # 데이터 있음 표시판
    for a, b, c, d in envs:
        cov[int((b - y0) // cell):int(np.ceil((d - y0) / cell)), int((a - x0) // cell):int(np.ceil((c - x0) / cell))] = True
    if C.AREA_BBOX:                                    # 시험 범위를 걸었다면 그 밖도 "데이터 없음"
        bx0, by0, bx1, by1 = C.AREA_BBOX
        m = np.zeros_like(cov)
        m[max(0, int((by0 - y0) // cell)):int(np.ceil((by1 - y0) / cell)), max(0, int((bx0 - x0) // cell)):int(np.ceil((bx1 - x0) / cell))] = True
        cov &= m
    out = (~cov).astype(np.int64)
    S = np.zeros((ny + 1, nx + 1), np.int64)
    S[1:, 1:] = out.cumsum(0).cumsum(1)                # 누적합 표
    ci = np.clip(((xs - x0) // cell).astype(int), 0, nx - 1)
    ri = np.clip(((ys - y0) // cell).astype(int), 0, ny - 1)
    r0, r1 = np.clip(ri - r, 0, ny), np.clip(ri + r + 1, 0, ny)
    c0, c1 = np.clip(ci - r, 0, nx), np.clip(ci + r + 1, 0, nx)
    cnt = S[r1, c1] - S[r0, c1] - S[r1, c0] + S[r0, c0]   # 주변 네모 안 "데이터 없음" 칸 수
    return cnt > 0
