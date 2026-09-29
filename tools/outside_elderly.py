# -*- coding: utf-8 -*-
"""
tools/outside_elderly.py ─ [안심구역 밖] 반출 dong_hbi.csv + 행정동 65세 이상 인구 → dong_hbi_with_elderly.csv

[실행]  python3 tools/outside_elderly.py results/raw_export/dong_hbi.csv [data_public/elderly_pop.csv]
        인구 파일을 생략하면 data_public/elderly_pop.csv (tools/prep_elderly_pop.py 로 만든 adm_cd, pop65, base_ym)
[계산]  동별 추정 = 65세 이상 인구 × (HBI 1.8 이상 건물 연면적 weight_high ÷ 동 전체 주거 연면적 weight_all)
[결과]  입력 dong_hbi.csv 와 **같은 폴더**의 dong_hbi_with_elderly.csv
        열: dong_hbi.csv 열 그대로(elderly_in_high_est 채움) + pop65 + base_ym(인구 기준연월)
[참고]  analysis/hbi/tools/outside_elderly.py (v4·v5 번들 안) 는 예전 인구 파일 형식("행정기관코드" + "65~69세" 연령대 열)을 기대하므로
        밖에서는 이 파일을 씁니다. 안심구역 안 단계(01~10)는 어느 쪽도 부르지 않습니다.
"""
import csv, os, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def read(p):
    for enc in ("utf-8-sig", "cp949"):
        try:
            with open(p, encoding=enc, newline="") as f:
                return list(csv.DictReader(f))
        except UnicodeDecodeError:
            pass
    raise SystemExit(f"인코딩을 알 수 없음: {p}")


def num(v):
    try:
        return float(str(v).replace(",", "").strip())
    except ValueError:
        return None


def main():
    if len(sys.argv) < 2:
        raise SystemExit(__doc__)
    dong = sys.argv[1]
    popf = sys.argv[2] if len(sys.argv) > 2 else os.path.join(ROOT, "data_public", "elderly_pop.csv")
    pr = read(popf)
    if not pr or "adm_cd" not in pr[0] or "pop65" not in pr[0]:
        raise SystemExit(f"인구 파일은 adm_cd, pop65 열이 필요합니다 (tools/prep_elderly_pop.py 결과): {popf}")
    pop = {r["adm_cd"].strip(): num(r["pop65"]) for r in pr}
    base = sorted({r.get("base_ym", "") for r in pr if r.get("base_ym")})
    base_ym = ",".join(base)
    rows = read(dong)
    out, total, hit = [], 0, 0
    for d in rows:
        p = pop.get(str(d["adm_cd"]).strip())
        wa, wh = num(d.get("weight_all")), num(d.get("weight_high"))
        est = round(p * wh / wa) if p and wa and wh is not None else ""
        if p is not None:
            hit += 1
        if est != "":
            total += est
        out.append({**d, "elderly_in_high_est": est, "pop65": "" if p is None else round(p), "base_ym": base_ym})
    dst = os.path.join(os.path.dirname(os.path.abspath(dong)), "dong_hbi_with_elderly.csv")
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from evenly_common import is_fake_dir, refuse_raw_export
    if is_fake_dir(os.path.dirname(dst)):
        refuse_raw_export(os.path.dirname(dst), "입력 폴더에 가짜 표지(_source.txt=fake)가 있습니다")
    with open(dst, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=list(out[0].keys()))
        w.writeheader()
        w.writerows(out)
    miss = [d["adm_nm"] for d in rows if str(d["adm_cd"]).strip() not in pop]
    print(f"인구 파일 {os.path.basename(popf)} (기준 {base_ym or '표시 없음'}), 결합 {hit}/{len(rows)}개 동, "
          f"HBI 1.8 이상 거주 고령인구 추정 약 {total:,}명")
    if miss:
        print(f"  인구가 없는 동 {len(miss)}개: {', '.join(miss)}")
    print(f"→ {dst}")


if __name__ == "__main__":
    main()
