# -*- coding: utf-8 -*-
"""
[1일차 첫 작업] 제공 데이터 구조 확인
 - 폴더 안의 레이어 코드, 파일 수, 좌표계, 좌표 범위, 필드명, 주요 코드값 분포를 출력
 - 결과는 work/inspect_report.txt 에 저장 (메타정보만 기록, 개별 객체 값은 기록하지 않음)
실행: python 01_inspect.py
"""
import os, re, sys, collections
import config as C
from lib.io_utils import find_files, read_one, guess_crs, log

lines = []
def out(s=""):
    print(s); lines.append(str(s))

out("=== 1. 수치지형도 폴더 내 레이어 코드 목록 ===")
allshp = find_files(C.DATA_ROOT_MAP, [""], ".shp")
out(f"shp 파일 총 {len(allshp)}개  (루트: {C.DATA_ROOT_MAP})")
codes = collections.Counter()
for p in allshp:
    m = re.search(r"N3[APLT]_[A-Z]\d{7}", os.path.basename(p).upper())
    codes[m.group(0) if m else os.path.splitext(os.path.basename(p))[0]] += 1
for k, v in sorted(codes.items()):
    out(f"  {k}: {v}개")

out("\n=== 2. 분석에 쓰는 레이어 점검 ===")
for key, keys in C.LAYERS.items():
    files = find_files(C.DATA_ROOT_MAP, keys)
    if not files:
        out(f"[없음] {key} {keys}  ← 파일명이 다르면 config.LAYERS 수정"); continue
    g = read_one(files[0])
    crs = g.crs.to_string() if g.crs else f"prj 없음 → 추정 {guess_crs(g.total_bounds)}"
    out(f"[있음] {key}: 파일 {len(files)}개 / 첫 파일 객체 {len(g)}개 / 좌표계 {crs}")
    out(f"       범위 {[round(b) for b in g.total_bounds]}")
    out(f"       필드 {list(g.columns)}")
    for col in C.COL.values():
        if col in g.columns:
            out(f"       {col} 분포: {{k: int(v) for k, v in g[col].astype(str).value_counts().head(8).items()}}")

out("\n=== 3. DEM ===")
for root, nm in [(C.DATA_ROOT_DEM, "DEM 5m"), (C.DATA_ROOT_DEM1M, "DEM 1m")]:
    if not root: continue
    fs = []
    for e in (".img", ".tif", ".tiff", ".asc"):
        fs += find_files(root, [""], e)
    out(f"{nm}: 파일 {len(fs)}개")
    if fs:
        import rasterio
        with rasterio.open(fs[0]) as s:
            out(f"  예시 {os.path.basename(fs[0])}: 크기 {s.width}x{s.height}, 해상도 {s.res}, 좌표계 {s.crs}, nodata {s.nodata}")
            out(f"  범위 {[round(b) for b in s.bounds]}")

out("\n=== 4. 반입 공개데이터 ===")
for f in sorted(os.listdir(C.EXTERNAL)) if os.path.exists(C.EXTERNAL) else []:
    out(f"  {f}")

os.makedirs(C.WORK, exist_ok=True)
with open(os.path.join(C.WORK, "inspect_report.txt"), "w", encoding="utf-8") as fp:
    fp.write("\n".join(lines))
log("완료 → work/inspect_report.txt")
