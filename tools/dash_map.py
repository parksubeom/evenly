# -*- coding: utf-8 -*-
"""
tools/dash_map.py ─ [10/20] 24장 "evenly 화면" 의 지도 칸 (prepare_deck_data·prepare_fallback_deck 가 함께 씀)

  저장된 밝은 배경지도(deck/basemap/, tools/make_basemap.py) 위에 250m 격자를 반투명으로 (14장과 같은 색·같은 구간 기준),
  행정동 이름·봉천 선정지·역(봉천·서울대입구·낙성대)·관악산 이름, 17장 후보 1~3 격자 번호, 구석에 "서울 속 관악구" 위치도.
  격자는 넘겨받은 것만 그림 (22일 real-day 는 반출 격자). 격자가 없으면(대비책 판) 배경지도와 이름만.
  draw_basemap 은 prepare_deck_data 의 14·19장 지도도 씀
"""
import csv, glob, json, os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BASEMAP_DIR = os.path.join(ROOT, "deck", "basemap")
V6C = ["#8CB8A0", "#F2B134", "#E4572E"]                 # 14장 지도와 같은 색 (평지 수준 · 체감 부담 · 고립 위험)
STATIONS = [("봉천역", "봉천"), ("서울대입구역", "서울대입구(관악구청)"), ("낙성대역", "낙성대")]
GWANAKSAN = (126.9585, 37.4655)                          # 관악산 이름 자리 (서울대 북쪽 산자락, 이름표 위치만)


def draw_basemap(ax, ext, alpha=1.0, zorder=0):
    """deck/basemap/*.png 중 ext(x0, x1, y0, y1, EPSG:5186)를 다 덮는 가장 촘촘한 것을 맨 아래에 깜 → 출처 글자 (없으면 None)"""
    import matplotlib.pyplot as plt
    best = None
    for j in sorted(glob.glob(os.path.join(BASEMAP_DIR, "*.json"))):
        try:
            m = json.load(open(j, encoding="utf-8"))
            bx0, bx1, by0, by1 = m["extent_5186"]
        except Exception:
            continue
        png = j[:-5] + ".png"
        if os.path.exists(png) and bx0 <= ext[0] and bx1 >= ext[1] and by0 <= ext[2] and by1 >= ext[3]:
            if best is None or m["m_per_px"] < best[0]["m_per_px"]:
                best = (m, png)
    if not best:
        return None
    m, png = best
    bx0, bx1, by0, by1 = m["extent_5186"]
    ax.imshow(plt.imread(png), extent=(bx0, bx1, by0, by1), origin="upper", interpolation="bilinear", alpha=alpha, zorder=zorder)
    return m.get("attribution") or "© OpenStreetMap contributors"


def _font(plt, matplotlib):
    names = {f.name for f in matplotlib.font_manager.fontManager.ttflist}
    plt.rcParams["font.family"] = next((f for f in ["Malgun Gothic", "Apple SD Gothic Neo", "AppleGothic", "NanumGothic"] if f in names), "sans-serif")


