# -*- coding: utf-8 -*-
"""
tools/print_zone_doc.py ─ 1차 방문 문서 → 인쇄용 A4 PDF (두 가지)
  docs/1차방문_구역별실행.md → .pdf  (상세판)
  docs/1차방문_따라하기.md   → .pdf  (초보자용: 본문 11pt, 명령 12pt, AREA_BBOX 14pt, 2쪽 이내)

[실행]  python3 tools/print_zone_doc.py            (Google Chrome 이 있어야 함: HTML 을 만들어 Chrome 으로 PDF 인쇄)
[하는 일]
  1. 이 문서에 쓰인 마크다운(제목, 목록, 표, 코드 블록, `코드`, **굵게**)만 HTML 로 바꿈 (표준 라이브러리만)
  2. 구역별 AREA_BBOX 표 바로 아래에 "옮겨 적을 줄" 칸을 넣음: 구역마다 한 줄씩 큰 글씨로 (안심구역에서 보고 옮겨 적기 쉽게)
  3. 표·코드 줄은 줄바꿈해서 종이 밖으로 잘리지 않게, 쪽 아래에 쪽 번호
[주의]  .md 를 고치면 이 스크립트를 다시 돌려 PDF 도 새로 만들어야 합니다.
"""
import html, os, re, subprocess, sys, tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"

CSS = """
@page { size: A4; margin: 14mm 13mm 16mm 13mm;
        @bottom-center { content: counter(page) " / " counter(pages); font: 9pt 'Apple SD Gothic Neo', sans-serif; color: #555; } }
body { font-family: 'Apple SD Gothic Neo', 'Malgun Gothic', sans-serif; font-size: 10pt; line-height: 1.45; color: #111; margin: 0; }
h1 { font-size: 17pt; margin: 0 0 6pt; } h2 { font-size: 12.5pt; margin: 13pt 0 5pt; border-bottom: 1.2pt solid #333; padding-bottom: 2pt; break-after: avoid; }
p { margin: 3pt 0; } ul, ol { margin: 3pt 0 3pt 16pt; padding: 0; } li { margin: 1.5pt 0; }
code { font-family: Menlo, Consolas, monospace; font-size: 8.8pt; background: #f1f1f1; padding: 0 2pt; border-radius: 2pt; overflow-wrap: anywhere; }
pre { font-family: Menlo, Consolas, monospace; font-size: 7.5pt; background: #f4f4f4; border: 0.6pt solid #bbb; padding: 5pt 6pt;
      white-space: pre-wrap; overflow-wrap: anywhere; break-inside: avoid; margin: 4pt 0; }
table { border-collapse: collapse; width: 100%; table-layout: fixed; margin: 4pt 0; break-inside: avoid; }
th, td { border: 0.6pt solid #777; padding: 3pt 4pt; vertical-align: top; word-break: break-all; overflow-wrap: anywhere; font-size: 9pt; }
th { background: #e8e8e8; }
td code { font-size: 8.3pt; }
.bbox td code { font-size: 8pt; white-space: nowrap; word-break: keep-all; }
.big { border: 1.6pt solid #000; padding: 6pt 8pt; margin: 6pt 0 8pt; break-inside: avoid; }
.big .t { font-size: 10pt; font-weight: bold; margin-bottom: 4pt; }
.big .row { font-family: Menlo, Consolas, monospace; font-size: 15pt; line-height: 1.7; white-space: nowrap; }
.big .row b { display: inline-block; width: 1.6em; }
.rec td { height: 26pt; }
"""


# 표 머리글 → 열 너비(%) (따라하기판: 좁은 열이 한 글자씩 줄바꿈되지 않게)
WIDTHS = {("구역", "동네", "config.py 에 넣을 줄"): (8, 15, 77), ("명령", "화면 문구", "괜찮은 값"): (7, 55, 38),
          ("화면에 나온 것", "뜻", "할 일"): (35, 19, 46), ("화면 문구", "뜻 → 할 일"): (37, 63), ("무엇", "적어 둘 폴더"): (50, 50)}


def inline(t):
    """`코드` 를 먼저 자리표로 빼 두고 **굵게** 를 처리 (굵은 글씨 안에 코드가 있어도 되게)"""
    codes = []
    def keep(m):
        codes.append(f"<code>{html.escape(m.group(1))}</code>")
        return f"\x00{len(codes) - 1}\x00"
    e = html.escape(re.sub(r"`([^`]*)`", keep, t))
    e = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", e)
    return re.sub(r"\x00(\d+)\x00", lambda m: codes[int(m.group(1))], e)


def cells(line):
    return [c.strip() for c in line.strip().strip("|").split("|")]


