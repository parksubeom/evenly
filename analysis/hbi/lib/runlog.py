# -*- coding: utf-8 -*-
"""
lib/runlog.py ─ [v6.2] 반출 없이 원인을 찾는 기록: 전체 로그는 안에(work/logs), 멈추면 손으로 적을 메모 카드(5줄), 값 가리기

[왜]  반출은 건마다 심사가 있어 느림. 손메모 반출은 센터가 허용함 → 전체 로그는 안에 두고, 멈추면 짧은 카드를 화면에 띄움.
[쓰는 법] 진입점(setup·check·run_all·01~14) 맨 위, 무거운 import 보다 먼저:
        import lib.runlog as _RL; _RL.start(globals())
    → 이 스크립트를 기록 장치 안에서 다시 실행함 (runpy). 화면에 나오는 글자는 그대로 work/logs/<시각>_<스크립트>[_방식].log 에도
      (줄마다 flush), 처리되지 않은 오류·안내 멈춤(SystemExit)·Ctrl+C 는 같은 로그에 남기고 화면에 메모 카드를 띄움.
      work/logs/마지막.log 는 늘 가장 최근 로그와 같은 내용 (UTF-16 이라 cmd 의 type 으로도 한글이 보임. notepad 도 됨).
      run_all 이 부른 단계는 마지막.log 를 쓰지 않음 (run_all 로그에 단계 글자가 다 들어 있음)
    QGIS 파이썬 콘솔에서 exec 로 돌릴 때(파일 이름이 없음)는 아무것도 하지 않음 (GDAL 경고 처리기도 걸지 않음).
[오류 번호] E<단계>-<6자>: 단계 = 스크립트 앞 두 글자(01~14) 또는 SU(setup)·CK(check)·RA(run_all).
    6자 = 오류가 난 파일·줄(우리 코드 안에서 가장 안쪽)과 판의 내용 해시(VERSION 의 #…)로 만든 5자 + 확인 1자.
    32자 표(헷갈리는 I·L·O·U 없음), 확인 글자는 GF(32) 가중합이라 한 글자 틀림·이웃 두 글자 바뀜을 모두 잡음.
    같은 판·같은 위치면 늘 같은 번호, 판이 다르면 다른 번호 (밖에서 다른 판으로 찾으면 엉뚱한 줄 대신 '찾지 못함').
    밖에서: python3 tools/lookup_error.py E03-7K2Q4M --bundle <그 번들> → 파일·줄·함수·주변 코드
[값 가리기] 오류 글자(화면의 stderr·카드·로그 모두)에서 따옴표 안 글자·바이트·긴 숫자·좌표·지번은 모양만 (<한글 13자·숫자 3자>).
    칸·레이어 이름(mapping·config·schema.txt 의 이름, 영문 식별자), 코덱 이름, 실제 경로 모양, 코드 줄, 개수·비율은 그대로.
    stdout(우리 진행 글자)은 원래 값 없이 쓰므로 그대로. 한계: 따옴표 없는 사람 이름 같은 것은 규칙으로 못 잡음 → 우리 오류 글자에는 값을 넣지 않음
[표준 라이브러리만] numpy·GDAL 보다 먼저 켜져야 하므로 (GDAL import 실패도 남게)
"""
import hashlib, os, re, sys, time, traceback

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))     # hbi 폴더
LOGDIR = os.path.join(HERE, "work", "logs")
LAST = os.path.join(LOGDIR, "마지막.log")
ALPHA = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"                             # 32자 (I·L·O·U 없음)
WEIGHTS = (2, 3, 4, 5, 6)                                              # 확인 글자 가중치 (GF(32) 원소, 확인 글자 자신은 1)
PREFIX = {"setup.py": "SU", "check.py": "CK", "run_all.py": "RA"}
CARD_MARK = "==== 메모 카드"
_ACTIVE = False
_STATE = {"stop_at": None, "stop_txt": None, "n_stop": 0, "suppress": False, "t0": None, "script": "", "files": [],
          "relay": False, "stage": None, "stage_todo": None, "gdal": [0, 0], "code": None}


# ── 판 ───────────────────────────────────────────────────
def _version():
    try:
        with open(os.path.join(HERE, "VERSION"), encoding="utf-8-sig") as fh:
            return fh.read().strip() or "개발판"
    except Exception:
        return "개발판"


def salt_of(version):
    """VERSION 글자의 #<내용 해시> → 오류 번호 소금 (개발판은 빈 글자)"""
    m = re.search(r"#([0-9a-f]{6,})", version or "")
    return m.group(1) if m else ""


_SALT = []


def _salt():
    if not _SALT:
        _SALT.append(salt_of(_version()))
    return _SALT[0]


# ── 오류 번호 ─────────────────────────────────────────────
def _gmul(a, b):
    """GF(32) 곱셈 (다항식 x^5+x^2+1)"""
    r = 0
    while b:
        if b & 1:
            r ^= a
        b >>= 1
        a <<= 1
        if a & 32:
            a ^= 0b100101
    return r


def check_char(body):
    """몸 5자 → 확인 1자 (가중합 + 확인 = 0)"""
    v = 0
    for w, c in zip(WEIGHTS, body):
        v ^= _gmul(w, ALPHA.index(c))
    return ALPHA[v]


def code_ok(c6):
    return len(c6) == 6 and all(c in ALPHA for c in c6) and check_char(c6[:5]) == c6[5]


