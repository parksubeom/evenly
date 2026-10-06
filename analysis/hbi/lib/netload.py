# -*- coding: utf-8 -*-
"""lib/netload.py ─ 02_network.py 가 저장한 work/network.npz 를 다시 불러오는 함수
 (.npz = numpy 배열 여러 개를 한 파일에 압축 저장하는 형식)"""
import os, numpy as np
import config as C

def load():
    z = np.load(os.path.join(getattr(C, "WORK_NET", C.WORK), "network.npz"))   # [v6] 여러 방식이 같이 씀
    e = {k[2:]: z[k] for k in z.files if k.startswith("e_")}   # 저장할 때 붙인 "e_" 접두사를 떼서 링크 정보 복원
    # [v6.1] walkall = 걸을 수 없는 길을 빼지 않은 비교용 네트워크 (뺀 길이 있을 때만, 노드는 같음)
    wa = None
    if "xgiant" in z.files:
        wa = dict(giant=z["xgiant"], e={k[2:]: z[k] for k in z.files if k.startswith("x_")}, s5=z["xs5"])
    return dict(nodes=z["nodes"], giant=z["giant"], e=e, s5=z["s5"], z5=z["z5"],
                s1=z["s1"] if "s1" in z.files else None,        # s5 = DEM 5m 경사, s1 = DEM 1m 경사(있을 때만)
                c1=z["c1"] if "c1" in z.files else None,        # [v6.1] 노드가 DEM 1m 범위 안인지 (없으면 None = 전부)
                walkall=wa, walk_excl=z["walk_excl"].tolist() if "walk_excl" in z.files else [0, 0])
