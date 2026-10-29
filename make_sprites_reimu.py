# -*- coding: utf-8 -*-
"""
博丽灵梦 · 精细版桌宠精灵（320x380）。

一设依据（THBWiki「外貌特征」）：
- 黑发及肩，脑后**巨大红色蝴蝶结**；两鬓发束扎红白束发带
- 黑/棕色瞳孔；红色调改良巫女服（红白两色，故称“红白”）
- 白色宽袖与上衣在肩部分离，袖顶以束带固定于上臂
- 红色及膝裙，裙摆白色图案；手持驱魔棒（御币）

管线：4 倍超采样 → LANCZOS 降采样 → 以 KEY 色为底二值抠图（避免透明窗彩边）。
"""
from PIL import Image, ImageDraw
import os

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "characters", "reimu")
os.makedirs(OUT, exist_ok=True)

W, H = 320, 380
SS = 4
KEY = (255, 0, 254)

HAIR = (46, 36, 55)
HAIR_DK = (32, 24, 39)
HAIR_HI = (92, 72, 108)
SKIN = (255, 231, 219)
SKIN_SH = (246, 203, 189)
RED = (224, 75, 75)
RED_DK = (178, 46, 59)
RED_HI = (242, 120, 126)
WHITE = (253, 251, 247)
WHITE_SH = (227, 219, 211)
GOLD = (247, 200, 106)
GOLD_DK = (208, 154, 62)
INK = (42, 34, 51)
EYE_DK = (104, 64, 42)
EYE_MID = (146, 94, 58)
EYE_LT = (204, 148, 98)
PINK = (255, 172, 177)
PINK_LT = (255, 205, 208)
MOUTH = (172, 76, 84)
WOOD = (208, 162, 106)
WOOD_DK = (168, 122, 72)


def s(v):
    return int(round(v * SS))


def ellipse(d, box, fill, outline=None, width=3):
    d.ellipse([s(box[0]), s(box[1]), s(box[2]), s(box[3])], fill=fill,
              outline=outline, width=s(width) if outline else 0)


def poly(d, pts, fill, outline=None, width=3):
    p = [(s(x), s(y)) for x, y in pts]
    d.polygon(p, fill=fill)
    if outline:
        d.line(p + [p[0]], fill=outline, width=s(width), joint="curve")


def rrect(d, box, r, fill, outline=None, width=3):
    d.rounded_rectangle([s(box[0]), s(box[1]), s(box[2]), s(box[3])], radius=s(r),
                        fill=fill, outline=outline, width=s(width) if outline else 0)


def line(d, pts, fill, width=3):
    d.line([(s(x), s(y)) for x, y in pts], fill=fill, width=s(width), joint="curve")


def arc(d, box, start, end, fill, width=3):
    d.arc([s(box[0]), s(box[1]), s(box[2]), s(box[3])], start=start, end=end,
          fill=fill, width=s(width))


def bez(points, steps=20):
    (x0, y0), (x1, y1), (x2, y2), (x3, y3) = points
    out = []
    for i in range(steps + 1):
        t = i / steps
        mt = 1 - t
        x = mt ** 3 * x0 + 3 * mt ** 2 * t * x1 + 3 * mt * t ** 2 * x2 + t ** 3 * x3
        y = mt ** 3 * y0 + 3 * mt ** 2 * t * y1 + 3 * mt * t ** 2 * y2 + t ** 3 * y3
        out.append((x, y))
    return out


def strand(d, pts, w0, w1, fill, outline=INK, ow=4):
    left, right = [], []
    n = len(pts)
    for i, (x, y) in enumerate(pts):
        t = i / max(1, n - 1)
        w = w0 + (w1 - w0) * t
        x2, y2 = pts[min(i + 1, n - 1)]
        x1, y1 = pts[max(i - 1, 0)]
        dx, dy = x2 - x1, y2 - y1
        ln = (dx * dx + dy * dy) ** 0.5 or 1
        nx, ny = -dy / ln, dx / ln
        left.append((x + nx * w / 2, y + ny * w / 2))
        right.append((x - nx * w / 2, y - ny * w / 2))
    poly(d, left + right[::-1], fill, outline, ow)


