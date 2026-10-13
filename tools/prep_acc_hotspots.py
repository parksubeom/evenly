# -*- coding: utf-8 -*-
"""
tools/prep_acc_hotspots.py ─ [안심구역 밖] 도로교통공단 교통사고다발지역 → 서울 '보행노인' 사고다발지 (점·행정동)

[실행]  python3 tools/prep_acc_hotspots.py [data_public/raw/한국도로교통공단_교통사고다발지역.csv] [--recent 2020] [--out-dir data_public]
[읽는 것] 공공데이터포털 "한국도로교통공단_교통사고다발지역" CSV (UTF-8): 사고연도, 사고유형구분(보행노인·보행어린이·자전거·스쿨존어린이),
          사고다발지역시도시군구, 사고지역위치명, 사고건수·사상자수·사망자수·중상자수·경상자수·부상신고자수, 위도·경도(가운데 점), 폴리곤(반경 200m 원)
[하는 일]
  1. 사고유형구분 = "보행노인" 이고 사고다발지역시도시군구가 "서울특별시" 로 시작하는 행만 (다른 유형·지역은 쓰지 않음)
  2. 가운데 점(위도·경도)이 우리 동 경계(analysis/hbi/external/dong_boundary.geojson) 어느 행정동 안인지 붙임 (점-다각형, 경계 밖이면 빈 칸)
  3. 같은 자리가 여러 해 다발지로 뽑힌 것을 하나로 묶음: 가운데 점끼리 100m 안이면 같은 자리(spot_id) — 반경 200m 원의 절반
  4. 동마다: 다발지 행 수(해×자리), 서로 다른 자리 수, 최근(--recent 부터) 자리 수·사고건수·사상자수
[결과] <out-dir>/acc_elder_ped_seoul.csv (행마다 점, 폴리곤 칸은 뺌), <out-dir>/acc_elder_ped_dong.csv (서울 426개 동, 다발지 없는 동은 0)
[주의] 다발지 = 그 해 같은 반경 안 사고가 기준 건수 이상인 곳 (도로교통공단 선정). 큰길·역 부근에 몰리고, 사고가 적은 골목·계단은 거의 뽑히지 않음
"""
import argparse, csv, json, math, os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TYPE, SIDO = "보행노인", "서울특별시"
SAME_M = 100.0


def rings(geom):
    if geom["type"] == "Polygon":
        return [geom["coordinates"]]
    return geom["coordinates"]                    # MultiPolygon


def inside(lon, lat, polys):
    for poly in polys:
        hit = False
        for k, ring in enumerate(poly):            # 첫 고리 = 바깥, 나머지 = 구멍
            c = False
            for (x1, y1), (x2, y2) in zip(ring, ring[1:] + ring[:1]):
                if (y1 > lat) != (y2 > lat) and lon < (x2 - x1) * (lat - y1) / (y2 - y1) + x1:
                    c = not c
            if k == 0:
                hit = c
                if not hit:
                    break
            elif c:
                hit = False
                break
        if hit:
            return True
    return False


