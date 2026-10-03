# -*- coding: utf-8 -*-
"""
tools/prep_building_register.py ─ 서울시 건축물대장 표제부(공개) → analysis/hbi/external/building_register.csv

[왜]  안심구역의 수치지형도 건물(N3A_B0010000)에 용도·층수 칸이 없으면(1차 방문 실제 사례: UFID 하나뿐)
      v6 는 건물 → 필지 → 건축물대장으로 용도·층수를 붙인다 (config/mapping 의 building_attr_mode = register).
      이 스크립트는 그때 쓸 대장 파일을 밖에서 미리 만든다. 분석에 쓰지 않는 열(주소·면적 상세·인증 등)은 버린다.

[실행]  python3 tools/prep_building_register.py                 서울 전역
        python3 tools/prep_building_register.py --area          분석 범위(대상 5개 구 + 옆 3개 구)만
        python3 tools/prep_building_register.py --area --zip    위 + zip 압축본도

[입력]  data_public/raw/서울시 건축물대장 표제부.csv   (서울 열린데이터광장, CP949, 쉼표, 62열)
        data_public/raw/서울시 자치구별 도보 네트워크 공간정보.csv  (법정동 이름 → 코드 표로만 씀)

[출력 열]
  bldrgst_pk  ← 건축물대장일련번호 (원본에 '관리건축물대장PK' 열이 없어 이 열을 씀. 필지 쪽 BLDRGST_PK 와 같은 체계인지는
                안심구역 스키마로 확인. 다르면 v6 는 pnu 로 붙임)
  pnu         ← 19자리 = 시군구코드(5) + 법정동코드(5) + 대지구분(1) + 본번(4) + 부번(4)
                · 원본에 코드 열이 없어 (시군구명, 법정동명) → 10자리 법정동코드를 **행정안전부 법정동 주민등록 인구 파일**
                  (법정동코드·시도명·시군구명·읍면동명, 서울 452개 동, 리명 빈 행)에서 가져옴. 이 파일이 없을 때만 도보 네트워크 파일의
                  시군구명·읍면동명·읍면동코드로 대신함 (2026-10-03 대조: 공식 표에 있는 이름 450개는 코드가 모두 같았고, 도보 표의 나머지
                  113쌍은 구 경계를 넘는 링크 등이 만든 실제로 없는 이름 쌍. 강서구 오쇠동·오곡동은 도보 표에 없어 공식 표로만 채워짐)
                · 공식 인구 파일에는 주민이 없는 동(세종로·훈정동·양평동 등 15곳)이 빠져 있어, 그 동만 도보 표로 보충함. 단 그 구의
                  공식 시군구 코드(앞 5자리)와 같고 다른 공식 동이 쓰지 않는 코드일 때만 (가짜 쌍 제외)
                · 대지구분: 원본 '대지구분코드명' 대지 → 1, 산 → 2 (PNU 11번째 자리: 1 일반, 2 산).
                  대장 코드로는 대지 0, 산 1 이라 '대지 0→1, 산 1→2' 변환과 같음. '블록'(지번 대신 블록번호) 은 pnu 를 비움
                · 본번·부번: '주지번'·'부지번' (원본이 이미 네 자리, 앞을 0 으로 채움)
  main_use_cd ← 원본에 주용도코드 열이 없어 비움 (코드를 추정해 채우지 않음)
  main_use_nm ← 주용도코드명
  use_class   ← 아래 USE_CLASS 표 (주거 / 의료 / 노유자 / 기타)
  grnd_flr    ← 지상층수 (빈 값은 빈 칸)
  tot_area    ← 연면적 (㎡)
  main_atch   ← 주부속구분코드명 → 주 / 부속 (빈 값은 빈 칸)
  버리는 열: 대지위치·새주소·동명·특수지명·블록·로트·대지/건축면적·건폐율·용적률·구조·지붕·세대/가구/호수·높이·승강기·주차·
            허가/착공/사용승인일·에너지·인증·내진 등 (분석에 쓰지 않음)
"""
import argparse, csv, io, os, zipfile, collections

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW = os.path.join(ROOT, "data_public", "raw")
SRC = os.path.join(RAW, "서울시 건축물대장 표제부.csv")
WALK = os.path.join(RAW, "서울시 자치구별 도보 네트워크 공간정보.csv")
LEGAL_PREFIX = "행정안전부_지역별(법정동)"     # 공식 법정동 코드 표 (파일 이름 앞부분, 날짜는 달라도 됨)
OUT = os.path.join(ROOT, "analysis", "hbi", "external", "building_register.csv")

# 주용도 → 분류. 원본 파일의 '주용도코드명' 39종 (2026-10-03 확인) 을 아래처럼 나눔. 명칭으로 매칭 (코드 열이 없음).
# 코드로도 매칭할 수 있게 건축법 시행령 별표1 용도 대분류 코드 앞 두 자리를 함께 둠 (안심구역 대장에 코드가 있을 때 v6 가 사용)
USE_CLASS = {
    "주거":   {"names": ["단독주택", "공동주택", "다가구주택"], "codes": ["01", "02"]},
    "의료":   {"names": ["의료시설"], "codes": ["09"]},
    "노유자": {"names": ["노유자시설"], "codes": ["11"]},
}
# 그 밖(기타): 근린생활시설(1·2종 포함), 업무, 교육연구, 종교, 공장, 숙박, 자동차관련, 창고, 문화및집회, 판매, 위험물, 운동,
#   교정및군사, 운수, 관광휴게, 위락, 동물및식물, 교육연구및복지(옛 분류: 복지 여부를 나눌 수 없어 기타), 분뇨·쓰레기, 국방군사,
#   방송통신, 자원순환, 수련, 묘지, 판매및영업, 발전, 야영장, 공공용, 장례, 가설건축물, 교정시설, 빈 값

