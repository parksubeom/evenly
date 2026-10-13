# -*- coding: utf-8 -*-
"""
tools/real_day.py ─ [10/22 반출 결과 받은 날] 받은 반출 파일 → 실제 기획서·PDF·판정 줄까지 한 번에 (docs/22일_기획서_절차.md)

[실행]  cd deck && npm run real-day -- <받은 반출 zip 또는 폴더>      (deck/py.js 가 QGIS Python 으로 실행)
        다시 돌릴 때(inputs.json 을 고친 뒤 등)는 인자 없이: npm run real-day   (results/raw_export 에 있는 것으로)
        --later-ok : 관악 실측·상호제공 칸만 ___ 대신 "실측 후"·"상호제공데이터 확보 시" (build_v6.js --later-ok)
[하는 일]
  1. 놓기: zip 이면 풀고, 방식 폴더(layer·register·gisbld·all)가 든 층을 찾아 그 안을 results/raw_export/ 로 복사.
     results/raw_export 에 이미 있던 것은 results/raw_export_old/<시각>/ 로 옮김 (지우지 않음). 받은 파일은 그대로 둠
  2. 점검: run_summary.txt (판 번호·멈춘 곳·방식별 빨강), 대표 방식(run_meta is_rep_mode), 결과 점검표 빨강, 대표 방식의 파일
  3. 밖 도구: outside_elderly(고령인구) → outside_join_dong(독거노인) → public_baseline(공개 대조군, 분석한 구만) → [v6.3] outing_compare(SKT 지수, 없으면 공개 생활인구)
  4. prepare_deck_data --expect real → prep_photos(15장 사진) → build_v6.js --expect real → check_deck → render_deck (_render/final)
     → deliverables/언덕위우리동네_기획서_final.pptx · .pdf (PDF 는 렌더링으로 확인한 그 파일)
  5. 판정 줄: 실제판 후보 / inputs.json 채우고 다시 / --later-ok 로 다시 / 대비책 판
[결과] 화면 + _render/final/real_day_report.txt (값은 적지 않음: 파일 이름·개수·판정만)
"""
import csv, datetime, os, re, shutil, subprocess, sys, tempfile, time, zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW = os.path.join(ROOT, "results", "raw_export")
OLD = os.path.join(ROOT, "results", "raw_export_old")
DECK = os.path.join(ROOT, "deck")
NAME = "언덕위우리동네_기획서_final"
PPTX = os.path.join(ROOT, "deliverables", NAME + ".pptx")
PDF = os.path.join(ROOT, "deliverables", NAME + ".pdf")
RENDER = os.path.join(ROOT, "_render", "final")
MISSING = os.path.join(DECK, "data", "missing.txt")
MODES = ("layer", "register", "gisbld", "all")
EXPECT_CODE = "v6.2 #ddc743"                      # 반입본 (~/Downloads/2차_반입요청). 다르면 경고만
ALONE = os.path.join(ROOT, "data_public", "raw", "독거노인+현황(성별_동별)_20260929102221.csv")
NETWORK = os.path.join(ROOT, "data_public", "raw", "서울시 자치구별 도보 네트워크 공간정보.csv")
STATIONS = os.path.join(ROOT, "data_public", "subway_stations.csv")
# 대표 방식 폴더에 있어야 기획서 칸이 차는 파일 (없으면 그 칸이 누락으로 나옴)
NEED = ["summary.csv", "grid_hbi.csv", "dong_hbi.csv", "run_meta.csv", "result_check.txt", "validation_sites.csv",
        "validation_routes.csv", "validation_ablation.csv", "intervention_summary.csv", "intervention_wait.csv", "sensitivity.csv"]
OPT = ["isochrone_summary.csv", "siting_summary.csv", "dong_context.csv", "parcel_summary.csv", "validation_new_candidates.csv",
       "intervention_candidates.csv"]                     # [v6.3] 09 후보 자동 (17장)