def content_hash(files):
    """[build_bundle·lookup] 판의 내용 해시 = 오류 번호 소금: .py 파일 (hbi 기준 상대 경로, 글자) 를 정렬해 sha1 앞 6자"""
    h = hashlib.sha1()
    for rel in sorted(k for k in files if k.endswith(".py")):
        h.update(rel.encode("utf-8") + b"\0" + files[rel].encode("utf-8") + b"\0")
    return h.hexdigest()[:6]


def site_code(rel, line, salt=None):
    """파일(hbi 기준 상대 경로, / 로)·줄 → 6자 (5자 + 확인 1자). 소금 = 판의 내용 해시"""
    salt = _salt() if salt is None else salt
    h = hashlib.sha1(f"{salt}|{str(rel).lower()}:{int(line or 0)}".encode("utf-8")).digest()
    v = int.from_bytes(h[:4], "big") >> 7                                # 25비트
    body = "".join(ALPHA[(v >> s) & 31] for s in (20, 15, 10, 5, 0))
    return body + check_char(body)


def prefix_of(script):
    b = os.path.basename(script).lower()
    return b[:2] if b[:2].isdigit() else PREFIX.get(b, "XX")


def error_code(script, rel, line):
    return f"E{prefix_of(script)}-{site_code(rel, line)}"


def _rel(path):
    """hbi 폴더 안의 실제 파일이면 상대 경로(/), 아니면 None (<…> 같은 가짜 파일 이름도 None)"""
    if not path or str(path).startswith("<"):
        return None
    try:
        p = os.path.abspath(path)
        if not os.path.isfile(p):
            return None
        r = os.path.relpath(p, HERE)
    except (ValueError, OSError, TypeError):             # 다른 드라이브 (Windows)
        return None
    return None if r.startswith("..") else r.replace(os.sep, "/")


def _site(tb, script_rel=None):
    """traceback → (우리 코드 중 가장 안쪽 (파일, 줄), 진입 스크립트 자신의 가장 안쪽 (파일, 줄)). 없으면 None"""
    inner = caller = None
    for fr, ln in traceback.walk_tb(tb):
        r = _rel(fr.f_code.co_filename)
        if r and r != "lib/runlog.py":
            inner = (r, ln or 0)
            if script_rel and r.lower() == script_rel.lower():
                caller = (r, ln or 0)
    return inner, caller


def note_stop(why=None, todo=None, exc=None, depth=2):
    """[check 의 stop() 처럼] 멈춤을 모았다가 나중에 sys.exit(1) 로 끝낼 때: 첫 멈춤의 자리·글자를 카드에 쓰게 기록.
    exc 를 주면 그 예외가 난 자리(예: battr 의 안내 멈춤)를 씀"""
    _STATE["n_stop"] += 1
    if _STATE["stop_at"] is None:
        site = _site(exc.__traceback__)[0] if exc is not None and getattr(exc, "__traceback__", None) else None
        if site is None:
            f = sys._getframe(depth)
            r = _rel(f.f_code.co_filename)
            site = (r, f.f_lineno) if r else None
        _STATE["stop_at"], _STATE["stop_txt"] = site, (why, todo)


def suppress_card():
    """run_all 처럼 자식 단계가 이미 카드를 띄웠을 때 자기 카드는 띄우지 않음"""
    _STATE["suppress"] = True


def set_stage(stage=None, todo=None):
    """[run_all] 지금 돌고 있는 단계 (Ctrl+C 카드의 단계·할 일에 씀). None 이면 지움"""
    _STATE["stage"], _STATE["stage_todo"] = stage, todo


def relay(on):
    """[run_all] 자식 단계 글자를 넘기는 동안은 [시:분:초] 줄 끝에 run_all 자신의 메모리를 붙이지 않음"""
    _STATE["relay"] = bool(on)


# ── 값 가리기 ─────────────────────────────────────────────
CODECS = {"utf-8", "utf8", "utf-8-sig", "cp949", "euc-kr", "euckr", "ascii", "utf-16", "utf-16-le", "utf-16-be",
          "latin-1", "latin1", "iso-8859-1", "mbcs", "charmap", "cp1252", "cp437"}
EXT = r"py|shp|shx|dbf|prj|cpg|csv|txt|img|tif|tiff|asc|gpkg|geojson|json|zip|npz|log|xlsx|xls|dxf|md|bak|pdf|png|ige|rrd|aux|xml"
_KEEP = {}
_IDENT = re.compile(r"[A-Za-z_][A-Za-z0-9_.\-]{0,40}")
_QUOTE = re.compile(r"(?<![A-Za-z0-9_])([bB]?)(['\"])(.*?)\2(?![A-Za-z0-9_])")
_PAIR = re.compile(r"(?<![A-Za-z0-9_./\\-])-?\d{2,7}\.\d+\s*[,; \t]\s*-?\d{2,7}\.\d+(?![A-Za-z0-9_./\\])")   # 좌표 쌍 (소수점 둘)
_AXIS = re.compile(r"(?<![0-9.])-?(?:12[4-9]|13[0-2]|3[3-9])\.\d{4,}(?![0-9])")                              # 경위도 한 축
_JIBUN = re.compile(r"[가-힣]+[동리가로길]\s*(?:산\s*)?\d{1,5}-\d{1,5}(?:번지)?|\d{1,5}(?:-\d{1,5})?번지")
_DASHNUM = re.compile(r"(?<![A-Za-z0-9_./\\-])\d+(?:-\d+)+(?![A-Za-z0-9_\-])")                             # 숫자-숫자 묶음
_LONG10 = re.compile(r"\d{10,}")
_LONG6 = re.compile(r"(?<![A-Za-z0-9_./\\<])\d{6,}(?:\.\d+)?(?![A-Za-z0-9_./\\])")


