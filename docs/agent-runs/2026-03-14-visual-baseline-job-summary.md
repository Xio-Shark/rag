# 2026-03-14 视觉基线 Job Summary / PR Comment

- 任务名称：视觉基线变更摘要写入 Job Summary / PR Comment
- 项目类型：C 成熟项目优化 / 重构
- 次类型：B 现有项目新增功能
- 风险等级：R1

## 正式执行前说明

- 目标：
  - 把视觉基线变更摘要从 step 日志提升到 GitHub Actions job summary。
  - 让 reviewer 在 Action 页面首屏即可看到基线变更对应的测试、视口和覆盖链路。
- 非目标：
  - 不发布逐行代码 review comment。
  - 不修改 manifest、基线文件或视觉阈值。
- 约束：
  - 继续复用现有 `--summary/--path` 能力。
  - 优先保持 workflow 逻辑简单，不引入额外 action 依赖。
- 风险：
  - 若 `GITHUB_STEP_SUMMARY` 不可用，workflow 仍需至少保留控制台输出。
  - 文本断言需要跟随 workflow 小改动同步维护。
- 验收标准：
  - workflow 会把变更摘要追加到 `GITHUB_STEP_SUMMARY`。
  - 对同仓库 PR，workflow 会创建或更新一条固定 PR comment。
  - 无变更或缺少 diff 基线时，job summary 也会写出明确提示。
  - 相关测试与全量 pytest 通过。
- 当前项目类型：C 成熟项目优化 / 重构
- 当前风险等级：R1
- 仓库现状：
  - 已存在：`scripts/render_visual_regression_baselines.py --summary`、`.github/workflows/visual-baseline-sync.yml`、`tests/test_visual_baseline_manifest.py`
  - 缺失：基线变更摘要写入固定 PR comment 的 workflow 行为和对应断言
- 方案对比：
  - 方案 A：在现有 step 基础上保留 job summary，并增加官方 `actions/github-script` step 更新固定 PR comment。复杂度低，推荐。
  - 方案 B：只写 job summary，不做 PR comment。实现更简单，但 reviewer 可见性仍然有限。
  - 方案 C：引入第三方 action 发布评论。能力更强，但超出当前最小门禁范围。
- 推荐方案：方案 A。
- 是否需要 ADR：否。
- 测试计划：
  - 更新 workflow 文本断言。
  - 运行 `python3 -m pytest -q tests/test_visual_baseline_manifest.py`
  - 运行 `python3 -m ruff check app tests`
  - 运行 `python3 -m pytest -q`

## 实施记录

- 方案摘要：
  - 复用现有“打印变更基线摘要”step，在同一段 bash 里新增 `write_summary()`，把文本同时输出到控制台、`GITHUB_STEP_SUMMARY` 和临时摘要文件。
  - 对 pull request 且来源不是 fork 的场景，增加 `actions/github-script@v8` step，按隐藏标记查找并更新固定 PR comment。
  - 对“无 diff 基线”和“缺少 base sha”两种分支也统一生成摘要文件，避免 comment step 和 job summary 看到空白内容。
- 关键决策：
  - 保留控制台输出，确保即使 `GITHUB_STEP_SUMMARY` 不可用也不会丢失摘要信息。
  - PR comment 采用“更新同一条固定 comment”而不是重复追加，避免评论刷屏。
  - fork PR 明确跳过评论步骤，避免只读 `GITHUB_TOKEN` 失败。
  - 继续用文本断言保护 workflow 关键行为，不引入更重的 workflow 测试框架。
- 变更文件：
  - `.github/workflows/visual-baseline-sync.yml`
  - `tests/test_visual_baseline_manifest.py`
  - `scripts/render_visual_regression_baselines.py`
  - `README.md`
  - `docs/visual-regression-baselines.md`
  - `docs/agent-runs/2026-03-14-visual-baseline-job-summary.md`
- 风险与未覆盖项：
  - 当前 comment 采用 issue comment API，不会产生逐行 review comment。
  - fork PR 仍然只会看到 job summary 和 step 日志，不会收到自动 PR comment。
  - 由于本地不是 git 仓库，本轮无法直接实跑 GitHub job summary / PR comment，只能通过 workflow 文本断言和脚本输出间接验证。
- 回滚方式：
  - 回退 workflow 中对 `GITHUB_STEP_SUMMARY` 的写入逻辑与对应测试断言
  - 若需要彻底回退本轮扩展，再移除 `actions/github-script@v8` 的 PR comment step

## 验证结果

- `python3 -m pytest -q tests/test_visual_baseline_manifest.py`：通过，`8 passed`
- `python3 scripts/render_visual_regression_baselines.py --write`：通过，已重建文档
- `python3 scripts/render_visual_regression_baselines.py --check`：通过
- `python3 -m ruff check app tests`：通过
- `python3 -m pytest -q`：通过，`38 passed`
