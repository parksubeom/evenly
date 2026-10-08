# -*- coding: utf-8 -*-
"""
tools/merge_exports.py ─ [안심구역 밖] 1차 방문(v4)에서 구역별로 따로 돌린 반출 결과 4개 → 하나의 반출 폴더로 합치기

[왜]  v4 는 "가장 큰 길 연결망 하나"만 남겨서, 서로 떨어진 5개 구를 한 번에 돌리면 구 묶음 하나만 남습니다.
      그래서 1차 방문에서는 구역(종로·중 / 관악 / 광진 / 강서)마다 AREA_BBOX 를 바꿔 02→05 를 따로 돌리고
      output 을 구역별로 반출합니다 (docs/1차방문_안내서.md). 이 도구가 그 4개를 합칩니다.
[실행]
  python3 tools/merge_exports.py --zone A=results/raw_export_zones/A --zone B=results/raw_export_zones/B \\
                                 --zone C=results/raw_export_zones/C --zone D=results/raw_export_zones/D \\
                                 [--out results/raw_export]
  구역 이름: A = 종로구·중구, B = 관악구, C = 광진구, D = 강서구 (구역 bbox 는 대상 구 + 1,000m 라 옆 구 건물도 조금 들어 있음)
[합치는 규칙]
  - 격자(grid_hbi.csv)·행정동(dong_hbi.csv)·결합(join_*)·필지(parcel_by_legal_dong): 각 구역의 **대상 구 안** 것만 남겨 이어 붙임
    (격자는 격자 중심이 대상 구 행정동 안, 동·법정동은 코드 앞 5자리가 대상 구)
  - summary.csv: 남긴 격자로 다시 셈 (건물 수 = n_bld 합, 1.8 이상 = n_bld × share_high 합, 연면적 = weight 합).
    건물 5개 미만 격자는 원래 반출에서 빠졌으므로 그만큼 적게 셈. 중앙값 지표는 합칠 수 없어 넣지 않음
  - validation_sites.csv: 선정지가 들어 있는 구역의 행을 쓰고, 백분위는 **합친 격자 전체** 기준으로 다시 계산
  - validation_new_candidates.csv: 합친 의료시설 격자로 다시 뽑음 (선정지 최저 HBI 초과, 모든 선정지에서 500m 초과, 상위 30)
  - validation_routes.csv: 출발·도착이 모두 그 구역 bbox 안, 잘린 선에서 500m 이상 안쪽인 구역의 행만
    (그 밖의 구역 행은 구역 안의 엉뚱한 노드에 붙어 계산된 값. 대현산처럼 구 경계를 넘는 구간도 bbox 안이면 씀)
  - validation_ablation.csv·sensitivity.csv: 구역별 값을 구역 분석 건물 수로 가중 평균 (근사)
  - join_summary.csv: 합친 join_<이름>.csv 로 상관계수를 다시 계산
[결과] --out 폴더 (기본 results/raw_export) + merge_notes.txt (구역별 행 수, 근사한 항목)
"""
import csv, math, os, shutil, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from evenly_common import ROOT, load_dongs, dong_of, load_sites, read_csv, write_csv, num, truthy, is_fake_dir, mark_fake, refuse_raw_export, source_of, mark_source, PUBLIC_REHEARSAL

ZONES = {"A": ["종로구", "중구"], "B": ["관악구"], "C": ["광진구"], "D": ["강서구"]}
# 1차 방문 구역별 AREA_BBOX (EPSG:5186, 대상 구 범위 + 1,000m, 100m 단위). docs/1차방문_안내서.md 와 같은 값
ZONE_BBOX = {"A": [194500, 548300, 203400, 560200], "B": [190100, 536300, 200000, 545000],
             "C": [203900, 546100, 211100, 553700], "D": [178200, 546400, 190500, 557200]}
EDGE = 500   # config.EDGE_BUFFER
HI = 1.8


def parse_args(argv):
    zones, out = {}, os.path.join(ROOT, "results", "raw_export")
    i = 0
    while i < len(argv):
        if argv[i] == "--zone":
            k, v = argv[i + 1].split("=", 1)
            if k not in ZONES:
                raise SystemExit(f"구역 이름은 {list(ZONES)} 중 하나: {k}")
            zones[k] = os.path.abspath(v)
        elif argv[i] == "--out":
            out = os.path.abspath(argv[i + 1])
        elif argv[i] in ("-h", "--help"):
            raise SystemExit(__doc__)
        else:
            raise SystemExit(f"모르는 옵션: {argv[i]}")
        i += 2
    if not zones:
        raise SystemExit(__doc__)
    return zones, out


