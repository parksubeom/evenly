# -*- coding: utf-8 -*-
"""
tools/print_card.py ─ 1차 방문 한 장 카드 (v5, v4) → docs/1차방문_v5_카드.pdf, docs/1차방문_v4_카드.pdf

[실행]  python3 tools/print_card.py     (Google Chrome, pdftotext 필요)
[원칙]
  - 쪽 번호는 손으로 적지 않고 안내서 PDF 에서 단계 제목이 있는 쪽을 찾아 넣음 (안내서를 다시 만들면 이것도 다시 실행)
  - 카드의 명령은 안내서 md 의 입력 상자·검은 칸(`$ …`)에 있는 명령과 한 글자씩 같아야 하고,
    명령이 부르는 파일(01_inspect.py, hbi_code_bundle_v5.txt 등)은 번들에 있어야 함. 하나라도 어긋나면 PDF 를 만들지 않고 멈춤
  - 글자 14pt 이상, 명령 16pt 고정폭 굵게, 줄마다 □ 와 번호
"""
import html, os, re, subprocess, sys, tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
DOCS = os.path.join(ROOT, "docs")

CSS = """
@page { size: A4; margin: 8mm 8mm; }
body { font-family: 'Apple SD Gothic Neo', 'Malgun Gothic', sans-serif; font-size: 14pt; line-height: 1.25; margin: 0; color: #000; }
h1 { font-size: 19pt; margin: 0 0 4pt; padding: 3pt 8pt; background: #1f3b2d; color: #fff; }
h2 { font-size: 15pt; margin: 6pt 0 2pt; border-bottom: 1.6pt solid #1f3b2d; color: #1f3b2d; break-after: avoid; }
.gold { border: 2.4pt solid #c0392b; background: #fdf0ee; padding: 3pt 8pt; margin: 0 0 4pt; }
.gold b.t { color: #c0392b; font-size: 15pt; }
.gold ol { margin: 1pt 0 0 22pt; padding: 0; } .gold li { margin: 1pt 0; }
table { border-collapse: collapse; width: 100%; table-layout: fixed; }
tr { break-inside: avoid; }
td, th { border: 1pt solid #555; padding: 1.5pt 3pt; vertical-align: middle; font-size: 14pt; overflow-wrap: anywhere; }
th { background: #ddd; font-size: 14pt; }
td.box { text-align: center; font-size: 17pt; padding: 0; }
td.n { text-align: center; font-weight: bold; padding: 0; white-space: nowrap; }
td.pg { text-align: center; font-weight: bold; color: #1f3b2d; white-space: nowrap; padding: 0; }
code { font: bold 16pt Menlo, Consolas, monospace; background: #1e1e1e; color: #fff; padding: 0 3pt; white-space: nowrap; }
.see { font-size: 14pt; line-height: 1.15; }
.see q { font-family: Menlo, Consolas, monospace; font-size: 14pt; background: #eee; quotes: none; padding: 0 2pt; }
td.blank { height: 21pt; }
td.bbox code { font-size: 15pt; background: none; color: #000; }
tr.note td { background: #eef5f0; font-weight: bold; }
tr.sec td { background: #1f3b2d; color: #fff; font-weight: bold; font-size: 14pt; padding: 1pt 6pt; }
"""


def guide_pages(pdf):
    """안내서 PDF 에서 '단계 N.' 제목이 처음 나오는 쪽 번호 → {"0": 3, "3-2": 7, ...}"""
    n = int(re.search(r"Pages:\s+(\d+)", subprocess.run(["pdfinfo", pdf], capture_output=True, text=True).stdout).group(1))
    pages = {}
    for i in range(1, n + 1):
        t = subprocess.run(["pdftotext", "-f", str(i), "-l", str(i), pdf, "-"], capture_output=True, text=True).stdout
        for m in re.finditer(r"^단계 ([0-9]+(?:-[0-9]+)?)\.", t, re.M):
            pages.setdefault(m.group(1), i)
    return pages


def guide_commands(md):
    """안내서 md 에서 입력할 명령: ```run 상자 안의 줄 + 문장·표 속 `$ 명령`"""
    s = open(md, encoding="utf-8").read()
    cmds = set()
    for body in re.findall(r"```run[^\n]*\n(.*?)\n```", s, re.S):
        cmds.update(x.strip() for x in body.split("\n") if x.strip())
    cmds.update(x.strip() for x in re.findall(r"`\$ ([^`]+)`", s))
    return cmds


