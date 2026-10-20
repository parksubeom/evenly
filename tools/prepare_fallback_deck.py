# -*- coding: utf-8 -*-
"""
tools/prepare_fallback_deck.py ─ [10/13] 대비책 판 기획서 데이터: 1차 방문(10/2) 반출 결과만으로 deck/data/results.json

[실행]  cd deck && npm run build:fallback      (= node py.js ../tools/prepare_fallback_deck.py && node build_v6.js --expect fallback)
[하는 일] [10/20] 반출(10/19)이 없을 때의 판: 반출 없이 미리 빌드와 같은 계산(prepare_deck_data: 10/20 현장 메모 + 공개 자료 계산,
        빈 반출 폴더 deck/data/_no_export)을 먼저 하고, 그 위에 1차 반출(10/2) 숫자(deck/first_visit_results.json)를 덧씌움.
        반출이 있어야 채워지는 칸은 build_v6.js 대비책 갈래가 빼고 배치를 맞춤 ("반영 예정" 같은 대체 문구를 쓰지 않음).
        실제 반출(results/raw_export)·리허설·가짜 폴더는 읽지 않음. 팀명·방문일이 비면 그대로 누락
[채우는 칸] 14장 제목 = HBI 1.3 이상 건물 비율 (1.3~1.8 + 1.8 이상), 16장 선정지 = 봉천 백분위 → "상위 (100 − 백분위)%".
        한계(v5 계산·모든 건물 방식·의료 = 약국만·관악 일대 11도엽)는 14·16장 출처 줄에
"""
import json, os, subprocess, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from evenly_common import visit_plan

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DECK = os.path.join(ROOT, "deck")


def main():
    fv_p = os.path.join(DECK, "first_visit_results.json")
    fv = json.load(open(fv_p, encoding="utf-8"))
    if fv.get("source") != "first_visit_export":
        raise SystemExit(f"!! {fv_p}: source 가 first_visit_export 가 아님 → 대비책 판은 1차 반출 결과만 씀")
    inp = json.load(open(os.path.join(DECK, "inputs.json"), encoding="utf-8"))
    # [10/20] 1) 반출 없이 미리 빌드와 같은 값 (메모 + 공개 계산). --no-export: 빈 폴더를 반출 자리로 쓰고 results/ 밖 결과도 읽지 않음
    r_ = subprocess.run([sys.executable, os.path.join(ROOT, "tools", "prepare_deck_data.py"), "--no-export", "--expect", "real",
                         "--memo", os.path.join(DECK, "inputs_memo_1020.json"), "--public", os.path.join(DECK, "public_calc", "public_calc.json")],
                        stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    if r_.returncode:
        print(r_.stdout.decode("utf-8", "replace")[-1500:])
        raise SystemExit("!! 반출 없는 값 만들기(prepare_deck_data) 실패")
    base_ = json.load(open(os.path.join(DECK, "data", "results.json"), encoding="utf-8"))
    F = dict(base_.get("fields") or {})

    def put(key, label, need, value, later=None, optional=False):
        F[key] = {"value": value, "label": label, "need": need}
        if later:
            F[key]["later"] = later
        if optional:
            F[key]["optional"] = True

    fvn = "deck/first_visit_results.json (docs/1차방문_반출결과.md)"
    put("team_name", "팀명", ["deck/inputs.json"], inp.get("team_name") or None)
    put("team_display", "팀 표시 (1·26장)", ["deck/inputs.json"], inp.get("team_display") or inp.get("team_name") or None)
    vrows_, vn_ = visit_plan(inp)                      # [10/14 v14] 13장 방문일 (prepare_deck_data 와 같은 키)
    tables_ = dict(base_.get("tables") or {})
    if vrows_:
        tables_["V6.13.visits"] = {"label": "안심구역 방문일·한 일 (13장)", "need": ["deck/inputs.json 의 visits"], "rows": vrows_}
    put("V6.13.n_visits", "안심구역 방문 일수 (visits 의 done, 예비 날 제외)", ["deck/inputs.json 의 visits (다녀온 날 done: true)"], f"{vn_}일" if vn_ else None)
    # [10/13] 대비책 판은 1차 반출(v5, 어르신 0.8m/s) 값 → 속도 0.8 과 그 출처 문구 (inputs.json elder_speed_source["0.8"])
    put("V6.speed", "어르신 평지 보행속도 (m/s)", [fvn], "0.8", optional=True)
    ss_ = inp.get("elder_speed_source")
    put("V6.16.speed_src", "어르신 평지 보행속도 0.8m/s 의 출처", ['deck/inputs.json 의 elder_speed_source["0.8"]'], (ss_.get("0.8") if isinstance(ss_, dict) else ss_) or None)   # [v6.3]
    put("V6.hb", "체감 부담 HBI 문턱", [], "1.3", optional=True)
    put("V6.rmin", "고립 위험 왕복 추가 분", [], "10", optional=True)
    put("V6.scope", "분석 범위(구)", [fvn], "관악구", optional=True)
    s13 = fv["share_hbi_13_18"] + fv["share_hbi_18_up"]
    put("V6.fb.share13", "HBI 1.3 이상 건물 비율 (1차: 1.3~1.8 + 1.8 이상)", [fvn], f"{s13 * 100:.0f}")
    put("V6.fb.limits", "1차 반출 값의 한계", [fvn],
        f"1차 반출(10/2) 값: {fv['code'].split(' (')[0]} 계산, {fv['area'].split(' (')[0]}(옆 구 일부 포함), 모든 건물을 집으로 본 방식, "
        f"의료 목적지는 약국만, 걸을 수 없는 길을 빼지 않음", optional=True)
    p = fv["bongcheon_site_percentile"]
    put("V6.16.site", "선정지 백분위 (1차)", [fvn], f"상위 {100 - p:.1f}%")
    put("V6.16.site_label", "선정지 줄 이름", [], "서울시 선정지 봉천동의 위치 (1차 반출: 관악 일대 격자 중)", optional=True)
    put("V6.fb.hbi_median", "1차 HBI 중앙값", [fvn], f"{fv['hbi_median']:.2f}", optional=True)
    put("V6.fb.share18", "1차 HBI 1.8 이상 비율", [fvn], f"{fv['share_hbi_18_up'] * 100:.1f}", optional=True)
    put("V6.fb.n_dong", "1차 행정동 수", [fvn], str(fv["n_dong"]), optional=True)
    put("V6.15.date", "현장실측 날짜", ["deck/inputs.json 의 survey_date"], inp.get("survey_date"), later="2026.10.__")
    images_ = dict(base_.get("images") or {})          # [10/21] 24장 화면 지도도 반출 없는 계산 그대로 (격자 없이 배경지도·이름·17장 후보 3곳)
    out = {"source": "fallback", "src": os.path.relpath(fv_p, ROOT), "bands": "mix", "fields": F, "images": images_, "tables": tables_}
    os.makedirs(os.path.join(DECK, "data"), exist_ok=True)
    json.dump(out, open(os.path.join(DECK, "data", "results.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"[fallback] {os.path.relpath(fv_p, ROOT)} → deck/data/results.json (값 {sum(1 for f in F.values() if f['value'] is not None)}/{len(F)}, "
          f"반출이 있어야 하는 칸은 build_v6.js 대비책 갈래가 뺌)")


if __name__ == "__main__":
    main()
