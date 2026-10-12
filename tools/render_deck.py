# -*- coding: utf-8 -*-
"""
tools/render_deck.py ─ 기획서 pptx 를 미리보기 그림(PDF·장별 PNG)으로 (LibreOffice, 맥에서 확인용)

[실행]  python3 tools/render_deck.py deliverables/_rehearsal_기획서_v6_A.pptx [--out _render/v6_A] [--dpi 80]
[하는 일] 맥에는 맑은 고딕이 없어 LibreOffice 가 한글을 비워 그리므로, pptx **사본**의 글꼴 이름만 Apple SD Gothic Neo 로 바꿔
        soffice 로 PDF 를 만들고 pdftoppm 으로 장마다 PNG (s-01.png …). 원본 pptx 는 고치지 않음 (제출본은 맑은 고딕 그대로)
        [10/12] 이 맥의 LibreOffice 26.8 은 시스템 글꼴을 찾지 못해, 렌더링 전용 프로필(--profile, 기본 _render/lo_profile)의
        user/fonts 에 Apple SD Gothic Neo·Arial Unicode 사본을 넣고 그 프로필로 실행함 (사용자 LibreOffice 설정은 건드리지 않음)
[결과]  <out>/<이름>.pdf, <out>/s-NN.png  (_render/ 는 git 에 넣지 않음)
"""
import argparse, os, shutil, subprocess, sys, tempfile, zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FROM, TO = "Malgun Gothic", "Apple SD Gothic Neo"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("pptx")
    ap.add_argument("--out")
    ap.add_argument("--dpi", type=int, default=80)
    ap.add_argument("--profile", default=os.path.join(ROOT, "_render", "lo_profile"))
    a = ap.parse_args()
    src = os.path.abspath(a.pptx)
    name = os.path.splitext(os.path.basename(src))[0]
    out = os.path.abspath(a.out or os.path.join(ROOT, "_render", name))
    os.makedirs(out, exist_ok=True)
    for f in os.listdir(out):
        if f.startswith("s-") and f.endswith(".png"):
            os.remove(os.path.join(out, f))
    tmp = tempfile.mkdtemp()
    cp = os.path.join(tmp, name + ".pptx")
    with zipfile.ZipFile(src) as zi, zipfile.ZipFile(cp, "w", zipfile.ZIP_DEFLATED) as zo:
        for it in zi.infolist():
            b = zi.read(it.filename)
            if it.filename.endswith(".xml"):
                b = b.replace(FROM.encode(), TO.encode())
            zo.writestr(it, b)
    prof = os.path.abspath(a.profile)
    fdir = os.path.join(prof, "user", "fonts")
    os.makedirs(fdir, exist_ok=True)
    for f in ("/System/Library/Fonts/AppleSDGothicNeo.ttc", "/Library/Fonts/Arial Unicode.ttf"):
        if os.path.exists(f) and not os.path.exists(os.path.join(fdir, os.path.basename(f))):
            shutil.copy(f, fdir)
    soffice = "/Applications/LibreOffice.app/Contents/MacOS/soffice" if os.path.exists("/Applications/LibreOffice.app") else shutil.which("soffice")
    subprocess.run([soffice, f"-env:UserInstallation=file://{prof}", "--headless", "--convert-to", "pdf", "--outdir", tmp, cp], check=True, capture_output=True)
    pdf = os.path.join(out, name + ".pdf")
    shutil.move(os.path.join(tmp, name + ".pdf"), pdf)
    subprocess.run(["pdftoppm", "-r", str(a.dpi), "-png", pdf, os.path.join(out, "s")], check=True)
    shutil.rmtree(tmp, ignore_errors=True)
    n = len([f for f in os.listdir(out) if f.startswith("s-")])
    print(f"{os.path.relpath(pdf, ROOT)} + 장별 PNG {n}개 → {os.path.relpath(out, ROOT)}")


if __name__ == "__main__":
    main()
