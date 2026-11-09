"""MOAI v2 SVG 생성기 (64 격자). 참조 시트를 따라 그리지 않고 같은 몸통에 얼굴 층만 바꾼다.

실행: python3 build.py  ->  같은 폴더에 SVG, png/ 아래 512 px 원본(Chrome 촬영은 render.sh).
상태 색(Eric 11:52 판정 3번): 듣기 초록, 쓰기 형광 노랑, 엇갈림 빨강, 표결 흰빛, 결정 진초록.
소품(Eric 12:16 정정: 판정 3의 기각은 소품을 없애자는 안의 기각): 듣기 헤드폰, 쓰기 연필, 결정 엄지. 크고 단순하게.
"""
from pathlib import Path

OUT = Path(__file__).parent
INK = "#17212B"

HEAD = "M21 6H43Q45 6 45.3 8L48 46H16L18.7 8Q19 6 21 6Z"
BASE = "M11 60L15.5 48H48.5L53 60Z"

FACES = {
    # 듣는 중: 기본 무표정 (눈썹과 코가 이어진 T, 입 막대)
    "neutral": ["M22 17H42V22H22Z", "M29.5 22H34.5V33H29.5Z", "M26 38H38V41H26Z"],
    # 쓰는 중: T 전체가 아래로(문서를 내려다봄), 입은 그대로
    "down": ["M23 22H41V26H23Z", "M29.5 26H34.5V34H29.5Z", "M26 38H38V41H26Z"],
    # 엇갈림 감지, 쓰기 멈춤: 오른쪽 눈썹만 올림
    "brow": ["M22 18H31V23H22Z", "M33 15.5L42 11.5L43.6 16L34.6 20Z", "M29.5 20H34.5V33H29.5Z", "M27 38H37V41H27Z"],
    # 표결 후보 B: 찌푸림(눈썹이 가운데로 내려옴), 입 좁힘
    "frown": ["M21 14.5L31.5 19V24L21 19.5Z", "M43 14.5L32.5 19V24L43 19.5Z", "M29.5 22H34.5V33H29.5Z", "M27.5 39H36.5V42H27.5Z"],
}

THUMB = "M45 41V31.5Q45 29 47.5 29H49Q51.5 29 51.5 31.5V41H55Q58 41 58 44V52Q58 55 55 55H44Q41 55 41 52V44Q41 41 44 41Z"
THUMB_CUTS = ["M41 45.5H52V47H41Z", "M41 49.5H52V51H41Z"]

# 듣기: 헤드폰. 귀덮개가 머리 옆을 살짝 파고들고 둘레에 틈(가면)을 둔다. 머리띠는 머리 위로 떠 있다.
PHONES_CUPS = ("M7 20.5Q7 17 10.5 17H14.5Q18.5 17 18.5 20.5V33.5Q18.5 37 14.5 37H10.5Q7 37 7 33.5Z"
               "M45.5 20.5Q45.5 17 49.5 17H53.5Q57 17 57 20.5V33.5Q57 37 53.5 37H49.5Q45.5 37 45.5 33.5Z")
PHONES_BAND = "M12.5 18V14Q12.5 2 32 2Q51.5 2 51.5 14V18"
# 쓰기: 연필 한 자루, 오른쪽 아래로 비스듬히(촉이 왼쪽 아래 받침을 향함). 지우개 띠와 깎은 촉 경계는 틈.
PENCIL = "M-4 -17H4V8L0 16L-4 8Z"
PENCIL_CUTS = ["M-4 -11.5H4V-9.5H-4Z", "M-4 7H4V9H-4Z"]
PENCIL_T = "translate(48.5 37) rotate(30)"

WIG_BACK = "".join(
    f'<circle cx="{x}" cy="{y}" r="5.6"/>' for x in (13.5, 50.5) for y in (17, 25.5, 34)
)
WIG_CAP = "M16 15Q15 3.5 32 3.5Q49 3.5 48 15Q44 11.5 40 13Q36 10 32 12.5Q28 10 24 13Q20 11.5 16 15Z"

