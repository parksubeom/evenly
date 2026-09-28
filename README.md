# evenly

**어디에 살든, 7분은 7분이어야 하니까.**

평지 기준 지도에서는 "가깝다"고 나오지만, 언덕과 계단 때문에 어르신과 휠체어 이용자에게는
몇 배 먼 동네가 있습니다. evenly는 집집마다 "가까운 병원·정류장·역까지 왕복하는 데 경사 때문에
평지보다 몇 배가 걸리는지"를 계산해, 거리만 보는 지도에 숨은 사각지대를 드러냅니다.
이 배수를 **언덕 부담 지수(HBI, Hill Burden Index)** 라고 부릅니다.

| | |
|---|---|
| 서비스명 | evenly (이븐리) |
| 이름의 뜻 | even = **평평한** + **공평한**. 기울어진 길의 부담을 공평하게 |
| 공모전 참가주제명 | 언덕 위 우리동네: 경사 반영 이동약자 접근성 지도 |
| 대회 | 2026 데이터+AI 혁신 챌린지: 데이터안심구역 경진대회 (참가센터: 한국국토정보공사 서울) |
| 핵심 지표 | 언덕 부담 지수 (HBI) = 경사 반영 왕복 시간 ÷ 평지 가정 왕복 시간 |

---

## 폴더 구조

```
evenly/
├─ analysis/              안심구역에서 돌릴 분석 코드 (원본 소스)
│  ├─ hbi/                기본 버전: QGIS 내장 Python (numpy + GDAL)  ← 실제로 쓰는 것
│  └─ hbi_geopandas/      대체 버전: geopandas 환경용 (v2 기능까지만)
├─ tools/
│  └─ build_bundle.py     analysis/ → 반입용 txt 번들 만들기
├─ deliverables/          제출·반입용 완성 파일 (기획서 pptx, 코드 번들 txt)
├─ results/
│  └─ raw_export/         안심구역에서 반출 승인받은 파일을 그대로 넣는 곳 (git 제외)
├─ deck/                  기획서 PPT 생성기 (Node + pptxgenjs)
├─ demo/                  본선 데모 화면 (미리보기 html + 생성 스크립트)
└─ docs/                  신청서 문안, 일정·체크리스트, 예상 질의응답, 결정 기록, 출처, 데이터정의서
```

## 환경 준비

| 용도 | 필요한 것 | 확인 |
|---|---|---|
| 분석 코드 연습 | QGIS 3.x (맥: `/Applications/QGIS.app/Contents/MacOS/bin/python3`) | `python3 -c "from osgeo import gdal"` |
| 번들 만들기 | 일반 Python 3 | `python3 --version` |
| 기획서 만들기 | Node 18+ , `npm i pptxgenjs` (deck 폴더에서) | `node -v` |
| 데모 화면 | 브라우저만 있으면 됨 (html 더블클릭) | |

## 자주 하는 작업

### A. 분석 코드를 고쳤을 때 → 새 번들 만들기
```
# analysis/hbi 안의 파일 수정 후, 연습 데이터로 확인
cd analysis/hbi
python3 tools/make_test_data.py
# config.py 경로를 testdata 로 바꾸고
python3 run_all.py --sens
# (확인 끝나면 config.py 경로 원복!)
cd ../..
python3 tools/build_bundle.py v5          # → deliverables/hbi_code_bundle_v5.txt
```
반입자료를 바꾸면 심의가 다시 필요할 수 있으니, 교체 전에 센터에 먼저 확인합니다.

### B. 반출 결과를 받았을 때 → 기획서 채우기
1. 반출 승인된 파일을 전부 `results/raw_export/` 에 넣기 (파일명 그대로)
2. `docs/02_일정_체크리스트.md` 의 "반출 파일 체크리스트"로 빠진 파일 확인
3. 고령인구 추정: `python3 analysis/hbi/tools/outside_elderly.py results/raw_export/dong_hbi.csv 인구파일.csv`
4. 기획서 빈칸(`___`) 채우기 → `deck/` 생성기 실행 → `deliverables/` 에 새 pptx

### C. 본선 데모 갱신
`demo/page_template.html` 에 실제 `grid_hbi.csv` 를 넣어 다시 생성 (현재 `hbi_preview.html` 은 공개 지형으로 만든 미리보기)

## 이름 규칙
- 서비스·레포 이름은 **evenly** (문서에서는 소문자 그대로, 한글 표기는 "이븐리"), 지표 이름은 **HBI**
- `analysis/hbi/` 와 반입 번들 파일명(`hbi_code_bundle_*.txt`)은 이미 안심구역 심의를 받은 이름이라 **바꾸지 않습니다**
- 공모전 제출물(기획서 표지·참가신청서)의 참가주제명은 "언덕 위 우리동네"를 유지하고, 서비스명 "evenly"는 활용방안·확산 장표와 마지막 장에서 소개합니다

## 꼭 지킬 것

- **미개방 원자료(수치지형도, DEM, 필지)는 절대 이 레포에 넣지 않습니다.** 안심구역 밖으로 나올 수도 없습니다.
- 안심구역의 `work/` 폴더(건물 단위 결과)도 반출하지 않습니다. `output/` 중 반출 승인받은 것만 `results/raw_export/` 에.
- 반출 결과도 집계 자료이지만 대회 데이터에서 나온 것이므로, 레포는 **비공개(private)** 로 유지합니다.