def convert(md, big=True):
    lines = md.split("\n")
    out, i, stack = [], 0, []            # stack: 열린 목록 (들여쓰기, 태그)

    def close_lists(indent=-1):
        while stack and stack[-1][0] > indent:
            out.append(f"</li></{stack.pop()[1]}>")

    while i < len(lines):
        ln = lines[i]
        if ln.startswith("```"):
            close_lists()
            j = i + 1
            while j < len(lines) and not lines[j].startswith("```"):
                j += 1
            out.append("<pre>" + html.escape("\n".join(lines[i + 1:j])) + "</pre>")
            i = j + 1
            continue
        if ln.startswith("|") and i + 1 < len(lines) and re.match(r"^\|[-| :]+\|$", lines[i + 1].strip()):
            close_lists()
            head = cells(ln)
            rows = []
            j = i + 2
            while j < len(lines) and lines[j].startswith("|"):
                rows.append(cells(lines[j]))
                j += 1
            rec = all(sum(1 for c in r if c and c != "[ ]") <= 2 for r in rows)      # 빈 기록표
            cols = "".join(f'<col style="width:{w}%">' for w in WIDTHS[tuple(head)]) if tuple(head) in WIDTHS else "<col>" * len(head)
            if "config.py 에 넣을 줄" in head and len(head) == 5:
                cols = '<col style="width:5%"><col style="width:11%"><col style="width:43%"><col style="width:13%"><col style="width:28%">'
            klass = "rec" if rec else ("bbox" if "config.py 에 넣을 줄" in head else "")
            out.append(f'<table class="{klass}"><colgroup>{cols}</colgroup><tr>' + "".join(f"<th>{inline(h)}</th>" for h in head) + "</tr>")
            for r in rows:
                out.append("<tr>" + "".join(f"<td>{inline(c)}</td>" for c in r) + "</tr>")
            out.append("</table>")
            bb = [(r[0], re.search(r"`(AREA_BBOX = \[[^\]]+\])`", r[2]).group(1), r[1]) for r in rows
                  if len(r) > 2 and re.search(r"`AREA_BBOX = \[", r[2])]
            if bb and big:
                out.append('<div class="big"><div class="t">옮겨 적을 줄 (config.py 의 AREA_BBOX 줄을 구역마다 이 한 줄로 바꿈)</div>'
                           + "".join(f'<div class="row"><b>{html.escape(z)}</b>{html.escape(line)}</div>' for z, line, _ in bb) + "</div>")
            i = j
            continue
        m = re.match(r"^(\s*)([-*]|\d+\.)\s+(.*)$", ln)
        if m:
            ind, tag = len(m.group(1)), ("ol" if m.group(2)[0].isdigit() else "ul")
            while stack and stack[-1][0] > ind:                 # 더 깊은 목록 닫기
                out.append(f"</li></{stack.pop()[1]}>")
            if stack and stack[-1][0] == ind:
                if stack[-1][1] == tag:
                    out.append("</li>")
                else:
                    out.append(f"</li></{stack.pop()[1]}><{tag}>"); stack.append((ind, tag))
            else:                                                 # 새 목록(처음이거나 한 단계 안쪽)
                out.append(f"<{tag}>"); stack.append((ind, tag))
            out.append("<li>" + inline(m.group(3)))
            i += 1
            continue
        close_lists()
        if ln.startswith("# "):
            out.append(f"<h1>{inline(ln[2:])}</h1>")
        elif ln.startswith("## "):
            out.append(f"<h2>{inline(ln[3:])}</h2>")
        elif ln.strip():
            out.append(f"<p>{inline(ln)}</p>")
        i += 1
    close_lists()
    return "\n".join(out)


EASY_CSS = """
@page { size: A4; margin: 11mm 12mm 13mm 12mm;
        @bottom-center { content: counter(page) " / " counter(pages); font: 9pt 'Apple SD Gothic Neo', sans-serif; color: #555; } }
body { font-family: 'Apple SD Gothic Neo', 'Malgun Gothic', sans-serif; font-size: 11pt; line-height: 1.3; color: #000; margin: 0; }
h1 { font-size: 15pt; margin: 0 0 2pt; } h2 { font-size: 12.5pt; margin: 6pt 0 2pt; background: #222; color: #fff; padding: 1pt 6pt; break-after: avoid; }
p { margin: 1.5pt 0; } ul, ol { margin: 0 0 1pt 18pt; padding: 0; } li { margin: 0; }
code { font-family: Menlo, Consolas, monospace; font-size: 10pt; background: #eee; padding: 0 2pt; overflow-wrap: anywhere; }
pre { font-family: Menlo, Consolas, monospace; font-size: 12pt; line-height: 1.25; background: #fff; border: 1.2pt solid #000; padding: 1.5pt 7pt;
      white-space: pre-wrap; overflow-wrap: anywhere; break-inside: avoid; margin: 2pt 0; }
table { border-collapse: collapse; width: 100%; table-layout: fixed; margin: 2pt 0; break-inside: avoid; }
th, td { border: 0.8pt solid #555; padding: 1.5pt 4pt; vertical-align: top; font-size: 10pt; line-height: 1.25; overflow-wrap: anywhere; }
th { background: #ddd; }
td code { font-size: 9.5pt; }
table.bbox td { vertical-align: middle; font-size: 11pt; white-space: nowrap; }
table.bbox td code { font-size: 14pt; background: none; white-space: nowrap; font-weight: bold; }
"""

DOCS = [("1차방문_구역별실행", CSS, True, None), ("1차방문_따라하기", EASY_CSS, False, 2)]


def main():
    if not os.path.exists(CHROME):
        raise SystemExit(f"Google Chrome 이 없습니다: {CHROME}")
    for name, css, big, max_pages in DOCS:
        src, out = os.path.join(ROOT, "docs", name + ".md"), os.path.join(ROOT, "docs", name + ".pdf")
        body = convert(open(src, encoding="utf-8").read(), big=big)
        doc = f'<!doctype html><html lang="ko"><head><meta charset="utf-8"><title>{name}</title><style>{css}</style></head><body>{body}</body></html>'
        with tempfile.TemporaryDirectory() as td:
            hp = os.path.join(td, "doc.html")
            open(hp, "w", encoding="utf-8").write(doc)
            subprocess.run([CHROME, "--headless", "--disable-gpu", "--no-pdf-header-footer", f"--print-to-pdf={out}", "file://" + hp],
                           check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        pages = len(re.findall(rb"/Type\s*/Page[^s]", open(out, "rb").read()))
        print(f"→ {os.path.relpath(out, ROOT)} ({pages}쪽)")
        if max_pages and pages > max_pages:
            raise SystemExit(f"!! {name}.pdf 가 {pages}쪽 → {max_pages}쪽 이내로 줄여야 함")


if __name__ == "__main__":
    main()
