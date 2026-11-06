#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Assemble square collage panels into a connected grid, with an optional cross-panel guide line.

Panels should be square and share one palette. The optional guide line is a
low-brightness silver arc drawn across the whole grid so the nine cells read as a
single continuous composition instead of nine separate pictures.

Usage:
    python assemble_grid.py --out grid.png --panels p1.png p2.png ... p9.png
    python assemble_grid.py --out grid.png --panel-dirs 01 02 03 04 05 06 07 08 09
    python assemble_grid.py --out grid.png --panel-dirs 0*/ --guide diagonal --clean

--panel-dirs picks the newest .png/.jpg inside each directory (recursively).
Requires: pillow, numpy, opencv-python-headless (only for --clean).
"""
import argparse
import math
import sys
from pathlib import Path

try:
    from PIL import Image, ImageDraw, ImageFilter
except ImportError:  # pragma: no cover
    sys.exit("需要 Pillow：python -m pip install pillow")

CANVAS_BG = (12, 13, 13)


def newest_image(folder):
    folder = Path(folder)
    files = [p for p in folder.rglob("*") if p.suffix.lower() in {".png", ".jpg", ".jpeg"}]
    if not files:
        sys.exit(f"目录中没有图片：{folder}")
    return max(files, key=lambda p: p.stat().st_mtime)


def to_square(im, cell):
    im = im.convert("RGB")
    w, h = im.size
    if w != h:
        s = min(w, h)
        im = im.crop(((w - s) // 2, (h - s) // 2, (w - s) // 2 + s, (h - s) // 2 + s))
    return im.resize((cell, cell), Image.LANCZOS)


def clean_panel(path, cell):
    """Clear a corner badge before scaling. Falls back to the original on failure."""
    try:
        import cv2
        import numpy as np
        sys.path.insert(0, str(Path(__file__).parent))
        from clean_corner import clean, corner_box

        pil = Image.open(path).convert("RGB")
        img = cv2.cvtColor(np.array(pil), cv2.COLOR_RGB2BGR)
        res, cov = clean(img, corner_box(pil.size, "br", 0.26, 0.09))
        if cov < 0.002:
            print(f"  {Path(path).name[:28]}: 未检出角标，保留原图")
            return pil
        print(f"  {Path(path).name[:28]}: 已清理角标 (覆盖率 {cov:.3f})")
        return Image.fromarray(cv2.cvtColor(res, cv2.COLOR_BGR2RGB))
    except SystemExit:
        raise
    except Exception as exc:  # pragma: no cover
        print(f"跳过角标清理（{path.name}）：{exc}")
        return Image.open(path)


def bezier(points, steps=600):
    """Sample a Bezier curve through the control points with de Casteljau's algorithm."""
    out = []
    for i in range(steps + 1):
        t = i / steps
        layer = list(points)
        while len(layer) > 1:
            layer = [((layer[j][0] * (1 - t) + layer[j + 1][0] * t),
                      (layer[j][1] * (1 - t) + layer[j + 1][1] * t))
                     for j in range(len(layer) - 1)]
        out.append(layer[0])
    return out


def guide_points(kind, w, h):
    if kind == "diagonal":
        return [(0.01 * w, 0.06 * h), (0.34 * w, 0.30 * h), (0.52 * w, 0.62 * h), (0.99 * w, 0.94 * h)]
    if kind == "horizontal":
        return [(0.01 * w, 0.38 * h), (0.30 * w, 0.30 * h), (0.68 * w, 0.44 * h), (0.99 * w, 0.66 * h)]
    if kind == "vertical":
        return [(0.62 * w, 0.01 * h), (0.50 * w, 0.34 * h), (0.66 * w, 0.70 * h), (0.58 * w, 0.99 * h)]
    return None


def add_guide(canvas, kind, color=(201, 199, 190, 88), width=4, blur=2.4):
    pts = guide_points(kind, canvas.width, canvas.height)
    if not pts:
        return canvas
    layer = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer)
    curve = bezier(pts)
    draw.line(curve, fill=color, width=width, joint="curve")
    layer = layer.filter(ImageFilter.GaussianBlur(blur))
    return Image.alpha_composite(canvas.convert("RGBA"), layer).convert("RGB")


def main():
    ap = argparse.ArgumentParser(description="把方形拼贴拼成九宫格并叠加贯穿动线")
    ap.add_argument("--out", required=True)
    ap.add_argument("--panels", nargs="+", help="按顺序给出的方格图片")
    ap.add_argument("--panel-dirs", nargs="+", help="按顺序给出的目录，各取最新一张图")
    ap.add_argument("--cell", type=int, default=1024, help="单格边长，默认 1024")
    ap.add_argument("--cols", type=int, default=3)
    ap.add_argument("--guide", default="none", choices=["none", "diagonal", "horizontal", "vertical"])
    ap.add_argument("--clean", action="store_true", help="拼合前清理每格右下角角标")
    a = ap.parse_args()

    if a.panel_dirs:
        paths = [newest_image(d) for d in a.panel_dirs]
    elif a.panels:
        paths = [Path(p) for p in a.panels]
    else:
        sys.exit("需要 --panels 或 --panel-dirs")

    for p in paths:
        if not p.exists():
            sys.exit(f"找不到图片：{p}")

    rows = math.ceil(len(paths) / a.cols)
    canvas = Image.new("RGB", (a.cols * a.cell, rows * a.cell), CANVAS_BG)

    for i, p in enumerate(paths):
        im = clean_panel(p, a.cell) if a.clean else Image.open(p)
        canvas.paste(to_square(im, a.cell), ((i % a.cols) * a.cell, (i // a.cols) * a.cell))

    if a.guide != "none":
        canvas = add_guide(canvas, a.guide)

    out = Path(a.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(out)
    print(f"grid -> {out}  ({canvas.width}x{canvas.height}, {len(paths)} cells, guide={a.guide})")


if __name__ == "__main__":
    main()
