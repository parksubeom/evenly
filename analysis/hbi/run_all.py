# -*- coding: utf-8 -*-
"""
run_all.py ─ 01~05 단계(+ 설정에 따라 06·07·08·09·10·11)를 순서대로 한 번에 실행 (package.json 의 "scripts" 를 연달아 돌리는 것과 비슷)

[실행]  python run_all.py            (DEM 1m 비교: --dem1m, 민감도 분석: --sens  예) python run_all.py --dem1m --sens)
        [v6.1] config.DATA_ROOT_DEM1M 이 있으면 --dem1m·--sens 없이도 1m 비교(04·08)를 함 (config.DEM1M_AUTO)
        python run_all.py --from 03  [v6] 03 단계부터 다시 (02 결과 work/network.npz 를 그대로 씀. 멈춘 단계 번호를 넣음)
  - 한 단계에서 오류가 나면 거기서 멈추고 어느 단계인지, 알려진 원인이면 고칠 곳까지 알려 줍니다. [v6]
  - [v6.2] 화면에 나온 글자는 work/logs/ 에 저장 (반출하지 않음, lib/runlog.py). 멈추면 화면에 메모 카드(손으로 적을 5줄).
    output/run_summary.txt 에 단계별 결과·시간·경고 수 요약 한 장 (값 없음). 받은 자료의 구조는 output/schema/schema.txt
  - QGIS Python 콘솔에서는 쓸 수 없습니다 → 단계별 스크립트를 하나씩 실행하세요 (README 참고)
"""
import lib.runlog as _RL; _RL.start(globals())   # [v6.2] 기록·멈추면 메모 카드 (무거운 import 보다 먼저. lib/runlog.py)
import subprocess, sys, os, re, time
if "python" not in os.path.basename(sys.executable).lower():
    raise SystemExit("QGIS Python 콘솔에서는 run_all.py 대신 단계별 스크립트를 exec로 실행하세요 (README 참고)")
import config as C
from lib.conout import safe_console
safe_console()
os.makedirs(C.OUTPUT, exist_ok=True)
T0 = time.time()
RECS = []                                  # [v6.2] 단계별 (단계, 방식, 종료 코드, 초, 경고 수, 최대 메모리 MB) → output/run_summary.txt
STOPPED = {}
MEMO = []                                  # [v6.2] 구조 메모 (02 의 코드값 분포·남긴 링크, 값 없음) → run_summary
CUR = {}                                   # 지금 돌고 있는 자식 (Ctrl+C 때 정리)
# [v6.2] 끝나기 전에 멈추면(안내 멈춤·Ctrl+C·오류) 지난번 요약이 반출본에 남지 않게, 먼저 '끝나지 않음' 으로 써 둠
with open(os.path.join(C.OUTPUT, "run_summary.txt"), "w", encoding="utf-8-sig") as _fh:
    _fh.write(f"run_all 요약 ({_RL._version()}) - 끝나지 않음 (멈췄거나 Ctrl+C) → 화면의 메모 카드\n"
              f"시작 {time.strftime('%m-%d %H:%M', time.localtime(T0))} · 명령: run_all.py {' '.join(sys.argv[1:])}\n")
# [v6.2] v6.1 이 output 에 남긴 화면 기록은 반출되지 않게 work/logs/v61_runlog/ 로 옮김 (지우지 않음)
for _old in ("runlog", "diagnose.txt"):
    _p = os.path.join(C.OUTPUT, _old)
    if os.path.exists(_p):
        import shutil
        _dst = os.path.join(C.WORK, "logs", "v61_runlog")
        os.makedirs(_dst, exist_ok=True)
        shutil.move(_p, os.path.join(_dst, _old if not os.path.exists(os.path.join(_dst, _old)) else f"{_old}_{int(T0)}"))
        print(f"# v6.1 이 남긴 output/{_old} → work/logs/v61_runlog/ 로 옮김 (반출하지 않음)")
