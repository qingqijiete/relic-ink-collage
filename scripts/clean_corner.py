#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Remove a baked-in corner badge (e.g. an "AI generated" label) by inpainting.

Badges are light glyphs on a dark ground, so isolate them with a brightness
threshold measured against the local median, dilate, inpaint, then add grain back
so the patch does not read as a plastic blur.

Known limit: when the badge sits on a light paper surface, glyph and paper have
similar luminance and a threshold cannot separate them. Such a badge is also
visually faint; the better fix is a composition rule - keep the bottom-right
corner dark - rather than fighting it here.

Usage:
    python clean_corner.py --image panel.png --out panel_clean.png
    python clean_corner.py --image panel.png --out panel_clean.png --check c.png
    python clean_corner.py --image panel.png --out panel_clean.png --box 880,1450,1024,1536
    python clean_corner.py --image panel.png --out panel_clean.png --mode dark

Requires: pillow, numpy, opencv-python-headless
"""
import argparse
import shutil
import sys
from pathlib import Path

try:
    import cv2
    import numpy as np
    from PIL import Image
except ImportError:  # pragma: no cover
    sys.exit("需要 pillow / numpy / opencv-python-headless：\n"
             "python -m pip install pillow numpy opencv-python-headless")


CORNERS = ("br", "bl", "tr", "tl")


def corner_box(size, corner, w_frac, h_frac):
    w, h = size
    bw, bh = int(w * w_frac), int(h * h_frac)
    x0 = w - bw if corner in ("br", "tr") else 0
    y0 = h - bh if corner in ("br", "bl") else 0
    x1 = w if corner in ("br", "tr") else bw
    y1 = h if corner in ("br", "bl") else bh
    return x0, y0, x1, y1


def _mask(gray, offset, mode):
    bg = float(np.median(gray))
    if mode == "dark":
        return cv2.inRange(gray, 0, int(max(0, bg - offset)))
    return cv2.inRange(gray, int(min(250, bg + offset)), 255)


def clean(img, box, offset=46.0, dilate=2, radius=7, noise=3.0, seed=7, mode="auto"):
    """Inpaint a badge inside box. Returns (result_bgr, coverage_ratio).

    mode="light" targets light glyphs on a dark ground (the usual case),
    mode="dark" targets dark glyphs on a light ground, "auto" picks the one whose
    coverage looks like a badge rather than a subject.
    """
    h, w = img.shape[:2]
    x0, y0, x1, y1 = box
    x0, y0 = max(0, x0), max(0, y0)
    x1, y1 = min(w, max(x0 + 1, x1)), min(h, max(y0 + 1, y1))
    if x1 - x0 < 8 or y1 - y0 < 8:
        return img, 0.0

    roi = img[y0:y1, x0:x1]
    gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)

    modes = ["light", "dark"] if mode == "auto" else [mode]
    best = None
    for m in modes:
        cand = _mask(gray, offset, m)
        cov = float(cand.mean()) / 255.0
        score = abs(cov - 0.06) if cov > 0.002 else 1.0
        if best is None or score < best[0]:
            best = (score, cand, cov)
    _, mask, coverage = best

    if dilate > 0:
        mask = cv2.dilate(mask, np.ones((5, 5), np.uint8), iterations=dilate)

    full = np.zeros((h, w), np.uint8)
    full[y0:y1, x0:x1] = mask
    res = cv2.inpaint(img, full, radius, cv2.INPAINT_TELEA)

    if noise > 0:
        patch = res[y0:y1, x0:x1].astype(np.float32)
        rng = np.random.default_rng(seed)
        patch = np.clip(patch + rng.normal(0, noise, patch.shape).astype(np.float32), 0, 255)
        res[y0:y1, x0:x1] = patch.astype(np.uint8)
    return res, coverage


def main():
    ap = argparse.ArgumentParser(description="清除图片角落烧录的水印/角标")
    ap.add_argument("--image", required=True)
    ap.add_argument("--out", help="输出路径，默认在原名后加 _clean")
    ap.add_argument("--corner", default="br", choices=CORNERS, help="水印所在角，默认 br")
    ap.add_argument("--roi-w", type=float, default=0.26, help="搜索区宽度占比，默认 0.26")
    ap.add_argument("--roi-h", type=float, default=0.09, help="搜索区高度占比，默认 0.09")
    ap.add_argument("--box", help="直接指定像素框 x0,y0,x1,y1，优先于 --corner")
    ap.add_argument("--offset", type=float, default=46.0,
                    help="亮度阈值相对局部中位数的偏移，越低越敏感，默认 46")
    ap.add_argument("--mode", default="auto", choices=["auto", "light", "dark"],
                    help="light=深底亮字，dark=浅底暗字，auto 自动选择")
    ap.add_argument("--dilate", type=int, default=2)
    ap.add_argument("--radius", type=int, default=7)
    ap.add_argument("--noise", type=float, default=3.0)
    ap.add_argument("--check", help="额外输出一张放大裁切用于目视验证")
    a = ap.parse_args()

    src = Path(a.image)
    pil = Image.open(src).convert("RGB")
    img = cv2.cvtColor(np.array(pil), cv2.COLOR_RGB2BGR)

    box = (tuple(int(v) for v in a.box.split(",")) if a.box
           else corner_box(pil.size, a.corner, a.roi_w, a.roi_h))

    res, cov = clean(img, box, a.offset, a.dilate, a.radius, a.noise, mode=a.mode)
    out = Path(a.out) if a.out else src.with_name(src.stem + "_clean.png")
    out.parent.mkdir(parents=True, exist_ok=True)

    if cov < 0.002:
        shutil.copyfile(src, out)
        print(f"未检测到明显水印（覆盖率 {cov:.4f}），已原样复制 -> {out}")
    else:
        Image.fromarray(cv2.cvtColor(res, cv2.COLOR_BGR2RGB)).save(out)
        print(f"已修补 -> {out}  box={box} 覆盖像素占比={cov:.4f}  mode={a.mode}")
        if cov > 0.40:
            print("提示：覆盖偏高，可能把主体也纳入掩膜。缩小 --roi-w/--roi-h 或改用 --box")

    if a.check:
        x0, y0, x1, y1 = box
        Image.open(out).crop((x0, y0, x1, y1)).resize(
            ((x1 - x0) * 2, (y1 - y0) * 2), Image.LANCZOS).save(a.check)
        print(f"检查图 -> {a.check}（务必目视确认文字已消失）")


if __name__ == "__main__":
    main()
