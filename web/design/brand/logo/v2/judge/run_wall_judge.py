"""V5 실화면 무맥락 판독 (기획서 11-5절). 기준은 결과 보기 전 12:58에 고정한다.

- 그림: 결정 벽 앱 장면 촬영(wall_judge/app/band0/<장면>.png, 1920x1080)을 영상 해상도 1280x720으로 줄인 전체 화면.
  상태별 장면: 듣기 d1, 쓰기 r1, 엇갈림 멈춤 d2, 표결 s3, 결정 s8 (장면 표는 scenes.ts MOAI_OF).
- 조건 A(출시 그대로, 판정 대상): 마스코트 + 상태 단어가 보이는 화면.
- 조건 B(진단용, 판정 아님): 상태 단어 자리를 벽색으로 지운 화면. 그림 자체의 몫을 본다.
- 질문: 'This is a meeting assistant's screen. Look at the status figure at the top right. In two words,
  what is the assistant doing right now?' 상태와 조건마다 3회, 낱말군은 run_judge.py RUBRIC(11:58 고정, 표결은 vote-wig).
- 통과: 3회 중 2회 이상. 목표: 조건 A에서 다섯 상태 모두.
- 무작위 이름 사본, 저장소 밖 빈 임시 폴더, claude-sonnet-5-5, 동시 3개.
python3 run_wall_judge.py  ->  answers_wall.json, result_wall.txt, 그림은 png/wall/ 에 남긴다.

13:10 재판독(Eric 13:07, 마스코트를 오른쪽 위에서 글자판 9칸 바로 옆으로 옮김, 상태 단어 없음). 결과 전 고정:
python3 run_wall_judge.py flap  ->  answers_wall_flap.json, result_wall_flap.txt. 조건 A만, 질문은 Q_FLAP,
낱말군과 통과 기준은 위와 같다. 조건 B(단어 지움)는 단어가 없어 뜻이 없으므로 뺀다."""
import json, random, re, shutil, string, subprocess, sys, tempfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from PIL import Image

HERE = Path(__file__).parent
SHOTS = HERE.parents[3] / "wall_judge" / "app" / "band0"  # web/design/wall_judge/app/band0
OUT = HERE.parent / "png" / ("wall_flap" if len(sys.argv) > 1 and sys.argv[1] == "flap" else "wall")
SCENE = {"listening": "d1", "writing": "r1", "paused": "d2", "vote": "s3", "decided": "s8"}
RUBRIC_KEY = {"vote": "vote-wig"}
src = (HERE / "run_judge.py").read_text()
RUBRIC = eval(re.search(r"RUBRIC = (\{.*?\n\})", src, re.S).group(1))
Q = ("Look at the image file {f}. This is a meeting assistant's screen. Look at the status figure at the top right. "
     "In two words, what is the assistant doing right now? Answer in English with the two words only.")
RUNS = 3
FLAP = len(sys.argv) > 1 and sys.argv[1] == "flap"
Q_FLAP = ("Look at the image file {f}. This is a meeting assistant's screen. Look at the small statue figure right next to "
          "the big letter board. In two words, what is the assistant doing right now? Answer in English with the two words only.")
WALL = (0xCD, 0xD6, 0xD0)

def is_ink(p):  # statue is --ink #17212B; the word is --ink2 #4A5762
    return abs(p[0] - 0x17) < 18 and abs(p[1] - 0x21) < 18 and abs(p[2] - 0x2B) < 18

def prepare():
    OUT.mkdir(parents=True, exist_ok=True)
    for state, sc in SCENE.items():
        im = Image.open(SHOTS / f"{sc}.png").convert("RGB")
        im.resize((1280, 720), Image.LANCZOS).save(OUT / f"A_{state}.png")
        # B: find the statue's right edge in the header band (x >= 1500, y 14..76), then paint the word area
        px = im.load(); cols = [x for x in range(1500, 1910) if any(is_ink(px[x, y]) for y in range(14, 76))]
        right = max(cols) if cols else 1700
        b = im.copy(); b.paste(WALL, (right + 6, 8, 1916, 86))
        b.resize((1280, 720), Image.LANCZOS).save(OUT / f"B_{state}.png")
        print(state, sc, "statue right edge", right)

def one(job):
    cond, state, run, tmp = job
    dst = Path(tmp) / ("".join(random.choices(string.ascii_lowercase, k=8)) + ".png")
    shutil.copy(OUT / f"{cond}_{state}.png", dst)
    r = subprocess.run(["claude", "-p", (Q_FLAP if FLAP else Q).format(f=dst), "--model", "claude-sonnet-5-5", "--allowedTools", "Read"],
                       cwd=tmp, capture_output=True, text=True, timeout=180)
    ans = r.stdout.strip().splitlines()[-1] if r.stdout.strip() else "(no answer) " + r.stderr[-200:]
    return {"cond": cond, "state": state, "run": run, "answer": ans,
            "hit": bool(re.search(RUBRIC[RUBRIC_KEY.get(state, state)], ans, re.I))}

def main():
    prepare()
    if "--prepare" in sys.argv: return
    with tempfile.TemporaryDirectory(prefix="ic_", ignore_cleanup_errors=True) as tmp:
        jobs = [(c, s, k, tmp) for c in ("A" if FLAP else "AB") for s in SCENE for k in range(RUNS)]
        with ThreadPoolExecutor(3) as ex:
            rows = list(ex.map(one, jobs))
    (HERE / f"answers_wall{'_flap' if FLAP else ''}.json").write_text(json.dumps(rows, ensure_ascii=False, indent=1))
    out = ["cond state      hits  answers"]
    for c in ("A" if FLAP else "AB"):
        for s in SCENE:
            rs = [r for r in rows if r["cond"] == c and r["state"] == s]
            h = sum(r["hit"] for r in rs)
            out.append(f"{c}    {s:10s} {h}/{RUNS} {'PASS' if h >= 2 else 'fail'}  " + " | ".join(r["answer"] for r in rs))
    print("\n".join(out)); (HERE / f"result_wall{'_flap' if FLAP else ''}.txt").write_text("\n".join(out) + "\n")

main()
