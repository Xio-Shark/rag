from __future__ import annotations

from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
WORKFLOW_PATH = ROOT_DIR / ".github" / "workflows" / "mainline-quality-gate.yml"


def test_mainline_quality_gate_workflow_covers_core_checks() -> None:
    workflow_text = WORKFLOW_PATH.read_text(encoding="utf-8")

    assert "name: Mainline Quality Gate" in workflow_text
    assert 'python-version: "3.9"' in workflow_text
    assert 'python -m pip install -e ".[dev]"' in workflow_text
    assert "python -m playwright install --with-deps chromium" in workflow_text
    assert "python -m ruff check app tests scripts" in workflow_text
    assert "python -m pytest -q" in workflow_text
    assert "python -m compileall app tests scripts" in workflow_text
    assert ".github/workflows/mainline-quality-gate.yml" in workflow_text
    assert '"tests/**"' in workflow_text
    assert '"app/**"' in workflow_text
    assert '"scripts/**"' in workflow_text
    assert '".github/workflows/release-gate.yml"' in workflow_text
