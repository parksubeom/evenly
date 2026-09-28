# -*- coding: utf-8 -*-
"""
run_all.py ─ 01~05 단계(+ 설정에 따라 06·07·08)를 순서대로 한 번에 실행 (package.json 의 "scripts" 를 연달아 돌리는 것과 비슷)

[실행]  python run_all.py            (DEM 1m 비교: --dem1m, 민감도 분석: --sens  예) python run_all.py --dem1m --sens)
  - 한 단계에서 오류가 나면 거기서 멈추고 어느 단계인지 알려 줍니다.
  - QGIS Python 콘솔에서는 쓸 수 없습니다 → 단계별 스크립트를 하나씩 실행하세요 (README 참고)
  - 처음 방문한 날에는 run_all 보다 01 → 02 → 03 ... 을 하나씩 돌려 보며 화면을 확인하는 걸 권장합니다.
"""
import subprocess, sys, os
if "python" not in os.path.basename(sys.executable).lower():
    raise SystemExit("QGIS Python 콘솔에서는 run_all.py 대신 단계별 스크립트를 exec로 실행하세요 (README 참고)")
import config as C
steps = ["01_inspect.py", "02_network.py", "03_hbi.py", "04_validate.py", "05_export.py"]
if C.DATA_ROOT_PARCEL: steps.append("06_parcel.py")                                   # 필지 경로가 있으면 자동 포함
if any(v.get("path") for v in C.JOIN_DATA.values()): steps.append("07_join_dong.py")  # SKT·KCB 경로가 있으면
if "--sens" in sys.argv: steps.append("08_sensitivity.py")                           # python run_all.py --sens
for s in steps:
    args = [sys.executable, s] + (["--dem1m"] if s == "02_network.py" and "--dem1m" in sys.argv else [])
    print(f"\n########## {s} ##########", flush=True)
    if subprocess.call(args) != 0:        # 0 이 아니면 = 오류로 끝남
        print(f"!! {s} 에서 중단. 위 오류 메시지를 확인하세요.")
        sys.exit(1)
