# -*- coding: utf-8 -*-
"""
tools/make_candidates_csv.py ─ [대비책, v6.3 이 10/16 에 반입되지 못할 때] v6.2 번들로 후보 시설을 돌리기 위한 interventions_candidates.csv

[실행]  python3 tools/make_candidates_csv.py [--ends data_public/rehearsal/박수범/hbi6/work/layer/intervention_candidates_ends.csv]
                                             [--out deliverables/interventions_candidates.csv]
[하는 일] 공개 대역 리허설(공개 연속수치지형도·공개 지형, v6.3 09 후보 자동)이 찾은 후보 구간의 양 끝 경위도를
        v6.2 번들의 external/interventions.csv (git 2a3e193) 아래에 줄로 붙임. 이름 = "후보N (리허설)", status planned.
        → 메일로 이 파일 하나만 반입 → 안심구역에서 hbi6\\external\\interventions.csv 를 이 파일로 바꾸고 python run_all.py --from 09
        (v6.2 09 는 interventions.csv 만 읽고, 좌표가 찬 줄을 모두 시설로 계산함. 실제 수치지형도 길에 다시 붙이므로 끝점이 50m 넘게 떨어지면 경고)
[주의] 좌표는 공개 자료로 찾은 것이고 안심구역 자료에서 나온 것이 아님. 반출되는 것은 시설 이름별 수혜 건물 수·시간뿐 (v6.2 09 그대로)
"""
import argparse, csv, io, os, subprocess

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ends", default=os.path.join(ROOT, "data_public", "rehearsal", "박수범", "hbi6", "work", "layer", "intervention_candidates_ends.csv"))
    ap.add_argument("--base-rev", default="2a3e193", help="v6.2 반입 번들 커밋")
    ap.add_argument("--out", default=os.path.join(ROOT, "deliverables", "interventions_candidates.csv"))
    a = ap.parse_args()
    base = subprocess.run(["git", "-C", ROOT, "show", f"{a.base_rev}:analysis/hbi/external/interventions.csv"], capture_output=True, check=True).stdout
    txt = base.decode("utf-8-sig")
    rows = list(csv.reader(io.StringIO(txt)))
    head = rows[0]
    ends = list(csv.DictReader(open(a.ends, encoding="utf-8-sig")))
    if not ends:
        raise SystemExit(f"!! 후보 끝점이 없습니다: {a.ends} (v6.3 리허설 09 결과)")
    for e in ends:
        r = dict.fromkeys(head, "")
        r.update(name=f"{e['name']} (리허설)", type=e["type"], a_lon=e["a_lon"], a_lat=e["a_lat"], b_lon=e["b_lon"], b_lat=e["b_lat"], status="planned",
                 note=f"v6.3 후보 자동이 공개 대역 리허설에서 찾은 구간 (높이 차 {e['rise_m']}m · 수평 {e['straight_m']}m). a = 낮은 끝")
        rows.append([r[k] for k in head])
    os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
    with open(a.out, "w", encoding="utf-8-sig", newline="") as f:
        csv.writer(f, lineterminator="\r\n").writerows(rows)
    print(f"→ {os.path.relpath(a.out, ROOT)}: v6.2 interventions.csv {len(rows) - 1 - len(ends)}줄 + 후보 {len(ends)}줄 (UTF-8 BOM, 윈도 줄바꿈)")


if __name__ == "__main__":
    main()
