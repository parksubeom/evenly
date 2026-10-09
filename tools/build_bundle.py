# -*- coding: utf-8 -*-
"""
tools/build_bundle.py ─ analysis/ 의 코드를 안심구역 반입용 텍스트 번들 하나로 묶기

[왜] 반입 허용 확장자에 .py/.zip 이 없어서, 모든 파일을 txt 하나에 담고 실행하면 풀리게 만듭니다.
[실행] 레포 최상위에서:  python tools/build_bundle.py v5
[결과] deliverables/hbi_code_bundle_v5.txt
[주의] 코드 파일 안에 작은따옴표 세 개(''' 가 아닌 것) 제한이 있습니다 → 번들이 r-문자열로 감싸기 때문
"""
import os, sys
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ver = sys.argv[1] if len(sys.argv) > 1 else "vX"
Q3 = "'" * 3
SKIP_DIRS = {"__pycache__", "work", "output", "testdata"}

def collect(src, prefix, skip_external=False):
    out = {}
    for dp, dns, fs in os.walk(src):
        dns[:] = [d for d in dns if d not in SKIP_DIRS]
        for f in fs:
            p = os.path.join(dp, f)
            rel = os.path.relpath(p, src).replace(os.sep, "/")
            if skip_external and rel.startswith("external/"):
                continue
            if rel.startswith(("external/building_register", "external/gis_building")):   # [v6] 건축물대장 가공본은 크기 때문에 번들에 넣지 않고 따로 반입
                continue
            txt = open(p, encoding="utf-8-sig").read()
            assert Q3 not in txt and not txt.endswith("\\"), f"번들에 넣을 수 없는 문자열 포함: {p}"
            out[f"{prefix}/{rel}"] = txt
    return dict(sorted(out.items()))

# [v6] v6 부터는 hbi6/ 로 풀림 (안심구역에 남아 있는 v5 의 hbi/ 를 덮어쓰지 않게). hbi_geopandas(대체 구현)는 v6 에서 고치지 않아 넣지 않음
import re
_m = re.match(r"v?(\d+)", ver.lower())                 # [v6.1] "v6.1"·"v6-test" 도 6 으로 (v6 까지는 "6.1" 을 숫자로 못 읽었음)
V6 = bool(_m) and int(_m.group(1)) >= 6
A = collect(os.path.join(ROOT, "analysis", "hbi"), "hbi6" if V6 else "hbi")
B = {}
if not V6:
    B = collect(os.path.join(ROOT, "analysis", "hbi_geopandas"), "hbi_geopandas", skip_external=True)
    k = "hbi_geopandas/config.py"
    B[k] = B[k].replace('EXTERNAL = os.path.join(BASE, "external")  # 반입한 공개데이터 CSV',
                        'EXTERNAL = os.path.join(BASE, "..", "hbi", "external")  # 공개데이터는 hbi/external 공용')
files = {**A, **B}
_v62 = V6 and os.path.exists(os.path.join(ROOT, "analysis", "hbi", "lib", "runlog.py"))
if _v62:                                              # [v6.2] 메모 카드에 판 이름·내용 해시가 나오게 (lib/runlog.py 가 hbi6/VERSION 을 읽음)
    sys.path.insert(0, os.path.join(ROOT, "analysis", "hbi"))
    import lib.runlog as _RL
    SALT = _RL.content_hash({k.split("/", 1)[1]: v for k, v in A.items()})     # 오류 번호 소금: 판이 다르면 번호가 다름
    files["hbi6/VERSION"] = f"hbi_code {ver} #{SALT}\n"
    import subprocess as _sp
    _dirty = _sp.run(["git", "-C", ROOT, "status", "--porcelain", "--", "analysis/hbi"], capture_output=True, text=True).stdout.strip()
    if _dirty:
        print(f"!! analysis/hbi 에 커밋하지 않은 변경이 있음 ({len(_dirty.splitlines())}개 파일) → 번들의 판(#{SALT})과 git 판이 다를 수 있음. "
              "밖에서는 이 번들 파일로 찾기 (lookup_error.py --bundle)")
name = f"hbi_code_bundle_{ver}.txt"
# [v6.2] 풀린 뒤 안내: v6 부터는 hbi6/ 하나 (v6.1a 까지는 v5 때 글이 그대로 남아 있었음)
UNPACK = ("#   → 같은 폴더에 hbi6/ 폴더가 생깁니다 (1차 때의 hbi/ 는 그대로 둠).\n"
          "#   → 이후 cd hbi6 → python setup.py (hbi6/README.md 참고)\n") if V6 else (
          "#   → 같은 폴더에 hbi/ (기본, QGIS 내장 Python용) 와 hbi_geopandas/ (대체) 폴더가 생깁니다.\n"
          "#   → 이후 hbi/README.md 순서대로 실행 (python 01_inspect.py ...)\n")