def looks_like_value(name):
    """[v6.2] 칸 이름 자리에 값이 온 것으로 보이면 True (머리줄 없는 CSV 의 첫 행): 숫자만, 5자리 이상 숫자, 숫자-숫자"""
    s = str(name).strip().lstrip("\ufeff")
    return bool(re.fullmatch(r"[-+]?[\d.,]+", s) or re.search(r"\d{5,}", s) or re.search(r"\d+-\d+", s))


def _schema_names():
    """output/schema/schema.txt 의 칸 이름 (값이 아닌 것으로 보이는 것만)"""
    names = set()
    try:
        import ast
        p = os.path.join(HERE, "output", "schema", "schema.txt")
        with open(p, encoding="utf-8-sig") as fh:
            for ln in fh:
                s = ln.strip()
                if s.startswith("칸 ") and "(" in s:                       # shp: 칸 A(문자), B(정수)
                    names.update(re.sub(r"\([^()]*\)$", "", x.strip()) for x in s[2:].split(", "))
                m = re.search(r", 칸 (\[.*\])$", s)                         # CSV: … 칸 ['A', 'B']
                if m:
                    names.update(str(x) for x in ast.literal_eval(m.group(1)))
    except Exception:
        pass
    return {n for n in names if n and not looks_like_value(n)}


def _known_names():
    key = id(sys.modules.get("config"))
    if key in _KEEP:
        return _KEEP[key]
    names = set()
    try:
        from lib import mapping as M
        for v in M.DEFAULTS.values():
            names.update(x.strip() for x in str(v[0]).replace(";", ",").split(",") if x.strip())
        for v in M.ALIASES.values():
            names.update(v)
    except Exception:
        pass
    C = sys.modules.get("config")
    if C is not None:
        try:
            for d in (getattr(C, "MAPPING", {}) or {}, getattr(C, "COL", {}) or {}, getattr(C, "FIELD", {}) or {}):
                for x in d.values():
                    names.update(x if isinstance(x, (list, tuple)) else [x])
            for v in (getattr(C, "LAYERS", {}) or {}).values():
                names.update(v if isinstance(v, (list, tuple)) else [v])
            for grp in ("JOIN_DATA", "POINT_DATA", "LEGAL_DONG_DATA"):     # 묶음 이름과 *_col·value_cols·filter 칸
                for k, cfg in (getattr(C, grp, {}) or {}).items():
                    names.add(k)
                    for kk, vv in (cfg or {}).items():
                        if kk.endswith("_col") or kk.endswith("_cols"):
                            names.update(vv if isinstance(vv, (list, tuple)) else [vv])
                        elif kk in ("filter", "contains") and isinstance(vv, dict):
                            names.update(vv.keys())
        except Exception:
            pass
    names.update(_schema_names())
    _KEEP[key] = out = {str(n) for n in names if n}
    return out


def shape(t):
    """글자 → 모양만 (<한글 13자·숫자 3자>)"""
    k = sum(1 for c in t if "가" <= c <= "힣")
    d = sum(c.isdigit() for c in t)
    a = sum(c.isascii() and c.isalpha() for c in t)
    o = len(t) - k - d - a - t.count(" ")
    parts = [f"한글 {k}자"] * bool(k) + [f"숫자 {d}자"] * bool(d) + [f"영문 {a}자"] * bool(a) + [f"기타 {o}자"] * bool(o > 0)
    return "<" + "·".join(parts or ["빈 글자"]) + ">"


def _pathlike(t):
    """실제 경로 모양일 때만 True: 드라이브·/·./·~ 로 시작, 또는 (repr 이스케이프 없이) 구분자 + 아는 확장자, 또는 영문 파일 이름"""
    s = t.replace("\\\\", "/")
    if re.match(r"([A-Za-z]:[/\\]|//|/|\.{1,2}[/\\]|~[/\\]?)", s):
        return True
    if re.search(r"\\(x[0-9a-fA-F]{2}|u[0-9a-fA-F]{4}|U[0-9a-fA-F]{8}|N\{|[ntr0abfv'\"])", s):
        return False                                     # 값 안의 \xa0·\t 같은 repr 이스케이프
    s = s.replace("\\", "/")
    if "/" in s and re.search(rf"\.({EXT})$", s, re.I):
        return True
    return bool(re.fullmatch(rf"[A-Za-z][A-Za-z0-9_\-]*\.({EXT})", s, re.I))     # 예: N3A_A0010000.shp


def _keep_body(b, keep):
    b2 = b[6:] if b.startswith("\\ufeff") else b.lstrip("\ufeff")
    if not b or b in keep or b2 in keep or b2.lower() in CODECS:
        return True
    if re.fullmatch(r"<[^<>]*>", b):                     # 이미 가린 모양
        return True
    if len(b) <= 3 and not re.search(r"[0-9A-Za-z가-힣]", b):     # 괄호 같은 기호 ("'(' was never closed")
        return True
    if _IDENT.fullmatch(b2) and sum(c.isdigit() for c in b2) <= 4 and "\\" not in b2:
        return True
    return _pathlike(b)


