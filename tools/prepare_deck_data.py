# -*- coding: utf-8 -*-
"""
tools/prepare_deck_data.py ─ 반출 결과 파일 → 기획서에 넣을 값(deck/data/results.json)과 그림(deck/img/results/*.png)

[실행]  python3 tools/prepare_deck_data.py                          (기본: results/raw_export, 실제 결과)
        python3 tools/prepare_deck_data.py --src results/fake_export  (가짜 결과로 시험)
[결과]
  deck/data/results.json   슬라이드별 값. 숫자 서식(%, 콤마, 소수점)은 여기서 확정합니다.
                           값이 없으면 null → build_deck.js 가 빈칸(___)·점선 박스를 그대로 두고 누락 목록에 적습니다.
  deck/data/missing.txt    누락 목록 초안 (build_deck.js 가 슬라이드 번호를 붙여 다시 씁니다)
  deck/img/results/*.png   결과 지도(목적지별), 순위 역전 산점도, 선정지 백분위 막대, SKT 결합 산점도(있을 때)
[19장]  외출 지수 = SKT 60세 이상 유동인구(행정동 합) ÷ 60세 이상 거주인구. SKT 는 v5 10(points_SKT_*_dong.csv) 우선, 없으면 v4 07(join_SKT_*.csv).
        분모는 결과 폴더의 pop60.csv(가짜 시험) 또는 data_public/pop60.csv (tools/prep_elderly_pop.py --min-age 60).
        KCB 중첩 방향은 KCB_HIGH_IS_POOR 한 줄. 보조 근거는 11(legal_summary.csv) 우선, 없으면 10 개수 모드 점 자료
[원칙]  값을 지어내지 않습니다. 파일이 없거나 값이 비어 있으면 null 로 두고 "필요한 파일"을 적습니다.
        그림은 matplotlib 이 필요합니다. deck 의 npm 스크립트는 deck/py.js 로 matplotlib 이 있는 Python(EVENLY_PY → QGIS → python3)을 고름.
        --expect real 에서 matplotlib 이 없으면 멈춤 (그림 빠진 제출본 방지). 가짜 빌드는 경고만 하고 그림을 누락으로 처리.
"""
import argparse, datetime, json, math, os, re, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from evenly_common import (ROOT, TARGET_GU, TARGET_LABEL, FAKE_MARKER, RAW_EXPORT, is_fake_dir, load_dongs, dong_of, read_csv, num, truthy)

HI, LO = 1.8, 1.3
# 19장 KCB 중첩 방향. v5 기본 KCB 값 "KCB_60세이상_월200만원이하비율" = C1~C3 인원 ÷ C1~C22 인원
#   (KCB_데이터정의서.xlsx: C1_CNT~C22_CNT 는 월 소득 구간별 인원, C1~C3 가 월 200만원 이하) → 값이 높을수록 저소득
KCB_HIGH_IS_POOR = True
KCB_EXPECT = "월200만원이하비율"   # KCB 값 이름에 이 글자가 없으면 방향을 모르는 값으로 보고 중첩 수를 비움 (v4 "KCB_소득" 은 금액)
DECK = os.path.join(ROOT, "deck")
OUT_JSON = os.path.join(DECK, "data", "results.json")
OUT_MISSING = os.path.join(DECK, "data", "missing.txt")
IMG_DIR = os.path.join(DECK, "img", "results")
COLORS = ["#7FA88E", "#F2D16B", "#E8743B", "#B23A2A"]
SITE_SHORT = [("중곡", "광진구 중곡동"), ("화곡", "강서구 화곡동"), ("봉천", "관악구 봉천동"), ("숭인", "종로구 숭인동"), ("신당", "중구 신당동")]
WEEKDAY = "월화수목금토일"



# ── 서식 ────────────────────────────────────────────────────────
def f_int(v):
    return None if v is None else f"{round(v):,}"


def f_pct(v, d=1):
    return None if v is None else f"{v * 100:.{d}f}%"


def f_num(v, d=2):
    return None if v is None else f"{v:.{d}f}"


def f_about(v):
    """큰 수 → '약 1.2만' 식이 아니라 반올림 콤마 (지어낸 정밀도 방지: 세 자리 유효숫자)"""
    if v is None:
        return None
    if v >= 1000:
        mag = 10 ** (int(math.log10(v)) - 2)
        v = round(v / mag) * mag
    return f"{round(v):,}"


# ── p-value (t 분포, 표준 라이브러리만) ───────────────────────────
def _betacf(a, b, x):
    qab, qap, qam = a + b, a + 1, a - 1
    c, d = 1.0, 1 - qab * x / qap
    d = 1 / (d if abs(d) > 1e-30 else 1e-30)
    h = d
    for m in range(1, 300):
        m2 = 2 * m
        aa = m * (b - m) * x / ((qam + m2) * (a + m2))
        d = 1 + aa * d; d = 1 / (d if abs(d) > 1e-30 else 1e-30)
        c = 1 + aa / c if abs(c) > 1e-30 else 1e30
        h *= d * c
        aa = -(a + m) * (qab + m) * x / ((a + m2) * (qap + m2))
        d = 1 + aa * d; d = 1 / (d if abs(d) > 1e-30 else 1e-30)
        c = 1 + aa / c if abs(c) > 1e-30 else 1e30
        de = d * c
        h *= de
        if abs(de - 1) < 1e-12:
            break
    return h


def betainc(a, b, x):
    if x <= 0 or x >= 1:
        return 0.0 if x <= 0 else 1.0
    bt = math.exp(math.lgamma(a + b) - math.lgamma(a) - math.lgamma(b) + a * math.log(x) + b * math.log(1 - x))
    return bt * _betacf(a, b, x) / a if x < (a + 1) / (a + b + 2) else 1 - bt * _betacf(b, a, 1 - x) / b


def corr_p(r, n):
    """피어슨 r 의 양측 p (H0: r=0)"""
    if r is None or n is None or n < 3 or abs(r) >= 1:
        return None
    df = n - 2
    t2 = r * r * df / (1 - r * r)
    return betainc(df / 2, 0.5, df / (df + t2))


def pearson(xs, ys):
    n = len(xs)
    if n < 3:
        return None
    mx, my = sum(xs) / n, sum(ys) / n
    sxy = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    sxx = sum((x - mx) ** 2 for x in xs)
    syy = sum((y - my) ** 2 for y in ys)
    return sxy / math.sqrt(sxx * syy) if sxx > 0 and syy > 0 else None


def ranks(xs):
    """순위 (같은 값은 평균 순위)"""
    o = sorted(range(len(xs)), key=lambda i: xs[i])
    rk = [0.0] * len(xs)
    i = 0
    while i < len(o):
        j = i
        while j + 1 < len(o) and xs[o[j + 1]] == xs[o[i]]:
            j += 1
        for t in range(i, j + 1):
            rk[o[t]] = (i + j) / 2 + 1
        i = j + 1
    return rk


