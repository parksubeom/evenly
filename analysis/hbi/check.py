# -*- coding: utf-8 -*-
"""
check.py ─ [v6] 분석 출발 전 점검 (python setup.py 다음, python run_all.py 전에 한 줄)

[실행]  python check.py
[하는 일]  자료를 고치지 않고 읽기만 합니다. 몇 분 안에 끝나도록 대상 구마다 1km 네모 창(표본)만 봅니다.
  1. 경로·mapping.txt
  2. 읽을 폴더(map_folders)와 AREA_BBOX: 정한 값과 이유, 대상 구가 모두 자료 범위 안에 있나
  3. DEM 이 대상 범위를 덮나
  4. 레이어 세 등급 (분석 불가 / 결과 약화 / 괜찮음)
  5. 칸 매핑: mapping 의 칸 이름이 실제 자료에 있나 (대소문자 무시)
  6. 인코딩: 한글 칸 표본이 깨지지 않았나 (값은 화면·파일에 남기지 않음)
  7. 좌표계
  8. 표본 창: 건물 중 주거 비율(register 이면 대장 연결률), 주거 건물 → 길 연결 비율, 목적지 개수
  9. 예상 소요 시간
[멈춤]  말이 안 되면 "!! 멈춤" 과 원인·고칠 mapping 키를 보여 주고 끝냄 (종료 코드 1). 경고(!)는 진행해도 됨
[결과]  화면 + output/check_report.txt (구조·비율·개수만, 값 없음)
"""
import os, re, sys, collections
import numpy as np
import config as C
from lib.conout import Tee, safe_console
from lib.qio import find_files, open_vector, layer_srs, layer_files, iter_layer, read_csv, transformer, transform_xy, TARGET
from lib import area, battr
from lib.qgraph import NearestIndex
from osgeo import gdal, ogr
gdal.UseExceptions(); ogr.UseExceptions()
safe_console()

SEC_PER_KLINE = (1.0, 6.0)   # 길 선 1,000개당 02~05 걸린 초 (이 맥 v6 시험에서 잰 값의 범위, tools 시험 결과로 갱신)


def estimate_minutes(n_lines):
    lo, hi = (n_lines / 1000 * s * 3 / 60 for s in SEC_PER_KLINE)
    return max(1, int(round(lo))), max(2, int(round(hi)) + 1)


GU_COVER_MIN = 0.5      # 대상 구 면적의 이 비율 넘게 자료 범위 안이어야 "있음"
WIN = 1000              # 표본 창 한 변 (m)
STOP, WARN = [], []


def stop(why, todo):
    STOP.append((why, todo)); print(f"  !! 멈춤: {why}\n     → {todo}")


def warn(why, todo=""):
    WARN.append(why); print(f"  ! 경고: {why}" + (f"\n     → {todo}" if todo else ""))


def fields_of(f, enc=None):
    ds = open_vector(f, enc)
    d = ds.GetLayer(0).GetLayerDefn()
    return [d.GetFieldDefn(i).GetName() for i in range(d.GetFieldCount())]


def has_field(names, want):
    return bool(want) and want.upper() in {n.upper() for n in names}


def env_of(files):
    out = []
    for f in files:
        try:
            ds = open_vector(f)
            lyr = ds.GetLayer(0)
            if lyr.GetFeatureCount() == 0:
                continue
            s, _ = layer_srs(lyr)
            x0, x1, y0, y1 = lyr.GetExtent()
            xs, ys = transform_xy(transformer(s), [x0, x1, x0, x1], [y0, y0, y1, y1])
            out.append((min(xs), min(ys), max(xs), max(ys)))
        except Exception:
            continue
    return out


def clip(envs, b):
    if not b:
        return envs
    return [(max(e[0], b[0]), max(e[1], b[1]), min(e[2], b[2]), min(e[3], b[3])) for e in envs
            if e[0] < b[2] and e[2] > b[0] and e[1] < b[3] and e[3] > b[1]]


def count_in(files, bbox):
    """파일들의 객체 수 (bbox 가 있으면 그 안만, 공간 필터로 빠르게)"""
    n = 0
    for f in files:
        try:
            ds = open_vector(f)
            lyr = ds.GetLayer(0)
            if bbox:
                s, _ = layer_srs(lyr)
                ct = transformer(TARGET, s)
                xs, ys = transform_xy(ct, [bbox[0], bbox[2]], [bbox[1], bbox[3]])
                lyr.SetSpatialFilterRect(min(xs), min(ys), max(xs), max(ys))
            n += lyr.GetFeatureCount()
            ds = None
        except Exception:
            continue
    return n


