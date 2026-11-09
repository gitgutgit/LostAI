"""워드마크 무맥락 판독(Eric 12:21, MOAT 오독). 기준(12:27 고정, 결과 보기 전):
답에서 영문자만 남겨 대문자로 바꾼 값이 MOAI 이면 맞음. 후보마다 바탕 2(light, dark) x 높이 2(64, 24 px) x 3회.
통과 = 네 칸 모두 3회 중 3회. 그림은 저장소 밖 빈 임시 폴더에 무작위 이름으로 복사, 동시 3개."""
import json, random, re, shutil, string, subprocess, sys, tempfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

HERE = Path(__file__).parent
Q = ("Look at the image file {f}. It is a logo wordmark. What word does it spell? "
     "Answer with the word only, in capital letters.")
VARIANTS = sys.argv[1:] or ["v0", "v1", "v2", "v3", "v4"]
CELLS = [(s, h) for s in ("light", "dark") for h in (64, 24)]
RUNS = 3

def one(job):
    v, s, h, k, tmp = job
    dst = Path(tmp) / ("".join(random.choices(string.ascii_lowercase, k=8)) + ".png")
    shutil.copy(HERE / "png" / f"wm_{v}_{s}_{h}.png", dst)
    r = subprocess.run(["claude", "-p", Q.format(f=dst), "--model", "claude-sonnet-5-5", "--allowedTools", "Read"],
                       cwd=tmp, capture_output=True, text=True, timeout=180)
    ans = r.stdout.strip().splitlines()[-1] if r.stdout.strip() else "(no answer)"
    return {"v": v, "surface": s, "h": h, "run": k, "answer": ans, "hit": re.sub(r"[^A-Za-z]", "", ans).upper() == "MOAI"}

def main():
    with tempfile.TemporaryDirectory(prefix="wm_", ignore_cleanup_errors=True) as tmp:
        jobs = [(v, s, h, k, tmp) for v in VARIANTS for s, h in CELLS for k in range(RUNS)]
        with ThreadPoolExecutor(3) as ex:
            rows = list(ex.map(one, jobs))
    (HERE / "answers_wm.json").write_text(json.dumps(rows, ensure_ascii=False, indent=1))
    out = []
    for v in VARIANTS:
        cells = []
        for s, h in CELLS:
            rs = [r for r in rows if r["v"] == v and r["surface"] == s and r["h"] == h]
            cells.append(f"{s}{h} {sum(r['hit'] for r in rs)}/{RUNS} [{', '.join(r['answer'] for r in rs)}]")
        ok = all(sum(r["hit"] for r in rows if r["v"] == v and r["surface"] == s and r["h"] == h) == RUNS for s, h in CELLS)
        out.append(f"{v} {'PASS' if ok else 'fail'} | " + " | ".join(cells))
    print("\n".join(out)); (HERE / "result_wm.txt").write_text("\n".join(out) + "\n")

main()
