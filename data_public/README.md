# data_public — 공개 데이터와 밖(안심구역 외부) 도구

원본은 `data_public/raw/` 에 둡니다 (git 에 올라가지 않음). 정리한 결과만 필요한 곳으로 옮깁니다.

## 받을 파일

| 파일 | 받는 곳 | 쓰는 도구 | 상태 |
|---|---|---|---|
| 행정동별 연령별 인구 (65세 이상) | 행정안전부 주민등록 인구통계 (jumin.mois.go.kr) | `tools/prep_elderly_pop.py` → `elderly_pop.csv` → `outside_elderly.py` | **다시 받기**: 9/29 파일은 구 단위(26행)만. 읍면동까지 펼쳐서 받아야 함 |
| 동별 장애인 현황 (장애유형별) | 서울 열린데이터광장 | `tools/outside_join_dong.py --cols 지체,뇌병변` | **다시 받기**: 9/29 파일은 동별(1)·(2)=구 단위만. 동별(3)까지 선택 |
| 동별 독거노인 현황 (성별) | 서울 열린데이터광장 | `tools/outside_join_dong.py --cols 합계` | 받음 9/29 (동 단위, 5개 구 88/88 동 결합) |
| 자치구별 도보 네트워크 공간정보 (+ 링크노드유형코드.xlsx) | 서울 열린데이터광장 | `tools/public_baseline.py --network --gu …` | 받음 9/29. 유형코드에 계단·엘리베이터·육교·횡단보도 없음 |
| 지하철 역사 좌표 (역사마스터) | 서울 열린데이터광장 | `tools/prep_points.py … --seoul` → `subway_stations.csv` (400행) | 받음 9/29 |
| [2차 반입용] 지하철역 엘리베이터 위치 | 서울 열린데이터광장 | `analysis/hbi/tools/prep_public.py elevator` → `external/subway_elevators.csv` | 받음 9/29, v5 번들에 552행 |
| [2차 반입용] 약국 위치 | 지방행정인허가 건강_약국 (서울) | `analysis/hbi/tools/prep_public.py pharmacy` → `external/pharmacy.csv` | 받음 9/29, v5 번들에 5,859행 (EPSG:5174, 구 일치 99.91%) |
| AWS Terrain Tiles (terrarium z15) | 자동 다운로드 | `tools/public_baseline.py` (캐시: `raw/terrain_cache/`) | 자동 |
| 기설치·예정 이동편의시설 15곳 | 서울시 보도자료 등 | `existing_facilities.csv` (feat/field-survey) | 정리됨 |

## 밖 도구 (레포 최상위 `tools/`)

| 도구 | 입력 | 출력 | 한 줄 설명 |
|---|---|---|---|
| `outside_join_dong.py` | 반출 `dong_hbi.csv` + 동별 통계 CSV (여러 개) | `results/dong_joined.csv` | "자치구 + 동 이름"으로 결합, `<label>_<열>_in_high` = 값 × weight_high ÷ weight_all |
| `public_baseline.py` | 도보 네트워크 CSV, 역 좌표, (선택) 반출 `grid_hbi.csv` | `results/public_baseline/grid_public_<target>.csv`, `compare_<target>.csv` | 공개데이터만으로 같은 모델(analysis/hbi/lib 그대로)을 돌린 대조군과 LX 결과 비교 |
| `prep_points.py` | 아무 점 CSV | `name, lon, lat` CSV | 이름·좌표 열 자동 인식, 미터 좌표면 경위도로 변환, `--seoul` 서울 경계 안만 |
| `prep_elderly_pop.py` | 주민등록 고령 인구현황 CSV | `elderly_pop.csv` (adm_cd, pop65) | 동 단위 행만. 구 단위 파일이면 저장하지 않음 |

실행 환경: 일반 Python 3 + numpy. `public_baseline.py` 는 osgeo(QGIS Python) 또는 pyproj + Pillow 가 필요합니다
(`--backend auto` 가 실제로 한 번 변환·이미지 읽기를 해 보고 되는 쪽을 고름).