TARGET_GU = ["종로구", "중구", "관악구", "광진구", "강서구"]
NEIGHBOR_GU = ["성북구", "성동구", "동대문구"]
OUT_COLS = ["bldrgst_pk", "pnu", "main_use_cd", "main_use_nm", "use_class", "grnd_flr", "tot_area", "main_atch"]


def decode(path):
    b = open(path, "rb").read()
    for enc in ("utf-8-sig", "cp949"):
        try:
            return b.decode(enc), enc
        except UnicodeDecodeError:
            pass
    return b.decode("cp949", errors="replace"), "cp949(깨진 바이트는 대체 문자)"


def use_class(nm):
    for k, v in USE_CLASS.items():
        if nm in v["names"]:
            return k
    return "기타"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--area", action="store_true", help="대상 5개 구 + 옆 3개 구만")
    ap.add_argument("--zip", action="store_true", help="zip 압축본도 만듦")
    ap.add_argument("--out", default=OUT)
    a = ap.parse_args()

    import unicodedata
    legal = [os.path.join(RAW, f) for f in sorted(os.listdir(RAW)) if unicodedata.normalize("NFC", f).startswith(LEGAL_PREFIX)]
    code, src = {}, collections.Counter()
    if legal:
        lt, lenc = decode(legal[-1])
        for r in csv.DictReader(io.StringIO(lt, newline="")):
            if r["시도명"] == "서울특별시" and r["읍면동명"] and not r.get("리명"):
                code[(r["시군구명"], r["읍면동명"])] = r["법정동코드"]
        src["공식"] = len(code)
    sgg = {gu: c[:5] for (gu, _), c in code.items()}
    used = set(code.values())
    wt, wenc = decode(WALK)
    for r in csv.DictReader(io.StringIO(wt, newline="")):
        k, c = (r["시군구명"], r["읍면동명"]), r["읍면동코드"]
        if not c or k in code:
            continue
        # 공식 표가 있으면: 그 구의 공식 시군구 코드(앞 5자리)와 같고, 다른 공식 동이 쓰는 코드가 아닐 때만 (구 경계를 넘는 링크가 만든 가짜 쌍 제외)
        if legal and (sgg.get(k[0]) != c[:5] or c in used):
            continue
        code[k] = c; used.add(c); src["도보 보충"] += 1
    print(f"법정동 코드 표: {len(code)}개 동 = " + ", ".join(f"{k} {v}" for k, v in src.items())
          + (f" (공식: {unicodedata.normalize('NFC', os.path.basename(legal[-1]))}. 도보 보충 = 주민등록 인구가 없어 공식 인구 파일에 빠진 동)" if legal else " (공식 파일 없음)"))

    t, enc = decode(SRC)
    rd = csv.DictReader(io.StringIO(t, newline=""))
    print(f"입력: {os.path.basename(SRC)} ({os.path.getsize(SRC) / 1e6:.1f}MB, 인코딩 {enc}, 열 {len(rd.fieldnames)}개)")
    keep = set(TARGET_GU + NEIGHBOR_GU)
    st = collections.Counter(); cls = collections.Counter(); nopnu = collections.Counter()
    rows = []
    for r in rd:
        st["읽음"] += 1
        sido_gu = r["시군구코드명"].strip()
        if not (sido_gu.startswith("서울특별시") or sido_gu.startswith("서울시")):
            st["서울 아님 → 버림"] += 1; continue
        gu = sido_gu.replace("서울특별시", "").replace("서울시", "").strip()
        if a.area and gu not in keep:
            continue
        dong = r["법정동코드명"].strip()
        land = {"대지": "1", "산": "2"}.get(r["대지구분코드명"].strip())
        c10 = code.get((gu, dong))
        bon, bu = r["주지번"].strip(), r["부지번"].strip()
        if c10 and land and bon.isdigit() and bu.isdigit():
            pnu = c10 + land + bon.zfill(4) + bu.zfill(4)
        else:
            pnu = ""
            nopnu["법정동 코드 없음" if not c10 else ("블록 등 대지구분" if not land else "지번 숫자 아님")] += 1
        nm = r["주용도코드명"].strip()
        uc = use_class(nm); cls[uc] += 1
        atch = {"주건축물": "주", "부속건축물": "부속"}.get(r["주부속구분코드명"].strip(), "")
        rows.append([r["건축물대장일련번호"].strip(), pnu, "", nm, uc, r["지상층수"].strip(), r["연면적"].strip(), atch])
    os.makedirs(os.path.dirname(a.out), exist_ok=True)
    with open(a.out, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f); w.writerow(OUT_COLS); w.writerows(rows)
    print(f"읽은 행 {st['읽음']:,}, 서울 아님 {st['서울 아님 → 버림']}, 쓴 행 {len(rows):,} ({'분석 범위 8개 구' if a.area else '서울 전역'})")
    print(f"pnu 있음 {len(rows) - sum(nopnu.values()):,} ({(len(rows) - sum(nopnu.values())) / max(len(rows), 1):.2%}), pnu 빈 칸 {dict(nopnu)}")
    print(f"분류: {dict(cls)}")
    print(f"출력: {os.path.relpath(a.out, ROOT)} ({os.path.getsize(a.out) / 1e6:.1f}MB)")
    if a.zip:
        zp = os.path.splitext(a.out)[0] + ".zip"
        with zipfile.ZipFile(zp, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as z:
            z.write(a.out, os.path.basename(a.out))
        print(f"압축: {os.path.relpath(zp, ROOT)} ({os.path.getsize(zp) / 1e6:.1f}MB)")


if __name__ == "__main__":
    main()