def bundle_files(bundle_text):
    return {k.split("/")[-1] for k in re.findall(r"FILES\['([^']+)'\]", bundle_text)}


def check(card, md, bundle_text, bundle_name):
    """카드 명령이 안내서에 그대로 있는지, 부르는 파일이 번들(또는 번들 자신)인지. 불일치 목록을 돌려줌"""
    gcmds, files = guide_commands(md), bundle_files(bundle_text) | {bundle_name} | {"mapping.txt"}   # mapping.txt 는 setup.py 가 만듦
    bad = []
    for c in card["cmds"]:
        if c not in gcmds:
            bad.append(f"안내서에 없는 명령: {c}")
        for f in re.findall(r"[\w.]+\.(?:py|txt)", c):
            if f not in files:
                bad.append(f"번들에 없는 파일: {f} ({c})")
    return bad


def p(pages, *steps):
    return "·".join(f"{pages[s]}" for s in steps) + "쪽"


def row(n, cmd, see, pg):
    c = f"<code>{html.escape(cmd)}</code>" if cmd else ""
    return (f'<tr><td class="box">□</td><td class="n">{n}</td><td>{c}</td>'
            f'<td class="see">{see}</td><td class="pg">{pg}</td></tr>')


def note_row(text, pg):
    return f'<tr class="note"><td class="box">□</td><td class="n"></td><td colspan="2">{text}</td><td class="pg">{pg}</td></tr>'


def q(s):
    return f"<q>{html.escape(s)}</q>"


Q_WORK, Q_HBI, Q_R, Q_NONE = q("D:\\작업폴더>"), q("…\\hbi>"), q('r"…"'), q("AREA_BBOX = None")
Q_HAS, Q_HASH, Q_DONE, Q_SKIP, Q_SHARP = q("[있음]"), q("#####"), q("완료 → output/"), q("건너뜀"), q("#")

HEAD = ('<table><colgroup><col style="width:4%"><col style="width:4.5%"><col style="width:60%"><col style="width:21.5%"><col style="width:10%">'
        '</colgroup><tr><th></th><th>#</th><th>칠 명령</th><th>화면에서 볼 것</th><th>쪽</th></tr>')


def gold(stuck_page):
    return ('<div class="gold"><b class="t">황금 규칙 3개</b><ol>'
            '<li>명령 치기 전 <b>한/영 키</b>로 영어인지 확인 (한글이면 <q>ㅔㅛ쇄ㅜ</q> 로 쳐짐)</li>'
            '<li>실행 중엔 <b>검은 창 클릭 금지</b> (제목에 <q>선택</q> 이 보이면 Esc)</li>'
            f'<li>막히면 <b>오류 마지막 줄</b>을 적고 안내서 <b>{stuck_page}쪽</b></li></ol></div>')


def folders(parcel_note):
    rows = [("① 수치지형도", ""), ("② DEM 5m", ""), (f"③ 국토정보필지 {parcel_note}", ""), ("④ 작업 폴더 (번들 있는 곳)", "")]
    cells = [f'<td>{a}</td><td class="blank"></td>' for a, _ in rows]
    return ('<h2>담당자에게 물을 것 (폴더 주소 받아 적기)</h2><table><colgroup><col style="width:17%"><col style="width:33%"><col style="width:17%"><col style="width:33%"></colgroup>'
            + "".join(f"<tr>{cells[i]}{cells[i + 1]}</tr>" for i in (0, 2)) + "</table>")


