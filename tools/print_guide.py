# -*- coding: utf-8 -*-
"""
tools/print_guide.py ─ docs/1차방문_안내서.md → 인쇄용 A4 PDF (docs/1차방문_안내서.pdf)

[실행]  python3 tools/print_guide.py        (Google Chrome 필요: HTML 을 만들어 Chrome 으로 PDF 인쇄)
[이 문서에만 쓰는 표기]
  # 제목           → 첫 번째는 문서 제목, 그다음부터는 "부" 표지 (새 쪽)
  ## 제목          → 새 쪽 (한 쪽에 한 단계). 부 표지 바로 뒤의 첫 ## 은 같은 쪽
  ### 제목         → 쪽을 넘기지 않는 작은 제목
  할 일: …          → 쪽 맨 위 큰 글씨 칸
  ```run 하는 일    → 입력 상자: 위에 "하는 일"(설명, 입력 안 함), 아래 검은 코드 상자(이 글자만 입력). 13pt 고정폭, 한 상자에 한 가지 일
  `$ 명령`         → 문장·표 속 입력할 명령 (검은 칸). 그냥 `이름` 은 회색 칸 = 찾을 글자, 입력 안 함
  ```screen 종류 제목 → 화면 예시 그림. 종류: cmd(OSGeo4W Shell) plaincmd(일반 명령 프롬프트) notepad(메모장) start(시작 메뉴 검색) explorer(탐색기 주소창) folder(폴더 목록)
      ⟦1⟧글자⟦/⟧   → 빨간 테두리 + 번호 동그라미 ① (본문 번호와 맞춤)
  | 성공하면 | 이상하면 |  → 초록·빨강 두 칸
[원칙]  화면 예시의 출력 글자는 맥 리허설(v4) 로그에서 그대로 가져옴. 경로만 D:\작업폴더\hbi 등으로 바꿈. 줄인 곳은 "…"
"""
import html, os, re, subprocess, sys, tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.abspath(sys.argv[1]) if len(sys.argv) > 1 else os.path.join(ROOT, "docs", "1차방문_안내서.md")   # 다른 안내서: python tools/print_guide.py <md> [pdf]
OUT = os.path.abspath(sys.argv[2]) if len(sys.argv) > 2 else os.path.splitext(SRC)[0] + ".pdf"
CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
CIRCLE = "①②③④⑤⑥⑦⑧⑨"
CAPTION = "화면 예시 — 실제 화면과 글꼴·색·숫자가 다를 수 있음"

