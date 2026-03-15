# 视觉回归基线清单

这份文档只记录当前工作区里真实存在的视觉回归资产，避免把正式基线、失败诊断产物和更新命令混在一起。
机器可校验的事实源在 `tests/baselines/manifest.json`，新增或调整正式基线时，应该先更新这份 manifest，再同步这份 Markdown 清单和 README。
正式基线当前以 GitHub Actions 的 Linux 渲染结果为准；非 Linux 本机默认跳过 `tests/test_e2e_visual_regression.py`，如需强制执行，可设置 `ALLOW_NON_LINUX_VISUAL_REGRESSION=1`。
如需重建本文，可执行 `python3 scripts/render_visual_regression_baselines.py --write`。
如果仓库托管到 GitHub，`.github/workflows/visual-baseline-sync.yml` 也会自动检查 manifest、本文以及 `app/tests` 轻量 lint 是否保持通过。
如需快速查看某张基线对应的测试、视口和覆盖链路，可执行 `python3 scripts/render_visual_regression_baselines.py --summary --path tests/baselines/report-panel.png`。
在 GitHub Actions 中，变更基线摘要也会写入 job summary，不需要翻完整 step 日志才能看到。
对于同仓库 PR，workflow 还会把这段摘要更新到一条固定 PR comment；fork PR 会跳过评论步骤。
仓库还提供独立的 `.github/workflows/visual-regression-e2e.yml`，会运行 `tests/test_e2e_visual_regression.py`，并在失败时上传 `.actual.png` / `.diff.png` 诊断产物。
这条 workflow 失败时，还会把诊断图关联回正式基线、视口、覆盖链路和测试名，并写入 job summary。
对于同仓库 PR，这段失败诊断摘要也会被更新到固定 PR comment；fork PR 会跳过评论步骤。
这条 workflow 还会上传 `pytest` 生成的 JUnit XML，以及失败诊断摘要 markdown 文件本身，便于离开 GitHub UI 后继续复用。
对于同仓库 PR，失败 comment 现在还会带上这些 artifact 的可点击链接，方便直接跳到 JUnit、摘要或诊断图下载页。
当后续运行恢复通过时，这条固定失败 comment 会自动更新为“已恢复通过”，避免 PR 页面残留过期告警。
失败或恢复 comment 现在还会带上本次 GitHub Actions run 的直达链接和 run 编号，方便 reviewer 直接跳转到对应构建。

## 正式基线

| 基线文件 | 视口 | 覆盖链路 | 对应测试 |
| --- | --- | --- | --- |
| `tests/baselines/experiment-center.png` | `桌面 1440x2200` | 实验中心摘要、回归钻取、报告联动 | `test_experiment_center_visual_regression` |
| `tests/baselines/qa-evidence-workflow.png` | `桌面 1440x2200` | 问答工作流 + 证据浏览 | `test_qa_and_evidence_visual_regression` |
| `tests/baselines/report-panel.png` | `桌面 1440x2200` | 报告查看 + 报告导航 + 恢复完整报告 | `test_report_panel_visual_regression` |
| `tests/baselines/mobile-experiment-center.png` | `移动端 430x2400` | 实验中心主链路 | `test_mobile_experiment_center_visual_regression` |
| `tests/baselines/tablet-qa-evidence-workflow.png` | `平板 900x2400` | 问答工作流 + 证据浏览 | `test_tablet_qa_and_evidence_visual_regression` |
| `tests/baselines/tablet-report-panel.png` | `平板 900x2400` | 报告查看 + 报告导航 + 恢复完整报告 | `test_tablet_report_panel_visual_regression` |

这些基线都由 [tests/test_e2e_visual_regression.py](/Users/xioshark/Desktop/rag/tests/test_e2e_visual_regression.py) 驱动，实际像素对比由 [tests/visual_regression.py](/Users/xioshark/Desktop/rag/tests/visual_regression.py) 执行。

## 失败诊断产物

以下文件不是正式基线，只在视觉回归失败时作为排障材料出现：

| 产物模式 | 用途 | 生成位置 |
| --- | --- | --- |
| `tests/baselines/*.actual.png` | 保存当前测试实际截图 | `assert_visual_match(...)` |
| `tests/baselines/*.diff.png` | 高亮像素差异区域 | `assert_visual_match(...)` |

当前目录里如果看到 `*.actual.png`、`*.diff.png` 这一类文件，应视为历史诊断产物，而不是需要长期维护的正式基线。
当同名视觉回归重新通过，或者基线被刷新后，`assert_visual_match(...)` 会自动清理这两类过期诊断产物。
`tests/test_visual_baseline_manifest.py` 也会直接校验当前工作区没有残留诊断产物，避免把历史失败截图误当成正式资产。

## 更新基线

只有在以下情况才应该更新基线：

1. 页面样式或布局有意改变，且变化经过确认。
2. 测试归一化逻辑调整后，旧基线不再反映真实稳定状态。
3. 新增了新的视觉回归用例，需要首次生成基线。

更新命令：

```bash
UPDATE_VISUAL_BASELINES=1 python3 -m pytest -q tests/test_e2e_visual_regression.py
```

如果当前机器不是 Linux，还需要显式加上：

```bash
ALLOW_NON_LINUX_VISUAL_REGRESSION=1 UPDATE_VISUAL_BASELINES=1 python3 -m pytest -q tests/test_e2e_visual_regression.py
```

如果只想更新单条基线，优先使用 `-k` 限定到具体测试函数。

## 排障步骤

当视觉回归失败时，按下面顺序处理：

1. 先看报错里指向的 `baseline`、`actual`、`diff` 路径。
2. 打开 `.diff.png`，确认是预期改动还是非预期抖动。
3. 如果是动态字段导致的噪声，优先补归一化逻辑，不直接刷新基线。
4. 如果是预期 UI 改动，确认对应 README / 任务日志也需要同步，再更新基线。
5. 成功修复并重新跑过对应用例后，同名旧诊断产物会自动被清理。
6. 如果目录里还留着更早历史的诊断产物，可手工清理，避免和正式基线混淆。

清理命令：

```bash
rm -f tests/baselines/*.actual.png tests/baselines/*.diff.png
```

## 维护约束

- 新增视觉基线时，必须同时更新这份清单和 README 的汇总描述。
- 新增或调整正式基线后，优先执行 `python3 scripts/render_visual_regression_baselines.py --write` 重建本文。
- 正式基线文件名应和测试函数覆盖范围一致，避免出现语义不清的图片名。
- 失败诊断产物不应写进正式清单数量统计。
