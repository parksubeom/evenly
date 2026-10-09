# -*- coding: utf-8 -*-
"""
lib/qio.py ─ 파일 읽고 쓰기 담당 (입출력 = IO)

[이 파일이 하는 일]
 1) 로그 출력 (진행상황을 시간과 함께 화면에 표시)
 2) 좌표계 변환 (GPS 경위도 ↔ 미터 좌표 등)
 3) 폴더 안에서 shp/img 파일 찾기
 4) shp(지도 도형 파일) 읽기
 5) DEM(높이 격자 이미지) 읽고, 원하는 좌표의 높이 알아내기
 6) CSV 읽기·쓰기, 결과를 QGIS에서 열 수 있는 GPKG 파일로 저장하기

[사용 라이브러리]
 - numpy (np): 숫자 배열을 한꺼번에 계산하는 라이브러리.
     JS에서 arr.map(x => x*2) 를 쓰는 대신, 파이썬 numpy 는 arr * 2 라고만 쓰면 배열 전체가 계산됩니다.
 - osgeo (gdal, ogr, osr): QGIS 안에 들어 있는 지도 데이터 처리 라이브러리.
     gdal = 래스터(격자 이미지, DEM), ogr = 벡터(점·선·면, shp), osr = 좌표계
"""
import os, glob, time, csv, math
import numpy as np
from osgeo import gdal, ogr, osr

# 오류가 나면 조용히 넘어가지 말고 예외(에러)를 던지라는 설정 (JS의 strict mode 비슷)
gdal.UseExceptions(); ogr.UseExceptions(); osr.UseExceptions()
import lib.runlog as _RL
_RL.gdal_errors(gdal)      # [v6.2] GDAL 경고 글자도 값 가림·work/logs 로 (기록 장치가 켜졌을 때만. QGIS 콘솔에서는 그대로)
import config as C


def log(msg):
    """[12:30:01] 메시지 형태로 화면에 출력. flush=True 는 즉시 화면에 표시하라는 뜻"""
    print(time.strftime("[%H:%M:%S] "), msg, flush=True)


# ───────────────────────── 좌표계 ─────────────────────────
def srs_from(s):
    """"EPSG:5186" 같은 문자열 → 좌표계 객체"""
    r = osr.SpatialReference()
    if isinstance(s, str) and s.upper().startswith("EPSG:"):
        r.ImportFromEPSG(int(s.split(":")[1]))       # "EPSG:5186" → 5186
    else:
        r.SetFromUserInput(s)
    # 좌표 순서를 항상 (x, y) = (동서, 남북) = (경도, 위도) 로 고정. 안 하면 경위도가 뒤집힐 수 있음
    r.SetAxisMappingStrategy(osr.OAMS_TRADITIONAL_GIS_ORDER)
    return r

TARGET = srs_from(C.TARGET_CRS)   # 분석에 쓰는 기준 좌표계 (config 에서 지정)


def transformer(src, dst=None):
    """src 좌표계 → dst 좌표계(기본: 분석 기준) 변환기. 같은 좌표계면 None(변환 불필요)"""
    src = src if isinstance(src, osr.SpatialReference) else srs_from(src)
    src.SetAxisMappingStrategy(osr.OAMS_TRADITIONAL_GIS_ORDER)
    dst = dst or TARGET              # dst 가 None 이면 TARGET 사용 (JS의 dst ?? TARGET)
    if src.IsSame(dst):
        return None
    return osr.CoordinateTransformation(src, dst)


def transform_xy(ct, xs, ys):
    """x 배열, y 배열을 변환기 ct 로 한꺼번에 변환해서 (새 x 배열, 새 y 배열) 반환"""
    if ct is None:
        return np.asarray(xs, float), np.asarray(ys, float)
    # np.c_[xs, ys] : 두 배열을 [[x1,y1],[x2,y2],...] 모양으로 붙임 (JS의 xs.map((x,i)=>[x, ys[i]]))
    pts = ct.TransformPoints(np.c_[np.asarray(xs, float), np.asarray(ys, float)].tolist())
    a = np.asarray(pts, float)
    return a[:, 0], a[:, 1]          # a[:, 0] = 모든 행의 0번째 열 = 새 x 값들


