# -*- coding: utf-8 -*-
"""
01_inspect.py ─ [1일차 가장 먼저] 제공받은 데이터가 어떻게 생겼는지 확인

[실행]  python 01_inspect.py
[하는 일] 데이터 내용은 건드리지 않고 "구조"만 봅니다.
  0. 실행 환경 (Python·GDAL 버전, scipy·matplotlib 설치 여부)
  1. 수치지형도 폴더에 어떤 레이어 코드의 파일이 몇 개 있는지
  2. 분석에 쓰는 레이어별: 파일 수, 좌표계, 좌표 범위, 속성 이름, 주요 코드 분포
  3. DEM 파일 수, 해상도, 좌표
  4. external 폴더에 반입한 공개데이터 목록
[결과] 화면 + work/inspect_report.txt  (개별 객체 값은 기록하지 않으므로 메모해 나와도 되는 수준)

[결과 보는 법 → 고칠 곳]
  "[없음] ..."               → config.py 의 LAYERS 에 실제 파일명 글자 추가
  "prj 없음" + 범위 x 80만대 → config.py 의 DEFAULT_CRS = "EPSG:5179"
  BPRP_SE 분포에 BDU001 없음 → config.py 의 RESIDENTIAL_USE 를 실제 코드로
  shp 파일 총 0개            → config.py 의 DATA_ROOT_MAP 경로가 틀림
"""
import os, re, collections, sys
import config as C
from lib.deps import HAS_SCIPY, HAS_MPL
from lib.qio import find_files, open_vector, layer_srs, log
from osgeo import gdal, osr
gdal.UseExceptions(); osr.UseExceptions()

lines = []                       # 화면에 찍은 내용을 모아 두었다가 마지막에 파일로 저장
def out(s=""):
    print(s)
    lines.append(str(s))

# 0. 실행 환경 ────────────────────────────────────────────
out(f"=== 0. 실행 환경 ===\nPython {sys.version.split()[0]} / GDAL {gdal.__version__} / "
    f"scipy {'있음' if HAS_SCIPY else '없음(대체 구현 사용)'} / matplotlib {'있음' if HAS_MPL else '없음(QGIS로 지도 제작)'}")

# 1. 레이어 코드 목록 ─────────────────────────────────────
out("\n=== 1. 수치지형도 폴더 내 레이어 코드 ===")
allshp = find_files(C.DATA_ROOT_MAP, [""], ".shp")
out(f"shp 파일 총 {len(allshp)}개 (루트: {C.DATA_ROOT_MAP})")
codes = collections.Counter()    # Counter: 개수 세기용 딕셔너리 {"N3L_A0020000": 12, ...}
for p in allshp:
    # 파일명에서 N3L_A0020000 같은 레이어 코드 패턴을 찾음 (정규식)
    m = re.search(r"N3[APLT]_[A-Z]\d{7}", os.path.basename(p).upper())
    codes[m.group(0) if m else os.path.splitext(os.path.basename(p))[0]] += 1
for k, v in sorted(codes.items()):
    out(f"  {k}: {v}개")

# 2. 분석용 레이어 점검 ───────────────────────────────────
out("\n=== 2. 분석에 쓰는 레이어 점검 ===")
for key, keys in C.LAYERS.items():
    files = find_files(C.DATA_ROOT_MAP, keys)
    if not files:
        out(f"[없음] {key} {keys}  ← 파일명이 다르면 config.LAYERS 수정")
        continue
    ds = open_vector(files[0])                 # 첫 번째 파일만 열어서 구조 확인
    lyr = ds.GetLayer(0)
    s, has = layer_srs(lyr)
    defn = lyr.GetLayerDefn()
    names = [defn.GetFieldDefn(i).GetName() for i in range(defn.GetFieldCount())]
    ext = lyr.GetExtent()
    crs_txt = ("prj 있음 " + (s.GetAuthorityCode(None) or s.GetName())) if has else ("prj 없음 → 추정 " + (s.GetAuthorityCode(None) or ""))
    out(f"[있음] {key}: 파일 {len(files)}개 / 첫 파일 객체 {lyr.GetFeatureCount()}개 / 좌표계 {crs_txt}")
    out(f"       범위 x {ext[0]:.0f}~{ext[1]:.0f}, y {ext[2]:.0f}~{ext[3]:.0f}")
    out(f"       필드 {names}")
    for col in C.COL.values():                # 건물 용도 등 주요 코드 칸의 값 분포 (상위 8개)
        if col in names:
            cnt = collections.Counter(str(f.GetField(col)) for f in lyr)
            out(f"       {col} 분포: {dict(cnt.most_common(8))}")
            lyr.ResetReading()                 # 다시 처음부터 읽을 수 있게 되감기
    ds = None

