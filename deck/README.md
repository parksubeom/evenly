# 기획서 생성기

**[10/12] 기준본은 v6 (편집형 30장)**: `build_v6.js` (디자인 원본 `v6_source/build6.js`, 결과 칸만 결과 키로). 결과 키 표는 `docs/기획서_v6_결과키.md`

```
cd deck
npm install                  # 처음 한 번 (pptxgenjs)
npm run build:fake           # 가상 수치 → ../deliverables/_test_기획서_v6.pptx (오른쪽 위 "가상 수치 · 검토용")
npm run build:rehearsal      # 공개 대역, 혼합 기준 → _rehearsal_기획서_v6.pptx ("공개 대역 · 제출 금지")
npm run build:rehearsal:ab   # 비교용 A(HBI 1.3·1.8)·B(왕복 추가 5·10분) → _rehearsal_기획서_v6_A·B.pptx
npm run build:real           # 실제 반출 결과 → ../deliverables/언덕위우리동네_기획서_final.pptx (가짜·공개 대역이면 멈춤)
npm run build:real:later     # 위와 같고, 관악 실측·상호제공 칸만 ___ 대신 '실측 후'·'상호제공데이터 확보 시' (--later-ok)
npm run real-day -- <받은 반출 zip 또는 폴더>   # [10/22] 놓기 → 점검 → 밖 도구 → build:real → check_deck → 렌더링 → PDF → 판정 줄 (tools/real_day.py)
npm run build:fallback       # 대비책 판: 1차 반출(10/2) 숫자만 → ../deliverables/언덕위우리동네_기획서_대비책.pptx (deck/first_visit_results.json)
npm run fallback-pdf         # 대비책 판 + check_deck + 렌더링 → ../deliverables/언덕위우리동네_기획서_대비책.pdf
python3 ../tools/check_deck.py ../deliverables/_rehearsal_기획서_v6.pptx --missing data/missing_v6.txt
python3 ../tools/render_deck.py ../deliverables/_rehearsal_기획서_v6.pptx --out ../_render/v6_mix   # 미리보기 PNG
```
- [10/12] 구간 기준은 **혼합**이다. 체감 부담은 HBI 1.3 이상이고, 고립 위험은 왕복이 10분 이상 더 걸리는 경우다. 문턱은 분석 mapping 의 `hbi_band`·`extra_min_bands` 에서 정하고, 결과의 `run_meta.csv` 를 거쳐 기획서로 온다. 기획서 안에 숫자를 따로 적지 않는다.
- [10/13] 15장 사진: `docs/photos/15_1`~`15_4` (.jpg·.png·.heic; 1 봉천 계단 · 2 봉천역 오르막 · 3 도림천 · 4 낙성대). `tools/prep_photos.py`(build:real·fallback·real-day 가 먼저 부름)가 바로 세우고 촬영 정보(GPS 등 EXIF)를 지운 사본 `docs/photos/_deck/15_N.jpg` 만 기획서에 들어감. 없으면 '사진 자리'
- 절차: 10/19 현장 `docs/2차방문_1019_한장.pdf`, 10/22 마감일 `docs/22일_기획서_절차.pdf` (원본 html, Chrome 으로 PDF)
- 예전 29장 생성기 `build_deck.js` 는 쓰지 않음 (`npm run build:v5deck:fake|real` 로만 남김)

## (예전 29장 생성기 설명)

```
cd deck
npm install              # 처음 한 번 (pptxgenjs)
npm run build:fake       # 가짜 결과로 시험 → ../deliverables/_test_기획서.pptx (전 장 워터마크)
npm run build:real       # 실제 반출 결과 → ../deliverables/언덕위우리동네_기획서_final.pptx
```
- 걸리는 시간: `npm run build:fake` 1회 약 2초 (가짜 결과 생성 + 변환 + pptx). 처음 한 번은 matplotlib 글꼴 캐시를 만드느라 10~15초
- 파이썬 쪽 그림(지도·산점도)은 matplotlib 이 필요합니다. npm 스크립트는 `deck/py.js` 로 Python 을 고릅니다:
  (1) 환경변수 `EVENLY_PY` → (2) 이 맥의 QGIS 내장 Python (`/Applications/QGIS*.app/Contents/MacOS/python3.x`, matplotlib 포함) → (3) 시스템 `python3`.
  실행할 때 첫 줄에 `[py.js] 파이썬: QGIS Python (...)` 처럼 어느 것을 썼는지 나옵니다. 시스템 python3 에는 matplotlib 이 없습니다
  - `build:real` : matplotlib 이 없으면 **멈추고 pptx 를 만들지 않습니다** (그림 빠진 제출본 방지)
  - `build:fake*` : 경고만 하고 그림 자리를 주황 점선 박스 + 누락 목록으로 남깁니다
- 흐름: `results/<폴더>` → `tools/prepare_deck_data.py` → `deck/data/results.json` + `deck/img/results/*.png` → `build_deck.js` → pptx
- 값이 없는 칸은 `___` / 주황 점선 박스로 남고 `deck/data/missing.txt` 에 "누락: 슬라이드, 값, 필요한 파일"이 적힙니다
- 팀명·방문일은 반출 파일에 없어서 `deck/inputs.json` 에 직접 적습니다
- 확인: `python3 ../tools/check_deck.py ../deliverables/_test_기획서.pptx` (남은 빈칸이 missing.txt 에 있는 곳뿐인지)
- `npm run build:fake` 는 분석 코드 **v5** 형식(intervention_*, percentile_circle, "(경계 제외)" 지표), `npm run build:fake:v4` 는 v4 형식으로 시험
- `npm run build:fake:partial` : join·parcel·sensitivity 가 없는 경우 시험
- `check_deck.py` 는 빈칸 개체 이름표(BLANK:장:key)와 missing.txt 의 [key] 를 1:1 로 맞춰 N(pptx) = M(missing) = K(짝) 일 때만 통과
- `build_deck.js` : 29장 (본문 25 + 부록 4). `img/` 의 기본 이미지는 `make_images.py` 로 다시 만들 수 있음
- `results/public_baseline/compare_*.csv` 는 `lx_grid 출처` 가 real 인 것만 실제 빌드에 들어갑니다 (가짜 결과와 비교한 파일이면 build:real 이 멈춤)
- 고령인구는 레포 최상위 `tools/outside_elderly.py` 결과(`dong_hbi_with_elderly.csv`)를 읽습니다