def guess_crs(minx, maxx):
    """좌표계 정보가 없는 파일의 좌표 숫자 크기를 보고 좌표계를 추측"""
    x = (minx + maxx) / 2
    if 100000 < x < 400000: return "EPSG:5186"     # 중부원점 (서울 수치지형도)
    if 800000 < x < 1200000: return "EPSG:5179"    # UTM-K
    if 120 < x < 135: return "EPSG:4326"           # 경도 값 (GPS)
    return C.DEFAULT_CRS


def raster_envelope(files):
    """[v6.1a] 래스터(DEM) 파일들의 범위를 **분석 좌표계**로 (x0, y0, x1, y1).
    DEM 좌표계가 분석 좌표계와 다르면(예: 1차 DEM 은 KGD2002 = 5179, 분석은 5186) 네 모서리를 바꿔 감싸는 네모로.
    v6.1 까지는 바꾸지 않고 비교해 setup·check 가 "DEM 이 대상 구를 다 덮지 못함" 을 잘못 띄웠음 (분석 자체는 DEM 클래스가 바꿔서 영향 없음)"""
    vrt = gdal.BuildVRT("/vsimem/env.vrt", list(files))
    gt, nx, ny, wkt = vrt.GetGeoTransform(), vrt.RasterXSize, vrt.RasterYSize, vrt.GetProjection()
    vrt = None
    gdal.Unlink("/vsimem/env.vrt")
    x0, x1, y0, y1 = gt[0], gt[0] + gt[1] * nx, gt[3] + gt[5] * ny, gt[3]
    if wkt:
        s = osr.SpatialReference(wkt=wkt)
        s.SetAxisMappingStrategy(osr.OAMS_TRADITIONAL_GIS_ORDER)
    else:
        s = srs_from(guess_crs(x0, x1))
    xs, ys = transform_xy(transformer(s), [x0, x1, x0, x1], [y0, y0, y1, y1])
    return (float(min(xs)), float(min(ys)), float(max(xs)), float(max(ys))), abs(gt[1])


# ───────────────────────── 파일 찾기 ─────────────────────────
def find_files(root, keys, ext=".shp"):
    """root 폴더와 모든 하위 폴더에서, 확장자가 ext 이고 파일명에 keys 중 하나가 들어간 파일 목록.
    keys=[""] 이면 확장자만 맞으면 전부 (빈 글자는 모든 이름에 포함되므로)"""
    if not root or not os.path.exists(root):
        return []
    out = []
    # "**" + recursive=True : 모든 하위 폴더까지 뒤짐
    for p in glob.glob(os.path.join(root, "**", "*"), recursive=True):
        name = os.path.basename(p).upper()           # 대소문자 무시 비교를 위해 대문자로
        if p.lower().endswith(ext.lower()) and any(k.upper() in name for k in keys):
            out.append(p)
    return sorted(set(out))                          # 중복 제거 + 정렬


def in_map_folders(path):
    """[v6] config.MAP_FOLDERS(mapping.txt 의 map_folders) 가 있으면 그 하위 폴더 안의 파일만 True. 비어 있으면 모두 True"""
    sel = getattr(C, "MAP_FOLDERS", None)
    if not sel or not C.DATA_ROOT_MAP:
        return True
    rel = os.path.relpath(os.path.abspath(path), os.path.abspath(C.DATA_ROOT_MAP)).replace("\\", "/")
    return any(rel == f.replace("\\", "/").strip("/") or rel.startswith(f.replace("\\", "/").strip("/") + "/") for f in sel)


def layer_files(key):
    """[v6] 수치지형도 레이어 key 의 파일 목록 (config.LAYERS 의 글자가 파일명에 있고, map_folders 안에 있는 것)"""
    return [f for f in find_files(C.DATA_ROOT_MAP, C.LAYERS.get(key) or []) if in_map_folders(f)] if C.LAYERS.get(key) else []