CSS = """
@page { size: A4; margin: 12mm 13mm 12mm 13mm; }   /* 쪽 번호는 넣지 않음: 제목의 "0쪽~8쪽" 과 헷갈리지 않게 */
body { font-family: 'Apple SD Gothic Neo', 'Malgun Gothic', sans-serif; font-size: 12pt; line-height: 1.34; color: #000; margin: 0; }
h1 { font-size: 19pt; margin: 0 0 6pt; }
h2 { font-size: 16pt; margin: 0 0 5pt; padding: 3pt 8pt; background: #1f3b2d; color: #fff; break-before: page; }
h2.first { break-before: auto; margin-top: 10pt; }
h1.part { font-size: 20pt; break-before: page; margin: 0 0 6pt; padding: 6pt 10pt; border: 2.5pt solid #1f3b2d; color: #1f3b2d; }
h3 { font-size: 13.5pt; margin: 6pt 0 2pt; border-bottom: 1.2pt solid #1f3b2d; break-after: avoid; }
table.wide td code { font-size: 8.2pt; white-space: nowrap; }
pre.cmdbox.small { font-size: 9pt; font-weight: normal; }
p { margin: 2pt 0; } ol, ul { margin: 2pt 0 3pt 20pt; padding: 0; } li { margin: 1pt 0; }
.todo { font-size: 14pt; font-weight: bold; border: 2pt solid #1f3b2d; background: #eef5f0; padding: 3pt 9pt; margin: 3pt 0 5pt; }
.todo small { display: block; font-size: 10pt; font-weight: normal; color: #1f3b2d; }
code { font-family: Menlo, Consolas, monospace; font-size: 11pt; background: #eee; padding: 0 2pt; overflow-wrap: anywhere; }
pre.cmdbox { font-family: Menlo, Consolas, monospace; font-size: 13pt; font-weight: bold; border: 1.6pt solid #000; background: #fff;
             padding: 4pt 9pt; margin: 4pt 0; white-space: pre-wrap; overflow-wrap: anywhere; break-inside: avoid; }
table { border-collapse: collapse; width: 100%; table-layout: fixed; margin: 5pt 0; break-inside: avoid; }
th, td { border: 0.9pt solid #555; padding: 2pt 5pt; vertical-align: top; font-size: 10.5pt; line-height: 1.26; overflow-wrap: anywhere; }
th { background: #ddd; }
td code { font-size: 10pt; }
table.bbox td { vertical-align: middle; white-space: nowrap; font-size: 12pt; }
table.bbox td code { font-size: 15pt; font-weight: bold; background: none; }
table.memo td { height: 22pt; }
table.memo2 td { height: 30pt; vertical-align: middle; }
.run { margin: 3pt 0 3pt; break-inside: avoid; }
.run .what { font-size: 10.5pt; color: #1f3b2d; margin: 0 0 1.5pt 1pt; }
.run .what b { background: #e3efe6; padding: 0 4pt; margin-right: 4pt; border-radius: 2pt; }
.run .box { display: flex; border: 1.4pt solid #111; background: #1e1e1e; }
.run .tag { background: #f2c94c; color: #000; font: bold 10pt 'Apple SD Gothic Neo', sans-serif; padding: 4pt 6pt; display: flex; align-items: center; }
.run pre { flex: 1; min-width: 0; margin: 0; padding: 2.5pt 9pt; color: #fff; font: bold 13pt/1.35 Menlo, Consolas, monospace; white-space: pre-wrap; overflow-wrap: anywhere; }
.run.small pre { font-size: 9.5pt; font-weight: normal; }
kbd { font: bold 10.5pt Menlo, Consolas, monospace; background: #1e1e1e; color: #fff; padding: 0.5pt 4pt; border-radius: 2pt; overflow-wrap: anywhere; }
td kbd { font-size: 9.5pt; }
.okbad { display: flex; gap: 6pt; margin: 5pt 0 0; break-inside: avoid; }
.okbad div { flex: 1; border: 1.6pt solid; padding: 3pt 7pt; font-size: 10.5pt; line-height: 1.3; }
.okbad .ok { border-color: #2e7d32; background: #eef7ee; } .okbad .bad { border-color: #c62828; background: #fdeeee; }
.okbad b.h { display: block; font-size: 12pt; margin-bottom: 2pt; }
.shot { margin: 3pt 0 3pt; break-inside: avoid; }
.shot .cap { font-size: 8.5pt; color: #666; margin-top: 2pt; }
.shot .lab { font-size: 10pt; font-weight: bold; margin-bottom: 2pt; }
.win { border: 1pt solid #777; box-shadow: 1.5pt 1.5pt 0 #bbb; }
.win .tb { font: 9.5pt 'Segoe UI', 'Apple SD Gothic Neo', sans-serif; padding: 2pt 6pt; background: #f0f0f0; border-bottom: 1pt solid #ccc; display: flex; justify-content: space-between; }
.win .tb .ctl { letter-spacing: 9pt; color: #444; }
.win.cmd .tb { background: #fff; }
.win.cmd .body { background: #0c0c0c; color: #ececec; font: 8.8pt/1.32 Menlo, Consolas, monospace; padding: 5pt 7pt; white-space: pre-wrap; overflow-wrap: anywhere; }
.win.note .menu { font: 9pt 'Apple SD Gothic Neo', sans-serif; padding: 1pt 6pt; border-bottom: 1pt solid #ddd; color: #333; word-spacing: 6pt; }
.win.note .body { background: #fff; color: #000; font: 9.4pt/1.38 Menlo, Consolas, monospace; padding: 5pt 7pt; white-space: pre-wrap; overflow-wrap: anywhere; }
.win.start { width: 60%; background: #f3f3f3; }
.win.start .search { margin: 7pt; padding: 4pt 8pt; background: #fff; border: 1pt solid #888; border-radius: 12pt; font-size: 11pt; }
.win.start .item { margin: 3pt 7pt 8pt; padding: 5pt 8pt; background: #fff; font-size: 11pt; }
.pair { display: flex; gap: 8pt; break-inside: avoid; } .pair .shot { flex: 1; min-width: 0; }
.shot.narrow { width: 52%; }
.win.exp .addr { margin: 5pt 7pt; padding: 3pt 7pt; border: 1pt solid #888; background: #fff; font: 11pt Menlo, Consolas, monospace; }
.win.exp .body { background: #fff; padding: 4pt 9pt 7pt; font-size: 11pt; }
.win.exp .row { padding: 1pt 0; } .win.exp .row::before { content: "📁 "; }
.hl { outline: 2.2pt solid #e00000; outline-offset: 1.5pt; border-radius: 2pt; position: relative; }
.badge { display: inline-block; background: #e00000; color: #fff; font: bold 10pt 'Apple SD Gothic Neo', sans-serif; border-radius: 50%;
         width: 14pt; height: 14pt; line-height: 14pt; text-align: center; margin-left: 5pt; vertical-align: 1pt; }
.dim { color: #888; }
"""


