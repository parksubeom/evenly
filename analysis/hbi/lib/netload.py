# -*- coding: utf-8 -*-
"""lib/netload.py ─ 02_network.py 가 저장한 work/network.npz 를 다시 불러오는 함수
 (.npz = numpy 배열 여러 개를 한 파일에 압축 저장하는 형식)"""
import os, numpy as np
import config as C

def load():
    z = np.load(os.path.join(getattr(C, "WORK_NET", C.WORK), "network.npz"))   # [v6] 여러 방식이 같이 씀
    e = {k[2:]: z[k] for k in z.files if k.startswith("e_")}   # 저장할 때 붙인 "e_" 접두사를 떼서 링크 정보 복원
    return dict(nodes=z["nodes"], giant=z["giant"], e=e, s5=z["s5"], z5=z["z5"],
                s1=z["s1"] if "s1" in z.files else None)        # s5 = DEM 5m 경사, s1 = DEM 1m 경사(있을 때만)
