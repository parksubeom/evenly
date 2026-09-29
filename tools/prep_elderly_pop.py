# -*- coding: utf-8 -*-
"""
tools/prep_elderly_pop.py ─ [안심구역 밖] 행정안전부 행정동 인구 파일 → data_public/elderly_pop.csv (adm_cd, pop65, base_ym)

[읽는 형식 2가지]
  A) 공공데이터포털 "행정안전부_지역별(행정동) 성별 연령별 주민등록 인구수": 행정기관코드, 기준연월, …, "65세남자"~"110세이상 여자"
     → 65세 이상 남녀 열을 모두 더함 (권장)
  B) 주민등록 인구통계 "주민등록인구기타현황(고령 인구현황)": "행정구역" 열의 괄호 안 코드 + "…_65세이상전체" 열

[실행]  python3 tools/prep_elderly_pop.py 202608_202608_주민등록인구기타현황(고령 인구현황)_월간.csv [--out data_public/elderly_pop.csv]
        python3 tools/prep_elderly_pop.py "행정안전부_지역별(행정동) 성별 연령별 주민등록 인구수_20260831.csv" --min-age 60
          → data_public/pop60.csv (adm_cd, pop60, base_ym). 19장 외출 지수 분모: SKT·KCB 가 60세 이상 구간이라 같은 기준으로 맞춤
          (--min-age 는 1세 단위 열이 있는 형식 A 에서만. 형식 B 는 65세이상 합계 열뿐이라 65 만 됨)
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
    min_age = 65
    if "--min-age" in args:
        i = args.index("--min-age"); min_age = int(args[i + 1]); del args[i:i + 2]
    col = f"pop{min_age}"
    out = os.path.join(ROOT, "data_public", "elderly_pop.csv" if min_age == 65 else f"{col}.csv")
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
    if "행정기관코드" in head:                              # ── 형식 A (연령별 한 살 단위 열)
        ki, yi = head.index("행정기관코드"), (head.index("기준연월") if "기준연월" in head else None)
        age = [(i, int(m.group(1))) for i, c in enumerate(head) for m in [re.match(r"^(\d+)세(?:이상)?\s*(?:남자|여자)$", c.strip())] if m]
        old = [i for i, a in age if a >= min_age]
        print(f"형식 A: 연령 열 {len(age)}개 중 {min_age}세 이상 {len(old)}개 합산 ({head[old[0]]} … {head[old[-1]]}), 데이터 {len(rows) - 1}행")
        recs, gu_rows, ym = [], 0, set()
        for r in rows[1:]:
            code = r[ki].strip()
            if not re.fullmatch(r"\d{10}", code):
                continue
            if yi is not None:
                ym.add(r[yi])
            if code[5:] == "00000":
                gu_rows += 1
                continue
            recs.append((code, int(sum(float(r[i].replace(",", "") or 0) for i in old)), " ".join(r[2:5])))
        base_ym = ",".join(sorted(ym)) or ""
    else:
        recs = None
    if recs is None and min_age != 65:
        raise SystemExit(f"--min-age {min_age}: 1세 단위 연령 열이 있는 형식 A(행정기관코드 열) 파일만 됩니다. 이 파일은 65세이상 합계뿐")
    if recs is None:
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
        m = re.match(r"(\d{6})_", os.path.basename(args[0]))
        base_ym = m.group(1) if m else ""
    seoul = [x for x in recs if x[0].startswith("11")]
    tgt = [x for x in seoul if any(f" {g} " in f" {x[2]} " for g in TARGET_GU)]
    gj = json.load(open(os.path.join(ROOT, "analysis", "hbi", "external", "dong_boundary.geojson"), encoding="utf-8"))
    bcodes = {str(f["properties"]["ADM_CD"]) for f in gj["features"]}
    tcodes = {str(f["properties"]["ADM_CD"]) for f in gj["features"] if f["properties"].get("sggnm") in TARGET_GU}
    got = {x[0] for x in seoul}
    print(f"기준연월 {base_ym}, 시·구 합계 행 {gu_rows}, 서울 행정동 {len(seoul)}, 대상 5개 구 행정동 {len(tgt)}")
    print(f"dong_boundary ADM_CD 와 짝: 서울 {len(got & bcodes)} / {len(bcodes)}, 대상 5개 구 {len(got & tcodes)} / {len(tcodes)}")
    if bcodes - got:
        print(f"  경계에는 있는데 인구 파일에 없는 코드: {sorted(bcodes - got)}")
    if got - bcodes:
        print(f"  인구 파일에는 있는데 경계에 없는 코드 {len(got - bcodes)}개: {sorted(got - bcodes)[:10]}")
    if not seoul:
        raise SystemExit("!! 동 단위 행이 없습니다 (구 단위 파일). 행정구역을 읍면동까지 펼쳐서 다시 내려받으세요 → 저장하지 않음")
    os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
    with open(out, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(["adm_cd", col, "base_ym"])
        w.writerows([(c, v, base_ym) for c, v, _ in seoul])
    print(f"→ {out} ({len(seoul)}행)")


if __name__ == "__main__":
    main()
