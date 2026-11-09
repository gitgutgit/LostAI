"""APCA-W3 0.0.98G 대비(Lc). 사용: python3 apca.py <바탕> <색> [색 ...]
기준(조사 12:20): 단색 아이콘 하한 Lc 30, 다크 모드 큰 요소 상한 Lc -90(절댓값 90)."""
import sys

def Y(h):
    h = h.lstrip("#"); r, g, b = (int(h[i:i + 2], 16) / 255 for i in (0, 2, 4))
    y = 0.2126729 * r ** 2.4 + 0.7151522 * g ** 2.4 + 0.0721750 * b ** 2.4
    return y + (0.022 - y) ** 1.414 if y < 0.022 else y

def lc(bg, fg):
    yb, yt = Y(bg), Y(fg)
    if abs(yb - yt) < 0.0005: return 0.0
    if yb > yt:
        s = (yb ** 0.56 - yt ** 0.57) * 1.14; return 0.0 if s < 0.1 else (s - 0.027) * 100
    s = (yb ** 0.65 - yt ** 0.62) * 1.14; return 0.0 if s > -0.1 else (s + 0.027) * 100

if __name__ == "__main__":
    bg = sys.argv[1]
    for c in sys.argv[2:]: print(f"{c}  Lc {lc(bg, c):6.1f}")
