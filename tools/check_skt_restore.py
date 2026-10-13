# -*- coding: utf-8 -*-
"""
tools/check_skt_restore.py ─ [10/13 판정 A2 시험] SKT 지수 × 공개 인구로 절대값(유동인구)이 되살아나지 않는지

[실행]  python3 tools/check_skt_restore.py <v6.3 hbi 폴더> <정답 hbi 폴더(v6.2, 값 합계 n_points 가 있는 결과)>
        (scratchpad 회귀 regress63.sh 의 reg63_<이름표>/v63/hbi 와 v62/hbi: 같은 가짜 자료·같은 가짜 SKT)
[보는 것]
  1. v6.3 points_SKT_*_dong.csv 의 index 가 구마다 평균 1.0 (유효숫자 2자리라 ±0.05)
  2. 정답 유동 ÷ (index × 공개 60세 이상 인구) = 구마다 같은 배율 K (±6%) → 지수 × 인구 는 유동을 모르는 K 로 나눈 값일 뿐
  3. K, 1/K, 구 유동 합·평균, 구 (유동 합 ÷ 인구 합) 이 v6.3 결과 CSV 어디에도 숫자로 없음 (±1%. 방식 폴더 모두, run_summary 포함)
[결과] 화면에 통과/실패. 실패하면 종료 코드 1
"""
import csv, glob, os, re, sys

def read(p):
    with open(p, encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))

def num(v):
    try:
        return float(str(v).replace(",", "").strip())
    except (TypeError, ValueError):
        return None

H63, H62 = map(os.path.abspath, sys.argv[1:3])
bad = []
f63 = sorted(glob.glob(f"{H63}/output/**/points_SKT*60*_dong.csv", recursive=True))
f62 = sorted(glob.glob(f"{H62}/output/**/points_SKT*60*_dong.csv", recursive=True))
if not f63 or not f62:
    sys.exit(f"!! points_SKT*_dong.csv 없음: v6.3 {len(f63)}개, 정답 {len(f62)}개")
truth = {r["adm_cd"]: num(r.get("n_points")) for r in read(f62[0])}
pop = {r["adm_cd"]: num(r.get("pop60")) for r in read(os.path.join(H63, "external", "pop60.csv"))}
targets = []
for f in f63:
    idx = {r["adm_cd"]: num(r.get("index")) for r in read(f) if num(r.get("index")) is not None}
    if not idx:
        continue
    print(f"[{os.path.relpath(f, H63)}] 지수를 낸 동 {len(idx)}개")
    for gk in sorted({c[:5] for c in idx}):
        cs = [c for c in idx if c[:5] == gk]
        m = sum(idx[c] for c in cs) / len(cs)
        ok1 = abs(m - 1) <= 0.05
        ks = [truth[c] / (idx[c] * pop[c]) for c in cs if truth.get(c) and pop.get(c) and idx[c] > 0]
        kmed = sorted(ks)[len(ks) // 2] if ks else None
        spread = max(abs(k / kmed - 1) for k in ks) if ks else None
        ok2 = spread is not None and spread <= 0.06
        tot = sum(truth[c] for c in cs if truth.get(c))
        ptot = sum(pop[c] for c in cs if pop.get(c))
        print(f"  구 {gk}: 동 {len(cs)}개, 지수 평균 {m:.3f} ({'통과' if ok1 else '실패'}) · 정답 ÷ (지수 × 인구) 배율 퍼짐 ±{spread:.1%} ({'통과: 배율 K 를 모르면 절대값이 안 나옴' if ok2 else '실패'})")
        if not ok1:
            bad.append(f"{gk} 지수 평균 {m:.3f}")
        if not ok2:
            bad.append(f"{gk} 배율 퍼짐 {spread}")
        if kmed:
            targets += [(f"{gk} K", kmed), (f"{gk} 1/K", 1 / kmed), (f"{gk} 유동 합", tot), (f"{gk} 유동 평균", tot / len(cs)),
                        (f"{gk} 유동 합÷인구 합", tot / ptot if ptot else None)]
# 3. 그 수들이 결과 어디에도 없는지
targets = [(n, v) for n, v in targets if v and abs(v) > 1e-9]
hits = []
for p in glob.glob(f"{H63}/output/**/*.csv", recursive=True) + glob.glob(f"{H63}/output/**/*.txt", recursive=True):
    txt = open(p, encoding="utf-8-sig", errors="replace").read()
    for tok in set(re.findall(r"-?\d+(?:\.\d+)?", txt.replace(",", ""))):
        x = float(tok)
        if abs(x) < 1e-9 or len(tok.replace("-", "").replace(".", "")) < 3:   # 두 자리 이하 숫자(작은 개수·비율)는 흔해서 뺌
            continue
        for n, v in targets:
            if abs(x - v) / abs(v) <= 0.01:
                hits.append((os.path.relpath(p, H63), tok, n, v))
for h in hits[:20]:
    print(f"  !! {h[0]}: {h[1]} ≈ {h[2]} ({h[3]:.4g})")
if hits:
    bad.append(f"결과 안에 배율·합계와 같은 수 {len(hits)}곳")
print(f"[결과 숫자 찾기] 대상 수 {len(targets)}개 (구마다 K·1/K·유동 합·평균·합÷인구 합) → 같은 수 {len(hits)}곳")
print("통과" if not bad else f"실패: {bad}")
sys.exit(1 if bad else 0)
