# 기획서 생성기

```
cd deck
npm install              # 처음 한 번 (pptxgenjs)
npm run build:fake       # 가짜 결과로 시험 → ../deliverables/_test_기획서.pptx (전 장 워터마크)
npm run build:real       # 실제 반출 결과 → ../deliverables/언덕위우리동네_기획서_final.pptx
```
- 파이썬 쪽 그림(지도·산점도)은 matplotlib 이 필요합니다: `python3 -m pip install --user matplotlib`
  (없어도 빌드는 되고, 그림 자리가 주황 점선 박스로 남고 누락 목록에 적힙니다)
- 흐름: `results/<폴더>` → `tools/prepare_deck_data.py` → `deck/data/results.json` + `deck/img/results/*.png` → `build_deck.js` → pptx
- 값이 없는 칸은 `___` / 주황 점선 박스로 남고 `deck/data/missing.txt` 에 "누락: 슬라이드, 값, 필요한 파일"이 적힙니다
- 팀명·방문일은 반출 파일에 없어서 `deck/inputs.json` 에 직접 적습니다
- 확인: `python3 ../tools/check_deck.py ../deliverables/_test_기획서.pptx` (남은 빈칸이 missing.txt 에 있는 곳뿐인지)
- `npm run build:fake` 는 분석 코드 **v5** 형식(intervention_*, percentile_circle, "(경계 제외)" 지표), `npm run build:fake:v4` 는 v4 형식으로 시험
- `npm run build:fake:partial` : join·parcel·sensitivity 가 없는 경우 시험
- `check_deck.py` 는 빈칸 개체 이름표(BLANK:장:key)와 missing.txt 의 [key] 를 1:1 로 맞춰 N(pptx) = M(missing) = K(짝) 일 때만 통과
- `build_deck.js` : 29장 (본문 25 + 부록 4). `img/` 의 기본 이미지는 `make_images.py` 로 다시 만들 수 있음