INPUT_RE = re.compile(r"^(team_name|team_display|V6\.13\.visit\d)$")          # deck/inputs.json 에서 꼭 채울 칸 (팀명·방문일)
SURVEY_IN_RE = re.compile(r"^V6\.15\.(\d\.app|date)$")                                # 실측을 했으면 inputs.json (mapapp_min·survey_date)
LATER_OK_RE = re.compile(r"^V6\.15\.\d\.(app|meas|model)$|^V6\.15\.date$|^V6\.16\.meas_r$|^V6\.21\.(skt|kcb)$|^V6\.22\.acc$")   # build_v6.js 와 같게

LOG = []


def say(t=""):
    print(t, flush=True)
    LOG.append(t)


def run(label, cmd, cwd=ROOT):
    t0 = time.time()
    say(f"\n── {label}")
    say("   $ " + " ".join(os.path.relpath(c, ROOT) if os.path.isabs(c) and c.startswith(ROOT) else c for c in cmd))
    p = subprocess.run(cmd, cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, errors="replace")
    out = [l for l in p.stdout.splitlines() if l.strip()]
    for l in out[-12:]:
        say("   " + l)
    say(f"   → {'정상' if p.returncode == 0 else '실패 (종료 코드 %d)' % p.returncode} · {time.time() - t0:.0f}초")
    return p.returncode == 0, p.stdout