def inline(t):
    codes = []

    def keep(m):
        c = m.group(1)
        codes.append(f"<kbd>{html.escape(c[2:])}</kbd>" if c.startswith("$ ") else f"<code>{html.escape(c)}</code>")
        return f"\x00{len(codes) - 1}\x00"
    e = html.escape(re.sub(r"`([^`]*)`", keep, t))
    e = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", e)
    return re.sub(r"\x00(\d+)\x00", lambda m: codes[int(m.group(1))], e)


def marks(text):
    """⟦n⟧…⟦/⟧ → 빨간 테두리 + 번호 (이미 html escape 된 글자에 적용)"""
    return re.sub(r"⟦(\d)⟧(.*?)⟦/⟧", lambda m: f'<span class="hl">{m.group(2)}</span><span class="badge">{m.group(1)}</span>', text, flags=re.S)


def screen(kind, title, body):
    esc = html.escape(body)
    lab = f'<div class="lab">{html.escape(title)}</div>' if title and kind in ("cmd", "plaincmd", "notepad") else ""
    ctl = '<span class="ctl">–□✕</span>'
    if kind in ("cmd", "plaincmd"):                       # plaincmd = QGIS 가 아닌 일반 명령 프롬프트
        lines = [f'<span class="dim">{ln}</span>' if ln.strip() == "…" else ln for ln in esc.split("\n")]
        wt = "OSGeo4W Shell" if kind == "cmd" else "명령 프롬프트"
        w = f'<div class="win cmd"><div class="tb"><span>{wt}</span>{ctl}</div><div class="body">{marks(chr(10).join(lines))}</div></div>'
    elif kind == "notepad":
        w = (f'<div class="win note"><div class="tb"><span>config.py - 메모장</span>{ctl}</div>'
             f'<div class="menu">파일(F) 편집(E) 서식(O) 보기(V) 도움말(H)</div><div class="body">{marks(esc)}</div></div>')
    elif kind == "start":
        q, *items = esc.split("\n")
        w = (f'<div class="win start"><div class="search">🔍 {q}</div>'
             + "".join(f'<div class="item">{marks(it)}</div>' for it in items) + "</div>")
    elif kind == "explorer":
        w = f'<div class="win exp"><div class="tb"><span>파일 탐색기</span>{ctl}</div><div class="addr">{marks(esc)}</div><div class="body">…</div></div>'
    elif kind == "folder":
        w = (f'<div class="win exp"><div class="tb"><span>파일 탐색기</span>{ctl}</div><div class="addr">{html.escape(title)}</div>'
             f'<div class="body">' + "".join(f'<div class="dim">… (파일은 줄임)</div>' if r.strip() == "…" else f'<div class="row">{marks(r)}</div>'
                                       for r in esc.split("\n")) + "</div></div>")
    else:
        raise SystemExit(f"모르는 화면 종류: {kind}")
    narrow = " narrow" if kind == "folder" else ""
    return f'<div class="shot{narrow}">{lab}{w}<div class="cap">{CAPTION}</div></div>'


