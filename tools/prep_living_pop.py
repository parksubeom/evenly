# -*- coding: utf-8 -*-
"""
tools/prep_living_pop.py ─ [안심구역 밖] 서울 생활인구(행정동, 내국인) → 65세 이상 외출 지수 (공개 자료판, SKT 대신)

[실행]  python3 tools/prep_living_pop.py [data_public/raw/LOCAL_PEOPLE_DONG_202607.zip] [--prefix 1162] [--out data_public/living65_outing.csv]
[읽는 것] 서울 열린데이터광장 "서울 생활인구 (행정동 단위, 내국인)" LOCAL_PEOPLE_DONG_YYYYMM.csv (zip 그대로 됨, UTF-8)
          칸: 기준일ID, 시간대구분(00~23), 행정동코드(8자리), 총생활인구수, 남자·여자 연령대별 생활인구수 (… 65세부터69세, 70세이상)
[코드 대조] 생활인구의 행정동코드 = 우리 동 경계(analysis/hbi/external/dong_boundary.geojson) ADM_CD(10자리) 의 앞 8자리.
          생활인구는 2016년 기준 행정동 코드라서 그 뒤 바뀐 동(강북구 번·수유동 번호, 구로 항동, 강남 개포3동, 강동 상일1·2동)은 맞지 않음
          → 고른 구(--prefix) 안에서 하나라도 안 맞으면 멈춤 (관악구 1162 는 21개 동 모두 맞음, 2026.7 파일로 확인)
[외출 지수] 생활인구는 "그 시각 그 동에 있는 사람 수" 라서, 새벽(3~5시) 65세 이상 = 사는 어르신, 낮(10~17시) 65세 이상 = 그 시각 동에 있는 어르신으로 보고
          외출 지수 = 1 − 낮 평균 ÷ 새벽 평균  (낮에 동을 비우는 어르신의 순비율. 클수록 많이 나감)
          · 동 안에서 다니는 외출은 보이지 않고, 다른 동 어르신이 들어오면 작아짐 (시장·역이 있는 동은 음수도 됨) → 보조 지표, 상관 관찰만
          · 전체 날짜와 평일(월~금, 공휴일은 따로 빼지 않음) 두 가지. 새벽 평균 ÷ 주민등록 65세 이상(data_public/elderly_pop.csv)도 함께 (거주 대리값 점검)
[결과] data_public/living65_outing.csv (adm_cd, adm_nm, lp_code, base_ym, night65, day65, outing_index, night65_wd, day65_wd, outing_index_wd, pop65_reg, night_vs_reg)
"""
import argparse, csv, datetime, io, json, os, sys, zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
NIGHT = {"03", "04"}                            # 03:00~04:59
DAY = {f"{h:02d}" for h in range(10, 17)}       # 10:00~16:59
OLD = ("남자65세부터69세생활인구수", "남자70세이상생활인구수", "여자65세부터69세생활인구수", "여자70세이상생활인구수")


def open_rows(path):
    if path.lower().endswith(".zip"):
        z = zipfile.ZipFile(path)
        name = next(n for n in z.namelist() if n.lower().endswith(".csv"))
        return csv.reader(io.TextIOWrapper(z.open(name), encoding="utf-8-sig", newline="")), name
    return csv.reader(open(path, encoding="utf-8-sig", newline="")), os.path.basename(path)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("src", nargs="?", default=os.path.join(ROOT, "data_public", "raw", "LOCAL_PEOPLE_DONG_202607.zip"))
    ap.add_argument("--prefix", default="1162", help="행정동코드 앞자리 (1162 = 관악구)")
    ap.add_argument("--out", default=os.path.join(ROOT, "data_public", "living65_outing.csv"))
    a = ap.parse_args()
    g = json.load(open(os.path.join(ROOT, "analysis", "hbi", "external", "dong_boundary.geojson"), encoding="utf-8"))
    bd = {f["properties"]["ADM_CD"][:8]: (f["properties"]["ADM_CD"], f["properties"]["adm_nm"]) for f in g["features"]}
    rd, name = open_rows(a.src)
    head = next(rd)
    ix = {k: head.index(k) for k in ("기준일ID", "시간대구분", "행정동코드")}
    io_ = [head.index(k) for k in OLD]
    acc = {}                                     # code → {(night/day, wd): [합, 칸 수]}
    days, codes_all = set(), set()
    for r in rd:
        cd = r[ix["행정동코드"]]
        codes_all.add(cd)
        if not cd.startswith(a.prefix):
            continue
        h, d = r[ix["시간대구분"]], r[ix["기준일ID"]]
        part = "night" if h in NIGHT else ("day" if h in DAY else None)
        if part is None:
            continue
        days.add(d)
        wd = datetime.date(int(d[:4]), int(d[4:6]), int(d[6:])).weekday() < 5
        v = sum(float(r[i] or 0) for i in io_)
        for key in ((part, "all"), (part, "wd") if wd else None):
            if key:
                s = acc.setdefault(cd, {}).setdefault(key, [0.0, 0])
                s[0] += v
                s[1] += 1
    mine = sorted(acc)
    gu_b = sorted(k for k in bd if k.startswith(a.prefix))
    miss_b, miss_l = [k for k in gu_b if k not in acc], [k for k in mine if k not in bd]
    print(f"{name}: 행정동 코드 {len(codes_all)}개 (서울), 그중 {a.prefix}… {len(mine)}개 · 우리 경계 {a.prefix}… {len(gu_b)}개 · 날짜 {len(days)}일 ({min(days)}~{max(days)})")
    if miss_b or miss_l:
        print(f"!! 코드가 맞지 않음: 경계에만 {[(k, bd[k][1]) for k in miss_b]} / 생활인구에만 {miss_l} → 멈춤 (구가 바뀐 동이면 대응표를 먼저 만들 것)")
        sys.exit(1)
    pop = {r["adm_cd"]: float(r["pop65"]) for r in csv.DictReader(open(os.path.join(ROOT, "data_public", "elderly_pop.csv"), encoding="utf-8-sig")) if r.get("pop65")}
    ym = min(days)[:6]
    rows = []
    for cd in mine:
        m = acc[cd]
        mean = lambda k: m[k][0] / m[k][1] if k in m and m[k][1] else None
        n_a, d_a, n_w, d_w = mean(("night", "all")), mean(("day", "all")), mean(("night", "wd")), mean(("day", "wd"))
        full, nm = bd[cd]
        reg = pop.get(full)
        rows.append({"adm_cd": full, "adm_nm": nm, "lp_code": cd, "base_ym": ym,
                     "night65": round(n_a, 1), "day65": round(d_a, 1), "outing_index": round(1 - d_a / n_a, 4),
                     "night65_wd": round(n_w, 1), "day65_wd": round(d_w, 1), "outing_index_wd": round(1 - d_w / n_w, 4),
                     "pop65_reg": int(reg) if reg else "", "night_vs_reg": round(n_a / reg, 3) if reg else ""})
    os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
    with open(a.out, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    oi = sorted(r["outing_index"] for r in rows)
    nv = sorted(r["night_vs_reg"] for r in rows if r["night_vs_reg"] != "")
    print(f"→ {os.path.relpath(a.out, ROOT)}: {len(rows)}개 동 · 외출 지수 {oi[0]:+.3f} ~ {oi[-1]:+.3f} (중앙값 {oi[len(oi) // 2]:+.3f})"
          + (f" · 새벽 65세 이상 ÷ 주민등록 65세 이상 {nv[0]:.2f} ~ {nv[-1]:.2f}" if nv else ""))


if __name__ == "__main__":
    main()
