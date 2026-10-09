# -*- coding: utf-8 -*-
"""
tools/lookup_error.py ─ [v6.2] 메모 카드의 오류 번호 → 파일·줄·함수·주변 코드 (밖에서, 반출 없이 원인 찾기)

[실행]  python3 tools/lookup_error.py E03-7K2Q4M --bundle deliverables/hbi_code_bundle_v6.2.txt   (안에서 쓴 번들 기준, 권장)
        python3 tools/lookup_error.py E03-7K2Q4M --rev v6.2-submitted     (git 판 기준: 그 판으로 만든 번들과 같은 내용 해시를 계산)
        python3 tools/lookup_error.py E03-7K2Q4M                         (지금 작업 폴더 analysis/hbi 기준 = 개발판)
[오류 번호]  E<단계>-<5자><확인 1자>. 단계 = 01~14, SU(setup), CK(check), RA(run_all). 하이픈·띄어쓰기는 빼도 됨.
        5자는 파일·줄과 판의 내용 해시(VERSION 의 #…)로 만든 값이라 **카드를 띄운 번들과 같은 판**에서 찾아야 함
        (판이 다르면 '찾지 못함'). 번호 계산은 고른 판 안의 lib/runlog.py 를 그대로 씀.
        손글씨 헷갈림: 5자·확인 쪽의 O→0, I·L→1, U→V 는 자동으로 고침. 확인 글자가 안 맞으면 한 글자 틀림·이웃 두 글자 바뀜 후보를,
        그래도 없으면 비슷한 글자(0↔D/Q/G/8, 1↔7/T, 2↔Z, 5↔S, 6↔G/E, 8↔B, 9↔G, M↔N/W, V↔Y)로 바꾼 후보를 찾음
[보이는 것]  파일:줄, 그 줄을 품은 함수, 앞뒤 4줄, 그 줄이 안내 멈춤(SystemExit·stop)이면 안내 글자
"""
import argparse, ast, os, re, subprocess, sys, types

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STAGE = {"SU": "setup.py", "CK": "check.py", "RA": "run_all.py"}
SKIP = {"__pycache__", "work", "output", "testdata"}
LOOK = {"0": "DQG8", "D": "0", "Q": "0", "G": "0698", "8": "0B", "1": "7T", "7": "1", "T": "1", "2": "Z", "Z": "2",
        "5": "S", "S": "5", "6": "GE", "E": "6", "B": "8", "9": "G", "M": "NW", "N": "M", "W": "M", "V": "Y", "Y": "V"}


def from_src(d):
    out = {}
    for dp, dns, fs in os.walk(d):
        dns[:] = [x for x in dns if x not in SKIP]
        for f in fs:
            if f.endswith(".py") or f == "VERSION":
                p = os.path.join(dp, f)
                out[os.path.relpath(p, d).replace(os.sep, "/")] = open(p, encoding="utf-8-sig").read()
    return out


def from_bundle(path):
    """번들 텍스트를 실행하지 않고 FILES['hbi6/…'] = r'…' 만 읽음"""
    tree = ast.parse(open(path, encoding="utf-8-sig").read())
    out = {}
    for n in tree.body:
        if isinstance(n, ast.Assign) and isinstance(n.targets[0], ast.Subscript) and getattr(n.targets[0].value, "id", "") == "FILES":
            k = n.targets[0].slice
            k = k.value if isinstance(k, ast.Constant) else getattr(k, "value", None)
            key = k.value if isinstance(k, ast.Constant) else k
            if isinstance(key, str) and (key.endswith(".py") or key.endswith("/VERSION")) and isinstance(n.value, ast.Constant):
                out[key.split("/", 1)[1]] = n.value.value
    return out


def from_rev(rev):
    names = subprocess.run(["git", "-C", ROOT, "ls-tree", "-r", "--name-only", rev, "analysis/hbi"], capture_output=True, check=True).stdout.decode("utf-8").split("\n")
    return {n[len("analysis/hbi/"):]: subprocess.run(["git", "-C", ROOT, "show", f"{rev}:{n}"], capture_output=True, check=True).stdout.decode("utf-8")
            for n in names if n.endswith(".py")}


def runlog_of(files):
    """고른 판의 lib/runlog.py 를 모듈로 (번호 계산을 그 판 그대로). 없으면 지금 작업트리 것"""
    src = files.get("lib/runlog.py")
    if src is None:
        sys.path.insert(0, os.path.join(ROOT, "analysis", "hbi"))
        import lib.runlog as R
        return R
    m = types.ModuleType("runlog_of_bundle")
    m.__file__ = os.path.join(ROOT, "_lookup_", "lib", "runlog.py")
    exec(compile(src, "lib/runlog.py", "exec"), m.__dict__)
    return m


def func_of(text, line):
    try:
        tree = ast.parse(text)
    except SyntaxError:
        return "(구문 분석 안 됨)"
    best = "(모듈 맨 위)"
    for n in ast.walk(tree):
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)) and n.lineno <= line <= getattr(n, "end_lineno", n.lineno):
            best = f"{'class' if isinstance(n, ast.ClassDef) else 'def'} {n.name} ({n.lineno}줄)"
    return best