# ───────────────────────── 벡터(shp) 읽기 ─────────────────────────
def open_vector(path, encoding=None):
    """shp 등 벡터 파일 열기. .cpg(인코딩 정보) 파일이 없으면 한글 인코딩을 지정해서 엶
    encoding: 직접 지정 (없으면 config.SHP_ENCODING)"""
    need_enc = path.lower().endswith(".shp") and not os.path.exists(os.path.splitext(path)[0] + ".cpg")
    opts = [f"ENCODING={encoding or C.SHP_ENCODING}"] if need_enc else []
    try:
        return gdal.OpenEx(path, gdal.OF_VECTOR, open_options=opts)
    except Exception:
        return gdal.OpenEx(path, gdal.OF_VECTOR)   # 옵션 때문에 실패하면 옵션 없이 다시


def layer_srs(lyr):
    """레이어의 좌표계와, 원래 좌표계 정보가 있었는지(True/False)를 반환"""
    s = lyr.GetSpatialRef()
    if s is None:                                  # .prj 파일이 없는 경우 → 추측
        ext = lyr.GetExtent()                      # (x최소, x최대, y최소, y최대)
        return srs_from(guess_crs(ext[0], ext[1])), False
    s = s.Clone()
    s.SetAxisMappingStrategy(osr.OAMS_TRADITIONAL_GIS_ORDER)
    return s, True


def iter_layer(key=None, files=None, fields=None, bbox=None, encoding=None):
    """레이어의 도형과 속성을 하나씩 꺼내 주는 함수 (제너레이터).

    사용법:  for geom, attrs in iter_layer("building"):  ...
      - geom  : 도형 객체 (분석 좌표계로 변환 완료)
      - attrs : 속성 딕셔너리. 예) {"BPRP_SE": "BDU001", "BFLR_CO": "3"}
    [제너레이터란] return 대신 yield 를 쓰면 결과를 한꺼번에 만들지 않고 하나씩 넘겨 줍니다.
      파일이 커도 메모리를 적게 씁니다. (JS의 function* / yield 와 같음)

    key    : config.LAYERS 의 키 (예: "building"). 그 레이어 파일을 전부 찾아 이어서 읽음
    files  : key 대신 파일 목록을 직접 줄 수도 있음
    fields : 읽을 속성 이름 목록 (None 이면 전부). [v6] 대소문자 무시 (파일이 "pnu" 여도 "PNU" 로 요청 가능),
             돌려주는 키는 요청한 이름 그대로. None·"?" 처럼 비어 있는 이름은 건너뜀
    bbox   : 이 범위 안의 도형만 (None 이면 config.AREA_BBOX, 그것도 None 이면 전체. [v6] False 면 무조건 전체)
    encoding: 한글 인코딩 직접 지정 (필지는 config.PARCEL_ENCODING)
    """
    files = files if files is not None else layer_files(key)
    bbox = C.AREA_BBOX if bbox is None else (bbox or None)    # [v6] bbox=False 면 AREA_BBOX 도 무시하고 전부
    for f in files:
        try:
            ds = open_vector(f, encoding)
        except RuntimeError as e:                             # [v6.2] 손상된 shp 처럼 GDAL 글자가 비어 있어도 어느 파일인지 남게
            raise RuntimeError(f"{os.path.basename(f)} 읽기 실패: {e}") from e
        if ds is None:
            continue
        lyr = ds.GetLayer(0)
        s, _ = layer_srs(lyr)
        ct = transformer(s)                                   # 파일 좌표계 → 분석 좌표계
        if bbox:                                              # 범위 필터 (파일 좌표계 기준으로 바꿔서 적용)
            if ct is None:
                lyr.SetSpatialFilterRect(*bbox)               # *bbox : 리스트를 인자 4개로 펼침 (JS의 ...bbox)
            else:
                inv = osr.CoordinateTransformation(TARGET, s)
                (x0, y0, _), (x1, y1, _) = inv.TransformPoint(bbox[0], bbox[1]), inv.TransformPoint(bbox[2], bbox[3])
                lyr.SetSpatialFilterRect(min(x0, x1), min(y0, y1), max(x0, x1), max(y0, y1))
        defn = lyr.GetLayerDefn()
        names = [defn.GetFieldDefn(i).GetName() for i in range(defn.GetFieldCount())]   # 속성 이름 목록
        if fields is None:
            want = [(n, n) for n in names]
        else:                                                 # [v6] (돌려줄 이름, 파일의 실제 이름) 쌍, 대소문자 무시
            up = {}
            for n in names:
                up.setdefault(n.upper(), n)
            want = [(q, up[q.upper()]) for q in dict.fromkeys(fields) if q and q.upper() in up]
        for feat in lyr:                                      # 도형(feature) 하나씩
            g = feat.GetGeometryRef()
            if g is None or g.IsEmpty():
                continue
            g = g.Clone()                                     # 파일을 닫아도 쓸 수 있게 복사
            if ct is not None:
                g.Transform(ct)
            g.FlattenTo2D()                                   # 높이(z) 좌표는 버리고 평면 좌표만
            yield g, {q: feat.GetField(n) for q, n in want}
        ds = None                                             # 파일 닫기


