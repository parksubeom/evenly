# -*- coding: utf-8 -*-
"""
tools/field_fix_v62.py ─ [10/14 상황 변경] 센터가 v6.2(#ddc743)를 이미 적용 → 19일은 v6.2 + 현장 수정 몇 줄로 v6.3 에 가깝게

여기 한 곳에 적은 것을 세 군데가 같이 씀 (글자가 어긋나지 않게):
  - 19일 추가 수정 한 장 (tools/make_1019_fix_sheet.py → docs/19일_추가수정_v6.2.html·pdf)
  - 공개 대역 리허설 (tools/run_public_rehearsal.py --field-fix v62 --hand-candidates)
  - 기획서 준비 (tools/prepare_deck_data.py 가 v6.2 출력에서 후보 줄을 알아봄: HAND_NAMES)

[현장 수정] setup 뒤, check 전에 (메모장으로 연 뒤 '=' 오른쪽 글자만 바꾸고 저장)
  1. config.py 107번째 줄  ELDER_SPEED = 0.8 → 0.7  (경찰청 매뉴얼 2020.11.30 개정 교통약자 보행속도)
  2. config.py 134번째 줄  민감도 "보행속도 0.7m/s" → "보행속도 0.8m/s" (기본이 0.7 이 되니 개정 전 0.8 을 비교로. v6.3 과 같게)
  3. mapping.txt           extra_min_bands = 3,5,10 → 3,5,10,15  (15분 구간: 부록 3 문턱 비교. 고립 위험은 기획서가 10분으로 읽음)
[후보 손 입력] 본 분석(run_all --modes auto,all)과 실측(--from 04, 12·13·14) 뒤, external/interventions.csv 맨 끝에 다섯 줄
  → python run_all.py --from 09 --modes auto  (all 방식에는 후보를 넣지 않음: 방식끼리 빼서 몇 채가 드러나지 않게)
  후보 좌표 = deliverables/interventions_candidates.csv (v6.3 후보 자동이 공개 대역 리허설, 어르신 0.7m/s 에서 찾은 구간)

[실행]  python3 tools/field_fix_v62.py            → 고칠 줄·손 입력 줄·09 에 나와야 할 길이를 화면에
        python3 tools/field_fix_v62.py --apply <hbi6 폴더>   → 리허설 폴더에 1~3 을 적용 (줄 글자가 다르면 멈춤)
"""
import argparse, csv, math, os, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools"))
from evenly_common import to5186   # noqa: E402

BUNDLE = "v6.2 #ddc743"
# (파일, 줄 번호 또는 None = 키로 찾음, 고치기 전 글자, 고친 뒤 글자, 화면에서 바꿀 부분 (전, 후), 이유)
EDITS = [
    {"file": "config.py", "line": 107,
     "old": "ELDER_SPEED = 0.8        # 고령자 평지 보행속도 (m/초). 성인은 약 1.1~1.3",
     "new": "ELDER_SPEED = 0.7        # 고령자 평지 보행속도 (m/초). 성인은 약 1.1~1.3",
     "part": ("0.8", "0.7"), "why": "어르신 평지 보행속도 0.7m/s (경찰청 교통신호기 설치·관리 매뉴얼 2020.11.30 개정)"},
    {"file": "config.py", "line": 134,
     "old": '    "보행속도 0.7m/s": {"ELDER_SPEED": 0.7},',
     "new": '    "보행속도 0.8m/s": {"ELDER_SPEED": 0.8},',
     "part": ('"보행속도 0.7m/s": {"ELDER_SPEED": 0.7}', '"보행속도 0.8m/s": {"ELDER_SPEED": 0.8}'),
     "why": "민감도 비교를 개정 전 0.8m/s 로 (기본이 0.7 이므로, 0.7 을 그대로 두면 같은 계산을 한 번 더 함)"},
    {"file": "mapping.txt", "line": None, "key": "extra_min_bands",
     "old": "extra_min_bands = 3,5,10", "new": "extra_min_bands = 3,5,10,15",
     "part": ("3,5,10", "3,5,10,15"), "why": "15분 구간을 더 냄 (부록 3: 5·10·15분 상위 3개 동 비교). 고립 위험 문턱은 10분 그대로"},
]
CAND_CSV = os.path.join(ROOT, "deliverables", "interventions_candidates.csv")
HAND_FIELDS = ["name", "type", "a_lon", "a_lat", "b_lon", "b_lat", "wait_s", "speed", "status"]   # note 칸은 치지 않음


