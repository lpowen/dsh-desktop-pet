# -*- coding: utf-8 -*-
"""
生成桌宠精灵图（纯 PIL 绘制，无外部素材）。

思路：3 倍超采样绘制 → 降采样 → 以 KEY 色为底做二值抠图，
这样 Tk 的 -transparentcolor 抠图不会出现彩色毛边。
生成结果在 assets/ 下，可随时用自己的 PNG 覆盖（同尺寸、同 KEY 底色）。
"""
from PIL import Image, ImageDraw
import os

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets")
os.makedirs(OUT, exist_ok=True)

W, H = 240, 280
SS = 3
KEY = (255, 0, 254)  # 抠图色，画面里不要用这个颜色

HAIR = (74, 63, 107)
HAIR_HI = (107, 95, 150)
SKIN = (255, 227, 211)
SKIN_SH = (238, 197, 178)
DRESS = (47, 53, 80)
DRESS_HI = (72, 82, 122)
WHITE = (247, 247, 252)
GOLD = (255, 209, 102)
PINK = (255, 179, 198)
INK = (42, 36, 56)
EYE = (255, 168, 76)


def s(v):
    return int(round(v * SS))


def ellipse(d, box, fill, outline=None, width=3):
    b = [s(box[0]), s(box[1]), s(box[2]), s(box[3])]
    d.ellipse(b, fill=fill, outline=outline, width=s(width) if outline else 0)


def poly(d, pts, fill, outline=None, width=3):
    p = [(s(x), s(y)) for x, y in pts]
    d.polygon(p, fill=fill)
    if outline:
        d.line(p + [p[0]], fill=outline, width=s(width), joint="curve")


def rrect(d, box, r, fill, outline=None, width=3):
    b = [s(box[0]), s(box[1]), s(box[2]), s(box[3])]
    d.rounded_rectangle(b, radius=s(r), fill=fill, outline=outline,
                        width=s(width) if outline else 0)


def draw_char(expr="idle", talking=False):
    img = Image.new("RGBA", (W * SS, H * SS), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)

    # ---- 身体 ----
    poly(d, [(80, 192), (160, 192), (180, 266), (60, 266)], DRESS, INK, 3)
    poly(d, [(120, 200), (134, 240), (120, 262), (106, 240)], DRESS_HI)
    # 领子
    poly(d, [(104, 196), (136, 196), (128, 210), (112, 210)], WHITE, INK, 2)
    # 蝴蝶结
    poly(d, [(120, 214), (104, 206), (104, 224)], GOLD, INK, 2)
    poly(d, [(120, 214), (136, 206), (136, 224)], GOLD, INK, 2)
    ellipse(d, (115, 209, 125, 219), GOLD, INK, 2)

    # ---- 脖子 ----
    rrect(d, (108, 180, 132, 202), 8, SKIN_SH, INK, 2)

    # ---- 后发 ----
    ellipse(d, (46, 40, 194, 196), HAIR, INK, 3)

    # ---- 猫耳 ----
    poly(d, [(72, 74), (56, 20), (108, 52)], HAIR, INK, 3)
    poly(d, [(80, 68), (68, 34), (100, 54)], PINK)
    poly(d, [(168, 74), (184, 20), (132, 52)], HAIR, INK, 3)
    poly(d, [(160, 68), (172, 34), (140, 54)], PINK)

    # ---- 脸 ----
    ellipse(d, (58, 54, 182, 178), SKIN, INK, 3)

    # ---- 刘海 ----
    poly(d, [(56, 96), (60, 62), (84, 44), (120, 38), (156, 44), (180, 62), (184, 96),
             (170, 78), (150, 92), (128, 70), (104, 92), (80, 74)], HAIR, INK, 3)
    poly(d, [(96, 50), (124, 44), (150, 52), (140, 44), (110, 42)], HAIR_HI)

    # ---- 侧发 ----
    poly(d, [(62, 84), (50, 130), (58, 166), (74, 172), (72, 130), (78, 92)], HAIR, INK, 3)
    poly(d, [(178, 84), (190, 130), (182, 166), (166, 172), (168, 130), (162, 92)], HAIR, INK, 3)

    # ---- 呆毛 ----
    poly(d, [(118, 40), (126, 14), (136, 40)], HAIR, INK, 2)

    # ---- 眼睛 ----
    if expr == "blink" or talking:
        for cx in (98, 142):
            d.line([(s(cx - 11), s(118)), (s(cx), s(124)), (s(cx + 11), s(118))],
                   fill=INK, width=s(4), joint="curve")
    elif expr == "happy":
        for cx in (98, 142):
            d.line([(s(cx - 12), s(122)), (s(cx), s(108)), (s(cx + 12), s(122))],
                   fill=INK, width=s(4), joint="curve")
    elif expr == "sleepy":
        for cx in (98, 142):
            d.line([(s(cx - 11), s(120)), (s(cx + 11), s(120))], fill=INK, width=s(4))
    else:
        for cx in (98, 142):
            ellipse(d, (cx - 11, 105, cx + 11, 132), WHITE, INK, 2)
            ellipse(d, (cx - 8, 110, cx + 8, 130), EYE)
            ellipse(d, (cx - 3, 114, cx + 3, 124), INK)
            ellipse(d, (cx + 1, 111, cx + 6, 116), WHITE)

    # ---- 腮红 ----
    ellipse(d, (78, 136, 100, 150), PINK)
    ellipse(d, (140, 136, 162, 150), PINK)

    # ---- 嘴 ----
    if expr == "happy":
        ellipse(d, (112, 140, 128, 154), (120, 60, 70), INK, 2)
    elif talking:
        ellipse(d, (114, 144, 126, 156), (120, 60, 70), INK, 2)
    elif expr == "sleepy":
        ellipse(d, (115, 148, 125, 154), (120, 60, 70), INK, 2)
    else:
        d.arc([s(112), s(140), s(128), s(152)], start=15, end=165, fill=INK, width=s(3))

    # ---- 降采样 + 二值化抠图 ----
    small = img.resize((W, H), Image.LANCZOS)
    out = Image.new("RGB", (W, H), KEY)
    px = small.load()
    op = out.load()
    for y in range(H):
        for x in range(W):
            r, g, b, a = px[x, y]
            op[x, y] = (r, g, b) if a >= 128 else KEY
    return out


FRAMES = {
    "idle": dict(expr="idle"),
    "blink": dict(expr="blink"),
    "talk": dict(expr="idle", talking=True),
    "happy": dict(expr="happy"),
    "sleepy": dict(expr="sleepy"),
}

if __name__ == "__main__":
    for name, kw in FRAMES.items():
        draw_char(**kw).save(os.path.join(OUT, f"{name}.png"))
    print("sprites ->", OUT)
    print("frames:", ", ".join(FRAMES))
