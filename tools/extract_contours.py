# -*- coding: utf-8 -*-
"""
tools/extract_contours.py ─ [10/20] 연속수치지형도 등고선(N3L_F0010000, 국토지리정보원) zip 에서 관악 일대만 꺼내 한 파일로

[왜] 11·28장 과정 그림의 경사 색칠·등고선 배경을 공개 등고선으로 그리려고. 서울은 017·018·019 세 묶음에 나뉨
     (시도별_등고선_파일_목록.xlsx). 묶음은 전국을 객체 수로 자른 것이라 묶음마다 관악이 들었는지 모름 → 다 훑음
[실행]  (QGIS 파이썬) python tools/extract_contours.py [--raw data_public/raw] [--nums 017,018,019]
[하는 일] zip 마다 GDAL 로 열어 보고, 열리지 않으면(내려받기가 덜 끝나 zip 끝 목차가 없거나 압축이 손상) zip 안 머리 정보로
         .dbf(온전한 것)와 .shp 를 앞에서부터 풀 수 있는 데까지 풀어, 레코드 번호가 1, 2, 3 … 으로 이어지고 좌표·높이가 정상인
         데까지만 읽음 (손상 지점 뒤는 버림). 그중 관악 범위(공개 대역 DEM 범위 + 500m) 에 걸치는 등고선만 남김
[결과] data_public/raw/contour_gwanak.gpkg (EPSG:5179, 칸: CONT 높이 m, DIVI 구분, UFID, src 묶음, rec 레코드 번호)
       data_public/raw/contour_gwanak_report.json (묶음별 받은 비율·읽은 레코드·관악 등고선 수·손상 여부) — 화면에도 같은 내용
       ※ 원본 zip 은 고치지 않음. 결과는 data_public/raw (git 에 넣지 않음)
"""
import argparse, json, os, struct, sys, unicodedata, zlib
import numpy as np
from osgeo import gdal, ogr, osr
gdal.UseExceptions(); ogr.UseExceptions(); osr.UseExceptions()

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GWANAK_5179 = (946730.0, 1936120.0, 956005.0, 1944900.0)    # 공개 대역 dem5_gwanak.img 범위 (x0, y0, x1, y1)
PAD = 500.0
KOREA = (600000.0, 1300000.0, 1400000.0, 2200000.0)          # 좌표 정상 범위 (5179)


def nfc_find(raw, name):
    for x in os.listdir(raw):
        if unicodedata.normalize("NFC", x) == name:
            return os.path.join(raw, x)
    return None