steps = ["01_inspect.py", "02_network.py", "03_hbi.py", "04_validate.py", "05_export.py"]
if C.DATA_ROOT_PARCEL: steps.append("06_parcel.py")                                   # 필지 경로가 있으면 자동 포함
if any(v.get("path") for v in C.JOIN_DATA.values()): steps.append("07_join_dong.py")  # SKT·KCB 경로가 있으면
if "--sens" in sys.argv or (C.DATA_ROOT_DEM1M and getattr(C, "DEM1M_AUTO", False)):   # --sens, [v6.1] 또는 DEM 1m 폴더가 있으면
    steps.append("08_sensitivity.py")                                                 # (DEM 1m 가 있으면 08 에 "DEM 1m" 줄)
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

# [v6] --modes register,all : 건물 용도 방식 여러 개를 한 번에 (auto = check 가 고른 방식, 예: --modes auto,all). 01·02 는 한 번, 03 부터는 방식마다 output/<방식>/·work/<방식>/
MODES = None
MODE_NOTE = ""
LAST_MODES = os.path.join(C.WORK, "last_modes.txt")     # 지난번 --modes (--from 만 쳐도 같은 방식들로 이어서)
if "--modes" not in sys.argv and "--from" in sys.argv and os.path.exists(LAST_MODES):
    sys.argv += ["--modes", open(LAST_MODES, encoding="utf-8").read().strip()]
    MODE_NOTE = f"지난번 --modes {sys.argv[-1]} 를 그대로 씀"
if "--modes" in sys.argv:
    i = sys.argv.index("--modes")
    MODES_ARG = sys.argv[i + 1] if i + 1 < len(sys.argv) else ""          # 사용자가 친 그대로
    MODES = [m.strip().lower() for m in MODES_ARG.split(",") if m.strip()]
    if "auto" in MODES:                    # auto = check.py 가 고른 방식 (mapping 의 building_attr_chosen)
        ch = (C.MAPPING.get("building_attr_chosen") or "").strip().lower()
        if not ch:
            raise SystemExit("--modes 에 auto 가 있는데 check.py 가 고른 방식이 없습니다 → python check.py 먼저")
        full = [ch if m == "auto" else m for m in MODES]
        MODES = list(dict.fromkeys(full))
        if len(MODES) < len(full):         # 예: --modes auto,all 인데 check 가 all 을 고름 → 같은 계산을 두 번 하지 않음
            MODE_NOTE = (MODE_NOTE + " / " if MODE_NOTE else "") + f"auto = {ch} 이라 한 번만 실행 (방식: {', '.join(MODES)})"
    bad = [m for m in MODES if m not in ("layer", "register", "gisbld", "all")]
    if not MODES or bad:
        raise SystemExit(f"--modes 뒤에는 layer·register·gisbld·all 을 쉼표로 (예: --modes register,all). 틀린 값: {bad}")
    os.makedirs(C.WORK, exist_ok=True)
    open(LAST_MODES, "w", encoding="utf-8").write(MODES_ARG)
elif "--from" not in sys.argv and os.path.exists(LAST_MODES):
    os.remove(LAST_MODES)                  # --modes 없이 처음부터 돌리면 지난 방식 기억을 지움

# [v6] --from NN : 그 번호 단계부터 (예: --from 03). 02 를 건너뛰면 work/network.npz 가 있어야 함
if "--from" in sys.argv:
    i = sys.argv.index("--from")
    want = (sys.argv[i + 1] if i + 1 < len(sys.argv) else "").zfill(2)[:2]
    k = next((j for j, s in enumerate(steps) if s.startswith(want)), None)
    if k is None:
        raise SystemExit(f"--from {want}: 이번 실행 목록에 없는 단계입니다. 목록: {', '.join(s[:2] for s in steps)}")
    if k > 1 and not os.path.exists(os.path.join(C.WORK, "network.npz")):
        raise SystemExit("work/network.npz 가 없습니다 → 02 부터 (python run_all.py)")
    for m in (MODES or [None]):
        wb = os.path.join(C.WORK, m, "buildings_hbi.csv") if m else os.path.join(C.WORK, "buildings_hbi.csv")
        if k > 2 and not os.path.exists(wb):
            raise SystemExit(f"{os.path.relpath(wb, C.BASE)} 가 없습니다 → --from 03")
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


