# 본선 데모 화면

```
python3 demo/build_demo.py                            # 실제 반출 결과(results/raw_export) → demo/evenly_demo.html
python3 demo/build_demo.py --src results/fake_export  # 가짜 결과로 시험 (상단에 빨간 "테스트 데이터" 경고)
```
- `evenly_demo.html` : html 파일 하나. 외부 요청(웹폰트·CDN·지도 타일) 없이 더블클릭으로 열림. 모바일 390px 대응
  - 자치구 선택, 목적지 선택, 보기 전환(평지로 계산 / 경사 반영 / 언덕 부담 지수), 칸 클릭 시 "평지 N분 → 실제 M분" 카드, 선정지 5곳 표시
  - 배경은 공개 행정동 경계만 사용 (DEM 음영 없음)
- `evenly_template.html` : 위 화면의 틀 (`__DATA__` 자리에 데이터가 들어감)
- `build_demo.py` 가 쓰는 파일: `grid_hbi.csv`(필수), `validation_sites.csv`, `validation_new_candidates.csv`(있으면)

## 예전 미리보기 (참고용)
- `hbi_preview.html` : 공개 지형(약 30m급) + 지하철역 7곳으로 만든 **미리보기** (창신·숭인동)
- `page_template.html` : 미리보기 화면 틀. `fetch_public_dem.py` → `sim_public_terrain.py` → `prep_preview_data.py` 로 재현
