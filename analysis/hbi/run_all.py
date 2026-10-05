# -*- coding: utf-8 -*-
"""
run_all.py ─ 01~05 단계(+ 설정에 따라 06·07·08·09·10·11)를 순서대로 한 번에 실행 (package.json 의 "scripts" 를 연달아 돌리는 것과 비슷)

[실행]  python run_all.py            (DEM 1m 비교: --dem1m, 민감도 분석: --sens  예) python run_all.py --dem1m --sens)
        python run_all.py --from 03  [v6] 03 단계부터 다시 (02 결과 work/network.npz 를 그대로 씀. 멈춘 단계 번호를 넣음)
  - 한 단계에서 오류가 나면 거기서 멈추고 어느 단계인지, 알려진 원인이면 고칠 곳까지 알려 줍니다. [v6]
  - [v6] 화면에 나온 글자는 output/runlog/ 에도 저장 (반출해서 밖에서 확인). 받은 자료의 구조는 output/schema/schema.txt
  - QGIS Python 콘솔에서는 쓸 수 없습니다 → 단계별 스크립트를 하나씩 실행하세요 (README 참고)
"""
import subprocess, sys, os, re, time
if "python" not in os.path.basename(sys.executable).lower():
    raise SystemExit("QGIS Python 콘솔에서는 run_all.py 대신 단계별 스크립트를 exec로 실행하세요 (README 참고)")
import config as C
from lib.conout import safe_console
safe_console()
steps = ["01_inspect.py", "02_network.py", "03_hbi.py", "04_validate.py", "05_export.py"]
if C.DATA_ROOT_PARCEL: steps.append("06_parcel.py")                                   # 필지 경로가 있으면 자동 포함
if any(v.get("path") for v in C.JOIN_DATA.values()): steps.append("07_join_dong.py")  # SKT·KCB 경로가 있으면
if "--sens" in sys.argv: steps.append("08_sensitivity.py")                           # python run_all.py --sens
# [v5] 09: interventions.csv 에 양 끝 좌표 4개가 다 채워진 행이 하나라도 있으면
def _has_facility():
    import csv
    p = os.path.join(C.EXTERNAL, "interventions.csv")
    if not os.path.exists(p):
        return False
    with open(p, encoding="utf-8-sig") as f:
        return any(all((r.get(k) or "").strip() for k in ("a_lon", "a_lat", "b_lon", "b_lat")) for r in csv.DictReader(f))
if _has_facility(): steps.append("09_intervention.py")
if any(v.get("path") for v in C.POINT_DATA.values()): steps.append("10_points_join.py")   # [v5] 점 자료 경로가 있으면
if any(v.get("path") for v in C.LEGAL_DONG_DATA.values()): steps.append("11_legal_dong_join.py")   # [v5] 법정동 이름 자료가 있으면

# [v6] --from NN : 그 번호 단계부터 (예: --from 03). 02 를 건너뛰면 work/network.npz 가 있어야 함
if "--from" in sys.argv:
    i = sys.argv.index("--from")
    want = (sys.argv[i + 1] if i + 1 < len(sys.argv) else "").zfill(2)[:2]
    k = next((j for j, s in enumerate(steps) if s.startswith(want)), None)
    if k is None:
        raise SystemExit(f"--from {want}: 이번 실행 목록에 없는 단계입니다. 목록: {', '.join(s[:2] for s in steps)}")
    if k > 1 and not os.path.exists(os.path.join(C.WORK, "network.npz")):
        raise SystemExit("work/network.npz 가 없습니다 → 02 부터 (python run_all.py)")
    if k > 2 and not os.path.exists(os.path.join(C.WORK, "buildings_hbi.csv")):
        raise SystemExit("work/buildings_hbi.csv 가 없습니다 → --from 03")
    steps = steps[k:]

# [v6] 알려진 실패 → (찾을 글자, 원인, 할 일). 마지막 화면 글자에서 위에서부터 찾음
KNOWN = [
    (r"KeyError: '([^']+)'", "칸(필드) 이름 '{0}' 을 자료에서 찾지 못함",
     "mapping.txt 에서 값이 {0} 인 줄({keys})을 실제 칸 이름으로 고치거나 python setup.py 를 다시 → python check.py"),
    (r"min\(\) (iterable argument is empty|arg is an empty sequence)|zero-size array", "집계할 건물이 0채 (집으로 고른 건물이 없음)",
     "python check.py 로 주거 비율 확인. 건물 용도 칸이 없으면 mapping.txt 의 building_attr_mode = register (또는 all)"),
    (r"UnicodeDecodeError", "한글 인코딩이 맞지 않음",
     "config.py 의 SHP_ENCODING·PARCEL_ENCODING (UTF-8 ↔ CP949), CSV 는 저장 인코딩 확인. python check.py 의 인코딩 줄"),
    (r"보도중심선/도로중심선이 없습니다", "길(보도·도로 중심선) 레이어를 찾지 못함",
     "mapping.txt 의 layer_road_cl·layer_sidewalk_cl 을 실제 파일 이름 글자로, map_folders 확인 → python check.py"),
    (r"목적지가 없습니다", "목적지(병원·정류장·역·약국)를 하나도 찾지 못함", "python check.py 의 목적지 개수 줄 → 해당 레이어·external 파일 확인"),
    (r"FileNotFoundError|No such file|DEM 파일 없음|cannot open|not recognized as", "파일·폴더 주소가 틀림",
     "config.py 의 DATA_ROOT_… 줄 (python setup.py 를 다시 하면 채워 줌)"),
    (r"MemoryError", "메모리 부족", "config.py 의 AREA_BBOX 로 범위를 좁히거나 map_folders 를 줄이기"),
]


