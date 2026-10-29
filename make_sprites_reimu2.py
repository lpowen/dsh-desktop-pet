# -*- coding: utf-8 -*-
"""
博丽灵梦 · 封面风 Q 版（360x420）

风格参考用户提供的同人专辑封面（LIVE 幻想郷 02）：
- 头身比更极端：脑袋占画面一大半，身体只到肩膀
- 眼睛又大又圆，深棕虹膜 + 下缘亮色 + 双高光 + 粗上眼线 + 细下眼线
- 小鼻子一个点，张嘴笑（露一点牙齿和舌头）
- 头发分股、带大块高光带和飞散发丝
- 粗描边、柔和腮红

只借鉴画风，不使用原图任何素材；一设特征仍是 THBWiki 那一套（黑发、大红蝴蝶结、
红白巫女服、白色分离袖）。
"""
from PIL import Image, ImageDraw
import os

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "characters", "reimu2")
os.makedirs(OUT, exist_ok=True)

W, H = 360, 420
SS = 4
KEY = (255, 0, 254)

HAIR = (58, 45, 64)
HAIR_DK = (34, 25, 40)
HAIR_HI = (116, 92, 130)
HAIR_HI2 = (140, 116, 156)
SKIN = (255, 235, 224)
SKIN_SH = (248, 205, 192)
RED = (226, 72, 74)
RED_DK = (176, 44, 56)
RED_HI = (246, 126, 128)
WHITE = (254, 252, 249)
WHITE_SH = (226, 218, 210)
GOLD = (249, 202, 108)
GOLD_DK = (206, 152, 62)
INK = (40, 32, 48)
IRIS_DK = (92, 54, 36)
IRIS_MID = (140, 88, 52)
IRIS_LT = (206, 150, 98)
PINK = (255, 166, 172)
PINK_LT = (255, 200, 204)
MOUTH = (150, 56, 64)
TONGUE = (240, 140, 146)
TOOTH = (255, 250, 246)


def s(v):
    return int(round(v * SS))


def ellipse(d, box, fill, outline=None, width=4):
    d.ellipse([s(box[0]), s(box[1]), s(box[2]), s(box[3])], fill=fill,
              outline=outline, width=s(width) if outline else 0)


def poly(d, pts, fill, outline=None, width=4):
    p = [(s(x), s(y)) for x, y in pts]
    d.polygon(p, fill=fill)
    if outline:
        d.line(p + [p[0]], fill=outline, width=s(width), joint="curve")


def rrect(d, box, r, fill, outline=None, width=4):
    d.rounded_rectangle([s(box[0]), s(box[1]), s(box[2]), s(box[3])], radius=s(r),
                        fill=fill, outline=outline, width=s(width) if outline else 0)


def line(d, pts, fill, width=4):
    d.line([(s(x), s(y)) for x, y in pts], fill=fill, width=s(width), joint="curve")


def arc(d, box, start, end, fill, width=4):
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


def draw_eye(d, cx, cy, expr):
    """封面风的大眼睛：粗上眼线、深棕虹膜、双高光。"""
    if expr in ("blink", "sleepy"):
        arc(d, (cx - 30, cy - 34, cx + 30, cy + 18), 200, 340, INK, 8)
        return
    if expr == "happy":
        arc(d, (cx - 30, cy - 6, cx + 30, cy + 46), 200, 340, INK, 8)
        return

    # 眼白
    ellipse(d, (cx - 30, cy - 36, cx + 30, cy + 36), WHITE, INK, 4)
    # 虹膜：上深下亮
    ellipse(d, (cx - 25, cy - 32, cx + 25, cy + 30), IRIS_DK)
    ellipse(d, (cx - 22, cy - 8, cx + 22, cy + 28), IRIS_MID)
    ellipse(d, (cx - 17, cy + 6, cx + 17, cy + 26), IRIS_LT)
    # 瞳孔
    ellipse(d, (cx - 11, cy - 14, cx + 11, cy + 14), INK)
    # 高光（一大一小，左上 + 右下）
    ellipse(d, (cx - 20, cy - 24, cx - 2, cy - 6), WHITE)
    ellipse(d, (cx + 6, cy + 8, cx + 16, cy + 18), (255, 246, 240))
    # 上眼线（外眼角带一点挑）
    arc(d, (cx - 32, cy - 38, cx + 32, cy + 34), 180, 350, INK, 7)
    line(d, [(cx + 26, cy - 20), (cx + 34, cy - 26)], INK, 5)
    # 下眼线
    arc(d, (cx - 26, cy - 4, cx + 26, cy + 34), 20, 160, (120, 84, 76), 3)


