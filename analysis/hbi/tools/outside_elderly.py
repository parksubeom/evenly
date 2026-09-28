# -*- coding: utf-8 -*-
"""
tools/outside_elderly.py ─ [안심구역 밖, 반출 후] 고령인구 추정 ("HBI 1.8 이상 집에 사는 고령자 약 ○명")

[언제] 반출한 output/dong_hbi.csv 와, 밖에서 받은 행정안전부 행정동별 연령 인구 파일이 있을 때
[준비] 인구 파일을 CSV 로 저장하고 아래 두 줄의 열 이름을 파일에 맞게 고칩니다
[실행] python tools/outside_elderly.py 반출폴더/dong_hbi.csv 인구파일.csv
[계산] 동별 추정 = 65세 이상 인구 × (HBI 1.8 이상 건물 연면적 ÷ 동 전체 주거 연면적)
"""
import csv, sys
CODE_COL = "행정기관코드"          # ▲ 인구 파일의 행정동 코드 열 (10자리)
POP65_COLS = ["65~69세", "70~74세", "75~79세", "80~84세", "85~89세", "90~94세", "95~99세", "100세 이상"]  # ▲ 65세 이상 열들

def read(p):
    for enc in ("utf-8-sig", "cp949"):
        try:
            return list(csv.DictReader(open(p, encoding=enc)))
        except UnicodeDecodeError:
            pass
num = lambda v: float(str(v).replace(",", "") or 0)
dong, popf = sys.argv[1], sys.argv[2]
pop = {}
for r in read(popf):
    code = "".join(c for c in str(r.get(CODE_COL, "")) if c.isdigit())
    if code:
        pop[code] = sum(num(r.get(c, 0)) for c in POP65_COLS if c in r)
out, total = [], 0
for d in read(dong):
    p = pop.get(d["adm_cd"])
    wa, wh = num(d["weight_all"]), num(d["weight_high"])
    est = round(p * wh / wa) if p and wa else ""
    if est != "": total += est
    out.append({**d, "pop65": p or "", "elderly_in_high_est": est})
with open("dong_hbi_with_elderly.csv", "w", newline="", encoding="utf-8-sig") as f:
    w = csv.DictWriter(f, fieldnames=list(out[0].keys())); w.writeheader(); w.writerows(out)
print(f"결합 {sum(1 for o in out if o['pop65'] != '')}/{len(out)}개 동, HBI 1.8 이상 거주 고령인구 추정 약 {total:,}명 → dong_hbi_with_elderly.csv")