def out(s):
    print(s, flush=True)                   # [v6.2] 화면 글자는 lib/runlog 가 work/logs/ 에 기록 (output/runlog 는 쓰지 않음)


def code_memo(line):
    """[v6.2] 02 의 '도로구분(칸) 값: RDC014 소로 975, …' 줄 → 코드와 개수만 (코드 모양이 아닌 값은 글자 모양만, 이름표는 뺌)"""
    head, _, rest = line.partition(" 값: ")
    items, note = rest.split("  ← ")[0], (" ← " + rest.split("  ← ")[1]) if "  ← " in rest else ""
    kept = []
    for it in items.split(", "):
        tok, n = it.split(" ")[0], it.rsplit(" ", 1)[-1]
        if it.startswith("(빈 값)"):
            tok = "(빈 값)"
        elif not re.fullmatch(r"[A-Z]{2,5}\d{2,4}", tok):
            tok = _RL.shape(tok)
        kept.append(f"{tok} {n}")
    return f"{head.strip()} 값: {', '.join(kept)}{note if re.fullmatch(r' ← 뺄 값 [A-Z0-9, ]*', note) else ''}"


def write_summary(reds=None):
    """[v6.2] output/run_summary.txt: 단계별 결과·시간·경고 수·최대 메모리, 고른 방식, 빨강 수, 구조 메모 (값 없음, 한 쪽).
    요약을 못 써도 분석 결과와는 상관없으므로 run_all 을 멈추지 않음"""
    try:
        _write_summary(reds)
    except Exception as e:
        out(f"(요약 output/run_summary.txt 를 쓰지 못함: {type(e).__name__} → 결과 파일은 그대로)")


def _write_summary(reds):
    import csv
    L = [f"run_all 요약 ({_RL._version()}) - 값 없음, 전체 기록은 work/logs/ (반출하지 않음)",
         f"시작 {time.strftime('%m-%d %H:%M', time.localtime(T0))} · 걸린 시간 {round(time.time() - T0) // 60}분 · 명령: run_all.py {' '.join(sys.argv[1:])}",
         f"건물 용도 방식: {','.join(MODES) if MODES else C.BUILDING_ATTR_MODE} (check 가 고른 방식: {(C.MAPPING.get('building_attr_chosen') or '-').strip()})",
         f"대상 구: {','.join(C.TARGET_GU) or '전체'}" + (f" ({C.TARGET_NOTE})" if getattr(C, 'TARGET_NOTE', '') else ""), "",
         "단계   방식      결과   시간(초)  경고 줄 수  최대 메모리(MB)"]
    for st, md, rc, sec, nw, mb in RECS:
        res = "정상" if rc == 0 else ("Ctrl+C" if rc == "Ctrl+C" else f"멈춤 {rc}")
        L.append(f"{st[:2]:<6} {md or '-':<9} {res:<6} {sec:>7}   {nw:>5}       {mb if mb is not None else '-':>6}")
    if STOPPED:
        L += ["", f"멈춘 곳: {STOPPED['step']}{' [방식 ' + STOPPED['mode'] + ']' if STOPPED.get('mode') else ''} · 오류 번호 {STOPPED.get('code', '-')} "
              f"(화면의 메모 카드) · 원인: {STOPPED.get('why', '-')}"]
    for m in (MODES or [None]):
        f = os.path.join(C.OUTPUT, m, "summary.csv") if m else os.path.join(C.OUTPUT, "summary.csv")
        try:
            n = next((r["value"] for r in csv.DictReader(open(f, encoding="utf-8-sig")) if r["target"] == "medical" and r["metric"] == "분석 건물 수"), "-")
            if os.path.getmtime(f) < T0:
                n = f"{n} (이번 실행 아님)"
        except Exception:
            n = "-"
        r = (reds or {}).get(m)
        L.append(f"결과 {('output/' + m + '/') if m else 'output/'}: 의료 분석 건물 {n}" + ("" if r is None else f", 결과 점검표 빨강 {len(r)}개"))
    if MEMO:
        L += ["", "구조 메모 (다음 번들 맞춤용, 코드값과 개수만):"] + [f"  {x}" for x in dict.fromkeys(MEMO)]
    with open(os.path.join(C.OUTPUT, "run_summary.txt"), "w", encoding="utf-8-sig") as fh:
        fh.write("\n".join(L) + "\n")


