# -*- coding: utf-8 -*-
"""
tools/check_real_text.py ─ [10/20] 제출용 실제판 글자 점검 (check_deck 의 빈칸 대조와 따로)

[실행]  python3 tools/check_real_text.py deliverables/언덕위우리동네_기획서_final.pptx
[보는 것]
  1. 금지 글자 (있으면 실패): "리허설", "청사진", "공개 대역", "제출 금지", "가상" (4장 "가상 인물"·인물 설명만 뺌)
  2. 발표자 노트의 "[청사진 메모]" (있으면 실패)
  3. 대체 문구 (빈칸으로 셈, 있으면 경고): "실측 후", "실제 결과 후", "확보 시", "교체 예정", "반영 예정", "기입 예정", "다녀온 날로 기입", "출처 기입"
     (25장 한계 줄의 "다시 계산 예정"은 계획 문장이라 셈에서 뺌)
[결과] 화면에 장별 목록. 금지 글자·노트가 있으면 종료 코드 1, 대체 문구만 있으면 2, 없으면 0
"""
import re, sys, zipfile

BANNED = ["리허설", "청사진", "공개 대역", "제출 금지", "가상"]
ALLOW = {4: ["가상"]}                                # 4장 "가상 인물"·"인물은 가상" ([10/20] 24장은 숫자가 본문 값이라 "가상" 없음)
LATER = ["실측 후", "실제 결과 후", "확보 시", "교체 예정", "반영 예정", "기입 예정", "다녀온 날로 기입", "출처 기입"]
SKIP_LATER = ["다시 계산 예정"]


def texts(z, name):
    x = z.read(name).decode("utf-8")
    return ["".join(re.findall(r"<a:t>([^<]*)</a:t>", p)) for p in re.findall(r"<a:p>.*?</a:p>", x, flags=re.S)]


def main():
    p = sys.argv[1]
    z = zipfile.ZipFile(p)
    slides = sorted((n for n in z.namelist() if re.fullmatch(r"ppt/slides/slide\d+\.xml", n)), key=lambda n: int(re.findall(r"\d+", n)[0]))
    bad, later = [], []
    for n in slides:
        no = int(re.findall(r"\d+", n)[0])
        for t in texts(z, n):
            for w in BANNED:
                if w in t and w not in ALLOW.get(no, []):
                    bad.append((no, w, t[:70]))
            tt = t
            for sk in SKIP_LATER:
                tt = tt.replace(sk, "")
            for w in LATER:
                if w in tt:
                    later.append((no, w, t[:70]))
    notes = [n for n in z.namelist() if re.fullmatch(r"ppt/notesSlides/notesSlide\d+\.xml", n)]
    bpn = [n for n in notes if "[청사진 메모]" in z.read(n).decode("utf-8")]
    print(f"{p}: 장 {len(slides)} · 금지 글자 {len(bad)}곳 · 노트 [청사진 메모] {len(bpn)}장 · 대체 문구 {len(later)}곳")
    for no, w, t in bad:
        print(f"  !! {no}장 금지 '{w}': {t}")
    for n in bpn:
        print(f"  !! 노트 [청사진 메모]: {n}")
    for no, w, t in later:
        print(f"  대체 {no}장 '{w}': {t}")
    sys.exit(1 if (bad or bpn) else (2 if later else 0))


if __name__ == "__main__":
    main()