def draw_dash_map(out, cells, cands, site, W=5.0, H=2.62, dpi=240, alpha=0.72):
    """cells = [(cell_x, cell_y, 구간 0/1/2)] (EPSG:5186 격자 가운데, 250m), cands = [(번호, cell_x, cell_y)], site = (x, y) 봉천 선정지.
    반환: (그림 경로, 배경지도 출처 또는 None)"""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import matplotlib.patheffects as pe
    from matplotlib.collections import PatchCollection, LineCollection
    from matplotlib.patches import Rectangle, Polygon as MPoly
    from evenly_common import load_dongs, to5186
    _font(plt, matplotlib)
    st = {}
    for r in csv.DictReader(open(os.path.join(ROOT, "data_public", "subway_stations.csv"), encoding="utf-8-sig")):
        for lab, nm in STATIONS:
            if r["name"] == nm and lab not in st:
                st[lab] = to5186(float(r["lon"]), float(r["lat"]))
    P = [site] + list(st.values()) + [(cx, cy) for _, cx, cy in cands]      # 선정지·역·후보가 다 들어가게, 그림 비율에 맞춤
    x0, x1 = min(p[0] for p in P) - 450, max(p[0] for p in P) + 450
    y0, y1 = min(p[1] for p in P) - 330, max(p[1] for p in P) + 330
    if (x1 - x0) / (y1 - y0) < W / H:
        c, h_ = (x0 + x1) / 2, (y1 - y0) * W / H / 2; x0, x1 = c - h_, c + h_
    else:
        c, h_ = (y0 + y1) / 2, (x1 - x0) * H / W / 2; y0, y1 = c - h_, c + h_
    fig = plt.figure(figsize=(W, H), dpi=dpi)
    ax = fig.add_axes([0, 0, 1, 1]); ax.axis("off"); fig.patch.set_facecolor("#FFFFFF")
    bm = draw_basemap(ax, (x0, x1, y0, y1))
    if cells:
        rects = [Rectangle((cx - 125, cy - 125), 250, 250) for cx, cy, _ in cells]
        ax.add_collection(PatchCollection(rects, facecolors=[V6C[k] for _, _, k in cells], linewidths=0, alpha=alpha, zorder=2))
    alld = load_dongs(None)
    near = [d for d in alld if not (d["bbox"][2] < x0 or d["bbox"][0] > x1 or d["bbox"][3] < y0 or d["bbox"][1] > y1)]
    ax.add_collection(LineCollection([r for d in near for r in d["rings"]], colors="#7E8683", linewidths=0.45, alpha=0.8, zorder=3))
    halo = [pe.withStroke(linewidth=2.0, foreground="white")]
    for d in near:
        if d["gu"] != "관악구":
            continue
        ring = max(d["rings"], key=len)
        cx_ = sum(x for x, _ in ring) / len(ring); cy_ = sum(y for _, y in ring) / len(ring)
        if x0 + 150 < cx_ < x1 - 150 and y0 + 120 < cy_ < y1 - 120:
            ax.text(cx_, cy_, (d["adm_nm"] or "").split()[-1], fontsize=6.2, color="#4A524F", ha="center", va="center", zorder=5, path_effects=halo)
    for n, cx, cy in cands:
        ax.add_patch(Rectangle((cx - 125, cy - 125), 250, 250, fill=False, edgecolor="#1C2321", linewidth=1.1, zorder=6))
        ax.text(cx, cy, str(n), fontsize=7.5, color="#1C2321", fontweight="bold", ha="center", va="center", zorder=7, path_effects=halo)
    for lab, (sx_, sy_) in st.items():
        ax.scatter([sx_], [sy_], s=26, color="#FFFFFF", edgecolors="#1C2321", linewidths=1.1, zorder=8)
        ax.text(sx_, sy_ + 70, lab, fontsize=6.8, color="#1C2321", fontweight="bold", ha="center", va="bottom", zorder=8, path_effects=halo)
    ax.scatter([site[0]], [site[1]], marker="*", s=95, color="#1C2321", edgecolors="white", linewidths=0.6, zorder=9)
    ax.text(site[0] - 70, site[1] - 60, "봉천 선정지", fontsize=7.5, color="#1C2321", fontweight="bold", ha="right", va="top", zorder=9, path_effects=halo)
    gx, gy = to5186(*GWANAKSAN)
    if x0 < gx < x1 and y0 < gy < y1:
        ax.text(gx, gy, "관악산", fontsize=8, color="#55785A", fontweight="bold", ha="center", va="center", zorder=5, path_effects=halo)
    elif gy < y0:                                         # 범위 남쪽 밖 → 아래 가장자리에 방향만
        ax.text(min(max(gx, x0 + 500), x1 - 900), y0 + 60, "관악산 ↓", fontsize=7.5, color="#55785A", fontweight="bold", ha="center", va="bottom", zorder=9, path_effects=halo)
    ax.plot([x1 - 650, x1 - 150], [y0 + 120, y0 + 120], color="#1C2321", lw=1.6, zorder=9)
    ax.text(x1 - 400, y0 + 165, "500m", fontsize=6.5, color="#1C2321", ha="center", va="bottom", zorder=9, path_effects=halo)
    ax.set_xlim(x0, x1); ax.set_ylim(y0, y1); ax.set_aspect("equal")
    # 서울 속 관악구 (오른쪽 위)
    ins = fig.add_axes([0.838, 0.63, 0.155, 0.355]); ins.axis("off")
    gu = [d for d in alld]
    ins.add_patch(Rectangle((0, 0), 1, 1, transform=ins.transAxes, facecolor="white", edgecolor="#C9CECB", linewidth=0.6, zorder=0))
    ins.add_collection(PatchCollection([MPoly(r) for d in gu if d["gu"] != "관악구" for r in d["rings"]], facecolor="#E9ECEA", edgecolor="#E9ECEA", linewidths=0.2, zorder=1))
    ins.add_collection(PatchCollection([MPoly(r) for d in gu if d["gu"] == "관악구" for r in d["rings"]], facecolor="#E4572E", edgecolor="#E4572E", linewidths=0.2, zorder=2))
    ins.add_patch(Rectangle((x0, y0), x1 - x0, y1 - y0, fill=False, edgecolor="#1C2321", linewidth=0.6, zorder=3))
    X = [x for d in gu for r in d["rings"] for x, _ in r]; Y = [y for d in gu for r in d["rings"] for _, y in r]
    pad = (max(X) - min(X)) * 0.04
    ins.set_xlim(min(X) - pad, max(X) + pad); ins.set_ylim(min(Y) - pad * 3.2, max(Y) + pad); ins.set_aspect("equal")
    ins.text(0.5, 0.03, "서울 속 관악구", transform=ins.transAxes, fontsize=5.6, color="#1C2321", ha="center", va="bottom", zorder=4)
    os.makedirs(os.path.dirname(out), exist_ok=True)
    fig.savefig(out, dpi=dpi, facecolor="#FFFFFF")
    plt.close(fig)
    return out, bm
