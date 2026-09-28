# -*- coding: utf-8 -*-
"""
언덕 위 우리동네 - 분석 설정 파일
안심구역에서 실제 경로와 구조를 확인한 뒤 이 파일만 고치면 됩니다.
(01_inspect.py 실행 결과를 보고 수정하세요)
"""
import os
BASE = os.path.dirname(os.path.abspath(__file__))

# ── 1. 경로 ──────────────────────────────────────────
# 안심구역에서 제공받은 데이터가 있는 최상위 폴더 (하위 폴더까지 자동 탐색)
DATA_ROOT_MAP = r"D:\data\수치지형도"     # 수치지형도 shp 폴더
DATA_ROOT_DEM = r"D:\data\DEM5m"          # DEM 5m .img 폴더
DATA_ROOT_DEM1M = None                     # DEM 1m 비교용 (없으면 None)
DATA_ROOT_PARCEL = None                    # 국토정보필지 (2회차에 추가, 없으면 None)
EXTERNAL = os.path.join(BASE, "external")  # 반입한 공개데이터 CSV
WORK = os.path.join(BASE, "work")          # 중간 산출물 (반출 대상 아님)
OUTPUT = os.path.join(BASE, "output")      # 반출 신청 대상 (집계 결과만)

# ── 2. 좌표계 ─────────────────────────────────────────
TARGET_CRS = "EPSG:5186"      # GRS80 중부원점 (서울 수치지형도 기본)
DEFAULT_CRS = "EPSG:5186"     # .prj 파일이 없을 때 가정할 좌표계
SHP_ENCODINGS = ["cp949", "utf-8", "euc-kr"]

# 분석 범위 제한 (테스트용). None이면 데이터 전체. [xmin, ymin, xmax, ymax] (TARGET_CRS 기준)
AREA_BBOX = None

# ── 3. 수치지형도 레이어 코드 (데이터정의서 기준) ─────────────
LAYERS = {
    "sidewalk_cl": ["N3L_A0033328", "보도중심선"],   # 보행 네트워크 1순위
    "road_cl":     ["N3L_A0020000", "도로중심선"],   # 보행 네트워크 2순위
    "stairs":      ["N3A_C0390000", "계단"],
    "building":    ["N3A_B0010000", "건물"],
    "bus_stop":    ["N3P_A0140000", "정류장"],
    "bridge":      ["N3A_A0070000", "교량"],
    "tunnel":      ["N3A_A0110020", "터널"],
    "overpass":    ["N3A_A0063321", "육교"],
}

# 건물 용도/종류 코드
RESIDENTIAL_USE = ["BDU001", "BDU002"]            # 주거용 단독·공동주택
RESIDENTIAL_KIND = ["BDC001", "BDC002", "BDC003"] # 일반주택·연립·아파트 (용도 비어있을 때)
MEDICAL_USE = ["BDU009"]                           # 의료시설
ELDERLY_USE = ["BDU011"]                           # 노유자시설
STAIR_CODE = "PGS001"
COL = {  # 필드명 (다르면 수정)
    "bld_use": "BPRP_SE", "bld_kind": "BULD_SE", "bld_floor": "BFLR_CO",
    "stair_kind": "ARSFCKD_SE", "bus_kind": "PTRFCKD_SE",
}

# ── 4. 모델 파라미터 ──────────────────────────────────────
SEG_LEN = 30.0           # 링크 분할 길이 (m)
SNAP_TOL = 1.0           # 노드 병합 허용오차 (m)
STAIR_CONNECT_TOL = 15.0 # 계단 끝점-네트워크 연결 허용거리 (m)
ORIGIN_SNAP_MAX = 60.0   # 건물 중심점-노드 최대 연결거리 (m)
BRIDGE_TOL = 10.0        # 끊긴 선 끝점을 다른 선에 연결하는 허용거리 (m, 보도-도로 연결)
SLOPE_CLIP = 0.40        # 비정상 경사 절단 (±40%)

ELDER_SPEED = 0.8        # 고령자 평지 보행속도 (m/s)
STAIR_FACTOR = 1.2       # 계단 추가 가중
DOWNHILL_WEIGHT = 0.5    # 내리막 부담 = 같은 경사 오르막 부담의 50% (고령자는 내리막도 느려짐, 0이면 Tobler 원식)

WHEEL_SPEED = 1.0        # 수동휠체어 평지속도 (m/s)
WHEEL_LIMIT = 1 / 12     # 자력 통행 한계 경사
WHEEL_STEEP_PENALTY = 10 # 한계 초과 구간 시간 배수

HBI_BANDS = [1.3, 1.8]   # 평지수준 / 체감부담 / 고립위험 경계

# ── 5. 반출용 집계 ───────────────────────────────────────
GRID = 250               # 격자 크기 (m)
GRID_COARSE = 500        # 기여도 분석용 큰 격자
MIN_COUNT = 5            # 건물 수가 이보다 적은 격자는 반출 결과에서 제외 (비식별)