def v5_card(pg):
    cmds = [r"cd /d D:\작업폴더", "python hbi_code_bundle_v5.txt", "cd hbi", "notepad config.py",
            'findstr /b "DATA_ROOT" config.py', 'findstr /b "AREA_BBOX" config.py', "python 01_inspect.py", "python run_all.py",
            "python 12_isochrone.py", "python 13_siting.py", "python 14_dong_context.py"]
    see = ["작업폴더 = ④ 주소", q("완료: 파일 53개"), f"맨 아래 {Q_HBI}",
           f"주소 3줄, 저장 ({Q_R} 의 r 그대로)", "받아 적은 주소인지", f"{q('None')} 한 줄",
           f"shp 0개 아님, {Q_HAS} 3줄, 지목 한글", f"{Q_HASH} 줄이 차례로, 끝에 {Q_DONE}",
           f"끝에 {Q_DONE}…", f"{Q_SKIP} 이 정상", f"끝에 {Q_DONE}…"]
    pgs = [p(pg, "2"), p(pg, "2"), p(pg, "2"), p(pg, "3"), p(pg, "3-2"), p(pg, "3-2"), p(pg, "4"), p(pg, "5", "5-2"),
           p(pg, "6"), p(pg, "6"), p(pg, "6")]
    body = [HEAD] + [row(i + 1, c, s, g) for i, (c, s, g) in enumerate(zip(cmds, see, pgs))]
    body += [note_row("(상호제공데이터를 받았으면) 안내서대로 주소 넣고 run_all 다시", p(pg, "7")),
             note_row("<code>output</code> 폴더 반출 신청 (work 는 반출 안 함), 반출 시각 메모", p(pg, "8")), "</table>"]
    memo = ('<h2>메모 칸 (값은 적지 않음)</h2><table><colgroup><col style="width:17%"><col style="width:33%"><col style="width:17%"><col style="width:33%"></colgroup>'
            '<tr><td>연결망</td><td class="blank">____ 개, 노드 ____ %</td><td>scipy · matplotlib</td><td>있음/없음 · 있음/없음</td></tr>'
            '<tr><td>오류 마지막 줄</td><td class="blank"></td><td>반출 시각</td><td class="blank"></td></tr></table>')
    html_body = ("<h1>1차 방문 카드 · v5 (작업 폴더에 hbi_code_bundle_v5.txt 가 있을 때)</h1>" + gold(pg["9"]) + folders("서울 폴더")
                 + "<h2>명령 (위에서부터 한 줄씩, 끝나면 □ 체크)</h2>" + "".join(body) + memo)
    return {"cmds": cmds, "html": html_body}


BBOX = [("A", "종로구·중구", "AREA_BBOX = [194500, 548300, 203400, 560200]"), ("B", "관악구", "AREA_BBOX = [190100, 536300, 200000, 545000]"),
        ("C", "광진구", "AREA_BBOX = [203900, 546100, 211100, 553700]"), ("D", "강서구", "AREA_BBOX = [178200, 546400, 190500, 557200]")]


def v4_card(pg):
    prep = [r"cd /d D:\작업폴더", "python hbi_code_bundle_v4.txt", "cd hbi", "notepad config.py",
            'findstr /b "DATA_ROOT" config.py', "python 01_inspect.py"]
    prep_see = ["작업폴더 = ④ 주소", q("완료: 파일 43개"), f"맨 아래 {Q_HBI}",
                f"주소 3줄, 저장 ({Q_R} 의 r 그대로)", "받아 적은 주소인지", f"shp 0개 아님, {Q_HAS} 3줄, 지목 한글"]
    prep_pg = [p(pg, "2"), p(pg, "2"), p(pg, "2"), p(pg, "3"), p(pg, "3-2"), p(pg, "4")]
    zone = ["notepad config.py", 'findstr /b "AREA_BBOX" config.py', "python run_all.py", "ren output output_A"]
    zone_see = [f"{Q_SHARP} 없는 AREA_BBOX 줄 → 위 표의 그 구역 줄, 저장", "딱 한 줄, 그 구역 줄과 같음",
                f"끝에 {Q_DONE}, 비율 2개 메모", "B·C·D 는 output_B·C·D"]
    zone_pg = [p(pg, "5", "6"), p(pg, "5", "6"), p(pg, "5", "5-2"), p(pg, "5-2")]
    end = ["notepad config.py", 'findstr /b "AREA_BBOX" config.py']
    end_see = [f"{Q_NONE} 로 되돌리고 저장", f"{Q_NONE} 한 줄"]
    k = 0
    out = ["<h2>준비 (한 번)</h2>", HEAD]
    for c, s, g in zip(prep, prep_see, prep_pg):
        k += 1; out.append(row(k, c, s, g))
    out.append("</table>")
    out.append('<h2>구역 표 (메모장에 넣을 줄)</h2><table><colgroup><col style="width:9%"><col style="width:19%"><col style="width:72%"></colgroup>'
               + "".join(f'<tr><td class="box">{z}□</td><td>{d}</td><td class="bbox"><code>{html.escape(b)}</code></td></tr>' for z, d, b in BBOX) + "</table>")
    out.append('<h2 style="break-before: page">구역마다 반복: A → B → C → D (□ 네 칸 = 구역 A·B·C·D)</h2>' + HEAD.replace("<th></th>", "<th>×4</th>"))
    for c, s, g in zip(zone, zone_see, zone_pg):
        k += 1
        out.append(row(k, c, s, g).replace('<td class="box">□</td>', '<td class="box" style="font-size:12pt">□□□□</td>'))
    out.append("</table><h2>마무리</h2>" + HEAD)
    for c, s, g in zip(end, end_see, [p(pg, "7"), p(pg, "7")]):
        k += 1; out.append(row(k, c, s, g))
    out.append(note_row("<code>output_A</code> ~ <code>output_D</code> 반출 신청 (work·_실패 폴더는 반출 안 함), 반출 시각 메모", p(pg, "7")) + "</table>")
    memo = ('<h2>메모 칸 (값은 적지 않음)</h2><table><colgroup><col style="width:10%"><col style="width:26%"><col style="width:26%"><col style="width:38%"></colgroup>'
            '<tr><th>구역</th><th>최대 연결망 노드 비율</th><th>경계 500m 이내 (x%)</th><th>×일 때 오류 마지막 줄</th></tr>'
            + "".join(f'<tr><td class="n">{z}</td><td class="blank"></td><td></td><td></td></tr>' for z in "ABCD")
            + '<tr><td colspan="2">scipy · matplotlib</td><td colspan="2">있음 / 없음 · 있음 / 없음</td></tr>'
            '<tr><td colspan="2">반출 시각</td><td colspan="2" class="blank"></td></tr></table>')
    html_body = ("<h1>1차 방문 카드 · v4 (작업 폴더에 v5 번들이 없을 때)</h1>" + gold(pg["8"]) + folders("폴더 (없으면 생략)") + "".join(out) + memo)
    return {"cmds": prep + zone + end + ["ren output output_B"], "html": html_body}


