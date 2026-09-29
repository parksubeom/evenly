# -*- coding: utf-8 -*-
"""
tools/prep_elderly_pop.py ─ [안심구역 밖] 행정안전부 "주민등록인구기타현황(고령 인구현황)" → data_public/elderly_pop.csv (adm_cd, pop65)

[실행]  python3 tools/prep_elderly_pop.py 202608_202608_주민등록인구기타현황(고령 인구현황)_월간.csv [--out data_public/elderly_pop.csv]
[받는 법] 주민등록 인구통계 사이트에서 행정구역을 "서울특별시 → 전체 구 → 읍면동" 까지 펼친 상태로 내려받아야 동 단위가 나옴
[하는 일]
  1. "행정구역" 열의 "서울특별시 종로구 청운효자동 (1111051500)" 에서 괄호 안 10자리 행정기관코드를 꺼냄
  2. "…_65세이상전체" 열(쉼표 제거)을 65세 이상 인구로 씀
  3. 동 단위 코드(끝 5자리가 00000 이 아닌 것)만 남기고, external/dong_boundary.geojson 의 ADM_CD 와 몇 개가 맞는지 보고
  4. 동 단위 행이 하나도 없으면(구 단위 파일) 저장하지 않고 멈춤 → 구 단위 값을 동에 나눠 채우지 않음
[결과] data_public/elderly_pop.csv  → analysis/hbi/tools/outside_elderly.py 의 인구 파일로 바로 사용 (adm_cd, pop65 형식 인식)
"""
import csv, json, os, re, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TARGET_GU = ["종로구", "중구", "관악구", "광진구", "강서구"]


def main():
    args = sys.argv[1:]
    out = os.path.join(ROOT, "data_public", "elderly_pop.csv")
    if "--out" in args:
        i = args.index("--out"); out = args[i + 1]; del args[i:i + 2]
    if not args:
        raise SystemExit(__doc__)
    for enc in ("utf-8-sig", "cp949", "euc-kr"):
        try:
            rows = list(csv.reader(open(args[0], encoding=enc, newline="")))
            break
        except UnicodeDecodeError:
            continue
    head = rows[0]
    ci = next((i for i, c in enumerate(head) if "행정구역" in c), None)
    pi = next((i for i, c in enumerate(head) if re.search(r"65세이상(전체|계)?$", c.replace(" ", "")) and "남" not in c and "여" not in c), None)
    if ci is None or pi is None:
        raise SystemExit(f"'행정구역' 또는 '65세이상전체' 열을 찾지 못함. 머리 줄: {head}")
    print(f"열: 행정구역='{head[ci]}', 65세 이상='{head[pi]}', 데이터 {len(rows) - 1}행")
    recs, gu_rows = [], 0
    for r in rows[1:]:
        m = re.search(r"\((\d{10})\)", r[ci])
        if not m:
            continue
        code = m.group(1)
        if code[5:] == "00000":                            # 시·구 합계 행
            gu_rows += 1
            continue
        v = r[pi].replace(",", "").strip()
        if v.isdigit():
            recs.append((code, int(v), r[ci]))
    seoul = [x for x in recs if x[0].startswith("11")]
    tgt = [x for x in seoul if any(g in x[2] for g in TARGET_GU)]
    gj = json.load(open(os.path.join(ROOT, "analysis", "hbi", "external", "dong_boundary.geojson"), encoding="utf-8"))
    bcodes = {str(f["properties"]["ADM_CD"]) for f in gj["features"]}
    hit = sum(1 for x in seoul if x[0] in bcodes)
    print(f"시·구 합계 행 {gu_rows}, 서울 행정동 {len(seoul)}, 대상 5개 구 행정동 {len(tgt)}, "
          f"dong_boundary ADM_CD 와 일치 {hit} / {len(bcodes)} (경계 기준)")
    if not seoul:
        raise SystemExit("!! 동 단위 행이 없습니다 (구 단위 파일). 행정구역을 읍면동까지 펼쳐서 다시 내려받으세요 → 저장하지 않음")
    os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
    with open(out, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(["adm_cd", "pop65"])
        w.writerows([(c, v) for c, v, _ in seoul])
    print(f"→ {out} ({len(seoul)}행)")


if __name__ == "__main__":
    main()
