# -*- coding: utf-8 -*-
"""
tools/prep_photos.py ─ 15장 현장실측 사진 → 기획서용 사본 (바로 세우기 · 크기 줄이기 · 촬영 정보 지우기)

[실행]  python3 tools/prep_photos.py          (npm run real-day·build:fallback 이 먼저 부름. Pillow 가 있는 Python: deck/py.js 의 QGIS Python)
[넣는 곳] docs/photos/15_1 ~ 15_4 (.jpg·.jpeg·.png·.heic, 대소문자 무관)
        1 = 봉천동 선정지 계단, 2 = 봉천역 → 언덕 오르막, 3 = 도림천 산책로(평지), 4 = 낙성대역 → 언덕
        사람 얼굴·집 안·번지 표지가 보이는 사진은 넣지 않음 (관악 실측 기록지)
[하는 일] HEIC 는 맥의 sips 로 JPEG 로 바꾼 뒤, 휴대폰의 회전 정보(EXIF)대로 바로 세우고, 긴 변 1600px 로 줄여
        docs/photos/_deck/15_N.jpg 로 저장. EXIF(촬영 위치 GPS·기기·시각)는 남기지 않음. 원본은 고치지 않음
        build_v6.js 는 _deck 사본만 읽음 (없으면 그 칸은 '사진 자리'). docs/photos/ 는 git 에 넣지 않음
"""
import os, shutil, subprocess, sys, tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "docs", "photos")
OUT = os.path.join(SRC, "_deck")
EXT = (".jpg", ".jpeg", ".png", ".heic")
MAXPX = 1600


def main():
    try:
        from PIL import Image, ImageOps
    except ImportError:
        raise SystemExit("!! Pillow 가 없는 Python 입니다 → cd deck && node py.js ../tools/prep_photos.py (QGIS Python)")
    os.makedirs(OUT, exist_ok=True)
    files = {f.lower(): f for f in os.listdir(SRC)} if os.path.isdir(SRC) else {}
    done = []
    for n in range(1, 5):
        src = next((os.path.join(SRC, files[k]) for k in (f"15_{n}{e}" for e in EXT) if k in files), None)
        dst = os.path.join(OUT, f"15_{n}.jpg")
        if not src:
            if os.path.exists(dst):
                os.remove(dst)                        # 원본을 뺐으면 사본도 뺌 (그 칸은 '사진 자리')
            continue
        tmp = None
        if src.lower().endswith(".heic"):
            tmp = tempfile.mkdtemp()
            j = os.path.join(tmp, "x.jpg")
            r = subprocess.run(["sips", "-s", "format", "jpeg", src, "--out", j], capture_output=True, text=True)
            if r.returncode or not os.path.exists(j):
                print(f"!! {os.path.basename(src)}: HEIC 를 JPEG 로 바꾸지 못함 (sips) → 사진 앱에서 JPEG 로 내보내 15_{n}.jpg 로")
                continue
            src_open = j
        else:
            src_open = src
        im = ImageOps.exif_transpose(Image.open(src_open))
        im = im.convert("RGB")
        im.thumbnail((MAXPX, MAXPX))
        im.save(dst, "JPEG", quality=88)             # exif 인자를 주지 않으면 촬영 정보는 저장되지 않음
        if tmp:
            shutil.rmtree(tmp, ignore_errors=True)
        done.append(f"15_{n} {im.size[0]}×{im.size[1]}")
    print(f"[photos] 15장 사진 {len(done)}/4장 → docs/photos/_deck/ (EXIF 지움)" + (": " + ", ".join(done) if done else " — 없으면 '사진 자리'"))


if __name__ == "__main__":
    main()