STATES = {
    # 이름: (얼굴, 색, 소품)
    "listening": ("neutral", "#3FC27F", "phones"),
    "writing": ("down", "#F3C316", "pencil"),
    "paused": ("brow", "#B3261B", None),
    "vote-wig": ("neutral", "#FFFFFF", "wig"),
    "vote-frown": ("frown", "#FFFFFF", None),
    "decided": ("neutral", "#1E7B4F", "thumb"),
}


# 어두운 바탕판(앱 styles.css 의 #1c1917). 석상 자체를 상태 색으로 칠하고(등불), 번짐빛은 한 겹 45%.
# 상태 색은 APCA Lc -45 ~ -55 한 띠(judge/apca.py). 근거는 기획서 9절. moai.css 의 다크 묶음과 같은 값.
DARK_BG = "#1c1917"
DARK = {"listening": "#5cae82", "writing": "#c9a640", "paused": "#ec8273",
        "vote-wig": "#a598dc", "vote-frown": "#a598dc", "decided": "#4aa877"}
DARK_WIG = ("#c9c3ba", DARK_BG)
# 비교용 이전판: 밝은 글자색 몸통(#f5f5f4) + 밝은 바탕용 번짐빛
BEFORE_BODY = "#f5f5f4"


def glow_filter(fid: str, color: str, alpha: float = 1.0, double: bool = True) -> str:
    merge = '<feMergeNode in="g"/>' * (2 if double else 1)
    return (
        f'<filter id="{fid}" x="-40%" y="-40%" width="180%" height="180%">'
        '<feMorphology in="SourceAlpha" operator="dilate" radius="1.6" result="d"/>'
        '<feGaussianBlur in="d" stdDeviation="2.4" result="b"/>'
        f'<feFlood flood-color="{color}" flood-opacity="{alpha}" result="f"/>'
        '<feComposite in="f" in2="b" operator="in" result="g"/>'
        f'<feMerge>{merge}<feMergeNode in="SourceGraphic"/></feMerge>'
        "</filter>"
    )


def mascot(face: str, color: str | None, prop: str | None, ink: str = INK, dark: bool = False) -> str:
    cuts = "".join(f'<path d="{d}"/>' for d in FACES[face])
    hand_gap = {
        "thumb": f'<path d="{THUMB}" stroke="#000" stroke-width="5" stroke-linejoin="round"/>',
        "phones": f'<path d="{PHONES_CUPS}" stroke="#000" stroke-width="5"/>',
        "pencil": f'<path transform="{PENCIL_T}" d="{PENCIL}" stroke="#000" stroke-width="5" stroke-linejoin="round"/>',
    }.get(prop or "", "")
    defs = [f'<mask id="m"><rect width="64" height="64" fill="#fff"/><g fill="#000">{cuts}{hand_gap}</g></mask>']
    if color:
        defs.append(glow_filter("g", color, 0.45, False) if dark else glow_filter("g", color))
    body = [f'<g mask="url(#m)"><path d="{HEAD}"/><path d="{BASE}"/></g>']
    if prop == "wig":
        wf, wl = DARK_WIG if dark else ("#fff", "currentColor")
        body.insert(0, f'<g fill="{wf}" stroke="{wl}" stroke-width="2.4">{WIG_BACK}</g>')
        body.append(f'<path d="{WIG_CAP}" fill="{wf}" stroke="{wl}" stroke-width="2.4" stroke-linejoin="round"/>')
    if prop == "thumb":
        thumb_cuts = "".join(f'<path d="{d}"/>' for d in THUMB_CUTS)
        defs.append(f'<mask id="h"><rect width="64" height="64" fill="#fff"/><g fill="#000">{thumb_cuts}</g></mask>')
        body.append(f'<path d="{THUMB}" mask="url(#h)"/>')
    if prop == "phones":
        body.append(f'<path d="{PHONES_BAND}" fill="none" stroke="currentColor" stroke-width="4" stroke-linecap="round"/>')
        body.append(f'<path d="{PHONES_CUPS}"/>')
    if prop == "pencil":
        pc = "".join(f'<path d="{d}"/>' for d in PENCIL_CUTS)
        defs.append(f'<mask id="p" maskUnits="userSpaceOnUse" x="-30" y="-30" width="60" height="60"><rect x="-30" y="-30" width="60" height="60" fill="#fff"/><g fill="#000">{pc}</g></mask>')
        body.append(f'<g transform="{PENCIL_T}"><path d="{PENCIL}" mask="url(#p)"/></g>')
    filt = ' filter="url(#g)"' if color else ""
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64" width="64" height="64" color="{ink}">'
        f'<defs>{"".join(defs)}</defs><g fill="currentColor"{filt}>{"".join(body)}</g></svg>\n'
    )


