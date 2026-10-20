# -*- coding: utf-8 -*-
"""
tools/make_basemap.py ─ [10/20] 기획서 지도 장(14·19)의 밝은 배경지도를 오픈스트리트맵 "자료"로 직접 그려 레포에 저장

[왜] 네이버·카카오·구글 지도 캡처는 이용 약관상 쓰지 않음. 오픈스트리트맵 타일 서버(tile.openstreetmap.org)는
     "오프라인 사용 불가, 지역을 미리 받아 두는 것은 대량 다운로드로 금지" (OSMF Tile Usage Policy) 라서 타일을 받아 저장하지 않음.
     대신 OSM 자료(ODbL, 출처 "© OpenStreetMap contributors" 를 밝히면 저장·가공 가능)를 Overpass API 로 관악 범위 한 번만 받아
     길·철도·물·공원·숲·건물만 옅게 그림 (글자 없음). 22일 real-day 는 저장된 그림만 씀 (인터넷 필요 없음)
[실행]  (QGIS 파이썬) python tools/make_basemap.py [--refresh]
          --refresh : data_public/raw 의 OSM 응답(받아 둔 것)을 버리고 다시 받음 (보통은 받아 둔 것으로 다시 그림)
[결과]  deck/basemap/gwanak_light.png + .json  (관악구 동 경계 범위 + 2km, 5m/화소, 14장 결과 지도용)
        deck/basemap/bongcheon_light.png + .json (봉천 선정지 둘레 ±1.5km, 1.25m/화소, 19장 등시선용)
        .json = {extent_5186: [x0, x1, y0, y1], m_per_px, attribution, osm_fetched}  ← tools/prepare_deck_data.py 가 읽음
        OSM 응답 원본: data_public/raw/osm_basemap_gwanak.json, osm_buildings_gwanak.json (git 에 넣지 않음)
"""
import argparse, json, os, sys, time, urllib.parse, urllib.request
import numpy as np
from osgeo import osr
osr.UseExceptions()
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.collections import LineCollection, PolyCollection

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW = os.path.join(ROOT, "data_public", "raw")
OUT = os.path.join(ROOT, "deck", "basemap")
sys.path.insert(0, os.path.join(ROOT, "tools"))
from evenly_common import load_dongs   # noqa: E402

OVERPASS = "https://overpass-api.de/api/interpreter"
UA = {"User-Agent": "evenly-basemap/1.0 (one-time small-area fetch for a contest deck)"}
ATTR = "© OpenStreetMap contributors"
# 밝은 배경 (기획서 색과 겹치지 않게 아주 옅게)
BG, GREEN, WATER, BLD, MINOR, MAJOR, PATH, RAIL = "#FAFAF8", "#E7EFE4", "#DDE8EF", "#EDEDEA", "#E2E4E1", "#D3D7D4", "#ECEDEB", "#CFD3D0"
MAJOR_T = {"motorway", "trunk", "primary", "secondary", "motorway_link", "trunk_link", "primary_link", "secondary_link"}
MINOR_T = {"tertiary", "tertiary_link", "residential", "unclassified", "living_street", "service", "road"}
PATH_T = {"footway", "path", "pedestrian", "steps", "cycleway", "track"}
GREEN_Q = {("leisure", "park"), ("leisure", "garden"), ("leisure", "playground"), ("landuse", "forest"), ("landuse", "grass"),
           ("landuse", "meadow"), ("landuse", "recreation_ground"), ("landuse", "village_green"), ("landuse", "cemetery"),
           ("natural", "wood"), ("natural", "scrub"), ("natural", "grassland"), ("natural", "heath")}


def srs(c):
    s = osr.SpatialReference(); s.ImportFromEPSG(c); s.SetAxisMappingStrategy(osr.OAMS_TRADITIONAL_GIS_ORDER)
    return s


S4326, S5186 = srs(4326), srs(5186)
TO5186 = osr.CoordinateTransformation(S4326, S5186)
TO4326 = osr.CoordinateTransformation(S5186, S4326)


