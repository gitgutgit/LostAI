#!/usr/bin/env bash
# capture.sh <name> <url-template> [serve-dir]
#   Captures 11 scenes x band 0/1 = 22 PNGs to <here>/<name>/band<b>/<id>.png
#   url-template placeholders: {id} {band} and, when serve-dir is given, {port}
#   serve-dir: folder served by python3 -m http.server on a free port (killed on exit).
#   Example (reference): ./capture.sh ref 'http://127.0.0.1:{port}/index.html?shot&band={band}#{id}' /path/render_v04
#   Example (app):       ./capture.sh app 'http://localhost:5173/?view=wall&shot&band={band}#{id}'
#   Env: SCENES="d1 s6" BANDS="0" to limit; CHROME_EXTRA="--flag1|--flag2" extra flags (| separated);
#        PROFILE=<dir> other Chrome user-data-dir (default .v04diff-chrome-profile, keeps font cache);
#        STABLE=0 to shoot once instead of until two identical shots.
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
NAME="$1"; TPL="$2"; SERVE="${3:-}"
CHROME="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
PROFILE="${PROFILE:-$HERE/.v04diff-chrome-profile}"
SCENES="${SCENES:-d1 d2 s2 s3 s4 s5 s6 s7 s8 r1 s9}"
BANDS="${BANDS:-0 1}"
SRV_PID=""
cleanup(){ set +e; if [ -n "$SRV_PID" ]; then kill "$SRV_PID" 2>/dev/null; wait "$SRV_PID" 2>/dev/null; SRV_PID=""; fi; }
trap cleanup EXIT
trap 'exit 130' INT TERM

if [ -n "$SERVE" ]; then
  PORT=$(python3 -c 'import socket;s=socket.socket();s.bind(("127.0.0.1",0));print(s.getsockname()[1]);s.close()')
  nice -n 10 python3 -m http.server "$PORT" --bind 127.0.0.1 --directory "$SERVE" >/dev/null 2>&1 &
  SRV_PID=$!
  for _ in $(seq 50); do curl -sf -o /dev/null "http://127.0.0.1:$PORT/" && break; sleep 0.1; done
  TPL="${TPL//\{port\}/$PORT}"
  echo "serving $SERVE on :$PORT (pid $SRV_PID)"
fi

EXTRA=(); [ -n "${CHROME_EXTRA:-}" ] && IFS='|' read -ra EXTRA <<< "$CHROME_EXTRA"
shoot(){ # shoot <url> <out>   one Chrome invocation (sequential, never parallel)
  rm -f "$2"
  nice -n 10 "$CHROME" --headless=new --disable-gpu --hide-scrollbars \
    --force-device-scale-factor=1 --window-size=1920,1080 --virtual-time-budget=4000 \
    --user-data-dir="$PROFILE" --no-first-run --no-default-browser-check \
    --disable-background-networking --disable-component-update --disable-sync \
    ${EXTRA[@]+"${EXTRA[@]}"} --screenshot="$2" "$1" >/dev/null 2>&1 || true
  [ -s "$2" ]
}
# STABLE=1 (default): shoot twice; if the PNGs differ (headless sometimes leaves a
# half-painted tile strip), shoot up to 3 more times and keep the first repeated result.
STABLE="${STABLE:-1}"
fail=0; TMPD="$HERE/.tmp_$NAME"; mkdir -p "$TMPD"
for b in $BANDS; do
  mkdir -p "$HERE/$NAME/band$b"
  for id in $SCENES; do
    url="${TPL//\{id\}/$id}"; url="${url//\{band\}/$b}"
    out="$HERE/$NAME/band$b/$id.png"; rm -f "$out"; note=""
    if ! shoot "$url" "$TMPD/0.png"; then echo "FAIL $NAME band$b $id (no png) $url"; fail=1; continue; fi
    if [ "$STABLE" = 1 ]; then
      got=""; n=1
      while [ -z "$got" ] && [ $n -le 4 ]; do
        shoot "$url" "$TMPD/$n.png" || true
        for k in $(seq 0 $((n-1))); do cmp -s "$TMPD/$k.png" "$TMPD/$n.png" && { got="$TMPD/$n.png"; break; }; done
        n=$((n+1))
      done
      if [ -z "$got" ]; then got="$TMPD/0.png"; note=" UNSTABLE(no two of $n shots equal)"; fail=1
      elif [ $n -gt 2 ]; then note=" (needed $n shots)"; fi
      mv "$got" "$out"
    else mv "$TMPD/0.png" "$out"; fi
    rm -f "$TMPD"/*.png
    dim=$(python3 -c 'import struct,sys;d=open(sys.argv[1],"rb").read(24);print("%dx%d"%struct.unpack(">II",d[16:24]))' "$out")
    if [ "$dim" != "1920x1080" ]; then echo "FAIL $NAME band$b $id size $dim"; fail=1; else echo "ok   $NAME band$b $id$note"; fi
  done
done
rmdir "$TMPD" 2>/dev/null || true
cleanup
exit $fail
