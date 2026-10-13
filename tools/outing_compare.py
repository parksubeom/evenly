# -*- coding: utf-8 -*-
"""
tools/outing_compare.py ─ [안심구역 밖, v6.3] "언덕 부담이 큰 동의 어르신은 실제로 덜 나가는가?" — 반출된 동 단위 지수로 비교 그림

[실행]  node deck/py.js tools/outing_compare.py [--src results/raw_export] [--out results/outing]    (matplotlib 있는 QGIS Python)
[읽는 것] (대표 방식 폴더, run_meta.csv 의 is_rep_mode = yes. 모두 동 단위 지수·비율만 — 원값 없음)
  dong_hbi.csv                     : share_add<R>m (고립 위험 비율, R = run_meta 의 risk_min, 없으면 10)
  points_SKT_60대이상유동인구_dong.csv : index = 60세 이상 유동 ÷ 60세 이상 인구 (외출 지수, 10_points_join 지수 방식)
  join_KCB_60세이상_월200만원이하비율.csv : 60세 이상 중 월 200만원 이하 비율 (07)
  [10/13] --outing living: SKT 대신 공개 자료 data_public/living65_outing.csv (tools/prep_living_pop.py, 서울 생활인구 65세 이상,
          외출 지수 = 1 − 낮 10~17시 ÷ 새벽 3~5시, 관악구 동만). --outing auto(기본) = SKT 가 있으면 SKT, 없으면 생활인구. --weekday 면 평일 값
[하는 일]
  1. 세 표를 adm_cd 로 붙임 (외출 지수가 있는 동만)
  2. 부담 높음 / 낮음: 고립 위험 비율이 동 중앙값보다 큰 동 / 나머지 (중앙값이 0 이면 0 보다 큰 동 / 0 인 동)
  3. 두 묶음의 외출 지수 중앙값 차이와 순열 검정 p (10,000번, 시드 고정) — 전체, 그리고 KCB 저소득 비율 세 구간(삼분위) 안에서 따로
  4. 그림 두 장: outing_groups.png (두 묶음), outing_by_income.png (소득 구간별 두 묶음)
[결과] <out>/outing_compare.csv (동마다 adm_cd·동 이름·고립 위험 비율·외출 지수·저소득 비율·소득 구간·묶음),
       <out>/outing_summary.csv (묶음별 동 수·중앙값·차이·p), 그림 두 장
[해석] 상관 관찰이며 인과가 아님. 동 단위라 동 안의 차이는 보지 못함 (생태학적 오류). 동 수가 적으면 p 가 커짐
"""
import argparse, csv, os, sys
import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SKT = "SKT_60대이상유동인구"
KCB = "KCB_60세이상_월200만원이하비율"


