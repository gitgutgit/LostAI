"""Build the demo script reading page from demo_script.json.

Author: ProfessionalSeaweedDevourer (주현)
Usage:
  python3 docs/demo/build.py                 # writes docs/demo/demo_script.html
  python3 docs/demo/build.py --fragment OUT  # body-only page (no doctype/head), for hosted viewers
Standard library only. Edit demo_script.json, then rebuild; do not hand-edit the HTML.
"""
import html
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
E = html.escape


def mmss(s):
    return f"{s // 60}:{s % 60:02d}"


def doc_seconds(scenes):
    total = 0
    for sc in scenes:
        if sc["doc"] == "yes":
            total += sc["t"][1] - sc["t"][0]
        elif sc["doc"] == "partial":
            total += sc.get("doc_sec", 0)
    return total


def chip(d, spk):
    s = d["speakers"][spk]
    return f'<span class="spk c-{s["color"]}">{E(spk)} <small>{E(s["ko"])}</small></span>'


def judg_badges(nums):
    return "".join(f'<a class="pend" href="#j{n}" title="판정 {n}번 대기">판정 {n}</a>' for n in nums)


def timeline(d):
    total = d["scenes"][-1]["t"][1]
    segs = []
    for sc in d["scenes"]:
        a, b = sc["t"]
        w = (b - a) / total * 100
        dot = '<i class="tl-dot" title="판정 대기"></i>' if sc["judg"] else ""
        segs.append(
            f'<a class="tl-seg doc-{sc["doc"]}" style="width:{w:.3f}%" href="#{sc["id"]}">'
            f'<span class="tl-t">{a}~{b}</span><span class="tl-n">{E(sc["title"])}</span>{dot}</a>'
        )
    take = d["take_start"]
    return (
        '<div class="tl-wrap"><div class="tl">' + "".join(segs) + "</div>"
        f'<div class="tl-take" style="left:{take / total * 100:.3f}%;width:{(90 - take) / total * 100:.3f}%">연속 테이크 6~90초</div></div>'
        '<p class="legend"><span class="lg doc-yes"></span>문서가 보임 <span class="lg doc-partial"></span>일부 '
        '<span class="lg doc-no"></span>안 보임 <i class="tl-dot static"></i>판정 대기</p>'
    )


def line_cards(d):
    scenes = {s["id"]: s for s in d["scenes"]}
    out = []
    for i, ln in enumerate(d["lines"]):
        sc = scenes[ln["scene"]]
        cue = f'<p class="cue">{E(ln["cue"])}</p>' if ln.get("cue") else ""
        src = E(ln["src"])
        if ln.get("src_ko"):
            src += f' <span class="src-ko">{E(ln["src_ko"])}</span>'
        out.append(
            f'<article class="line" id="line-{E(ln["id"])}" data-spk="{E(ln["speaker"])}" data-i="{i}">'
            f'<header><b class="tid">{E(ln["id"])}</b>{chip(d, ln["speaker"])}'
            f'<a class="scene-ref" href="#{sc["id"]}">{sc["t"][0]}~{sc["t"][1]}초 {E(sc["title"])}</a>'
            f'<button type="button" class="read-here" data-i="{i}">여기서 읽기</button></header>'
            f'<p class="say" lang="en">{E(ln["text"])}</p>{cue}'
            f'<dl><dt>화면</dt><dd>{E(ln.get("result", ""))}</dd><dt>op</dt><dd><code>{E(ln["op"])}</code></dd>'
            f'<dt>출처</dt><dd>{src}</dd></dl></article>'
        )
    return "\n".join(out)


def storyboard(d):
    rows = []
    for sc in d["scenes"]:
        tags = "".join(f'<span class="tag">{E(r)}</span>' for r in sc["repo"])
        docl = {"yes": "예", "no": "아니오", "partial": f'일부(약 {sc.get("doc_sec", 0)}초)'}[sc["doc"]]
        rows.append(
            f'<tr id="{sc["id"]}"><td class="num">{sc["t"][0]}~{sc["t"][1]}</td>'
            f'<td><b>{E(sc["title"])}</b> {judg_badges(sc["judg"])}<br>{E(sc["screen"])}</td>'
            f'<td lang="en" class="cap">{E(sc["caption"])}</td><td>{tags}</td><td>{docl}</td></tr>'
        )
    return (
        '<div class="tbl"><table><thead><tr><th>초</th><th>화면</th><th>자막</th><th>리포 우선순위</th><th>문서</th></tr></thead><tbody>'
        + "".join(rows) + "</tbody></table></div>"
    )


