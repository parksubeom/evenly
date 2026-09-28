# 언덕 위 우리동네 – 분석 코드 (데이터안심구역 반입용)

경사를 반영한 이동약자 보행 접근성(언덕 부담 지수, HBI)을 계산합니다.
수치지형도(보도·도로중심선, 계단, 건물, 정류장)와 DEM 5m를 결합합니다.

## 0. 준비 (안심구역 밖, 방문 전)
1. `pip install -r requirements.txt`
2. `python tools/make_test_data.py` → `testdata/` 생성
3. `config.py`의 경로를 `testdata/map`, `testdata/dem`으로 바꾸고 `python run_all.py` 실행 → 오류 없이 끝나는지 확인
4. `external/` 폴더의 CSV 채우기 (아래 표). 좌표는 **WGS84 경위도(lon, lat)**

| 파일 | 내용 | 출처 |
|---|---|---|
| pharmacy.csv | name, lon, lat | 공공데이터포털 약국 정보(국립중앙의료원 또는 건강보험심사평가원). 좌표 열 이름을 lon, lat로 변경 |
| sites.csv | 서울시 2025 선정지 5곳 좌표 | 포함됨 (OSM 지명 기준 근사 좌표, note 열 확인) |
| od_pairs.csv | 검증 구간 출발·도착 좌표, 실측 분 | 대현산배수지공원 구간 + 팀 현장실측 |
| elderly_pop.csv | adm_cd(행정동코드), pop65 | 행정안전부 주민등록 인구통계 (선택) |
| dong_boundary.geojson | 서울 행정동 경계 426개 (ADM_CD=행정기관코드 10자리) | 포함됨 (공개 행정동 경계, 2025.04 기준) |

## 1. 안심구역에서 실행 순서
| 일차 | 명령 | 확인할 것 |
|---|---|---|
| 1 | `python 01_inspect.py` | 레이어 코드·좌표계·필드명이 config와 맞는지. 다르면 `config.py`만 수정 |
| 2 | `python 02_network.py` (`--dem1m` 선택) | "최대 연결망 노드 비율" 90% 이상, 경사 절단 비율 1% 미만 |
| 3 | `python 03_hbi.py` | 주거 건물 네트워크 연결 95% 이상, HBI 분포 |
| 4 | `python 04_validate.py` | 선정지 백분위, 구간 재현, 기여도 표 |
| 5 | `python 05_export.py` | `output/` 파일 → 반출 신청 |
| 2회차 | `python 06_parcel.py` | 국토정보필지 결합 |

한 번에: `python run_all.py` (DEM 1m 비교 포함: `python run_all.py --dem1m`)
처음에는 `config.AREA_BBOX`에 작은 범위(예: 관악구 일부)를 넣어 빠르게 시험한 뒤 전체로 돌리세요.

## 2. 반출 원칙
- `output/`만 반출 신청 (격자·행정동 집계, 요약 통계, 지도 이미지)
- 건물 수 `MIN_COUNT`(5)개 미만 격자는 자동 제외
- `work/`(건물·필지 단위 결과)는 반출하지 않음. 필지 소유·공시지가 정보는 읽지 않음

## 3. 자주 나는 문제
| 증상 | 조치 |
|---|---|
| `레이어 없음` | 01_inspect 결과의 실제 파일명을 `config.LAYERS`에 추가 |
| 한글 필드가 깨짐 | `config.SHP_ENCODINGS` 순서 변경 |
| 좌표가 엉뚱한 곳 | 01_inspect의 "범위" 확인. x가 10만~40만이면 EPSG:5186, 80만~120만이면 EPSG:5179 → `DEFAULT_CRS` 수정 |
| 최대 연결망 비율이 낮음 | `BRIDGE_TOL`을 10 → 15로 올려 재실행 |
| 주거 건물이 0개 | 01_inspect의 BPRP_SE 분포 확인 후 `RESIDENTIAL_USE` 수정 |
| 메모리 부족 | `AREA_BBOX`로 구 단위로 나눠 실행 |
| 경로가 계단을 안 탐 | `STAIR_CONNECT_TOL`을 15 → 25로 조정 |

오류가 나면 **오류 메시지 마지막 줄만** 메모해 오세요(데이터 값은 적지 않기).

## 4. 모델 요약
- 고령자: 평지 0.8m/s × Tobler 보행함수(오르막), 내리막은 오르막 부담의 50%, 계단 최소 경사 25%·가중 1.2
- 휠체어: 1.0m/s, 경사 1/12 초과 시간 10배, 계단 통행 불가
- HBI = 경사 반영 왕복시간 ÷ 평지 가정 왕복시간 (귀갓길 편도 배수도 함께 산출)