def coverage_envelopes(keys=("sidewalk_cl", "road_cl")):
    """받은 데이터가 덮는 범위 = 레이어 파일(도엽)마다의 네모 범위 목록 [(x0, y0, x1, y1), ...] (분석 좌표계)
    경계 효과 처리(03_hbi.py)에 사용: 이 범위들의 합집합 가장자리에 가까운 건물을 표시"""
    out = []
    for key in keys:
        for f in layer_files(key):
            ds = open_vector(f)
            if ds is None:
                continue
            lyr = ds.GetLayer(0)
            if lyr.GetFeatureCount() == 0:
                continue
            s, _ = layer_srs(lyr)
            x0, x1, y0, y1 = lyr.GetExtent()
            xs, ys = transform_xy(transformer(s), [x0, x1, x0, x1], [y0, y0, y1, y1])   # 네 모서리 변환
            out.append((min(xs), min(ys), max(xs), max(ys)))
            ds = None
    return out


# ───────────────────────── DEM(높이) ─────────────────────────
class DEM:
    """DEM(수치표고모델) = 땅 높이를 5m 간격 격자로 저장한 이미지. 픽셀 값 = 해발고도(m).

    사용법:
        dem = DEM(C.DATA_ROOT_DEM)          # 폴더 안의 모든 DEM 타일을 하나로 이어 붙여 메모리에 올림
        z = dem.sample(xs, ys)               # 좌표 배열을 주면 각 위치의 높이 배열을 돌려줌
    [class 문법] JS의 class 와 같습니다. __init__ 은 constructor, self 는 this 입니다.
    """
    def __init__(self, root, bbox=None):
        files = []
        for e in (".img", ".tif", ".tiff", ".asc"):
            files += find_files(root, [""], e)
        if not files:
            raise FileNotFoundError(f"DEM 파일 없음: {root}")
        # BuildVRT : 여러 타일을 복사 없이 하나의 큰 이미지처럼 보이게 묶음 (/vsimem = 메모리 속 가상 파일)
        vrt = gdal.BuildVRT("/vsimem/dem.vrt", files, srcNodata=None)
        wkt = vrt.GetProjection()
        if wkt:
            s = osr.SpatialReference(wkt=wkt)
            s.SetAxisMappingStrategy(osr.OAMS_TRADITIONAL_GIS_ORDER)
        else:
            gt = vrt.GetGeoTransform()
            s = srs_from(guess_crs(gt[0], gt[0] + gt[1] * vrt.RasterXSize))
        self.ct = transformer(TARGET, s)       # 분석 좌표 → DEM 좌표 (DEM 좌표계가 다를 때 대비)
        # GeoTransform: 픽셀 ↔ 좌표 변환 정보. gt[0]=왼쪽 x, gt[1]=픽셀 가로크기, gt[3]=위쪽 y, gt[5]=픽셀 세로크기(음수)
        gt = vrt.GetGeoTransform()
        bbox = bbox or C.AREA_BBOX
        x0, y0, nx, ny = 0, 0, vrt.RasterXSize, vrt.RasterYSize
        if bbox:                               # 범위가 있으면 그 부분만 잘라 읽기 (메모리 절약)
            bx, by = transform_xy(self.ct, [bbox[0], bbox[2]], [bbox[1], bbox[3]])
            c0 = int(max(0, math.floor((min(bx) - gt[0]) / gt[1]) - 2)); c1 = int(min(nx, math.ceil((max(bx) - gt[0]) / gt[1]) + 2))
            r0 = int(max(0, math.floor((max(by) - gt[3]) / gt[5]) - 2)); r1 = int(min(ny, math.ceil((min(by) - gt[3]) / gt[5]) + 2))
            x0, y0, nx, ny = c0, r0, max(1, c1 - c0), max(1, r1 - r0)
        band = vrt.GetRasterBand(1)
        self.arr = band.ReadAsArray(x0, y0, nx, ny).astype("float32")   # 2차원 배열 [행][열] = 높이
        nod = band.GetNoDataValue()                  # "값 없음"을 뜻하는 숫자 (예: -9999)
        if nod is not None:
            self.arr[self.arr == nod] = np.nan       # 값 없음 → NaN (JS의 NaN 과 같음)
        self.arr[(self.arr < -100) | (self.arr > 3000)] = np.nan   # 말도 안 되는 높이도 NaN
        self.gt = (gt[0] + x0 * gt[1], gt[1], 0, gt[3] + y0 * gt[5], 0, gt[5])
        log(f"  DEM: 파일 {len(files)}개, 격자 {self.arr.shape}, 해상도 {gt[1]:.2f}m")
        vrt = None
        gdal.Unlink("/vsimem/dem.vrt")

    def sample(self, xs, ys):
        """좌표 배열 → 높이 배열. 픽셀 사이 위치는 주변 4픽셀을 거리 비율로 섞어서 부드럽게 계산(쌍선형 보간)"""
        xs, ys = transform_xy(self.ct, xs, ys)
        # 좌표 → 픽셀 번호(소수점 포함). -0.5 는 픽셀 "중심" 기준으로 맞추기 위함
        c = (xs - self.gt[0]) / self.gt[1] - 0.5
        r = (ys - self.gt[3]) / self.gt[5] - 0.5
        c0, r0 = np.floor(c).astype(int), np.floor(r).astype(int)   # 왼쪽 위 픽셀 번호
        dc, dr = c - c0, r - r0                                     # 그 픽셀에서 얼마나 떨어졌나 (0~1)
        H, W = self.arr.shape

        def v(rr, cc):
            """픽셀 값 읽기 (배열 밖이면 NaN)"""
            ok = (rr >= 0) & (rr < H) & (cc >= 0) & (cc < W)       # & 는 배열 원소별 AND
            out = np.full(rr.shape, np.nan, "float32")
            out[ok] = self.arr[rr[ok], cc[ok]]
            return out

        # 주변 4픽셀 × 가중치의 합 = 보간 높이
        z = (v(r0, c0) * (1 - dc) * (1 - dr) + v(r0, c0 + 1) * dc * (1 - dr) +
             v(r0 + 1, c0) * (1 - dc) * dr + v(r0 + 1, c0 + 1) * dc * dr)
        # 가장자리라서 계산이 안 된 곳(NaN)은 가장 가까운 픽셀 값으로 채움
        near = self.arr[np.clip(np.rint(r).astype(int), 0, H - 1), np.clip(np.rint(c).astype(int), 0, W - 1)]
        return np.where(np.isnan(z), near, z)   # np.where(조건, 참일때, 거짓일때) : 원소별 삼항연산자

    def covers(self, xs, ys):
        """[v6.1] 좌표가 DEM 범위 안이고 값이 있는지 (True/False 배열). sample 은 범위 밖을 가장자리 값으로 채우므로,
        DEM 1m 처럼 일부만 덮는 자료를 비교할 때 이것으로 범위 안만 고름"""
        xs, ys = transform_xy(self.ct, xs, ys)
        c = np.floor((xs - self.gt[0]) / self.gt[1]).astype(int)
        r = np.floor((ys - self.gt[3]) / self.gt[5]).astype(int)
        H, W = self.arr.shape
        ok = (r >= 0) & (r < H) & (c >= 0) & (c < W)
        out = np.zeros(len(ok), bool)
        out[ok] = np.isfinite(self.arr[r[ok], c[ok]])
        return out