def simple_table(head, rows, cls=""):
    th = "".join(f"<th>{E(h)}</th>" for h in head)
    body = "".join("<tr>" + "".join(f"<td>{c}</td>" for c in r) + "</tr>" for r in rows)
    return f'<div class="tbl"><table class="{cls}"><thead><tr>{th}</tr></thead><tbody>{body}</tbody></table></div>'


def references(d):
    out = [f'<p class="note">{E(d["ref_note"])}</p>']
    for g in d["references"]:
        items = []
        for it in g["items"]:
            st = it["status"]
            stc = {"현행": "ok", "델타": "ok", "일부 승계": "mid", "참고": "ref", "대체됨": "old"}.get(st, "ref")
            if it.get("url"):
                name = f'<a href="{E(it["url"])}" target="_blank" rel="noopener">{E(it["path"])}</a>'
            else:
                name = f'<code class="path">{E(it["path"])}</code>'
            items.append(f'<li><span class="st st-{stc}">{E(st)}</span><div>{name}<p>{E(it["what"])}</p></div></li>')
        out.append(f'<h3>{E(g["group"])}</h3><ul class="refs">{"".join(items)}</ul>')
    return "".join(out)


def page(d):
    sc_by = {s["id"]: s for s in d["scenes"]}
    ds = doc_seconds(d["scenes"])
    bluf = "".join(f"<li>{E(b)}</li>" for b in d["bluf"])
    spk_btns = '<button type="button" class="f on" data-f="">전체</button>' + "".join(
        f'<button type="button" class="f" data-f="{E(k)}">{E(k)} {E(v["ko"])}</button>'
        for k, v in d["speakers"].items() if k != "ALL"
    )
    cast = "".join(
        f'<li>{chip(d, k)} {E(v["role"])}</li>' for k, v in d["speakers"].items() if k != "ALL"
    )
    judg = "".join(
        f'<li id="j{j["n"]}"><b>{j["n"]}</b><div><p>{E(j["q"])}</p><p class="def">기본값: {E(j["default"])}</p></div></li>'
        for j in d["judgments"]
    )
    fb = simple_table(["빠지는 것", "대체 장면", "잃는 것"], [[E(f["miss"]), E(f["alt"]), E(f["loss"])] for f in d["fallbacks"]])
    ck = simple_table(["번호", "무엇", "통과 조건과 결과", "언제"], [[f'<b>{E(c["id"])}</b>', E(c["what"]), E(c["pass"]), E(c["when"])] for c in d["checks"]])
    v6 = simple_table(["항목", "v0.2", "v0.3 첫 판"], [[E(a), f'<span class="num">{E(b)}</span>', f'<span class="num">{E(c)}</span>'] for a, b, c in d["v6"]["rows"]], "narrow")
    ev = simple_table(["항목", "내용"], [[E(a), E(b)] for a, b in d["event"]])
    jd = simple_table(["심사위원", "소속", "볼 것(추론 포함)"], [[f'<b>{E(j["name"])}</b>', E(j["org"]), E(j["sees"])] for j in d["judges"]])
    fq = simple_table(["질문", "답하는 장면", "화면"], [[f'<span lang="en">{E(q["q"])}</span>', f'<a href="#{q["scene"]}">{sc_by[q["scene"]]["t"][0]}~{sc_by[q["scene"]]["t"][1]}초 {E(sc_by[q["scene"]]["title"])}</a>', E(q["a"])] for q in d["four_questions"]])
    reader_data = json.dumps(
        {
            "take": d["take_start"],
            "speakers": d["speakers"],
            "scenes": {s["id"]: {"t": s["t"], "title": s["title"]} for s in d["scenes"]},
            "lines": d["lines"],
        },
        ensure_ascii=False,
    ).replace("</", "<\\/")
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
  <p class="eyebrow">c0mpiled-17 Seoul 제출 영상</p>
  <h1>{E(d["title"])}</h1>
  <p class="meta"><span class="pill">{E(d["status"])}</span> {E(d["version"])}, {E(d["author"])}</p>
  <blockquote lang="en">{E(d["one_liner"])}</blockquote>
  <nav class="toc"><a href="#script">대본</a><a href="#board">콘티</a><a href="#judg">판정 대기</a><a href="#fallback">막힐 때</a><a href="#check">검증</a><a href="#judges">심사진</a><a href="#refs">참고 자료</a></nav>
