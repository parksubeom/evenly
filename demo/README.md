# 본선 데모 화면

- `hbi_preview.html` : 지금 버전. 공개 지형(약 30m급) + 지하철역 7곳으로 만든 **미리보기** (창신·숭인동)
- `page_template.html` : 화면 틀. `__DATA__`, `__HILL__` 자리에 데이터가 들어감
- `fetch_public_dem.py` → `sim_public_terrain.py` → `prep_preview_data.py` : 미리보기 데이터를 만든 과정 (재현용)

실제 결과로 바꿀 때: 반출된 `grid_hbi.csv`(target=medical 또는 station)의 `cell_x, cell_y, hbi_mean, elder_min, flat_min` 을
화면의 격자 데이터로 변환해 넣으면 됩니다. (변환 스크립트는 결과 형식 확정 후 작성)