def cells(line):
    return [c.strip() for c in line.strip().strip("|").split("|")]


WIDTHS = {("물어볼 것", "받아 적을 주소"): (52, 48), ("화면 문구", "뜻 → 할 일"): (40, 60), ("구역", "동네", "메모장에 넣을 줄"): (9, 15, 76),
          ("화면에 나온 것", "뜻", "할 일"): (36, 19, 45), ("자료", "config.py 에서 찾을 이름", "미리 넣은 열 (정의서 기준)"): (18, 34, 48), ("항목", "적을 것"): (34, 66), ("순서", "할 일", "입력"): (12, 50, 38), ("부", "누가 보나", "내용"): (24, 26, 50),
          ("순서", "할 일", "명령 / 바꿀 줄"): (14, 46, 40), ("단계", "화면 문구", "기준"): (8, 40, 52), ("찾을 줄 (처음 모습)", "바꿀 내용"): (50, 50),
          ("볼 줄", "연습 구역 1", "연습 구역 2"): (40, 28, 32), ("항목", "이 맥 (리허설)", "안심구역 (Windows, QGIS 3.32)"): (16, 32, 52),
          ("구역", "대상 구", "config.py 에 넣을 줄", "크기", "들어 있는 선정지 (잘린 선까지 거리)"): (6, 11, 42, 14, 27), ("구역", "① 최대 연결망 노드 비율", "② 데이터 경계 500m 이내 (x%)", "끝났나 ○/×", "×일 때 오류 마지막 줄"): (8, 20, 22, 14, 36)}