def local_entries(path):
    """zip 안 머리(local header) 를 앞에서부터 차례로: {확장자: (데이터 시작, 압축 크기, 원래 크기, 방식, CRC)}"""
    size = os.path.getsize(path)
    out, off = {}, 0
    with open(path, "rb") as fh:
        while off + 30 <= size:
            fh.seek(off); h = fh.read(30)
            if h[:4] != b"PK\x03\x04":
                break
            _, flag, meth, _, _, crc, csz, usz, nl, xl = struct.unpack("<HHHHHIIIHH", h[4:30])
            name = fh.read(nl).decode("cp437", "replace"); extra = fh.read(xl)
            if 0xFFFFFFFF in (csz, usz):                        # zip64
                i = 0
                while i + 4 <= len(extra):
                    hid, hl = struct.unpack("<HH", extra[i:i + 4])
                    if hid == 1:
                        v = list(struct.unpack("<" + "Q" * (hl // 8), extra[i + 4:i + 4 + hl]))
                        if usz == 0xFFFFFFFF: usz = v.pop(0)
                        if csz == 0xFFFFFFFF: csz = v.pop(0)
                    i += 4 + hl
            d0 = off + 30 + nl + xl
            out[name.rsplit(".", 1)[-1].lower()] = (d0, csz, usz, meth, crc)
            if flag & 8 or d0 + csz > size:
                break
            off = d0 + csz
    return out, size


def inflate(path, d0, csz, meth, limit=None):
    """데이터를 풀 수 있는 데까지 (잘렸거나 손상이면 거기서 멈춤). 반환 (바이트, 다 풀렸는지, 압축 읽은 양)"""
    with open(path, "rb") as fh:
        fh.seek(d0)
        if meth == 0:
            b = fh.read(csz)
            return b, len(b) == csz, len(b)
        dec, buf, got = zlib.decompressobj(-15), bytearray(), 0
        while got < csz:
            ch = fh.read(min(1 << 22, csz - got))
            if not ch:
                break
            got += len(ch)
            try:
                buf += dec.decompress(ch)
            except zlib.error:
                return bytes(buf), False, got
            if limit and len(buf) >= limit:
                break
        return bytes(buf), dec.eof, got


def dbf_records(b):
    """dBASE III: 머리 → 칸 정의 → 레코드. 반환 (칸 이름 목록, 레코드 읽는 함수)"""
    n = struct.unpack("<I", b[4:8])[0]
    hl, rl = struct.unpack("<HH", b[8:12])
    fields, p, off = [], 32, 1
    while b[p] != 0x0D:
        nm = b[p:p + 11].split(b"\0")[0].decode("ascii", "replace")
        ln = b[p + 16]
        fields.append((nm, off, ln)); off += ln; p += 32
    def rec(i):                                                      # i = 0 부터
        s = hl + i * rl
        if s + rl > len(b):
            return None
        r = b[s:s + rl]
        return {nm: r[o:o + ln].decode("cp949", "replace").strip() for nm, o, ln in fields}
    return [f[0] for f in fields], rec, n


def shp_records(b):
    """.shp 레코드를 차례로: (번호, 도형 종류, 네모, 점 배열 목록). 번호가 이어지지 않거나 값이 이상하면 멈춤"""
    p, want = 100, 1
    while p + 8 <= len(b):
        rn, cl = struct.unpack(">ii", b[p:p + 8]); L = cl * 2
        if rn != want or L < 4 or p + 8 + L > len(b):
            return
        c = b[p + 8:p + 8 + L]
        st = struct.unpack("<i", c[:4])[0]
        if st == 0:
            yield rn, 0, None, []
        elif st in (3, 13, 23):                                      # PolyLine (Z·M)
            x0, y0, x1, y1 = struct.unpack("<4d", c[4:36])
            npt, nptot = struct.unpack("<ii", c[36:44])
            if not (KOREA[0] <= x0 <= x1 <= KOREA[2] and KOREA[1] <= y0 <= y1 <= KOREA[3]) or npt < 1 or nptot < 2 or 44 + 4 * npt + 16 * nptot > L:
                return
            parts = list(struct.unpack(f"<{npt}i", c[44:44 + 4 * npt])) + [nptot]
            xy = np.frombuffer(c, dtype="<f8", count=2 * nptot, offset=44 + 4 * npt).reshape(-1, 2)
            yield rn, st, (x0, y0, x1, y1), [xy[parts[k]:parts[k + 1]] for k in range(npt)]
        else:
            return
        want += 1; p += 8 + L


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--raw", default=os.path.join(ROOT, "data_public", "raw"))
    ap.add_argument("--nums", default="017,018,019")
    a = ap.parse_args()
    BB = (GWANAK_5179[0] - PAD, GWANAK_5179[1] - PAD, GWANAK_5179[2] + PAD, GWANAK_5179[3] + PAD)
    s5179 = osr.SpatialReference(); s5179.ImportFromEPSG(5179)
    out_p = os.path.join(a.raw, "contour_gwanak.gpkg")
    if os.path.exists(out_p):
        os.remove(out_p)
    ds = ogr.GetDriverByName("GPKG").CreateDataSource(out_p)
    lyr = ds.CreateLayer("contour", s5179, ogr.wkbMultiLineString)
    for nm, t in (("CONT", ogr.OFTReal), ("DIVI", ogr.OFTString), ("UFID", ogr.OFTString), ("src", ogr.OFTString), ("rec", ogr.OFTInteger)):
        lyr.CreateField(ogr.FieldDefn(nm, t))
    rep = {"_설명": "연속수치지형도 등고선(국토지리정보원) 중 관악 범위(공개 대역 DEM + 500m, EPSG:5179) 등고선. zip 이 덜 받아졌거나 손상이면 앞에서부터 읽힌 데까지", "files": {}}
    lyr.StartTransaction()
    for n in a.nums.split(","):
        p = nfc_find(a.raw, f"(연속수치지형도)등고선_{n}.zip")
        r = rep["files"][n] = {"zip": os.path.basename(p) if p else None}
        if not p:
            r["상태"] = "파일 없음"; continue
        ents, size = local_entries(p)
        if "shp" not in ents or "dbf" not in ents:
            r["상태"] = "zip 안에 shp·dbf 머리가 없음"; continue
        d0, csz, usz, meth, crc = ents["shp"]
        r["zip_bytes"] = size; r["shp_expected_bytes"] = usz
        r["zip_complete"] = d0 + csz <= size
        dbf, dbf_ok, _ = inflate(p, ents["dbf"][0], ents["dbf"][1], ents["dbf"][3])
        if not dbf_ok:
            r["상태"] = "dbf 가 잘림 → 높이 칸을 못 읽음"; continue
        names, rec, nrec = dbf_records(dbf)
        shp, shp_ok, got = inflate(p, d0, csz, meth)
        r["shp_inflated_bytes"] = len(shp); r["shp_inflated_share"] = round(len(shp) / usz, 3)
        r["shp_crc_ok"] = bool(shp_ok and len(shp) == usz and (zlib.crc32(shp) & 0xFFFFFFFF) == crc)   # 다 풀려도 CRC 가 다르면 손상
        last, hit = 0, 0
        for rn, st, bb, parts in shp_records(shp):
            last = rn
            if st == 0 or bb[2] < BB[0] or bb[0] > BB[2] or bb[3] < BB[1] or bb[1] > BB[3]:
                continue
            at = rec(rn - 1)
            try:
                z = float(at.get("CONT"))
            except (TypeError, ValueError):
                continue
            if not 0 <= z <= 2000:
                continue
            g = ogr.Geometry(ogr.wkbMultiLineString)
            for xy in parts:
                ln = ogr.Geometry(ogr.wkbLineString)
                for x, y in xy:
                    ln.AddPoint_2D(float(x), float(y))
                g.AddGeometry(ln)
            f = ogr.Feature(lyr.GetLayerDefn())
            f.SetGeometry(g)
            f.SetField("CONT", z); f.SetField("DIVI", at.get("DIVI", "")); f.SetField("UFID", at.get("UFID", "")); f.SetField("src", n); f.SetField("rec", rn)
            lyr.CreateFeature(f)
            hit += 1
        r.update(dbf_records=nrec, shp_records_read=last, shp_records_share=round(last / max(nrec, 1), 3), gwanak_contours=hit,
                 상태=("온전" if (r["shp_crc_ok"] and last == nrec) else
                       (f"손상(CRC 다름): 레코드 {last:,}/{nrec:,} 까지 번호·좌표가 정상" if r["zip_complete"] else f"덜 받아짐: 레코드 {last:,}/{nrec:,} 까지만 읽힘")))
        print(f"{n}: zip {size:,} / shp 풀림 {len(shp):,}/{usz:,} ({len(shp) / usz:.0%}) · 레코드 {last:,}/{nrec:,} · 관악 범위 등고선 {hit:,}개 · {r['상태']}", flush=True)
    lyr.CommitTransaction()
    ds = None
    rep["output"] = os.path.relpath(out_p, ROOT)
    json.dump(rep, open(os.path.join(a.raw, "contour_gwanak_report.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"→ {os.path.relpath(out_p, ROOT)} · 보고 data_public/raw/contour_gwanak_report.json")


if __name__ == "__main__":
    main()
