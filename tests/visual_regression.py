from __future__ import annotations

import os
from io import BytesIO
from pathlib import Path

from PIL import Image, ImageChops


def stack_images_vertically(
    image_bytes_list: list[bytes],
    *,
    gap: int = 0,
    background: tuple[int, int, int, int] = (242, 241, 234, 255),
) -> bytes:
    images = [Image.open(BytesIO(item)).convert("RGBA") for item in image_bytes_list]
    if not images:
        raise ValueError("至少需要一张图片用于拼接")

    width = max(image.width for image in images)
    total_height = sum(image.height for image in images) + gap * (len(images) - 1)
    canvas = Image.new("RGBA", (width, total_height), background)

    top = 0
    for image in images:
        canvas.paste(image, ((width - image.width) // 2, top))
        top += image.height + gap

    output = BytesIO()
    canvas.save(output, format="PNG")
    return output.getvalue()


def build_diff_image(expected: Image.Image, actual: Image.Image) -> Image.Image:
    diff = ImageChops.difference(actual, expected)
    mask = diff.convert("L").point(lambda value: 255 if value else 0)
    highlight = Image.new("RGBA", expected.size, (220, 38, 38, 255))
    return Image.composite(highlight, expected, mask)


def _diagnostic_artifact_paths(baseline_path: Path) -> tuple[Path, Path]:
    return (
        baseline_path.with_name(f"{baseline_path.stem}.actual.png"),
        baseline_path.with_name(f"{baseline_path.stem}.diff.png"),
    )


def _remove_diagnostic_artifacts(baseline_path: Path) -> None:
    actual_path, diff_path = _diagnostic_artifact_paths(baseline_path)
    actual_path.unlink(missing_ok=True)
    diff_path.unlink(missing_ok=True)


def assert_visual_match(
    image_bytes: bytes,
    baseline_path: Path,
    *,
    max_diff_ratio: float = 0.002,
) -> None:
    baseline_path.parent.mkdir(parents=True, exist_ok=True)

    if os.getenv("UPDATE_VISUAL_BASELINES") == "1" or not baseline_path.exists():
        baseline_path.write_bytes(image_bytes)
        _remove_diagnostic_artifacts(baseline_path)
        return

    actual = Image.open(BytesIO(image_bytes)).convert("RGBA")
    expected = Image.open(baseline_path).convert("RGBA")

    if actual.size != expected.size:
        raise AssertionError(
            f"视觉基线尺寸不一致: actual={actual.size}, expected={expected.size}"
        )

    diff = ImageChops.difference(actual, expected)
    diff_pixels = sum(1 for pixel in diff.getdata() if pixel != (0, 0, 0, 0))
    total_pixels = actual.size[0] * actual.size[1]
    diff_ratio = diff_pixels / total_pixels if total_pixels else 0.0

    if diff_ratio > max_diff_ratio:
        actual_path, diff_path = _diagnostic_artifact_paths(baseline_path)
        actual_path.write_bytes(image_bytes)
        build_diff_image(expected, actual).save(diff_path, format="PNG")
        raise AssertionError(
            f"视觉回归差异超阈值: ratio={diff_ratio:.4%}, max={max_diff_ratio:.4%}, "
            f"actual={actual_path}, diff={diff_path}, baseline={baseline_path}"
        )

    _remove_diagnostic_artifacts(baseline_path)
