# 언덕 위 우리동네 – 분석 코드 따라하기 안내서 (v6)

> **이 문서만 보고 따라 하면 됩니다.** 파이썬을 처음 써도 괜찮습니다.
> 각 코드 파일 맨 위에도 "이 파일이 뭘 하는지, 결과를 어떻게 보는지"가 적혀 있습니다.

---

## v6 먼저 읽기: 명령 세 줄

v6 는 **자료가 어떻게 생겼든 코드를 고치지 않고** 맞추도록 만든 판입니다 (계산 방법은 v5 와 같음).

```
python setup.py E:\제공자료      ← 자료 최상위 폴더 (앞글자 + Tab). 질문에는 Enter 만 눌러도 추천값
python check.py                  ← 출발 전 점검. "통과" 가 나오면 다음 줄, "!! 멈춤" 이면 → 안내대로 mapping.txt 고치기
python run_all.py                ← 분석. 멈추면 고친 뒤 python run_all.py --from 03 처럼 멈춘 번호부터
```

| 새 파일 | 하는 일 |
|---|---|
| `setup.py` | 하위 폴더를 훑어 수치지형도·DEM·필지·상호제공 CSV 를 찾음, zip 풀기 제안, 대상 구와 겹치는 폴더만 고름(map_folders), AREA_BBOX 자동 결정, 칸 이름 맞추기 → `mapping.txt` 저장, `config.py` 경로 줄 채움(원본 `config.py.bak`) |
| `check.py` | 경로·레이어·칸·인코딩·좌표계·대상 구 범위·DEM 범위·주거 비율·길 연결·목적지 수 점검 → `output/check_report.txt` |
| `mapping.txt` | `키 = 값  # 설명`. 칸 이름(대소문자 무시)·레이어 파일 이름 글자·읽을 폴더·대상 구·건물 용도 방식. `?` 는 못 찾음 |
| `lib/mapping.py` `lib/area.py` `lib/battr.py` `lib/conout.py` `lib/schema.py` | mapping 읽기 / 구 경계·범위 / 건물 용도·층수 / 한글 출력·화면+파일 기록 / 자료 구조 기록 |

- **건물 용도 방식** (`building_attr_mode`): `layer` 건물 레이어 칸(v5 와 같음) / `register` 건물 → 필지 → 건축물대장(`external/building_register.csv`, 번들과 따로 반입) / `all` 모든 건물을 집(용도 미구분) / `stop`
- **대상 구** (`target_gu`): 출발점(집)은 대상 구 안 건물만. 옆 구(`neighbor_gu`)는 길·목적지로만 씀. 비우면 v5 와 같이 자료 전체
- `run_all.py` 는 화면 글자를 `output/runlog/` 에, 자료 구조를 `output/schema/schema.txt` 에 함께 저장하고, 멈추면 원인·할 일을 보여 줌 (`output/diagnose.txt`)
- `output/run_meta.csv`: 대상 구, 건물 용도 방식, 건축물대장 연결률, AREA_BBOX 와 이유

아래 v5 설명(단계별 파일)은 그대로 유효합니다.

## 0. 전체 그림 (5분 읽기)

**무엇을 계산하나**
집집마다 "가까운 병원·정류장까지 왕복하는 데, 경사 때문에 평지보다 몇 배 오래 걸리나"를 계산합니다.
이 배수가 **언덕 부담 지수(HBI)** 입니다. 1.0이면 평지와 같고, 1.8 이상이면 고립 위험입니다.

**순서** (각 단계는 파일 하나, 앞 단계의 결과를 다음 단계가 읽습니다)

