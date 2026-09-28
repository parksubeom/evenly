# -*- coding: utf-8 -*-
"""
tools/check_deck.py ─ 만든 기획서에 남은 빈칸이 deck/data/missing.txt 에 적힌 곳뿐인지 확인

[실행] python3 tools/check_deck.py deliverables/_test_기획서.pptx
[보는 것]
  - 슬라이드 글자 중 ___ (밑줄 빈칸), ○○○ (팀명 자리)
  - 주황 점선 박스(ph: 채우기 FFF7F2)
  - 워터마크 "테스트 데이터 — 제출 금지" 가 몇 장에 있는지 (가짜면 전 장, 실제면 0장이어야 함)
  - 30장 이내인지
빈칸이 있는데 missing.txt 에 그 슬라이드가 없으면 실패(종료코드 1).
"""
import os, re, sys, zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def main():
    path = sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, "deliverables", "_test_기획서.pptx")
    miss_path = os.path.join(ROOT, "deck", "data", "missing.txt")
    z = zipfile.ZipFile(path)
    slides = sorted((n for n in z.namelist() if re.fullmatch(r"ppt/slides/slide\d+\.xml", n)), key=lambda n: int(re.findall(r"\d+", n)[0]))
    miss_pages = set()
    if os.path.exists(miss_path):
        for line in open(miss_path, encoding="utf-8"):
            m = re.match(r"누락: (\d+)장", line)
            if m:
                miss_pages.add(int(m.group(1)))
    blanks, wm = {}, 0
    for n in slides:
        no = int(re.findall(r"\d+", n)[0])
        x = z.read(n).decode("utf-8")
        text = "".join(re.findall(r"<a:t>([^<]*)</a:t>", x))
        found = []
        if "___" in text:
            found.append(f"___ {text.count('___')}곳")
        if "○○○" in text:
            found.append("○○○")
        ph = x.count('val="FFF7F2"')
        if ph:
            found.append(f"점선 박스 {ph}개")
        if found:
            blanks[no] = found
        if "테스트 데이터 — 제출 금지" in text:
            wm += 1
    ok = True
    print(f"{os.path.relpath(path, ROOT)}: {len(slides)}장, 워터마크 {wm}장")
    if len(slides) > 30:
        print("  !! 30장 초과"); ok = False
    for no, f in sorted(blanks.items()):
        flag = "OK (missing.txt 에 있음)" if no in miss_pages else "!! missing.txt 에 없음"
        if no not in miss_pages:
            ok = False
        print(f"  {no}장: {', '.join(f)} → {flag}")
    for no in sorted(miss_pages - set(blanks)):
        print(f"  {no}장: missing.txt 에 있지만 화면상 빈칸 표시 없음 (그림·표 누락 등, 확인 필요)")
    if not blanks:
        print("  남은 빈칸 없음")
    print("결과:", "통과" if ok else "실패")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
