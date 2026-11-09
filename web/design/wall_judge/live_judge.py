"""실시간 결정 벽 판정: 서버 /api/state 와 브라우저 DOM(#rows, #said, #count, #log)이 같은지 칸 단위로 대조."""
import asyncio, json, re, subprocess, sys, html
import httpx, websockets
B = "http://localhost:8001"; UI = "http://localhost:5175"
SP = sys.argv[1]
LINES = [("Ines", "불안정한 결제 테스트 티켓 하나 추가해 줘"), ("Owen", "결제 테스트가 불안정한 게 리스크야"),
         ("Ravi", "점심 뭐 먹지"), ("Ines", "SSO 로그인 티켓 추가해 줘"), ("Owen", "방금 거 취소해 줘"), ("Ravi", "로그 정리 티켓 추가해 줘")]
CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"

async def speak():
    httpx.post(B + "/api/reset")
    toks = {n: httpx.post(B + "/api/join/manual", json={"name": n, "host": "judge"}).json()["token"] for n in {"Ines", "Owen", "Ravi"}}
    socks = {n: await websockets.connect(f"ws://localhost:8001/ws?token={t}") for n, t in toks.items()}
    for s in socks.values(): await s.recv()
    for who, text in LINES:
        await socks[who].send(json.dumps({"kind": "utterance.final", "payload": {"text": text}}))
        await asyncio.sleep(0.4)
    await asyncio.sleep(0.8)
    for s in socks.values(): await s.close()

def dom(url, shot):
    """Chrome 원격 디버깅으로 페이지를 열고 실제 시간 4초 기다린 뒤 DOM과 화면을 받는다."""
    import base64, time, random
    port = random.randint(9300, 9399)
    p = subprocess.Popen(["nice", "-n", "10", CHROME, "--headless=new", "--disable-gpu", "--hide-scrollbars", f"--user-data-dir={SP}/chrome",
                          "--force-device-scale-factor=1", "--window-size=1920,1140", f"--remote-debugging-port={port}", "about:blank"],
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        for _ in range(50):
            try:
                tabs = httpx.get(f"http://127.0.0.1:{port}/json").json(); break
            except Exception: time.sleep(0.2)
        ws_url = next(t for t in tabs if t["type"] == "page")["webSocketDebuggerUrl"]
        async def run():
            async with websockets.connect(ws_url, max_size=50_000_000) as ws:
                i = 0
                async def call(m, **params):
                    nonlocal i; i += 1; await ws.send(json.dumps({"id": i, "method": m, "params": params}))
                    while True:
                        r = json.loads(await ws.recv())
                        if r.get("id") == i: return r.get("result", {})
                await call("Page.navigate", url=url)
                await asyncio.sleep(4)
                html_ = (await call("Runtime.evaluate", expression="document.documentElement.outerHTML", returnByValue=True))["result"]["value"]
                png = (await call("Page.captureScreenshot", format="png"))["data"]
                open(shot, "wb").write(base64.b64decode(png))
                return html_
        return asyncio.run(run())
    finally:
        p.terminate(); p.wait()

def text(s): return html.unescape(re.sub(r"<[^>]+>", "", s)).strip()

asyncio.run(speak())
st = httpx.get(B + "/api/state").json()
state, changes = st["state"], {c["change_id"]: c for c in st["changes"]}
key, sheet = next((k, d) for k, d in state["docs"].items() if d["kind"] == "sheet")
d = dom(UI + "/?as=Judge", f"{SP}/live_wall.png")
rows_html = re.findall(r'<div class="g(?! colh)[^"]*"[^>]*>(.*?)</div>(?=<div class="g|</div></div></div>)', d, re.S)
fails, checks = [], 0
# 1) 행 수
checks += 1
if len(rows_html) != len(sheet["rows"]): fails.append(f"행 수: 서버 {len(sheet['rows'])} 화면 {len(rows_html)}")
# 2) 칸 값: 티켓, 제목, 담당, 추정, 상태
col = {"w": "티켓", "t": "제목", "o": "담당", "d": "추정", "st": "상태"}
for r, h in zip(sheet["rows"], rows_html):
    spans = re.findall(r"<span[^>]*>(.*?)</span>", h, re.S)
    cells = [text(x) for x in spans]
    # 순서: w, t, o, s, e, d, st, (src 안 칩들)
    got = {"w": cells[0], "t": cells[1], "o": cells[2], "d": cells[3], "st": cells[4]}  # 시작, 종료 열은 시트에 없어 숨김
    for k, c in col.items():
        checks += 1
        want = "" if r["cells"].get(c) is None else str(r["cells"][c])
        if not got[k].endswith(want): fails.append(f"{r['row_id']} {c}: 서버 '{want}' 화면 '{got[k]}'")
    # 3) 출처 칩 수 = 이 행을 마지막으로 바꾼 change 수 + 되돌림 칩
    cids = {cid for a, cid in state["provenance"].items() if a == f"{key}/{r['row_id']}" or a.startswith(f"{key}/{r['row_id']}/")}
    undo = sum(1 for c in changes.values() if c["status"] == "reverted" and any(t.startswith(f"{key}/{r['row_id']}") for t in c["targets"]))
    chips = len(re.findall(r'class="chip ', h)) - len(re.findall(r'class="chip tag', h))
    checks += 1
    if chips != len(cids) + undo: fails.append(f"{r['row_id']} 출처 칩: 서버 {len(cids)}+되돌림 {undo} 화면 {chips}")
# 4) 발화 줄 = 마지막 발화
checks += 1
said = text(re.search(r'<div id="said"[^>]*>(.*?)</div>', d, re.S).group(1))
if LINES[-1][1] not in said or f"L{len(LINES)}" not in said: fails.append(f"발화 줄: '{said}'")
# 5) 쓴 횟수 = applied/approved + reverted
checks += 1
n_ed = sum(1 for c in changes.values() if c["status"] in ("applied", "approved", "reverted"))
n_un = sum(1 for c in changes.values() if c["status"] == "reverted")
cnt = text(re.search(r'<span id="count"[^>]*>(.*?)</span>', d, re.S).group(1))
if f"{n_ed} edits written, {n_un} undone" not in cnt: fails.append(f"쓴 횟수: 서버 {n_ed}/{n_un} 화면 '{cnt}'")
print(json.dumps({"checks": checks, "fails": fails, "rows": len(sheet["rows"]), "changes": {s: sum(1 for c in changes.values() if c['status']==s) for s in ('applied','reverted','failed')}, "count": cnt, "said": said}, ensure_ascii=False, indent=1))