MODES_TIME = "⟪○○분⟫"      # 두 방식(--modes auto,all) 걸린 시간: 화요일 runlog 의 03 이후 소요로 채움


def v6_card(pg):
    prep = [r"cd /d C:\Users\user\Desktop\박수범", "python hbi_code_bundle_v6.txt", "cd hbi6"]
    prep_see = ["<b>박</b> 까지 치고 Tab", q("완료: 파일 46개"), f"맨 아래 {q('…' + chr(92) + 'hbi6>')}"]
    main = ["python setup.py", "python check.py", "python run_all.py --modes auto,all"]
    main_see = ["질문은 모두 <b>Enter</b> (기본 폴더)", f"끝에 {q('통과')} (멈춤 → 7)", f"두 방식 {MODES_TIME}, 끝에 빨강 없음"]
    fix = ["notepad mapping.txt", "python run_all.py --from 06", "chcp 65001"]
    fix_see = [f"{q('→')} 안내대로, = 오른쪽만", "06 자리에 멈춘 번호 (방식은 기억함)", "화면 한글이 깨지면 치고 같은 명령 다시"]
    more = ["python run_all.py --from 09", "python 12_isochrone.py", "python 13_siting.py", "python 14_dong_context.py"]
    sec = lambda t: f'<tr class="sec"><td colspan="5">{t}</td></tr>'
    head6 = HEAD.replace('<col style="width:60%"><col style="width:21.5%">', '<col style="width:55%"><col style="width:26.5%">')
    k, out = 0, ["<h2>명령 (위에서부터 한 줄씩, 끝나면 □)</h2>", head6, sec("준비 (한 번)")]
    def add(c, s_, g):
        nonlocal k
        k += 1
        if len(c) > 30:      # 긴 명령은 "볼 것" 칸까지 써서 한 줄에 (볼 것은 명령 뒤에 작게)
            out.append(f'<tr><td class="box">□</td><td class="n">{k}</td><td colspan="2"><code>{html.escape(c)}</code> '
                       f'<span class="see">{s_}</span></td><td class="pg">{g}</td></tr>')
        else:
            out.append(row(k, c, s_, g))
    for c, s_, g in zip(prep, prep_see, [p(pg, "2")] * 3):
        add(c, s_, g)
    out.append(sec("명령 세 줄 (이것이 전부)"))
    for c, s_, g in zip(main, main_see, [p(pg, "3", "3-2"), p(pg, "4"), p(pg, "5", "5-2")]):
        add(c, s_, g)
    out.append(sec("멈췄을 때"))
    for c, s_, g in zip(fix, fix_see, [p(pg, "4-2"), p(pg, "6"), p(pg, "9")]):
        add(c, s_, g)
    out.append(sec("실측 좌표를 넣은 뒤 (안내서대로 interventions.csv)"))
    add(more[0], "09 시설 효과", p(pg, "7"))
    k += 1
    out.append(f'<tr><td class="box">□</td><td class="n">{k}</td><td>' + "<br>".join(f"<code>{html.escape(c)}</code>" for c in more[1:])
               + f'</td><td class="see">한 줄씩. 13 은 좌표 없는 시설 건너뜀</td><td class="pg">{p(pg, "7")}</td></tr>')
    out.append(note_row("<code>output</code> 폴더 반출 신청 (work 는 반출 안 함), 반출 시각 메모", p(pg, "8")) + "</table>")
    folders6 = ('<h2>담당자에게 물을 것</h2><table><colgroup><col style="width:24%"><col style="width:26%"><col style="width:24%"><col style="width:26%"></colgroup>'
                '<tr><td>박수범 폴더에 자료·번들</td><td>○ / ×</td><td>대장·GIS 건물 파일</td><td>○ / ×</td></tr></table>')
    memo = ('<h2>메모 칸 (값은 적지 않음)</h2><table><colgroup><col style="width:17%"><col style="width:33%"><col style="width:17%"><col style="width:33%"></colgroup>'
            '<tr><td>고른 방식·연결률</td><td class="blank">______ ____ %</td><td>연결망·노드</td><td class="blank">____ 개, ____ %</td></tr>'
            '<tr><td>오류 마지막 줄</td><td class="blank"></td><td>시간·반출</td><td class="blank">__:__ → __:__, 반출 __:__</td></tr></table>')
    html_body = ("<h1>2차 방문 카드 · v6 (hbi_code_bundle_v6.txt)</h1>" + gold(pg["9"]) + folders6 + "".join(out) + memo)
    return {"cmds": prep + main + fix + more, "html": html_body}


