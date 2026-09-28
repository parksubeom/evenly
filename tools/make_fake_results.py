# -*- coding: utf-8 -*-
"""
tools/make_fake_results.py ─ 반출 결과와 똑같은 형식의 "가짜" 결과 만들기 (파이프라인 시험용)

[왜]   실제 반출 결과는 10/15~19에야 들어옵니다. 그 전에 기획서·데모 자동 생성이 끝까지 도는지
       미리 확인하려고, analysis/hbi/04~08 이 쓰는 파일 형식을 그대로 흉내 낸 가짜 파일을 만듭니다.
[실행] python3 tools/make_fake_results.py              → results/fake_export/ (전체)
       python3 tools/make_fake_results.py --partial    → join_*, parcel_*, sensitivity, map_* 없이 (누락 처리 시험)
[주의] 여기서 나온 숫자는 전부 지어낸 값입니다. 이 폴더로 만든 PPT에는 "테스트 데이터 — 제출 금지"
       워터마크가 붙고, 파일명도 deliverables/_test_기획서.pptx 로 따로 나옵니다.
       표준 라이브러리만 씁니다 (matplotlib 이 있으면 map_*.png 도 그림).
"""
import argparse, json, math, os, random, shutil, sqlite3, struct, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from evenly_common import (ROOT, TARGET_GU, FAKE_MARKER, load_dongs, load_sites, dong_of, write_csv)

GRID = 250
MIN_COUNT = 5
HI, LO = 1.8, 1.3
TARGETS = ["medical", "bus", "elderly", "station"]      # v4 는 약국 미포함 → pharmacy 는 만들지 않음
# 목적지별 평지 가정 왕복 시간(분)의 대략 범위, HBI 강도
TPROF = {"medical": (8, 34, 1.0), "bus": (3, 14, 0.8), "elderly": (10, 40, 1.05), "station": (14, 48, 1.15)}
SENS = ["보행속도 0.7m/s", "보행속도 1.0m/s", "내리막 부담 0%(Tobler 원식)", "내리막 부담 100%", "계단 가중 1.5", "경사 절단 30%"]