def _dashnum(m):
    """숫자-숫자 묶음: 두 묶음이면서 숫자 4자 이상(지번 987-65 등) 또는 숫자 9자 이상(전화·등록번호)이면 가림. 날짜 2026-10-09 는 남김"""
    t = m.group(0)
    n, g = sum(c.isdigit() for c in t), t.count("-") + 1
    return "<번호 모양>" if (g == 2 and n >= 4) or n >= 9 else t


def mask(text, keep=None):
    """오류 글자에서 값이 될 수 있는 것을 모양만 남김. 칸 이름·경로·코드·개수·비율은 그대로. 여러 번 해도 같음"""
    keep = _known_names() if keep is None else keep

    def q(m):
        pre, qt, body = m.group(1), m.group(2), m.group(3)
        if (not pre and _keep_body(body, keep)) or re.fullmatch(r"<[^<>]*>", body):
            return m.group(0)
        return pre + qt + (shape(body) if body else "") + qt          # 바이트(b'…')는 늘 가림
    out = []
    for ln in str(text).split("\n"):
        if re.match(r'\s*File "', ln):                          # traceback 의 파일 줄은 그대로 (경로·줄 번호)
            out.append(ln)
            continue
        ln = _QUOTE.sub(q, ln)
        ln = _PAIR.sub("<좌표>", ln)
        ln = _AXIS.sub("<좌표>", ln)
        ln = _JIBUN.sub("<지번>", ln)
        ln = _DASHNUM.sub(_dashnum, ln)
        ln = _LONG10.sub(lambda m: f"<숫자 {len(m.group(0))}자리>", ln)
        ln = _LONG6.sub(lambda m: f"<숫자 {len(m.group(0).split('.')[0])}자리>", ln)
        out.append(ln)
    return "\n".join(out)


def _relpaths(text):
    """카드 내용: hbi 폴더 아래 경로는 상대 경로로 (예: work\\network.npz) — 110자 안에 파일 이름이 들어가게"""
    for h in (HERE, HERE.replace("\\", "\\\\"), HERE.replace("\\", "/")):
        for sep in ("\\\\", "\\", "/"):
            text = text.replace(h + sep, "")
    return text


def masked_traceback(e, script=None):
    """traceback 글자 (스크립트 첫 틀부터, 파일 줄·코드 줄은 그대로, 오류 내용은 가림)"""
    tb = e.__traceback__
    if script:                                                  # runpy·runlog 틀은 버림
        t = tb
        while t is not None and os.path.abspath(t.tb_frame.f_code.co_filename) != os.path.abspath(script):
            t = t.tb_next
        tb = t or tb
    keep = _known_names()
    res, ours = [], False
    for chunk in traceback.format_exception(type(e), e, tb):
        if chunk.startswith("  File "):                         # 파일 줄 + 코드 줄
            res.append(chunk)
            m = re.match(r'  File "([^"]+)"', chunk)
            r = _rel(m.group(1)) if m else None
            ours = bool(r) and r != "config.py" and chunk.count("\n") <= 1     # SyntaxError 의 파일 줄 (코드 조각이 따로 옴)
        elif ours and chunk.startswith("    "):                # SyntaxError 의 코드 조각 (우리 코드 파일만. config.py 는 가림)
            res.append(chunk)
        else:
            res.append(mask(chunk, keep))
            ours = False
    return "".join(res)


# ── 메모리 ────────────────────────────────────────────────
_WIN = []


def _win_mem():
    if not _WIN:
        import ctypes
        from ctypes import wintypes

        class PMC(ctypes.Structure):
            _fields_ = [("cb", wintypes.DWORD), ("PageFaultCount", wintypes.DWORD), ("PeakWorkingSetSize", ctypes.c_size_t),
                        ("WorkingSetSize", ctypes.c_size_t), ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
                        ("QuotaPagedPoolUsage", ctypes.c_size_t), ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
                        ("QuotaNonPagedPoolUsage", ctypes.c_size_t), ("PagefileUsage", ctypes.c_size_t), ("PeakPagefileUsage", ctypes.c_size_t)]
        k = ctypes.WinDLL("kernel32")
        k.GetCurrentProcess.restype = wintypes.HANDLE
        p = ctypes.WinDLL("psapi")
        p.GetProcessMemoryInfo.argtypes = [wintypes.HANDLE, ctypes.POINTER(PMC), wintypes.DWORD]
        p.GetProcessMemoryInfo.restype = wintypes.BOOL
        _WIN.append((ctypes, PMC, k, p))
    ctypes, PMC, k, p = _WIN[0]
    c = PMC()
    c.cb = ctypes.sizeof(PMC)
    if not p.GetProcessMemoryInfo(k.GetCurrentProcess(), ctypes.byref(c), c.cb):
        return None, None
    return round(c.WorkingSetSize / 2**20), round(c.PeakWorkingSetSize / 2**20)


def mem_mb():
    """(지금, 최대) MB. 모르면 (None, None)"""
    try:
        if os.name == "nt":
            return _win_mem()
        import resource
        peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        peak = peak / 2**20 if sys.platform == "darwin" else peak / 1024     # 맥은 바이트, 리눅스는 KB
        return None, round(peak)
    except Exception:
        return None, None


def _mem_txt():
    now, peak = mem_mb()
    return f"메모리 {now}MB (최대 {peak}MB)" if now is not None else (f"최대 메모리 {peak}MB" if peak is not None else "메모리 모름")


