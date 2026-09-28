# 기획서 생성기

```
cd deck
npm install          # 처음 한 번
npm run build        # → ../deliverables/언덕위우리동네_기획서_v2.pptx
```
- `build_deck.js` : 슬라이드 28장 전체. 결과 자리는 `___` 와 주황 점선 박스(ph 함수)로 표시돼 있음
- `img/` : 등고선 배경, 고도 단면, 예시 지도 등 이미지 (`make_images.py` 로 다시 만들 수 있음, matplotlib 필요)
- 반출 결과가 들어오면 `___` 자리를 실제 값으로 바꾸는 작업을 여기서 합니다