out(f"# run_all.py {' '.join(sys.argv[1:])} / 단계: {', '.join(s[:2] for s in steps)} / 대상 구: {','.join(C.TARGET_GU) or '전체'} / "
    f"건물 용도 방식: {','.join(MODES) if MODES else C.BUILDING_ATTR_MODE} / AREA_BBOX: {C.AREA_BBOX}")
if MODE_NOTE:
    out(f"# {MODE_NOTE}")
if getattr(C, "TARGET_NOTE", ""):                  # [v6.1] 예: 대상 5개 구 중 1개 구만 자료 있음 (자료 없음: …)
    out(f"# 대상 구 범위: {C.TARGET_NOTE} → {','.join(C.TARGET_GU)} 만 분석")
try:
    from lib.schema import dump
    out(f"# 자료 구조 저장 → {os.path.relpath(dump(), C.BASE)}")
except Exception as e:                     # 구조 저장이 안 돼도 분석은 계속
    out(f"# 자료 구조 저장 실패 ({type(e).__name__}) → 분석은 계속")


C_LEVEL = re.compile(r"(Warning|ERROR|FATAL) \d+:|proj_\w+:|PROJ: |GDAL: ")    # GDAL·PROJ 가 C 쪽에서 직접 찍는 줄 (값이 들어갈 수 있음)


def run_step(s, mode=None):
    env = dict(os.environ, PYTHONIOENCODING="utf-8", PYTHONUNBUFFERED="1", HBI_RUNLOG_CHILD="1")   # 자식 출력은 UTF-8 로 받아 그대로 화면에 (자식 로그는 work/logs/)
    if mode:
        env["HBI_SUBRUN"] = mode
    else:
        env["HBI_NOPICK"] = "1"         # 방식 없이 돌 때 지난 --modes 결과 폴더를 고르지 않게 (config.py)
    args = [sys.executable, s] + (["--dem1m"] if s == "02_network.py" and "--dem1m" in sys.argv else [])
    stage = f"{s}{f' [방식 {mode}]' if mode else ''}"
    again = f"python run_all.py --from {s[:2]}"     # --modes 는 기억해 두므로 다시 안 쳐도 됨
    out(f"\n########## {s}{f'  [방식 {mode}]' if mode else ''} ##########")
    _RL.set_stage(f"{stage} 실행 중 (run_all)", f"같은 명령을 다시 ({again})")    # Ctrl+C 카드에 씀
    t0 = time.time()
    p = subprocess.Popen(args, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, env=env)
    CUR.update(p=p, rec=(s, mode, t0))
    tail, nwarn, had_card, peak = [], 0, False, None
    _RL.relay(True)                 # 자식 줄 끝에 run_all 자신의 메모리를 붙이지 않음
    try:
        for raw in p.stdout:
            line = raw.decode("utf-8", "replace").rstrip("\r\n")
            if C_LEVEL.match(line):
                line = _RL.mask(line)
            out(line)
            tail = (tail + [line])[-60:]
            nwarn += bool(re.match(r"\s*(! 경고|!! )", line))
            had_card = had_card or line.startswith(_RL.CARD_MARK)
            m = re.match(r"# 끝: .*최대(?: 메모리)? (\d+)MB", line)
            if m:
                peak = int(m.group(1))
            if s.startswith("02") and (" 값: " in line or "남긴 링크:" in line):
                MEMO.append(code_memo(re.sub(r"^\[\d\d:\d\d:\d\d\]\s*", "", line)) if " 값: " in line else re.sub(r"^\[\d\d:\d\d:\d\d\]\s*", "", line).strip())
        rc = p.wait()
    finally:
        _RL.relay(False)
    CUR.clear()
    RECS.append((s, mode, rc, round(time.time() - t0), nwarn, peak))
    if rc != 0:              # 0 이 아니면 = 오류로 끝남
        out(f"!! {s} 에서 중단. 위 오류 메시지를 확인하세요.")
        d = diagnose(tail, s)
        if d:
            out(f"!! 원인: {d[0]}\n!! 할 일: {d[1]}\n!! 고친 뒤: {again}")
        else:
            out(f"!! 알려진 오류가 아닙니다 → 위 메모 카드 다섯 줄을 적어 오세요 (반출하지 않아도 됨). 고친 뒤: {again}")
        # [v6.2] 자식이 카드를 띄웠으면 그 카드를, 못 띄웠으면(그 스크립트 자체의 문법 오류, C 코드 충돌 등) 마지막 화면으로 만든 카드를 적어 오게.
        #        요약은 output/run_summary.txt, 전체 기록은 work/logs/
        code = next((re.search(r"E\w\w-[0-9A-Z?]{6}", x).group(0) for x in tail if "1 오류 번호" in x and re.search(r"E\w\w-[0-9A-Z?]{6}", x)), None)
        if not had_card:              # C 코드 충돌이면 그 단계의 로그에 faulthandler 글자가 있음
            lg = None if any(_RL.FATAL.match(x) for x in tail) else _RL.latest_log(s, mode, t0)
            code = _RL.card_from_text(s, tail + (_RL.fatal_lines(lg) if lg else []), stage, rc)
        STOPPED.update(step=s, mode=mode, code=code or "-", why=_RL.mask(d[0]) if d else f"알 수 없음 ({_RL.rc_text(rc)})")
        _RL.suppress_card()       # run_all 자신의 카드는 띄우지 않음 (위 카드 하나만)
        write_summary()
        sys.exit(1)