# ── 화면 + 로그 ───────────────────────────────────────────
class _Tee:
    """화면(원래 출력)과 로그 파일들에 같은 글자를 씀.
    stdout: 화면에는 바로, 로그에는 줄 단위 ([시:분:초] 줄 끝에 메모리). stderr(masked): 줄마다 값 가림 뒤 화면·로그 둘 다"""

    def __init__(self, orig, files, masked=False):
        self.orig, self.files, self.masked, self.buf = orig, files, masked, ""

    def _screen(self, s):
        try:
            self.orig.write(s)
        except UnicodeEncodeError:
            enc = getattr(self.orig, "encoding", None) or "utf-8"
            try:
                self.orig.write(s.encode(enc, "replace").decode(enc, "replace"))
            except Exception:
                pass
        except Exception:
            pass
        try:
            self.orig.flush()
        except Exception:
            pass

    def _log(self, ln):
        if not self.masked and not _STATE["relay"] and re.match(r"\[\d\d:\d\d:\d\d\]", ln):
            ln += f"   · {_mem_txt()}"
        for f in self.files:
            try:
                f.write(ln + "\n")
                f.flush()
            except Exception:
                pass

    def write(self, s):
        s = str(s)
        if not self.masked:
            self._screen(s)
        self.buf += s
        if "\n" in self.buf:
            parts = self.buf.split("\n")
            self.buf = parts.pop()
            for ln in parts:
                if self.masked:
                    ln = mask(ln)
                    self._screen(ln + "\n")
                self._log(ln)
        return len(s)

    def write_raw(self, s):
        """이미 가린 글자(카드·traceback) — 다시 가리지 않고 화면·로그에"""
        self.end()
        self._screen(s)
        for ln in s.rstrip("\n").split("\n"):
            self._log(ln)

    def end(self):
        """줄바꿈 없이 남은 글자도 내보냄"""
        if self.buf:
            ln, self.buf = self.buf, ""
            if self.masked:
                ln = mask(ln)
                self._screen(ln + "\n")
            self._log(ln)

    def note_input(self, v):
        """[conout.ask] 질문 줄 + 친 답을 로그에 한 줄로 (화면은 이미 보임)"""
        ln, self.buf = self.buf + mask(str(v)), ""
        self._log(ln)

    def flush(self):
        try:
            self.orig.flush()
        except Exception:
            pass

    def isatty(self):
        try:
            return self.orig.isatty()
        except Exception:
            return False

    @property
    def encoding(self):
        return getattr(self.orig, "encoding", "utf-8")

    def fileno(self):
        return self.orig.fileno()


def _raw(s):
    t = sys.stderr
    if isinstance(t, _Tee):
        t.write_raw(s)
    else:
        print(s, file=t, end="", flush=True)


def _filelog(text):
    for f in _STATE["files"]:
        try:
            f.write(text.rstrip("\n") + "\n")
            f.flush()
        except Exception:
            pass


def _config_summary():
    C = sys.modules.get("config")
    if C is None:
        return "설정 읽기 전에 끝남"
    try:
        return (f"방식 {getattr(C, 'BUILDING_ATTR_MODE', '?')}, 대상 구 {','.join(getattr(C, 'TARGET_GU', []) or []) or '전체'}, "
                f"지도 폴더 {len(getattr(C, 'MAP_FOLDERS', []) or [])}개, AREA_BBOX {'있음' if getattr(C, 'AREA_BBOX', None) else '없음'}, "
                f"DEM 1m {'있음' if getattr(C, 'DATA_ROOT_DEM1M', None) else '없음'}, 필지 {'있음' if getattr(C, 'DATA_ROOT_PARCEL', None) else '없음'}")
    except Exception:
        return "설정 요약 실패"


# ── GDAL 경고 ─────────────────────────────────────────────
def gdal_errors(gdal):
    """[v6.2] GDAL 이 C 쪽에서 직접 찍던 경고·오류 글자를 파이썬 sys.stderr 로 (→ 값 가림·로그). 기록 장치가 켜졌을 때만.
    같은 경고는 3번까지만. GDAL 바인딩은 UTF-8 이 아닌(cp949 칸 값이 든) 경고를 글자로 못 바꾸면 UnicodeDecodeError 를 걸어 둔 채
    인자 없이 부름 → 그 오류의 원래 바이트를 cp949 로 읽어 씀.
    처리기 안에서 예외가 나면 GDAL 이 깨지므로 모두 삼킴. setup 처럼 그 위에 CPLQuietErrorHandler 를 쌓으면 계속 조용함"""
    if not _ACTIVE or _STATE.get("gdal_h"):
        return
    seen, names = {}, {2: "Warning", 3: "ERROR", 4: "FATAL"}

    def _undecoded(e):
        """글자로 못 바꾼 경고: 걸려 있던 UnicodeDecodeError(직접 또는 SystemError 의 원인)에 원래 바이트가 있음"""
        for x in (e, getattr(e, "__cause__", None), getattr(e, "__context__", None)):
            if isinstance(x, UnicodeDecodeError) and isinstance(x.object, (bytes, bytearray)):
                return bytes(x.object).decode("cp949", "replace")
        return None

    def h(*a):
        try:
            try:
                n = len(a)                                   # 걸려 있던 오류가 있으면 여기서 올라옴
                cls, no, msg = (a[0], a[1], a[2]) if n >= 3 else (gdal.GetLastErrorType(), gdal.GetLastErrorNo(), gdal.GetLastErrorMsg())
            except BaseException as e:                       # GDAL 3.13 등: cp949 값이 든 경고를 UTF-8 로 못 바꾼 채 인자 없이 부름
                msg = _undecoded(e)
                if msg is None:
                    return
                cls, no = gdal.GetLastErrorType() or 2, gdal.GetLastErrorNo() or 1
            if cls < 2:                                      # 디버그 글자는 내지 않음
                return
            raw = str(msg)
            k = re.sub(r"'[^']*'|\"[^\"]*\"|\d+", "", raw)[:80]       # 같은 경고 판정 (값·숫자 빼고). 가리기는 낼 때만
            seen[k] = seen.get(k, 0) + 1
            _STATE["gdal"][0] += 1
            if seen[k] <= 3:
                sys.stderr.write(f"{names.get(cls, 'GDAL')} {no}: {mask(raw)}" + (" (같은 경고는 이후 생략)" if seen[k] == 3 else "") + "\n")
            else:
                _STATE["gdal"][1] += 1
        except BaseException:
            pass
    try:
        gdal.PushErrorHandler(h)
        _STATE["gdal_h"] = h                                 # 처리기가 사라지지 않게 붙잡아 둠
    except Exception:
        pass