def dist_m(a, b):
    la = math.radians((a[1] + b[1]) / 2)
    return math.hypot((a[0] - b[0]) * 111320 * math.cos(la), (a[1] - b[1]) * 110540)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("src", nargs="?", default=os.path.join(ROOT, "data_public", "raw", "한국도로교통공단_교통사고다발지역.csv"))
    ap.add_argument("--recent", type=int, default=2020, help="최근 몇 년부터 따로 셀지 (기본 2020 → 2020~2024 다섯 해)")
    ap.add_argument("--out-dir", default=os.path.join(ROOT, "data_public"))
    a = ap.parse_args()
    g = json.load(open(os.path.join(ROOT, "analysis", "hbi", "external", "dong_boundary.geojson"), encoding="utf-8"))
    dongs = []
    for f in g["features"]:
        ps = rings(f["geometry"])
        xs = [p[0] for poly in ps for p in poly[0]]
        ys = [p[1] for poly in ps for p in poly[0]]
        dongs.append((f["properties"]["ADM_CD"], f["properties"]["adm_nm"], ps, (min(xs), min(ys), max(xs), max(ys))))
    allr = list(csv.DictReader(open(a.src, encoding="utf-8-sig")))
    rows = [r for r in allr if r["사고유형구분"] == TYPE and r["사고다발지역시도시군구"].startswith(SIDO)]
    out = []
    for r in rows:
        lon, lat = float(r["경도"]), float(r["위도"])
        cd = nm = ""
        for c, n, ps, (x0, y0, x1, y1) in dongs:
            if x0 <= lon <= x1 and y0 <= lat <= y1 and inside(lon, lat, ps):
                cd, nm = c, n
                break
        out.append({"acc_id": r["사고지역관리번호"], "year": int(r["사고연도"]), "gu": r["사고다발지역시도시군구"].split()[1].rstrip("0123456789"),
                    "place": r["사고지역위치명"], "n_acc": int(r["사고건수"]), "n_cas": int(r["사상자수"]), "n_dead": int(r["사망자수"]),
                    "n_serious": int(r["중상자수"]), "n_minor": int(r["경상자수"]), "n_report": int(r["부상신고자수"]),
                    "lat": lat, "lon": lon, "adm_cd": cd, "adm_nm": nm, "base_date": r["데이터기준일자"]})
    # 같은 자리 묶기 (100m 안, 이어지면 한 묶음)
    par = list(range(len(out)))
    def root(i):
        while par[i] != i:
            par[i] = par[par[i]]
            i = par[i]
        return i
    pts = [(o["lon"], o["lat"]) for o in out]
    for i in range(len(out)):
        for j in range(i + 1, len(out)):
            if abs(pts[i][1] - pts[j][1]) < 0.002 and dist_m(pts[i], pts[j]) <= SAME_M:
                par[root(i)] = root(j)
    ids = {}
    for i, o in enumerate(out):
        o["spot_id"] = ids.setdefault(root(i), len(ids) + 1)
    os.makedirs(a.out_dir, exist_ok=True)
    p1 = os.path.join(a.out_dir, "acc_elder_ped_seoul.csv")
    with open(p1, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(out[0]))
        w.writeheader()
        w.writerows(sorted(out, key=lambda o: (o["year"], o["acc_id"])))
    yrs = sorted({o["year"] for o in out})
    rec = [o for o in out if o["year"] >= a.recent]
    dl = []
    for c, n, _, _ in dongs:
        mine = [o for o in out if o["adm_cd"] == c]
        mr = [o for o in mine if o["year"] >= a.recent]
        dl.append({"adm_cd": c, "adm_nm": n, "n_rows": len(mine), "n_spots": len({o["spot_id"] for o in mine}),
                   f"n_spots_{a.recent}": len({o["spot_id"] for o in mr}), f"acc_{a.recent}": sum(o["n_acc"] for o in mr),
                   f"cas_{a.recent}": sum(o["n_cas"] for o in mr), "years": f"{yrs[0]}~{yrs[-1]}", "recent_from": a.recent})
    p2 = os.path.join(a.out_dir, "acc_elder_ped_dong.csv")
    with open(p2, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(dl[0]))
        w.writeheader()
        w.writerows(dl)
    nout = sum(1 for o in out if not o["adm_cd"])
    gw = [o for o in out if o["gu"] == "관악구"]
    print(f"원본 {len(allr):,}행 중 {TYPE}·{SIDO} {len(out):,}행 ({yrs[0]}~{yrs[-1]}), 서로 다른 자리 {len(ids):,}곳, 동 경계 밖 {nout}행"
          f" · 최근({a.recent}~) {len(rec)}행")
    print(f"  관악구: {len(gw)}행, 자리 {len({o['spot_id'] for o in gw})}곳, 최근 {sum(1 for o in gw if o['year'] >= a.recent)}행"
          f" · 구 이름과 붙은 동의 구가 다른 행 {sum(1 for o in out if o['adm_nm'] and o['gu'] not in o['adm_nm'])}")
    print(f"→ {os.path.relpath(p1, ROOT)}, {os.path.relpath(p2, ROOT)}")


if __name__ == "__main__":
    main()
