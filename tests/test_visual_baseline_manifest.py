from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from scripts.render_visual_regression_baselines import (
    render_baseline_summary,
    render_diagnostic_summary,
    render_markdown_document,
)

ROOT_DIR = Path(__file__).resolve().parent.parent
BASELINES_DIR = Path(__file__).resolve().parent / "baselines"
MANIFEST_PATH = BASELINES_DIR / "manifest.json"
README_PATH = ROOT_DIR / "README.md"
DOC_PATH = ROOT_DIR / "docs" / "visual-regression-baselines.md"
E2E_TEST_PATH = Path(__file__).resolve().parent / "test_e2e_visual_regression.py"
WORKFLOW_PATH = ROOT_DIR / ".github" / "workflows" / "visual-baseline-sync.yml"
VISUAL_E2E_WORKFLOW_PATH = ROOT_DIR / ".github" / "workflows" / "visual-regression-e2e.yml"


def _load_manifest() -> dict:
    return json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))


def _formal_baseline_paths() -> list[str]:
    baseline_paths = []
    for path in BASELINES_DIR.glob("*.png"):
        if path.name.endswith(".actual.png") or path.name.endswith(".diff.png"):
            continue
        baseline_paths.append(str(path.relative_to(ROOT_DIR)))
    return sorted(baseline_paths)


def _diagnostic_artifact_paths() -> list[str]:
    paths = []
    for path in BASELINES_DIR.glob("*.png"):
        if path.name.endswith(".actual.png") or path.name.endswith(".diff.png"):
            paths.append(str(path.relative_to(ROOT_DIR)))
    return sorted(paths)


def test_visual_baseline_manifest_matches_formal_files() -> None:
    manifest = _load_manifest()
    formal_entries = manifest["formal_baselines"]
    manifest_paths = sorted(item["path"] for item in formal_entries)

    assert manifest_paths == _formal_baseline_paths()
    assert len(manifest_paths) == len(set(manifest_paths))
    assert all(not path.endswith(".actual.png") for path in manifest_paths)
    assert all(not path.endswith(".diff.png") for path in manifest_paths)


def test_visual_baseline_workspace_has_no_diagnostic_artifacts() -> None:
    assert _diagnostic_artifact_paths() == []


def test_visual_baseline_manifest_matches_docs_and_readme() -> None:
    manifest = _load_manifest()
    formal_entries = manifest["formal_baselines"]
    unique_tests = {entry["test"] for entry in formal_entries}
    readme_text = README_PATH.read_text(encoding="utf-8")
    doc_text = DOC_PATH.read_text(encoding="utf-8")
    e2e_test_text = E2E_TEST_PATH.read_text(encoding="utf-8")

    assert f"当前已补 {len(formal_entries)} 份视觉基线资产" in readme_text
    assert f"覆盖 {len(unique_tests)} 条本地视觉回归测试" in readme_text
    assert "docs/visual-regression-baselines.md" in readme_text
    assert "tests/baselines/manifest.json" in doc_text
    assert ".github/workflows/visual-regression-e2e.yml" in readme_text
    assert ".github/workflows/visual-regression-e2e.yml" in doc_text

    for entry in formal_entries:
        baseline_name = Path(entry["path"]).name
        canonical_baseline_name = baseline_name.replace(".darwin", "").replace(".windows", "")
        assert entry["path"] in doc_text
        assert entry["viewport"] in doc_text
        assert entry["flow"] in doc_text
        assert entry["test"] in doc_text
        assert entry["test"] in e2e_test_text
        assert canonical_baseline_name in e2e_test_text

    for artifact in manifest["diagnostic_artifacts"]:
        assert artifact["pattern"] in doc_text
        assert artifact["purpose"] in doc_text
        assert artifact["source"] in doc_text


def test_visual_baseline_markdown_is_rendered_from_manifest() -> None:
    manifest = _load_manifest()
    rendered = render_markdown_document(manifest)
    existing = DOC_PATH.read_text(encoding="utf-8")

    assert rendered == existing


