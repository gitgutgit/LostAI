#!/bin/bash
# SVG를 회녹 벽색(#CDD6D0) 위 512 px로 Chrome 촬영, sips로 64, 32, 16 px 축소. 한 번에 Chrome 하나, nice 10.
# 인자(선택): render.sh <출력 폴더> <바탕색> <svg 접두>  예) render.sh png/props "#CDD6D0" moai_
cd "$(dirname "$0")"
OUT=${1:-png}; BG=${2:-#CDD6D0}; PRE=${3:-moai_}
mkdir -p "$OUT"
CH="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
TMP=$(mktemp -d)
for f in "$PRE"*.svg; do
  n=${f%.svg}; w=512; h=512
  case $n in moai_wordmark*) w=776; h=304;; esac
  printf '<html><body style="margin:0;background:%s"><img src="file://%s" style="width:%spx;height:%spx;display:block"></body></html>' "$BG" "$PWD/$f" $w $h > "$TMP/$n.html"
  nice -n 10 "$CH" --headless=new --disable-gpu --hide-scrollbars --allow-file-access-from-files --window-size=$w,$h --screenshot="$OUT/${n}_512.png" "file://$TMP/$n.html" >/dev/null 2>&1
  case $n in moai_wordmark*) continue;; esac
  for s in 64 32 16; do sips -z $s $s "$OUT/${n}_512.png" --out "$OUT/${n}_${s}.png" >/dev/null; done
done
rm -rf "$TMP"
ls "$OUT" | wc -l