def check_result(mode=None):
    """[v6] 결과 점검표 (lib/rcheck.py) → 화면 + output[/<방식>]/result_check.txt"""
    try:
        from lib.rcheck import report
        o = os.path.join(C.OUTPUT, mode) if mode else C.OUTPUT
        w = os.path.join(C.WORK, mode) if mode else C.WORK
        txt, reds = report(out=o, work=w, net_work=C.WORK_NET)
        out("\n" + txt)
        return reds
    except Exception as e:                 # 점검표가 실패해도 분석 결과는 그대로
        out(f"\n(결과 점검표를 만들지 못함: {type(e).__name__} → 결과 파일은 그대로)")
        return []


common = [s for s in steps if s[:2] in ("01", "02")]
per = [s for s in steps if s[:2] not in ("01", "02")]
summary_reds = {}
try:
    for s in common:
        run_step(s)
    for m in (MODES or [None]):
        for s in per:
            run_step(s, m)
        if per and any(x[:2] in ("03", "04", "05") for x in per) or not MODES:
            summary_reds[m] = check_result(m)
except KeyboardInterrupt:              # [v6.2] Ctrl+C: 어느 단계였는지 요약에 남기고 카드는 lib/runlog 가 (단계·할 일은 set_stage)
    if CUR:
        s, m, t0 = CUR["rec"]
        RECS.append((s, m, "Ctrl+C", round(time.time() - t0), 0, None))
        STOPPED.update(step=s, mode=m, code="Ctrl+C", why="Ctrl+C 로 멈춤")
        try:
            CUR["p"].wait(timeout=10)
        except Exception:
            CUR["p"].kill()
    write_summary()
    raise
_RL.set_stage()
if MODES:
    out("\n=== 방식별 결과 폴더 ===")
    for m in MODES:
        r = summary_reds.get(m, [])
        out(f"  output/{m}/  →  " + ("빨강 없음" if not r else f"빨강 {len(r)}개: {', '.join(dict.fromkeys(r))}"))
    out("  반출: output 폴더 하나 (방식별 결과가 output/<방식>/ 에 모두 들어 있음). 빨강이 있는 방식은 고친 뒤 다시 돌리거나, 빨강 없는 방식만 써도 됨")
write_summary(summary_reds)
out("# 요약 → output/run_summary.txt (전체 기록은 work/logs/, 반출하지 않음)")
