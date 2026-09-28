# -*- coding: utf-8 -*-
"""데이터 탐색·읽기·DEM 샘플링 공통 함수"""
import glob, os, time, warnings
import numpy as np, pandas as pd, geopandas as gpd
from shapely.geometry import box
warnings.filterwarnings("ignore")
import config as C

def log(msg):
    print(time.strftime("[%H:%M:%S] "), msg, flush=True)

def find_files(root, keys, ext=".shp"):
    """root 하위에서 파일명에 keys 중 하나가 포함된 파일을 모두 찾음 (대소문자 무시)"""
    if not root or not os.path.exists(root):
        return []
    out = []
    for p in glob.glob(os.path.join(root, "**", "*"), recursive=True):
        if not p.lower().endswith(ext.lower()):
            continue
        name = os.path.basename(p).upper()
        if any(k.upper() in name for k in keys):
            out.append(p)
    return sorted(set(out))

def guess_crs(bounds):
    """좌표 범위로 좌표계 추정 (prj 없을 때)"""
    x = (bounds[0] + bounds[2]) / 2
    if 100000 < x < 400000: return "EPSG:5186"   # GRS80 중부원점
    if 800000 < x < 1200000: return "EPSG:5179"  # UTM-K
    if 120 < x < 135: return "EPSG:4326"
    return C.DEFAULT_CRS

def read_one(path):
    last = None
    for enc in C.SHP_ENCODINGS:
        try:
            return gpd.read_file(path, encoding=enc)
        except Exception as e:
            last = e
    raise last

def read_layer(key, bbox=None):
    files = find_files(C.DATA_ROOT_MAP, C.LAYERS[key])
    if not files:
        log(f"  ! 레이어 없음: {key} {C.LAYERS[key]}")
        return gpd.GeoDataFrame(geometry=[], crs=C.TARGET_CRS)
    parts = []
    for f in files:
        try:
            g = read_one(f)
        except Exception as e:
            log(f"  ! 읽기 실패 {f}: {e}"); continue
        if len(g) == 0: continue
        if g.crs is None:
            g = g.set_crs(guess_crs(g.total_bounds))
        parts.append(g.to_crs(C.TARGET_CRS))
    if not parts:
        return gpd.GeoDataFrame(geometry=[], crs=C.TARGET_CRS)
    g = gpd.GeoDataFrame(pd.concat(parts, ignore_index=True), crs=C.TARGET_CRS)
    g = g[g.geometry.notna() & ~g.geometry.is_empty]
    bbox = bbox or C.AREA_BBOX
    if bbox:
        g = g[g.intersects(box(*bbox))]
    log(f"  {key}: 파일 {len(files)}개, 객체 {len(g):,}개")
    return g.reset_index(drop=True)

class DEM:
    """여러 DEM 타일을 병합해 메모리에 올리고, 좌표별 고도를 쌍선형 보간으로 추출"""
    def __init__(self, root, bbox=None, exts=(".img", ".tif", ".tiff", ".asc")):
        import rasterio
        from rasterio.merge import merge
        files = []
        for e in exts:
            files += find_files(root, [""], e)
        if not files:
            raise FileNotFoundError(f"DEM 파일 없음: {root}")
        srcs = [rasterio.open(f) for f in files]
        crs = srcs[0].crs
        self.src_crs = crs.to_string() if crs else guess_crs(srcs[0].bounds)
        bbox = bbox or C.AREA_BBOX
        bnds = None
        if bbox:
            bnds = tuple(bbox) if self.src_crs == C.TARGET_CRS else tuple(
                gpd.GeoSeries([box(*bbox)], crs=C.TARGET_CRS).to_crs(self.src_crs).total_bounds)
        arr, tr = merge(srcs, bounds=bnds, nodata=np.nan, dtype="float32")
        self.arr = arr[0].astype("float32")
        self.arr[(self.arr < -100) | (self.arr > 3000)] = np.nan
        self.tr = tr
        for s in srcs: s.close()
        log(f"  DEM: 파일 {len(files)}개, 격자 {self.arr.shape}, 해상도 {tr.a:.2f}m, 좌표계 {self.src_crs}")
        from pyproj import Transformer
        self.tf = None if self.src_crs == C.TARGET_CRS else Transformer.from_crs(C.TARGET_CRS, self.src_crs, always_xy=True)

    def sample(self, xs, ys):
        xs, ys = np.asarray(xs, float), np.asarray(ys, float)
        if self.tf: xs, ys = self.tf.transform(xs, ys)
        c, r = (~self.tr) * (xs, ys)
        c, r = np.asarray(c) - 0.5, np.asarray(r) - 0.5
        c0, r0 = np.floor(c).astype(int), np.floor(r).astype(int)
        dc, dr = c - c0, r - r0
        H, W = self.arr.shape
        def v(rr, cc):
            ok = (rr >= 0) & (rr < H) & (cc >= 0) & (cc < W)
            out = np.full(rr.shape, np.nan, "float32")
            out[ok] = self.arr[rr[ok], cc[ok]]
            return out
        z = (v(r0, c0) * (1 - dc) * (1 - dr) + v(r0, c0 + 1) * dc * (1 - dr) +
             v(r0 + 1, c0) * (1 - dc) * dr + v(r0 + 1, c0 + 1) * dc * dr)
        near = self.arr[np.clip(np.rint(r).astype(int), 0, H - 1), np.clip(np.rint(c).astype(int), 0, W - 1)]  # 가장자리는 최근접 값
        return np.where(np.isnan(z), near, z)

def load_points_csv(path, lon="lon", lat="lat"):
    df = pd.read_csv(path, encoding="utf-8-sig")
    df = df.dropna(subset=[lon, lat])
    g = gpd.GeoDataFrame(df, geometry=gpd.points_from_xy(df[lon], df[lat]), crs="EPSG:4326")
    return g.to_crs(C.TARGET_CRS)