def spearman(xs, ys):
    """스피어만 ρ = 순위의 피어슨 r. p 는 corr_p(ρ, n) 로 t 분포 근사"""
    return pearson(ranks(xs), ranks(ys))


# ── 결과 모음 ───────────────────────────────────────────────────
class Box:
    def __init__(self):
        self.fields, self.images, self.tables = {}, {}, {}

    def put(self, key, label, need, value):
        """value 가 None 이면 누락. need = 필요한 파일 목록"""
        self.fields[key] = {"value": value, "label": label, "need": need}

    def img(self, key, label, need, path):
        self.images[key] = {"path": os.path.relpath(path, DECK).replace(os.sep, "/") if path else None, "label": label, "need": need}

    def table(self, key, label, need, rows):
        self.tables[key] = {"rows": rows, "label": label, "need": need}

    def missing(self):
        out = []
        for kind in (self.fields, self.images, self.tables):
            for k, v in kind.items():
                if v.get("optional"):
                    continue
                if v.get("value", v.get("path", v.get("rows"))) in (None, []):
                    out.append({"key": k, "label": v["label"], "need": v["need"]})
        return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", default=os.path.join(ROOT, "results", "raw_export"))
    ap.add_argument("--expect", choices=["real", "fake"], help="build:real 은 real: 가짜 표지가 있으면 멈춤")
    a = ap.parse_args()
    src = os.path.abspath(a.src)
    if not os.path.isdir(src):
        raise SystemExit(f"결과 폴더가 없습니다: {src}")
    # 출처 판정: 가짜 표지(_source.txt=fake 또는 _FAKE_DATA_README.txt)가 있으면 fake.
    #   real 은 "가짜 표지가 없고, 폴더가 results/raw_export" 일 때만 (실제 반출 파일에는 표지가 없음)
    fake = is_fake_dir(src) or os.path.basename(src) == "fake_export"
    is_raw = os.path.abspath(src) == os.path.abspath(RAW_EXPORT)
    if a.expect == "real" and fake:
        raise SystemExit(f"!! {os.path.relpath(src, ROOT)} 에 가짜 표지(_source.txt=fake)가 있습니다 → 실제 기획서를 만들지 않습니다. 폴더 내용을 확인하세요")
    if not fake and not is_raw:
        raise SystemExit(f"!! 가짜 표지가 없는데 폴더가 results/raw_export 가 아닙니다: {os.path.relpath(src, ROOT)}\n"
                         "   실제 결과는 results/raw_export 에서만 빌드합니다. 시험이면 make_fake_results.py 로 만든 폴더를 쓰세요")
    if a.expect == "fake" and not fake:
        raise SystemExit("!! --expect fake 인데 가짜 표지가 없습니다")
    source = "fake" if fake else "real"
    try:                                              # 그림(지도·차트)용. 실제 빌드에서 없으면 그림 빠진 제출본이 조용히 나오므로 멈춤
        import matplotlib  # noqa: F401
    except ImportError:
        if a.expect == "real":
            raise SystemExit(f"!! matplotlib 이 없는 Python 입니다 ({sys.executable}) → 실제 기획서를 만들지 않습니다.\n"
                             "   deck 에서 npm run build:real 로 실행하면 deck/py.js 가 QGIS Python 을 고릅니다 (또는 EVENLY_PY=<matplotlib 있는 python>)")
        print(f"!! matplotlib 없음 ({sys.executable}) → 그림은 누락으로 처리하고 계속 (가짜 빌드라 경고만)")
    S = lambda n: os.path.join(src, n)
    R = lambda n: read_csv(S(n))
    B = Box()
    os.makedirs(IMG_DIR, exist_ok=True)
    for f in os.listdir(IMG_DIR):                     # 지난 실행의 그림이 남아 섞이지 않도록
        if f.endswith(".png"):
            os.remove(os.path.join(IMG_DIR, f))

    # ── 입력 파일 ──
    summary = R("summary.csv") or []
    sm = {}
    for r in summary:
        sm.setdefault(r["target"], {})[r["metric"].strip()] = num(r["value"])
    grid = R("grid_hbi.csv") or []
    abl = {(r["scenario"].strip(), r["metric"].strip()): num(r["value"]) for r in (R("validation_ablation.csv") or [])}
    targets = [t for t in ["medical", "bus", "elderly", "station", "station_ev", "pharmacy"] if t in sm or any(g["target"] == t for g in grid)]
    T0 = "medical" if "medical" in targets else (targets[0] if targets else "medical")
    m0 = sm.get(T0, {})

    # ── 기획서 입력값 (팀명·방문일) ──
    inp_path = S("deck_inputs.json") if fake and os.path.exists(S("deck_inputs.json")) else os.path.join(DECK, "inputs.json")
    inp = json.load(open(inp_path, encoding="utf-8")) if os.path.exists(inp_path) else {}
    inp_rel = os.path.relpath(inp_path, ROOT)
    B.put("team_name", "팀명", [inp_rel], inp.get("team_name") or None)
    dates = (inp.get("visit_dates") or []) + [None] * 5
    for i in range(5):
        d = dates[i]
        v = None
        if d:
            try:
                dt = datetime.date.fromisoformat(str(d))
                v = f"{dt:%Y.%m.%d} ({WEEKDAY[dt.weekday()]})"
            except ValueError:
                v = str(d)
        B.put(f"SAFE.day{i + 1}", f"안심구역 {i + 1}일차 방문일", [inp_rel], v)

    # ── 16장 결과 ① ──
    need_s = ["summary.csv"]
    hi_n = m0.get(f"HBI {HI} 이상 건물 수")
    hi_sh = m0.get(f"HBI {HI} 이상 비율")
    n_all = m0.get("분석 건물 수")
    B.put("RES1.target", "기준 목적지", need_s, TARGET_LABEL.get(T0) if m0 else None)
    B.put("RES1.n_bld", "분석 주거 건물 수", need_s, f_int(n_all))
    B.put("RES1.high_n", f"HBI {HI} 이상 건물 수", need_s, f_int(hi_n))
    B.put("RES1.high_share", f"HBI {HI} 이상 비율", need_s, f_pct(hi_sh))
    # 경계 500m 포함 여부가 v4/v5 에서 다른 세 지표: v5 "(경계 제외)" 이름을 우선, v4 이름뿐이면 발표자 노트에만 (본문 금지)
    def edge_metric(key, label, v5, v4, d):
        if v5 in m0:
            v, scope = m0[v5], "v5"
        elif v4 in m0:
            v, scope = m0[v4], "v4"
        else:
            v, scope = None, None
        B.fields[key] = {"value": f_num(v, d), "label": label, "need": need_s, "optional": True, "scope": scope}
    edge_metric("RES1.median", "HBI 중앙값", "HBI 중앙값(경계 제외)", "HBI 중앙값", 2)
    edge_metric("RES1.home_ratio", "귀갓길 편도 배수 중앙값", "귀갓길(목적지→집) 편도 배수 중앙값(경계 제외)", "귀갓길(목적지→집) 편도 배수 중앙값", 2)
    edge_metric("RES1.elder_rt", "고령자 왕복 중앙값(분)", "고령자 왕복 중앙값(분, 경계 제외)", "고령자 왕복 중앙값(분)", 1)
    ev = sm.get("station_ev", {})
    B.fields["RES1.wheel_ev"] = {"value": f_pct(ev.get("휠체어 도달불가 비율")), "label": "휠체어 도달불가 비율(엘리베이터 역 기준)", "need": need_s, "optional": True}
    k_good = ("DEM 제외(평지 가정)", "HBI 1.8 이상 건물 중 평지 기준 소요시간이 중앙값 이하('양호')인 비율")
    good = abl.get(k_good)
    B.put("RES1.inverted_n", "평지 기준 '양호' → 경사 반영 '취약' 건물 수", ["summary.csv", "validation_ablation.csv"],
          f_about(hi_n * good) if hi_n is not None and good is not None else None)
    B.put("RES1.inverted_share", "HBI 1.8 이상 중 평지 기준 '양호' 비율", ["validation_ablation.csv"], f_pct(good, 0))
    B.put("RES1.insight", "인사이트 한 줄", ["validation_ablation.csv"],
          f"고립 위험 집의 {f_pct(good, 0)}는 평지 기준으로 '가까운 동네'였습니다" if good is not None else None)
    # 고령인구 추정: 밖에서 만든 dong_hbi_with_elderly.csv 우선, 없으면 dong_hbi.csv 의 추정 열(안심구역 안에서 인구파일을 넣은 경우)
    ew = R("dong_hbi_with_elderly.csv")
    eld_total, eld_src = None, None
    for fn, rows in [("dong_hbi_with_elderly.csv", ew), ("dong_hbi.csv", R("dong_hbi.csv"))]:
        vals = [num(r.get("elderly_in_high_est")) for r in (rows or [])]
        vals = [v for v in vals if v is not None]
        if vals:
            eld_total, eld_src = sum(vals), fn
            break
    B.put("RES1.elderly", f"HBI {HI} 이상 건물 거주 고령인구 추정", ["dong_hbi_with_elderly.csv (tools/outside_elderly.py)"],
          f_about(eld_total))
    B.put("RES1.elderly_src", "고령인구 추정 출처 파일", ["dong_hbi_with_elderly.csv"], eld_src)
    ym = sorted({r.get("base_ym", "") for r in (ew or []) if r.get("base_ym")})
    B.fields["RES1.elderly_ym"] = {"value": ",".join(ym) or None, "label": "고령인구 기준연월", "need": ["dong_hbi_with_elderly.csv 의 base_ym 열 (tools/outside_elderly.py)"], "optional": True}
    ps = {r["metric"].strip(): num(r["value"]) for r in (R("parcel_summary.csv") or [])}
    B.put("RES1.parcel_share", "국토정보필지(지목 '대') HBI 1.8 이상 비율", ["parcel_summary.csv"], f_pct(ps.get("'대' 필지 HBI 1.8 이상 비율")))
    B.put("RES1.parcel_n", "HBI 산출 필지 수", ["parcel_summary.csv"], f_int(ps.get("HBI 산출 필지 수")))
    # 목적지별 한 줄 비교 (지도 아래 작은 표)
    B.table("RES1.by_target", "목적지별 HBI 1.8 이상 비율", need_s,
            [[TARGET_LABEL.get(t, t), f_pct(sm[t].get(f"HBI {HI} 이상 비율")), f_num(sm[t].get("HBI 중앙값"))] for t in targets if t in sm])

    # ── 17장 검증 ──
    vs = R("validation_sites.csv") or []
    site_rows = []
    for key, label in SITE_SHORT:
        r = next((x for x in vs if key in x.get("name", "")), None)
        circle = bool(r) and num(r.get("percentile_circle")) is not None     # v5: 같은 반경 원 평균끼리 비교
        pct = (num(r.get("percentile_circle")) if circle else num(r.get("percentile"))) if r else None
        t10 = r.get("top10_circle") if circle else (r.get("top10") if r else None)
        site_rows.append({"name": label, "percentile": pct, "top_text": f"상위 {max(0.1, (1 - pct) * 100):.1f}%" if pct is not None else None,
                          "top10": ("포함" if truthy(t10) else "미포함") if r and pct is not None else None, "mode": "circle" if circle else "grid",
                          "hbi": f_num(num(r.get("hbi_mean"))) if r else None})
    B.table("VALID.sites", "선정지 5곳 백분위·상위10% 여부", ["validation_sites.csv"], site_rows if vs else [])
    B.fields["VALID.pct_mode"] = {"value": ("circle" if any(x["mode"] == "circle" for x in site_rows) else "grid") if vs else None,
                                  "label": "선정지 백분위 비교 방식", "need": ["validation_sites.csv"], "optional": True}
    n_top = sum(1 for s in site_rows if s["top10"] == "포함")
    B.put("VALID.top10_count", "상위 10% 안에 든 선정지 수", ["validation_sites.csv"], f"{n_top}/5" if vs else None)
    routes = R("validation_routes.csv") or []
    dh = next((r for r in routes if "대현산" in r.get("name", "")), None)
    B.put("VALID.wheel_m", "대현산배수지공원 휠체어 경로 길이", ["validation_routes.csv"], f"{round(num(dh['wheel_path_m'])):,}m" if dh and num(dh.get("wheel_path_m")) else None)
    B.put("VALID.net_m", "대현산배수지공원 보행 최단거리", ["validation_routes.csv"], f"{round(num(dh['net_m'])):,}m" if dh and num(dh.get("net_m")) else None)
    meas = [(r["name"], num(r.get("adult_min")), num(r.get("measured_min"))) for r in routes]
    meas = [m for m in meas if m[1] is not None and m[2] is not None]
    r_meas = pearson([m[1] for m in meas], [m[2] for m in meas]) if len(meas) >= 3 else None
    vm = (R("validation_measured.csv") or [None])[0]            # v5: 04 가 r 을 파일로 저장
    if vm and num(vm.get("r_adult_pred_vs_measured")) is not None:
        r_meas = num(vm["r_adult_pred_vs_measured"])
    B.put("VALID.meas_n", "현장 실측 경로 수", ["validation_routes.csv (measured_min)"],
          (f_int(num(vm["n"])) if vm and num(vm.get("n")) else (str(len(meas)) if meas else None)))
    B.put("VALID.meas_r", "실측 vs 예측(성인 1.1m/s) 상관계수 r", ["validation_routes.csv (measured_min 3개 이상)"], f_num(r_meas))
    B.table("VALID.meas_rows", "실측 경로별 비교", ["validation_routes.csv (measured_min)"],
            [[n, f"{p:.1f}분", f"{m:.1f}분"] for n, p, m in meas])
    nc = R("validation_new_candidates.csv")
    B.put("VALID.new_n", "선정지보다 HBI 높은 비선정 격자 수", ["validation_new_candidates.csv"],
          None if nc is None else (f"{len(nc)}곳 이상" if len(nc) >= 30 else f"{len(nc)}곳"))

    # ── 18장 기여도 ──
    B.put("ABL.dem_top10", "DEM 제외 시 상위10% 취약 건물 누락 비율", ["validation_ablation.csv"],
          f_pct(abl.get(("DEM 제외(평지 가정)", "경사 반영 상위10% 취약건물 중 평지 기준으로는 상위10%가 아닌 비율")), 0))
    B.put("ABL.rank_corr", "경사 반영 vs 평지 순위상관", ["validation_ablation.csv"],
          f_num(abl.get(("DEM 제외(평지 가정)", "경사 반영 vs 평지 소요시간 순위상관(Spearman)"))))
    B.put("ABL.stairs", "계단 제외 시 휠체어 시간 과소추정", ["validation_ablation.csv"],
          f_pct(abl.get(("계단 레이어 제외", "계단을 통행가능으로 잘못 가정할 때 휠체어 시간 과소추정 비율(평균)")), 0))
    B.put("ABL.wheel_unreach", "휠체어 도달불가 건물 비율", ["validation_ablation.csv"],
          f_pct(abl.get(("계단 레이어 제외", "휠체어 도달불가 건물 비율(계단 반영 시)"))))
    k_hid = next((k for k in abl if k[1].startswith("HBI 1.8 이상 건물 중 평균이 1.3 미만인 격자")), None)
    B.put("ABL.grid_hidden", "500m 격자 집계 시 가려지는 고위험 건물 비율", ["validation_ablation.csv"], f_pct(abl.get(k_hid), 0) if k_hid else None)
    dem1 = abl.get(("DEM 5m vs 1m", "HBI 순위상관(Spearman)"))
    B.fields["ABL.dem1m"] = {"value": f_num(dem1), "label": "DEM 5m vs 1m 순위상관", "need": ["validation_ablation.csv"], "optional": True}

    # ── 밖 도구 결과 (있을 때만, 없으면 표시 안 함) ──
    #   가짜 결과는 <src> 안에서만, 실제 결과는 <src> → results/ 순서로 찾음 (가짜가 실제 기획서에 섞이지 않도록)
    def opt_file(rel):
        for base in ([src] if fake else [src, os.path.join(ROOT, "results")]):
            pth = os.path.join(base, rel)
            if os.path.exists(pth):
                return pth
        return None
    optional = lambda key, label, need, value: B.fields.__setitem__(key, {"value": value, "label": label, "need": need, "optional": True})
    cp = opt_file(os.path.join("public_baseline", "compare_station.csv"))
    cmpd = {r["metric"].strip(): r["value"] for r in (read_csv(cp) or [])} if cp else {}
    if cp and not fake:
        # 가드: 실제 빌드에서는 "실제 LX 결과와 비교한" compare 만 받음 (public_baseline.py 가 lx_grid 출처를 기록)
        prov = (cmpd.get("lx_grid 출처") or "").strip()
        if prov != "real":
            raise SystemExit(f"!! {os.path.relpath(cp, ROOT)} 는 lx_grid 출처가 '{prov or '기록 없음'}' 입니다 (입력: {cmpd.get('lx_grid 입력', '-')}).\n"
                             "   가짜 결과와 비교한 파일일 수 있어 실제 기획서에 넣지 않습니다. 반출 grid_hbi.csv 로 public_baseline.py 를 다시 돌리거나 이 파일을 지우세요.")
    rho_pub = num(cmpd.get("순위상관(스피어만, LX vs 공개)"))
    miss_pub = num(cmpd.get("그중 공개데이터로 1.3 미만(놓침) 비율"))
    optional("ABL.pub_rho", "공개데이터 대조군 순위상관", ["results/public_baseline/compare_station.csv"], f_num(rho_pub))
    optional("ABL.pub_miss", "공개데이터로 놓치는 LX 1.3 이상 격자 비율", ["results/public_baseline/compare_station.csv"], f_pct(miss_pub, 0))
    optional("ABL.pub_note", "공개데이터 대조군 비고", ["results/public_baseline/compare_station.csv"], cmpd.get("비고") or None)
    optional("ABL.pub_n", "공통 격자 수", ["results/public_baseline/compare_station.csv"], cmpd.get("공통 격자 수") or None)
    dj = opt_file("dong_joined.csv")
    jrows = read_csv(dj) if dj else None
    # 라벨(outside_join_dong.py --label) → 표시 이름, 합치는 방식. 라벨에 "_" 가 있을 수 있어 가장 길게 맞는 라벨을 씀
    LABELS = {"장애인_유형": ("지체·뇌병변 장애인", "sum"), "장애인_정도": ("중증 장애인", "first"),
              "독거노인": ("독거노인", "first"), "alone65": ("독거노인", "first"), "alone": ("독거노인", "first"),
              "disabled": ("장애인", "first")}
    parts = []
    if jrows:
        groups = {}
        for c in jrows[0]:
            if not c.endswith("_in_high"):
                continue
            lab = max((k for k in LABELS if c.startswith(k + "_")), key=len, default=c.split("_")[0])
            groups.setdefault(lab, []).append(c)
        for lab, cs in groups.items():
            ko, how = LABELS.get(lab, (lab, "first"))
            use = cs if how == "sum" else cs[:1]           # 장애인_유형은 지체+뇌병변 합(휠체어 수요), 나머지는 첫 열(합계)
            tot = sum(num(r.get(c)) or 0 for r in jrows for c in use)
            parts.append(f"{ko} 약 {f_about(tot)}명")
    optional("IMPACT.joined", "HBI 1.8 이상 거주 추정(장애인·독거노인)", ["results/dong_joined.csv (tools/outside_join_dong.py)"], ", ".join(parts) or None)
    # ── 보조 근거 1줄: 11 법정동 교통사고(v5) 우선, 없으면 10 점 자료(개수 모드). SKT 처럼 값 합계 모드인 점 자료는 여기서 빼고 19장 본문에서 씀 ──
    pts = {}
    for r in R("points_summary.csv") or []:
        pts.setdefault(r["data"], {})[r["metric"].strip()] = num(r["value"])
    legal = {}
    for r in R("legal_summary.csv") or []:
        legal.setdefault(r["data"], {})[r["metric"].strip()] = num(r["value"])
    ptxt, psrc = None, None
    for nm, m in legal.items():
        lo_, hi_, rho_ = (m.get("HBI 하위 25% 법정동 평균(필지 100개당)"), m.get("HBI 상위 25% 법정동 평균(필지 100개당)"),
                          m.get("법정동 HBI 평균 vs 필지 100개당 건수: 스피어만"))
        if lo_ is not None and hi_ is not None:
            ptxt = (f"{nm.replace('_', ' ')}: HBI 상위 25% 법정동 필지 100개당 {hi_:.2f}건 vs 하위 25% {lo_:.2f}건"
                    + (f", 순위상관 ρ = {rho_:.2f}" if rho_ is not None else "") + " (상관이며 인과 아님)")
            psrc = f"legal_summary.csv ({nm}, 11_legal_dong_join.py)"
            break
    for nm, m in pts.items():
        if ptxt or any(k.startswith("분석 범위 안 값 합계") for k in m):
            continue
        lo_, hi_, rho_ = (m.get("HBI 하위 25% 동 평균(건물 100개당)"), m.get("HBI 상위 25% 동 평균(건물 100개당)"),
                          m.get("동별 HBI 평균 vs 건물 100개당 점 수: 스피어만"))
        if lo_ is not None and hi_ is not None:
            ptxt = (f"{nm.replace('_', ' ')}: HBI 상위 25% 동 건물 100개당 {hi_:.2f}건 vs 하위 25% 동 {lo_:.2f}건"
                    + (f", 순위상관 ρ = {rho_:.2f}" if rho_ is not None else "") + " (상관이며 인과 아님)")
            psrc = f"points_summary.csv ({nm}, 10_points_join.py)"
    optional("CROSS.points", "보조 근거: 교통사고 등 결합", ["legal_summary.csv (11, v5) 또는 points_summary.csv (10)"], ptxt)
    optional("CROSS.points_src", "보조 근거 출처 파일", ["legal_summary.csv (11) 또는 points_summary.csv (10)"], psrc)

    # ── 19장 상호제공데이터 ──
    js = {}
    for r in R("join_summary.csv") or []:
        js.setdefault(r["data"], {})[r["metric"].strip()] = num(r["value"])
    # (1) SKT 60세 이상 유동인구 행정동 합: v5 는 10_points_join 결과(points_<이름>_dong.csv, 값 합계 모드), v4 는 07(join_<이름>.csv)
    skt_rows, skt_src, skt_mode = None, None, None
    p10 = [k for k in pts if "SKT" in k.upper() and any(x.startswith("분석 범위 안 값 합계") for x in pts[k])]
    p10 = sorted(p10, key=lambda k: ("60" not in k, k))                 # 60세 이상 자료 우선 (낮시간 유동인구는 전 연령)
    if p10 and R(f"points_{p10[0]}_dong.csv"):
        k = p10[0]
        skt_rows = [(r["adm_cd"], num(r.get("hbi_mean")), num(r.get("n_points"))) for r in R(f"points_{k}_dong.csv")]
        skt_src, skt_mode = f"points_{k}_dong.csv (10_points_join.py, 값 합계)", "sum"
    else:
        k7 = next((k for k in js if "SKT" in k.upper()), None)
        if k7 and R(f"join_{k7}.csv"):
            skt_rows = [(r["adm_cd"], num(r.get("hbi_mean")), num(r.get(k7))) for r in R(f"join_{k7}.csv")]
            skt_src, skt_mode = f"join_{k7}.csv (07_join_dong.py)", "join"
    # (2) 분모: 60세 이상 거주인구 (tools/prep_elderly_pop.py --min-age 60). 결과 폴더에 있으면 그것(가짜 시험), 없으면 data_public
    pop_path = next((p for p in (S("pop60.csv"), os.path.join(ROOT, "data_public", "pop60.csv")) if os.path.exists(p)), None)
    pop60 = {r["adm_cd"]: num(r.get("pop60")) for r in (read_csv(pop_path) or [])} if pop_path else {}
    pop_ym = sorted({r.get("base_ym", "") for r in (read_csv(pop_path) or [])} - {""}) if pop_path else []
    # (3) 외출 지수 = SKT 60세 이상 유동인구(행정동 합) ÷ 60세 이상 거주인구. 07 경로(v4)는 값의 뜻을 몰라 나누지 않고 그대로 씀
    idx = []
    for code, h, v in skt_rows or []:
        if h is None or v is None:
            continue
        if skt_mode == "sum":
            p = pop60.get(code)
            if p:
                idx.append((h, v / p))
        else:
            idx.append((h, v))
    rho = spearman([x for x, _ in idx], [y for _, y in idx]) if len(idx) >= 5 else None
    p_rho = corr_p(rho, len(idx)) if rho is not None else None
    need_j = ["points_SKT_*_dong.csv (10, v5) 또는 join_SKT_*.csv (07)"] + (["data_public/pop60.csv (tools/prep_elderly_pop.py --min-age 60)"] if skt_mode != "join" else [])
    B.put("CROSS.skt_rho", "외출 지수 vs HBI 순위상관 ρ", need_j, f_num(rho))
    B.put("CROSS.skt_p", "외출 지수 순위상관 p", need_j, (("p < 0.001" if p_rho < 0.001 else f"p = {p_rho:.3f}") if p_rho is not None else None))
    B.put("CROSS.skt_n", "외출 지수 행정동 수", need_j, f_int(len(idx)) if rho is not None else None)
    optional("CROSS.skt_src", "SKT 읽은 파일", ["points_SKT_*_dong.csv (10) 또는 join_SKT_*.csv (07)"], (skt_src + (f" ÷ {os.path.relpath(pop_path, ROOT)}" if skt_mode == "sum" and pop_path else "")) if skt_src else None)
    optional("CROSS.skt_unit", "SKT 값 단위", ["points_SKT_*_dong.csv (10) 또는 join_SKT_*.csv (07)"], {"sum": "SKT: 50m 셀별 '월의 일평균' 60대 이상 유동인구(남녀 합)를 기준월 평균해 행정동별로 더한 값(명/일)",
                                                  "join": "SKT: 07_join_dong.py 결과 값 그대로 (v4 형식, 거주인구로 나누지 않음)"}.get(skt_mode))
    optional("CROSS.pop60_ym", "60세 이상 거주인구 기준일", ["pop60.csv 의 base_ym 열 (tools/prep_elderly_pop.py --min-age 60)"], ",".join(pop_ym) or None)
    interp = None
    if rho is not None and p_rho is not None:
        if rho < 0 and p_rho < 0.05:
            interp = f"가설 지지: HBI가 높은 동일수록 60세 이상 외출 지수가 낮습니다 (ρ = {rho:.2f})"
        elif rho < 0:
            interp = f"같은 방향이지만 통계적으로 뚜렷하지 않습니다 (ρ = {rho:.2f}, p = {p_rho:.2f})"
        else:
            interp = f"가설과 다른 결과: 경사 외 요인이 외출을 좌우합니다 (ρ = {rho:.2f})"
    B.put("CROSS.interp", "결과 해석", need_j, interp)
    # (4) KCB 중첩: HBI 상위 25% ∩ 저소득 쪽 25%. 방향은 맨 위 KCB_HIGH_IS_POOR 한 줄로 정함
    kcb_key = next((k for k in js if "KCB" in k.upper()), None)
    kcb_rows = R(f"join_{kcb_key}.csv") if kcb_key else None
    overlap = None
    if kcb_rows and KCB_EXPECT not in kcb_key:
        print(f"  !! KCB 값 '{kcb_key}' 이름에 '{KCB_EXPECT}' 가 없어 높은 값이 저소득인지 알 수 없습니다 → 중첩 수를 비움 (KCB_HIGH_IS_POOR 확인)")
    elif kcb_rows:
        vals = [(num(r["hbi_mean"]), num(r.get(kcb_key))) for r in kcb_rows]
        vals = [v for v in vals if v[0] is not None and v[1] is not None]
        if len(vals) >= 8:
            hq = sorted(v[0] for v in vals)[int(len(vals) * 0.75)]
            ks = sorted(v[1] for v in vals)
            if KCB_HIGH_IS_POOR:
                iq = ks[int(len(vals) * 0.75)]
                overlap = sum(1 for h, i in vals if h >= hq and i >= iq)
            else:
                iq = ks[int(len(vals) * 0.25)]
                overlap = sum(1 for h, i in vals if h >= hq and i <= iq)
    B.put("CROSS.kcb_overlap", "HBI 상위 25% × KCB 60세 이상 저소득 25% 행정동 수", ["join_KCB_*.csv (07_join_dong.py)"], f"{overlap}곳" if overlap is not None else None)
    optional("CROSS.kcb_rule", "KCB 중첩 기준", ["prepare_deck_data.py 의 KCB_HIGH_IS_POOR"], "60세 이상 월 200만원 이하 비율 상위 25%" if KCB_HIGH_IS_POOR else "60세 이상 소득 하위 25%")
    optional("CROSS.kcb_src", "KCB 읽은 파일", ["join_KCB_*.csv (07)"], f"join_{kcb_key}.csv (07_join_dong.py), KCB_HIGH_IS_POOR = {KCB_HIGH_IS_POOR}" if kcb_rows else None)
    skt_plot = idx

    # ── 22장 한 사람의 변화: 실측 구간 + intervention_summary 의 선정지(planned) 행 (v5) ──
    isum = R("intervention_summary.csv") or []
    planned = [r for r in isum if r.get("target") == T0 and not r.get("facility", "").startswith("ALL")
               and ("planned" in r.get("facility", "").lower() or "선정" in r.get("facility", ""))]
    route = None
    for r in routes:
        e, ad, mm = num(r.get("elder_min")), num(r.get("adult_min")), num(r.get("measured_min"))
        if e and ad and mm is not None and "대현산" not in r.get("name", ""):
            route = route or (r["name"], e, ad, mm)
    need22 = ["intervention_summary.csv (v5, 선정지 planned 행)", "validation_routes.csv (measured_min)"]
    if planned and route:
        pr = max(planned, key=lambda r: num(r.get("sum_saved_bld_min")) or 0)
        hb, ha = num(pr.get("hbi_before")), num(pr.get("hbi_after"))
        ok = hb is not None and ha is not None
        B.put("ONE.mode", "한 사람의 변화 계산 근거", need22, "intervention" if ok else "example")
        if ok:
            B.put("ONE.facility", "선정지 시설", need22, "선정지 " + re.sub(r"^\s*(planned|선정지)\s*[:_\-]?\s*", "", pr["facility"], flags=re.I))
            B.put("ONE.hbi_before", "설치 전 HBI(수혜 건물 평균)", need22, f"{hb:.2f}")
            B.put("ONE.hbi_after", "설치 후 HBI(수혜 건물 평균)", need22, f"{ha:.2f}")
            B.put("ONE.saved", "수혜 건물 평균 왕복 단축(분)", need22, f_num(num(pr.get("mean_saved_min")), 1))
            B.put("ONE.saved_max", "최대 왕복 단축(분)", need22, f_num(num(pr.get("max_saved_min")), 1))
            B.put("ONE.n_benefit", "수혜 주거 건물 수", need22, f_int(num(pr.get("n_benefit"))))
            B.put("ONE.route", "실측 구간 이름", need22, route[0])
            B.put("ONE.route_model", "실측 구간 모델 예측(성인, 분)", need22, f"{route[2]:.1f}분")
            B.put("ONE.measured", "팀 실측(분)", need22, f"{route[3]:g}분")
    else:
        B.put("ONE.mode", "한 사람의 변화 계산 근거", need22, "example")

    # ── 23장 공익 효과: Σ_동 pop65 × weight_x_saved_min ÷ weight_all (1회 왕복 기준, v5) ──
    #   연간 환산은 하지 않음: 외출 빈도 등 출처 있는 가정이 확보되지 않았음
    idong = R("intervention_dong.csv") or []
    all_name = next((r["facility"] for r in isum if r.get("facility", "").startswith("ALL")), None)
    popd = {r["adm_cd"]: num(r.get("pop65")) for r in (ew or [])}
    people = minutes = None
    if all_name and idong and popd:
        rows = [r for r in idong if r.get("facility") == all_name and r.get("target") == T0]
        acc_p = acc_m = 0.0
        used = 0
        for r in rows:
            p65, wa = popd.get(r["adm_cd"]), num(r.get("weight_all"))
            if p65 and wa:
                acc_p += p65 * (num(r.get("weight_benefit")) or 0) / wa
                acc_m += p65 * (num(r.get("weight_x_saved_min")) or 0) / wa
                used += 1
        if used:
            people, minutes = acc_p, acc_m
    n_fac = len({r["facility"] for r in isum if r.get("target") == T0 and not r.get("facility", "").startswith("ALL")})
    need_i = ["intervention_summary.csv (v5)", "intervention_dong.csv (v5)", "dong_hbi_with_elderly.csv (tools/outside_elderly.py)"]
    B.put("IMPACT.n_sites", "개입 후보지 수", ["intervention_summary.csv (v5)"], f"{n_fac}곳" if n_fac else None)
    B.put("IMPACT.people", "수혜 고령인구(추정)", need_i, f_about(people) if people else None)
    B.put("IMPACT.minutes", "1회 왕복당 합계 단축(분)", need_i,
          (f"{minutes / 10000:,.1f}만 분" if minutes >= 1e5 else f"{f_about(minutes)}분") if minutes else None)
    B.fields["IMPACT.note"] = {"value": "1회 왕복 기준: 동별 65세 이상 인구 × (수혜 건물 연면적 × 단축 분 ÷ 동 주거 연면적)의 합. 연간 환산은 출처 있는 외출 빈도 가정이 없어 하지 않음",
                               "label": "공익효과 계산식", "need": [], "optional": True}

    # ── 부록 민감도 ──
    sens = R("sensitivity.csv") or []
    sh_col = next((k for k in (sens[0].keys() if sens else []) if k.startswith("share_ge")), None)
    B.table("APPX.sens", "민감도 분석 표", ["sensitivity.csv (08_sensitivity.py)"],
            [[r["scenario"], f_num(num(r["hbi_median"])), f_pct(num(r.get(sh_col))) if sh_col else None,
              f_num(num(r["rank_corr_vs_base"])), f_pct(num(r["top10_overlap"]), 0)] for r in sens])

    # ── 그림 ──
    plots = make_plots(B, grid, targets, T0, vs, site_rows, skt_plot, rho, p_rho)
    if not plots:
        for k, lab, need in [("map", "결과 지도", ["grid_hbi.csv", "matplotlib"]), ("ranks", "순위 역전 산점도", ["grid_hbi.csv", "matplotlib"]),
                             ("sites", "선정지 백분위 막대", ["validation_sites.csv", "matplotlib"]), ("skt", "외출 지수 산점도", ["points_SKT_*_dong.csv", "pop60.csv", "matplotlib"])]:
            B.img(k, lab, need, None)

    data = {"source": source, "src": os.path.relpath(src, ROOT), "generated_at": datetime.datetime.now().isoformat(timespec="seconds"),
            "targets": targets, "base_target": T0, "fields": B.fields, "images": B.images, "tables": B.tables, "missing": B.missing()}
    os.makedirs(os.path.dirname(OUT_JSON), exist_ok=True)
    with open(OUT_JSON, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=1)
    miss = data["missing"]
    with open(OUT_MISSING, "w", encoding="utf-8") as f:
        f.write(f"# 누락 목록 초안 (source={source}, src={data['src']}) — 슬라이드 번호는 build_deck.js 가 채웁니다\n")
        for m in miss:
            f.write(f"누락: ?, {m['label']}, {' / '.join(m['need'])}\n")
        opt = [(k, v) for k, v in B.fields.items() if v.get("optional") and v.get("value") in (None, "")]
        if opt:
            f.write("# 선택 항목 대체 (값이 없어 기본 문구로 바뀔 수 있는 곳. 필수 빈칸이 아니라 check_deck N=M=K 에는 넣지 않음)\n")
            for k, v in opt:
                f.write(f"대체: ?, {v['label']}, {' / '.join(v['need']) or '-'}  [{k}]\n")
    print(f"[{source}] {data['src']} → deck/data/results.json  (값 {sum(1 for v in B.fields.values() if v['value'] is not None)}/{len(B.fields)}, "
          f"그림 {sum(1 for v in B.images.values() if v['path'])}/{len(B.images)}, 누락 {len(miss)})")


