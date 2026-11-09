"""Build the demo video narration page from narration.json.

Author: ProfessionalSeaweedDevourer (주현)
Usage:
  python3 docs/demo/build.py                 # writes docs/demo/narration.html
  python3 docs/demo/build.py --fragment OUT  # body-only page (no doctype/head), for hosted viewers
Standard library only. Edit narration.json, then rebuild; do not hand-edit the HTML.
"""
import html
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
E = html.escape
SLOT = re.compile(r"\{([A-Z]+)\}")


def slots(text):
    """Escape text and mark {PLACEHOLDER} slots that still need a value."""
    return SLOT.sub(lambda m: f'<mark class="slot">{m.group(1)}</mark>', E(text))


def words(text):
    return len(SLOT.sub("xx yy", text).split())  # an empty slot counts as about two words


def cue_stats(c):
    sec = c["t"][1] - c["t"][0]
    w = words(c["en"])
    return sec, w, w / sec


def timeline(d):
    total = d["cues"][-1]["t"][1]
    segs = []
    for i, c in enumerate(d["cues"]):
        a, b = c["t"]
        label = "목소리" if c["kind"] == "vo" else "자막"
        segs.append(
            f'<a class="tl-seg k-{c["kind"]}" style="width:{(b - a) / total * 100:.3f}%" href="#cue-{i}" title="{a}~{b}초 {label}">'
            f'<span class="tl-t">{a}~{b}</span><span class="tl-n">{label}</span></a>'
        )
    return (
        '<div class="tl-wrap"><div class="tl">' + "".join(segs) + '</div>'
        f'<div class="tl-take" style="left:{6 / total * 100:.3f}%;width:{84 / total * 100:.3f}%">연속 테이크 6~90초</div></div>'
        '<p class="legend"><span class="lg k-vo"></span>Eric이 읽음(자막 같음) <span class="lg k-sub"></span>목소리 없이 자막만</p>'
    )


def cue_cards(d):
    out = []
    for i, c in enumerate(d["cues"]):
        sec, w, pace = cue_stats(c)
        fast = pace > d["pace_ok"]
        kind = "읽기" if c["kind"] == "vo" else "자막만"
        fill = "".join(f"<li>{E(f)}</li>" for f in c.get("fill", []))
        fill = f'<ul class="fill">{fill}</ul>' if fill else ""
        pace_txt = f'{w}단어, 초당 {pace:.1f}' if c["kind"] == "vo" else f'{sec}초 동안 띄움'
        out.append(
            f'<article class="cue k-{c["kind"]}" id="cue-{i}">'
            f'<header><b class="num">{c["t"][0]}~{c["t"][1]}초</b><span class="kind">{kind}</span>'
            f'<span class="scene">{E(c["scene"])}</span>'
            f'<span class="pace num{" fast" if fast else ""}">{pace_txt}</span></header>'
            f'<p class="en" lang="en">{slots(c["en"])}</p><p class="ko">{slots(c["ko"])}</p>{fill}'
            f'<button type="button" class="copy" data-text="{E(c["en"])}">자막 복사</button>'
            f'<button type="button" class="read-here" data-i="{i}">여기부터 읽기</button></article>'
        )
    return "\n".join(out)


def references(d):
    out = [f'<p class="note">{E(d["ref_note"])}</p>']
    for g in d["references"]:
        items = []
        for it in g["items"]:
            st = it["status"]
            stc = {"현행": "ok", "일부 승계": "mid"}.get(st, "ref")
            if it.get("url"):
                name = f'<a href="{E(it["url"])}" target="_blank" rel="noopener">{E(it["path"])}</a>'
            else:
                name = f'<code class="path">{E(it["path"])}</code>'
            items.append(f'<li><span class="st st-{stc}">{E(st)}</span><div>{name}<p>{E(it["what"])}</p></div></li>')
        out.append(f'<h3>{E(g["group"])}</h3><ul class="refs">{"".join(items)}</ul>')
    return "".join(out)


