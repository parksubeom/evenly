# -*- coding: utf-8 -*-
"""
lib/schema.py ─ [v6] 받은 자료의 "구조" 만 기록 → output/schema/schema.txt  (ogrinfo -so 수준, 값 없음)

[왜] 1차 방문 뒤 반출 심사를 거쳐 받은 schema.txt(ogrinfo 결과)로 다음 번 코드를 맞췄음. v6 는 run_all 이 매번 자동으로 남김.
[적는 것] 파일 이름, 도형 종류, 객체 수, 좌표계, 범위, 칸 이름·형식 / DEM 크기·해상도 / CSV 칸 이름·행 수·인코딩
[적지 않는 것] 칸의 값 (주소·코드·이름 등). 범위는 m 단위 반올림
"""
import os, glob
import config as C
from lib.qio import find_files, open_vector, layer_srs, in_map_folders, safe_head
from osgeo import gdal, ogr

TYPES = {ogr.OFTString: "문자", ogr.OFTInteger: "정수", ogr.OFTInteger64: "정수", ogr.OFTReal: "실수", ogr.OFTDate: "날짜"}


def vector_lines(path, root, enc=None):
    out = [f"  {os.path.relpath(path, root)}"]
    try:
        ds = open_vector(path, enc)
        lyr = ds.GetLayer(0)
        s, has = layer_srs(lyr)
        d = lyr.GetLayerDefn()
        x0, x1, y0, y1 = lyr.GetExtent()
        out.append(f"    도형 {ogr.GeometryTypeToName(lyr.GetGeomType())}, 객체 {lyr.GetFeatureCount():,}, 좌표계 "
                   f"{'prj ' + (s.GetAuthorityCode(None) or s.GetName()) if has else 'prj 없음'}, 범위 x {x0:.0f}~{x1:.0f} y {y0:.0f}~{y1:.0f}")
        out.append("    칸 " + ", ".join(f"{d.GetFieldDefn(i).GetName()}({TYPES.get(d.GetFieldDefn(i).GetType(), '기타')})"
                                     for i in range(d.GetFieldCount())))
        ds = None
    except Exception as e:                        # 구조를 못 읽어도 실행은 계속
        out.append(f"    읽기 실패: {type(e).__name__}")
    return out


def csv_head(p):
    """CSV 첫 줄(칸 이름)·행 수·인코딩·구분자만 (큰 파일도 빠르게). 값은 읽지 않음"""
    import csv as _csv
    raw = open(p, "rb").read(1 << 16)
    enc = "utf-8-sig"
    for e in ("utf-8-sig", "cp949", "euc-kr"):
        try:
            raw.decode(e)
            enc = e
            break
        except UnicodeDecodeError as x:
            if x.start > len(raw) - 4:            # 잘린 글자 때문이면 이 인코딩 맞음
                enc = e
                break
    with open(p, encoding=enc, errors="replace", newline="") as f:
        first = f.readline()
    sep = max([",", "|", "\t"], key=first.count)
    head = next(_csv.reader([first], delimiter=sep), [])
    with open(p, "rb") as f:
        n = sum(chunk.count(b"\n") for chunk in iter(lambda: f.read(1 << 20), b""))
    return head, max(n - 1, 0), enc, sep


def dump(path=None):
    path = path or os.path.join(C.OUTPUT, "schema", "schema.txt")
    L = ["# 받은 자료의 구조 (값은 적지 않음). v6 run_all.py 가 자동 저장"]
    if C.DATA_ROOT_MAP:
        fs = [f for f in find_files(C.DATA_ROOT_MAP, [""], ".shp") if in_map_folders(f)]
        L += ["", f"[수치지형도] shp {len(fs)}개 (map_folders {len(C.MAP_FOLDERS) or '전체'})"]
        for f in fs:
            L += vector_lines(f, C.DATA_ROOT_MAP)
    for root, nm in [(C.DATA_ROOT_DEM, "DEM 5m"), (C.DATA_ROOT_DEM1M, "DEM 1m")]:
        if not root:
            continue
        fs = [f for e in (".img", ".tif", ".tiff", ".asc") for f in find_files(root, [""], e)]
        L += ["", f"[{nm}] 파일 {len(fs)}개"]
        for f in fs[:200]:
            try:
                d = gdal.Open(f)
                gt = d.GetGeoTransform()
                L.append(f"  {os.path.relpath(f, root)}: {d.RasterXSize}x{d.RasterYSize}, 해상도 {gt[1]:.2f}, 좌표계 {'있음' if d.GetProjection() else '없음'}")
                d = None
            except Exception as e:
                L.append(f"  {os.path.relpath(f, root)}: 읽기 실패 {type(e).__name__}")
    if C.DATA_ROOT_PARCEL:
        fs = find_files(C.DATA_ROOT_PARCEL, [""], ".shp")
        L += ["", f"[국토정보필지] shp {len(fs)}개"]
        for f in fs:
            L += vector_lines(f, C.DATA_ROOT_PARCEL, C.PARCEL_ENCODING)
    csvs = [(k, v.get("path")) for d in (C.JOIN_DATA, C.POINT_DATA, C.LEGAL_DONG_DATA) for k, v in d.items() if v.get("path")]
    if getattr(C, "REGISTER_FILE", None) and os.path.exists(C.REGISTER_FILE):
        csvs.append(("건축물대장", C.REGISTER_FILE))
    if csvs:
        L += ["", "[CSV]"]
        for k, p in csvs:
            try:
                head, n, enc, sep = csv_head(p)
                shown, nohead = safe_head(head, 400)          # [v6.2] 머리줄 없는 CSV 면 첫 행 값 대신 모양만
                L.append(f"  {k}: {os.path.basename(p)}, 약 {n:,}행, 인코딩 {enc}, 구분자 {sep!r}, " + (shown if nohead else f"칸 {shown}"))
            except Exception as e:
                L.append(f"  {k}: {os.path.basename(p) if p else ''} 읽기 실패 {type(e).__name__}")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    open(path, "w", encoding="utf-8-sig").write("\n".join(L) + "\n")
    return path
