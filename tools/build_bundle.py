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