def rank(v):
    o = sorted(range(len(v)), key=lambda i: v[i])
    r = [0.0] * len(v)
    i = 0
    while i < len(o):
        j = i
        while j + 1 < len(o) and v[o[j + 1]] == v[o[i]]:
            j += 1
        for k in range(i, j + 1):
            r[o[k]] = (i + j) / 2
        i = j + 1
    return r


def pearson(a, b):
    n = len(a)
    if n < 3:
        return None
    ma, mb = sum(a) / n, sum(b) / n
    sab = sum((x - ma) * (y - mb) for x, y in zip(a, b))
    saa = sum((x - ma) ** 2 for x in a); sbb = sum((y - mb) ** 2 for y in b)
    return sab / math.sqrt(saa * sbb) if saa > 0 and sbb > 0 else None


def main():
    zones, out = parse_args(sys.argv[1:])
    if os.path.abspath(out) in zones.values():
        raise SystemExit("--out 은 구역 폴더와 달라야 합니다")
    kind = {z: source_of(d) for z, d in zones.items()}                # 출처 표지: fake / public_rehearsal / "" (실제)
    fake_in = [z for z, k in kind.items() if k == "fake"]              # 하나라도 가짜면 결과도 가짜
    reh_in = [z for z, k in kind.items() if k == PUBLIC_REHEARSAL]     # [v6.1] 공개 대역 리허설
    real_in = [z for z, k in kind.items() if not k]
    if (fake_in or reh_in) and real_in:
        raise SystemExit(f"!! 실제 구역 {real_in} 과 가짜·공개 대역 구역 {fake_in + reh_in} 을 섞어 합치지 않습니다")
    if fake_in and reh_in:
        raise SystemExit(f"!! 가짜 구역 {fake_in} 과 공개 대역 구역 {reh_in} 을 섞어 합치지 않습니다")
    if fake_in:
        refuse_raw_export(out, f"입력 구역 {fake_in} 이 가짜(_source.txt=fake) 입니다")
    if reh_in:
        refuse_raw_export(out, f"입력 구역 {reh_in} 이 공개 대역 리허설(_source.txt=public_rehearsal) 입니다")
    os.makedirs(out, exist_ok=True)
    dongs = load_dongs(sum(ZONES.values(), []))
    gu_code = {}
    for d in dongs:
        gu_code.setdefault(d["gu"], d["adm_cd"][:5])
    notes = [f"merge_exports: 구역 {', '.join(f'{k}={v}' for k, v in zones.items())}"]
    P = lambda z, n: os.path.join(zones[z], n)
    zone_of_xy = {}

    def in_zone(z, x, y):
        k = (z, round(x), round(y))
        if k not in zone_of_xy:
            d = dong_of(x, y, dongs)
            zone_of_xy[k] = bool(d and d["gu"] in ZONES[z])
        return zone_of_xy[k]

    # ── 격자 ──
    grid, head = [], None
    for z in zones:
        rows = read_csv(P(z, "grid_hbi.csv")) or []
        keep = [r for r in rows if in_zone(z, num(r["cell_x"]), num(r["cell_y"]))]
        head = head or (list(rows[0].keys()) if rows else None)
        grid += keep
        notes.append(f"grid_hbi.csv  구역 {z}: {len(rows)}행 중 대상 구 안 {len(keep)}행")
    if head:
        write_csv(os.path.join(out, "grid_hbi.csv"), head, [[r[h] for h in head] for r in grid])

    # ── 행정동·결합·필지: 코드 앞 5자리로 대상 구만 ──
    def by_code(name, col):
        allr, hd = [], None
        for z in zones:
            rows = read_csv(P(z, name)) or []
            pre = {gu_code[g] for g in ZONES[z]}
            keep = [r for r in rows if str(r.get(col, ""))[:5] in pre]
            hd = hd or (list(rows[0].keys()) if rows else None)
            allr += keep
            notes.append(f"{name}  구역 {z}: {len(rows)}행 중 대상 구 {len(keep)}행")
        if hd:
            write_csv(os.path.join(out, name), hd, [[r[h] for h in hd] for r in allr])
        return allr
    by_code("dong_hbi.csv", "adm_cd")
    by_code("parcel_by_legal_dong.csv", "emd_cd")
    jnames = sorted({f for z in zones for f in os.listdir(zones[z]) if f.startswith("join_") and f != "join_summary.csv"})
    js = []
    for jn in jnames:
        rows = by_code(jn, "adm_cd")
        name = jn[5:-4]
        pts = [(num(r["hbi_mean"]), num(r["share_high"]), num(r.get(name))) for r in rows]
        pts = [p for p in pts if None not in p]
        if len(pts) >= 5:
            h, sh, v = [p[0] for p in pts], [p[1] for p in pts], [p[2] for p in pts]
            js += [[name, "결합 행정동 수", len(pts)], [name, "HBI 평균 vs 값: 피어슨 상관", round(pearson(h, v), 3)],
                   [name, "HBI 평균 vs 값: 스피어만 순위상관", round(pearson(rank(h), rank(v)), 3)],
                   [name, "고위험 비율 vs 값: 스피어만 순위상관", round(pearson(rank(sh), rank(v)), 3)]]
    if js:
        write_csv(os.path.join(out, "join_summary.csv"), ["data", "metric", "value"], js)
        notes.append("join_summary.csv: 합친 join_*.csv 로 상관계수 다시 계산 (구역 파일의 4분위 평균은 넣지 않음)")

    # ── summary (남긴 격자로 다시 셈) ──
    summ = []
    for t in sorted({r["target"] for r in grid}):
        cs = [r for r in grid if r["target"] == t]
        nb = sum(num(r["n_bld"]) for r in cs)
        hi = sum(num(r["n_bld"]) * num(r["share_high"]) for r in cs)
        wt = sum(num(r["weight"]) for r in cs)
        summ += [[t, "분석 건물 수", round(nb)], [t, f"HBI {HI} 이상 건물 수", round(hi)], [t, f"HBI {HI} 이상 비율", round(hi / nb, 3) if nb else ""],
                 [t, "분석 건물 연면적 합(㎡)", round(wt)]]
    write_csv(os.path.join(out, "summary.csv"), ["target", "metric", "value"], summ)
    notes.append("summary.csv: 대상 구 격자에서 다시 셈 (건물 5개 미만 격자는 원래 반출에 없어 빠짐). 중앙값 지표는 합칠 수 없어 없음")

    # ── 필지 요약: 수는 더하고, 비율은 '대' 필지 수로 가중 ──
    pn = pd = pw = 0.0
    for z in zones:
        m = {r["metric"]: num(r["value"]) for r in read_csv(P(z, "parcel_summary.csv")) or []}
        if m:
            pn += m.get("HBI 산출 필지 수") or 0; d_ = m.get("그중 지목 '대' 필지 수") or 0; pd += d_
            pw += (m.get("'대' 필지 HBI 1.8 이상 비율") or 0) * d_
    if pn:
        write_csv(os.path.join(out, "parcel_summary.csv"), ["metric", "value"],
                  [["HBI 산출 필지 수", round(pn)], ["그중 지목 '대' 필지 수", round(pd)], ["'대' 필지 HBI 1.8 이상 비율", round(pw / pd, 3) if pd else ""]])
        notes.append("parcel_summary.csv: 구역 합 (확장 띠의 옆 구 필지도 포함된 근사)")

    # ── 선정지: 들어 있는 구역의 행, 백분위는 합친 의료시설 격자 기준으로 다시 ──
    med = [num(r["hbi_mean"]) for r in grid if r["target"] == "medical"]
    sites = load_sites()
    vs = []
    for s in sites:
        z = next((z for z in zones if in_zone(z, s["x"], s["y"])), None)
        r = next((r for r in (read_csv(P(z, "validation_sites.csv")) or []) if r["name"] == s["name"]), None) if z else None
        h = num(r.get("hbi_mean")) if r else None
        if h is None or h != h:                          # 빈 칸·nan
            vs.append([s["name"], r.get("n_bld", "") if r else "", "", "", "", ""])
            continue
        pct = sum(1 for v in med if v < h) / len(med) if med else None
        vs.append([s["name"], r["n_bld"], round(h, 3), r.get("share_high", ""), round(pct, 3) if pct is not None else "", (pct >= 0.9) if pct is not None else ""])
        notes.append(f"validation_sites: {s['name']} ← 구역 {z}, 구역 백분위 {r.get('percentile')} → 합친 격자 백분위 {round(pct, 3) if pct is not None else '-'}")
    write_csv(os.path.join(out, "validation_sites.csv"), ["name", "n_bld", "hbi_mean", "share_high", "percentile", "top10"], vs)
    sh = [v[2] for v in vs if v[2] != ""]
    if sh and med:
        thr = min(sh)
        cand = []
        for r in grid:
            if r["target"] != "medical":
                continue
            x, y, h = num(r["cell_x"]), num(r["cell_y"]), num(r["hbi_mean"])
            if h > thr and all(math.hypot(x - s["x"], y - s["y"]) > 500 for s in sites):
                cand.append((h, x, y, r["n_bld"]))
        cand.sort(reverse=True)
        write_csv(os.path.join(out, "validation_new_candidates.csv"), ["cell_x", "cell_y", "hbi_mean", "n_bld"],
                  [[x, y, round(h, 3), n] for h, x, y, n in cand[:30]])
        notes.append(f"validation_new_candidates.csv: 합친 격자에서 다시 뽑음 (선정지 최저 HBI {thr} 초과 {len(cand)}곳 중 상위 30)")

    # ── 구간: 출발·도착이 모두 그 구역 대상 구 안인 행만 ──
    od = {r["name"]: r for r in read_csv(os.path.join(ROOT, "analysis", "hbi", "external", "od_pairs.csv")) or []}
    rt, hd = [], None
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from evenly_common import to5186
    for z in zones:
        rows = read_csv(P(z, "validation_routes.csv")) or []
        hd = hd or (list(rows[0].keys()) if rows else None)
        for r in rows:
            o = od.get(r["name"])
            if not o or not all((o.get(k) or "").strip() for k in ("o_lon", "o_lat", "d_lon", "d_lat")):
                continue
            ox, oy = to5186(float(o["o_lon"]), float(o["o_lat"])); dx, dy = to5186(float(o["d_lon"]), float(o["d_lat"]))
            b = ZONE_BBOX[z]
            inner = lambda x, y: min(x - b[0], b[2] - x, y - b[1], b[3] - y) >= EDGE
            if inner(ox, oy) and inner(dx, dy):
                rt.append(r)
                notes.append(f"validation_routes: {r['name']} ← 구역 {z}")
    if hd:
        write_csv(os.path.join(out, "validation_routes.csv"), hd, [[r[h] for h in hd] for r in rt])

    # ── 가중 평균 (구역 분석 건물 수) ──
    w = {}
    for z in zones:
        s0 = {(r["target"], r["metric"]): num(r["value"]) for r in read_csv(P(z, "summary.csv")) or []}
        w[z] = s0.get(("medical", "분석 건물 수")) or 0
    for name, keycols, valcols in [("validation_ablation.csv", ["scenario", "metric"], ["value"]),
                                   ("sensitivity.csv", ["scenario"], None)]:
        acc, hd = {}, None
        for z in zones:
            rows = read_csv(P(z, name)) or []
            if not rows:
                continue
            hd = hd or list(rows[0].keys())
            vc = valcols or [c for c in hd if c not in keycols]
            for r in rows:
                k = tuple(r[c] for c in keycols)
                a = acc.setdefault(k, {c: [0.0, 0.0] for c in vc})
                for c in vc:
                    v = num(r.get(c))
                    if v is not None and w[z]:
                        a[c][0] += v * w[z]; a[c][1] += w[z]
        if acc:
            vc = valcols or [c for c in hd if c not in keycols]
            write_csv(os.path.join(out, name), keycols + vc,
                      [list(k) + [round(a[c][0] / a[c][1], 3) if a[c][1] else "" for c in vc] for k, a in acc.items()])
            notes.append(f"{name}: 구역별 값을 구역 분석 건물 수({', '.join(f'{z}={int(w[z])}' for z in zones)})로 가중 평균 (근사)")

    # ── 그대로 복사하는 것 (구역 이름을 붙여서) ──
    for z in zones:
        for f in os.listdir(zones[z]):
            if f.endswith((".gpkg", ".png")):
                shutil.copy2(P(z, f), os.path.join(out, f"{z}_{f}"))
    notes.append("grid_hbi_*.gpkg·map_*.png: 구역 이름을 앞에 붙여 복사 (A_grid_hbi_medical.gpkg …). QGIS 에서 함께 열면 됨")
    if fake_in:
        mark_fake(out, f"merge_exports: 가짜 입력 구역 {fake_in}")
        notes.append(f"출처: 가짜 (입력 구역 {fake_in} 이 fake) → _source.txt=fake")
    if reh_in:
        mark_source(out, PUBLIC_REHEARSAL, f"merge_exports: 공개 대역 입력 구역 {reh_in}")
        notes.append(f"출처: 공개 대역 리허설 (입력 구역 {reh_in}) → _source.txt=public_rehearsal")
    with open(os.path.join(out, "merge_notes.txt"), "w", encoding="utf-8") as f:
        f.write("\n".join(notes) + "\n")
    print("\n".join(notes))
    print(f"→ {out}")


if __name__ == "__main__":
    main()
