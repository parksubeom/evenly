# -*- coding: utf-8 -*-
"""전체 실행: python run_all.py   (DEM 1m 비교 포함: python run_all.py --dem1m)"""
import subprocess, sys
steps = ["01_inspect.py", "02_network.py", "03_hbi.py", "04_validate.py", "05_export.py"]
for s in steps:
    args = [sys.executable, s] + (["--dem1m"] if s == "02_network.py" and "--dem1m" in sys.argv else [])
    print(f"\n########## {s} ##########", flush=True)
    if subprocess.call(args) != 0:
        print(f"!! {s} 에서 중단. 위 오류 메시지를 확인하세요."); sys.exit(1)