def draw_char(expr="idle", talking=False):
    img = Image.new("RGBA", (W * SS, H * SS), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)

    # ================= 巨大红色蝴蝶结 =================
    poly(d, [(106, 112), (34, 78), (20, 136), (38, 186), (98, 162), (110, 136)], RED, INK, 4)
    poly(d, [(100, 124), (44, 94), (34, 134), (50, 168), (94, 150)], RED_DK)
    poly(d, [(218, 112), (290, 78), (304, 136), (286, 186), (226, 162), (214, 136)], RED, INK, 4)
    poly(d, [(224, 124), (280, 94), (290, 134), (274, 168), (230, 150)], RED_DK)
    ellipse(d, (142, 92, 178, 124), RED, INK, 4)
    ellipse(d, (152, 100, 170, 116), RED_DK)

    # ================= 后发 =================
    ellipse(d, (84, 92, 236, 264), HAIR, INK, 4)
    poly(d, [(100, 210), (160, 256), (220, 210), (212, 250), (160, 270), (108, 250)], HAIR_DK)

    # ================= 身体 =================
    poly(d, [(116, 254), (204, 254), (228, 372), (92, 372)], RED, INK, 4)
    poly(d, [(196, 258), (204, 254), (228, 372), (200, 372)], RED_DK)
    # 裙摆白边
    poly(d, [(92, 346), (228, 346), (228, 372), (92, 372)], WHITE, INK, 3)
    for x in (112, 140, 168, 196):
        ellipse(d, (x, 354, x + 8, 362), WHITE_SH)

    # 领口 + 脖子
    poly(d, [(140, 250), (180, 250), (172, 268), (148, 268)], WHITE, INK, 3)
    rrect(d, (146, 228, 174, 256), 10, SKIN_SH, INK, 3)

    # 黄色领结
    poly(d, [(160, 272), (142, 262), (142, 284)], GOLD, INK, 3)
    poly(d, [(160, 272), (178, 262), (178, 284)], GOLD, INK, 3)
    ellipse(d, (153, 265, 167, 279), GOLD_DK, INK, 2)

    # ================= 白色分离袖 =================
    for x0, x1 in ((62, 106), (214, 258)):
        rrect(d, (x0, 266, x1, 358), 18, WHITE, INK, 4)
        rrect(d, (x0 + 4, 342, x1 - 4, 355), 10, WHITE_SH)
        poly(d, [(x0, 270), (x1, 270), (x1, 288), (x0, 288)], RED, INK, 3)
        poly(d, [(x0, 270), (x1, 270), (x1, 277), (x0, 277)], RED_HI)
        line(d, [(x0 + 10, 298), (x0 + 10, 336)], WHITE_SH, 2)

    # ================= 脸 =================
    ellipse(d, (80, 96, 240, 254), SKIN, INK, 4)

    # ================= 刘海 =================
    poly(d, [(78, 152), (82, 112), (106, 84), (160, 68), (214, 84), (238, 112), (242, 152),
             (226, 134), (206, 152), (184, 126), (160, 148), (136, 126), (114, 152), (94, 134)],
         HAIR, INK, 4)
    for pts in ([(104, 86), (116, 108), (124, 132)],
                [(160, 68), (160, 100), (158, 126)],
                [(216, 86), (204, 108), (196, 132)]):
        line(d, bez([pts[0], pts[1], pts[1], pts[2]]), HAIR_DK, 2)
    for cx, cy, rx, ry in ((126, 82, 24, 8), (196, 84, 22, 7)):
        arc(d, (cx - rx, cy - ry, cx + rx, cy + ry), 200, 340, HAIR_HI, 4)

    # ================= 两侧发束 =================
    for xc, sgn in ((72, -1), (248, 1)):
        strand(d, bez([(xc, 128), (xc + sgn * 12, 176), (xc + sgn * 4, 222), (xc + sgn * 8, 252)]),
               26, 12, HAIR, INK, 4)
        bx = xc + sgn * 2
        poly(d, [(bx - 13, 190), (bx + 13, 190), (bx + 13, 202), (bx - 13, 202)], WHITE, INK, 2)
        poly(d, [(bx - 13, 202), (bx + 13, 202), (bx + 13, 208), (bx - 13, 208)], RED, INK, 2)

    # ================= 眼睛 =================
    EYES = ((126, 194), (194, 194))
    if expr in ("blink", "sleepy") or talking:
        for cx, cy in EYES:
            if expr == "sleepy":
                line(d, [(cx - 16, cy + 2), (cx + 16, cy + 2)], INK, 5)
            else:
                d.line([(s(cx - 16), s(cy + 2)), (s(cx - 4), s(cy + 9)), (s(cx + 8), s(cy + 5))],
                       fill=INK, width=s(5), joint="curve")
    elif expr == "happy":
        for cx, cy in EYES:
            d.line([(s(cx - 17), s(cy + 8)), (s(cx), s(cy - 9)), (s(cx + 17), s(cy + 8))],
                   fill=INK, width=s(5), joint="curve")
    else:
        for cx, cy in EYES:
            ellipse(d, (cx - 16, cy - 21, cx + 16, cy + 21), WHITE, INK, 3)
            ellipse(d, (cx - 12, cy - 17, cx + 12, cy + 18), EYE_DK)
            ellipse(d, (cx - 9, cy - 7, cx + 9, cy + 16), EYE_MID)
            ellipse(d, (cx - 6, cy + 3, cx + 6, cy + 15), EYE_LT)
            ellipse(d, (cx - 5, cy + 5, cx + 5, cy + 14), INK)
            ellipse(d, (cx - 10, cy - 14, cx - 1, cy - 4), WHITE)
            ellipse(d, (cx + 3, cy + 8, cx + 9, cy + 14), (255, 244, 238))
            arc(d, (cx - 17, cy - 23, cx + 17, cy + 21), 185, 355, INK, 5)
            arc(d, (cx - 14, cy - 36, cx + 14, cy - 22), 205, 335, HAIR_DK, 3)

    # ================= 腮红 / 嘴 =================
    for cx in (100, 220):
        ellipse(d, (cx - 20, 214, cx + 20, 232), PINK_LT)
        ellipse(d, (cx - 17, 216, cx + 17, 230), PINK)
        for i in range(3):
            x = cx - 10 + i * 7
            line(d, [(x, 219), (x + 3, 227)], (255, 158, 164), 1)

    if expr == "happy":
        poly(d, [(151, 238), (169, 238), (160, 252)], MOUTH, INK, 2)
        ellipse(d, (154, 243, 166, 251), (255, 150, 150))
    elif talking:
        ellipse(d, (151, 238, 169, 255), MOUTH, INK, 2)
        ellipse(d, (155, 244, 165, 252), (255, 150, 150))
    elif expr == "sleepy":
        ellipse(d, (155, 244, 165, 251), MOUTH, INK, 2)
    else:
        arc(d, (150, 236, 170, 252), 20, 160, INK, 3)

    # ================= 降采样 + 二值抠图 =================
    small = img.resize((W, H), Image.LANCZOS)
    out = Image.new("RGB", (W, H), KEY)
    px, op = small.load(), out.load()
    for y in range(H):
        for x in range(W):
            r, g, b, a = px[x, y]
            op[x, y] = (r, g, b) if a >= 120 else KEY
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
    print("reimu sprites (320x380) ->", OUT)
