# -*- coding: utf-8 -*-
"""
lib/codebook.py ─ [v6.1] 수치지형도 코드 ↔ 코드명 (tools/make_codebook.py 가 정의서에서 만든 파일, 손으로 고치지 말 것)
  원본: 한국국토정보공사_데이터정의서.xlsx 의 "■ 수치지형도 작성 작업 및 성과에 관한 규정 [별표 2] <개정 2026. 5. 28.>"
  쓰는 곳: lib/battr.py (건물 용도·종류), lib/qnetwork.py (계단 구조, 걸을 수 없는 도로), lib/mapping.py (한글 필드명 별칭)
"""

LAYERS = {
    'N3L_A0020000': {"name": '도로중심선', "fields": {
        'UFID': {"name": '유일식별자', "type": '문자열', "codes": {}},
        'MOLIT_UFID': {"name": '국토부UFID', "type": '문자열', "codes": {}},
        'REFNF_ID': {"name": '참조고유식별자아이디', "type": '문자열', "codes": {}},
        'ROAD_NO': {"name": '도로번호', "type": '문자열', "codes": {}},
        'ROAD_NM': {"name": '명칭', "type": '문자열', "codes": {}},
        'ROAD_SE': {"name": '도로구분', "type": '구분코드', "codes": {'RDC001': '고속국도', 'RDC002': '일반국도', 'RDC003': '지방도', 'RDC004': '특별시도', 'RDC005': '광역시도', 'RDC006': '시도', 'RDC007': '군도', 'RDC008': '구도', 'RDC010': '면리간도로', 'RDC011': '부지안도로', 'RDC014': '소로', 'RDC015': '주요도로'}},
        'USGSTT_SE': {"name": '도로사용상태', "type": '구분코드', "codes": {'RUS001': '건설예정', 'RUS002': '공사중', 'RUS003': '운영중', 'RUS004': '폐쇄'}},
        'STPT': {"name": '시점', "type": '문자열', "codes": {}},
        'EDPT': {"name": '종점', "type": '문자열', "codes": {}},
        'PMTR_SE': {"name": '포장재질', "type": '구분코드', "codes": {'PVM001': '아스팔트', 'PVM003': '콘크리트', 'PVM004': '블록', 'PVM005': '비포장', 'PVM006': '우레탄', 'PVM007': '고무'}},
        'EDENNC_AT': {"name": '분리대유무', "type": '구분코드', "codes": {'1': '유', '0': '무'}},
        'CARTRK_CO': {"name": '차로수', "type": '숫자', "codes": {}},
        'ROAD_BT': {"name": '도로폭', "type": '숫자', "codes": {}},
        'OSPS_SE': {"name": '일방통행', "type": '구분코드', "codes": {'OWI001': '일방통행', 'OWI002': '양방통행'}},
        'MTRWY_SE': {"name": '자동차전용', "type": '구분코드', "codes": {'MWI001': '일반', 'MWI002': '자동차전용'}},
        'REST': {"name": '기타', "type": '문자열', "codes": {}},
        'PHY_LV': {"name": '위상수준', "type": '숫자', "codes": {}},
        'ROAD_TP': {"name": '차도유형', "type": '구분코드', "codes": {'RFI101': '일반차도', 'RFI102': '고가차도', 'RFI103': '지하차도', 'RFI104': '인터체인지', 'RFI201': '교량', 'RFI202': '터널'}},
        'NF_ID': {"name": '고유식별자아이디', "type": '문자열', "codes": {}},
        'OBCHG_DT': {"name": '객체변동일시', "type": '날짜', "codes": {}},
        'MESRMTH_SE': {"name": '측량방법', "type": '구분코드', "codes": {'P': '사진측량', 'F': '현황측량', 'C': '지적측량'}},
        'CSCHG_SE': {"name": '객체변동구분', "type": '구분코드', "codes": {'CSC001': '객체생성', 'CSC002': '공간도형과 속성을 함께 수정', 'CSC003': '공간도형만 수정', 'CSC004': '공간도형 분할', 'CSC005': '공간도형 합병', 'CSC006': '위치 이동', 'CSC007': '속성만 수정', 'CSC008': '객체 삭제'}},
        'MNENT_NM': {"name": '제작업체명', "type": '문자열', "codes": {}},
        'SUSI_ID': {"name": '국토변화정보아이디', "type": '문자열', "codes": {}},
        'SCALE_SE': {"name": '축척구분', "type": '구분코드', "codes": {'1K': '1K', '5K': '5K'}},
    }},
    'N3A_A0033320': {"name": '인도(보도)', "fields": {
        'UFID': {"name": '유일식별자', "type": '문자열', "codes": {}},
        'WIDT': {"name": '폭', "type": '숫자', "codes": {}},
        'QUAL': {"name": '재질', "type": '구분코드', "codes": {'PVM001': '아스팔트', 'PVM003': '콘크리트', 'PVM004': '블록', 'PVM005': '비포장', 'PVM006': '우레탄', 'PVM007': '고무', 'PVM008': '아스팔트/블록'}},
        'NF_ID': {"name": '고유식별자아이디', "type": '문자열', "codes": {}},
        'OBCHG_DT': {"name": '객체변동일시', "type": '날짜', "codes": {}},
        'MESRMTH_SE': {"name": '측량방법', "type": '구분코드', "codes": {'P': '사진측량', 'F': '현황측량', 'C': '지적측량'}},
        'CSCHG_SE': {"name": '객체변동구분', "type": '구분코드', "codes": {'CSC001': '객체생성', 'CSC002': '공간도형과 속성을 함께 수정', 'CSC003': '공간도형만 수정', 'CSC004': '공간도형 분할', 'CSC005': '공간도형 합병', 'CSC006': '위치 이동', 'CSC007': '속성만 수정', 'CSC008': '객체 삭제'}},
        'MNENT_NM': {"name": '제작업체명', "type": '문자열', "codes": {}},
        'SCALE_SE': {"name": '축척구분', "type": '구분코드', "codes": {'1K': '1K', '5K': '5K'}},
    }},
    'N3L_A0033330': {"name": '자전거도로', "fields": {
        'UFID': {"name": '유일식별자', "type": '문자열', "codes": {}},
        'WIDT': {"name": '폭', "type": '숫자', "codes": {}},
        'PMTR_SE': {"name": '재질', "type": '구분코드', "codes": {'PVM001': '아스팔트', 'PVM003': '콘크리트', 'PVM004': '블록', 'PVM005': '비포장', 'PVM006': '우레탄', 'PVM007': '고무', 'PVM008': '아스팔트/블록'}},
        'BCYKND_SE': {"name": '구분', "type": '구분코드', "codes": {'BIW001': '자전거전용도로', 'BIW002': '자전거보행자겸용도로', 'BIW003': '자전거 전용차로', 'BIW004': '자전거우선도로'}},
        'NF_ID': {"name": '고유식별자아이디', "type": '문자열', "codes": {}},
        'OBCHG_DT': {"name": '객체변동일시', "type": '날짜', "codes": {}},
        'MESRMTH_SE': {"name": '측량방법', "type": '구분코드', "codes": {'P': '사진측량', 'F': '현황측량', 'C': '지적측량'}},
        'CSCHG_SE': {"name": '객체변동구분', "type": '구분코드', "codes": {'CSC001': '객체생성', 'CSC002': '공간도형과 속성을 함께 수정', 'CSC003': '공간도형만 수정', 'CSC004': '공간도형 분할', 'CSC005': '공간도형 합병', 'CSC006': '위치 이동', 'CSC007': '속성만 수정', 'CSC008': '객체 삭제'}},
        'MNENT_NM': {"name": '제작업체명', "type": '문자열', "codes": {}},
        'SCALE_SE': {"name": '축척구분', "type": '구분코드', "codes": {'1K': '1K', '5K': '5K'}},
    }},
    'N3P_A0131122': {"name": '정거장', "fields": {
        'UFID': {"name": '유일식별자', "type": '문자열', "codes": {}},
        'PTWFC_NM': {"name": '명칭', "type": '문자열', "codes": {}},
        'PTWFCKD_SE': {"name": '점형철도시설종류구분', "type": '구분코드', "codes": {'RAF001': '철도정거장', 'RAF002': '지하철역', 'RAF003': '철도/지하철 공용', 'RAF999': '기타'}},
        'MESRMTH_SE': {"name": '측량방법', "type": '구분코드', "codes": {'P': '사진측량', 'F': '현황측량', 'C': '지적측량'}},
        'SCALE_SE': {"name": '축척구분', "type": '구분코드', "codes": {'1K': '1K', '5K': '5K'}},
    }},
    'N3A_B0010000': {"name": '건물', "fields": {
        'UFID': {"name": '유일식별자', "type": '문자열', "codes": {}},
        'BULD_NM': {"name": '명칭', "type": '문자열', "codes": {}},
        'BULD_SE': {"name": '종류', "type": '구분코드', "codes": {'BDC001': '일반주택', 'BDC002': '연립주택', 'BDC003': '아파트', 'BDC004': '주택외건물', 'BDC005': '무벽건물', 'BDC006': '온실', 'BDC007': '공사중건물', 'BDC008': '가건물'}},
        'BPRP_SE': {"name": '용도', "type": '구분코드', "codes": {'BDU001': '주거용단독주택', 'BDU002': '주거용공동주택', 'BDU003': '제1종근린생활시설', 'BDU004': '제2종근린생활시설', 'BDU005': '문화및집회시설', 'BDU006': '종교시설', 'BDU007': '판매시설', 'BDU008': '운수시설', 'BDU009': '의료시설', 'BDU010': '교육연구시설', 'BDU011': '노유자(노인및어린이)시설', 'BDU012': '수련시설', 'BDU013': '운동시설', 'BDU014': '업무시설', 'BDU015': '숙박시설', 'BDU016': '위락시설', 'BDU017': '공장', 'BDU018': '창고시설', 'BDU019': '위험물저장및처리시설', 'BDU020': '자동차관련시설', 'BDU021': '동물및식물관련시설', 'BDU022': '자원순환관련시설', 'BDU023': '교정및군사시설', 'BDU024': '방송통신시설', 'BDU025': '발전시설', 'BDU026': '묘지관련시설', 'BDU027': '관광휴게시설', 'BDU028': '장례시설', 'BDU999': '기타시설', 'BDU029': '야영장시설'}},
        'BATC_NM': {"name": '주기', "type": '문자열', "codes": {}},
        'BFLR_CO': {"name": '층수', "type": '숫자', "codes": {}},
        'MOLIT_UFID': {"name": '국토부UFID', "type": '문자열', "codes": {}},
        'BLDMN_NO': {"name": '건물번호본번', "type": '숫자', "codes": {}},
        'BLDSL_NO': {"name": '건물번호부번', "type": '숫자', "codes": {}},
        'PNU_NO': {"name": 'PNU번호', "type": '문자열', "codes": {}},
        'USECON_DE': {"name": '사용승인일', "type": '문자열', "codes": {}},
        'RNCODE_DC': {"name": '도로명코드', "type": '문자열', "codes": {}},
        'REFNF_ID': {"name": '참조NFID', "type": '문자열', "codes": {}},
        'BLDH_MN': {"name": '최저높이', "type": '숫자', "codes": {}},
        'BLDH_MX': {"name": '최고높이', "type": '숫자', "codes": {}},
        'BLDH_BV': {"name": '기본높이', "type": '숫자', "codes": {}},
        'BLDFH_MX': {"name": '시설물높이', "type": '숫자', "codes": {}},
        'MNBLDG_SE': {"name": '주건물구분', "type": '구분코드', "codes": {'MBS001': '주건물', 'MBS002': '부속건물'}},
        'BD_MGT_SN': {"name": '도로명주소건물관리번호', "type": '문자열', "codes": {}},
        'BLDRGST_PK': {"name": '건축물대장일련번호', "type": '문자열', "codes": {}},
        'SIG_CD': {"name": '시군구코드', "type": '문자열', "codes": {}},
        'ROAD_NM': {"name": '도로명', "type": '문자열', "codes": {}},
        'BDGSYMB_SE': {"name": '건물기호구분', "type": '구분코드', "codes": {'BSB001': '특별시청', 'BSB002': '광역시청', 'BSB003': '도청', 'BSB004': '시청', 'BSB005': '군청', 'BSB006': '구청', 'BSB007': '읍사무소', 'BSB008': '주민센터', 'BSB009': '면사무소', 'BSB010': '(치안행정)미분류', 'BSB011': '법원', 'BSB012': '경찰청', 'BSB013': '경찰서', 'BSB014': '파출소,지서', 'BSB015': '소방서', 'BSB016': '보건소', 'BSB017': '세무서', 'BSB018': '세관', 'BSB019': '우체국', 'BSB020': '기상대, 측후소', 'BSB021': '전화국', 'BSB022': '병무청', 'BSB023': '기타관공서', 'BSB024': '농업기술센터', 'BSB025': '지방산림청', 'BSB026': '한국도로공사', 'BSB027': '한국토지주택공사', 'BSB028': '한국농어촌공사', 'BSB029': '공 장', 'BSB030': '시장', 'BSB031': '백화점', 'BSB032': '관광음식점', 'BSB033': '양배수장', 'BSB034': '축사', 'BSB035': '종축장', 'BSB036': '도축장', 'BSB037': '정미소', 'BSB038': '하수종말처리장기호', 'BSB039': '공단폐수처리장기호', 'BSB040': '축산폐수처리장기호', 'BSB041': '농공단지오폐수기호', 'BSB042': '간이오수처리장기호', 'BSB043': '분뇨처리장기호', 'BSB044': '학교', 'BSB045': '유치원, 유아원', 'BSB046': '도서관', 'BSB047': '실내체육관', 'BSB048': '학원', 'BSB049': '기숙사', 'BSB050': '교회', 'BSB051': '성당', 'BSB052': '절', 'BSB053': '기타종교시설', 'BSB054': '박물관', 'BSB055': '미술관', 'BSB056': '공회당', 'BSB057': 'TV방송국', 'BSB058': '라디오 방송국', 'BSB059': '신문사', 'BSB060': '잡지사', 'BSB061': 'CATV방송국', 'BSB062': '호텔', 'BSB063': '여관', 'BSB064': '콘도미니엄', 'BSB065': '목욕탕', 'BSB066': '고속버스터미널', 'BSB067': '시외버스터미널', 'BSB068': '창고', 'BSB069': '공항', 'BSB070': '자동차정비수리소', 'BSB071': '세차장', 'BSB072': '은행', 'BSB073': '협동조합', 'BSB074': '기타금융기관', 'BSB075': '보험회사', 'BSB076': '일반병원', 'BSB077': '결핵병원', 'BSB078': '나병원', 'BSB079': '정신병원', 'BSB080': '약국', 'BSB081': '아동상담소', 'BSB082': '자립지원시설', 'BSB083': '탁아시설', 'BSB084': '영아시설', 'BSB085': '아동일시보호시설', 'BSB086': '아동직업보도시설', 'BSB087': '양로시설', 'BSB088': '장애인재활시설', 'BSB089': '모자보호시설', 'BSB090': '미혼모시설', 'BSB091': '노인복지회관', 'BSB092': '부녀복지관', 'BSB093': '사회복지관', 'BSB999': '해당없음'}},
        'NF_ID': {"name": '고유식별자아이디', "type": '문자열', "codes": {}},
        'OBCHG_DT': {"name": '객체변동일시', "type": '날짜', "codes": {}},
        'MESRMTH_SE': {"name": '측량방법', "type": '구분코드', "codes": {'P': '사진측량', 'F': '현황측량', 'C': '지적측량'}},
        'CSCHG_SE': {"name": '객체변동구분', "type": '구분코드', "codes": {'CSC001': '객체생성', 'CSC002': '공간도형과 속성을 함께 수정', 'CSC003': '공간도형만 수정', 'CSC004': '공간도형 분할', 'CSC005': '공간도형 합병', 'CSC006': '위치 이동', 'CSC007': '속성만 수정', 'CSC008': '객체 삭제'}},
        'MNENT_NM': {"name": '제작업체명', "type": '문자열', "codes": {}},
        'SUSI_ID': {"name": '국토변화정보아이디', "type": '문자열', "codes": {}},
        'SCALE_SE': {"name": '축척구분', "type": '구분코드', "codes": {'1K': '1K', '5K': '5K'}},
    }},
    'N3A_C0390000': {"name": '계단', "fields": {
        'UFID': {"name": '유일식별자', "type": '문자열', "codes": {}},
        'ARSFC_NM': {"name": '명칭', "type": '문자열', "codes": {}},
        'ARSFCKD_SE': {"name": '구조', "type": '구분코드', "codes": {'PGS001': '계단', 'PGS002': '스텐드'}},
        'WIDT': {"name": '폭', "type": '숫자', "codes": {}},
        'MESRMTH_SE': {"name": '측량방법', "type": '구분코드', "codes": {'P': '사진측량', 'F': '현황측량', 'C': '지적측량'}},
        'SCALE_SE': {"name": '축척구분', "type": '구분코드', "codes": {'1K': '1K', '5K': '5K'}},
    }},
}

import re as _re


def _key(s):
    """비교용: 공백·괄호·가운뎃점을 빼고 대문자 (예: "노유자(노인및어린이)시설" → "노유자노인및어린이시설")"""
    return _re.sub(r"[\s()（）·.,/]", "", str(s or "")).upper()


def codes(layer, field):
    """{코드: 코드명}. 레이어·필드가 없으면 {}"""
    return LAYERS.get(layer, {}).get("fields", {}).get(field, {}).get("codes", {})


def to_code(layer, field, value):
    """값 → 정의서 코드. 코드(대소문자 무시)나 코드명(공백·괄호 무시) 모두 받음. 표에 없으면 원래 값을 대문자로"""
    v = str(value or "").strip()
    if not v:
        return ""
    cs = codes(layer, field)
    up = v.upper()
    if up in cs:
        return up
    k = _key(v)
    for c, n in cs.items():
        if _key(n) == k:
            return c
    return up


def field_names(layer):
    """{필드 코드: 한글 필드명} (예: BPRP_SE → 용도)"""
    return {f: v["name"] for f, v in LAYERS.get(layer, {}).get("fields", {}).items()}
