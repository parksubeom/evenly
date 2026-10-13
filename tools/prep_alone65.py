# -*- coding: utf-8 -*-
"""
tools/prep_alone65.py ─ [안심구역 밖, v6.3] 서울시 동별 독거노인 현황 → data_public/alone65.csv (adm_cd, alone65, base) → 반입 external/alone65.csv

[실행]  python3 tools/prep_alone65.py ["data_public/raw/독거노인+현황(성별_동별)_….csv"] [--out data_public/alone65.csv]
[하는 일] 통계 파일의 (자치구, 동 이름) 을 external/dong_boundary.geojson 의 행정동 이름과 맞춰 10자리 행정동 코드를 붙임
        (이름 맞추기·머리 줄 찾기는 tools/outside_join_dong.py 와 같은 함수: 공백 제거, "제3동" → "3동", 가운뎃점 통일).
        값 열 = '합계' (합계_소계_계_소계 = 독거노인 전체). 맞지 않은 이름은 화면에 적고 버림 (추정하지 않음)
[쓰는 곳] 05_export.py 가 '고립 위험 격자 안 독거노인 추정' = 동 독거노인 × (고립 위험 격자 안 주거 연면적 ÷ 동 주거 연면적) 으로 씀 (어르신 추정과 같은 방식)
"""
import argparse, csv, json, os, sys, unicodedata

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools"))
from outside_join_dong import parse_stat, norm          # noqa: E402  (같은 이름 맞추기)

GEO = os.path.join(ROOT, "analysis", "hbi", "external", "dong_boundary.geojson")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("stat", nargs="?", default=None)
    ap.add_argument("--out", default=os.path.join(ROOT, "data_public", "alone65.csv"))
    a = ap.parse_args()
    raw = os.path.join(ROOT, "data_public", "raw")              # 맥 파일 이름은 NFD 일 수 있어 NFC 로 바꿔 찾음
    hit = sorted(f for f in os.listdir(raw) if unicodedata.normalize("NFC", f).startswith("독거노인") and "동별" in unicodedata.normalize("NFC", f)) if os.path.isdir(raw) else []
    src = a.stat or (os.path.join(raw, hit[0]) if hit else None)
    if not src or not os.path.exists(src):
        raise SystemExit("독거노인 동별 통계 파일이 없습니다 (data_public/raw/독거노인+현황(성별_동별)_….csv)")
    st = parse_stat(src, ["합계"], None)                 # {(구, 동): {"vals": [값], "gu":…, "dong":…}}
    g = json.load(open(GEO, encoding="utf-8"))
    by = {}
    for f in g["features"]:
        p = f["properties"]
        nm = (p.get("ADM_NM") or p.get("adm_nm") or "").split()
        cd = str(p.get("ADM_CD") or p.get("adm_cd") or "")
        if len(nm) >= 3 and cd:
            by[(norm(nm[-2]), norm(nm[-1]))] = cd
    rows, miss = [], []
    for k, v in st.items():
        if k in by and v["vals"] and v["vals"][0] is not None:
            rows.append([by[k], int(round(v["vals"][0])), os.path.basename(src)])
        else:
            miss.append(f"{v['gu']} {v['dong']}")
    rows.sort()
    os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
    with open(a.out, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(["adm_cd", "alone65", "source"])
        w.writerows(rows)
    print(f"→ {os.path.relpath(a.out, ROOT)}: 행정동 {len(rows)}개 (통계 행 {len(st)}개 중 이름이 맞은 것). 맞지 않은 {len(miss)}개: {', '.join(miss[:20]) or '-'}")


if __name__ == "__main__":
    main()
