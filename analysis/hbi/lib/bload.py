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