def test_visual_baseline_summary_can_filter_to_selected_paths() -> None:
    manifest = _load_manifest()
    rendered = render_baseline_summary(
        manifest,
        paths=["tests/baselines/report-panel.png"],
    )

    assert "视觉基线变更摘要" in rendered
    assert "tests/baselines/report-panel.png" in rendered
    assert "桌面 1440x2200" in rendered
    assert "报告查看 + 报告导航 + 恢复完整报告" in rendered
    assert "test_report_panel_visual_regression" in rendered
    assert "tests/baselines/tablet-report-panel.png" not in rendered


def test_visual_baseline_summary_rejects_unknown_paths() -> None:
    manifest = _load_manifest()

    with pytest.raises(ValueError):
        render_baseline_summary(
            manifest,
            paths=["tests/baselines/not-in-manifest.png"],
        )


def test_visual_diagnostic_summary_can_map_artifacts_back_to_formal_baseline() -> None:
    manifest = _load_manifest()
    rendered = render_diagnostic_summary(
        manifest,
        artifact_paths=[
            "tests/baselines/report-panel.actual.png",
            "tests/baselines/report-panel.diff.png",
        ],
    )

    assert "视觉回归失败诊断摘要" in rendered
    assert "tests/baselines/report-panel.png" in rendered
    assert "桌面 1440x2200" in rendered
    assert "报告查看 + 报告导航 + 恢复完整报告" in rendered
    assert "test_report_panel_visual_regression" in rendered
    assert "tests/baselines/report-panel.actual.png" in rendered
    assert "tests/baselines/report-panel.diff.png" in rendered


def test_visual_diagnostic_summary_handles_untracked_baseline_paths() -> None:
    manifest = _load_manifest()
    rendered = render_diagnostic_summary(
        manifest,
        artifact_paths=["tests/baselines/untracked-panel.actual.png"],
    )

    assert "视觉回归失败诊断摘要" in rendered
    assert "tests/baselines/untracked-panel.png" in rendered
    assert "未在 manifest 中登记" in rendered


def test_visual_diagnostic_summary_handles_empty_artifact_list() -> None:
    manifest = _load_manifest()
    rendered = render_diagnostic_summary(manifest, artifact_paths=[])

    assert "视觉回归失败诊断摘要" in rendered
    assert "当前没有视觉诊断产物" in rendered


