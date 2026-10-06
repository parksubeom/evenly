# -*- coding: utf-8 -*-
"""
tools/make_fake_shared.py ─ 가짜 상호제공데이터 (KCB 소득·SKT 유동인구·교통사고) ※ 시험용, 안심구역 반입 안 함

[왜] 07·10·11 을 시험하려면 데이터정의서와 같은 열 이름의 파일이 필요. 값은 무작위(씨앗 고정)라 결과에 뜻은 없음.
[실행]  python3 tools/make_fake_shared.py <만들 폴더> [--lower]      (--lower: 머리 줄(열 이름)을 모두 소문자로 — 대소문자 시험)
[만드는 것]
  TB_KCB_INCOME_STAT_DATASET.csv : BS_YR_QT, RES_COM_CD, EMD_CD, SEX_CD, AGE_CD, C1_CNT~C22_CNT (행정동 = external/dong_boundary 의 ADM_CD 앞 8자리)
  seoul_flow_age.csv             : STD_YM|X_COORD|Y_COORD|MAN_FLOW_POP_CNT_10G … 60GU, WMAN_… (UTM-K 5179, 서울 범위 500m 셀, | 구분)
  TB_KRD_ACCIDENT_DATA.csv       : sido_nm, sigungu_nm, bjd_nm, …, accident_type_lv1, victim_age … (구 = 실제 구 이름 + "가상구",
                                   법정동 = 시험 필지 이름 "가상N동"·"가상1동"·"가상2동")
"""
import csv, json, os, random, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.abspath(sys.argv[1] if len(sys.argv) > 1 and not sys.argv[1].startswith("-") else "defdata")
LOWER = "--lower" in sys.argv
rnd = random.Random(11)
os.makedirs(OUT, exist_ok=True)
H = (lambda cols: [c.lower() for c in cols]) if LOWER else (lambda cols: cols)

gj = json.load(open(os.path.join(ROOT, "analysis", "hbi", "external", "dong_boundary.geojson"), encoding="utf-8"))
dongs = [(str(f["properties"]["ADM_CD"])[:8], f["properties"]["sggnm"]) for f in gj["features"]]
gus = sorted({g for _, g in dongs})

# KCB: 분기 2개 × 거주/직장 × 성 2 × 연령 4
cols = ["BS_YR_QT", "RES_COM_CD", "EMD_CD", "SEX_CD", "AGE_CD"] + [f"C{i}_CNT" for i in range(1, 23)]
with open(os.path.join(OUT, "TB_KCB_INCOME_STAT_DATASET.csv"), "w", encoding="utf-8-sig", newline="") as f:
    w = csv.writer(f); w.writerow(H(cols))
    for q in ("20230930", "20231231"):
        for code, _ in dongs:
            for res in ("1", "2"):
                for sex in ("1", "2"):
                    for age in ("40", "50", "60", "70"):
                        w.writerow([q, res, code, sex, age] + [rnd.randint(0, 40) for _ in range(22)])

# SKT: 서울 범위(5179) 500m 셀, 두 달
cols = ["STD_YM", "X_COORD", "Y_COORD"] + [f"MAN_FLOW_POP_CNT_{a}" for a in ("10G", "20G", "30G", "40G", "50G", "60GU")] + \
       [f"WMAN_FLOW_POP_CNT_{a}" for a in ("10G", "20G", "30G", "40G", "50G", "60GU")]
with open(os.path.join(OUT, "seoul_flow_age.csv"), "w", encoding="utf-8-sig", newline="") as f:
    w = csv.writer(f, delimiter="|"); w.writerow(H(cols))
    for ym in ("202308", "202309"):
        for x in range(940000, 972001, 500):
            for y in range(1936000, 1966001, 500):
                w.writerow([ym, x + 25, y + 25] + [round(rnd.uniform(0, 20), 2) for _ in range(12)])

# 교통사고: 법정동 이름만 (좌표 없음)
cols = ["sido_nm", "sigungu_nm", "bjd_nm", "year", "month", "day", "hour", "day_night", "accident_type_lv1", "accident_type_lv2",
        "driver_age", "victim_age", "victim_injury", "fatal", "serious", "minor", "reported_injury"]
names = [(g, f"가상{i}동") for g in gus for i in range(11)] + [("가상구", "가상1동"), ("가상구", "가상2동")]   # make_v6_cases 의 필지 이름과 맞춤
with open(os.path.join(OUT, "TB_KRD_ACCIDENT_DATA.csv"), "w", encoding="utf-8-sig", newline="") as f:
    w = csv.writer(f); w.writerow(H(cols))
    for k in range(3000):
        g, d = rnd.choice(names)
        w.writerow(["서울특별시", g, d, 2023, rnd.randint(1, 12), rnd.randint(1, 28), rnd.randint(0, 23), rnd.choice(["주", "야"]),
                    rnd.choice(["차대사람", "차대차", "차량단독"]), "기타", "40대", rnd.choice(["65세이상", "20대", "40대"]),
                    "경상", 0, 0, 1, 0])
print("완료:", OUT, "(머리 줄 소문자)" if LOWER else "")