# ───────────────────────── CSV / 결과 저장 ─────────────────────────
def read_csv(path):
    """CSV → [{"열이름": 값, ...}, ...] 형태의 리스트. 파일이 없으면 빈 리스트.
    encoding="utf-8-sig" : 엑셀에서 저장한 CSV 맨 앞의 보이지 않는 표시(BOM)를 자동 제거"""
    if not os.path.exists(path):
        return []
    with open(path, encoding="utf-8-sig") as f:      # with: 블록이 끝나면 파일을 자동으로 닫음
        return list(csv.DictReader(f))


def _ci_row_class(header):
    """[v6] 열 이름을 대소문자·앞뒤 공백 무시로 찾는 행(dict). 정확히 같은 이름이 있으면 그대로 (v5 와 같음)
    예) 파일 열이 "x_coord" 여도 r.get("X_COORD") 로 읽힘. JS로 치면 Proxy 로 키를 대문자로 바꿔 찾는 것"""
    up = {}
    for h in header or []:
        if h is not None:
            up.setdefault(str(h).strip().upper(), h)

    class Row(dict):
        def __missing__(self, k):
            a = up.get(str(k).strip().upper())
            if a is None or a == k:
                raise KeyError(k)
            return dict.__getitem__(self, a)

        def get(self, k, d=None):
            try:
                return self[k]
            except KeyError:
                return d

        def __contains__(self, k):
            return dict.__contains__(self, k) or str(k).strip().upper() in up
    return Row


