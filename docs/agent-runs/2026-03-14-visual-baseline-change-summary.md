# 2026-03-14 视觉基线变更摘要

- 任务名称：视觉基线变更摘要输出
- 项目类型：C 成熟项目优化 / 重构
- 次类型：B 现有项目新增功能
- 风险等级：R1

## 正式执行前说明

- 目标：
  - 当正式基线图片发生变更时，给 reviewer 和 CI 日志输出对应的测试名、视口和覆盖链路摘要。
  - 继续复用 `manifest.json` 作为唯一机器事实源。
- 非目标：
  - 不引入新的元数据文件。
  - 不修改正式基线本身或视觉阈值。
- 约束：
  - 优先复用 `scripts/render_visual_regression_baselines.py`，不新增平行脚本。
  - 在本地可测试，在 GitHub Actions 可直接运行。
- 风险：
  - workflow 依赖 `git diff`，需要完整历史可用。
  - 若变更图片未登记在 manifest 中，摘要步骤会直接失败。
- 验收标准：
  - 渲染脚本支持按路径输出基线摘要。
  - workflow 在基线 PNG 变化时会打印变更摘要。
  - 对应测试和全量 pytest 通过。
- 当前项目类型：C 成熟项目优化 / 重构
- 当前风险等级：R1
- 仓库现状：
  - 已存在：`tests/baselines/manifest.json`、`scripts/render_visual_regression_baselines.py`、`tests/test_visual_baseline_manifest.py`、`.github/workflows/visual-baseline-sync.yml`
  - 缺失：按变更基线输出 reviewer 摘要的 CLI 和 workflow 步骤
- 方案对比：
  - 方案 A：扩展现有渲染脚本，新增 `--summary/--path`，workflow 用 `git diff` 取变化图片再调用。复杂度低，事实源单一，推荐。
  - 方案 B：新增独立摘要脚本。功能可分离，但脚本边界重复，不必要。
  - 方案 C：只在文档里写人工操作说明，不做自动输出。不满足目标。
- 推荐方案：方案 A。
- 是否需要 ADR：否。
- 测试计划：
  - 先补脚本单测和 workflow 断言。
  - 运行 `python3 -m pytest -q tests/test_visual_baseline_manifest.py`
  - 运行 `python3 scripts/render_visual_regression_baselines.py --check`
  - 运行 `python3 -m ruff check app tests`
  - 运行 `python3 -m pytest -q`

## 实施记录

- 方案摘要：
  - 扩展 `scripts/render_visual_regression_baselines.py`，新增 `--summary` 与可重复传入的 `--path` 参数。
  - 在 workflow 中用 `git diff` 计算本次变更的基线 PNG，再把这些路径喂给 `--summary`，直接输出测试、视口和覆盖链路。
  - 用 manifest 测试锁定脚本摘要能力与 workflow 关键字符串，避免后续改坏。
- 关键决策：
  - 不新增独立摘要脚本，继续复用现有 manifest 渲染器。
  - workflow 只输出变更摘要，不尝试自动评论 PR 或写回文件。
  - `actions/checkout` 改为 `fetch-depth: 0`，保证 `git diff` 在 PR / push 上都能工作。
- 变更文件：
  - `scripts/render_visual_regression_baselines.py`
  - `tests/test_visual_baseline_manifest.py`
  - `.github/workflows/visual-baseline-sync.yml`
  - `README.md`
  - `docs/visual-regression-baselines.md`
  - `docs/agent-runs/2026-03-14-visual-baseline-change-summary.md`
- 风险与未覆盖项：
  - 当前摘要只覆盖 manifest 中已登记的正式基线；未登记 PNG 会让摘要步骤失败。
  - workflow 目前只把摘要打印到 job 日志，尚未做 PR comment 或 artifact 输出。
  - 由于当前工作区不是 git 仓库，`git diff` 路径选择逻辑只能通过文本断言和脚本本地调用间接验证。
- 回滚方式：
  - 回退渲染脚本中的 `--summary/--path` 能力，以及 workflow 摘要输出步骤

## 验证结果

- `python3 -m pytest -q tests/test_visual_baseline_manifest.py`：通过，`8 passed`
- `python3 scripts/render_visual_regression_baselines.py --write`：通过，已重建文档
- `python3 scripts/render_visual_regression_baselines.py --check`：通过
- `python3 scripts/render_visual_regression_baselines.py --summary --path tests/baselines/report-panel.png`：通过，输出正确摘要
- `python3 -m ruff check app tests`：通过
- `python3 -m pytest -q`：通过，`38 passed`
