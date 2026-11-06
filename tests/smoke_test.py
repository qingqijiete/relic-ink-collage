"""冒烟测试：不依赖任何外部素材，验证三个脚本能跑通。

    python tests/smoke_test.py
"""

from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = ROOT / "scripts"

COLORS = [(180, 90, 60), (60, 120, 100), (90, 90, 160), (200, 190, 150)]


def make_source(path: Path, color, size=(600, 400)) -> Path:
    arr = np.full((size[1], size[0], 3), color, dtype="uint8")
    Image.fromarray(arr).save(path)
    return path


def run(args) -> None:
    subprocess.run([sys.executable, *args], check=True)


def test_refboard(tmp: Path) -> None:
    srcs = [make_source(tmp / f"src_{i}.jpg", c) for i, c in enumerate(COLORS)]
    out = tmp / "refboard.jpg"
    run([str(SCRIPTS / "make_refboard.py"), "--out", str(out), *map(str, srcs)])
    im = Image.open(out)
    assert im.width > 0 and im.height > 0, "素材板为空"
    print(f"  refboard      {im.size}")


def test_refboard_with_crop(tmp: Path) -> None:
    srcs = [make_source(tmp / f"crop_{i}.png", c) for i, c in enumerate(COLORS[:3])]
    out = tmp / "refboard_crop.jpg"
    run([
        str(SCRIPTS / "make_refboard.py"), "--out", str(out),
        "--crop", "0.1,0.1,0.9,0.9", str(srcs[0]),
        "--crop", "0.0,0.0,1.0,1.0", str(srcs[1]),
        "--crop", "0.2,0.05,0.8,0.95", str(srcs[2]),
    ])
    assert out.exists(), "带裁剪参数的素材板未生成"
    print(f"  refboard/crop {Image.open(out).size}")


def test_clean_corner(tmp: Path) -> None:
    # 深色底 + 右下角亮点，模拟烧录角标
    arr = np.zeros((400, 400, 3), dtype="uint8")
    arr[:] = (12, 14, 13)
    arr[370:385, 300:390] = 220
    src = tmp / "panel.png"
    Image.fromarray(arr).save(src)

    out, check = tmp / "panel_clean.png", tmp / "check.jpg"
    run([
        str(SCRIPTS / "clean_corner.py"),
        "--image", str(src), "--out", str(out), "--check", str(check),
    ])
    assert out.exists() and check.exists(), "清理脚本未产出结果"
    print(f"  clean_corner  {Image.open(out).size}")


def test_assemble_grid(tmp: Path) -> None:
    dirs = []
    for i in range(9):
        d = tmp / f"p{i + 1:02d}"
        d.mkdir()
        make_source(d / "panel.png", COLORS[i % len(COLORS)], size=(256, 256))
        dirs.append(str(d))

    out = tmp / "grid.png"
    run([
        str(SCRIPTS / "assemble_grid.py"), "--out", str(out),
        "--panel-dirs", *dirs, "--cell", "200", "--guide", "diagonal",
    ])
    im = Image.open(out)
    assert im.width == im.height, "九宫格应为正方形"
    print(f"  assemble_grid {im.size}")


def main() -> int:
    if not SCRIPTS.is_dir():
        print(f"找不到 scripts 目录：{SCRIPTS}", file=sys.stderr)
        return 1

    tmp = Path(tempfile.mkdtemp(prefix="relic-ink-"))
    try:
        print("冒烟测试")
        for fn in (test_refboard, test_refboard_with_crop, test_clean_corner, test_assemble_grid):
            fn(tmp)
        print("全部通过")
        return 0
    except subprocess.CalledProcessError as exc:
        print(f"脚本执行失败：{exc}", file=sys.stderr)
        return 1
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())
