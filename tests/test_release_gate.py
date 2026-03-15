from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
SCRIPT_PATH = ROOT_DIR / "scripts" / "release_gate.py"
README_PATH = ROOT_DIR / "README.md"
RUNBOOK_PATH = ROOT_DIR / "RUNBOOK.md"
PLAN_PATH = ROOT_DIR / "IMPLEMENTATION_PLAN.md"


def load_release_gate_module():
    spec = importlib.util.spec_from_file_location("release_gate", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec is not None
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_release_gate_plan_covers_three_release_phases() -> None:
    module = load_release_gate_module()

    phases = module.build_release_plan("http://127.0.0.1:9000")

    assert [phase.key for phase in phases] == ["pre-release", "release", "post-release"]

    pre_release_commands = [
        module.format_command(step.command)
        for step in phases[0].steps
        if step.kind == "command"
    ]
    release_commands = [
        module.format_command(step.command)
        for step in phases[1].steps
        if step.kind == "command"
    ]

    assert "python3 -m ruff check app tests scripts" in pre_release_commands
    assert "python3 -m pytest -q" in pre_release_commands
    assert "python3 -m pytest -q -m e2e" in pre_release_commands
    assert "python3 scripts/render_visual_regression_baselines.py --check" in pre_release_commands
    assert "alembic upgrade head" in release_commands
    assert phases[2].steps[0].kind == "health"
    assert phases[2].steps[0].url == "http://127.0.0.1:9000/v1/health"


def test_release_gate_cli_dry_run_renders_phase_plan() -> None:
    result = subprocess.run(
        ["python3", str(SCRIPT_PATH)],
        cwd=ROOT_DIR,
        check=True,
        capture_output=True,
        text=True,
    )

    stdout = result.stdout

    assert "发布前" in stdout
    assert "发布中" in stdout
    assert "发布后" in stdout
    assert "python3 -m pytest -q" in stdout
    assert "http://127.0.0.1:8000/v1/health" in stdout
    assert "dry-run" in stdout


def test_release_gate_execute_runs_commands_and_health_check(monkeypatch) -> None:
    module = load_release_gate_module()
    phases = module.select_phases(
        module.build_release_plan("http://127.0.0.1:9100"),
        ["pre-release", "post-release"],
    )
    executed_commands: list[tuple[str, ...]] = []
    checked_urls: list[str] = []

    def fake_run(command, cwd, check):
        executed_commands.append(tuple(command))
        assert cwd == ROOT_DIR
        assert check is True
        return subprocess.CompletedProcess(command, 0)

    def fake_check_health(url, timeout_seconds):
        checked_urls.append(url)
        assert timeout_seconds == module.DEFAULT_HEALTH_TIMEOUT_SECONDS
        return {
            "database_ok": True,
            "database_backend": "sqlite",
            "embedding_storage": "json",
            "feature_flags": {"evals_enabled": True},
        }

    monkeypatch.setattr(module.subprocess, "run", fake_run)
    monkeypatch.setattr(module, "check_health", fake_check_health)

    module.run_release_plan(phases, execute=True)

    assert ("python3", "-m", "ruff", "check", "app", "tests", "scripts") in executed_commands
    assert ("python3", "-m", "pytest", "-q") in executed_commands
    assert ("python3", "-m", "app.cli.search", "--query", "系统支持什么") in executed_commands
    assert checked_urls == ["http://127.0.0.1:9100/v1/health"]


def test_check_health_requires_database_and_feature_flags(monkeypatch) -> None:
    module = load_release_gate_module()

    class FakeResponse:
        status = 200

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def read(self) -> bytes:
            return json.dumps(
                {
                    "database_ok": True,
                    "database_backend": "postgresql",
                    "embedding_storage": "pgvector",
                    "feature_flags": {"evals_enabled": True},
                }
            ).encode("utf-8")

    monkeypatch.setattr(module, "urlopen", lambda url, timeout: FakeResponse())

    payload = module.check_health("http://127.0.0.1:9200/v1/health", timeout_seconds=3)

    assert payload["database_ok"] is True
    assert payload["feature_flags"]["evals_enabled"] is True


def test_release_gate_docs_reference_script_and_phases() -> None:
    readme_text = README_PATH.read_text(encoding="utf-8")
    runbook_text = RUNBOOK_PATH.read_text(encoding="utf-8")
    plan_text = PLAN_PATH.read_text(encoding="utf-8")

    assert "python3 scripts/release_gate.py --phase pre-release --execute" in readme_text
    assert "python3 scripts/release_gate.py --phase pre-release --execute" in runbook_text
    assert "发布中" in runbook_text
    assert "发布后" in runbook_text
    assert "scripts/release_gate.py" in plan_text