# ── 메모 카드 ─────────────────────────────────────────────
GENERIC = "이 카드를 적어 오면 밖에서 찾습니다 (반출하지 않아도 됨)"


def _todo(kind, line, site, exc=None, content=""):
    """오류 종류·자리 → 할 일 (run_all 의 진단과 같은 뜻)"""
    rel = (site or ("", 0))[0]
    if (exc is not None and isinstance(exc, MemoryError)) or "MemoryError" in kind:
        return "메모리 부족: 다른 프로그램을 닫고 같은 명령 다시. 또 멈추면 config.py 의 AREA_BBOX 로 범위를 좁힘"
    if (exc is not None and isinstance(exc, SyntaxError)) or kind in ("SyntaxError", "IndentationError", "TabError"):
        if rel == "config.py":
            return (f"config.py 의 {site[1]}줄 (따옴표·쉼표·괄호) 확인, 메모장이면 UTF-8 로 다시 저장. "
                    "안 되면 config.py.bak 을 config.py 로 복사 → python setup.py")
        return "코드 파일이 바뀌었음: 번들을 다시 풀기 (python hbi_code_bundle_….txt) → python setup.py → python check.py"
    if kind == "KeyError":
        key = re.search(r"KeyError: '([^']*)'", content)
        if key and key.group(1) and not key.group(1).startswith("<"):    # 가려지지 않은 = 아는 칸 이름
            return "mapping.txt 에서 그 칸 이름 줄을 실제 칸 이름으로 고치거나 python setup.py 다시 → python check.py"
        return GENERIC
    if kind in ("ModuleNotFoundError", "ImportError") and re.search(r"osgeo|gdal|ogr|numpy", line):
        return "QGIS 의 OSGeo4W Shell 에서 쳤는지 확인 (일반 명령창이면 단계 1 부터)"
    if kind == "FileNotFoundError" or "No such file" in line:
        return "파일·폴더 주소 확인 (python setup.py 를 다시 하면 config.py 를 채움)"
    if kind == "UnicodeDecodeError":
        return "글자 형식(인코딩): python check.py 의 인코딩 줄 확인, 메모장으로 고쳤으면 UTF-8 로 저장"
    return GENERIC


def card(code, stage, kind, content, todo):
    """화면(과 로그)에 메모 카드. 손으로 적을 다섯 줄 (내용·할 일은 이미 가린 글자)"""
    lines = [f"\n{CARD_MARK} (아래 다섯 줄만 적어 오면 됨 · 반출하지 않아도 됨) ====",
             f"  1 오류 번호 : {code}   ({_version()})",
             f"  2 단계      : {stage}",
             f"  3 오류 종류 : {kind}",
             f"  4 내용      : {content[:110]}",
             f"  5 할 일     : {todo}",
             "  (전체 기록: notepad work\\logs\\마지막.log  - 반출하지 않음)",
             "=" * 60]
    _raw("\n".join(lines) + "\n")


def _unesc(p):
    """faulthandler 가 쓴 경로의 \\uXXXX·\\xNN 를 원래 글자로"""
    return re.sub(r"\\(?:x([0-9a-f]{2})|u([0-9a-f]{4})|U([0-9a-f]{8}))", lambda m: chr(int(m.group(1) or m.group(2) or m.group(3), 16)), p)


def _frames(lines):
    out = []
    for x in lines:
        m = re.match(r'\s*File "([^"]+)", line (\d+)', x)
        if m:
            r = _rel(_unesc(m.group(1)))
            if r and r != "lib/runlog.py":
                out.append((r, int(m.group(2))))
    return out


def rc_text(rc):
    """종료 코드 글자. Windows 의 큰 코드는 16진수도 (0xC0000005 = 접근 위반), 맥·리눅스의 음수는 신호 번호"""
    if isinstance(rc, int) and rc > 255:
        return f"종료 코드 {rc} = {rc & 0xFFFFFFFF:#010x}"
    if isinstance(rc, int) and rc < 0:
        return f"종료 코드 {rc} (신호 {-rc})"
    return f"종료 코드 {rc}"