# 워드마크: M, O, A 손그림 경로(굵은 좁은 글꼴 느낌) + I 자리 석상(Eric 11:52 판정 4번 확정)
# 얼굴은 두 눈 + 떨어진 코(가로대 없음). 이어진 눈썹과 코가 T로 읽혀 MOAT 오독(12:21), 판독 v1 채택(wordmark/).
FACE_WORDMARK = ["M22.5 18H29.5V23H22.5Z", "M34.5 18H41.5V23H34.5Z", "M30 26H34V34H30Z", "M26 38H38V41H26Z"]
LETTERS = (
    '<path d="M0 60V4H12.5L20 29L27.5 4H40V60H30V27L23.5 47H16.5L10 27V60Z"/>'
    '<path fill-rule="evenodd" d="M63 4C72 4 80 10 80 20V44C80 54 72 60 63 60C54 60 46 54 46 44V20C46 10 54 4 63 4Z'
    'M63 15C60 15 58 17 58 20V44C58 47 60 49 63 49C66 49 68 47 68 44V20C68 17 66 15 63 15Z"/>'
    '<path fill-rule="evenodd" d="M95 4H113L124 60H113L111 48H97L95 60H84Z M98.5 38H109.5L104 13Z"/>'
)


def wordmark(fg: str, bg: str | None) -> str:
    cuts = "".join(f'<path d="{d}"/>' for d in FACE_WORDMARK)
    plate = f'<rect x="-8" y="-6" width="194" height="76" rx="3" fill="{bg}"/>' if bg else ""
    return (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="-8 -6 194 76" width="388" height="152">'
        f'<defs><mask id="w"><rect x="0" y="0" width="64" height="64" fill="#fff"/><g fill="#000">{cuts}</g></mask></defs>'
        f'{plate}<g fill="{fg}">{LETTERS}<g transform="translate(118 0)"><g mask="url(#w)"><path d="{HEAD}"/><path d="{BASE}"/></g></g></g></svg>\n'
    )


# 파비콘: 16 px 단순판. 얼굴은 굵은 T 하나만, 받침은 몸통과 붙인다.
FAV = (
    '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64" width="64" height="64">'
    '<defs><mask id="f"><rect width="64" height="64" fill="#fff"/><g fill="#000">'
    '<path d="M20 16H44V24H20Z"/><path d="M28 24H36V38H28Z"/></g></mask></defs>'
    f'<g fill="{{c}}" mask="url(#f)"><path d="M19 3H45L49 48H15Z"/><path d="M7 62L13 46H51L57 62Z"/></g></svg>\n'
)


def main() -> None:
    for name, (face, color, prop) in STATES.items():
        (OUT / f"moai_{name}.svg").write_text(mascot(face, color, prop))
        (OUT / f"moai_{name}_plain.svg").write_text(mascot(face, None, prop))
        (OUT / f"dark_moai_{name}.svg").write_text(mascot(face, DARK[name], prop, DARK[name], dark=True))
        # before_moai_* (light statue with a glow on the dark page): rejected by Eric 2026-11-09 12:45, files in _rejected/
    (OUT / "moai_wordmark_ink.svg").write_text(wordmark(INK, None))
    (OUT / "moai_wordmark_reverse.svg").write_text(wordmark("#FFFFFF", INK))
    (OUT / "moai_favicon.svg").write_text(FAV.replace("{c}", INK))
    print("ok", len(list(OUT.glob("*.svg"))), "svg")


if __name__ == "__main__":
    main()
