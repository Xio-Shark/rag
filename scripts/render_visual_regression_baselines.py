from __future__ import annotations

import argparse
import json
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
MANIFEST_PATH = ROOT_DIR / "tests" / "baselines" / "manifest.json"
DOC_PATH = ROOT_DIR / "docs" / "visual-regression-baselines.md"


def load_manifest(path: Path = MANIFEST_PATH) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _formal_baseline_index(manifest: dict) -> dict[str, dict]:
    return {entry["path"]: entry for entry in manifest["formal_baselines"]}


def _baseline_path_from_diagnostic_path(path: str) -> str | None:
    if path.endswith(".actual.png"):
        return f"{path[:-11]}.png"
    if path.endswith(".diff.png"):
        return f"{path[:-9]}.png"
    return None


def render_baseline_summary(manifest: dict, paths: list[str] | None = None) -> str:
    baseline_index = _formal_baseline_index(manifest)
    selected_paths = paths or [entry["path"] for entry in manifest["formal_baselines"]]
    entries = []
    unknown_paths = []

    for path in selected_paths:
        entry = baseline_index.get(path)
        if entry:
            entries.append(entry)
        else:
            unknown_paths.append(path)

    if unknown_paths:
        unknown_str = ", ".join(f"`{path}`" for path in unknown_paths)
        raise ValueError(f"以下基线文件未在 manifest 中登记: {unknown_str}")

    lines = ["视觉基线变更摘要", ""]
    for entry in entries:
        lines.append(
            "- "
            f"`{entry['path']}` | `{entry['viewport']}` | {entry['flow']} | "
            f"`{entry['test']}`"
        )
    return "\n".join(lines)


def render_diagnostic_summary(manifest: dict, artifact_paths: list[str] | None = None) -> str:
    baseline_index = _formal_baseline_index(manifest)
    grouped_paths: dict[str, list[str]] = {}

    selected_paths = sorted(artifact_paths or [])
    if not selected_paths:
        lines = ["视觉回归失败诊断摘要", "", "- 当前没有视觉诊断产物。"]
        return "\n".join(lines)

    for path in selected_paths:
        baseline_path = _baseline_path_from_diagnostic_path(path)
        if not baseline_path:
            continue
        grouped_paths.setdefault(baseline_path, []).append(path)

    lines = ["视觉回归失败诊断摘要", ""]
    for baseline_path in sorted(grouped_paths):
        artifact_list = ", ".join(f"`{path}`" for path in sorted(grouped_paths[baseline_path]))
        entry = baseline_index.get(baseline_path)
        if entry:
            lines.append(
                "- "
                f"`{baseline_path}` | `{entry['viewport']}` | {entry['flow']} | "
                f"`{entry['test']}` | 诊断图：{artifact_list}"
            )
            continue

        lines.append(
            f"- `{baseline_path}` | 未在 manifest 中登记 | 诊断图：{artifact_list}"
        )

    if len(lines) == 2:
        lines.append("- 当前没有可识别的视觉诊断产物。")
    return "\n".join(lines)