</header>

<section class="bluf"><h2>요약</h2><ul>{bluf}</ul>
<p class="stat"><b class="num">{ds}</b>초 / 120초 문서가 보임 <span class="sep"></span><b class="num">{len(d["lines"])}</b>개 대사와 공개 <span class="sep"></span><b class="num">{len(d["judgments"])}</b>건 판정 대기</p></section>

<section><h2>120초 흐름</h2>{timeline(d)}</section>

<section id="script"><h2>대본</h2>
<p class="lead">영어 원문으로 읽는다(LostAI eval/README.md 규칙). 오른쪽 아래 <b>읽기 모드</b>는 한 줄씩 크게 띄우고, 시계를 켜면 영상 시각과 장면 구간을 비교해 준다. 키보드: 스페이스나 오른쪽 화살표 다음, 왼쪽 화살표 이전, S 시계, Esc 닫기.</p>
<ul class="cast">{cast}</ul>
<p class="note">{E(d["cast_note"])}</p>
<div class="filters" role="group" aria-label="배역으로 강조">{spk_btns}</div>
<div class="lines">{line_cards(d)}</div>
<p class="note">{E(d["reading_note"])}</p>
</section>

<section id="board"><h2>콘티 (장면별)</h2>{storyboard(d)}</section>

<section id="judg"><h2>판정 대기</h2><p class="lead">대본과 콘티는 모두 기본값으로 그렸다. 판정이 바뀌면 demo_script.json을 고치고 다시 빌드한다.</p><ol class="judg">{judg}</ol></section>

<section id="fallback"><h2>12:00에 기능이 밀릴 때</h2><p class="lead">영상 길이는 그대로 두고 장면만 바꾼다.</p>{fb}</section>

<section id="check"><h2>판단 밖 검증</h2>{ck}<h3>맥락 없는 심사위원 판독(V6) 결과</h3>{v6}<p class="note">{E(d["v6"]["note"])}</p></section>

<section id="judges"><h2>심사진</h2>{ev}{jd}<h3>Merlin Kafka의 네 질문과 답하는 장면</h3>{fq}</section>

<section id="refs"><h2>참고 자료</h2>{references(d)}</section>

<footer class="foot">원천 {E(d["plan_path"])}. 이 페이지는 LostAI docs/demo/build.py가 demo_script.json에서 만든다.</footer>
</main>

<div id="reader" class="reader" hidden role="dialog" aria-modal="true" aria-label="읽기 모드">
  <div class="r-top"><span id="r-clock" class="num">테이크 0:00 / 영상 0:06</span><span id="r-scene"></span><span id="r-pos" class="num"></span><button type="button" id="r-close">닫기</button></div>
  <div class="r-body"><p id="r-prev" class="r-side"></p><div id="r-cur"></div><p id="r-next" class="r-side"></p></div>
  <div class="r-bot"><button type="button" id="r-back">이전</button><button type="button" id="r-timer">시계 시작</button><button type="button" id="r-reset">처음부터</button><button type="button" id="r-fwd" class="primary">다음</button></div>
  <ol id="r-log" class="r-log"></ol>
</div>
<button type="button" id="open-reader" class="fab">읽기 모드</button>
<script id="reader-data" type="application/json">{reader_data}</script>
<script>{js}</script>
"""


def main():
    with open(os.path.join(HERE, "demo_script.json"), encoding="utf8") as f:
        d = json.load(f)
    body = page(d)
    if len(sys.argv) == 3 and sys.argv[1] == "--fragment":
        out, text = sys.argv[2], body
    else:
        out = os.path.join(HERE, "demo_script.html")
        text = '<!doctype html>\n<html lang="ko">\n<head>\n<meta charset="utf-8">\n<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">\n' + body.replace("<main", "</head>\n<body>\n<main", 1) + "</body>\n</html>\n"
    with open(out, "w", encoding="utf8") as f:
        f.write(text)
    print(out, len(text), "bytes,", doc_seconds(d["scenes"]), "doc-visible seconds")


if __name__ == "__main__":
    main()
