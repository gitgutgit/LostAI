"""MOAT 오독 대응 워드마크 후보(Eric 12:21). 판독 기준은 결과 전 고정: judge_wm.py 머리말.
v0 현행 | v1 눈썹을 두 눈으로 끊고 코를 뗌(가로대 제거) | v2 v1 + 석상 폭 80%
v3 v1 + 돌모자(푸카오, I의 위 세리프) | v4 v1 + 폭 80% + 돌모자"""
import subprocess, tempfile
from pathlib import Path

HERE = Path(__file__).parent
LETTERS = (
    '<path d="M0 60V4H12.5L20 29L27.5 4H40V60H30V27L23.5 47H16.5L10 27V60Z"/>'
    '<path fill-rule="evenodd" d="M63 4C72 4 80 10 80 20V44C80 54 72 60 63 60C54 60 46 54 46 44V20C46 10 54 4 63 4Z'
    'M63 15C60 15 58 17 58 20V44C58 47 60 49 63 49C66 49 68 47 68 44V20C68 17 66 15 63 15Z"/>'
    '<path fill-rule="evenodd" d="M95 4H113L124 60H113L111 48H97L95 60H84Z M98.5 38H109.5L104 13Z"/>'
)
HEAD = "M21 6H43Q45 6 45.3 8L48 46H16L18.7 8Q19 6 21 6Z"
HEAD_CAP = "M21 13H43Q45 13 45.2 15L48 46H16L18.8 15Q19 13 21 13Z"   # 돌모자 아래로 내린 머리
CAP = "M18.5 4H45.5Q47 4 47 5.5V9.5Q47 11 45.5 11H18.5Q17 11 17 9.5V5.5Q17 4 18.5 4Z"
BASE = "M11 60L15.5 48H48.5L53 60Z"
FACE_T = ["M22 17H42V22H22Z", "M29.5 22H34.5V33H29.5Z", "M26 38H38V41H26Z"]
FACE_SPLIT = ["M22.5 18H29.5V23H22.5Z", "M34.5 18H41.5V23H34.5Z", "M30 26H34V34H30Z", "M26 38H38V41H26Z"]
FACE_SPLIT_CAP = ["M22.5 21H29.5V26H22.5Z", "M34.5 21H41.5V26H34.5Z", "M30 28.5H34V35H30Z", "M26 39H38V42H26Z"]

VARIANTS = {
    "v0": (HEAD, FACE_T, False, 1.0),
    "v1": (HEAD, FACE_SPLIT, False, 1.0),
    "v2": (HEAD, FACE_SPLIT, False, 0.8),
    "v3": (HEAD_CAP, FACE_SPLIT_CAP, True, 1.0),
    "v4": (HEAD_CAP, FACE_SPLIT_CAP, True, 0.8),
}

def svg(head, face, cap, sx, fg):
    cuts = "".join(f'<path d="{d}"/>' for d in face)
    capp = f'<path d="{CAP}"/>' if cap else ""
    tf = f"translate(118 0) translate(32 0) scale({sx} 1) translate(-32 0)"
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 178 64" width="356" height="128">'
            f'<defs><mask id="w" maskUnits="userSpaceOnUse" x="0" y="0" width="64" height="64"><rect width="64" height="64" fill="#fff"/><g fill="#000">{cuts}</g></mask></defs>'
            f'<g fill="{fg}">{LETTERS}<g transform="{tf}"><g mask="url(#w)"><path d="{head}"/><path d="{BASE}"/></g>{capp}</g></g></svg>\n')

SURF = {"light": ("#CDD6D0", "#17212B"), "dark": ("#1c1917", "#d6d0c6")}
SIZES = [64, 24]   # 워드마크 높이 px: 64 큰 표기, 24 머리줄 작은 표기
CH = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"

def main():
    (HERE / "svg").mkdir(exist_ok=True); (HERE / "png").mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        for v, (head, face, cap, sx) in VARIANTS.items():
            for sname, (bg, fg) in SURF.items():
                f = HERE / "svg" / f"wm_{v}_{sname}.svg"; f.write_text(svg(head, face, cap, sx, fg))
                for h in SIZES:
                    w = round(h * 178 / 64) + 2 * (h // 2); H = h + 2 * (h // 2)
                    html = Path(tmp) / f"{v}_{sname}_{h}.html"
                    html.write_text(f'<html><body style="margin:0;background:{bg};display:flex;align-items:center;justify-content:center;width:{w}px;height:{H}px">'
                                    f'<img src="file://{f}" style="height:{h}px"></body></html>')
                    subprocess.run(["nice", "-n", "10", CH, "--headless=new", "--disable-gpu", "--hide-scrollbars", "--allow-file-access-from-files",
                                    f"--window-size={w},{H}", f"--screenshot={HERE}/png/wm_{v}_{sname}_{h}.png", f"file://{html}"],
                                   capture_output=True)
    print("ok", len(list((HERE / "png").glob("*.png"))), "png")

if __name__ == "__main__":
    main()