def make_plots(B, grid, targets, T0, vs, site_rows, skt_plot, skt_rho, skt_p):
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        from matplotlib import font_manager as fm
        from matplotlib.collections import PatchCollection, LineCollection
        from matplotlib.patches import Rectangle
        from matplotlib.colors import LinearSegmentedColormap
    except ImportError:
        print("!! matplotlib 없음 → 그림 생략 (python3 -m pip install --user matplotlib)")
        return False
    names = {f.name for f in fm.fontManager.ttflist}
    for fnt in ["Malgun Gothic", "Apple SD Gothic Neo", "AppleGothic", "NanumGothic", "Noto Sans CJK KR"]:
        if fnt in names:
            plt.rcParams["font.family"] = fnt
            break
    plt.rcParams["axes.unicode_minus"] = False
    INK, MUTED, LINE, DARK, ORANGE = "#22302A", "#5F6B64", "#D5E2D8", "#1F3B2D", "#E8743B"
    cmap = LinearSegmentedColormap.from_list("hbi", COLORS)
    P = lambda n: os.path.join(IMG_DIR, n)

    def style(ax):
        for s in ["top", "right"]:
            ax.spines[s].set_visible(False)
        for s in ["left", "bottom"]:
            ax.spines[s].set_color("#BBBBBB")
        ax.tick_params(colors=MUTED, labelsize=9)

    # 1) 목적지별 격자 지도 (배경: 공개 행정동 경계 + 구 이름)
    if grid:
        alld = load_dongs(None)
        tgt = [d for d in alld if d["gu"] in TARGET_GU]
        x0 = min(d["bbox"][0] for d in tgt) - 600; x1 = max(d["bbox"][2] for d in tgt) + 600
        y0 = min(d["bbox"][1] for d in tgt) - 600; y1 = max(d["bbox"][3] for d in tgt) + 600
        W, H = 5.1, 3.4
        # 슬라이드 칸 비율(3:2)에 맞춰 범위를 넓힘
        if (x1 - x0) / (y1 - y0) < W / H:
            c, half = (x0 + x1) / 2, (y1 - y0) * W / H / 2; x0, x1 = c - half, c + half
        else:
            c, half = (y0 + y1) / 2, (x1 - x0) * H / W / 2; y0, y1 = c - half, c + half
        segs_all = [r for d in alld if d["gu"] not in TARGET_GU for r in d["rings"]]
        segs_t = [r for d in tgt for r in d["rings"]]
        for T in targets:
            cells = [g for g in grid if g["target"] == T]
            if not cells:
                continue
            fig = plt.figure(figsize=(W, H), dpi=220)
            ax = fig.add_axes([0, 0, 1, 1]); ax.set_facecolor("#F7F9F7"); fig.patch.set_facecolor("#F7F9F7")
            ax.add_collection(LineCollection(segs_all, colors="#DCE3DD", linewidths=0.35))
            pc = PatchCollection([Rectangle((num(g["cell_x"]) - 125, num(g["cell_y"]) - 125), 250, 250) for g in cells], cmap=cmap, linewidths=0)
            pc.set_array([num(g["hbi_mean"]) for g in cells]); pc.set_clim(1.0, 2.2)
            ax.add_collection(pc)
            ax.add_collection(LineCollection(segs_t, colors="#8A968F", linewidths=0.35))
            for gu in TARGET_GU:
                ds = [d for d in tgt if d["gu"] == gu]
                cx = sorted((d["bbox"][0] + d["bbox"][2]) / 2 for d in ds)[len(ds) // 2]
                cy = min(max(d["bbox"][3] for d in ds) + 250, y1 - 1100)      # 위쪽 끝 구는 그림 안으로
                ax.text(cx, cy, gu, fontsize=8.5, fontweight="bold", color=DARK, ha="center", va="bottom",
                        bbox=dict(fc="white", ec="none", alpha=0.8, pad=1.2))
            ax.set_xlim(x0, x1); ax.set_ylim(y0, y1); ax.set_aspect("equal"); ax.axis("off")
            ax.plot([x1 - 3400, x1 - 400], [y0 + 500, y0 + 500], color=INK, lw=2)
            ax.text(x1 - 1900, y0 + 650, "3km", fontsize=7.5, color=INK, ha="center", va="bottom")
            ax.text(x0 + 400, y0 + 450, f"250m 격자 평균 HBI · 목적지: {TARGET_LABEL.get(T, T)}", fontsize=7.5, color=MUTED, va="bottom")
            fig.savefig(P(f"map_{T}.png")); plt.close(fig)
        B.img("map", f"결과 지도({TARGET_LABEL.get(T0, T0)})", ["grid_hbi.csv"], P(f"map_{T0}.png") if os.path.exists(P(f"map_{T0}.png")) else None)
        for T in targets:
            if T != T0:
                B.img(f"map_{T}", f"결과 지도({TARGET_LABEL.get(T, T)})", ["grid_hbi.csv"], P(f"map_{T}.png") if os.path.exists(P(f"map_{T}.png")) else None)
        # 범례 (1.0 ~ 2.2)
        fig = plt.figure(figsize=(3, 0.5), dpi=220); ax = fig.add_axes([0.05, 0.45, 0.9, 0.3])
        ax.imshow([[i / 255 for i in range(256)]], aspect="auto", cmap=cmap, extent=(1.0, 2.2, 0, 1))
        ax.set_yticks([]); ax.set_xticks([1.0, 1.3, 1.8, 2.2]); ax.set_xticklabels(["1.0", "1.3", "1.8", "2.2+"], fontsize=8, color="#555555")
        for s in ax.spines.values():
            s.set_visible(False)
        fig.savefig(P("legend_hbi.png"), transparent=True); plt.close(fig)
        B.img("legend", "HBI 범례", ["grid_hbi.csv"], P("legend_hbi.png"))
    else:
        B.img("map", "결과 지도", ["grid_hbi.csv"], None)

    # 2) 순위 역전 산점도: 평지 가정 vs 경사 반영 (기준 목적지)
    cells = [g for g in grid if g["target"] == T0 and num(g["flat_min"]) and num(g["elder_min"])]
    if cells:
        fx = [num(g["flat_min"]) for g in cells]; ey = [num(g["elder_min"]) for g in cells]; hb = [num(g["hbi_mean"]) for g in cells]
        medf = sorted(fx)[len(fx) // 2]
        fig, ax = plt.subplots(figsize=(3.6, 2.9), dpi=220)
        base = [i for i in range(len(cells)) if not (hb[i] >= HI and fx[i] <= medf)]
        hot = [i for i in range(len(cells)) if hb[i] >= HI and fx[i] <= medf]
        ax.scatter([fx[i] for i in base], [ey[i] for i in base], s=4, color="#A9BFB0", alpha=0.6, linewidths=0)
        ax.scatter([fx[i] for i in hot], [ey[i] for i in hot], s=6, color=ORANGE, alpha=0.85, linewidths=0, label="평지 기준 '가까움' + HBI 1.8 이상")
        xm, ym = max(fx) * 1.05, max(ey) * 1.05
        ax.plot([0, min(xm, ym)], [0, min(xm, ym)], color=MUTED, lw=0.8, ls="--")
        ax.plot([0, min(xm, ym / HI)], [0, min(xm * HI, ym)], color=ORANGE, lw=0.8, ls=":")
        ax.text(xm * 0.98, min(xm, ym) * 0.9, "평지와 같음", fontsize=7, color=MUTED, ha="right", va="top")
        ax.text(min(xm, ym / HI) * 0.97, min(xm * HI, ym) * 0.97, "1.8배", fontsize=7, color=ORANGE, ha="right", va="top")
        ax.axvline(medf, color=LINE, lw=0.8)
        ax.text(medf, ym * 0.02, " 평지 기준 중앙값", fontsize=6.5, color=MUTED, va="bottom")
        ax.set_xlabel("평지로 계산한 왕복(분)", fontsize=8.5, color=MUTED); ax.set_ylabel("경사 반영 왕복(분)", fontsize=8.5, color=MUTED)
        ax.set_xlim(0, xm); ax.set_ylim(0, ym)
        ax.legend(fontsize=7, frameon=False, loc="upper left", handletextpad=0.2, markerscale=2, borderaxespad=0.1)
        style(ax); fig.tight_layout(pad=0.4); fig.savefig(P("ranks.png"), transparent=True); plt.close(fig)
        B.img("ranks", "순위 역전 산점도", ["grid_hbi.csv"], P("ranks.png"))
    else:
        B.img("ranks", "순위 역전 산점도", ["grid_hbi.csv"], None)

    # 3) 선정지 백분위 막대
    sr = [s for s in site_rows if s["percentile"] is not None]
    if sr:
        fig, ax = plt.subplots(figsize=(4.6, 2.2), dpi=220)
        ys = list(range(len(sr)))[::-1]
        for y, s in zip(ys, sr):
            ax.barh(y, s["percentile"] * 100, color=ORANGE if s["top10"] == "포함" else "#A9BFB0", height=0.56)
            ax.text(min(s["percentile"] * 100, 99) - 1.5, y, s["top_text"], va="center", ha="right", fontsize=8, color="white", fontweight="bold")
        ax.axvline(90, color="#B23A2A", lw=1.2); ax.text(90, len(sr) - 0.45, " 상위 10% 기준", fontsize=7.5, color="#B23A2A", va="bottom")
        ax.set_yticks(ys); ax.set_yticklabels([s["name"] for s in sr], fontsize=8.5, color=INK)
        ax.set_xlim(0, 100); ax.set_ylim(-0.6, len(sr) - 0.1); ax.set_xticks([0, 25, 50, 75, 90, 100])
        ax.set_xlabel("같은 반경 300m 원 평균끼리 비교한 백분위" if sr[0].get("mode") == "circle" else "전체 250m 격자 중 백분위", fontsize=8, color=MUTED)
        style(ax); fig.tight_layout(pad=0.3); fig.savefig(P("sites.png"), transparent=True); plt.close(fig)
        B.img("sites", "선정지 백분위 막대", ["validation_sites.csv"], P("sites.png"))
    else:
        B.img("sites", "선정지 백분위 막대", ["validation_sites.csv"], None)

    # 4) 외출 지수 산점도 (있을 때만): x 행정동 평균 HBI, y 60세 이상 유동인구 ÷ 60세 이상 거주인구
    pts = [p for p in (skt_plot or []) if p[0] is not None and p[1] is not None]
    need = ["points_SKT_*_dong.csv (10) 또는 join_SKT_*.csv (07)", "pop60.csv"]
    if len(pts) >= 3:
        fig, ax = plt.subplots(figsize=(4.4, 2.75), dpi=220)
        ax.scatter([p[0] for p in pts], [p[1] for p in pts], s=12, color=DARK, alpha=0.7, linewidths=0)
        n = len(pts); mx = sum(p[0] for p in pts) / n; my = sum(p[1] for p in pts) / n
        sxx = sum((p[0] - mx) ** 2 for p in pts)
        if sxx > 0:
            b = sum((p[0] - mx) * (p[1] - my) for p in pts) / sxx
            xs = [min(p[0] for p in pts), max(p[0] for p in pts)]
            ax.plot(xs, [my + b * (x - mx) for x in xs], color=ORANGE, lw=1.6)
        if skt_rho is not None:
            ptxt = ("p < 0.001" if skt_p < 0.001 else f"p = {skt_p:.3f}") if skt_p is not None else ""
            ax.text(0.98, 0.95, f"ρ = {skt_rho:.2f}  {ptxt}  (n = {n})", transform=ax.transAxes, ha="right", va="top", fontsize=8, color=ORANGE, fontweight="bold")
        ax.set_xlabel("행정동 평균 HBI", fontsize=8.5, color=MUTED); ax.set_ylabel("외출 지수 (60세 이상 유동 ÷ 거주)", fontsize=8.5, color=MUTED)
        style(ax); fig.tight_layout(pad=0.4); fig.savefig(P("skt.png"), transparent=True); plt.close(fig)
        B.img("skt", "외출 지수 산점도", need, P("skt.png"))
    else:
        B.img("skt", "외출 지수 산점도", need, None)
    return True


if __name__ == "__main__":
    main()