hdr = f"""# -*- coding: utf-8 -*-
# =====================================================================
#  언덕 위 우리동네 - 분석 코드 묶음 {ver} (데이터안심구역 반입용)
#  반입 허용 확장자에 .py/.zip이 없어 모든 코드와 공개데이터를 이 텍스트 파일 하나에 담았습니다.
#
#  [압축 풀기] 아래 중 편한 방법 하나
#   A) OSGeo4W Shell(QGIS와 함께 설치됨)에서:   python {name}
#   B) QGIS 메뉴 플러그인 → Python 콘솔에서:
#        import os; os.chdir(r"이 파일이 있는 폴더"); exec(open("{name}", encoding="utf-8").read())
{UNPACK}#
#  아래 FILES 안의 내용은 각 파일의 원문 그대로이며, 누구나 읽고 검토할 수 있습니다.
# =====================================================================
import os
FILES = {{}}
"""
body = "".join(f"\n# ---------------------------------------------------------------- {k}\nFILES[{k!r}] = r{Q3}{v}{Q3}\n" for k, v in files.items())
tail = """
try:
    _out = os.path.dirname(os.path.abspath(__file__))
except NameError:
    _out = os.getcwd()
for _name, _text in FILES.items():
    _p = os.path.join(_out, *_name.split("/"))
    os.makedirs(os.path.dirname(_p), exist_ok=True)
    with open(_p, "w", encoding="utf-8-sig" if _name.endswith(".csv") else "utf-8") as _fp:
        _fp.write(_text)
for _d in (("hbi6/work", "hbi6/output") if "hbi6/setup.py" in FILES else ("hbi/work", "hbi/output", "hbi_geopandas/work", "hbi_geopandas/output")):
    os.makedirs(os.path.join(_out, *_d.split("/")), exist_ok=True)
print(f"완료: 파일 {len(FILES)}개 → {_out}")
print("다음: cd hbi6  →  python setup.py   (README.md 참고)" if "hbi6/setup.py" in FILES else
      "다음: cd hbi  →  python 01_inspect.py   (README.md 참고)")
"""
dst = os.path.join(ROOT, "deliverables", name)
open(dst, "w", encoding="utf-8").write(hdr + body + tail)
print(f"{len(files)}개 파일 → {dst} ({os.path.getsize(dst)//1024} KB)")

# [v6.2] 오류 번호표: 안내 멈춤(SystemExit·check 의 stop·'→' 안내가 든 raise) 자리마다 번호 뒤 6자 → docs/오류번호표_<판>.md (반입하지 않음, 밖에서 씀)
if _v62:
    rows = []
    for k, v in sorted(A.items()):
        rel = k.split("/", 1)[1]
        if not k.endswith(".py") or rel == "lib/runlog.py" or rel.startswith("tools/"):
            continue
        for i, ln in enumerate(v.split("\n"), 1):
            s_ = ln.strip()
            if s_.startswith(("#", "def ")) or re.search(r"SystemExit\(0\)|sys\.exit\((\d*|rc|code)\)", s_):
                continue                                   # 카드가 나오지 않는 자리 (정상 끝, 글자 없는 끝)
            if (re.search(r"raise SystemExit\(|(?<![\w.])stop\(", ln)
                    or (re.search(r"raise (RuntimeError|FileNotFoundError|ValueError)\(", ln) and re.search(r"→|확인", ln))):
                lit = re.search(r"f?([\"'])(.+?)\1", ln)
                txt = (lit.group(2) if lit else s_)[:70].replace("|", "/")
                rows.append(f"| {_RL.site_code(rel, i, SALT)} | {rel}:{i} | {txt} |")
    tbl = os.path.join(ROOT, "docs", f"오류번호표_{ver}.md")
    with open(tbl, "w", encoding="utf-8") as fh:
        fh.write(f"# 오류 번호표 ({name}, hbi_code {ver} #{SALT})\n\n"
                 "메모 카드의 오류 번호 `E<단계>-<6자>` 중 **뒤 6자**로 찾는다 (앞 두 글자는 단계: 01~14, SU=setup, CK=check, RA=run_all).\n"
                 "이 표는 안내 멈춤 자리만 적음. 그 밖의 번호(처리되지 않은 오류)는 "
                 f"`python3 tools/lookup_error.py <번호> --bundle deliverables/{name}` 로 파일·줄·주변 코드를 찾는다 (한 글자 틀림도 후보를 찾음). "
                 f"번호는 파일·줄과 판의 내용 해시(#{SALT})로 만들므로 판이 다르면 맞지 않음.\n\n| 번호 뒤 6자 | 파일:줄 | 안내 글자 (앞부분) |\n|---|---|---|\n")
        fh.write("\n".join(rows) + "\n")
    print(f"오류 번호표 {len(rows)}줄 → {os.path.relpath(tbl, ROOT)}")