| 단계 | 파일 | 하는 일 | 걸리는 시간(예상) |
|---|---|---|---|
| 1 | `01_inspect.py` | 데이터 구조 확인 (파일 이름·좌표계·속성) | 1분 |
| 2 | `02_network.py` | 길 네트워크 만들기 + 경사 계산 | 5~30분 |
| 3 | `03_hbi.py` | 집마다 HBI 계산 | 5~30분 |
| 4 | `04_validate.py` | 검증·기여도 분석 | 5분 |
| 5 | `05_export.py` | 반출용 결과 만들기 | 5분 |
| 6 | `06_parcel.py` | 국토정보필지에 결과 붙이기 (방문 때 센터가 제공) | 10분 |
| 7 | `07_join_dong.py` | KCB 소득 등 행정동 코드가 있는 표를 행정동과 결합·상관분석 (구분자 `,`·`|`·탭 자동, config.JOIN_DATA) | 2분 |
| 8 | `08_sensitivity.py` | 민감도 분석: 설정을 바꿔도 결론이 유지되나 (질의응답 대비) | 10~30분 |
| 9 | `09_intervention.py` | [v5] 이동편의시설(엘리베이터·모노레일) 설치 효과: 몇 집이 몇 분 덜 걷나 (external/interventions.csv) | 시설당 1~5분 |
| 10 | `10_points_join.py` | [v5] 좌표가 있는 점 자료를 행정동·격자로 세거나(개수) 값을 더해(SKT 유동인구 `agg: "sum"`) HBI 와 비교 (config.POINT_DATA) | 2분 |
| 11 | `11_legal_dong_join.py` | [v5] 좌표 없이 법정동 이름만 있는 자료(한국도로교통공단 교통사고)를 법정동별로 세어 06 필지 HBI 와 비교 (config.LEGAL_DONG_DATA, 06 먼저) | 1분 |
| 12 | `12_isochrone.py` | [v5] 시설 주변 몇 분 안에 걸어서 올 수 있는 범위(등시선)를 평지·고령자·휠체어로 비교 (external/iso_points.csv) | 점당 1분 안팎 |
| 13 | `13_siting.py` | [v5] 시설 a–b 선분 둘레 30m 안 필지의 지목별 면적 비율 (도로·공원·대·임야·학교·하천구거·기타). 지목만 읽음 (external/interventions.csv + DATA_ROOT_PARCEL) | 1분 |
| 14 | `14_dong_context.py` | [v5] 행정동별 동네 성격 변수: 건물 용도별 수·연면적 비율, 평균 층수, 역·정류장 수, 보행 링크 밀도, (SKT 가 있으면) 주거 칸 한정 유동인구 합 | 2분 |

**12·13·14 는 run_all 뒤에 한 줄씩 따로 실행**합니다 (run_all 은 바꾸지 않음): `python 12_isochrone.py`, `python 13_siting.py`, `python 14_dong_context.py`. 셋 다 앞 단계 결과를 읽기만 하고 바꾸지 않습니다 (14 는 10 결과와 SKT 합계를 대조).

**폴더 구조**
```
hbi/
├─ config.py          ← 설정 파일. 여기만 고칩니다 (데이터 경로 등)
├─ 01_inspect.py ~ 06_parcel.py   ← 단계별 실행 파일
├─ run_all.py         ← 01~05 한 번에 실행
├─ lib/               ← 계산 부품들 (고칠 필요 없음)
├─ external/          ← 공개데이터 (선정지 좌표, 행정동 경계, 약국 등)
├─ work/              ← 중간 결과 (반출 금지: 건물 단위 결과)
├─ output/            ← 최종 결과 (이 폴더만 반출 신청)
└─ tools/make_test_data.py  ← 연습용 가짜 데이터 만들기
```

**프론트엔드 개발자를 위한 대응표**

| 파이썬 | JS / 프론트엔드 |
|---|---|
| `python 01_inspect.py` | `node index.js` |
| `config.py` | `.env` / `config.js` |
| `import config as C` → `C.GRID` | `import C from './config'` → `C.GRID` |
| `None`, `True`, `False` | `null`, `true`, `false` |
| `# 주석` | `// 주석` |
| `f"{x}개"` | `` `${x}개` `` |
| `r"C:\data"` | 역슬래시를 그대로 쓰는 문자열 (윈도우 경로는 꼭 `r` 붙이기) |
| 들여쓰기(스페이스 4칸)로 블록 구분 | `{ }` 로 블록 구분 → **들여쓰기를 함부로 바꾸면 오류** |