def candidates():
    """후보 다섯 줄: 손으로 칠 이름(후보1~5)과 좌표·종류, 리허설에서 잰 높이 차·수평 길이 (note 의 괄호), 좌표로 계산한 a·b 직선 길이"""
    out = []
    for r in csv.DictReader(open(CAND_CSV, encoding="utf-8-sig")):
        if not r["name"].startswith("후보"):
            continue
        nm = r["name"].split()[0]                                   # "후보1 (리허설)" → "후보1"
        ax, ay = to5186(float(r["a_lon"]), float(r["a_lat"]))
        bx, by = to5186(float(r["b_lon"]), float(r["b_lat"]))
        import re
        m = re.search(r"높이 차 ([0-9.]+)m · 수평 ([0-9.]+)m", r.get("note") or "")
        out.append({"name": nm, "type": r["type"], "a_lon": r["a_lon"], "a_lat": r["a_lat"], "b_lon": r["b_lon"], "b_lat": r["b_lat"],
                    "straight_m": math.hypot(bx - ax, by - ay), "rise_reh": float(m.group(1)) if m else None,
                    "line": ",".join([nm, r["type"], r["a_lon"], r["a_lat"], r["b_lon"], r["b_lat"], "", "", "planned"])})
    return out


HAND_NAMES = [f"후보{i}" for i in range(1, 6)]
# 후보마다 v6.3 후보 자동이 고른 출발 격자 가운데 (EPSG:5186, 250m): 그 격자의 고립 위험 집들이 지나는 경사 구간에 시설을 놓았음 (시설은 격자 밖일 수 있음).
#   기획서 17장 '고립 위험 주거 건물'·동·기존 시설 거리를 v6.2 결과에서 이 격자로 읽음. 출처: results/public_rehearsal/gwanak_v63/layer/intervention_candidates.csv (0.7m/s)
CAND_CELLS = {"후보1": (194875.0, 543375.0), "후보2": (194875.0, 543625.0), "후보3": (194875.0, 541625.0),
              "후보4": (193625.0, 541875.0), "후보5": (195875.0, 543375.0)}


def apply(hbi):
    """리허설 폴더(hbi6)에 EDITS 를 그대로 (메모장으로 '=' 오른쪽만 바꾼 것과 같게). 고치기 전 글자가 다르면 멈춤"""
    for e in EDITS:
        p = os.path.join(hbi, e["file"])
        raw = open(p, "rb").read()
        bom = raw.startswith(b"\xef\xbb\xbf")
        txt = raw.decode("utf-8-sig")
        nl = "\r\n" if "\r\n" in txt else "\n"
        lines = txt.split(nl)
        if e["line"]:
            i = e["line"] - 1
            if lines[i] != e["old"]:
                raise SystemExit(f"!! {e['file']} {e['line']}번째 줄이 예상과 다름:\n   있음: {lines[i]!r}\n   예상: {e['old']!r}")
            lines[i] = e["new"]
        else:
            hit = [i for i, l in enumerate(lines) if l.split("#")[0].strip().replace(" ", "") == e["old"].replace(" ", "")]
            if len(hit) != 1:
                raise SystemExit(f"!! {e['file']} 에 '{e['old']}' 줄이 {len(hit)}개")
            i = hit[0]
            lines[i] = lines[i].replace(e["part"][0], e["part"][1], 1)
        open(p, "wb").write((b"\xef\xbb\xbf" if bom else b"") + nl.join(lines).encode("utf-8"))
        print(f"고침: {e['file']} {i + 1}번째 줄 → {lines[i][:60]}")


def append_candidates(hbi):
    """external/interventions.csv 맨 끝에 손 입력 다섯 줄 (메모장에서 맨 끝 줄 뒤 Enter 하고 치는 것과 같게)"""
    p = os.path.join(hbi, "external", "interventions.csv")
    raw = open(p, "rb").read()
    txt = raw.decode("utf-8-sig")
    nl = "\r\n" if "\r\n" in txt else "\n"
    if not txt.endswith(nl):
        txt += nl
    txt += nl.join(c["line"] for c in candidates()) + nl
    open(p, "wb").write((b"\xef\xbb\xbf" if raw.startswith(b"\xef\xbb\xbf") else b"") + txt.encode("utf-8"))
    print(f"후보 손 입력: {p} 에 {len(candidates())}줄")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", metavar="hbi6 폴더")
    ap.add_argument("--candidates", metavar="hbi6 폴더", help="external/interventions.csv 에 손 입력 줄만")
    a = ap.parse_args()
    if a.apply:
        apply(a.apply)
        return
    if a.candidates:
        append_candidates(a.candidates)
        return
    for e in EDITS:
        print(f"{e['file']} {e['line'] or '(' + e['key'] + ' 줄)'}: {e['old']}  →  {e['new']}")
    for c in candidates():
        print(f"{c['line']}    # 직선 {c['straight_m']:.1f}m, 리허설 높이 차 {c['rise_reh']}m")


if __name__ == "__main__":
    main()
