# -*- coding: utf-8 -*-
"""
tools/contact_sheet.py ─ 렌더한 장 그림(s-01.png …)을 한 장에 모은 그림 (청사진 판 보관용)

[실행]  node deck/py.js tools/contact_sheet.py <render 폴더> <출력 png> [--cols 5] [--width 640]
        (render 폴더 = tools/render_deck.py 의 --out. Pillow 가 있는 QGIS Python)
[결과] 장마다 폭 --width 로 줄여 --cols 칸씩 배치, 왼쪽 위에 장 번호
"""
import argparse, glob, os, re
from PIL import Image, ImageDraw, ImageFont


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("folder")
    ap.add_argument("out")
    ap.add_argument("--cols", type=int, default=5)
    ap.add_argument("--width", type=int, default=640)
    a = ap.parse_args()
    files = sorted(glob.glob(os.path.join(a.folder, "s-*.png")), key=lambda f: int(re.findall(r"s-(\d+)", f)[0]))
    if not files:
        raise SystemExit(f"!! 장 그림이 없습니다: {a.folder}/s-*.png (tools/render_deck.py 먼저)")
    ims = [Image.open(f).convert("RGB") for f in files]
    w = a.width
    h = round(ims[0].height * w / ims[0].width)
    gap, cols = 12, a.cols
    rows = (len(ims) + cols - 1) // cols
    sheet = Image.new("RGB", (cols * w + (cols + 1) * gap, rows * h + (rows + 1) * gap), (232, 234, 233))
    dr = ImageDraw.Draw(sheet)
    font = None
    for f in ("/System/Library/Fonts/Supplemental/Arial Bold.ttf", "/System/Library/Fonts/Helvetica.ttc"):
        if os.path.exists(f):
            font = ImageFont.truetype(f, 22)
            break
    for k, (fn, im) in enumerate(zip(files, ims)):
        x = gap + (k % cols) * (w + gap)
        y = gap + (k // cols) * (h + gap)
        sheet.paste(im.resize((w, h), Image.LANCZOS), (x, y))
        no = re.findall(r"s-(\d+)", fn)[0].lstrip("0")
        dr.rectangle([x, y, x + 34, y + 28], fill=(28, 35, 33))
        dr.text((x + 6, y + 2), no, fill=(255, 255, 255), font=font)
    os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
    sheet.save(a.out)
    print(f"→ {a.out} ({len(ims)}장, {sheet.width}×{sheet.height})")


if __name__ == "__main__":
    main()