def parse(code):
    s = re.sub(r"[\s\-_]", "", code.strip().upper())
    m = re.fullmatch(r"E([0-9A-Z]{2})([0-9A-Z?]{6})", s)
    if not m:
        return None
    stage, c6 = m.groups()
    c6 = c6.replace("O", "0").replace("I", "1").replace("L", "1").replace("U", "V")    # 단계 쪽(SU)은 건드리지 않음
    return stage, c6


def candidates(c6, R, level):
    """level 1: 한 글자 틀림 + 이웃 두 글자 바뀜, level 2: 헷갈림 표로 한두 글자"""
    out = set()
    if level == 1:
        out |= {c6[:i] + ch + c6[i + 1:] for i in range(6) for ch in R.ALPHA}
        out |= {c6[:i] + c6[i + 1] + c6[i] + c6[i + 2:] for i in range(5)}
    else:
        one = {c6[:i] + ch + c6[i + 1:] for i in range(6) for ch in LOOK.get(c6[i], "")}
        out |= one | {w[:j] + ch + w[j + 1:] for w in one for j in range(6) for ch in LOOK.get(w[j], "")}
    return {w for w in out if w != c6 and R.code_ok(w)}


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("code", help="오류 번호, 예: E03-7K2Q4M")
    g = ap.add_mutually_exclusive_group()
    g.add_argument("--src", default=os.path.join(ROOT, "analysis", "hbi"))
    g.add_argument("--bundle")
    g.add_argument("--rev")
    ap.add_argument("--salt", help="번호 소금(VERSION 의 # 뒤). 보통은 번들에서 읽음")
    a = ap.parse_args()
    p = parse(a.code)
    if not p:
        raise SystemExit(f"오류 번호 모양이 아닙니다: {a.code} (예: E03-7K2Q4M)")
    stage, c6 = p
    files = from_bundle(a.bundle) if a.bundle else (from_rev(a.rev) if a.rev else from_src(a.src))
    R = runlog_of(files)
    version = (files.get("VERSION") or "").strip()
    if a.salt is not None:
        salt = a.salt
    elif version:                                        # 번들(또는 풀린 hbi6 폴더)의 VERSION
        salt = R.salt_of(version)
    elif a.rev and hasattr(R, "content_hash"):           # git 판: 그 판으로 만든 번들과 같은 해시
        salt = R.content_hash(files)
        version = f"git {a.rev} #{salt}"
    else:
        salt, version = "", "개발판"
    src = a.bundle or a.rev or os.path.relpath(a.src, ROOT)
    print(f"오류 번호 E{stage}-{c6} · 단계 {STAGE.get(stage, stage + '_*.py')} · 코드 기준 {src} ({version}, 파일 {sum(k.endswith('.py') for k in files)}개)")
    if "?" in c6:
        raise SystemExit("번호가 '??????' 이면 오류가 우리 코드 밖에서 났음 → 카드의 3 오류 종류·4 내용과 work/logs 를 함께 봄")

    def scan(want):
        hits = []
        for rel, text in sorted(files.items()):
            if not rel.endswith(".py"):
                continue
            lines = text.split("\n")
            for ln in range(0, len(lines) + 2):
                if R.site_code(rel, ln, salt) in want:
                    hits.append((rel, ln, lines))
        return hits
    exact = R.code_ok(c6)
    hits = scan({c6}) if exact else []
    if not exact:
        print("!! 확인 글자가 맞지 않음 → 한 글자를 잘못 적었거나 이웃 두 글자가 바뀐 후보를 찾음")
    if not hits:
        cand = candidates(c6, R, 1)
        hits = scan(cand)
        if hits:
            print(f"   후보 번호로 찾음 (원래 번호로는 없음)")
    if not hits:
        cand = candidates(c6, R, 2)
        hits = scan(cand)
        if hits:
            print("   비슷한 글자로 바꾼 '가까운 후보' (확실하지 않음)")
    if not hits:
        print("찾지 못함 → (1) 적을 때 틀렸거나 (2) 카드를 띄운 번들과 다른 판일 수 있음 (--bundle 로 그 번들을 지정)")
        return

    def stage_ok(rel):
        b = os.path.basename(rel).lower()
        entry = "/" not in rel
        return not entry or (b[:2] == stage.lower() if stage.isdigit() else STAGE.get(stage) == b)
    hits.sort(key=lambda h: not stage_ok(h[0]))
    for rel, ln, lines in hits:
        flag = "" if stage_ok(rel) else "   (단계와 맞지 않음, 가능성 낮음)"
        print(f"\n▶ {rel}:{ln}   {func_of(chr(10).join(lines), ln)}   (번호 E{stage}-{R.site_code(rel, ln, salt)}){flag}")
        for k in range(max(1, ln - 4), min(len(lines), ln + 4) + 1):
            print(f"  {'>>' if k == ln else '  '} {k:5d}  {lines[k - 1]}")
        cur = lines[ln - 1] if 0 < ln <= len(lines) else ""
        if "SystemExit" in cur or re.search(r"\bstop\(", cur):
            print("  → 안내 멈춤 자리: 위 줄의 글자가 화면에 나온 안내 (카드 5 할 일)")


if __name__ == "__main__":
    main()
