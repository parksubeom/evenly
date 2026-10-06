# -*- coding: utf-8 -*-
"""
tools/prep_gis_building.py ─ GIS건물통합정보(공개) → analysis/hbi/external/gis_building.gpkg  (v6 building_attr_mode = gisbld 용)

[왜]  LX 건물에 용도·층수 칸이 없고 건축물대장도 필지로 잘 안 붙을 때의 3순위: 공개 GIS 건물 도형과 겹치는 면적으로 용도를 붙임.
      이 스크립트는 밖에서 미리 8개 구로 자르고, 도형 + 주용도(코드·이름)·지상층수·연면적만 남김 (그 밖의 칸은 버림).
[실행]  (QGIS 파이썬)  python tools/prep_gis_building.py <입력: shp·gpkg·zip 또는 그것이 든 폴더> [--all] [--shp] [--out 경로]
        --all : 서울 전역 (기본은 대상 5개 구 + 옆 3개 구)
        --shp : gpkg 대신 shp 로도 (반입 허용 확장자에 맞추려면)
[칸 찾기]  대소문자 무시. 별칭 + 값 모양(표본 300개, 값은 화면에 남기지 않음)으로 고름:
  use_cd   ← A8 · USABILITY · BDTYP_CD · MAIN_PURPS_CD · 건축물용도코드 · 주용도코드      (모양: 숫자 5자리, 예 02000)
  use_nm   ← A9 · BDTYP_NM · MAIN_PURPS_CD_NM · 건축물용도명 · 주용도명               (모양: 한글)
  grnd_flr ← A26 · GRND_FLR · GRO_FLO_CO · 지상층수                                   (모양: 정수)
  tot_area ← A14 · TOTALAREA · TOT_AREA · 연면적                                      (모양: 숫자)
  (A0~A28 같은 일련 칸 이름은 국가공간정보포털 판의 칸 순서를 따른 것. 실제 파일의 칸 이름을 보고 맞는지 확인할 것)
[출력]  EPSG:5186 다각형, 칸 use_cd·use_nm·grnd_flr·tot_area. 크기와 건물 수를 화면에 보임
"""
import argparse, glob, os, re, sys, zipfile, tempfile, collections
from osgeo import gdal, ogr, osr
gdal.UseExceptions(); ogr.UseExceptions(); osr.UseExceptions()

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "analysis", "hbi", "external", "gis_building.gpkg")
TARGET_GU = ["종로구", "중구", "관악구", "광진구", "강서구"]
NEIGHBOR_GU = ["성북구", "성동구", "동대문구"]
ALIASES = {
    "use_cd": (["A8", "USABILITY", "BDTYP_CD", "MAIN_PURPS_CD", "건축물용도코드", "주용도코드"], r"\d{5}"),
    "use_nm": (["A9", "BDTYP_NM", "MAIN_PURPS_CD_NM", "건축물용도명", "주용도명", "주용도코드명"], r".*[가-힣].*"),
    "grnd_flr": (["A26", "GRND_FLR", "GRO_FLO_CO", "지상층수"], r"-?\d+(\.0+)?"),
    "tot_area": (["A14", "TOTALAREA", "TOT_AREA", "연면적"], r"\d+(\.\d+)?"),
}
S5186 = osr.SpatialReference(); S5186.ImportFromEPSG(5186); S5186.SetAxisMappingStrategy(osr.OAMS_TRADITIONAL_GIS_ORDER)


def inputs(path):
    """입력 경로 → 벡터 파일 목록 (zip 은 임시 폴더에 풂)"""
    if os.path.isdir(path):
        fs = [p for e in ("shp", "gpkg", "zip") for p in glob.glob(os.path.join(path, "**", f"*.{e}"), recursive=True)]
        fs += [p for e in ("SHP", "GPKG", "ZIP") for p in glob.glob(os.path.join(path, "**", f"*.{e}"), recursive=True)]
    else:
        fs = [path]
    out = []
    for f in sorted(set(fs)):
        if f.lower().endswith(".zip"):
            d = tempfile.mkdtemp(prefix="gisbld_")
            with zipfile.ZipFile(f) as z:
                z.extractall(d)
            out += inputs(d)
        else:
            out.append(f)
    return out


def open_any(p):
    """.cpg 가 없는 shp 는 UTF-8·CP949 중 한글이 바르게 읽히는 쪽"""
    if p.lower().endswith(".shp") and not os.path.exists(os.path.splitext(p)[0] + ".cpg"):
        best = None
        for enc in ("UTF-8", "CP949"):
            ds = gdal.OpenEx(p, gdal.OF_VECTOR, open_options=[f"ENCODING={enc}"])
            lyr = ds.GetLayer(0)
            txt = [str(v) for f, _ in zip(lyr, range(300)) for v in f.items().values() if isinstance(v, str)]
            score = sum(1 for t in txt if re.search("[가-힣]", t)) - 5 * sum(1 for t in txt if "�" in t)
            if best is None or score > best[0]:
                best = (score, enc)
        return gdal.OpenEx(p, gdal.OF_VECTOR, open_options=[f"ENCODING={best[1]}"]), best[1]
    return gdal.OpenEx(p, gdal.OF_VECTOR), "파일 표시대로"


