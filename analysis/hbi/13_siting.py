# -*- coding: utf-8 -*-
"""
13_siting.py ─ [v5] 이동편의시설(엘리베이터 등) 자리 주변 땅이 어떤 땅인지: 지목별 면적 비율

[실행]  python 13_siting.py      (run_all.py 가 끝난 뒤 한 줄 따로. config.py 의 DATA_ROOT_PARCEL 필요)
[준비]  external/interventions.csv 의 a_lon, a_lat(아래 끝), b_lon, b_lat(위 끝) 좌표 (09_intervention.py 와 같은 파일)
        좌표 4개가 다 있는 행만 계산합니다. 빈 행은 건너뛰고 화면에 적습니다.
[하는 일]
  1. 시설 a–b 선분 둘레 BUFFER_M(30m) 안의 국토정보필지를 찾음 (PARCEL_ENCODING 으로 읽기만 함)
  2. 필지마다 그 둘레와 겹치는 면적을 재서, 지목을 아래 JIMOK_CLASS 표로 7가지로 나눠 더함
       도로 / 공원 / 대 / 임야 / 학교 / 하천·구거 / 기타
  3. 분류별 면적 ÷ 전체 면적 = 비율 (합 = 1.0). 필지가 MIN_COUNT 개 미만이면 비율은 빈 칸
  ※ 필지의 지목(JIMOK)과 모양만 읽습니다. 소유·공시지가·필지번호(PNU)는 읽지도 저장하지도 않습니다
  JS로 치면: 선분 주위에 30m 폭 띠를 그리고, 띠와 겹치는 땅 조각을 종류별로 groupBy 해서 면적 합을 구하는 것
[결과] (output/ → 반출 대상. 기획서 23장)
  siting_summary.csv : facility, status, buffer_m, n_parcels, area_m2, share_도로, share_공원, share_대, share_임야,
                       share_학교, share_하천구거, share_기타
[결과 보는 법]
  - share_도로·share_공원 이 크면 공공 땅 위주 (설치 협의가 쉬운 편), share_대 가 크면 사유지 주거 땅이 많음
  - 화면의 "분류 안 된 지목" 에 ??? 같은 깨진 글자가 많으면 config.PARCEL_ENCODING 확인 (01_inspect.py 의 JIMOK 예시)
"""
import os, numpy as np
from osgeo import ogr
import config as C
from lib.qio import log, read_csv, write_csv, transform_xy, transformer, find_files, iter_layer

# ── 이 스크립트만의 설정 (config.py 는 바꾸지 않음) ─────────────
BUFFER_M = 30
# 지목 → 분류. 국토정보필지 JIMOK 은 "대장지목명"(LX 데이터정의서). 이름("도로")으로 오든 한 글자 부호("도")로 오든 맞도록 둘 다 적음.
#   부호는 지적 지목 부호 (도로=도, 공원=공, 대=대, 임야=임, 학교용지=학, 하천=천, 구거=구). 01_inspect.py 의 "JIMOK(지목) 예시" 로 실제 값 확인
JIMOK_CLASS = {
    "도로": ["도로", "도"],
    "공원": ["공원", "공"],
    "대": ["대"],
    "임야": ["임야", "임"],
    "학교": ["학교용지", "학"],
    "하천구거": ["하천", "천", "구거", "구"],
}
ORDER = ["도로", "공원", "대", "임야", "학교", "하천구거", "기타"]
LOOKUP = {v: k for k, vs in JIMOK_CLASS.items() for v in vs}

if not C.DATA_ROOT_PARCEL:
    raise SystemExit("config.DATA_ROOT_PARCEL 이 비어 있습니다 (국토정보필지 폴더) → 건너뜀")
os.makedirs(C.OUTPUT, exist_ok=True)


def fnum(x):
    x = (x or "").strip()
    return float(x) if x else None


tf = transformer("EPSG:4326")
fac = []
for r in read_csv(os.path.join(C.EXTERNAL, "interventions.csv")):
    c = [fnum(r.get(k)) for k in ("a_lon", "a_lat", "b_lon", "b_lat")]
    if any(v is None for v in c):
        log(f"  건너뜀: {r.get('name')} (a·b 좌표가 다 채워지지 않음)")
        continue
    (ax, bx), (ay, by) = transform_xy(tf, [c[0], c[2]], [c[1], c[3]])
    seg = ogr.Geometry(ogr.wkbLineString)
    seg.AddPoint_2D(float(ax), float(ay)); seg.AddPoint_2D(float(bx), float(by))
    fac.append((r["name"], (r.get("status") or "").strip(), seg.Buffer(BUFFER_M)))
if not fac:
    raise SystemExit("external/interventions.csv 에 a·b 좌표가 모두 있는 행이 없습니다 → 건너뜀")

env = [f[2].GetEnvelope() for f in fac]                           # (x0, x1, y0, y1)
bbox = [min(e[0] for e in env), min(e[2] for e in env), max(e[1] for e in env), max(e[3] for e in env)]
files = find_files(C.DATA_ROOT_PARCEL, [""], ".shp")
parcels = [(g.Clone(), str(a.get("JIMOK") or "").strip())
           for g, a in iter_layer(files=files, fields=["JIMOK"], bbox=bbox, encoding=C.PARCEL_ENCODING)]
log(f"시설 {len(fac)}곳 둘레 {BUFFER_M}m, 범위 안 필지 {len(parcels):,}개")

rows, unknown = [], {}
for name, status, buf in fac:
    x0, x1, y0, y1 = buf.GetEnvelope()
    area = dict.fromkeys(ORDER, 0.0)
    n = 0
    for g, jm in parcels:
        gx0, gx1, gy0, gy1 = g.GetEnvelope()
        if gx1 < x0 or gx0 > x1 or gy1 < y0 or gy0 > y1:
            continue
        a = g.Intersection(buf).GetArea() if g.Intersects(buf) else 0.0
        if a <= 0:
            continue
        n += 1
        cls = LOOKUP.get(jm, "기타")
        if cls == "기타":
            unknown[jm] = unknown.get(jm, 0) + 1
        area[cls] += a
    if n == 0:
        log(f"  건너뜀: {name} (둘레 {BUFFER_M}m 안에 필지 없음)")
        continue
    tot = sum(area.values())
    share = [round(area[k] / tot, 4) if n >= C.MIN_COUNT else "" for k in ORDER]
    rows.append([name, status, BUFFER_M, n, round(tot, 1)] + share)
    log(f"  {name}: 필지 {n}개, {tot:,.0f}㎡ → " + ", ".join(f"{k} {area[k] / tot:.0%}" for k in ORDER if area[k] > 0)
        + ("" if n >= C.MIN_COUNT else f"  (필지 {C.MIN_COUNT}개 미만이라 비율은 빈 칸)"))
if unknown:
    top = sorted(unknown.items(), key=lambda x: -x[1])[:10]
    log(f"  분류 안 된 지목(기타로 셈): {top}  ← 깨진 글자가 많으면 config.PARCEL_ENCODING 확인")

write_csv(os.path.join(C.OUTPUT, "siting_summary.csv"),
          ["facility", "status", "buffer_m", "n_parcels", "area_m2"] + [f"share_{k}" for k in ORDER], rows)
log(f"완료 → output/siting_summary.csv ({len(rows)}행, 필지 번호·소유 정보는 저장하지 않음)")