---

## 1. 실행 창 여는 법 (안심구역 Windows PC)

안심구역에는 일반 Python 대신 **QGIS 안에 들어 있는 Python**을 씁니다. 방법은 두 가지입니다.

### 방법 A. OSGeo4W Shell (권장)
1. 윈도우 시작 버튼 → "OSGeo4W Shell" 검색 → 실행 (검은 명령창이 뜸)
2. 이 폴더로 이동: `cd /d D:\작업폴더\hbi`  (`/d` 는 드라이브가 바뀔 때 필요)
3. 확인: `python --version` 이 3.x 로 나오면 준비 끝
4. 이후 `python 01_inspect.py` 처럼 실행

> OSGeo4W Shell이 없으면 QGIS 설치 폴더(예: `C:\Program Files\QGIS 3.32.3\`)의 `OSGeo4W.bat` 를 더블클릭해도 같은 창이 뜹니다.

### 방법 B. QGIS Python 콘솔 (A가 안 될 때)
1. QGIS 실행 → 메뉴 **플러그인 → Python 콘솔**
2. 콘솔 아래 입력줄에 다음을 한 줄씩 입력 (경로는 실제 폴더로)
   ```python
   import os, sys; os.chdir(r"D:\작업폴더\hbi"); sys.path.insert(0, os.getcwd())
   exec(open("01_inspect.py", encoding="utf-8").read())
   ```
3. 다음 단계는 파일 이름만 바꿔서 `exec(open("02_network.py", encoding="utf-8").read())`
4. 주의: 콘솔에서는 `run_all.py` 를 쓰지 마세요. `config.py` 를 고친 뒤에는 먼저
   `import importlib, config; importlib.reload(config)` 를 입력하세요 (안 하면 예전 설정으로 돎).

---

## 2. 방문 전 준비 (집에서, 내 PC)

1. 번들 풀기: `hbi_code_bundle_v4.txt` 가 있는 폴더에서 `python hbi_code_bundle_v4.txt`
   → `hbi/` 와 `hbi_geopandas/` 폴더가 생깁니다.
2. 연습용 가짜 데이터 만들기: `cd hbi` → `python tools/make_test_data.py`
3. `config.py` 를 메모장(또는 VS Code)으로 열어 두 줄 수정
   ```python
   DATA_ROOT_MAP = r"testdata/map"
   DATA_ROOT_DEM = r"testdata/dem"
   ```
4. `python run_all.py` → 마지막에 `완료 → output/ (반출 신청 대상)` 이 나오면 성공
5. **연습이 끝나면 3번에서 바꾼 경로를 원래대로 되돌리기**

맥북에서 연습할 때 Python 경로: `/Applications/QGIS.app/Contents/MacOS/bin/python3`
(예: `/Applications/QGIS.app/Contents/MacOS/bin/python3 run_all.py`)

---

## 3. 안심구역 1일차 따라하기

### 3-1. 번들 풀기
안심구역 PC에서 반입된 `hbi_code_bundle_v4.txt` 가 있는 폴더를 열고, 1장의 방법으로 실행 창을 연 뒤
```
python hbi_code_bundle_v4.txt
cd hbi
```

### 3-2. 데이터 경로 넣기 (config.py)
1. 윈도우 탐색기에서 제공받은 **수치지형도 폴더**를 찾아 주소창 클릭 → 경로 복사
2. `config.py` 를 메모장으로 열고 `DATA_ROOT_MAP = r"..."` 의 따옴표 안에 붙여넣기
3. DEM 5m 폴더도 같은 방식으로 `DATA_ROOT_DEM` 에
4. DEM 1m 을 받았다면 `DATA_ROOT_DEM1M = r"..."` (안 받았으면 `None` 그대로)
5. 저장 (메모장: 파일 → 저장, 인코딩이 UTF-8 인지 확인)

### 3-3. 구조 확인
```
python 01_inspect.py
```
화면을 보고 아래 표대로 판단합니다.

| 화면에 이렇게 나오면 | 이렇게 고치세요 (config.py) |
|---|---|
| `shp 파일 총 0개` | `DATA_ROOT_MAP` 경로가 틀림. 폴더를 다시 복사 |
| `[없음] sidewalk_cl ...` | 1번 목록에서 보도중심선에 해당하는 실제 파일명 글자를 `LAYERS["sidewalk_cl"]` 목록에 추가 |
| `prj 없음 → 추정 ...` 이고 범위 x가 80만~120만 | `DEFAULT_CRS = "EPSG:5179"` |
| `BPRP_SE 분포` 에 `BDU001` 이 없음 | 분포에 보이는 주거용 코드로 `RESIDENTIAL_USE` 수정 |
| 속성 이름이 `BPRP_SE` 가 아님 | `COL["bld_use"]` 를 실제 이름으로 |
| `DEM 5m: 파일 0개` | `DATA_ROOT_DEM` 경로 확인 |
| `scipy 없음` | 문제 없음. 느려질 뿐 결과는 같음 → 3-4에서 범위를 작게 |

### 3-4. 작은 범위로 시험 실행
1. 01_inspect 화면의 `범위 x ...~..., y ...~...` 에서 가운데쯤 2km×2km 를 골라 `config.py` 에 입력
   ```python
   AREA_BBOX = [194000, 541000, 196000, 543000]   # 예시. 실제 범위 숫자 안에서 고르기
   ```
2. `python 02_network.py` → `python 03_hbi.py` → `python 05_export.py`
3. 끝까지 되면 `AREA_BBOX = None` 으로 되돌리기 (2일차에 전체 실행)

### 3-5. 나오기 전에 메모할 것 (데이터 값은 적지 않기)
- `work/inspect_report.txt` 의 레이어 목록·좌표계 부분
- 오류가 났다면 **빨간 오류 메시지의 마지막 줄**과 몇 번 파일에서 났는지

---

## 4. 2~5일차

| 일차 | 명령 | 확인할 것 (화면) |
|---|---|---|
| 2 | `python 02_network.py` (DEM 1m 있으면 `--dem1m` 붙이기) | "남긴 연결망 N개 … 노드 비율" 90% 이상 (N = 서로 떨어진 구 묶음 수, 5개 구면 보통 4: 종로·중 / 관악 / 광진 / 강서) / "노드 고도 결측" 5% 이하 |
| 3 | `python 03_hbi.py` | "네트워크 연결" 95% 이상 / HBI 중앙값이 1.0~1.5 사이 |
| 3 | `external/od_pairs.csv`, `sites.csv` 를 메모장으로 열어 현장실측 좌표·시간, 화곡동 좌표 입력 | |
| 4 | `python 04_validate.py` | 선정지 percentile, 대현산 wheel_path_m, 기여도 표 |
| 3 | `config.py` 에 `DATA_ROOT_PARCEL`(센터가 준 필지 폴더, 서울 파일만 있는 폴더) 입력 → `python 06_parcel.py` | "필지 N개", 지목 '대' 필지 수 |
| 3 | KCB 파일을 받았으면 `config.py` 의 `JOIN_DATA` 경로 채우기 → `python 07_join_dong.py` (filter 의 `"__LATEST__"` = 그 열의 가장 늦은 값, `base_cols` = 분모 열 합) | "코드 방식 ... 로 N/M개 행정동 결합" 에서 N이 충분한지 |
| 4 | `python 08_sensitivity.py` (선택) | 순위상관이 0.9 이상이면 "가정을 바꿔도 결론 유지" |
| 4 | `external/interventions.csv` 에 시설 양 끝 좌표(현장실측 기록지) 입력 → `python 09_intervention.py` | "끝점이 길에서 N m 떨어져 있음" 경고가 없는지 / 시설별 "수혜 건물 N동, 평균 M분 단축" |
| 4 | SKT 유동인구 파일을 받았으면 `config.py` 의 `POINT_DATA` 경로 채우기 → `python 10_points_join.py` | "전체 → 조건 통과 → 좌표 있음 → 범위 안" 행 수와 "값 합계"(기간 수로 나눈 월평균) |
| 4 | 교통사고 파일을 받았으면 `config.py` 의 `LEGAL_DONG_DATA` 경로 채우기 → `python 11_legal_dong_join.py` | "전체 → 조건 통과 → 법정동 이름 있음 → 붙은 법정동" 건수, 06 결과에 법정동 이름(emd_nm)이 있는지 |
| 5 | `python 05_export.py` 를 한 번 더(최종) → 아래 "반출 전 체크리스트" 확인 → **반출 신청** |  |

한 번에 돌리려면 `python run_all.py` (DEM 1m 포함 `--dem1m`, 민감도 포함 `--sens`)
`DATA_ROOT_PARCEL` 이나 `JOIN_DATA` 경로를 채워 두면 06·07 도 자동으로 함께 실행됩니다.
[v5] `interventions.csv` 에 양 끝 좌표 4개가 다 채워진 행이 있으면 09, `POINT_DATA` 에 path 가 있으면 10 도 자동으로 실행됩니다.

### 반출 전 체크리스트 (output 폴더)
밖에서는 원자료를 다시 계산할 수 없으니, 반출 신청 전에 아래가 모두 있는지 확인하세요.
- [ ] `summary.csv` — 목적지별 요약 (기획서 16장)
- [ ] `grid_hbi.csv`, `grid_hbi_medical.gpkg` 등 — 격자 결과·지도 (16장, 본선 데모). [v6.2] 맨 뒤 `n_addNm`·`share_addNm` (왕복 추가 N분 이상 건물 수·비율, 문턱은 mapping 의 `extra_min_bands`)
- [ ] `dong_hbi.csv` — 행정동 결과 (weight_all·weight_high 열 포함 → 밖에서 고령인구 추정). [v6.2] 맨 뒤 `n_addNm`·`share_addNm`·`weight_addNm`. 연면적(weight_high·weight_addNm)은 1~4채 몫이 드러나면 빈 칸, weight_addNm 은 check 가 고른 방식 폴더에만
- [ ] `validation_sites.csv`, `validation_routes.csv`, `validation_new_candidates.csv`, `validation_ablation.csv` (17·18장)
- [ ] `validation_measured.csv` — [v5] 실측 vs 예측 상관계수 (실측 3구간 이상일 때, 17장)
- [ ] `intervention_summary.csv`, `intervention_grid.csv`, `intervention_dong.csv` — [v5] 시설 설치 효과 (22·23장). 맨 뒤 열 n_exit_high·weight_exit_high·n_exit_mid (summary), weight_exit_high (dong) = 설치 후 HBI 1.8(1.3) 아래로 내려온 주거 건물 (연면적은 MIN_COUNT 개 미만이면 빈 칸)
- [ ] `points_summary.csv`, `points_*_dong.csv`, `points_*_grid.csv` — [v5] 점 자료 결합 (개수·값 합계만, 좌표 없음)
- [ ] `legal_summary.csv`, `legal_*.csv` — [v5] 법정동별 교통사고 건수 (행 단위 사고 없음)
- [ ] `parcel_summary.csv`, `parcel_by_legal_dong.csv` (필지 결합)
- [ ] `join_summary.csv`, `join_*.csv` (KCB 를 썼다면, 19장)
- [ ] `sensitivity.csv` (민감도, 질의응답)
- [ ] `isochrone_*.gpkg`, `isochrone_summary.csv`, `map_isochrone_*.png` — [v5] 12_isochrone.py. 반출 설명: "시설 주변 도보 도달 범위를 나타낸 면 도형(길 중심선 25m 버퍼, 10m 단순화). 건물·필지 단위 정보 없음" (범위 안 주거 건물 수는 MIN_COUNT 개 미만이면 빈 칸)
- [ ] `dong_context.csv` — [v5] 14_dong_context.py. 행정동별 용도 비율·층수·역·정류장·링크 밀도·SKT 주거 칸 합 (건물 MIN_COUNT 개 이상 동만, 개별 건물·셀 좌표 없음)
- [ ] `siting_summary.csv` — [v5] 13_siting.py. 시설 둘레 30m 필지의 지목별 면적 비율만 (필지 번호·소유 정보 없음, 필지 MIN_COUNT 개 미만이면 비율 빈 칸)
- [ ] `map_*.png` (matplotlib 이 있을 때만. 없으면 gpkg 로 밖에서 지도 제작)

### 데이터 경계 처리
받은 도엽 범위의 가장자리에서 500m 안쪽 건물은 모든 통계에서 자동으로 빠집니다 (`config.EDGE_BUFFER`).
경계 근처 집은 가장 가까운 병원이 데이터 밖에 있을 수 있어 시간이 부풀려지기 때문입니다.
03단계 화면의 "데이터 경계 500m 이내 건물 N개" 비율이 50%를 넘으면 너무 많이 빠지는 것이니 `EDGE_BUFFER = 300` 으로 줄이세요.

---

## 5. 공개데이터 (external 폴더)

| 파일 | 내용 | 상태 |
|---|---|---|
| `sites.csv` | 서울시 2025 선정지 5곳 좌표 (lon=경도, lat=위도) | 입력됨 (근사 좌표, note 열 참고. 화곡동은 수정 권장) |
| `od_pairs.csv` | 검증 구간 출발·도착 좌표, `measured_min` = 실측 분 | 대현산배수지공원 입력됨. 현장실측 ①②③⑤ 네 줄(구역 B 관악·D 강서, 10/3~4)은 좌표·measured_min 을 직접 입력 |
| `dong_boundary.geojson` | 서울 행정동 경계 426개 (ADM_CD = 행안부 10자리, ADM_CD_STAT = 통계청 8자리) | 입력됨 |
| `pharmacy.csv` | 약국 `name, lon, lat` | 비어 있음 (없어도 의료시설 기준으로 분석됨) |
| `elderly_pop.csv` | 행정동 코드 `adm_cd`, 65세 이상 인구 `pop65` | 비어 있음 → 반출 후 밖에서 `tools/outside_elderly.py` 로 추정 |
| `pharmacy.csv` 만들기 | 공개 약국 파일 → `python tools/prep_public.py pharmacy 원본.csv [EPSG:5174]` (반입 전, 밖에서) | [v5] 서울·영업 중만 남김 |
| `subway_elevators.csv` | [v5] 엘리베이터 있는 지하철역 출입구 `name, lon, lat` → 목적지 `station_ev` (휠체어 결과 기준). `python tools/prep_public.py elevator 원본.csv` 로 만듦 | 머리 줄만 (반입 전 채우기) |
| `interventions.csv` | [v5] 설치 효과를 볼 시설: `name, type(elevator/monorail/vertical/ramp), a_lon, a_lat(아래), b_lon, b_lat(위), wait_s, speed, status(planned/existing), note`. wait_s·speed 를 비우면 `config.FACILITY` 기본값 | 대현산 모노레일 + 2025 선정지 5곳 입력됨. 양 끝 좌표는 현장실측 후 입력 (봉천동·화곡동은 현장실측 10/3~4 에서 입력 예정). 13_siting.py 도 이 좌표를 씀 |
| `iso_points.csv` | [v5] 12_isochrone.py 의 등시선 점: `name, lon, lat, minutes("5;10;15"), note` | 창신역 1번출구, 대현산배수지공원 모노레일 하부, 신당동 청구동 마을마당, 봉천동 비안어린이공원, 중곡동 용곡중 5곳 (근사 좌표, 현장실측 후 수정 가능) |

CSV는 메모장으로 열어 쉼표로 구분해서 입력하면 됩니다. 좌표는 네이버·카카오 지도에서 위치를 우클릭하면 나오는 **경위도**(예: 127.0215, 37.5569)를 쓰세요. 엑셀로 저장할 때는 "CSV UTF-8" 형식으로 저장하세요.

---

## 6. 반출 원칙

- **`output/` 만 반출 신청** (격자·행정동 집계, 요약 통계, 지도 이미지)
- 건물이 5개 미만인 격자·동은 자동으로 빠집니다 (`config.MIN_COUNT`)
- `work/` 는 건물 단위라 **반출하지 않습니다.** 필지의 소유·공시지가 정보는 읽지도 않습니다.

---

## 7. 자주 나는 오류

| 오류 메시지 (마지막 줄) | 원인과 해결 |
|---|---|
| `No module named 'osgeo'` | 일반 Python으로 실행함 → OSGeo4W Shell 또는 QGIS 콘솔 사용 |
| `No module named 'config'` | 폴더 위치가 틀림 → `cd` 로 `hbi` 폴더 안에 들어가서 실행 (콘솔은 `sys.path.insert` 줄 먼저) |
| `FileNotFoundError: ... network.npz` | 앞 단계를 안 돌림 → 02 → 03 순서대로 |
| `07_join_dong` 에서 "결합된 동이 너무 적습니다" | `JOIN_DATA` 의 `code_col` 이 실제 코드 열 이름인지, 파일을 열어 확인 |
| `SyntaxError` 또는 `IndentationError` | config.py 를 고치다 따옴표·쉼표를 지웠거나 들여쓰기가 바뀜 → 해당 줄 확인 |
| `보도중심선/도로중심선이 없습니다` | 3-3 표의 `[없음]` 해결 방법 참고 |
| `목적지가 없습니다` | 건물 용도 코드가 다름 → 01_inspect 의 BPRP_SE 분포 확인 후 `MEDICAL_USE` 수정 |
| `MemoryError` 또는 너무 느림 | `AREA_BBOX` 로 구 하나씩 나눠서 실행 |
| `swig/python detected a memory leak` | 무해한 경고. 무시 |
| 한글이 `???` 로 보임 | `SHP_ENCODING = "UTF-8"` 로 바꿔 보기 |

---

## 8. 안심구역 밖에서 (반출 후)
- 고령인구 추정: 행정안전부 인구 파일을 받아 `python tools/outside_elderly.py dong_hbi.csv 인구파일.csv`
- 결과 지도: `grid_hbi_medical.gpkg` 를 QGIS에서 열어 색칠 (05_export.py 맨 위 설명)
- 본선 데모: `grid_hbi.csv` 의 `elder_min`(경사 반영)·`flat_min`(평지 가정)·`hbi_mean` 을 미리보기 화면에 넣으면 됩니다

## 9. 모델 요약 (기획서·질의응답용)

- **고령자:** 평지 0.8m/s. 오르막은 Tobler 보행함수로 느려지고, 내리막은 같은 경사 오르막 부담의 50%만큼 느려짐. 계단은 최소 경사 25%로 보고 1.2배 가중
- **휠체어:** 평지 1.0m/s. 경사가 1/12(8.3%)를 넘으면 시간 10배(사실상 회피), 계단은 통행 불가
- **HBI** = 경사 반영 왕복시간 ÷ 평지 가정 왕복시간 (귀갓길 편도 배수 `home_ratio` 도 함께 산출)
- 다리·터널 위는 경사 0, 경사 ±40% 초과는 오류로 보고 잘라냄
