"""V6: the drawing constants in build.py (design canon) and Moai.tsx (app canon) must be the same strings.
python3 check_geometry.py <path to LostAI web/src/views/brand/Moai.tsx>"""
import re, sys, ast
from pathlib import Path

NAMES = ["HEAD", "BASE", "FACE_WORDMARK", "THUMB", "THUMB_CUTS", "PHONES_CUPS", "PHONES_BAND",
         "PENCIL", "PENCIL_CUTS", "PENCIL_T", "WIG_CAP"]
py = Path(__file__).with_name("build.py").read_text()
ts = Path(sys.argv[1]).read_text()

def norm(v):  # flatten a str or list of str
    return v if isinstance(v, str) else "|".join(v)

def py_val(n):
    m = re.search(rf"^{n} = (.+?)\n(?=[A-Z_#]|\n|def )", py, re.S | re.M)
    if not m: return None
    return norm(ast.literal_eval(m.group(1).strip()))

def ts_val(n):
    m = re.search(rf"^const {n} = (.+?);\n", ts, re.S | re.M)
    if not m: return None
    src = m.group(1).replace(" +\n", " + ").strip()
    src = re.sub(r'"\s*\+\s*"', "", src)  # join "a" + "b"
    return norm(ast.literal_eval(src))

bad = 0
for n in NAMES:
    a, b = py_val(n), ts_val(n)
    ok = a is not None and a == b
    bad += not ok
    print(("ok  " if ok else "DIFF"), n, "" if ok else f"\n  build.py: {a}\n  Moai.tsx: {b}")
print(f"{len(NAMES) - bad}/{len(NAMES)} equal")
sys.exit(1 if bad else 0)