def fetch(query, cache, refresh):
    if os.path.exists(cache) and not refresh:
        return json.load(open(cache, encoding="utf-8"))
    req = urllib.request.Request(OVERPASS, data=urllib.parse.urlencode({"data": query}).encode(), headers=UA)
    with urllib.request.urlopen(req, timeout=300) as r:
        data = json.loads(r.read().decode("utf-8"))
    data.update(_query=query, _license=f"{ATTR} (ODbL)", _fetched=time.strftime("%Y-%m-%d %H:%M"))
    json.dump(data, open(cache, "w", encoding="utf-8"), ensure_ascii=False)
    time.sleep(5)                                                     # 다음 요청 전 쉼 (Overpass 서버 배려)
    return data


def xy(geom):
    a = np.array([(p["lon"], p["lat"]) for p in geom if p])
    return np.asarray(TO5186.TransformPoints(a.tolist()))[:, :2] if len(a) else np.zeros((0, 2))


def parts(e):
    """way → [점 배열], relation(multipolygon) → 바깥 고리들 (out geom)"""
    if e["type"] == "way":
        return [xy(e.get("geometry") or [])]
    return [xy(m.get("geometry") or []) for m in e.get("members", []) if m.get("type") == "way" and m.get("role") in ("outer", "")]


def classify(data, bld):
    G, W, Wl, B, Ma, Mi, Pa, Ra = [], [], [], [], [], [], [], []
    for e in data.get("elements", []):
        t = e.get("tags", {})
        if t.get("tunnel") in ("yes", "building_passage") or t.get("layer", "0").startswith("-"):
            continue                                                  # 땅 밑은 그리지 않음
        for p in parts(e):
            if len(p) < 2:
                continue
            closed = len(p) >= 4 and np.allclose(p[0], p[-1])
            if bld and "building" in t:
                if closed: B.append(p)
            elif t.get("natural") == "water" or t.get("landuse") == "reservoir" or t.get("waterway") == "riverbank":
                if closed: W.append(p)
            elif t.get("waterway") in ("river", "stream", "canal"):
                Wl.append(p)
            elif any((k, t.get(k)) in GREEN_Q for k in ("leisure", "landuse", "natural")):
                if closed: G.append(p)
            elif t.get("railway") in ("rail", "light_rail", "subway"):
                Ra.append(p)
            elif t.get("highway") in MAJOR_T:
                Ma.append(p)
            elif t.get("highway") in MINOR_T:
                Mi.append(p)
            elif t.get("highway") in PATH_T:
                Pa.append(p)
    return dict(green=G, water=W, waterline=Wl, bld=B, major=Ma, minor=Mi, path=Pa, rail=Ra)