def convert(md):
    lines = md.split("\n")
    out, i, lst, title_done, after_part = [], 0, None, False, False

    def close():
        nonlocal lst
        if lst:
            out.append(f"</{lst}>"); lst = None

    while i < len(lines):
        ln = lines[i]
        if ln.startswith("```"):
            close()
            info = ln[3:].strip()
            j = i + 1
            while not lines[j].startswith("```"):
                j += 1
            body = "\n".join(lines[i + 1:j])
            if info.startswith("run"):
                small = " small" if max(len(x) for x in body.split("\n")) > 60 else ""
                what = f'<div class="what"><b>하는 일</b>{inline(info[3:].strip())}</div>' if info[3:].strip() else ""
                out.append(f'<div class="run{small}">{what}<div class="box"><span class="tag">입력</span><pre>{html.escape(body)}</pre></div></div>')
            elif info.startswith("screen"):
                parts = info.split(None, 2)
                html_ = screen(parts[1], parts[2] if len(parts) > 2 else "", body)
                short = parts[1] not in ("cmd", "plaincmd") and max(len(x) for x in body.split("\n")) <= 48
                # 바로 앞이 짧은 화면이면 나란히 두 칸으로 (쪽 수 줄이기)
                if short and out and out[-1].startswith("<!--short-->"):
                    out[-1] = '<div class="pair">' + out[-1][len("<!--short-->"):] + html_ + "</div>"
                else:
                    out.append(("<!--short-->" if short else "") + html_)
            else:
                small = "small" if max(len(x) for x in body.split("\n")) > 60 else ""   # 긴 줄(리허설 준비 줄·밖에서 할 일)은 작게
                out.append(f'<pre class="cmdbox {small}">{html.escape(body)}</pre>')
            i = j + 1
            continue
        if ln.startswith("|") and i + 1 < len(lines) and re.match(r"^\|[-| :]+\|$", lines[i + 1].strip()):
            close()
            head = cells(ln)
            rows, j = [], i + 2
            while j < len(lines) and lines[j].startswith("|"):
                rows.append(cells(lines[j])); j += 1
            if head == ["성공하면", "이상하면"]:
                out.append('<div class="okbad"><div class="ok"><b class="h">✔ 성공하면</b>' + inline(rows[0][0]) +
                           '</div><div class="bad"><b class="h">✘ 이상하면</b>' + inline(rows[0][1]) + "</div></div>")
            else:
                klass = "bbox" if "메모장에 넣을 줄" in head else ("memo" if "끝났나 ○/×" in head else ("memo2" if head == ["항목", "적을 것"] else ("wide" if "config.py 에 넣을 줄" in head else "")))
                cols = "".join(f'<col style="width:{w}%">' for w in WIDTHS[tuple(head)]) if tuple(head) in WIDTHS else ""
                out.append(f'<table class="{klass}"><colgroup>{cols}</colgroup><tr>' + "".join(f"<th>{inline(h)}</th>" for h in head) + "</tr>"
                           + "".join("<tr>" + "".join(f"<td>{inline(c)}</td>" for c in r) + "</tr>" for r in rows) + "</table>")
            i = j
            continue
        m = re.match(r"^(\d+\.|-)\s+(.*)$", ln)
        if m:
            tag = "ol" if m.group(1)[0].isdigit() else "ul"
            if lst != tag:                                   # 번호 목록이 상자 뒤에서 다시 시작해도 번호를 이어감 (예: 2. 부터)
                num = int(m.group(1)[:-1]) if tag == "ol" else 1
                close(); out.append(f'<{tag} start="{num}">' if num > 1 else f"<{tag}>"); lst = tag
            out.append(f"<li>{inline(m.group(2))}</li>")
            i += 1
            continue
        close()
        if ln.startswith("# "):
            if not title_done:
                out.append(f"<h1>{inline(ln[2:])}</h1>"); title_done = True
            else:
                out.append(f'<h1 class="part">{inline(ln[2:])}</h1>'); after_part = True
        elif ln.startswith("## "):
            out.append(f'<h2 class="{"first" if after_part else ""}">{inline(ln[3:])}</h2>'); after_part = False
        elif ln.startswith("### "):
            out.append(f"<h3>{inline(ln[4:])}</h3>")
        elif ln.startswith("할 일:"):
            out.append(f'<div class="todo"><small>이 단계에서 할 일</small>{inline(ln[4:].strip())}</div>')
        elif ln.strip():
            out.append(f"<p>{inline(ln)}</p>")
        i += 1
    close()
    return "\n".join(out)


def main():
    if not os.path.exists(CHROME):
        raise SystemExit(f"Google Chrome 이 없습니다: {CHROME}")
    doc = (f'<!doctype html><html lang="ko"><head><meta charset="utf-8"><title>1차 방문 안내서</title><style>{CSS}</style></head>'
           f'<body>{convert(open(SRC, encoding="utf-8").read())}</body></html>')
    with tempfile.TemporaryDirectory() as td:
        hp = os.path.join(td, "doc.html")
        open(hp, "w", encoding="utf-8").write(doc)
        subprocess.run([CHROME, "--headless", "--disable-gpu", "--no-pdf-header-footer", f"--print-to-pdf={OUT}", "file://" + hp],
                       check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    pages = len(re.findall(rb"/Type\s*/Page[^s]", open(OUT, "rb").read()))
    print(f"→ {os.path.relpath(OUT, ROOT)} ({pages}쪽)")


if __name__ == "__main__":
    main()
