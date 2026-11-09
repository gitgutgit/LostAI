"""다크 바탕 밝기 측정(외부 판정). 512 px 렌더에서 화소마다 바탕 대비 APCA Lc 를 구해 센다.
기준(조사 12:20): 큰 요소 다크 상한 |Lc| 90, 단색 아이콘 하한 30, 세부 그림 45.
사용: python3 dark_measure.py <폴더> [<폴더> ...]   (예: ../png/before ../png/dark)"""
import sys
from pathlib import Path
from PIL import Image
sys.path.insert(0, str(Path(__file__).parent))
from apca import lc

BG = "#1c1917"
STATES = ["listening", "writing", "paused", "vote-wig", "vote-frown", "decided"]

def stats(png):
    im = Image.open(png).convert("RGB").resize((128, 128))
    cache, over90, over75, fig, tot = {}, 0, 0, 0, 0.0
    for px in im.getdata():
        h = "#%02x%02x%02x" % px
        v = cache.get(h)
        if v is None: v = cache[h] = abs(lc(BG, h))
        if v >= 15: fig += 1; tot += v
        over90 += v > 90; over75 += v > 75
    n = 128 * 128
    return 100 * over90 / n, 100 * over75 / n, tot / max(fig, 1), tot / n

print(f"{'set':8s} {'state':11s} {'>90%':>6s} {'>75%':>6s} {'figLc':>6s} {'load':>6s}")
for d in sys.argv[1:]:
    rows = [stats(Path(d) / f"moai_{s}_512.png") for s in STATES]
    for s, r in zip(STATES, rows):
        print(f"{Path(d).name:8s} {s:11s} {r[0]:6.1f} {r[1]:6.1f} {r[2]:6.1f} {r[3]:6.1f}")
    m = [sum(c) / len(rows) for c in zip(*rows)]
    print(f"{Path(d).name:8s} {'MEAN':11s} {m[0]:6.1f} {m[1]:6.1f} {m[2]:6.1f} {m[3]:6.1f}")