def card_from_text(script, tail, stage=None, rc=None):
    """[run_all] 자식이 카드 없이 끝났을 때(그 스크립트 자체의 SyntaxError, C 코드 충돌 등) 마지막 화면 글자로 카드를 만듦"""
    fatal = next((i for i, x in enumerate(tail) if re.match(r"\s*(Fatal Python error|Windows fatal exception)", x)), None)
    if fatal is not None:                                    # faulthandler: 가장 최근 호출이 먼저
        fr = _frames(tail[fatal:])
        site = fr[0] if fr else None
        kind, content = "비정상 종료 (프로그램이 갑자기 죽음)", f"{tail[fatal].strip()} · {rc_text(rc)}"
    else:
        fr = _frames(tail)
        site = fr[-1] if fr else None
        last = next((x for x in reversed(tail) if x.strip() and not x.startswith("#")), "").strip()
        if re.match(r"[\w.]+(Error|Exception|Interrupt)\b", last):
            kind, content = last.split(":")[0].split(".")[-1], last
        else:
            kind, content = "카드 없이 끝남", f"카드 없이 끝남 ({rc_text(rc)})"
    code = error_code(script, *site) if site else f"E{prefix_of(script)}-??????"
    content = mask(_relpaths(content))
    card(code, stage or script, kind, content, _todo(kind, content, site, content=content))
    return code


def _prev_crash():
    """지난 단독 실행이 끝 줄 없이 끝났으면 (창을 닫았거나 갑자기 죽음) 한 줄 알림. faulthandler 글자가 있으면 그 자리의 오류 번호"""
    try:
        with open(LAST, encoding="utf-16") as fh:
            txt = fh.read()
    except Exception:
        return None
    if "# 기록 시작" not in txt or "\n# 끝:" in txt:
        return None
    m = re.search(r"# 기록 시작 [^·]*· (\S+)", txt)
    script = m.group(1) if m else "?"
    lg = re.search(r"· 로그 (\S+\.log)", txt)
    code = ""
    try:
        full = open(os.path.join(HERE, lg.group(1)), encoding="utf-8-sig", errors="replace").read().split("\n") if lg else []
        i = next((k for k, x in enumerate(full) if re.match(r"\s*(Fatal Python error|Windows fatal exception)", x)), None)
        if i is not None:
            fr = _frames(full[i:])
            code = f" · 갑자기 죽은 자리 오류 번호 {error_code(script, *fr[0])}" if fr else " · 갑자기 죽음 (우리 코드 밖)"
    except Exception:
        pass
    return f"(지난번 {script} 실행은 끝 줄 없이 끝남: 창을 닫았거나 프로그램이 갑자기 죽음{code})"


# ── 시작 ─────────────────────────────────────────────────
def _open_logs(script, sub, child):
    files, note, rel = [], "", ""
    base = os.path.splitext(script)[0] + (f"_{sub}" if sub else "")
    try:
        os.makedirs(LOGDIR, exist_ok=True)
        stamp = time.strftime("%Y%m%d_%H%M%S")
        path = os.path.join(LOGDIR, f"{stamp}_{base}.log")
        try:
            fh = open(path, "x", encoding="utf-8-sig", errors="backslashreplace")
        except FileExistsError:                              # 같은 초에 또 (예: --modes 로 빠른 단계가 연달아)
            path = os.path.join(LOGDIR, f"{stamp}_{base}_{os.getpid()}.log")
            fh = open(path, "w", encoding="utf-8-sig", errors="backslashreplace")
        files.append(fh)
        rel = os.path.relpath(path, HERE).replace(os.sep, "/")
    except Exception as e:
        note = f"(기록 파일을 못 만듦: {type(e).__name__} → 화면에만, 분석은 계속)"
    if not child:
        try:
            files.append(open(LAST, "w", encoding="utf-16", errors="backslashreplace"))    # cmd 의 type 이 코드페이지와 상관없이 읽음
        except Exception:
            pass
    return files, note, rel


def _report(e, kind_end, f, script, stage, msg):
    """except 블록 밖에서 부름 (보고 중 오류가 원래 오류를 덮지 않게)"""
    srel = _rel(f) or script
    inner, caller = _site(e.__traceback__, srel)
    if isinstance(e, SyntaxError) and getattr(e, "filename", None) and _rel(e.filename):
        inner, caller = (_rel(e.filename), e.lineno or 0), None
    if kind_end == "멈춤" and _STATE["stop_at"]:          # check: 멈춤을 모았다가 sys.exit(1)
        inner, caller = _STATE["stop_at"], None
    code = error_code(script, *inner) if inner else f"E{prefix_of(script)}-??????"
    _STATE["code"] = code
    where = (f"{inner[0]}:{inner[1]}" if inner else "모름")
    if caller and inner and inner[0].startswith("lib/"):
        stage = f"{stage} (부른 곳 {caller[0]}:{caller[1]})"
    if kind_end == "Ctrl+C":
        _filelog(masked_traceback(e, f))
        card(code, _STATE["stage"] or stage, "Ctrl+C 로 멈춤", f"{where} 에서 멈춤",
             _STATE["stage_todo"] or "같은 명령을 다시 (run_all 이면 python run_all.py --from <멈춘 번호>)")
        _filelog(f"# 멈춘 곳: {where}")
        return
    if kind_end.startswith("멈춤"):
        if msg:
            _raw(mask(msg).rstrip("\n") + "\n")             # 파이썬이 하던 것처럼 안내 글자를 화면에 (값 가림)
        if not _STATE["suppress"]:
            if msg:
                lines = [x for x in msg.split("\n") if x.strip()]
                arrow = next((x for x in lines if "→" in x), "")
                content = lines[0] if lines else ""
                todo = mask(arrow.split("→", 1)[1].strip()) if arrow else _todo("SystemExit", content, inner)
            elif _STATE["stop_txt"]:
                why, todo = _STATE["stop_txt"]
                n = _STATE["n_stop"]
                content = str(why or "") + (f" (외 {n - 1}건)" if n > 1 else "")
                todo = mask(str(todo or "위 화면의 → 안내대로"))
            else:
                content, todo = "(위 화면의 !! 줄)", "위 화면의 → 안내대로"
            card(code, stage, "멈춤 (안내)", mask(_relpaths(content)), todo)
        _filelog(f"# 멈춘 곳: {where}")
        return
    _raw(masked_traceback(e, f))
    if not _STATE["suppress"]:
        kind = type(e).__name__
        content = mask(_relpaths(f"{kind}: {e}".split("\n")[0]))
        line = f"{kind}: {e}"
        card(code, stage, kind, content, _todo(kind, line, inner, e, content))
    _filelog(f"# 오류 위치: {where}" if inner else "# 오류 위치: 우리 코드 밖")