def broken_share(vals):
    """깨진 한글 표본 비율: 대체문자(�)·물음표 연속·제어문자가 든 값의 비율"""
    vals = [str(v) for v in vals if v not in (None, "")]
    if not vals:
        return None
    bad = sum(1 for v in vals if "�" in v or "??" in v or re.search(r"[\x00-\x08\x0e-\x1f]", v))
    return bad / len(vals)


def main():
    print("=== 1. 경로 ===")
    for nm, p in [("수치지형도", C.DATA_ROOT_MAP), ("DEM 5m", C.DATA_ROOT_DEM), ("국토정보필지", C.DATA_ROOT_PARCEL)]:
        ok = bool(p) and os.path.exists(p)
        print(f"  {nm}: {'있음' if ok else ('비어 있음' if not p else '없음')}  ({p})")
        if nm != "국토정보필지" and not ok:
            stop(f"{nm} 폴더가 없음", "python setup.py 를 다시 (자료 최상위 폴더를 넣으면 config.py 를 채움)")
    print(f"  mapping.txt: {'있음' if os.path.exists(os.path.join(C.BASE, 'mapping.txt')) else '없음 (기본값 = v5 와 같은 이름)'}")
    print(f"  건물 용도 방식: {C.BUILDING_ATTR_MODE}, 대상 구: {','.join(C.TARGET_GU) or '전체'}, 옆 구: {','.join(C.NEIGHBOR_GU) or '없음'}")
    if STOP:
        return

    print("\n=== 2. 읽을 폴더와 분석 범위 ===")
    print(f"  map_folders: {len(C.MAP_FOLDERS)}개 {'(전부 읽음)' if not C.MAP_FOLDERS else ''}")
    for f in C.MAP_FOLDERS:
        print(f"    - {f}")
    print(f"  AREA_BBOX = {C.AREA_BBOX}  ({C.AREA_REASON or '이유 없음: setup.py 를 거치지 않았거나 직접 고침'})")
    bfiles = layer_files("building")
    envs = clip(env_of(bfiles + layer_files("road_cl") + layer_files("sidewalk_cl")), C.AREA_BBOX)   # 건물·길 파일 범위의 합
    gp = area.gu_polys() if area.boundary_file() else {}
    tgt = [g for g in C.TARGET_GU]
    if tgt and not gp:
        warn("external/dong_boundary.geojson 이 없어 대상 구 확인을 못 함 (결과는 자료 전체)")
    elif tgt:
        miss = []
        for g in tgt:
            if g not in gp:
                miss.append(f"{g}(경계 파일에 없는 이름)"); continue
            sh = area.cover_share(gp[g], envs)
            print(f"  대상 구 {g}: 면적의 {sh:.0%} 가 자료 범위 안")
            if sh < GU_COVER_MIN:
                miss.append(g)
        if miss:
            stop(f"대상 구가 자료 범위 밖: {', '.join(miss)}",
                 "그 구의 수치지형도 폴더가 map_folders 에 있는지 (python setup.py 다시), AREA_BBOX 가 그 구를 덮는지 확인")
        for g in C.NEIGHBOR_GU:
            if g in gp and area.cover_share(gp[g], envs) < GU_COVER_MIN:
                warn(f"옆 구 {g} 자료가 거의 없음 → 대상 구 경계 근처 집의 목적지가 빠질 수 있음")

    print("\n=== 3. DEM ===")
    dem = [f for e in (".img", ".tif", ".tiff", ".asc") for f in find_files(C.DATA_ROOT_DEM, [""], e)]
    print(f"  DEM 5m: 파일 {len(dem)}개")
    if not dem:
        stop("DEM 파일이 없음", "config.py 의 DATA_ROOT_DEM (python setup.py)")
    else:
        try:
            vrt = gdal.BuildVRT("/vsimem/chk.vrt", dem)
            gt = vrt.GetGeoTransform()
            res = gt[1]
            de = (gt[0], gt[3] + gt[5] * vrt.RasterYSize, gt[0] + gt[1] * vrt.RasterXSize, gt[3])
            vrt = None; gdal.Unlink("/vsimem/chk.vrt")
            print(f"  해상도 {res:.2f}m, 범위 x {de[0]:.0f}~{de[2]:.0f} y {de[1]:.0f}~{de[3]:.0f}")
            if tgt and gp:
                bad = [g for g in tgt if g in gp and area.cover_share(gp[g], [de]) < 0.95]
                if bad:
                    warn(f"DEM 이 대상 구를 다 덮지 못함: {', '.join(bad)} → 경사가 0 으로 계산되는 곳이 생김", "DEM 폴더 확인 (python setup.py)")
                else:
                    print("  대상 구를 모두 덮음")
        except Exception as e:
            warn(f"DEM 범위를 읽지 못함 ({type(e).__name__})")

    print("\n=== 4. 레이어 ===")
    have = {k: layer_files(k) for k in C.LAYERS}
    for k, fs in have.items():
        print(f"  [{'있음' if fs else '없음'}] {k}: 파일 {len(fs)}개")
    if not have.get("building") or not (have.get("sidewalk_cl") or have.get("road_cl")):
        stop("분석 불가: 건물 또는 길(보도·도로 중심선) 레이어가 없음", "mapping.txt 의 layer_building·layer_road_cl 을 실제 파일 이름 글자로 (python setup.py)")
    weak = [k for k in ("sidewalk_cl", "road_cl", "stairs", "bus_stop", "station") if not have.get(k)]
    if weak and not STOP:
        warn(f"결과 약화: {', '.join(weak)} 없음 (길 일부·계단·정류장·역이 빠짐) → 그대로 진행 가능")
    if STOP:
        return

    print("\n=== 5. 칸 매핑 ===")
    bnames = fields_of(have["building"][0])
    print(f"  건물 칸: {bnames}")
    use_ok = has_field(bnames, C.COL.get("bld_use"))
    for k in ("bld_use", "bld_kind", "bld_floor"):
        print(f"  {k} = {C.COL.get(k)} → {'있음' if has_field(bnames, C.COL.get(k)) else '없음'}")
    mode = C.BUILDING_ATTR_MODE
    reg_ok = bool(C.REGISTER_FILE) and (os.path.exists(C.REGISTER_FILE) or os.path.exists(os.path.splitext(C.REGISTER_FILE)[0] + ".txt"))
    if mode == "layer" and not use_ok:
        rec = "register" if (reg_ok and C.DATA_ROOT_PARCEL) else "all"
        stop("건물 레이어에 용도 칸이 없음 (layer 방식으로는 집을 고를 수 없음)",
             f"mapping.txt 의 building_attr_mode = {rec} (" + ("건축물대장·필지로 용도를 붙임" if rec == "register" else "모든 건물을 집으로 봄, 용도 미구분") + ")")
    if mode == "register":
        print(f"  건축물대장: {'있음' if reg_ok else '없음'} ({C.REGISTER_FILE})")
        if not reg_ok:
            stop("register 방식인데 건축물대장 파일이 없음", "external 에 building_register.csv 를 넣거나 building_attr_mode = all")
        if not C.DATA_ROOT_PARCEL:
            stop("register 방식인데 필지 폴더가 없음", "config.py 의 DATA_ROOT_PARCEL (python setup.py)")
    pfiles = find_files(C.DATA_ROOT_PARCEL, [""], ".shp") if C.DATA_ROOT_PARCEL else []
    if pfiles:
        pn = fields_of(pfiles[0], C.PARCEL_ENCODING)
        print(f"  필지 칸: {[n for n in pn if not any(x in n.upper() for x in ('OWN', 'JIGA'))]} (소유·공시지가 칸은 표시·사용 안 함)")
        for k in ("parcel_id", "parcel_bldrgst", "parcel_emd_cd", "jimok", "sgg_nm", "emd_nm"):
            print(f"  {k} = {C.FIELD.get(k)} → {'있음' if has_field(pn, C.FIELD.get(k)) else '없음'}")
        if not has_field(pn, C.FIELD.get("parcel_id")):
            (stop if mode == "register" else warn)("필지 고유번호 칸을 찾지 못함", "mapping.txt 의 parcel_id 를 필지 칸 중 19자리 번호 칸으로")
    if STOP:
        return

    print("\n=== 6. 인코딩 (표본, 값은 표시하지 않음) ===")
    smp = []
    for g, a in iter_layer(files=have["building"][:1], fields=[c for c in (C.COL.get("bld_use"), C.COL.get("bld_kind")) if c]):
        smp += list(a.values())
        if len(smp) > 600:
            break
    sh = broken_share(smp)
    print(f"  건물 칸 깨진 비율: {'칸 없음' if sh is None else f'{sh:.0%}'} (SHP_ENCODING = {C.SHP_ENCODING})")
    if sh and sh > 0.2:
        warn("건물 칸 한글이 깨짐", 'config.py 의 SHP_ENCODING 을 "UTF-8" ↔ "CP949" 로 바꿔 보기')
    if pfiles and C.FIELD.get("jimok"):
        vals = [a.get(C.FIELD["jimok"]) for _, (g, a) in zip(range(500), iter_layer(files=pfiles[:1], fields=[C.FIELD["jimok"]], bbox=False, encoding=C.PARCEL_ENCODING))]
        sh = broken_share(vals)
        han = np.mean([bool(re.search("[가-힣]", str(v))) for v in vals if v]) if any(vals) else 0
        print(f"  필지 지목 깨진 비율: {'칸 없음' if sh is None else f'{sh:.0%}'}, 한글 비율 {han:.0%} (PARCEL_ENCODING = {C.PARCEL_ENCODING})")
        if sh is not None and (sh > 0.2 or han < 0.5):
            warn("필지 지목 한글이 깨짐 (06 '대' 필지 0개로 나옴)", 'config.py 의 PARCEL_ENCODING 을 "CP949" ↔ "UTF-8" 로')

    print("\n=== 7. 좌표계 ===")
    crs = collections.Counter()
    for k, fs in have.items():
        for f in fs[:3]:
            try:
                ds = open_vector(f)
                s, has = layer_srs(ds.GetLayer(0))
                ds = None
                crs[(s.GetAuthorityCode(None) or s.GetName()) + ("" if has else " (prj 없음, 추정)")] += 1
            except Exception:
                pass
    print(f"  {dict(crs)} → 분석 좌표계 {C.TARGET_CRS} 로 바꿔 계산")
    if any("prj 없음" in k for k in crs):
        warn("prj 없는 파일은 좌표 크기로 좌표계를 추정함 (중부원점 5186 / UTM-K 5179)")

    print("\n=== 8. 표본 창 (대상 구마다 1km 네모) ===")
    wins = []
    if tgt and gp:
        nob = []
        for g in tgt:
            if g not in gp:
                continue
            # 창 가운데 = 그 구 안 실제 건물 하나 (구의 가운데 점은 산·공원일 수 있음): 건물 대표점들의 가운데에 가장 가까운 건물
            x0, x1, y0, y1 = gp[g].GetEnvelope()
            pts = []
            for geo, _ in iter_layer("building", fields=[], bbox=[x0, y0, x1, y1]):
                p = geo.Centroid()
                if gp[g].Contains(p):
                    pts.append((p.GetX(), p.GetY()))
                if len(pts) >= 3000:
                    break
            if not pts:
                nob.append(g); continue
            P = np.array(pts)
            c = P[np.argmin(((P - np.median(P, axis=0)) ** 2).sum(1))]
            wins.append((g, [c[0] - WIN / 2, c[1] - WIN / 2, c[0] + WIN / 2, c[1] + WIN / 2]))
        if nob:
            stop(f"대상 구 안에 건물이 하나도 없음: {', '.join(nob)}", "그 구의 건물 파일이 map_folders 안에 있는지, AREA_BBOX 가 그 구를 덮는지 (python setup.py 다시)")
    else:
        e = envs[0] if envs else None
        if e:
            cx, cy = (e[0] + e[2]) / 2, (e[1] + e[3]) / 2
            wins.append(("자료 가운데", [cx - WIN / 2, cy - WIN / 2, cx + WIN / 2, cy + WIN / 2]))
    old = C.AREA_BBOX
    tot = collections.Counter(); links = []
    for g, w in wins:
        C.AREA_BBOX = w
        n = res = med = eld = 0
        rx, ry = [], []
        try:
            for geo, a in battr.iter_buildings(save=False, quiet=True):
                n += 1
                use, kind = a["use"], a["kind"]
                if use in C.MEDICAL_USE: med += 1
                if use in C.ELDERLY_USE: eld += 1
                if use in C.RESIDENTIAL_USE or (not use.startswith("BDU") and kind in C.RESIDENTIAL_KIND):
                    res += 1
                    p = geo.PointOnSurface()
                    if p is not None and len(rx) < 300:
                        rx.append(p.GetX()); ry.append(p.GetY())
        except SystemExit as e:
            stop(f"건물 용도를 붙이지 못함: {e}", "위 안내대로 mapping.txt 고치기")
            break
        st = battr.LAST_STATS
        # 길 연결: 표본 집에서 ORIGIN_SNAP_MAX 안에 보도·도로 선(15m 간격 점)이 있나
        pts = []
        for k in ("sidewalk_cl", "road_cl"):
            for geo, _ in iter_layer(k, fields=[], bbox=[w[0] - 100, w[1] - 100, w[2] + 100, w[3] + 100]):
                geo = geo.Clone(); geo.Segmentize(15)
                for i in range(geo.GetGeometryCount() or 1):
                    sub = geo.GetGeometryRef(i) if geo.GetGeometryCount() else geo
                    pts += [q[:2] for q in sub.GetPoints() or []]
        if rx:
            if pts:
                d, _ = NearestIndex(np.array(pts)).query(np.c_[rx, ry], C.ORIGIN_SNAP_MAX)
                lk = float(np.mean(np.isfinite(d) & (d <= C.ORIGIN_SNAP_MAX)))
            else:
                lk = 0.0
            links.append(lk)
        else:
            lk = None
        tot.update(n=n, res=res, med=med, eld=eld)
        extra = f", 대장 연결 {st.get('link_rate', 0):.0%}" if st.get("mode") == "register" else ""
        print(f"  {g}: 건물 {n:,}, 주거 {res:,} ({res / n if n else 0:.0%}){extra}, 의료 {med}, 노유자 {eld}, "
              f"주거→길 연결 {'-' if lk is None else f'{lk:.0%}'}")
        if st.get("mode") == "register" and n and st.get("link_rate", 0) < 0.5:
            warn(f"{g}: 건축물대장 연결률 {st.get('link_rate', 0):.0%} (50% 미만)",
                 "mapping.txt 의 parcel_id·parcel_bldrgst·reg_pnu·reg_pk 확인 (필지 번호와 대장 번호가 같은 체계인지)")
    C.AREA_BBOX = old
    if not STOP and tot["n"]:
        rs = tot["res"] / tot["n"]
        print(f"  합계: 건물 {tot['n']:,}, 주거 비율 {rs:.0%}")
        if mode != "all" and (tot["res"] == 0 or rs >= 0.999):
            stop(f"주거 비율 {rs:.0%} (말이 안 됨)", "mapping.txt 의 bld_use 칸·building_attr_mode 확인 (layer 인데 용도 칸이 비었으면 register)")
        if links and np.mean(links) < 0.5:
            stop(f"주거 건물 → 길 연결 {np.mean(links):.0%} (50% 미만)", "길 레이어가 덜 들어왔거나 좌표계가 어긋남: layer_road_cl·map_folders·좌표계 확인")
    elif not STOP and wins:
        stop("표본 창에 건물이 0개", "대상 구에 건물 자료가 있는지 (map_folders·AREA_BBOX), layer_building 확인")
    # 목적지
    dest = {"정류장(bus_stop)": count_in(have.get("bus_stop", []), C.AREA_BBOX),
            "정거장(station)": count_in(have.get("station", []), C.AREA_BBOX),
            "약국(external)": len(read_csv(os.path.join(C.EXTERNAL, "pharmacy.csv"))),
            "엘리베이터 역 출입구(external)": len(read_csv(os.path.join(C.EXTERNAL, "subway_elevators.csv"))),
            "의료·노유자 건물(표본 창)": tot["med"] + tot["eld"]}
    print("  목적지: " + ", ".join(f"{k} {v:,}" for k, v in dest.items()))
    if sum(dest.values()) == 0:
        stop("목적지 0개", "정류장·정거장 레이어(layer_bus_stop·layer_station)와 external/pharmacy.csv 확인")

    print("\n=== 9. 예상 소요 시간 (대략) ===")
    nb = count_in(have["building"], C.AREA_BBOX)
    nl = count_in(have.get("road_cl", []) + have.get("sidewalk_cl", []), C.AREA_BBOX)
    lo, hi = estimate_minutes(nl)
    print(f"  읽을 건물 {nb:,}개, 길 선 {nl:,}개 → 02~05 약 {lo}~{hi}분 (이 맥 시험 기준 × 안심구역 PC 여유 3배, 대략)."
          f" 멈추면 python run_all.py --from <멈춘 번호>")


if __name__ == "__main__":
    path = os.path.join(C.OUTPUT, "check_report.txt")
    with Tee(path):
        print("# check.py ─ 출발 전 점검 (구조·비율·개수만, 값 없음)")
        main()
        print("\n=== 결과 ===")
        if STOP:
            print(f"!! 멈춤 {len(STOP)}건 → 위 '→' 대로 고친 뒤 python check.py 다시")
            for w, t in STOP:
                print(f"  - {w}")
        else:
            print(f"통과 (경고 {len(WARN)}건) → python run_all.py")
    print(f"(저장: output/check_report.txt)")
    sys.exit(1 if STOP else 0)