# 3. DEM ─────────────────────────────────────────────────
out("\n=== 3. DEM ===")
for root, nm in [(C.DATA_ROOT_DEM, "DEM 5m"), (C.DATA_ROOT_DEM1M, "DEM 1m")]:
    if not root:
        continue
    fs = [f for e in (".img", ".tif", ".tiff", ".asc") for f in find_files(root, [""], e)]
    out(f"{nm}: 파일 {len(fs)}개")
    if fs:
        d = gdal.Open(fs[0])
        gt = d.GetGeoTransform()
        b = d.GetRasterBand(1)
        out(f"  예시 {os.path.basename(fs[0])}: {d.RasterXSize}x{d.RasterYSize}, 해상도 {gt[1]:.2f}, "
            f"nodata {b.GetNoDataValue()}, 좌표계 {'있음' if d.GetProjection() else '없음'}")
        out(f"  좌상단 ({gt[0]:.0f}, {gt[3]:.0f})   ← 수치지형도 범위와 숫자 크기가 비슷해야 정상")

# 3-1. 국토정보필지 (방문 때 제공) ────────────────────────
if C.DATA_ROOT_PARCEL:
    out("\n=== 3-1. 국토정보필지 ===")
    ps = find_files(C.DATA_ROOT_PARCEL, [""], ".shp")
    out(f"shp 파일 {len(ps)}개: {[os.path.basename(p) for p in ps[:5]]}{' ...' if len(ps) > 5 else ''}")
    if ps:
        ds = open_vector(ps[0], C.PARCEL_ENCODING); lyr = ds.GetLayer(0); defn = lyr.GetLayerDefn()
        out(f"  필드 {[defn.GetFieldDefn(i).GetName() for i in range(defn.GetFieldCount())]}  ← PNU, EMD_CD, JIMOK 이 있어야 함")
        if defn.GetFieldIndex("JIMOK") >= 0:
            vals = collections.Counter(str(f.GetField("JIMOK")) for _, f in zip(range(2000), lyr))
            out(f"  JIMOK(지목) 예시: {dict(vals.most_common(6))}  ← 한글이 깨지면 config.PARCEL_ENCODING 변경")
        ds = None

# 3-2. 상호제공데이터 파일의 열 이름 (config.JOIN_DATA 채우기용) ──────
for nm, cfg in C.JOIN_DATA.items():
    if cfg.get("path") and os.path.exists(cfg["path"]):
        for enc in ("utf-8-sig", "cp949"):
            try:
                head = open(cfg["path"], encoding=enc).readline().strip()
                out(f"\n=== 3-2. {nm} 열 이름 ===\n  {head}  ← 이 중에서 code_col·value_cols 를 골라 config 에 적기")
                break
            except UnicodeDecodeError:
                continue

# 4. 반입 공개데이터 ──────────────────────────────────────
out("\n=== 4. 반입 공개데이터 ===")
for f in sorted(os.listdir(C.EXTERNAL)) if os.path.exists(C.EXTERNAL) else []:
    out(f"  {f}")

os.makedirs(C.WORK, exist_ok=True)
open(os.path.join(C.WORK, "inspect_report.txt"), "w", encoding="utf-8").write("\n".join(lines))
log("완료 → work/inspect_report.txt")