def diagnose(tail, step):
    """마지막 화면 글자 → (원인, 할 일) 또는 None"""
    txt = "\n".join(tail)
    for pat, why, todo in KNOWN:
        m = re.search(pat, txt)
        if m:
            g = m.group(1) if pat.startswith("KeyError") else ""
            keys = ", ".join(k for k, v in getattr(C, "MAPPING", {}).items() if v and g and v.upper() == g.upper()) or "해당 칸"
            return why.format(g), todo.format(g, keys=keys)
    guide = [x for x in tail if " → " in x and not x.startswith(("[", "!!", " "))]   # 코드가 직접 남긴 멈춤 안내 (SystemExit)
    if guide:
        return "위 줄에 멈춘 이유를 적어 둠", "위 줄의 → 뒤 안내대로 고치기 (mapping.txt 면 python check.py 로 확인)"
    return None


def scrub(line):
    """반출용 진단 파일에서 값이 될 수 있는 따옴표 안 글자를 가림 (칸 이름 KeyError 는 남김)"""
    if line.startswith("KeyError"):
        return line
    return re.sub(r"'[^']{12,}'|\"[^\"]{12,}\"", "'…'", line)


os.makedirs(C.OUTPUT, exist_ok=True)
if os.path.exists(os.path.join(C.OUTPUT, "diagnose.txt")):      # 지난번 실패 기록은 지움 (이번에 실패하면 새로 씀)
    os.remove(os.path.join(C.OUTPUT, "diagnose.txt"))
logdir = os.path.join(C.OUTPUT, "runlog")
os.makedirs(logdir, exist_ok=True)
logf = open(os.path.join(logdir, time.strftime("runlog_%Y%m%d_%H%M%S.txt")), "w", encoding="utf-8-sig")   # BOM: 메모장에서 바로 읽힘


def out(s):
    print(s, flush=True)
    logf.write(s + "\n"); logf.flush()


out(f"# run_all.py {' '.join(sys.argv[1:])} / 단계: {', '.join(s[:2] for s in steps)} / 대상 구: {','.join(C.TARGET_GU) or '전체'} / "
    f"건물 용도 방식: {C.BUILDING_ATTR_MODE} / AREA_BBOX: {C.AREA_BBOX}")
try:
    from lib.schema import dump
    out(f"# 자료 구조 저장 → {os.path.relpath(dump(), C.BASE)}")
except Exception as e:                     # 구조 저장이 안 돼도 분석은 계속
    out(f"# 자료 구조 저장 실패 ({type(e).__name__}) → 분석은 계속")

env = dict(os.environ, PYTHONIOENCODING="utf-8", PYTHONUNBUFFERED="1")   # 자식 출력은 UTF-8 로 받아 그대로 화면·파일에
for s in steps:
    args = [sys.executable, s] + (["--dem1m"] if s == "02_network.py" and "--dem1m" in sys.argv else [])
    out(f"\n########## {s} ##########")
    p = subprocess.Popen(args, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, env=env)
    tail = []
    for raw in p.stdout:
        line = raw.decode("utf-8", "replace").rstrip("\r\n")
        out(line)
        tail = (tail + [line])[-60:]
    if p.wait() != 0:        # 0 이 아니면 = 오류로 끝남
        out(f"!! {s} 에서 중단. 위 오류 메시지를 확인하세요.")
        d = diagnose(tail, s)
        if d:
            out(f"!! 원인: {d[0]}\n!! 할 일: {d[1]}\n!! 고친 뒤: python run_all.py --from {s[:2]}")
        else:
            out(f"!! 알려진 오류가 아닙니다 → 화면의 마지막 줄을 적어 오세요 (output/diagnose.txt 에도 저장). 고친 뒤: python run_all.py --from {s[:2]}")
        with open(os.path.join(C.OUTPUT, "diagnose.txt"), "w", encoding="utf-8-sig") as f:
            f.write(f"단계 {s}\n원인: {d[0] if d else '알 수 없음'}\n할 일: {d[1] if d else '-'}\n\n마지막 화면 (값이 될 수 있는 긴 따옴표 글자는 … 로 가림)\n")
            f.write("\n".join(scrub(x) for x in tail[-40:]) + "\n")
        logf.close()
        sys.exit(1)
logf.close()