def page(d):
    vo = [c for c in d["cues"] if c["kind"] == "vo"]
    vo_sec = sum(c["t"][1] - c["t"][0] for c in vo)
    vo_words = sum(words(c["en"]) for c in vo)
    rules = "".join(f"<li>{E(r)}</li>" for r in d["rules"])
    pend = "".join(f"<li>{slots(p)}</li>" for p in d["pending"])
    data = json.dumps({"cues": d["cues"]}, ensure_ascii=False).replace("</", "<\\/")
    with open(os.path.join(HERE, "page.css"), encoding="utf8") as f:
        css = f.read()
    with open(os.path.join(HERE, "reader.js"), encoding="utf8") as f:
        js = f.read()
    return f"""<title>{E(d["title"])}</title>
<meta name="claude:viewport-fit-sides" content="cover">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=IBM+Plex+Sans+KR:wght@400;600;700&family=IBM+Plex+Mono:wght@400;600&display=swap">
<style>{css}</style>
<main class="wrap">
<header class="top">
  <p class="eyebrow">c0mpiled-17 Seoul 제출 영상 120초</p>
  <h1>{E(d["title"])}</h1>
  <p class="meta">{E(d["version"])}, {E(d["author"])}</p>
  <nav class="toc"><a href="#script">대본</a><a href="#pending">채울 것</a><a href="#refs">참고 자료</a></nav>
</header>

<section class="bluf"><h2>읽는 법</h2><ul>{rules}</ul>
<p class="stat"><b class="num">{len(vo)}</b>개 구간을 읽음 <span class="sep"></span><b class="num">{vo_sec}</b>초 동안 <b class="num">{vo_words}</b>단어 <span class="sep"></span>나머지 <b class="num">{120 - vo_sec}</b>초는 자막만</p>
<p class="note">오른쪽 아래 <b>읽기 모드</b>는 0초부터 120초까지 시계를 돌리며 지금 읽을 문장을 크게 띄운다. 스페이스 시작과 멈춤, 오른쪽 화살표 다음 읽기 구간, 왼쪽 화살표 이전 구간, Esc 닫기. 녹음할 때 영상 편집본을 같이 틀고 맞춰 읽는다.</p></section>

<section><h2>120초 흐름</h2>{timeline(d)}</section>

<section id="script"><h2>대본</h2><div class="cues">{cue_cards(d)}</div>
<p class="note">{E(d["card_text"])}</p></section>

<section id="pending"><h2>채울 것</h2><ul class="pend-list">{pend}</ul></section>

<section id="refs"><h2>참고 자료</h2>{references(d)}</section>

<footer class="foot">원천 {E(d["plan_path"])}. 이 페이지는 LostAI docs/demo/build.py가 narration.json에서 만든다.</footer>
</main>

<div id="reader" class="reader" hidden role="dialog" aria-modal="true" aria-label="읽기 모드">
  <div class="r-top"><span id="r-clock" class="num">0:00 / 2:00</span><span id="r-scene"></span><button type="button" id="r-close">닫기</button></div>
  <div class="r-bar"><i id="r-fill"></i></div>
  <div class="r-body"><p id="r-state" class="r-state"></p><p id="r-cur" class="r-say" lang="en"></p><p id="r-ko" class="r-ko"></p><p id="r-next" class="r-side"></p></div>
  <div class="r-bot"><button type="button" id="r-back">이전 구간</button><button type="button" id="r-reset">처음부터</button><button type="button" id="r-fwd">다음 읽기</button><button type="button" id="r-play" class="primary">시작</button></div>
</div>
<button type="button" id="open-reader" class="fab">읽기 모드</button>
<script id="cue-data" type="application/json">{data}</script>
<script>{js}</script>
"""


def main():
    with open(os.path.join(HERE, "narration.json"), encoding="utf8") as f:
        d = json.load(f)
    body = page(d)
    if len(sys.argv) == 3 and sys.argv[1] == "--fragment":
        out, text = sys.argv[2], body
    else:
        out = os.path.join(HERE, "narration.html")
        head = '<!doctype html>\n<html lang="ko">\n<head>\n<meta charset="utf-8">\n<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">\n'
        text = head + body.replace("<main", "</head>\n<body>\n<main", 1) + "</body>\n</html>\n"
    with open(out, "w", encoding="utf8") as f:
        f.write(text)
    for c in d["cues"]:
        if c["kind"] == "vo":
            sec, w, pace = cue_stats(c)
            flag = "  FAST" if pace > d["pace_ok"] else ""
            print(f'{c["t"][0]:>3}-{c["t"][1]:<3} {w:>2} words {pace:.1f} w/s{flag}')
    print(out)


if __name__ == "__main__":
    main()
