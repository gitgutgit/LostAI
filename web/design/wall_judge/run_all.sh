#!/usr/bin/env bash
# run_all.sh <app-base-url> [name]
#   app-base-url without band/hash, e.g. 'http://localhost:5173/?view=wall&shot'
#   (if it already has '{band}' / '{id}' it is used as a template as is).
#   Captures the app (22 PNGs) to <here>/<name>/ and diffs against <here>/ref (captured once by selftest.sh).
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
BASE="$1"; NAME="${2:-app}"
REFSRC="$HERE/../render_v04"
if [ ! -f "$HERE/ref/band1/s9.png" ]; then
  "$HERE/capture.sh" ref 'http://127.0.0.1:{port}/index.html?shot&band={band}#{id}' "$REFSRC"
fi
if [[ "$BASE" == *"{id}"* ]]; then TPL="$BASE"
else
  case "$BASE" in *\?*) sep='&';; *) sep='?';; esac
  TPL="${BASE}${sep}band={band}#{id}"
fi
probe="${TPL%%#*}"; probe="${probe//\{band\}/1}"
if ! curl -s -o /dev/null --max-time 5 "$probe"; then echo "ERROR: app not reachable at $probe"; exit 2; fi
"$HERE/capture.sh" "$NAME" "$TPL" || echo "(some captures failed, diffing what exists)"
cd "$HERE" && uv run --no-project --with pillow python -I diff.py "$HERE/ref" "$HERE/$NAME" "$HERE/out_$NAME"