def read(p):
    if not os.path.exists(p):
        return []
    with open(p, encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def num(v):
    try:
        return float(str(v).replace(",", "").strip())
    except (TypeError, ValueError):
        return np.nan


def rep_dir(src):
    for m in ("layer", "register", "gisbld", "all"):
        d = os.path.join(src, m)
        if any(r.get("key") == "is_rep_mode" and r.get("value") == "yes" for r in read(os.path.join(d, "run_meta.csv"))):
            return d
    return src


def perm_p(a, b, n=10000, seed=7):
    """중앙값 차이(a − b)의 양쪽 순열 검정 p"""
    a, b = np.asarray(a, float), np.asarray(b, float)
    if len(a) < 2 or len(b) < 2:
        return np.nan
    obs = abs(np.median(a) - np.median(b))
    x = np.r_[a, b]
    rng = np.random.default_rng(seed)
    cnt = 0
    for _ in range(n):
        rng.shuffle(x)
        cnt += abs(np.median(x[:len(a)]) - np.median(x[len(a):])) >= obs - 1e-12
    return (cnt + 1) / (n + 1)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", default=os.path.join(ROOT, "results", "raw_export"))
    ap.add_argument("--out", default=os.path.join(ROOT, "results", "outing"))
    ap.add_argument("--outing", choices=["auto", "skt", "living"], default="auto")
    ap.add_argument("--living", default=os.path.join(ROOT, "data_public", "living65_outing.csv"))
    ap.add_argument("--weekday", action="store_true", help="생활인구 평일 값 (outing_index_wd)")
    a = ap.parse_args()
    d = rep_dir(os.path.abspath(a.src))
    meta = {r["key"]: r["value"] for r in read(os.path.join(d, "run_meta.csv")) if r.get("key")}
    R = meta.get("risk_min") or "10"
    col = f"share_add{float(R):g}m".replace(".", "_")
    dong = {r["adm_cd"]: r for r in read(os.path.join(d, "dong_hbi.csv"))}
    skt = {r["adm_cd"]: num(r.get("index")) for r in read(os.path.join(d, f"points_{SKT}_dong.csv"))}
    if skt and all(not np.isfinite(v) for v in skt.values()):
        skt = {}
    src_lab, ylab = "SKT 60세 이상 (유동 ÷ 거주)", "외출 지수 (60세 이상 유동 ÷ 거주)"
    if a.outing == "living" or (a.outing == "auto" and not skt):
        col_l = "outing_index_wd" if a.weekday else "outing_index"
        lv = read(a.living)
        skt = {r["adm_cd"]: num(r.get(col_l)) for r in lv}
        ym = lv[0].get("base_ym", "") if lv else ""
        src_lab = f"서울 생활인구 {ym[:4]}.{ym[4:]} 65세 이상{' 평일' if a.weekday else ''} (1 − 낮 10~17시 ÷ 새벽 3~5시)"
        ylab = "외출 지수 (65세 이상, 1 - 낮 ÷ 새벽)"
        if not skt:
            raise SystemExit(f"!! {os.path.relpath(a.living, ROOT)} 가 없습니다 → python3 tools/prep_living_pop.py")
    if not skt:
        raise SystemExit(f"!! {os.path.relpath(d, ROOT)}/points_{SKT}_dong.csv 의 외출 지수(index)가 없습니다 → v6.3 10_points_join 의 지수 방식 결과가 필요 (공개 자료로는 --outing living)")
    print(f"외출 지수: {src_lab} · 고립 위험: {os.path.relpath(d, ROOT)}/dong_hbi.csv {col}")
    kcb = {r["adm_cd"]: num(r.get(KCB)) for r in read(os.path.join(d, f"join_{KCB}.csv"))}
    rows = []
    for cd, ix in skt.items():
        r = dong.get(cd)
        if r is None or not np.isfinite(ix) or not np.isfinite(num(r.get(col))):
            continue
        rows.append(dict(adm_cd=cd, adm_nm=r.get("adm_nm", ""), risk=num(r.get(col)), outing=ix, low_income=kcb.get(cd, np.nan)))
    if len(rows) < 6:
        raise SystemExit(f"!! 붙은 동이 {len(rows)}개뿐 (6개 이상 필요)")
    risk = np.array([r["risk"] for r in rows])
    med = float(np.median(risk))
    hi = risk > med if med > 0 else risk > 0
    for r, h in zip(rows, hi):
        r["group"] = "부담 높음" if h else "부담 낮음"
    li = np.array([r["low_income"] for r in rows])
    okk = np.isfinite(li)
    tiers = np.full(len(rows), "", object)
    if okk.sum() >= 6:
        q1, q2 = np.quantile(li[okk], [1 / 3, 2 / 3])
        tiers[okk] = np.where(li[okk] <= q1, "저소득 비율 낮음", np.where(li[okk] <= q2, "중간", "저소득 비율 높음"))
    for r, t in zip(rows, tiers):
        r["income_tier"] = t
    os.makedirs(a.out, exist_ok=True)
    with open(os.path.join(a.out, "outing_compare.csv"), "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["adm_cd", "adm_nm", "risk", "outing", "low_income", "income_tier", "group"])
        w.writeheader()
        w.writerows(rows)
    ox = np.array([r["outing"] for r in rows])
    summ = []

    def comp(label, m):
        A, B = ox[m & hi], ox[m & ~hi]
        p = perm_p(A, B)
        summ.append([label, len(A), len(B), round(float(np.median(A)), 3) if len(A) else "", round(float(np.median(B)), 3) if len(B) else "",
                     round(float(np.median(A) - np.median(B)), 3) if len(A) and len(B) else "", round(p, 3) if np.isfinite(p) else ""])
    comp("전체", np.ones(len(rows), bool))
    for t in ("저소득 비율 낮음", "중간", "저소득 비율 높음"):
        if (tiers == t).any():
            comp(t, tiers == t)
    with open(os.path.join(a.out, "outing_summary.csv"), "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(["# 외출 지수", src_lab])
        w.writerow(["묶음", "부담 높음 동 수", "부담 낮음 동 수", "부담 높음 외출 지수 중앙값", "부담 낮음 외출 지수 중앙값", "차이(높음 − 낮음)", "순열 검정 p"])
        w.writerows(summ)
    for s_ in summ:
        print(f"  {s_[0]}: 높음 {s_[1]}동 중앙값 {s_[3]} / 낮음 {s_[2]}동 중앙값 {s_[4]} → 차이 {s_[5]}, p = {s_[6]}")
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        names = [x.name for x in matplotlib.font_manager.fontManager.ttflist]
        for fnt in ["Apple SD Gothic Neo", "AppleGothic", "Malgun Gothic", "NanumGothic"]:
            if any(fnt in n for n in names):
                plt.rcParams["font.family"] = next(n for n in names if fnt in n)
                break
        plt.rcParams["axes.unicode_minus"] = False
        INK, ACC, MUT = "#1C2321", "#E4572E", "#8CB8A0"
        rng = np.random.default_rng(3)

        def strip(ax, groups, labels):
            for i, (g, c) in enumerate(zip(groups, [MUT, ACC] * 4)):
                if not len(g):
                    continue
                ax.scatter(i + rng.uniform(-0.12, 0.12, len(g)), g, s=18, color=c, alpha=0.8, edgecolor="none")
                ax.plot([i - 0.25, i + 0.25], [np.median(g)] * 2, color=INK, lw=2)
            ax.set_xticks(range(len(labels)))
            ax.set_xticklabels(labels, fontsize=10)
            for sp in ("top", "right"):
                ax.spines[sp].set_visible(False)
        fig, ax = plt.subplots(figsize=(4.6, 3.4), dpi=200)
        strip(ax, [ox[~hi], ox[hi]], [f"부담 낮음\n({(~hi).sum()}개 동)", f"부담 높음\n({hi.sum()}개 동)"])
        ax.set_ylabel(ylab, fontsize=9)
        ax.set_title(f"고립 위험(왕복 +{float(R):g}분) 비율로 나눈 두 묶음 · p = {summ[0][6]}", fontsize=9)
        fig.tight_layout()
        fig.savefig(os.path.join(a.out, "outing_groups.png"))
        plt.close(fig)
        ts = [t for t in ("저소득 비율 낮음", "중간", "저소득 비율 높음") if (tiers == t).any()]
        if ts:
            fig, axs = plt.subplots(1, len(ts), figsize=(2.2 * len(ts) + 0.6, 3.2), dpi=200, sharey=True)
            axs = np.atleast_1d(axs)
            for ax, t in zip(axs, ts):
                m = tiers == t
                strip(ax, [ox[m & ~hi], ox[m & hi]], [f"부담 낮음\n({(m & ~hi).sum()})", f"부담 높음\n({(m & hi).sum()})"])
                pv = next(s_[6] for s_ in summ if s_[0] == t)
                ax.set_title(f"{t}\np = {pv}", fontsize=8)
            axs[0].set_ylabel("외출 지수", fontsize=9)
            fig.suptitle("소득 구간(KCB) 안에서도 부담 높은 동이 덜 나가는가", fontsize=9)
            fig.tight_layout()
            fig.savefig(os.path.join(a.out, "outing_by_income.png"))
            plt.close(fig)
        print(f"→ {os.path.relpath(a.out, ROOT)}/outing_groups.png" + (", outing_by_income.png" if ts else " (KCB 없음: 소득 구간 그림 없음)"))
    except ImportError:
        print("!! matplotlib 없음 → 그림은 건너뜀 (node deck/py.js 로 QGIS Python 을 쓰면 됨)")
    print(f"→ {os.path.relpath(a.out, ROOT)}/outing_compare.csv ({len(rows)}개 동), outing_summary.csv · 상관 관찰이며 인과가 아님")


if __name__ == "__main__":
    main()