def render(body, out):
    doc = f'<!doctype html><html lang="ko"><head><meta charset="utf-8"><title>1차 방문 카드</title><style>{CSS}</style></head><body>{body}</body></html>'
    with tempfile.TemporaryDirectory() as td:
        hp = os.path.join(td, "card.html")
        open(hp, "w", encoding="utf-8").write(doc)
        subprocess.run([CHROME, "--headless", "--disable-gpu", "--no-pdf-header-footer", f"--print-to-pdf={out}", "file://" + hp],
                       check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return len(re.findall(rb"/Type\s*/Page[^s]", open(out, "rb").read()))


def main():
    v4_bundle = open(os.path.join(ROOT, "deliverables", "hbi_code_bundle_v4.txt"), encoding="utf-8").read()
    v5_bundle = subprocess.run(["git", "-C", ROOT, "show", "v5-submitted:deliverables/hbi_code_bundle_v5.txt"],
                               capture_output=True, text=True, check=True).stdout
    jobs = [("v5", v5_card, "1차방문_v5_따라하기", v5_bundle, "hbi_code_bundle_v5.txt"),
            ("v4", v4_card, "1차방문_안내서", v4_bundle, "hbi_code_bundle_v4.txt")]
    # [v6] 2차 방문 카드: 번들이 아직 없으면 analysis/hbi 파일 목록으로 대조 (번들에 들어갈 파일과 같음)
    v6b = os.path.join(ROOT, "deliverables", "hbi_code_bundle_v6.txt")
    v6_bundle = open(v6b, encoding="utf-8").read() if os.path.exists(v6b) else "".join(
        f"FILES['hbi/{os.path.relpath(os.path.join(d, f), os.path.join(ROOT, 'analysis', 'hbi'))}']"
        for d, _, fs in os.walk(os.path.join(ROOT, "analysis", "hbi")) for f in fs if f.endswith((".py", ".txt", ".md", ".csv")))
    if os.path.exists(os.path.join(DOCS, "2차방문_v6_안내서.pdf")):
        jobs.append(("v6", v6_card, "2차방문_v6_안내서", v6_bundle, "hbi_code_bundle_v6.txt"))
    fail = False
    for tag, make, guide, bundle, bname in jobs:
        card = make(guide_pages(os.path.join(DOCS, guide + ".pdf")))
        bad = check(card, os.path.join(DOCS, guide + ".md"), bundle, bname)
        print(f"{tag} 카드 명령 {len(card['cmds'])}개 대조: 불일치 {len(bad)}")
        for b in bad:
            print("  ", b)
        if bad:
            fail = True; continue
        out = os.path.join(DOCS, f"{'2차방문' if tag == 'v6' else '1차방문'}_{tag}_카드.pdf")
        print(f"→ {os.path.relpath(out, ROOT)} ({render(card['html'], out)}쪽)")
    if fail:
        sys.exit(1)


if __name__ == "__main__":
    main()
