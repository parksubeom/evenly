# -*- coding: utf-8 -*-
"""
tools/run_public_rehearsal.py ─ "관악구 대역 리허설" 실행: 번들 풀기 → setup(Enter) → check → run_all --modes → 12·13·14
                                  ※ 결과는 공개 대역이라 실제 결과가 아님. results/public_rehearsal/<이름>/ 에 "공개 대역" 표지와 함께 복사

[실행]  python3 tools/run_public_rehearsal.py --py <QGIS 파이썬> [--root data_public/rehearsal/박수범] [--modes auto,register,all] [--name gwanak_v61] [--bundle <번들 파일 이름>]
        (먼저 QGIS 파이썬으로 tools/make_public_rehearsal.py 를 돌려 --root 자료를 만듦)
[하는 일] 안심구역에서 칠 명령을 그대로 (안내서 v6.1 단계 2~7). 화면 글자는 <root>/_logs/ 에 저장
[표지]  results/public_rehearsal/<이름>/_source.txt = "public_rehearsal" (원래 output 과 방식 폴더에도). run_all 이 실패하면 표지에 "미완료".
        결과 폴더에 run_result.json (단계별 종료 코드, 번들 이름·sha256). 기획서 빌드는 build:rehearsal 로만, build:real 은 멈춤
"""
import argparse, hashlib, json, os, re, shutil, subprocess, sys, time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools"))
from evenly_common import mark_source, refuse_raw_export, PUBLIC_REHEARSAL   # noqa: E402


def run(py, args, cwd, log, inp=""):
    t0 = time.time()
    p = subprocess.run([py] + args, cwd=cwd, input=inp.encode(), stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    out = p.stdout.decode("utf-8", "replace")
    open(log, "w", encoding="utf-8").write(out)
    return p.returncode, out, round(time.time() - t0)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--py", required=True, help="QGIS 파이썬 (osgeo·numpy 있는 것)")
    ap.add_argument("--root", default=os.path.join(ROOT, "data_public", "rehearsal", "박수범"))
    ap.add_argument("--modes", default="auto,register,all")
    ap.add_argument("--name", default="gwanak_v61", help="결과 폴더 이름 results/public_rehearsal/<이름> (영문·숫자·_.- 만). build:rehearsal 은 REHEARSAL=<이름>")
    ap.add_argument("--bundle", default="hbi_code_bundle_v6.1.txt", help="--root 안의 번들 파일 이름 (후보 번들 시험용)")
    a = ap.parse_args()
    root = os.path.abspath(a.root)
    if not os.path.exists(os.path.join(root, "공개대역_README.txt")):
        raise SystemExit(f"공개 대역 자료가 아닙니다 (공개대역_README.txt 없음): {root} → 먼저 tools/make_public_rehearsal.py")
    if not re.fullmatch(r"[A-Za-z0-9_.-]+", a.name) or a.name in (".", ".."):
        raise SystemExit(f"--name 은 영문·숫자·_.- 만: {a.name!r}")
    base = os.path.realpath(os.path.join(ROOT, "results", "public_rehearsal"))
    dst = os.path.join(base, a.name)
    if os.path.dirname(os.path.realpath(dst)) != base:
        raise SystemExit(f"결과 폴더가 results/public_rehearsal 바로 아래가 아님: {dst}")
    refuse_raw_export(dst, "공개 대역 리허설 결과")
    logs = os.path.join(root, "_logs")
    if os.path.exists(logs):
        shutil.rmtree(logs)                          # 지난 실행 기록이 섞이지 않게
    os.makedirs(logs)
    H = os.path.join(root, "hbi6")
    if os.path.exists(H):
        shutil.rmtree(H)
    res = {}
    steps = [("bundle", [a.bundle], root, ""),
             ("setup", ["setup.py", root], H, "\n" * 12),
             ("check", ["check.py"], H, ""),
             ("run_all", ["run_all.py", "--modes", a.modes], H, ""),
             ("12", ["12_isochrone.py"], H, ""), ("13", ["13_siting.py"], H, ""), ("14", ["14_dong_context.py"], H, "")]
    for name, args, cwd, inp in steps:
        rc, out, sec = run(a.py, args, cwd, os.path.join(logs, f"L_{name}.log"), inp)
        res[name] = {"rc": rc, "sec": sec}
        print(f"{name}: 끝남 {rc} ({sec}초)", flush=True)
        if name == "check" and rc != 0:
            print(out[-2000:])
            break
    bpath = os.path.join(root, a.bundle)
    res["bundle_file"] = a.bundle
    res["bundle_sha256"] = hashlib.sha256(open(bpath, "rb").read()).hexdigest() if os.path.exists(bpath) else None
    ok = res.get("run_all", {}).get("rc") == 0
    note = ("공개데이터 대역 리허설 (LX 미반영, 제출 금지)" + ("" if ok else f" — 미완료: run_all rc={res.get('run_all', {}).get('rc')}")
            + f". 번들 {a.bundle} sha256 {res['bundle_sha256']}. 자료: tools/make_public_rehearsal.py, 대응표: docs/리허설_코드대응.md")
    out_dir = os.path.join(H, "output")
    if os.path.exists(out_dir):
        for d in [out_dir] + [os.path.join(out_dir, m) for m in ("layer", "register", "gisbld", "all")]:
            if os.path.isdir(d):                     # 원래 output 에도 표지 (반출 연습으로 옮겨도 실제로 읽히지 않게)
                mark_source(d, PUBLIC_REHEARSAL, note)
        if os.path.exists(dst):
            shutil.rmtree(dst)
        shutil.copytree(out_dir, dst)
        shutil.copy(os.path.join(root, "rehearsal_meta.json"), os.path.join(dst, "rehearsal_meta.json"))
        res["copied_to"] = os.path.relpath(dst, ROOT)
        res["complete"] = ok
        json.dump(res, open(os.path.join(dst, "run_result.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    json.dump(res, open(os.path.join(logs, "run_result.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(json.dumps(res, ensure_ascii=False))


if __name__ == "__main__":
    main()
