# -*- coding: utf-8 -*-
"""
tools/make_codebook.py ─ 수치지형도 정의서 별표 2 → analysis/hbi/lib/codebook.py (코드 ↔ 코드명 표)

[왜]  1차 반출(10/2)에서 수치지형도 칸이 한글 필드명(용도·종류·층수·구조 …)이었고, 값이 코드(BDU001)인지
      한글 코드명(주거용단독주택)인지는 자료마다 다를 수 있음. 정의서 표를 그대로 옮겨 두고 v6.1 이 값을 코드로 맞춤.
[원본]  docs/한국국토정보공사_데이터정의서.xlsx 의 시트 "별표. 수치지형도 지형지물 속성목록(제15조 관련)"
        (수치지형도 작성 작업 및 성과에 관한 규정 [별표 2], 2026. 5. 28. 개정). 값을 추정해 넣지 않고 표 그대로 옮김
[실행]  python3 tools/make_codebook.py      → analysis/hbi/lib/codebook.py 를 새로 씀 (손으로 고치지 말 것)
"""
import os, re, zipfile, xml.etree.ElementTree as ET

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "docs", "한국국토정보공사_데이터정의서.xlsx")
OUT = os.path.join(ROOT, "analysis", "hbi", "lib", "codebook.py")
M = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
R = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}"
# 옮길 레이어 (v6.1 이 쓰는 것만)
LAYERS = ["N3A_B0010000", "N3L_A0020000", "N3A_C0390000", "N3P_A0131122", "N3A_A0033320", "N3L_A0033330"]


def rows():
    z = zipfile.ZipFile(SRC)
    ss = ["".join(x.text or "" for x in si.iter(M + "t")) for si in ET.fromstring(z.read("xl/sharedStrings.xml")).findall(M + "si")]
    wb = ET.fromstring(z.read("xl/workbook.xml"))
    rid = {r.get("Id"): r.get("Target") for r in ET.fromstring(z.read("xl/_rels/workbook.xml.rels"))}
    sh = next(s for s in wb.iter(M + "sheet") if s.get("name").startswith("별표"))
    x = ET.fromstring(z.read("xl/" + rid[sh.get(R + "id")].lstrip("/").replace("xl/", "")))
    for row in x.iter(M + "row"):
        d = {}
        for c in row.iter(M + "c"):
            col = re.match(r"([A-Z]+)", c.get("r")).group(1)
            v = c.find(M + "v")
            if v is None:
                isv = c.find(M + "is")
                val = "".join(t.text or "" for t in isv.iter(M + "t")) if isv is not None else ""
            else:
                val = ss[int(v.text)] if c.get("t") == "s" else v.text
            d[col] = re.sub(r"\s+", " ", val).strip()
        yield d


def main():
    book, cur, title = {}, None, ""
    for i, d in enumerate(rows()):
        if i == 0:
            title = d.get("A", "")
        if i < 3:
            continue
        if d.get("B"):
            cur = d["B"] if d["B"] in LAYERS else None
            if cur:
                book[cur] = {"name": d.get("A", ""), "fields": {}}
            last = None
            continue
        if not cur:
            continue
        if d.get("D") and d["D"] != "축척별 구축대상 여부":
            last = d["D"]
            book[cur]["fields"][last] = {"name": d.get("E", ""), "type": d.get("F", ""), "codes": {}}
        if last and d.get("G") and d["G"] != "-":
            book[cur]["fields"][last]["codes"][d["G"]] = d.get("H", "")
    L = ['# -*- coding: utf-8 -*-',
         '"""',
         'lib/codebook.py ─ [v6.1] 수치지형도 코드 ↔ 코드명 (tools/make_codebook.py 가 정의서에서 만든 파일, 손으로 고치지 말 것)',
         f'  원본: {os.path.basename(SRC)} 의 "{title}"',
         '  쓰는 곳: lib/battr.py (건물 용도·종류), lib/qnetwork.py (계단 구조, 걸을 수 없는 도로), lib/mapping.py (한글 필드명 별칭)',
         '"""',
         '', 'LAYERS = {']
    for lay, v in book.items():
        L.append(f'    {lay!r}: {{"name": {v["name"]!r}, "fields": {{')
        for f, fv in v["fields"].items():
            L.append(f'        {f!r}: {{"name": {fv["name"]!r}, "type": {fv["type"]!r}, "codes": {fv["codes"]!r}}},')
        L.append('    }},')
    L += ['}', '',
          'import re as _re', '',
          '',
          'def _key(s):',
          '    """비교용: 공백·괄호·가운뎃점을 빼고 대문자 (예: "노유자(노인및어린이)시설" → "노유자노인및어린이시설")"""',
          '    return _re.sub(r"[\\s()（）·.,/]", "", str(s or "")).upper()',
          '',
          '',
          'def codes(layer, field):',
          '    """{코드: 코드명}. 레이어·필드가 없으면 {}"""',
          '    return LAYERS.get(layer, {}).get("fields", {}).get(field, {}).get("codes", {})',
          '',
          '',
          'def to_code(layer, field, value):',
          '    """값 → 정의서 코드. 코드(대소문자 무시)나 코드명(공백·괄호 무시) 모두 받음. 표에 없으면 원래 값을 대문자로"""',
          '    v = str(value or "").strip()',
          '    if not v:',
          '        return ""',
          '    cs = codes(layer, field)',
          '    up = v.upper()',
          '    if up in cs:',
          '        return up',
          '    k = _key(v)',
          '    for c, n in cs.items():',
          '        if _key(n) == k:',
          '            return c',
          '    return up',
          '',
          '',
          'def field_names(layer):',
          '    """{필드 코드: 한글 필드명} (예: BPRP_SE → 용도)"""',
          '    return {f: v["name"] for f, v in LAYERS.get(layer, {}).get("fields", {}).items()}',
          '']
    open(OUT, "w", encoding="utf-8").write("\n".join(L))
    n = sum(len(f["codes"]) for v in book.values() for f in v["fields"].values())
    print(f"→ {os.path.relpath(OUT, ROOT)}: 레이어 {len(book)}개, 필드 {sum(len(v['fields']) for v in book.values())}개, 코드 {n}개")


if __name__ == "__main__":
    main()