def read_any(path, sep=None):
    """[v5] 안심구역에서 받는 CSV 를 읽기: 인코딩(utf-8-sig → cp949 → euc-kr)과 구분자(쉼표·파이프 | ·탭)를 자동으로 맞춤.
    sep 를 주면 그 구분자를 씀 (config 에서 직접 지정). 반환: (행 목록 [{열: 값}], 인코딩, 구분자)
    SKT 파일처럼 "|" 로 나뉜 파일도 읽힙니다. JS로 치면 Papa.parse(text, {delimiter: ""}) 의 자동 감지와 비슷"""
    for enc in ("utf-8-sig", "cp949", "euc-kr"):
        try:
            with open(path, encoding=enc, newline="") as f:
                head = f.readline()
                f.seek(0)
                d = sep or max([",", "|", "\t"], key=head.count)     # 첫 줄에 가장 많이 나오는 구분자
                rd = csv.DictReader(f, delimiter=d)
                Row = _ci_row_class(rd.fieldnames)                   # [v6] 열 이름 대소문자 무시
                return [Row(r) for r in rd], enc, d
        except UnicodeDecodeError:
            continue
    raise RuntimeError(f"인코딩을 알 수 없음: {path}")


def safe_head(head, n=20):
    """[v6.2] 칸 이름 목록을 화면·반출본에 쓸 때: 첫 줄이 값으로 보이면(머리줄 없는 CSV) 모두 모양만.
    (목록 글자, 머리줄 없음으로 보이는지)"""
    from lib.runlog import looks_like_value
    head = list(head)
    if any(looks_like_value(h) for h in head):
        return f"{len(head)}칸 {[value_shape(h) for h in head[:n]]} (첫 줄이 칸 이름이 아니라 값으로 보임)", True
    return str(head[:n]), False