def start(g):
    """진입점 맨 위에서. 기록 장치 안에서 이 스크립트를 다시 실행하고, 끝나면 종료 코드로 나감 (돌아오지 않음)"""
    global _ACTIVE
    if _ACTIVE or g.get("__name__") != "__main__":
        return
    f = g.get("__file__")
    if not f or not sys.argv or os.path.abspath(f) != os.path.abspath(sys.argv[0]):
        return                                          # QGIS 콘솔 exec 등
    _ACTIVE = True
    import runpy
    script = os.path.basename(f)
    child = bool(os.environ.get("HBI_RUNLOG_CHILD"))
    sub = os.environ.get("HBI_SUBRUN")
    stage = script + (f" [방식 {sub}]" if sub else "")
    prev = None if child else _prev_crash()             # 마지막.log 를 새로 쓰기 전에 읽음
    files, note, logrel = _open_logs(script, sub, child)
    _STATE.update(t0=time.time(), script=script, files=files)
    _filelog(f"# 기록 시작 {time.strftime('%Y-%m-%d %H:%M:%S')} · {script} {' '.join(sys.argv[1:])} · {_version()} · "
             f"Python {sys.version.split()[0]} ({sys.executable}) · 폴더 {HERE} · {_mem_txt()}"
             + (f" · 방식 {sub}" if sub else "") + (" · run_all 이 부름" if child else "") + (f" · 로그 {logrel}" if logrel else ""))
    old_out, old_err = sys.stdout, sys.stderr
    sys.stdout, sys.stderr = _Tee(old_out, files), _Tee(old_err, files, masked=True)
    for x in (note, prev):
        if x:
            _raw(x + "\n")
    try:                                                # C 코드 충돌(세그폴트·접근 위반) 때 파이썬 줄 위치를 남김
        import faulthandler
        faulthandler.enable(file=old_err if (child or not logrel) else files[0])
    except Exception:
        pass
    rc, kind_end, exc, msg = 0, "정상", None, None
    try:
        runpy.run_path(f, run_name="__main__")
    except SystemExit as e:
        c = e.code
        if c is None or c == 0:
            rc = 0
        elif isinstance(c, int):
            rc, kind_end, exc = c, "멈춤", e
        else:
            rc, kind_end, exc, msg = 1, "멈춤 (안내)", e, str(c)
    except KeyboardInterrupt as e:
        rc, kind_end, exc = 130, "Ctrl+C", e
    except BaseException as e:
        rc, kind_end, exc = 1, "오류", e
    try:
        if exc is not None:
            _report(exc, kind_end, f, script, stage, msg)
    except KeyboardInterrupt:
        rc, kind_end = 130, kind_end + " (카드를 내는 중 Ctrl+C)"
    except BaseException as e2:
        try:
            old_err.write(f"\n(카드를 만들다 {type(e2).__name__} · 오류 번호 {_STATE['code'] or '모름'} · 종료 코드 {rc})\n")
        except Exception:
            pass
    try:
        for t in (sys.stdout, sys.stderr):                 # 줄바꿈 없이 남은 글자도 로그에
            if isinstance(t, _Tee):
                t.end()
        sec = round(time.time() - _STATE["t0"])
        g_ = _STATE["gdal"]
        end = (f"# 끝: {kind_end} ({rc_text(rc)}) · 걸린 시간 {sec // 60}분 {sec % 60}초 · {_mem_txt()}"
               + (f" · GDAL 경고 {g_[0]}줄 (화면 생략 {g_[1]})" if g_[0] else ""))
        _filelog(f"{end} · 설정: {_config_summary()}")
        if child:                                          # run_all 이 단계별 최대 메모리를 읽음
            try:
                old_out.write(end + "\n")
                old_out.flush()
            except Exception:
                pass
    except BaseException:
        pass
    sys.stdout, sys.stderr = old_out, old_err
    try:
        import faulthandler
        faulthandler.disable()
    except Exception:
        pass
    for fh in files:
        try:
            fh.close()
        except Exception:
            pass
    sys.exit(rc)
