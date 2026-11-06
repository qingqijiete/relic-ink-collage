#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Compose N artifact photos into one reference board for image-to-image input.

Image generation tools usually accept only 1-3 input images. When a piece needs
more artifacts than that, lay the cropped subjects out on a single board first,
then pass the board as the only input image and instruct the model to recompose.

Usage:
    python make_refboard.py --out refboard.jpg img1.jpg img2.png img3.png ...
    python make_refboard.py --out refboard.jpg --crop 0.02,0,0.98,0.95 img1.jpg \
        --crop 0,0,1,1 img2.png --crop 0.26,0.02,0.74,0.94 img3.png
    python make_refboard.py --out refboard.jpg --auto-trim img*.jpg

Crop values are left,top,right,bottom as 0-1 fractions of the source image.
--crop must be repeated once per image, in the same order as the images.
"""
import argparse
import math
import sys
from pathlib import Path

try:
    import numpy as np
    from PIL import Image, ImageFilter
except ImportError:  # pragma: no cover
    sys.exit("需要 Pillow 与 numpy：python -m pip install pillow numpy")


def content_bbox(im, tol=32, pad=0.02):
    """Detect the subject bounding box as fractions, using edge pixels as background."""
    small = im.convert("RGB").resize((160, 160), Image.BILINEAR)
    a = np.asarray(small, dtype=np.int16)
    edges = np.concatenate([a[0], a[-1], a[:, 0], a[:, -1]], axis=0)
    bg = np.median(edges, axis=0)
    diff = np.abs(a - bg).sum(axis=2)
    mask = diff > tol
    if mask.mean() < 0.01 or mask.mean() > 0.92:
        return (0.0, 0.0, 1.0, 1.0)
    ys, xs = np.where(mask)
    x0, x1 = xs.min() / 160, (xs.max() + 1) / 160
    y0, y1 = ys.min() / 160, (ys.max() + 1) / 160
    x0, y0 = max(0.0, x0 - pad), max(0.0, y0 - pad)
    x1, y1 = min(1.0, x1 + pad), min(1.0, y1 + pad)
    if (x1 - x0) < 0.08 or (y1 - y0) < 0.08:
        return (0.0, 0.0, 1.0, 1.0)
    return (x0, y0, x1, y1)


def crop_frac(im, box):
    w, h = im.size
    l, t, r, b = box
    return im.crop((int(l * w), int(t * h), int(r * w), int(b * h)))


def plan_rows(n):
    """Split n items into rows of at most 3, balanced (5 -> 3+2, 8 -> 3+3+2)."""
    if n <= 3:
        return [n]
    rows = math.ceil(n / 3)
    base, extra = divmod(n, rows)
    return [base + (1 if i < extra else 0) for i in range(rows)]


def build(paths, crops, out, canvas, margin, gap, bg, auto_trim, inset=0.0):
    if crops and len(crops) != len(paths):
        sys.exit(f"--crop 数量({len(crops)}) 必须与图片数量({len(paths)}) 一致")

    items = []
    for i, p in enumerate(paths):
        im = Image.open(p).convert("RGB")
        if crops:
            im = crop_frac(im, crops[i])
        elif auto_trim:
            im = crop_frac(im, content_bbox(im))
        elif inset > 0:
            im = crop_frac(im, (inset, inset, 1 - inset, 1 - inset))
        items.append(im)

    cw, ch = canvas
    rows = plan_rows(len(items))
    avail_w = cw - 2 * margin
    avail_h = ch - 2 * margin - gap * (len(rows) - 1)

    # One shared row height keeps the board visually even.
    candidates = [avail_h / len(rows)]
    idx = 0
    for count in rows:
        chunk = items[idx: idx + count]
        idx += count
        ratio = sum(im.width / im.height for im in chunk)
        candidates.append((avail_w - gap * (count - 1)) / ratio)
    row_h = int(max(40, min(candidates)))

    canvas_im = Image.new("RGB", (cw, ch), bg)
    y = margin + max(0, (avail_h - row_h * len(rows)) // 2)
    idx = 0
    for count in rows:
        chunk = items[idx: idx + count]
        idx += count
        scaled = []
        for im in chunk:
            w = max(1, int(round(im.width * row_h / im.height)))
            scaled.append(im.resize((w, row_h), Image.LANCZOS))
        total_w = sum(im.width for im in scaled) + gap * (count - 1)
        x = margin + max(0, (avail_w - total_w) // 2)
        for im in scaled:
            # soft drop shadow so subjects read as objects, not photo tiles
            pad = 40
            sh = Image.new("RGBA", (im.width + pad * 2, im.height + pad * 2), (0, 0, 0, 0))
            sh.paste(im, (pad, pad))
            alpha = sh.filter(ImageFilter.GaussianBlur(16)).split()[3]
            canvas_im.paste((6, 7, 7), (x - pad, y - pad + 10), alpha)
            canvas_im.paste(im, (x, y))
            x += im.width + gap
        y += row_h + gap

    Path(out).parent.mkdir(parents=True, exist_ok=True)
    canvas_im.save(out, quality=95)
    print(f"refboard -> {out}  ({cw}x{ch}, {len(items)} items, rows={rows})")
    return out


def parse_crop(values):
    out = []
    for v in values or []:
        parts = [float(x) for x in v.split(",")]
        if len(parts) != 4:
            sys.exit(f"--crop 需要 4 个比例值：{v}")
        out.append(tuple(parts))
    return out


def main():
    ap = argparse.ArgumentParser(description="把多张文物照片排版成一张素材板")
    ap.add_argument("images", nargs="*", help="来源照片路径")
    ap.add_argument("--out", required=True, help="输出素材板路径")
    ap.add_argument("--crop", action="append", help="单张裁切比例 left,top,right,bottom，可重复")
    ap.add_argument("--auto-trim", action="store_true",
                    help="未给 --crop 时自动检测主体包围盒（仅纯色背景可靠，慎用）")
    ap.add_argument("--inset", type=float, default=0.0,
                    help="未给 --crop 时对每张图四周等比例内缩，默认 0")
    ap.add_argument("--canvas", default="1440x1080", help="画布尺寸，默认 1440x1080")
    ap.add_argument("--margin", type=int, default=56, help="画布留白，默认 56")
    ap.add_argument("--gap", type=int, default=44, help="器物间距，默认 44")
    ap.add_argument("--bg", default="18,19,20", help="背景色 R,G,B，默认 18,19,20")
    # --crop 与图片交替出现（"--crop ... a.jpg --crop ... b.jpg"），
    # 普通 parse_args 会把后面的图片当成 --crop 的值，必须用 intermixed 解析。
    parse = getattr(ap, "parse_intermixed_args", None) or ap.parse_args
    a = parse()
    if not a.images:
        ap.error("至少需要一张来源照片")

    cw, chh = [int(x) for x in a.canvas.lower().split("x")]
    bg = tuple(int(x) for x in a.bg.split(","))
    build(a.images, parse_crop(a.crop), a.out, (cw, chh), a.margin, a.gap, bg, a.auto_trim, a.inset)


if __name__ == "__main__":
    main()
