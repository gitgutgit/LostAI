#!/usr/bin/env bash
# selftest.sh: capture the reference twice (ref, ref2), diff them (noise floor),
# diff ref against the pre-existing render_v04/png/*.png, and a no-webfont control.
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
REFSRC="$HERE/../render_v04"
TPL='http://127.0.0.1:{port}/index.html?shot&band={band}#{id}'
cd "$HERE"
DIFF(){ uv run --no-project --with pillow python -I diff.py "$@"; }
rm -rf ref ref2 ref1x existing nofont coldfont
./capture.sh ref  "$TPL" "$REFSRC"
./capture.sh ref2 "$TPL" "$REFSRC"
# raw noise (single shot, no STABLE retry) to show what the retry guards against
STABLE=0 ./capture.sh ref1x "$TPL" "$REFSRC"
echo "== noise floor: ref vs ref2"; DIFF ref ref2 out_noise --no-images
# existing PNGs: <id>.png were taken with band off, band_<id>.png with band on
echo "== raw single-shot noise: ref vs ref1x (STABLE=0)"; DIFF ref ref1x out_noise1x --no-images | grep -v PASS
# render_v04/png/ is not in git (regenerated); skip this step when the export is absent
if compgen -G "$REFSRC/png/*.png" > /dev/null; then
  mkdir -p existing/band0 existing/band1
  for f in "$REFSRC"/png/*.png; do b=$(basename "$f" .png)
    case "$b" in features) ;; band_*) cp "$f" "existing/band1/${b#band_}.png";; *) cp "$f" "existing/band0/$b.png";; esac; done
  echo "== ref vs existing render_v04/png"; DIFF ref existing out_existing
else
  echo "== skip ref vs existing: no render_v04/png export"
fi
# controls use a cold profile so the HTTP cache cannot supply the webfonts
# (a) cold profile, fonts reachable: must match ref (fonts load within the virtual-time budget)
rm -rf .v04diff-cold-profile; PROFILE="$HERE/.v04diff-cold-profile" SCENES="s6 d1" BANDS="1" STABLE=0 ./capture.sh coldfont "$TPL" "$REFSRC"
echo "== cold profile vs ref (should PASS)"; DIFF ref coldfont out_coldfont --no-images | grep -vE '^(report|pass)'
# (b) cold profile, Google Fonts blocked: fallback fonts render, must FAIL clearly
rm -rf .v04diff-cold-profile; PROFILE="$HERE/.v04diff-cold-profile" SCENES="s6" BANDS="1" STABLE=0 \
  CHROME_EXTRA="--host-resolver-rules=MAP fonts.googleapis.com 127.0.0.1:9,MAP fonts.gstatic.com 127.0.0.1:9" \
  ./capture.sh nofont "$TPL" "$REFSRC"
echo "== no-webfont vs ref (should FAIL clearly)"; DIFF ref nofont out_nofont --no-images | grep -vE '^(report|pass)'
rm -rf .v04diff-cold-profile