def render_markdown_document(manifest: dict) -> str:
    lines = [
        "# 视觉回归基线清单",
        "",
        "这份文档只记录当前工作区里真实存在的视觉回归资产，避免把正式基线、失败诊断产物和更新命令混在一起。",
        (
            "机器可校验的事实源在 `tests/baselines/manifest.json`，新增或调整正式基线时，"
            "应该先更新这份 manifest，再同步这份 Markdown 清单和 README。"
        ),
        (
            "如需重建本文，可执行 "
            "`python3 scripts/render_visual_regression_baselines.py --write`。"
        ),
        (
            "如果仓库托管到 GitHub，`.github/workflows/visual-baseline-sync.yml` 也会"
            "自动检查 manifest、本文以及 `app/tests` 轻量 lint 是否保持通过。"
        ),
        (
            "如需快速查看某张基线对应的测试、视口和覆盖链路，可执行 "
            "`python3 scripts/render_visual_regression_baselines.py --summary --path "
            "tests/baselines/report-panel.png`。"
        ),
        (
            "在 GitHub Actions 中，变更基线摘要也会写入 job summary，"
            "不需要翻完整 step 日志才能看到。"
        ),
        (
            "对于同仓库 PR，workflow 还会把这段摘要更新到一条固定 PR comment；"
            "fork PR 会跳过评论步骤。"
        ),
        (
            "仓库还提供独立的 `.github/workflows/visual-regression-e2e.yml`，"
            "会运行 `tests/test_e2e_visual_regression.py`，并在失败时上传 "
            "`.actual.png` / `.diff.png` 诊断产物。"
        ),
        (
            "这条 workflow 失败时，还会把诊断图关联回正式基线、视口、覆盖链路和测试名，"
            "并写入 job summary。"
        ),
        (
            "对于同仓库 PR，这段失败诊断摘要也会被更新到固定 PR comment；"
            "fork PR 会跳过评论步骤。"
        ),
        (
            "这条 workflow 还会上传 `pytest` 生成的 JUnit XML，以及失败诊断摘要 "
            "markdown 文件本身，便于离开 GitHub UI 后继续复用。"
        ),
        (
            "对于同仓库 PR，失败 comment 现在还会带上这些 artifact 的可点击链接，"
            "方便直接跳到 JUnit、摘要或诊断图下载页。"
        ),
        (
            "当后续运行恢复通过时，这条固定失败 comment 会自动更新为“已恢复通过”，"
            "避免 PR 页面残留过期告警。"
        ),
        (
            "失败或恢复 comment 现在还会带上本次 GitHub Actions run 的直达链接和 "
            "run 编号，方便 reviewer 直接跳转到对应构建。"
        ),
        "",
        "## 正式基线",
        "",
        "| 基线文件 | 视口 | 覆盖链路 | 对应测试 |",
        "| --- | --- | --- | --- |",
    ]

    for entry in manifest["formal_baselines"]:
        lines.append(
            f"| `{entry['path']}` | `{entry['viewport']}` | {entry['flow']} | `{entry['test']}` |"
        )

    lines.extend(
        [
            "",
            (
                "这些基线都由 "
                "[tests/test_e2e_visual_regression.py]"
                "(/Users/xioshark/Desktop/rag/tests/test_e2e_visual_regression.py) 驱动，"
                "实际像素对比由 [tests/visual_regression.py]"
                "(/Users/xioshark/Desktop/rag/tests/visual_regression.py) 执行。"
            ),
            "",
            "## 失败诊断产物",
            "",
            "以下文件不是正式基线，只在视觉回归失败时作为排障材料出现：",
            "",
            "| 产物模式 | 用途 | 生成位置 |",
            "| --- | --- | --- |",
        ]
    )

    for artifact in manifest["diagnostic_artifacts"]:
        lines.append(
            f"| `{artifact['pattern']}` | {artifact['purpose']} | `{artifact['source']}` |"
        )

    lines.extend(
        [
            "",
            (
                "当前目录里如果看到 `*.actual.png`、`*.diff.png` 这一类文件，应视为历史"
                "诊断产物，而不是需要长期维护的正式基线。"
            ),
            (
                "当同名视觉回归重新通过，或者基线被刷新后，"
                "`assert_visual_match(...)` 会自动清理这两类过期诊断产物。"
            ),
            (
                "`tests/test_visual_baseline_manifest.py` 也会直接校验当前工作区没有"
                "残留诊断产物，避免把历史失败截图误当成正式资产。"
            ),
            "",
            "## 更新基线",
            "",
            "只有在以下情况才应该更新基线：",
            "",
            "1. 页面样式或布局有意改变，且变化经过确认。",
            "2. 测试归一化逻辑调整后，旧基线不再反映真实稳定状态。",
            "3. 新增了新的视觉回归用例，需要首次生成基线。",
            "",
            "更新命令：",
            "",
            "```bash",
            "UPDATE_VISUAL_BASELINES=1 python3 -m pytest -q tests/test_e2e_visual_regression.py",
            "```",
            "",
            "如果只想更新单条基线，优先使用 `-k` 限定到具体测试函数。",
            "",
            "## 排障步骤",
            "",
            "当视觉回归失败时，按下面顺序处理：",
            "",
            "1. 先看报错里指向的 `baseline`、`actual`、`diff` 路径。",
            "2. 打开 `.diff.png`，确认是预期改动还是非预期抖动。",
            "3. 如果是动态字段导致的噪声，优先补归一化逻辑，不直接刷新基线。",
            "4. 如果是预期 UI 改动，确认对应 README / 任务日志也需要同步，再更新基线。",
            "5. 成功修复并重新跑过对应用例后，同名旧诊断产物会自动被清理。",
            "6. 如果目录里还留着更早历史的诊断产物，可手工清理，避免和正式基线混淆。",
            "",
            "清理命令：",
            "",
            "```bash",
            "rm -f tests/baselines/*.actual.png tests/baselines/*.diff.png",
            "```",
            "",
            "## 维护约束",
            "",
            "- 新增视觉基线时，必须同时更新这份清单和 README 的汇总描述。",
            (
                "- 新增或调整正式基线后，优先执行 "
                "`python3 scripts/render_visual_regression_baselines.py --write` 重建本文。"
            ),
            "- 正式基线文件名应和测试函数覆盖范围一致，避免出现语义不清的图片名。",
            "- 失败诊断产物不应写进正式清单数量统计。",
            "",
        ]
    )

    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="从视觉基线 manifest 渲染 Markdown 清单")
    parser.add_argument("--write", action="store_true", help="将渲染结果写入默认文档路径")
    parser.add_argument("--stdout", action="store_true", help="将渲染结果输出到标准输出")
    parser.add_argument("--check", action="store_true", help="检查当前文档是否与渲染结果一致")
    parser.add_argument("--summary", action="store_true", help="输出视觉基线摘要")
    parser.add_argument("--diagnostic-summary", action="store_true", help="输出失败诊断摘要")
    parser.add_argument(
        "--path",
        action="append",
        default=[],
        help="为 --summary 指定一个或多个基线路径，可重复传入",
    )
    parser.add_argument(
        "--artifact-path",
        action="append",
        default=[],
        help="为 --diagnostic-summary 指定一个或多个诊断图路径，可重复传入",
    )
    args = parser.parse_args()

    manifest = load_manifest()
    rendered = render_markdown_document(manifest)

    if args.summary:
        try:
            summary = render_baseline_summary(manifest, paths=args.path or None)
        except ValueError as exc:
            print(str(exc))
            return 1
        print(summary)
        return 0

    if args.diagnostic_summary:
        summary = render_diagnostic_summary(manifest, artifact_paths=args.artifact_path or None)
        print(summary)
        return 0

    if args.check:
        current = DOC_PATH.read_text(encoding="utf-8")
        if current != rendered:
            print("视觉基线清单未和 manifest 同步")
            return 1
        print("视觉基线清单已和 manifest 同步")
        return 0

    if args.write:
        DOC_PATH.write_text(rendered, encoding="utf-8")

    if args.stdout or not args.write:
        print(rendered, end="")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