def value_shape(v):
    """[v6.1] 값을 보이지 않고 "글자 모양"만: 한글 → 가, 영문 → A, 숫자 → 9 (예: "Y" → "A", "BDU001" → "AAA999", "단독주택" → "가가가가").
    화면·runlog 에 값을 적지 않으면서 값 형식(코드인지, 한글 이름인지, Y·N 인지)을 알게 하려고 씀"""
    out = []
    for ch in str(v):
        if "가" <= ch <= "힣":
            out.append("가")
        elif ch.isascii() and ch.isalpha():
            out.append("A")
        elif ch.isdigit():
            out.append("9")
        else:
            out.append(ch)
    return "".join(out)


def csv_points(path, lon="lon", lat="lat"):
    """CSV 의 경위도(lon, lat) 열 → 분석 좌표계 x, y 배열. 좌표가 빈 행은 건너뜀.
    반환: (행 목록, x 배열, y 배열)"""
    rows = [r for r in read_csv(path) if (r.get(lon) or "").strip() and (r.get(lat) or "").strip()]
    if not rows:
        return [], np.array([]), np.array([])
    xs, ys = transform_xy(transformer("EPSG:4326"), [float(r[lon]) for r in rows], [float(r[lat]) for r in rows])
    return rows, xs, ys


def write_csv(path, header, rows):
    """header(열 이름 리스트) + rows(행 리스트의 리스트) → CSV 파일. 엑셀에서 한글이 안 깨지게 utf-8-sig"""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(header)
        for r in rows:
            w.writerow(r)


def write_points_gpkg(path, layer, xs, ys, cols):
    """점 레이어를 GPKG(QGIS에서 바로 열리는 지도 파일)로 저장. cols = {"열이름": 값배열}. work 폴더 확인용"""
    drv = ogr.GetDriverByName("GPKG")
    if os.path.exists(path):
        drv.DeleteDataSource(path)                 # 기존 파일이 있으면 지우고 새로
    ds = drv.CreateDataSource(path)
    lyr = ds.CreateLayer(layer, TARGET, ogr.wkbPoint)
    for k in cols:
        lyr.CreateField(ogr.FieldDefn(k, ogr.OFTReal))   # 숫자(실수) 열 만들기
    lyr.StartTransaction()                         # 한꺼번에 저장 (빠름)
    for i in range(len(xs)):
        f = ogr.Feature(lyr.GetLayerDefn())
        for k, v in cols.items():
            val = float(v[i])
            if np.isfinite(val):                   # NaN·무한대는 빈 칸으로 둠
                f.SetField(k, val)
        f.SetGeometry(ogr.CreateGeometryFromWkt(f"POINT ({xs[i]} {ys[i]})"))
        lyr.CreateFeature(f)
    lyr.CommitTransaction()
    ds = None


def write_grid_gpkg(path, layer, cells, size, cols):
    """격자 집계 결과 → 사각형 폴리곤 GPKG. cells = [(격자x번호, 격자y번호), ...]
    QGIS에서 열어 색을 칠하면 바로 결과 지도가 됩니다 (반출용)"""
    drv = ogr.GetDriverByName("GPKG")
    if os.path.exists(path):
        drv.DeleteDataSource(path)
    ds = drv.CreateDataSource(path)
    lyr = ds.CreateLayer(layer, TARGET, ogr.wkbPolygon)
    for k in cols:
        lyr.CreateField(ogr.FieldDefn(k, ogr.OFTReal))
    lyr.StartTransaction()
    for i, (gx, gy) in enumerate(cells):           # enumerate: (순번, 값) 쌍으로 반복 (JS의 arr.forEach((v,i)=>...))
        x0, y0 = gx * size, gy * size              # 격자 번호 → 왼쪽 아래 좌표
        f = ogr.Feature(lyr.GetLayerDefn())
        for k, v in cols.items():
            val = float(v[i])
            if np.isfinite(val):
                f.SetField(k, val)
        f.SetGeometry(ogr.CreateGeometryFromWkt(
            f"POLYGON (({x0} {y0},{x0+size} {y0},{x0+size} {y0+size},{x0} {y0+size},{x0} {y0}))"))
        lyr.CreateFeature(f)
    lyr.CommitTransaction()
    ds = None