def test_visual_baseline_renderer_check_mode_succeeds() -> None:
    result = subprocess.run(
        [
            "python3",
            str(ROOT_DIR / "scripts" / "render_visual_regression_baselines.py"),
            "--check",
        ],
        cwd=ROOT_DIR,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr or result.stdout


def test_visual_baseline_ci_workflow_runs_sync_guards() -> None:
    workflow_text = WORKFLOW_PATH.read_text(encoding="utf-8")

    assert ".github/workflows/visual-regression-e2e.yml" in workflow_text
    assert "tests/baselines/*.png" in workflow_text
    assert "tests/baselines/manifest.json" in workflow_text
    assert "docs/visual-regression-baselines.md" in workflow_text
    assert "tests/visual_regression.py" in workflow_text
    assert "tests/test_visual_regression.py" in workflow_text
    assert "tests/test_e2e_visual_regression.py" in workflow_text
    assert "issues: write" in workflow_text
    assert "pull-requests: write" in workflow_text
    assert "fetch-depth: 0" in workflow_text
    assert "python scripts/render_visual_regression_baselines.py --summary" in workflow_text
    assert (
        'git diff --name-only "$BASE_SHA" "$HEAD_SHA" -- "tests/baselines/*.png"'
        in workflow_text
    )
    assert 'echo "summary_path=$summary_file" >> "$GITHUB_OUTPUT"' in workflow_text
    assert "actions/github-script@v8" in workflow_text
    assert "github.event.pull_request.head.repo.fork == false" in workflow_text
    assert "<!-- visual-baseline-summary -->" in workflow_text
    assert "github.rest.issues.listComments" in workflow_text
    assert "github.rest.issues.updateComment" in workflow_text
    assert "github.rest.issues.createComment" in workflow_text
    assert "GITHUB_STEP_SUMMARY" in workflow_text
    assert 'write_summary "No formal visual baseline PNG changes detected."' in workflow_text
    assert "python -m ruff check app tests" in workflow_text
    assert "python -m pytest -q tests/test_visual_baseline_manifest.py" in workflow_text
    assert "python scripts/render_visual_regression_baselines.py --check" in workflow_text


def test_visual_regression_e2e_workflow_runs_visual_tests_and_uploads_artifacts() -> None:
    workflow_text = VISUAL_E2E_WORKFLOW_PATH.read_text(encoding="utf-8")

    assert "name: Visual Regression E2E" in workflow_text
    assert "issues: write" in workflow_text
    assert "pull-requests: write" in workflow_text
    assert "tests/test_e2e_visual_regression.py" in workflow_text
    assert "tests/visual_regression.py" in workflow_text
    assert "python -m playwright install --with-deps chromium" in workflow_text
    assert "python -m pytest -q tests/test_e2e_visual_regression.py" in workflow_text
    assert "--junitxml" in workflow_text
    assert "visual-regression-e2e-junit.xml" in workflow_text
    assert (
        "python scripts/render_visual_regression_baselines.py --diagnostic-summary"
        in workflow_text
    )
    assert "actions/upload-artifact@v4" in workflow_text
    assert "actions/github-script@v8" in workflow_text
    assert "if: failure()" in workflow_text
    assert "if: always() && github.event_name == 'pull_request'" in workflow_text
    assert "GITHUB_STEP_SUMMARY" in workflow_text
    assert 'echo "summary_path=$summary_file" >> "$GITHUB_OUTPUT"' in workflow_text
    assert "id: upload_junit" in workflow_text
    assert "id: upload_diagnostics" in workflow_text
    assert "id: upload_diagnostic_summary" in workflow_text
    assert "github.event.pull_request.head.repo.fork == false" in workflow_text
    assert "JOB_STATUS: ${{ job.status }}" in workflow_text
    assert (
        "RUN_URL: ${{ github.server_url }}/${{ github.repository }}/actions/runs/"
        "${{ github.run_id }}"
    ) in workflow_text
    assert "RUN_NUMBER: ${{ github.run_number }}" in workflow_text
    assert "RUN_ATTEMPT: ${{ github.run_attempt }}" in workflow_text
    assert "<!-- visual-regression-diagnostic-summary -->" in workflow_text
    assert "steps.upload_junit.outputs.artifact-url" in workflow_text
    assert "steps.upload_diagnostics.outputs.artifact-url" in workflow_text
    assert "steps.upload_diagnostic_summary.outputs.artifact-url" in workflow_text
    assert "Run" in workflow_text
    assert "[#${runNumber} attempt ${runAttempt}](${runUrl})" in workflow_text
    assert "Artifacts" in workflow_text
    assert "[${label}](${url})" in workflow_text
    assert "视觉回归 E2E 已恢复通过，历史失败诊断已失效。" in workflow_text
    assert "github.rest.issues.listComments" in workflow_text
    assert "github.rest.issues.updateComment" in workflow_text
    assert "github.rest.issues.createComment" in workflow_text
    assert "visual-regression-junit" in workflow_text
    assert "visual-regression-diagnostic-summary" in workflow_text
    assert "${{ steps.diagnostic_summary.outputs.summary_path }}" in workflow_text
    assert "tests/baselines/*.actual.png" in workflow_text
    assert "tests/baselines/*.diff.png" in workflow_text
    assert "if-no-files-found: ignore" in workflow_text
