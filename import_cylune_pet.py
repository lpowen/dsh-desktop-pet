# -*- coding: utf-8 -*-
"""
把 Cylune 的角色桌宠素材导入本桌宠。

Cylune 的主题素材在：
  Assets/Cylune/themes/<角色>/pet/{idle,happy,shy,sleepy}.png
  Assets/Cylune/pet/{...}.png            （默认主题＝帕秋莉）

用法：
  python import_cylune_pet.py --char reimu --height 150
  python import_cylune_pet.py --src "<完整 pet 目录>" --name <输出名> --height 150

处理：按 alpha 裁边 → 等比缩放到目标高度 → 以 KEY 色为底阈值抠图（Tk 透明窗只认色键）。
原图没有闭眼/说话帧，所以 blink、talk 复用 idle。
"""
import argparse
import os

from PIL import Image

CYLUNE = os.environ.get("CYLUNE_HOME", r"C:\path\to\Cylune\Assets\Cylune")
HERE = os.path.dirname(os.path.abspath(__file__))
KEY = (255, 0, 254)
ALPHA_CUT = 110


def resolve_src(args):
    if args.src:
        return args.src
    if args.char:
        theme = os.path.join(CYLUNE, "themes", args.char, "pet")
        if os.path.isdir(theme):
            return theme
        raise SystemExit(f"主题目录不存在：{theme}")
    return os.path.join(CYLUNE, "pet")


def convert(src_dir, out_dir, target_h, pad=14):
    os.makedirs(out_dir, exist_ok=True)
    jobs = [("idle", "idle"), ("idle", "blink"), ("idle", "talk"),
            ("happy", "happy"), ("sleepy", "sleepy"), ("shy", "shy")]
    for src_name, out_name in jobs:
        src = os.path.join(src_dir, f"{src_name}.png")
        if not os.path.exists(src):
            print(f"跳过 {src_name}（不存在）")
            continue
        im = Image.open(src).convert("RGBA")
        bbox = im.getbbox()
        if bbox:
            bbox = (max(0, bbox[0] - pad), max(0, bbox[1] - pad),
                    min(im.width, bbox[2] + pad), min(im.height, bbox[3] + pad))
            im = im.crop(bbox)

        ratio = target_h / im.height
        w = max(1, int(im.width * ratio))
        im = im.resize((w, target_h), Image.LANCZOS)

        out = Image.new("RGB", (w, target_h), KEY)
        px, op = im.load(), out.load()
        for y in range(target_h):
            for x in range(w):
                r, g, b, a = px[x, y]
                op[x, y] = (r, g, b) if a >= ALPHA_CUT else KEY

        out.save(os.path.join(out_dir, f"{out_name}.png"))
        print(f"{src_name:8s} -> {out_name:8s} {w}x{target_h}")
    print("输出：", out_dir)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", help="Cylune 的 pet 目录")
    ap.add_argument("--char", help="主题角色名，如 reimu / patchouli / sakuya")
    ap.add_argument("--name", help="输出到 characters/<name>，默认取 --char 或 patchouli")
    ap.add_argument("--height", type=int, default=150, help="成品高度（px）")
    args = ap.parse_args()

    src = resolve_src(args)
    name = args.name or (f"{args.char}_cylune" if args.char else "patchouli")
    convert(src, os.path.join(HERE, "characters", name), args.height)


if __name__ == "__main__":
    main()