def draw_char(expr="idle", talking=False):
    img = Image.new("RGBA", (W * SS, H * SS), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)

    # ============ 巨大蝴蝶结（脑后） ============
    poly(d, [(148, 148), (38, 88), (12, 196), (52, 276), (140, 228), (154, 190)], RED, INK, 5)
    poly(d, [(138, 164), (58, 118), (36, 196), (70, 258), (132, 214)], RED_DK)
    poly(d, [(132, 150), (64, 106), (56, 148)], RED_HI)
    poly(d, [(212, 148), (322, 88), (348, 196), (308, 276), (220, 228), (206, 190)], RED, INK, 5)
    poly(d, [(222, 164), (302, 118), (324, 196), (290, 258), (228, 214)], RED_DK)
    poly(d, [(228, 150), (296, 106), (304, 148)], RED_HI)

    # ============ 后发 ============
    ellipse(d, (46, 66, 314, 336), HAIR, INK, 5)
    poly(d, [(80, 250), (180, 320), (280, 250), (272, 312), (180, 340), (88, 312)], HAIR_DK)

    # ============ 身体（到肩） ============
    poly(d, [(122, 322), (238, 322), (262, 420), (98, 420)], RED, INK, 5)
    poly(d, [(226, 326), (238, 322), (262, 420), (232, 420)], RED_DK)
    poly(d, [(98, 396), (262, 396), (262, 420), (98, 420)], WHITE, INK, 4)
    # 领口
    poly(d, [(152, 318), (208, 318), (198, 340), (162, 340)], WHITE, INK, 4)
    # 领结
    poly(d, [(180, 348), (156, 336), (156, 364)], GOLD, INK, 4)
    poly(d, [(180, 348), (204, 336), (204, 364)], GOLD, INK, 4)
    ellipse(d, (171, 340, 189, 358), GOLD_DK, INK, 3)

    # ============ 白色分离袖 ============
    for x0, x1 in ((80, 128), (232, 280)):
        rrect(d, (x0, 330, x1, 414), 20, WHITE, INK, 5)
        poly(d, [(x0, 334), (x1, 334), (x1, 356), (x0, 356)], RED, INK, 4)
        poly(d, [(x0, 334), (x1, 334), (x1, 342), (x0, 342)], RED_HI)
        line(d, [(x0 + 12, 366), (x0 + 12, 402)], WHITE_SH, 3)

    # ============ 脸 ============
    ellipse(d, (58, 88, 302, 322), SKIN, INK, 5)

    # ============ 刘海（分股 + 飞散） ============
    # 先铺一层发块填缝，再叠一撮撮带圆弧发梢的发绺
    poly(d, [(52, 200), (58, 132), (92, 96), (180, 76), (268, 96), (302, 132), (308, 200),
             (280, 170), (240, 186), (180, 170), (120, 186), (80, 170)], HAIR, INK, 5)
    clumps = [
        ((100, 106), (80, 142), (78, 172), (84, 202)),
        ((146, 96), (132, 146), (132, 182), (140, 214)),
        ((214, 96), (228, 146), (228, 182), (220, 214)),
        ((260, 106), (280, 142), (282, 172), (276, 202)),
    ]
    for (x0, y0), (x1, y1), (x2, y2), (x3, y3) in clumps:
        path = bez([(x0, y0), (x1, y1), (x2, y2), (x3, y3)])
        strand(d, path, 74, 34, HAIR, INK, 4)
        ellipse(d, (x3 - 17, y3 - 18, x3 + 17, y3 + 10), HAIR, INK, 4)
    # 发绺之间的暗缝
    for (x0, y0), (x1, y1), (x2, y2), (x3, y3) in clumps:
        line(d, bez([(x0, y0 + 6), (x1, y1), (x2, y2), (x3, y3 - 6)]), HAIR_DK, 3)
    # 飞散呆毛
    strand(d, bez([(186, 84), (198, 44), (230, 30), (250, 44)]), 10, 2, HAIR, INK, 3)
    strand(d, bez([(160, 88), (142, 54), (110, 44), (94, 58)]), 8, 2, HAIR, INK, 3)

    # ============ 两侧发束 ============
    for xc, sgn in ((66, -1), (294, 1)):
        strand(d, bez([(xc, 150), (xc + sgn * 16, 220), (xc + sgn * 4, 280), (xc + sgn * 10, 326)]),
               40, 18, HAIR, INK, 5)
        bx = xc + sgn * 6
        poly(d, [(bx - 20, 240), (bx + 20, 240), (bx + 20, 258), (bx - 20, 258)], WHITE, INK, 3)
        poly(d, [(bx - 20, 258), (bx + 20, 258), (bx + 20, 268), (bx - 20, 268)], RED, INK, 3)

    # ============ 眼睛 ============
    EYES = ((132, 214), (228, 214))
    for cx, cy in EYES:
        draw_eye(d, cx, cy, expr)

    # ============ 腮红 / 鼻子 / 嘴 ============
    for cx in (92, 268):
        ellipse(d, (cx - 30, 250, cx + 30, 276), PINK_LT)
        ellipse(d, (cx - 26, 252, cx + 26, 274), PINK)
        for i in range(3):
            x = cx - 14 + i * 10
            line(d, [(x, 256), (x + 4, 268)], (255, 150, 158), 2)

    ellipse(d, (176, 244, 186, 251), SKIN_SH)  # 小鼻子

    if expr == "talking" or talking:
        ellipse(d, (164, 262, 196, 288), MOUTH, INK, 4)
        ellipse(d, (170, 276, 190, 286), TONGUE)
    elif expr == "happy":
        poly(d, [(164, 264), (196, 264), (180, 288)], MOUTH, INK, 4)
        arc(d, (168, 262, 192, 274), 0, 180, TOOTH, 3)
        ellipse(d, (172, 276, 188, 286), TONGUE)
    elif expr == "blink":
        ellipse(d, (168, 262, 192, 282), MOUTH, INK, 4)
        arc(d, (170, 260, 190, 272), 0, 180, TOOTH, 3)
        ellipse(d, (174, 274, 186, 281), TONGUE)
    elif expr == "sleepy":
        arc(d, (164, 258, 196, 280), 20, 160, INK, 4)
        for zx, zy, zs in ((250, 178, 14), (270, 146, 11), (286, 118, 8)):
            line(d, [(zx, zy), (zx + zs, zy), (zx, zy + zs), (zx + zs, zy + zs)], HAIR_HI, 3)
    else:
        # 默认：张小嘴笑
        ellipse(d, (168, 262, 192, 282), MOUTH, INK, 4)
        arc(d, (170, 260, 190, 272), 0, 180, TOOTH, 3)
        ellipse(d, (174, 274, 186, 281), TONGUE)

    # ============ 降采样 + 二值抠图 ============
    small = img.resize((W, H), Image.LANCZOS)
    out = Image.new("RGB", (W, H), KEY)
    px, op = small.load(), out.load()
    for y in range(H):
        for x in range(W):
            r, g, b, a = px[x, y]
            op[x, y] = (r, g, b) if a >= 118 else KEY
    return out


FRAMES = {
    "idle": dict(expr="idle"),
    "blink": dict(expr="blink"),
    "talk": dict(expr="talk"),
    "happy": dict(expr="happy"),
    "sleepy": dict(expr="sleepy"),
}

if __name__ == "__main__":
    for name, kw in FRAMES.items():
        draw_char(**kw).save(os.path.join(OUT, f"{name}.png"))
    print("reimu2 (cover-style chibi) ->", OUT)
