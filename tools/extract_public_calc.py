# -*- coding: utf-8 -*-
"""
tools/extract_public_calc.py ─ [10/20] 기획서 실제판의 (다) "공개 자료 보행망으로 계산 (같은 모델·같은 좌표)" 값을 한 파일로

[왜] 10/19 반출은 all 방식 01~05 뿐이고 10/20 의 09 는 봉천만이라, 후보 다섯 곳의 시설 효과·봉천 등시선은 안심구역 결과가 없음.
     같은 코드(v6.2 #ddc743)·같은 조건(0.8m/s, all 방식, 134줄 민감도만 고침)·같은 좌표로 공개 자료를 돌린 결과에서 그 값만 옮김
[실행]  python3 tools/extract_public_calc.py [--run gwanak_v62all08] [--modes-run gwanak_v62f]
          --run       : run_public_rehearsal --modes all --field-fix v62_1019 --hand-candidates --hand-modes all 의 결과 이름
          --modes-run : layer·all 두 방식이 다 있는 공개 대역 (주거만 vs 모든 건물 HBI 중앙값 비교, 0.8m/s)
[결과]  deck/public_calc/public_calc.json (출처·번들·조건·값), deck/public_calc/isochrone_봉천.gpkg (19장 그림 원본)
        결과 폴더의 공개 대역 표지(_source.txt)를 확인하고, 실제 반출(results/raw_export)은 읽지 않음
"""
import argparse, csv, glob, json, os, shutil, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools"))
from evenly_common import PUBLIC_REHEARSAL, source_of, num   # noqa: E402
import field_fix_v62 as FF                                   # noqa: E402

OUT = os.path.join(ROOT, "deck", "public_calc")
COLS = ["n_benefit", "n_benefit_any", "n_saved_30s", "n_saved_60s", "wheel_benefit", "wheel_cut_n", "wheel_cut_p50_m", "mean_saved_min", "rise_m", "pass_s"]


def rd(p):
    with open(p, encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", default="gwanak_v62all08")
    ap.add_argument("--modes-run", default="gwanak_v62f")
    a = ap.parse_args()
    base = os.path.join(ROOT, "results", "public_rehearsal", a.run)
    d = os.path.join(base, "all")
    if source_of(d) != PUBLIC_REHEARSAL and source_of(base) != PUBLIC_REHEARSAL:
        raise SystemExit(f"!! {d} 에 공개 대역 표지가 없습니다 → 공개 자료 계산 결과만 씀")
    rr = json.load(open(os.path.join(base, "run_result.json"), encoding="utf-8"))
    meta = {r["key"]: r["value"] for r in rd(os.path.join(d, "run_meta.csv"))}
    if (meta.get("rep_mode") or "") != "all" and os.path.basename(d) != "all":
        raise SystemExit(f"!! {d} 가 all 방식 결과가 아님")
    routes = rd(os.path.join(d, "validation_routes.csv"))
    vr = sorted(((num(r["net_m"]), num(r["flat_min"])) for r in routes if num(r.get("net_m")) and num(r.get("flat_min")) and num(r["flat_min"]) >= 3), reverse=True)
    spd = round(vr[0][0] / (vr[0][1] * 60) / 0.05) * 0.05 if vr else None
    if spd is None or abs(spd - 0.8) > 0.01:
        raise SystemExit(f"!! 공개 계산의 어르신 속도가 0.8m/s 가 아님 ({spd}) → 19일 조건(0.8)으로 다시")
    summ = rd(os.path.join(d, "intervention_summary.csv"))
    cands = {}
    for c in FF.candidates():
        rows = {r["target"]: {k: r.get(k, "") for k in COLS} for r in summ if r.get("facility") == c["name"]}
        if not rows:
            raise SystemExit(f"!! {c['name']} 줄이 09 결과에 없음 → 후보 손 입력·run_all --from 09 --modes all 확인")
        cands[c["name"]] = {"type": c["type"], "straight_m": round(c["straight_m"], 1), "targets": rows}
    bong = {r["target"]: {k: r.get(k, "") for k in COLS} for r in summ if r.get("facility", "").startswith("봉천")}
    os.makedirs(OUT, exist_ok=True)
    iso = sorted(glob.glob(os.path.join(d, "isochrone_*봉천*.gpkg")))
    iso_out = None
    if iso:
        iso_out = os.path.join(OUT, "isochrone_봉천.gpkg")
        shutil.copy2(iso[0], iso_out)
    # 주거만(layer) vs 모든 건물(all) HBI 중앙값 (약국, 경계 제외) — 두 방식이 다 있는 공개 대역
    med = {}
    for m in ("layer", "all"):
        p = os.path.join(ROOT, "results", "public_rehearsal", a.modes_run, m, "summary.csv")
        for r in rd(p) if os.path.exists(p) else []:
            if r["target"] == "pharmacy" and r["metric"] == "HBI 중앙값(경계 제외)":
                med[m] = num(r["value"])
    out = {"_source": "공개 자료 보행망으로 계산 (같은 모델·같은 좌표)",
           "_조건": "v6.2 #ddc743 번들 그대로 + config.py 134줄 민감도 0.8 (19일과 같음), 어르신 0.8m/s, all 방식, 후보1~5 손 입력 → run_all --from 09 --modes all",
           "_from": f"results/public_rehearsal/{a.run} (번들 {rr.get('bundle_file')} sha256 {str(rr.get('bundle_sha256'))[:16]}…)",
           "elder_speed": round(spd, 2), "mode": "all",
           "candidates": cands, "bongcheon_public": bong,
           "isochrone_gpkg": os.path.relpath(iso_out, ROOT) if iso_out else None,
           "hbi_median_by_mode": {"layer": med.get("layer"), "all": med.get("all"),
                                  "diff": round(abs(med["layer"] - med["all"]), 3) if len(med) == 2 else None,
                                  "_from": f"results/public_rehearsal/{a.modes_run} (공개 대역, 0.8m/s, 약국, 경계 제외)"}}
    json.dump(out, open(os.path.join(OUT, "public_calc.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"→ deck/public_calc/public_calc.json (후보 {len(cands)}곳, 목적지 {sorted(next(iter(cands.values()))['targets'])}, 등시선 {'있음' if iso_out else '없음'},"
          f" HBI 중앙값 layer {med.get('layer')} · all {med.get('all')})")


if __name__ == "__main__":
    main()
