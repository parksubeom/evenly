# -*- coding: utf-8 -*-
"""
lib/conout.py ─ [v6] 화면 출력: 콘솔 코드페이지(chcp 949 / 65001)와 상관없이 한글이 깨지지 않게, 화면과 파일에 동시에

[왜] 1차 방문 때 콘솔 한글이 깨져 chcp 65001 을 쳐야 했음. 파이썬 3.6+ 는 진짜 콘솔에는 코드페이지와 상관없이
     유니코드로 찍지만, 출력이 파일·파이프로 가면 코드페이지 인코딩을 써서 깨지거나 멈출 수 있음.
[쓰는 법]
    from lib.conout import Tee, safe_console
    safe_console()                     # 못 찍는 글자는 ? 로 바꾸고 멈추지 않게
    with Tee(path) as t:               # 이 안의 print 는 화면 + 파일(UTF-8) 둘 다
        print("…")
"""
import io, os, sys


def safe_console():
    for s in (sys.stdout, sys.stderr):
        try:
            s.reconfigure(errors="replace")
        except (AttributeError, ValueError):
            pass


class Tee:
    """print 를 화면과 파일(UTF-8) 에 동시에. JS로 치면 console.log 를 감싸 로그 파일에도 쓰는 것"""

    def __init__(self, path):
        self.path = path
        self.f = None
        self.old = None

    def __enter__(self):
        os.makedirs(os.path.dirname(self.path), exist_ok=True)
        self.f = open(self.path, "w", encoding="utf-8")
        self.old = sys.stdout
        sys.stdout = self
        return self

    def write(self, s):
        try:
            self.old.write(s)
        except UnicodeEncodeError:
            self.old.write(s.encode(self.old.encoding or "utf-8", "replace").decode(self.old.encoding or "utf-8", "replace"))
        self.f.write(s)
        return len(s)

    def flush(self):
        self.old.flush()
        self.f.flush()

    def __exit__(self, *a):
        sys.stdout = self.old
        self.f.close()
        return False


def ask(prompt, default=""):
    """입력 받기. 입력이 없거나(Enter) 입력 창이 없으면 default"""
    try:
        v = input(prompt)
    except EOFError:
        v = ""
    return v.strip() or default
