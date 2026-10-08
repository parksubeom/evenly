# -*- coding: utf-8 -*-
"""
demo/build_demo.py ─ 반출 결과(grid_hbi.csv 등) → 본선 데모 화면 demo/evenly_demo.html (파일 하나, 외부 요청 없음)

[실행]  python3 demo/build_demo.py                            (기본: results/raw_export, 실제 결과)
        python3 demo/build_demo.py --src results/fake_export   (가짜 결과로 시험 → 상단에 "테스트 데이터" 경고)
[쓰는 파일]  grid_hbi.csv (필수), validation_sites.csv, validation_new_candidates.csv (있으면)
[배경]  DEM 음영 대신 공개 행정동 경계(analysis/hbi/external/dong_boundary.geojson)만 그립니다.
[틀]    demo/evenly_template.html 의 __DATA__ 자리에 데이터를 넣습니다. 표준 라이브러리만 사용.
"""
import argparse, json, math, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "tools"))
from evenly_common import (ROOT, TARGET_GU, TARGET_LABEL, FAKE_MARKER, RAW_EXPORT, is_fake_dir, source_of, PUBLIC_REHEARSAL, load_dongs, load_sites, dong_of, simplify, read_csv, num, truthy)

SHORT = {"중곡": "광진구 중곡동 (무지개계단)", "화곡": "강서구 화곡동", "봉천": "관악구 봉천동 (비안어린이공원)", "숭인": "종로구 숭인동 (창신역 일대 계단)", "신당": "중구 신당동 (청구동 마을마당)"}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", default=os.path.join(ROOT, "results", "raw_export"))
    ap.add_argument("--out", default=os.path.join(HERE, "evenly_demo.html"))
    a = ap.parse_args()
    src = os.path.abspath(a.src)
    fake = is_fake_dir(src) or os.path.basename(src) == "fake_export"
    # [v6.1] 공개 대역 리허설: 띠를 달고, 기본 출력(evenly_demo.html) 대신 evenly_demo_rehearsal.html 에 씀
    reh = not fake and PUBLIC_REHEARSAL in (source_of(src), source_of(os.path.dirname(src)))
    if not fake and not reh and not os.path.realpath(src).startswith(os.path.realpath(RAW_EXPORT)):
        raise SystemExit(f"!! 표지 없는 폴더는 results/raw_export 에서만 (실제 결과): {os.path.relpath(src, ROOT)}")
    if reh and os.path.abspath(a.out) == os.path.join(HERE, "evenly_demo.html"):
        a.out = os.path.join(HERE, "evenly_demo_rehearsal.html")
    grid = read_csv(os.path.join(src, "grid_hbi.csv"))
    if not grid:
        raise SystemExit(f"grid_hbi.csv 가 없습니다: {src}")

    dongs = load_dongs(TARGET_GU)
    ox = int(min(d["bbox"][0] for d in dongs)) // 1000 * 1000
    oy = int(min(d["bbox"][1] for d in dongs)) // 1000 * 1000
    dmeta, dout = [], []
    for d in dongs:
        rings = []
        for r in d["rings"]:
            s = simplify(r, 12.0)
            rings.append([v for x, y in s for v in (round(x - ox), round(y - oy))])
        dout.append({"gu": d["gu"], "r": rings})
        dmeta.append({"gu": d["gu"], "nm": d["adm_nm"].split()[-1]})
    didx = {id(d): i for i, d in enumerate(dongs)}

    targets = [t for t in ["medical", "bus", "station", "station_ev", "elderly", "pharmacy"] if any(g["target"] == t for g in grid)]
    cells, tmax = {}, {}
    cache = {}
    for g in grid:
        t = g["target"]
        x, y = num(g["cell_x"]), num(g["cell_y"])
        h, e, f = num(g["hbi_mean"]), num(g["elder_min"]), num(g["flat_min"])
        if None in (x, y, h, e, f):
            continue
        key = (x, y)
        if key not in cache:
            d = dong_of(x, y, dongs)
            cache[key] = didx[id(d)] if d else -1
        di = cache[key]
        if di < 0:
            continue
        cells.setdefault(t, []).append([round(x), round(y), round(h, 3), round(e, 1), round(f, 1), round(num(g.get("share_high")) or 0, 3), int(num(g["n_bld"]) or 0), di])
    for t, cs in cells.items():
        es = sorted(c[3] for c in cs)
        tmax[t] = max(10, int(math.ceil(es[int(len(es) * 0.95)] / 5) * 5))       # 색 범위: 경사 반영 시간 95% 지점

    gubbox = {}
    for gname in TARGET_GU:
        ds = [d for d in dongs if d["gu"] == gname]
        gubbox[gname] = [min(d["bbox"][0] for d in ds), min(d["bbox"][1] for d in ds), max(d["bbox"][2] for d in ds), max(d["bbox"][3] for d in ds)]
    bbox = [min(b[0] for b in gubbox.values()), min(b[1] for b in gubbox.values()), max(b[2] for b in gubbox.values()), max(b[3] for b in gubbox.values())]

    vs = read_csv(os.path.join(src, "validation_sites.csv")) or []
    sites = []
    for s in load_sites():
        k = next((k for k in SHORT if k in s["name"]), None)
        r = next((v for v in vs if k and k in v.get("name", "")), None)
        d = dong_of(s["x"], s["y"], dongs)
        sites.append({"name": SHORT.get(k, s["name"]), "short": s["name"].split()[1] if len(s["name"].split()) > 1 else s["name"],
                      "x": round(s["x"]), "y": round(s["y"]), "r": s["radius"], "gu": d["gu"] if d else s["name"].split()[0],
                      # v5 는 같은 반경 원끼리 비교한 percentile_circle 을 우선
                      "pct": (num(r.get("percentile_circle")) if num(r.get("percentile_circle")) is not None else num(r.get("percentile"))) if r else None,
                      "hbi": num(r.get("hbi_mean")) if r else None,
                      "top10": truthy(r.get("top10_circle") if num(r.get("percentile_circle")) is not None else r.get("top10")) if r else False})
    base = "medical" if "medical" in targets else targets[0]
    cand = []
    for r in read_csv(os.path.join(src, "validation_new_candidates.csv")) or []:
        x, y, h = num(r["cell_x"]), num(r["cell_y"]), num(r["hbi_mean"])
        if None in (x, y, h):
            continue
        d = dong_of(x, y, dongs)
        cand.append({"x": round(x), "y": round(y), "hbi": h, "n": int(num(r.get("n_bld")) or 0),
                     "where": f"{d['gu']} {d['adm_nm'].split()[-1]}" if d else f"({round(x)}, {round(y)})"})

    data = {"source": "fake" if fake else ("rehearsal" if reh else "real"), "grid": 250, "o": [ox, oy], "targets": targets, "base": base,
            "tlabel": {t: TARGET_LABEL.get(t, t) for t in targets}, "gus": TARGET_GU, "gubbox": gubbox, "bbox": bbox,
            "dongs": dout, "dongmeta": dmeta, "cells": cells, "tmax": tmax, "sites": sites, "cand": cand}
    tpl = open(os.path.join(HERE, "evenly_template.html"), encoding="utf-8").read()
    html = tpl.replace("__DATA__", json.dumps(data, ensure_ascii=False, separators=(",", ":")))
    with open(a.out, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"[{data['source']}] {os.path.relpath(src, ROOT)} → {os.path.relpath(a.out, ROOT)} ({len(html) // 1024}KB, 목적지 {len(targets)}종, "
          f"격자 {sum(len(v) for v in cells.values())}칸, 선정지 결과 {sum(1 for s in sites if s['pct'] is not None)}/5, 후보 {len(cand)})")


if __name__ == "__main__":
    main()
