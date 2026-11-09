"""Pixel diff of two capture trees.

uv run --no-project --with pillow python -I diff.py <refdir> <testdir> <outdir> [--thr 24] [--pass 0.5]

refdir/testdir hold band0/<id>.png, band1/<id>.png (or flat <id>.png; any *.png present in
both trees, matched by relative path). A pixel differs when its max RGB channel difference > thr.
A frame passes when differing pixels <= pass %. Writes outdir/report.json, outdir/diff/*.png
(test dimmed 30%, differing pixels red) and outdir/side/*.png (ref | test | diff).
"""
import json, sys, argparse
from pathlib import Path
from PIL import Image, ImageChops

ap = argparse.ArgumentParser()
ap.add_argument('ref'); ap.add_argument('test'); ap.add_argument('out')
ap.add_argument('--thr', type=int, default=24)
ap.add_argument('--pass', dest='passpct', type=float, default=0.5)
ap.add_argument('--no-images', action='store_true')
a = ap.parse_args()
ref, test, out = Path(a.ref), Path(a.test), Path(a.out)
out.mkdir(parents=True, exist_ok=True)

pairs = sorted(p.relative_to(ref) for p in ref.rglob('*.png'))
rows, missing = [], []
for rel in pairs:
    t = test / rel
    if not t.exists():
        missing.append(str(rel)); continue
    A = Image.open(ref / rel).convert('RGB'); B = Image.open(t).convert('RGB')
    size_ok = A.size == B.size
    if not size_ok:  # compare on ref canvas; out-of-bounds area counts as different
        C = Image.new('RGB', A.size, (255, 0, 255)); C.paste(B.crop((0, 0) + A.size), (0, 0)); B = C
    d = ImageChops.difference(A, B)
    r, g, b = d.split()
    mx = ImageChops.lighter(ImageChops.lighter(r, g), b)
    mask = mx.point(lambda v: 255 if v > a.thr else 0)
    n = A.size[0] * A.size[1]
    ndiff = mask.histogram()[255]
    hist = mx.histogram()
    mean_max = sum(i * c for i, c in enumerate(hist)) / n
    mean_abs = sum(sum(i * c for i, c in enumerate(ch.histogram())) for ch in (r, g, b)) / (3 * n)
    bbox = mask.getbbox()
    pct = 100.0 * ndiff / n
    key = str(rel.with_suffix('')).replace('/', '_')
    row = dict(frame=str(rel.with_suffix('')), diff_pct=round(pct, 4), diff_px=ndiff,
               mean_abs=round(mean_abs, 3), mean_maxch=round(mean_max, 3), bbox=bbox,
               size_ok=size_ok, test_size=list(Image.open(t).size), passed=pct <= a.passpct)
    if not a.no_images:
        dim = Image.blend(B, Image.new('RGB', A.size, (0, 0, 0)), 0.3)
        dim.paste((255, 0, 0), mask=mask)
        (out / 'diff').mkdir(exist_ok=True); (out / 'side').mkdir(exist_ok=True)
        dim.save(out / 'diff' / f'{key}.png')
        sb = Image.new('RGB', (A.size[0] * 3, A.size[1]), (255, 255, 255))
        sb.paste(A, (0, 0)); sb.paste(B, (A.size[0], 0)); sb.paste(dim, (2 * A.size[0], 0))
        sb.resize((sb.size[0] // 2, sb.size[1] // 2), Image.LANCZOS).save(out / 'side' / f'{key}.png')
        row['diff_png'] = str(out / 'diff' / f'{key}.png'); row['side_png'] = str(out / 'side' / f'{key}.png')
    rows.append(row)

rows.sort(key=lambda r: -r['diff_pct'])
npass = sum(r['passed'] for r in rows)
rep = dict(ref=str(ref), test=str(test), threshold_maxch=a.thr, pass_pct=a.passpct,
           frames=len(rows) + len(missing), passed=npass, missing=missing, rows=rows)
(out / 'report.json').write_text(json.dumps(rep, indent=1))
print(f'{"frame":<12}{"diff%":>9}{"diff_px":>10}{"meanAbs":>9}  bbox')
for r in rows:
    print(f'{r["frame"]:<12}{r["diff_pct"]:>9.3f}{r["diff_px"]:>10}{r["mean_abs"]:>9.3f}  '
          f'{"PASS" if r["passed"] else "FAIL"} {r["bbox"]}{"" if r["size_ok"] else " SIZE " + str(r["test_size"])}')
print(f'pass {npass}/{len(rows) + len(missing)} (<= {a.passpct}% px with maxch > {a.thr})'
      + (f'; MISSING in test (count as fail): {", ".join(missing)}' if missing else ''))
print(f'report: {out / "report.json"}')
