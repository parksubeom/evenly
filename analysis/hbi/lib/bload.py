# -*- coding: utf-8 -*-
"""lib/bload.py ─ 03_hbi.py 가 저장한 건물별 결과(work/buildings_hbi.csv)를 다시 불러오는 함수"""
import os, csv, numpy as np
import config as C

def load_buildings():
    """CSV → {"열이름": 숫자배열}. 빈 칸은 NaN"""
    with open(os.path.join(C.WORK, "buildings_hbi.csv"), encoding="utf-8-sig") as f:
        r = csv.reader(f)
        head = next(r)                   # 첫 줄 = 열 이름
        rows = list(r)
    a = np.array([[float(v) if v != "" else np.nan for v in row] for row in rows]) if rows else np.zeros((0, len(head)))
    return {h: a[:, i] for i, h in enumerate(head)}

def usable(b):
    """통계에 쓸 건물 = 데이터 경계 근처(edge=1)가 아닌 건물 (True/False 배열)"""
    return b["edge"] < 0.5 if "edge" in b else np.ones(len(b["x"]), bool)

def targets(b):
    """결과에 들어 있는 목적지 종류 목록. 예) ["medical", "bus", "elderly"]  ("medical_hbi" 열 → "medical")"""
    return [k[:-4] for k in b if k.endswith("_hbi")]


def rep_mode():
    """[v6.2] 연면적 칸(05 의 왕복 추가 문턱·격자, 09 의 수혜 연면적)을 낼 방식 하나. --modes 로 여러 방식을 함께 내면 방식끼리 빼서 몇 채 몫이 드러날 수 있어서
    check 가 고른 방식(없으면 --modes 의 첫 방식)에만 냄. 방식 하나로 돌렸으면 그 방식"""
    if os.path.normpath(C.OUTPUT) == os.path.normpath(os.path.join(C.BASE, "output")):
        return C.BUILDING_ATTR_MODE
    try:
        modes = [m.strip().lower() for m in open(os.path.join(C.WORK_NET, "last_modes.txt"), encoding="utf-8").read().split(",") if m.strip()]
    except OSError:
        modes = []
    ch = (C.MAPPING.get("building_attr_chosen") or "").strip().lower()
    modes = [ch if m == "auto" else m for m in modes]
    # [10/12 검토] 방식 폴더(output/<방식>)인데 --modes 기억이 없으면(방식 없이 run_all 을 친 뒤 단독 실행 등) 대표 방식을 모름 → ""
    #   (예전에는 그 방식을 대표로 봐서 다른 방식 폴더와 함께 값이 나갈 수 있었음). auto 인데 check 가 고른 방식이 비어도 ""
    return ch if ch in modes else (modes[0] if modes else "")


def risk_cell_mask(b, T, U):
    """[v6.3] 건물마다 '고립 위험 격자' 안인가 (참/거짓 배열): 05 격자와 같은 칸(목적지 T 의 분석 건물 MIN_COUNT 이상) 중
    집 절반 이상이 왕복 RISK_MIN 분 이상 더 걸리는 칸 (기획서 17장 '후보'와 같은 정의). 05 독거노인 추정·09 연면적 검사·노출 검사 도구가 같이 씀"""
    out = np.zeros(len(b["x"]), bool)
    if not getattr(C, "RISK_MIN", None) or not T or f"{T}_hbi" not in b:
        return out
    v = np.isfinite(b[f"{T}_hbi"]) & U
    add = (b[f"{T}_t_elder"] - b[f"{T}_t_flat"]) / 60
    key = np.floor(b["x"] / C.GRID).astype(np.int64) * 10**7 + np.floor(b["y"] / C.GRID).astype(np.int64)
    uk, ik = np.unique(key[v], return_inverse=True)
    if not len(uk):
        return out
    nk = np.bincount(ik)
    rk = np.bincount(ik, (add[v] >= C.RISK_MIN).astype(float))
    keep = uk[(nk >= C.MIN_COUNT) & (rk / np.maximum(nk, 1) >= 0.5)]
    return np.isin(key, keep) if len(keep) else out