def render(L, ext, mpp, path, scale):
    """ext = (x0, x1, y0, y1) EPSG:5186, mpp = 화소당 m. scale = 선 굵기 배수 (상세 지도는 굵게)"""
    W, H = int(round((ext[1] - ext[0]) / mpp)), int(round((ext[3] - ext[2]) / mpp))
    dpi = 100
    fig = plt.figure(figsize=(W / dpi, H / dpi), dpi=dpi)
    ax = fig.add_axes([0, 0, 1, 1]); ax.set_xlim(ext[0], ext[1]); ax.set_ylim(ext[2], ext[3]); ax.axis("off")
    fig.patch.set_facecolor(BG)
    k = scale
    ax.add_collection(PolyCollection(L["green"], facecolors=GREEN, edgecolors="none", zorder=1))
    ax.add_collection(PolyCollection(L["water"], facecolors=WATER, edgecolors="none", zorder=2))
    ax.add_collection(LineCollection(L["waterline"], colors=WATER, linewidths=1.6 * k, zorder=2))
    ax.add_collection(PolyCollection(L["bld"], facecolors=BLD, edgecolors="none", zorder=3))
    ax.add_collection(LineCollection(L["path"], colors=PATH, linewidths=0.35 * k, zorder=4))
    ax.add_collection(LineCollection(L["minor"], colors=MINOR, linewidths=0.6 * k, zorder=5, capstyle="round"))
    ax.add_collection(LineCollection(L["major"], colors=MAJOR, linewidths=1.3 * k, zorder=6, capstyle="round"))
    ax.add_collection(LineCollection(L["rail"], colors=RAIL, linewidths=0.8 * k, linestyles=[(0, (3, 2))], zorder=7))
    fig.savefig(path, dpi=dpi, facecolor=BG)
    plt.close(fig)
    return W, H


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--refresh", action="store_true")
    a = ap.parse_args()
    os.makedirs(OUT, exist_ok=True)
    d = load_dongs(["관악구"])
    gx0, gy0 = min(x["bbox"][0] for x in d), min(x["bbox"][1] for x in d)
    gx1, gy1 = max(x["bbox"][2] for x in d), max(x["bbox"][3] for x in d)
    M = 2000.0
    ext = (gx0 - M, gx1 + M, gy0 - M, gy1 + M)
    ll = np.asarray(TO4326.TransformPoints([(ext[0], ext[2]), (ext[1], ext[2]), (ext[0], ext[3]), (ext[1], ext[3])]))[:, :2]
    s, w, n, e = ll[:, 1].min(), ll[:, 0].min(), ll[:, 1].max(), ll[:, 0].max()
    bb = f"{s:.5f},{w:.5f},{n:.5f},{e:.5f}"
    q1 = (f"[out:json][timeout:240];("
          f'way["highway"]({bb});way["railway"~"^(rail|light_rail|subway)$"]({bb});'
          f'way["natural"~"^(water|wood|scrub|grassland|heath)$"]({bb});relation["natural"~"^(water|wood)$"]({bb});'
          f'way["waterway"~"^(river|stream|canal|riverbank)$"]({bb});way["landuse"~"^(reservoir|forest|grass|meadow|recreation_ground|village_green|cemetery)$"]({bb});'
          f'relation["landuse"="forest"]({bb});way["leisure"~"^(park|garden|playground)$"]({bb});relation["leisure"="park"]({bb});'
          f");out geom;")
    q2 = f'[out:json][timeout:240];way["building"]({bb});out geom;'
    print(f"범위 (5186) {[round(v) for v in ext]} · 경위도 {bb}", flush=True)
    base = fetch(q1, os.path.join(RAW, "osm_basemap_gwanak.json"), a.refresh)
    blds = fetch(q2, os.path.join(RAW, "osm_buildings_gwanak.json"), a.refresh)
    L = classify(base, False)
    L["bld"] = classify(blds, True)["bld"]
    print("  " + " · ".join(f"{k} {len(v):,}" for k, v in L.items()), flush=True)
    fetched = base.get("_fetched") or "?"
    outs = []
    # 1) 관악 전체 (14장): 5m/화소
    W, H = render(L, ext, 5.0, os.path.join(OUT, "gwanak_light.png"), 1.0)
    outs.append(("gwanak_light", ext, 5.0, W, H))
    # 2) 봉천 선정지 둘레 (19장): 1.25m/화소, 선을 굵게
    import csv
    import field_fix_v62 as FF
    r = next(r for r in csv.DictReader(open(FF.CAND_CSV, encoding="utf-8-sig")) if r["name"].startswith("봉천동 비안어린이공원"))
    p = np.asarray(TO5186.TransformPoints([(float(r["a_lon"]), float(r["a_lat"])), (float(r["b_lon"]), float(r["b_lat"]))]))[:, :2].mean(axis=0)
    ext2 = (p[0] - 1500, p[0] + 1500, p[1] - 1500, p[1] + 1500)
    W2, H2 = render(L, ext2, 1.25, os.path.join(OUT, "bongcheon_light.png"), 2.4)
    outs.append(("bongcheon_light", ext2, 1.25, W2, H2))
    for nm, ex, mpp, w_, h_ in outs:
        json.dump({"extent_5186": [round(v, 1) for v in ex], "m_per_px": mpp, "px": [w_, h_], "attribution": ATTR,
                   "_설명": "OSM 자료(ODbL)로 직접 그린 밝은 배경지도 (타일 아님, 글자 없음). tools/make_basemap.py",
                   "osm_fetched": fetched}, open(os.path.join(OUT, nm + ".json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        print(f"→ deck/basemap/{nm}.png ({w_}×{h_}, {mpp}m/화소, {os.path.getsize(os.path.join(OUT, nm + '.png')) / 1e6:.1f}MB)")


if __name__ == "__main__":
    main()
