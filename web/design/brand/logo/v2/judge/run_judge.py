"""무맥락 판독. 기준(11:58 고정, 결과 보기 전): 3회 중 2회 이상이 아래 낱말군에 맞으면 통과.
그림은 저장소 밖 빈 임시 폴더에 무작위 이름으로 복사하고, 그 폴더에서 claude -p 를 띄운다. 동시 3개.
인자(선택): python3 run_judge.py <태그> [상태 ...]  ->  answers_<태그>.json, result_<태그>.txt, 그림은 png/<태그>/ 에서 읽는다.
인자 없이 돌리면 11:58 첫 판독과 같다(png/, answers.json)."""
import json, random, re, shutil, string, subprocess, sys, tempfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

HERE = Path(__file__).parent
PNG = HERE.parent / "png"
Q = ("Look at the image file {f}. This icon is the status light of a meeting assistant. "
     "In two words, what is it doing right now? Answer in English with the two words only.")
RUBRIC = {
    "listening": r"listen|hear|attentive|idle|standby|ready|waiting|monitor",
    "writing": r"writ|typ|record|note|transcrib|draft|document",
    "paused": r"paus|stop|question|confus|conflict|skeptic|doubt|hold|disagree|suspic|alert|puzzl|curious|halt",
    "vote-wig": r"vot|poll|ballot|decid|deliberat|judg|court|rul|session|adjudicat|verdict",
    "vote-frown": r"vot|poll|ballot|decid|deliberat|judg|think|consider|concentrat|focus|frown|disapprov|wait",
    "decided": r"approv|done|decid|confirm|agree|complet|finish|success|thumb|good|ok|accept|resolv|record",
}
SIZES = ["64", "32"]
RUNS = 3

TAG = sys.argv[1] if len(sys.argv) > 1 else ""
ONLY = sys.argv[2:] or list(RUBRIC)
SRC = PNG / TAG if TAG else PNG

def one(job):
    state, size, run, tmp = job
    name = "".join(random.choices(string.ascii_lowercase, k=8)) + ".png"
    dst = Path(tmp) / name
    shutil.copy(SRC / f"moai_{state}_{size}.png", dst)
    r = subprocess.run(["claude", "-p", Q.format(f=dst), "--model", "claude-sonnet-5-5", "--allowedTools", "Read"],
                       cwd=tmp, capture_output=True, text=True, timeout=180)
    ans = r.stdout.strip().splitlines()[-1] if r.stdout.strip() else "(no answer) " + r.stderr[-200:]
    hit = bool(re.search(RUBRIC[state], ans, re.I))
    return {"state": state, "size": size, "run": run, "answer": ans, "hit": hit}

def main():
    with tempfile.TemporaryDirectory(prefix="ic_", ignore_cleanup_errors=True) as tmp:
        jobs = [(s, z, k, tmp) for s in ONLY for z in SIZES for k in range(RUNS)]
        with ThreadPoolExecutor(3) as ex:
            rows = list(ex.map(one, jobs))
    sfx = f"_{TAG}" if TAG else ""
    (HERE / f"answers{sfx}.json").write_text(json.dumps(rows, ensure_ascii=False, indent=1))
    out = ["state       size  hits  answers"]
    for s in ONLY:
        for z in SIZES:
            rs = [r for r in rows if r["state"] == s and r["size"] == z]
            h = sum(r["hit"] for r in rs)
            out.append(f"{s:11s} {z:>4s}  {h}/{RUNS} {'PASS' if h >= 2 else 'fail'}  " + " | ".join(r["answer"] for r in rs))
    print("\n".join(out))
    if TAG:
        (HERE / f"result{sfx}.txt").write_text("\n".join(out) + "\n")

main()
