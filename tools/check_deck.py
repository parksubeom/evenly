# -*- coding: utf-8 -*-
"""
tools/check_deck.py ─ 만든 기획서에 남은 빈칸과 deck/data/missing.txt 를 1:1 로 맞춰 보기

[실행] python3 tools/check_deck.py deliverables/_test_기획서.pptx [--missing deck/data/missing.txt]
[짝짓는 법]
  build_deck.js 는 빈칸(___ / ○○○ / 주황 점선 박스)이 들어간 글상자·표·도형의 이름(objectName)을
  "BLANK:<장>:<key>|<key>..." 로 붙이고, missing.txt 각 줄 끝에 [key] 를 적습니다.
  pptx 쪽:  빈칸 표시가 있는 개체를 전부 찾고(이름과 무관하게 글자·채우기색으로), 그 이름에서 (장, key) 를 읽음
  N = pptx 에서 찾은 빈칸 항목 (장, key) 수      M = missing.txt 항목 수      K = 둘 다에 있는 항목 수
  통과 조건: N = M = K, 그리고 이름표 없는 빈칸 개체 0개
"""
import argparse, os, re, sys, zipfile
from html import unescape

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BLANK_RE = re.compile(r"_{3,}|○○○")
OBJ_RE = re.compile(r"<p:(sp|graphicFrame)>.*?</p:\1>", re.S)


def scan(path):
    z = zipfile.ZipFile(path)
    slides = sorted((n for n in z.namelist() if re.fullmatch(r"ppt/slides/slide\d+\.xml", n)), key=lambda n: int(re.findall(r"\d+", n)[0]))
    found, untagged, tokens, objs, wm, mism = set(), [], 0, 0, 0, []
    for n in slides:
        no = int(re.findall(r"\d+", n)[0])
        x = z.read(n).decode("utf-8")
        if "테스트 데이터 — 제출 금지" in "".join(re.findall(r"<a:t>([^<]*)</a:t>", x)):
            wm += 1
        for m in OBJ_RE.finditer(x):
            o = m.group(0)
            text = unescape(" ".join(re.findall(r"<a:t>([^<]*)</a:t>", o)))
            t = len(BLANK_RE.findall(text))
            is_ph = 'val="FFF7F2"' in o
            if not (t or is_ph):
                continue
            tokens += t
            objs += 1
            name = unescape((re.search(r'<p:cNvPr [^>]*name="([^"]*)"', o) or [None, ""])[1])
            mm = re.match(r"BLANK:(\d+):(.+)", name)
            if not mm:
                untagged.append((no, name, text[:30]))
                continue
            keys = mm.group(2).split("|")
            for k in keys:
                found.add((int(mm.group(1)), k))
            # 글자 빈칸 수 = 글자로 채워지는 key 수 (그림·표 통째·방문일 박스처럼 개체 전체가 한 항목인 key 는 제외)
            textual = [k for k in keys if not k.startswith(("img:", "tbl:", "SAFE.day"))]
            whole_tbl = any(k.startswith("tbl:") for k in keys)
            if re.findall(r"<a:t>", o) and not whole_tbl and t != len(textual):
                mism.append((no, name, t, len(textual)))
    return len(slides), found, untagged, tokens, objs, wm, mism


def read_missing(path):
    out = set()
    if os.path.exists(path):
        for line in open(path, encoding="utf-8"):
            m = re.match(r"누락: (\d+)장, .*\[([^\]]+)\]\s*$", line)
            if m:
                out.add((int(m.group(1)), m.group(2)))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("pptx", nargs="?", default=os.path.join(ROOT, "deliverables", "_test_기획서.pptx"))
    ap.add_argument("--missing", default=os.path.join(ROOT, "deck", "data", "missing.txt"))
    a = ap.parse_args()
    ns, found, untagged, tokens, objs, wm, mism = scan(a.pptx)
    miss = read_missing(a.missing)
    K = found & miss
    print(f"{os.path.relpath(a.pptx, ROOT)}: {ns}장, 워터마크 {wm}장")
    print(f"  pptx 빈칸 표시: 개체 {objs}개, 밑줄·○○○ {tokens}곳 (0 이면 '빈칸이 없어서 0' — 스캔은 글자와 점선 박스 채우기색을 직접 봄)")
    print(f"  N(pptx 빈칸 항목) = {len(found)}, M(missing.txt 항목) = {len(miss)}, K(짝지어진 항목) = {len(K)}, 이름표 없는 빈칸 개체 = {len(untagged)}, 빈칸 수≠key 수 개체 = {len(mism)}")
    for no, k in sorted(found - miss):
        print(f"  !! pptx {no}장 빈칸 [{k}] 가 missing.txt 에 없음")
    for no, k in sorted(miss - found):
        print(f"  !! missing.txt {no}장 [{k}] 에 해당하는 빈칸이 pptx 에 없음")
    for no, nm, t in untagged:
        print(f"  !! {no}장 이름표 없는 빈칸 개체 (name={nm!r}, 글자='{t}')")
    for no, nm, t, k in mism:
        print(f"  !! {no}장 개체 {nm!r}: 글자 빈칸 {t}곳 ≠ 이름표 key {k}개")
    ok = len(found) == len(miss) == len(K) and not untagged and not mism and ns <= 30
    if ns > 30:
        print("  !! 30장 초과")
    print("결과:", "통과" if ok else "실패")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