def pick_fields(names, sample):
    up = {n.upper(): n for n in names}
    got = {}
    for k, (al, pat) in ALIASES.items():
        for a in al:
            n = up.get(a.upper())
            if not n:
                continue
            v = [str(x).strip() for x in sample.get(n, []) if x not in (None, "")]
            if v and sum(1 for x in v if re.fullmatch(pat, x)) / len(v) >= 0.5:
                got[k] = n
                break
    return got


def gu_union(names):
    ds = ogr.Open(os.path.join(ROOT, "analysis", "hbi", "external", "dong_boundary.geojson"))
    lyr = ds.GetLayer(0)
    src = lyr.GetSpatialRef(); src.SetAxisMappingStrategy(osr.OAMS_TRADITIONAL_GIS_ORDER)
    ct = osr.CoordinateTransformation(src, S5186)
    u = None
    for f in lyr:
        if names and f.GetField("sggnm") not in names:
            continue
        g = f.GetGeometryRef().Clone(); g.Transform(ct)
        u = g if u is None else u.Union(g)
    return u


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("src"); ap.add_argument("--all", action="store_true"); ap.add_argument("--shp", action="store_true")
    ap.add_argument("--out", default=OUT)
    a = ap.parse_args()
    files = inputs(a.src)
    if not files:
        raise SystemExit(f"벡터 파일이 없습니다: {a.src}")
    clip = gu_union(None if a.all else set(TARGET_GU + NEIGHBOR_GU))
    os.makedirs(os.path.dirname(a.out), exist_ok=True)
    if os.path.exists(a.out):
        ogr.GetDriverByName("GPKG").DeleteDataSource(a.out)
    dst = ogr.GetDriverByName("GPKG").CreateDataSource(a.out)
    ol = dst.CreateLayer("gis_building", S5186, ogr.wkbMultiPolygon)
    for k in ("use_cd", "use_nm"):
        ol.CreateField(ogr.FieldDefn(k, ogr.OFTString))
    ol.CreateField(ogr.FieldDefn("grnd_flr", ogr.OFTInteger)); ol.CreateField(ogr.FieldDefn("tot_area", ogr.OFTReal))
    st = collections.Counter()
    ol.StartTransaction()
    for p in files:
        ds, enc = open_any(p)
        lyr = ds.GetLayer(0)
        d = lyr.GetLayerDefn()
        names = [d.GetFieldDefn(i).GetName() for i in range(d.GetFieldCount())]
        sample = collections.defaultdict(list)
        for f, _ in zip(lyr, range(300)):
            for n in names:
                sample[n].append(f.GetField(n))
        lyr.ResetReading()
        got = pick_fields(names, sample)
        s = lyr.GetSpatialRef()
        if s is not None:
            s.SetAxisMappingStrategy(osr.OAMS_TRADITIONAL_GIS_ORDER)
        ct = osr.CoordinateTransformation(s, S5186) if s is not None and not s.IsSame(S5186) else None
        print(f"입력 {os.path.basename(p)}: 객체 {lyr.GetFeatureCount():,}, 좌표계 {(s.GetAuthorityCode(None) or s.GetName()) if s else '없음(5186 으로 봄)'},"
              f" 인코딩 {enc}, 칸 {len(names)}개 {names[:30]}")
        print(f"  고른 칸: {got}  (못 찾은 칸은 빈 값)")
        for f in lyr:
            st["읽음"] += 1
            g = f.GetGeometryRef()
            if g is None:
                continue
            g = g.Clone()
            if ct:
                g.Transform(ct)
            if not g.Intersects(clip):
                continue
            if ogr.GT_Flatten(g.GetGeometryType()) == ogr.wkbPolygon:
                g = ogr.ForceToMultiPolygon(g)
            o = ogr.Feature(ol.GetLayerDefn())
            for k in ("use_cd", "use_nm"):
                if k in got and f.GetField(got[k]) not in (None, ""):
                    o.SetField(k, str(f.GetField(got[k])).strip())
            for k in ("grnd_flr", "tot_area"):
                if k in got:
                    try:
                        o.SetField(k, float(str(f.GetField(got[k])).replace(",", "")))
                    except (TypeError, ValueError):
                        pass
            o.SetGeometry(g)
            ol.CreateFeature(o)
            st["씀"] += 1
        ds = None
    ol.CommitTransaction()
    dst = None
    print(f"읽음 {st['읽음']:,} → {'서울 전역' if a.all else '8개 구'} 안 {st['씀']:,}개")
    print(f"출력: {os.path.relpath(a.out, ROOT)} ({os.path.getsize(a.out) / 1e6:.1f}MB)")
    if a.shp:
        sp = os.path.splitext(a.out)[0] + ".shp"
        gdal.VectorTranslate(sp, a.out, format="ESRI Shapefile", layerCreationOptions=["ENCODING=UTF-8"])
        tot = sum(os.path.getsize(x) for x in glob.glob(os.path.splitext(sp)[0] + ".*"))
        print(f"shp 도: {os.path.relpath(sp, ROOT)} 외 (모두 {tot / 1e6:.1f}MB)")


if __name__ == "__main__":
    main()
