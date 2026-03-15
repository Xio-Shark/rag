from __future__ import annotations

from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
WORKFLOW_PATH = ROOT_DIR / ".github" / "workflows" / "release-gate.yml"
README_PATH = ROOT_DIR / "README.md"
RUNBOOK_PATH = ROOT_DIR / "RUNBOOK.md"
PLAN_PATH = ROOT_DIR / "IMPLEMENTATION_PLAN.md"


def test_release_gate_workflow_supports_manual_dispatch_and_artifacts() -> None:
    workflow_text = WORKFLOW_PATH.read_text(encoding="utf-8")

    assert "name: Release Gate" in workflow_text
    assert "workflow_dispatch:" in workflow_text
    assert "phase:" in workflow_text
    assert "type: choice" in workflow_text
    assert "- pre-release" in workflow_text
    assert "- release" in workflow_text
    assert "- post-release" in workflow_text
    assert "- all" in workflow_text
    assert "execute:" in workflow_text
    assert "type: boolean" in workflow_text
    assert "base_url:" in workflow_text
    assert "http://127.0.0.1:8000" in workflow_text
    assert 'python-version: "3.9"' in workflow_text
    assert 'python -m pip install -e ".[dev]"' in workflow_text
    assert "python -m playwright install --with-deps chromium" in workflow_text
    assert "python3 scripts/release_gate.py" in workflow_text
    assert 'release-gate-plan.txt' in workflow_text
    assert 'release-gate-execute.log' in workflow_text
    assert "release-gate-plan" in workflow_text
    assert "release-gate-execution-log" in workflow_text


def test_release_workflow_docs_reference_manual_trigger() -> None:
    readme_text = README_PATH.read_text(encoding="utf-8")
    runbook_text = RUNBOOK_PATH.read_text(encoding="utf-8")
    plan_text = PLAN_PATH.read_text(encoding="utf-8")

    assert "gh workflow run release-gate.yml -f phase=pre-release -f execute=true" in readme_text
    assert "gh workflow run release-gate.yml -f phase=pre-release -f execute=true" in runbook_text
    assert ".github/workflows/release-gate.yml" in plan_text
