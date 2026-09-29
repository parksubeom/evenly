# data_public — 공개 데이터와 밖(안심구역 외부) 도구

원본은 `data_public/raw/` 에 둡니다 (git 에 올라가지 않음). 정리한 결과만 필요한 곳으로 옮깁니다.

## 받을 파일

| 파일 | 받는 곳 | 쓰는 도구 | 상태 |
|---|---|---|---|
| 행정동별 연령별 인구 (65세 이상) | 행정안전부 주민등록 인구통계 (jumin.mois.go.kr) | `analysis/hbi/tools/outside_elderly.py` | 받을 것 |
| 동별 장애인 현황 (장애유형별) | 서울 열린데이터광장 | `tools/outside_join_dong.py` | 받을 것 |
| 동별 독거노인 현황 (연령별) | 서울 열린데이터광장 | `tools/outside_join_dong.py` | 받을 것 |
| 자치구별 도보 네트워크 공간정보 | 서울 열린데이터광장 | `tools/public_baseline.py --network` | 받을 것 |
| 지하철 역사 좌표 | 공공데이터포털·서울 열린데이터광장 | `tools/prep_points.py` → `public_baseline.py --stations` | 받을 것 |
| [2차 반입용] 지하철역 엘리베이터 위치 | 공공데이터포털 | `analysis/hbi/tools/prep_public.py elevator` → `external/subway_elevators.csv` | 받을 것 (10/2 전) |
| [2차 반입용] 약국 위치 | 공공데이터포털 (전국약국표준데이터 등) | `analysis/hbi/tools/prep_public.py pharmacy` → `external/pharmacy.csv` | 받을 것 (10/2 전) |
| AWS Terrain Tiles (terrarium z15) | 자동 다운로드 | `tools/public_baseline.py` (캐시: `raw/terrain_cache/`) | 자동 |
| 기설치·예정 이동편의시설 15곳 | 서울시 보도자료 등 | `existing_facilities.csv` (feat/field-survey) | 정리됨 |

## 밖 도구 (레포 최상위 `tools/`)

| 도구 | 입력 | 출력 | 한 줄 설명 |
|---|---|---|---|
| `outside_join_dong.py` | 반출 `dong_hbi.csv` + 동별 통계 CSV (여러 개) | `results/dong_joined.csv` | "자치구 + 동 이름"으로 결합, `<label>_<열>_in_high` = 값 × weight_high ÷ weight_all |
| `public_baseline.py` | 도보 네트워크 CSV, 역 좌표, (선택) 반출 `grid_hbi.csv` | `results/public_baseline/grid_public_<target>.csv`, `compare_<target>.csv` | 공개데이터만으로 같은 모델(analysis/hbi/lib 그대로)을 돌린 대조군과 LX 결과 비교 |
| `prep_points.py` | 아무 점 CSV | `name, lon, lat` CSV | 이름·좌표 열 자동 인식, 미터 좌표면 경위도로 변환 |

실행 환경: 일반 Python 3 + numpy. `public_baseline.py` 는 osgeo(QGIS Python) 또는 pyproj + Pillow 가 필요합니다
(`--backend auto` 가 실제로 한 번 변환·이미지 읽기를 해 보고 되는 쪽을 고름).