def gpkg_write(path, layer, cells, cols):
    """아주 작은 GeoPackage 작성기 (sqlite3 + WKB). analysis/hbi/lib/qio.write_grid_gpkg 와 같은 필드 구성"""
    if os.path.exists(path):
        os.remove(path)
    con = sqlite3.connect(path)
    con.execute("PRAGMA application_id = 1196444487")      # 'GPKG'
    con.execute("PRAGMA user_version = 10200")
    con.executescript("""
    CREATE TABLE gpkg_spatial_ref_sys (srs_name TEXT NOT NULL, srs_id INTEGER PRIMARY KEY, organization TEXT NOT NULL,
      organization_coordsys_id INTEGER NOT NULL, definition TEXT NOT NULL, description TEXT);
    CREATE TABLE gpkg_contents (table_name TEXT PRIMARY KEY, data_type TEXT NOT NULL, identifier TEXT UNIQUE, description TEXT DEFAULT '',
      last_change DATETIME NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')), min_x DOUBLE, min_y DOUBLE, max_x DOUBLE, max_y DOUBLE, srs_id INTEGER);
    CREATE TABLE gpkg_geometry_columns (table_name TEXT NOT NULL, column_name TEXT NOT NULL, geometry_type_name TEXT NOT NULL,
      srs_id INTEGER NOT NULL, z TINYINT NOT NULL, m TINYINT NOT NULL, CONSTRAINT pk_geom_cols PRIMARY KEY (table_name, column_name));
    """)
    con.executemany("INSERT INTO gpkg_spatial_ref_sys VALUES (?,?,?,?,?,?)", [
        ("Undefined cartesian SRS", -1, "NONE", -1, "undefined", None),
        ("Undefined geographic SRS", 0, "NONE", 0, "undefined", None),
        ("WGS 84", 4326, "EPSG", 4326, 'GEOGCS["WGS 84",DATUM["WGS_1984",SPHEROID["WGS 84",6378137,298.257223563]],PRIMEM["Greenwich",0],UNIT["degree",0.0174532925199433]]', None),
        ("Korea 2000 / Central Belt 2010", 5186, "EPSG", 5186,
         'PROJCS["Korea 2000 / Central Belt 2010",GEOGCS["Korea 2000",DATUM["Geocentric_datum_of_Korea",SPHEROID["GRS 1980",6378137,298.257222101]],'
         'PRIMEM["Greenwich",0],UNIT["degree",0.0174532925199433]],PROJECTION["Transverse_Mercator"],PARAMETER["latitude_of_origin",38],'
         'PARAMETER["central_meridian",127],PARAMETER["scale_factor",1],PARAMETER["false_easting",200000],PARAMETER["false_northing",600000],UNIT["metre",1]]', None)])
    fields = ", ".join(f'"{k}" REAL' for k in cols)
    con.execute(f'CREATE TABLE "{layer}" (fid INTEGER PRIMARY KEY AUTOINCREMENT, geom POLYGON, {fields})')
    xs = [gx * GRID for gx, _ in cells] + [(gx + 1) * GRID for gx, _ in cells]
    ys = [gy * GRID for _, gy in cells] + [(gy + 1) * GRID for _, gy in cells]
    con.execute("INSERT INTO gpkg_contents (table_name, data_type, identifier, min_x, min_y, max_x, max_y, srs_id) VALUES (?,?,?,?,?,?,?,?)",
                (layer, "features", layer, min(xs), min(ys), max(xs), max(ys), 5186))
    con.execute("INSERT INTO gpkg_geometry_columns VALUES (?,?,?,?,?,?)", (layer, "geom", "POLYGON", 5186, 0, 0))
    keys = list(cols)
    for i, (gx, gy) in enumerate(cells):
        x0, y0, x1, y1 = gx * GRID, gy * GRID, (gx + 1) * GRID, (gy + 1) * GRID
        ring = [(x0, y0), (x1, y0), (x1, y1), (x0, y1), (x0, y0)]
        wkb = struct.pack("<BIII", 1, 3, 1, len(ring)) + b"".join(struct.pack("<dd", *p) for p in ring)
        hdr = b"GP" + struct.pack("<BBi", 0, 0b00000011, 5186) + struct.pack("<dddd", x0, x1, y0, y1)   # envelope xy, little endian
        con.execute(f'INSERT INTO "{layer}" (geom, {", ".join(chr(34) + k + chr(34) for k in keys)}) VALUES (?, {", ".join("?" * len(keys))})',
                    [sqlite3.Binary(hdr + wkb)] + [float(cols[k][i]) for k in keys])
    con.commit()
    con.close()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=os.path.join(ROOT, "results", "fake_export"))
    ap.add_argument("--partial", action="store_true", help="join_*, parcel_*, sensitivity, map_* 를 빼고 생성")
    ap.add_argument("--seed", type=int, default=20261015)
    a = ap.parse_args()
    rnd = random.Random(a.seed)
    out = os.path.abspath(a.out)
    if os.path.basename(out) == "raw_export":
        raise SystemExit("가짜 데이터를 raw_export 에 만들 수 없습니다")
    if os.path.isdir(out):
        shutil.rmtree(out)
    os.makedirs(out)
    P = lambda n: os.path.join(out, n)

    dongs = load_dongs(TARGET_GU)
    sites = load_sites()
    # 언덕: 선정지 5곳 + 구마다 무작위 2~3곳 (가짜 지형)
    # 화곡동은 일부러 약하게 → "상위 10% 밖" 선정지가 섞인 경우도 시험
    amp = [1.0, 0.3, 1.1, 0.9, 0.8]
    hills = [(s["x"] + rnd.uniform(-150, 150), s["y"] + rnd.uniform(-150, 150), rnd.uniform(500, 900), amp[i % 5]) for i, s in enumerate(sites)]
    for gu in TARGET_GU:
        ds = [d for d in dongs if d["gu"] == gu]
        for _ in range(rnd.randint(2, 3)):
            d = rnd.choice(ds)
            x0, y0, x1, y1 = d["bbox"]
            hills.append((rnd.uniform(x0, x1), rnd.uniform(y0, y1), rnd.uniform(400, 1100), rnd.uniform(0.4, 1.0)))

    def hill(x, y):
        return sum(h * math.exp(-((x - hx) ** 2 + (y - hy) ** 2) / (2 * r * r)) for hx, hy, r, h in hills)

    # 250m 격자: 5개 구 안에 중심이 들어가는 칸 중 약 70%를 "주거 건물이 있는 칸"으로
    cells = []
    for gu in TARGET_GU:
        ds = [d for d in dongs if d["gu"] == gu]
        x0 = min(d["bbox"][0] for d in ds); y0 = min(d["bbox"][1] for d in ds)
        x1 = max(d["bbox"][2] for d in ds); y1 = max(d["bbox"][3] for d in ds)
        for gx in range(int(x0 // GRID), int(x1 // GRID) + 1):
            for gy in range(int(y0 // GRID), int(y1 // GRID) + 1):
                cx, cy = (gx + 0.5) * GRID, (gy + 0.5) * GRID
                d = dong_of(cx, cy, ds)
                if d and rnd.random() < 0.72:
                    cells.append({"gx": gx, "gy": gy, "x": cx, "y": cy, "dong": d, "h": hill(cx, cy),
                                  "n": rnd.randint(MIN_COUNT, 110), "noise": rnd.gauss(0, 0.06), "far": rnd.random()})

    grid_rows, summary = [], []
    by_target = {}
    for T in TARGETS:
        lo_t, hi_t, k = TPROF[T]
        rows = []
        for c in cells:
            hbi = max(1.0, min(2.6, 1.0 + k * 0.95 * c["h"] + c["noise"] + rnd.gauss(0, 0.03)))
            flat = lo_t + (hi_t - lo_t) * (0.25 * c["far"] + 0.75 * rnd.random() ** 1.4)
            med = max(1.0, hbi + rnd.gauss(0, 0.03))
            share = max(0.0, min(1.0, 1 / (1 + math.exp(-(hbi - HI) * 9)) + rnd.gauss(0, 0.03)))
            wt = c["n"] * rnd.uniform(140, 520)
            rows.append({"c": c, "hbi": hbi, "med": med, "share": share, "wt": wt,
                         "elder": flat * hbi * rnd.uniform(0.97, 1.03), "flat": flat})
        by_target[T] = rows
        for r in rows:
            c = r["c"]
            grid_rows.append([T, c["x"], c["y"], c["n"], round(r["wt"]), round(r["hbi"], 3), round(r["med"], 3),
                              round(r["share"], 3), round(r["elder"], 1), round(r["flat"], 1)])
        nb = sum(r["c"]["n"] for r in rows)
        hi_n = round(sum(r["c"]["n"] * r["share"] for r in rows))
        mid_n = sum(r["c"]["n"] for r in rows if LO <= r["hbi"] < HI)
        hbis = sorted(r["hbi"] for r in rows)
        wt_hi = sum(r["wt"] * r["share"] for r in rows)
        summary += [[T, "분석 건물 수", nb],
                    [T, "경계 500m 이내라 제외한 건물 수", rnd.randint(9000, 16000)],
                    [T, "HBI 중앙값", round(hbis[len(hbis) // 2] - 0.02, 3)],
                    [T, f"HBI {LO}~{HI} 비율", round(mid_n / nb, 3)],
                    [T, f"HBI {HI} 이상 비율", round(hi_n / nb, 3)],
                    [T, f"HBI {HI} 이상 건물 수", hi_n],
                    [T, "귀갓길(목적지→집) 편도 배수 중앙값", round(1 + (hbis[len(hbis) // 2] - 1) * 1.6, 3)],
                    [T, "고령자 왕복 중앙값(분)", round(sorted(r["elder"] for r in rows)[len(rows) // 2], 1)],
                    [T, "휠체어 도달불가 비율", round(rnd.uniform(0.01, 0.05), 3)],
                    [T, f"HBI {HI} 이상 건물의 연면적 합(㎡, 고령인구 배분용)", round(wt_hi)],
                    [T, "분석 건물 연면적 합(㎡)", round(sum(r["wt"] for r in rows))]]
        gpkg_write(P(f"grid_hbi_{T}.gpkg"), f"grid_{T}", [(r["c"]["gx"], r["c"]["gy"]) for r in rows],
                   {"n_bld": [r["c"]["n"] for r in rows], "hbi_mean": [round(r["hbi"], 3) for r in rows],
                    "hbi_median": [round(r["med"], 3) for r in rows], "share_high": [round(r["share"], 3) for r in rows],
                    "elder_min": [round(r["elder"], 1) for r in rows], "flat_min": [round(r["flat"], 1) for r in rows]})
    write_csv(P("grid_hbi.csv"), ["target", "cell_x", "cell_y", "n_bld", "weight", "hbi_mean", "hbi_median", "share_high", "elder_min", "flat_min"], grid_rows)
    write_csv(P("summary.csv"), ["target", "metric", "value"], summary)

    # 행정동 (기준 목적지 medical)
    med = by_target["medical"]
    agg = {}
    for r in med:
        d = r["c"]["dong"]
        g = agg.setdefault(d["adm_cd"], {"d": d, "n": 0, "hs": 0.0, "sh": 0.0, "wa": 0.0, "wh": 0.0})
        g["n"] += r["c"]["n"]; g["hs"] += r["hbi"] * r["c"]["n"]; g["sh"] += r["share"] * r["c"]["n"]
        g["wa"] += r["wt"] * 1.06; g["wh"] += r["wt"] * r["share"]
    dong_rows = [[k, g["d"]["adm_cd_stat"], g["d"]["adm_nm"], g["n"], round(g["hs"] / g["n"], 3), round(g["sh"] / g["n"], 3),
                  round(g["wa"]), round(g["wh"]), ""] for k, g in agg.items() if g["n"] >= MIN_COUNT]
    hdr = ["adm_cd", "adm_cd_stat", "adm_nm", "n_bld", "hbi_mean", "share_high", "weight_all", "weight_high", "elderly_in_high_est"]
    write_csv(P("dong_hbi.csv"), hdr, dong_rows)
    # 밖에서 만드는 고령인구 추정표 (analysis/hbi/tools/outside_elderly.py 결과 형식: 열 순서 유지 + pop65)
    ew = []
    for r in dong_rows:
        pop = rnd.randint(2200, 9000)
        est = round(pop * r[7] / r[6]) if r[6] else ""
        ew.append(r[:8] + [est, pop])
    write_csv(P("dong_hbi_with_elderly.csv"), hdr + ["pop65"], ew)

    # 검증 ① 선정지
    cm = [r["hbi"] for r in med]
    vs, site_h = [], []
    for s in sites:
        near = [r for r in med if math.hypot(r["c"]["x"] - s["x"], r["c"]["y"] - s["y"]) <= s["radius"] + 125]
        if not near:
            vs.append([s["name"], 0, "", "", "", ""]); continue
        n = sum(r["c"]["n"] for r in near)
        hm = sum(r["hbi"] * r["c"]["n"] for r in near) / n
        pct = sum(1 for v in cm if v < hm) / len(cm)
        site_h.append(hm)
        vs.append([s["name"], n, round(hm, 3), round(sum(r["share"] * r["c"]["n"] for r in near) / n, 3), round(pct, 3), pct >= 0.9])
    write_csv(P("validation_sites.csv"), ["name", "n_bld", "hbi_mean", "share_high", "percentile", "top10"], vs)
    thr = min(site_h)
    cand = [r for r in med if r["hbi"] > thr and all(math.hypot(r["c"]["x"] - s["x"], r["c"]["y"] - s["y"]) > 500 for s in sites)]
    cand.sort(key=lambda r: -r["hbi"])
    write_csv(P("validation_new_candidates.csv"), ["cell_x", "cell_y", "hbi_mean", "n_bld"],
              [[r["c"]["x"], r["c"]["y"], round(r["hbi"], 3), r["c"]["n"]] for r in cand[:30]])
    # 검증 ② 구간
    write_csv(P("validation_routes.csv"), ["name", "straight_m", "net_m", "elder_min", "adult_min", "wheel_path_m", "flat_min", "measured_min"], [
        ["대현산배수지공원(모노레일 하부→공원)", 271, 356.0, 11.2, 8.1, 742.0, 7.4, ""],
        ["현장실측1", 402, 468.0, 15.6, 11.3, 1180.0, 9.8, 12.0],
        ["현장실측2", 310, 377.0, 10.9, 7.9, 655.0, 7.9, 8.5],
        ["현장실측3", 455, 520.0, 13.4, 9.7, 980.0, 10.8, 10.5]])
    # 검증 ③ 기여도 (04_validate.py 와 같은 문구)
    write_csv(P("validation_ablation.csv"), ["scenario", "metric", "value"], [
        ["DEM 제외(평지 가정)", "경사 반영 상위10% 취약건물 중 평지 기준으로는 상위10%가 아닌 비율", 0.463],
        ["DEM 제외(평지 가정)", "경사 반영 vs 평지 소요시간 순위상관(Spearman)", 0.712],
        ["DEM 제외(평지 가정)", "HBI 1.8 이상 건물 중 평지 기준 소요시간이 중앙값 이하('양호')인 비율", 0.388],
        ["계단 레이어 제외", "계단을 통행가능으로 잘못 가정할 때 휠체어 시간 과소추정 비율(평균)", 0.214],
        ["계단 레이어 제외", "휠체어 도달불가 건물 비율(계단 반영 시)", 0.027],
        ["500m 격자 평균으로 집계", "HBI 1.8 이상 건물 중 평균이 1.3 미만인 격자에 가려진 비율", 0.176],
        ["DEM 5m vs 1m", "HBI 순위상관(Spearman)", 0.934],
        ["DEM 5m vs 1m", "HBI 평균 절대차", 0.041]])

    if not a.partial:
        # 필지 (06_parcel.py)
        npar = int(sum(r["c"]["n"] for r in med) * 0.83)
        write_csv(P("parcel_summary.csv"), ["metric", "value"], [["HBI 산출 필지 수", npar], ["그중 지목 '대' 필지 수", int(npar * 0.91)],
                                                                 ["'대' 필지 HBI 1.8 이상 비율", 0.071]])
        emd = {}
        for r in med:
            k = r["c"]["dong"]["adm_cd"][:8] + "01"            # 가짜 법정동 코드
            emd.setdefault(k, []).append(r)
        write_csv(P("parcel_by_legal_dong.csv"), ["emd_cd", "n", "hbi_mean", "share_high"],
                  [[k, sum(r["c"]["n"] for r in v), round(sum(r["hbi"] for r in v) / len(v), 3), round(sum(r["share"] for r in v) / len(v), 3)]
                   for k, v in emd.items() if len(v) >= 2])
        # 상호제공데이터 결합 (07_join_dong.py)
        js = []
        for name, base, slope in [("SKT_고령유동인구", 0.62, -0.28), ("KCB_소득", 3150.0, -900.0)]:
            jr = []
            for r in dong_rows:
                v = base + slope * (r[4] - 1.2) + rnd.gauss(0, abs(base) * 0.08)
                jr.append([r[0], r[2], r[4], r[5], round(v, 4)])
            write_csv(P(f"join_{name}.csv"), ["adm_cd", "adm_nm", "hbi_mean", "share_high", name], jr)
            js += [[name, "결합 행정동 수", len(jr)], [name, "HBI 평균 vs 값: 피어슨 상관", -0.412 if "SKT" in name else -0.268],
                   [name, "HBI 평균 vs 값: 스피어만 순위상관", -0.395 if "SKT" in name else -0.241],
                   [name, "고위험 비율 vs 값: 스피어만 순위상관", -0.37 if "SKT" in name else -0.22]]
            for gname in ["HBI 하위 25% 동", "25~50%", "50~75%", "HBI 상위 25% 동"]:
                js.append([name, f"{gname} 평균값", ""])
        write_csv(P("join_summary.csv"), ["data", "metric", "value"], js)
        # 민감도 (08_sensitivity.py)
        base_med = [x for x in summary if x[0] == "medical" and x[1] == "HBI 중앙값"][0][2]
        base_sh = [x for x in summary if x[0] == "medical" and x[1] == f"HBI {HI} 이상 비율"][0][2]
        sens = [["기본값", base_med, base_sh, 1.0, 1.0]]
        for nm, dm, ds, rc, ov in zip(SENS, [0.0, 0.0, -0.041, 0.052, 0.018, -0.012], [0.0, 0.0, -0.019, 0.027, 0.009, -0.006],
                                      [0.998, 0.997, 0.962, 0.975, 0.991, 0.988], [0.97, 0.96, 0.84, 0.88, 0.93, 0.91]):
            sens.append([nm, round(base_med + dm, 3), round(max(0, base_sh + ds), 3), rc, ov])
        write_csv(P("sensitivity.csv"), ["scenario", "hbi_median", f"share_ge_{HI}", "rank_corr_vs_base", "top10_overlap"], sens)
        # 지도 이미지 (matplotlib 이 있을 때만, 05_export.py 처럼)
        try:
            import matplotlib
            matplotlib.use("Agg")
            import matplotlib.pyplot as plt
            for T in TARGETS:
                fig, ax = plt.subplots(figsize=(6, 6), dpi=80)
                rs = by_target[T]
                ax.scatter([r["c"]["x"] for r in rs], [r["c"]["y"] for r in rs], c=[r["hbi"] for r in rs], s=2, marker="s", vmin=1, vmax=2.2)
                ax.set_aspect("equal"); ax.set_title(f"FAKE {T}")
                fig.savefig(P(f"map_{T}.png")); plt.close(fig)
        except ImportError:
            pass

    with open(P("deck_inputs.json"), "w", encoding="utf-8") as f:
        json.dump({"team_name": "테스트팀", "visit_dates": ["2026-10-13", "2026-10-14", "2026-10-15", "2026-10-16", "2026-10-19"]},
                  f, ensure_ascii=False, indent=1)
    with open(P(FAKE_MARKER), "w", encoding="utf-8") as f:
        f.write("이 폴더의 파일은 tools/make_fake_results.py 가 만든 가짜(테스트) 데이터입니다.\n제출물에 절대 쓰지 마세요.\n"
                f"옵션: {'--partial' if a.partial else '전체'}, seed={a.seed}\n")
    print(f"가짜 결과 {len(os.listdir(out))}개 파일 → {os.path.relpath(out, ROOT)}  (격자 {len(cells)}칸 × 목적지 {len(TARGETS)}종"
          + (", --partial" if a.partial else "") + ")")


if __name__ == "__main__":
    main()
