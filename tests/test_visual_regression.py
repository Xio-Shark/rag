from __future__ import annotations

from io import BytesIO
from pathlib import Path

import pytest
from PIL import Image

from tests.visual_regression import (
    assert_visual_match,
    resolve_visual_baseline_path,
    stack_images_vertically,
)


def _image_bytes(
    color: tuple[int, int, int, int],
    *,
    size: tuple[int, int] = (12, 10),
    accent: tuple[int, int, int, int] | None = None,
) -> bytes:
    image = Image.new("RGBA", size, color)
    if accent:
        image.putpixel((size[0] // 2, size[1] // 2), accent)
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


def test_stack_images_vertically_combines_heights_and_centers_images() -> None:
    red = _image_bytes((255, 0, 0, 255), size=(6, 4))
    blue = _image_bytes((0, 0, 255, 255), size=(4, 5))

    combined = stack_images_vertically([red, blue], gap=2)
    image = Image.open(BytesIO(combined)).convert("RGBA")

    assert image.size == (6, 11)
    assert image.getpixel((0, 0)) == (255, 0, 0, 255)
    assert image.getpixel((1, 6)) == (0, 0, 255, 255)


def test_assert_visual_match_writes_baseline_when_missing(tmp_path: Path) -> None:
    baseline_path = tmp_path / "baseline.png"
    image_bytes = _image_bytes((10, 20, 30, 255))

    assert_visual_match(image_bytes, baseline_path)

    assert baseline_path.exists()
    assert baseline_path.read_bytes() == image_bytes


def test_assert_visual_match_writes_actual_and_diff_artifacts_on_failure(tmp_path: Path) -> None:
    baseline_path = tmp_path / "baseline.png"
    baseline_path.write_bytes(_image_bytes((255, 255, 255, 255)))
    actual_bytes = _image_bytes(
        (255, 255, 255, 255),
        accent=(255, 0, 0, 255),
    )

    with pytest.raises(AssertionError):
        assert_visual_match(actual_bytes, baseline_path, max_diff_ratio=0.0)

    actual_path = tmp_path / "baseline.actual.png"
    diff_path = tmp_path / "baseline.diff.png"
    assert actual_path.exists()
    assert diff_path.exists()

    diff_image = Image.open(diff_path).convert("RGBA")
    assert diff_image.size == (12, 10)
    assert any(pixel != (255, 255, 255, 255) for pixel in diff_image.getdata())


def test_assert_visual_match_removes_stale_diagnostic_artifacts_after_success(
    tmp_path: Path,
) -> None:
    baseline_path = tmp_path / "baseline.png"
    image_bytes = _image_bytes((255, 255, 255, 255))
    baseline_path.write_bytes(image_bytes)

    actual_path = tmp_path / "baseline.actual.png"
    diff_path = tmp_path / "baseline.diff.png"
    actual_path.write_bytes(b"stale-actual")
    diff_path.write_bytes(b"stale-diff")

    assert_visual_match(image_bytes, baseline_path)

    assert not actual_path.exists()
    assert not diff_path.exists()


def test_assert_visual_match_removes_stale_diagnostic_artifacts_when_updating_baseline(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    baseline_path = tmp_path / "baseline.png"
    baseline_path.write_bytes(_image_bytes((255, 255, 255, 255)))

    actual_path = tmp_path / "baseline.actual.png"
    diff_path = tmp_path / "baseline.diff.png"
    actual_path.write_bytes(b"stale-actual")
    diff_path.write_bytes(b"stale-diff")

    monkeypatch.setenv("UPDATE_VISUAL_BASELINES", "1")
    updated_image = _image_bytes((10, 20, 30, 255))

    assert_visual_match(updated_image, baseline_path)

    assert baseline_path.read_bytes() == updated_image
    assert not actual_path.exists()
    assert not diff_path.exists()


def test_resolve_visual_baseline_path_prefers_platform_specific_variant(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    baseline_path = tmp_path / "baseline.png"
    darwin_path = tmp_path / "baseline.darwin.png"
    baseline_path.write_bytes(_image_bytes((255, 255, 255, 255)))
    darwin_bytes = _image_bytes((10, 20, 30, 255))
    darwin_path.write_bytes(darwin_bytes)

    monkeypatch.setenv("VISUAL_BASELINE_PLATFORM", "darwin")

    assert resolve_visual_baseline_path(baseline_path) == darwin_path
    assert_visual_match(darwin_bytes, baseline_path)