def read_csv(p):
    if not os.path.exists(p):
        return []
    with open(p, encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def unzip(zp, dest):
    with zipfile.ZipFile(zp) as z:
        for it in z.infolist():
            name = it.filename
            if not it.flag_bits & 0x800:             # 윈도우 zip 은 한글 이름이 CP949 (UTF-8 표시 없음)
                try:
                    name = name.encode("cp437").decode("cp949")
                except (UnicodeEncodeError, UnicodeDecodeError):
                    pass
            if name.startswith("__MACOSX/") or "/." in "/" + name:
                continue
            tgt = os.path.normpath(os.path.join(dest, name))
            if not tgt.startswith(os.path.normpath(dest) + os.sep):
                continue
            if name.endswith("/"):
                os.makedirs(tgt, exist_ok=True)
                continue
            os.makedirs(os.path.dirname(tgt), exist_ok=True)
            with z.open(it) as a, open(tgt, "wb") as b:
                shutil.copyfileobj(a, b)


def find_root(d):
    """방식 폴더(layer 등)/summary.csv 가 있는 가장 얕은 폴더. 방식 폴더 없이 summary.csv 가 맨 위에 있는 옛 형식도 받음"""
    best = None
    for cur, dirs, files in os.walk(d):
        dirs[:] = [x for x in dirs if x != "__MACOSX" and not x.startswith(".")]
        depth = os.path.relpath(cur, d).count(os.sep) + (cur != d)
        hit = any(os.path.exists(os.path.join(cur, m, "summary.csv")) for m in MODES) or \
            ("summary.csv" in files and os.path.basename(cur) not in MODES)
        if hit and (best is None or depth < best[0]):
            best = (depth, cur)
    return best[1] if best else None


def place(src):
    tmp = None
    if os.path.isfile(src) and src.lower().endswith(".zip"):
        tmp = tempfile.mkdtemp(prefix="evenly_export_")
        unzip(src, tmp)
        src = tmp
    if not os.path.isdir(src):
        raise SystemExit(f"!! 반출 파일을 찾지 못함: {src} (zip 파일이나 폴더 주소)")
    top = find_root(src)
    if not top:
        raise SystemExit(f"!! {src} 안에 summary.csv 가 든 방식 폴더(layer·register·gisbld·all)가 없습니다 → 받은 파일이 output 폴더인지 확인")
    for d in [top] + [os.path.join(top, m) for m in MODES]:
        if os.path.exists(os.path.join(d, "_source.txt")):
            raise SystemExit(f"!! {d} 에 _source.txt (가짜·공개 대역 표지)가 있습니다 → 실제 반출 파일이 아님")
    old = [x for x in os.listdir(RAW) if x != ".gitkeep"] if os.path.isdir(RAW) else []
    if old:
        dst = os.path.join(OLD, datetime.datetime.now().strftime("%m%d_%H%M%S"))
        os.makedirs(dst, exist_ok=True)
        for x in old:
            shutil.move(os.path.join(RAW, x), os.path.join(dst, x))
        say(f"   results/raw_export 에 있던 {len(old)}개 → {os.path.relpath(dst, ROOT)}/ 로 옮김 (지우지 않음)")
    os.makedirs(RAW, exist_ok=True)
    n = 0
    for x in os.listdir(top):
        if x.startswith(".") or x == "__MACOSX":
            continue
        a, b = os.path.join(top, x), os.path.join(RAW, x)
        if os.path.isdir(a):
            shutil.copytree(a, b)
        else:
            shutil.copy2(a, b)
        n += 1
    say(f"   {os.path.relpath(top, src) if top != src else '받은 폴더'} 안 {n}개 → results/raw_export/")
    if tmp:
        shutil.rmtree(tmp, ignore_errors=True)


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    later_ok = "--later-ok" in sys.argv[1:]
    t_all = time.time()
    say(f"=== real_day ({datetime.datetime.now():%m-%d %H:%M}) {'--later-ok' if later_ok else ''}")

    # 1. 놓기
    say("\n[1] 반출 파일 놓기")
    if args:
        place(os.path.abspath(os.path.expanduser(args[0])))
    elif not [x for x in os.listdir(RAW) if x != ".gitkeep"]:
        raise SystemExit("!! results/raw_export 가 비어 있습니다 → npm run real-day -- <받은 zip 또는 폴더>")
    else:
        say("   (인자 없음: results/raw_export 에 있는 것으로)")

    # 2. 점검
    say("\n[2] 반출 점검")
    stop = []
    rs = os.path.join(RAW, "run_summary.txt")
    if os.path.exists(rs):
        lines = open(rs, encoding="utf-8-sig", errors="replace").read().splitlines()
        m = re.search(r"hbi_code (v[\w.]+ #[0-9a-f]{6})", lines[0] if lines else "")
        code = m.group(1) if m else "?"
        say(f"   판: {code}" + ("" if code == EXPECT_CODE else f"  ! 반입본 {EXPECT_CODE} 와 다름 (반출 파일 모양은 같으면 계속)"))
        for l in lines:
            if l.startswith("대상 구:") or l.startswith("결과 output/") or "멈춘 곳" in l or "끝나지 않음" in l:
                say("   " + l.strip())
            if "멈춘 곳" in l or "끝나지 않음" in l:
                stop.append("run_summary: 마지막 실행이 끝나지 않음")
    else:
        say("   ! run_summary.txt 없음 (output 맨 위 파일이 빠졌는지 확인)")
    subs = [m for m in MODES if os.path.exists(os.path.join(RAW, m, "summary.csv"))]
    rep = None
    for m in subs:
        meta = {r.get("key"): r.get("value") for r in read_csv(os.path.join(RAW, m, "run_meta.csv"))}
        if meta.get("is_rep_mode") == "yes":
            rep = m
    if not subs and os.path.exists(os.path.join(RAW, "summary.csv")):
        rep = ""
    if rep is None:
        stop.append("대표 방식(run_meta.csv is_rep_mode = yes) 폴더가 없음")
        rep = subs[0] if subs else ""
    rd = os.path.join(RAW, rep) if rep else RAW
    meta = {r.get("key"): r.get("value") for r in read_csv(os.path.join(rd, "run_meta.csv"))}
    say(f"   방식 폴더: {', '.join(subs) or '(없음, 맨 위)'} · 대표 방식: {rep or '-'}")
    rc = os.path.join(rd, "result_check.txt")
    red = [l.strip() for l in open(rc, encoding="utf-8-sig", errors="replace")] if os.path.exists(rc) else []
    red = [l for l in red if l.startswith("[빨강]")]
    say(f"   대표 방식 결과 점검표 빨강: {len(red)}개" + "".join("\n     " + l for l in red))
    if red:
        stop.append(f"대표 방식 결과 점검표 빨강 {len(red)}개")
    miss_f = [f for f in NEED if not os.path.exists(os.path.join(rd, f))]
    opt_f = [f for f in OPT if not os.path.exists(os.path.join(rd, f))]
    iso = [f for f in os.listdir(rd) if f.startswith("map_isochrone_") and f.endswith(".png")] if os.path.isdir(rd) else []
    say(f"   대표 방식 파일: 필요 {len(NEED) - len(miss_f)}/{len(NEED)}" + (f" (없음: {', '.join(miss_f)})" if miss_f else "")
        + f" · 추가 분석 {len(OPT) - len(opt_f)}/{len(OPT)}" + (f" (없음: {', '.join(opt_f)})" if opt_f else "") + f" · 등시선 그림 {len(iso)}장")
    gus = [g.strip() for g in (meta.get("target_gu") or "").split(",") if g.strip()]
    if not gus:
        gus = sorted({(r.get("adm_nm") or "").split()[1] for r in read_csv(os.path.join(rd, "dong_hbi.csv")) if len((r.get("adm_nm") or "").split()) >= 3})
    say(f"   분석한 구: {', '.join(gus) or '?'}" + (f" ({meta['target_note']})" if meta.get("target_note") else ""))

    # 3. 밖 도구
    say("\n[3] 밖 도구 (고령인구 · 독거노인 · 공개 대조군)")
    py = sys.executable
    dh = os.path.join(rd, "dong_hbi.csv")
    soft = []
    ok, _ = run("고령인구 추정 (outside_elderly)", [py, os.path.join(ROOT, "tools", "outside_elderly.py"), dh])
    ok or soft.append("outside_elderly")
    if os.path.exists(ALONE):
        ok, _ = run("독거노인 붙이기 (outside_join_dong)", [py, os.path.join(ROOT, "tools", "outside_join_dong.py"), "--dong", dh,
                                                       "--stat", ALONE, "--label", "alone65", "--cols", "합계"])
        ok or soft.append("outside_join_dong")
    else:
        say(f"\n── 독거노인: {os.path.relpath(ALONE, ROOT)} 없음 → 21장 독거노인 칸이 누락으로 나옴")
        soft.append("독거노인 파일 없음")
    if os.path.exists(NETWORK) and os.path.exists(os.path.join(rd, "grid_hbi.csv")):
        cmd = [py, os.path.join(ROOT, "tools", "public_baseline.py"), "--network", NETWORK, "--stations", STATIONS,
               "--lx-grid", os.path.join(rd, "grid_hbi.csv")] + (["--gu", ",".join(gus)] if gus else [])
        ok, _ = run("공개 대조군 (public_baseline)", cmd)
        ok or soft.append("public_baseline")
    else:
        say("\n── 공개 대조군: 도보 네트워크 파일 또는 grid_hbi.csv 없음 → 16장 공개데이터 칸이 누락으로 나옴")
        soft.append("공개 대조군 건너뜀")

    if os.path.exists(os.path.join(rd, "points_SKT_60대이상유동인구_dong.csv")) or os.path.exists(os.path.join(ROOT, "data_public", "living65_outing.csv")):
        # [v6.3] 외출 비교 그림 (SKT 지수·KCB, 동 단위). [10/13] SKT 가 없으면 공개 서울 생활인구 65세 이상 (tools/prep_living_pop.py)
        ok, _ = run("외출 비교 (outing_compare)", [py, os.path.join(ROOT, "tools", "outing_compare.py"), "--src", RAW])
        ok or soft.append("outing_compare")

    # 4. 기획서
    say("\n[4] 기획서 (prepare → build → check_deck → 렌더링)")
    ok, _ = run("결과 → results.json (prepare_deck_data --expect real)",
                [py, os.path.join(ROOT, "tools", "prepare_deck_data.py"), "--src", RAW, "--expect", "real"])
    if not ok:
        stop.append("prepare_deck_data 실패")
        return finish(stop, soft, later_ok, t_all, built=False)
    ok, _ = run("15장 사진 (prep_photos: 바로 세우기·촬영 정보 지우기)", [py, os.path.join(ROOT, "tools", "prep_photos.py")])
    ok or soft.append("prep_photos")
    ok, out = run("기획서 만들기 (build_v6.js --expect real" + (" --later-ok" if later_ok else "") + ")",
                  ["node", "build_v6.js", "--expect", "real"] + (["--later-ok"] if later_ok else []), cwd=DECK)
    if not ok:
        stop.append("build_v6.js 실패")
        return finish(stop, soft, later_ok, t_all, built=False)
    ok, out = run("빈칸 대조 (check_deck)", [py, os.path.join(ROOT, "tools", "check_deck.py"), PPTX, "--missing", MISSING])
    if not ok:
        stop.append("check_deck 통과 못 함")
    ok, _ = run("렌더링 (render_deck → _render/final)", [py, os.path.join(ROOT, "tools", "render_deck.py"), PPTX, "--out", RENDER])
    rp = os.path.join(RENDER, NAME + ".pdf")
    if ok and os.path.exists(rp):
        shutil.copy2(rp, PDF)
        say(f"   PDF → {os.path.relpath(PDF, ROOT)} (렌더링으로 확인하는 그 파일)")
    else:
        stop.append("렌더링 실패 (PDF 없음)")
    return finish(stop, soft, later_ok, t_all, built=True)


def finish(stop, soft, later_ok, t_all, built):
    say("\n[5] 판정")
    miss, alt = [], []
    if built and os.path.exists(MISSING):
        for l in open(MISSING, encoding="utf-8"):
            k = re.search(r"\[([^\]]+)\]", l)
            if l.startswith("누락:") and k:
                miss.append((k.group(1), l.strip()))
            elif l.startswith("대체:") and k:
                alt.append(k.group(1))
    inp = [m for m in miss if INPUT_RE.match(m[0])]
    lok = [m for m in miss if not INPUT_RE.match(m[0]) and LATER_OK_RE.match(m[0])]
    other = [m for m in miss if not INPUT_RE.match(m[0]) and not LATER_OK_RE.match(m[0])]
    if built:
        say(f"   누락 {len(miss)}건 = deck/inputs.json {len(inp)} · 실측·상호제공 {len(lok)} · 그 밖 {len(other)}"
            + (f" · (--later-ok 로 바꾼 칸 {sum(1 for a in alt if LATER_OK_RE.match(a))})" if later_ok else ""))
        for k, l in inp + lok + other:
            say("     " + l)
    if soft:
        say(f"   밖 도구 문제: {', '.join(soft)} (해당 칸이 누락으로 나옴)")
    if stop or other:
        why = stop + ([f"그 밖 누락 {len(other)}건"] if other else [])
        verdict = f"대비책 판 (npm run build:fallback) — 이유: {'; '.join(why)}"
    elif inp:
        verdict = "deck/inputs.json 을 채우고 다시: npm run real-day   (위 inputs.json 줄)"
    elif lok and not later_ok:
        sv = [m for m in lok if SURVEY_IN_RE.match(m[0])]
        verdict = ("관악 실측·상호제공 칸만 비었음 → "
                   + (f"관악 실측을 했으면 deck/inputs.json 의 mapapp_min·survey_date 를 채우고 다시 (15장 {len(sv)}칸), 아니면 " if sv else "")
                   + "npm run real-day -- --later-ok (그 칸은 '실측 후'·'상호제공데이터 확보 시')")
    else:
        verdict = "실제판 후보 → 장별 확인 목록(docs/22일_기획서_절차.md)으로 _render/final 확인"
    say(f"   ▶ {verdict}")
    say(f"\n걸린 시간 {time.time() - t_all:.0f}초 · 기록: {os.path.relpath(os.path.join(RENDER, 'real_day_report.txt'), ROOT)}")
    os.makedirs(RENDER, exist_ok=True)
    with open(os.path.join(RENDER, "real_day_report.txt"), "w", encoding="utf-8") as f:
        f.write("\n".join(LOG) + "\n")
    return 0 if verdict.startswith("실제판") else 1


if __name__ == "__main__":
    sys.exit(main())
