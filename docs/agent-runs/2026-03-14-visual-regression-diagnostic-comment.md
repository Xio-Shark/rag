# 2026-03-14 视觉回归失败诊断 Comment

- 任务名称：视觉回归失败诊断摘要写入 PR Comment
- 项目类型：C 成熟项目优化 / 重构
- 次类型：B 现有项目新增功能
- 风险等级：R1

## 正式执行前说明

- 目标：
  - 把视觉回归 E2E workflow 的失败诊断摘要同步到同仓库 PR comment。
  - 让 reviewer 不进入 Actions 页面也能看到失败基线对应的视口、覆盖链路和测试名。
- 非目标：
  - 不发布逐行 review comment。
  - 不修改失败诊断 artifact 上传逻辑。
- 约束：
  - 复用现有 `actions/github-script` 方案，不新增第三方依赖。
  - fork PR 需要显式跳过评论，避免 token 权限问题。
- 风险：
  - 若同时存在多种评论机器人，固定 comment 标记需要足够稳定，避免误更新。
  - 本地无法直接实跑 GitHub PR comment 流程，只能通过 workflow 文本断言验证。
- 验收标准：
  - visual-regression-e2e workflow 在失败且为同仓库 PR 时，会创建或更新固定 comment。
  - comment 内容来自失败诊断摘要，而不是 shell 手拼文本。
  - 相关测试和全量 pytest 通过。
- 当前项目类型：C 成熟项目优化 / 重构
- 当前风险等级：R1
- 仓库现状：
  - 已存在：失败诊断摘要 CLI、job summary 输出、sync workflow 的固定 PR comment 模式
  - 缺失：visual-regression-e2e workflow 的失败 PR comment
- 缺失机制清单：
  - 失败诊断摘要固定 comment
  - 对 visual-regression-e2e comment 行为的测试守卫
- 方案对比：
  - 方案 A：复用 `actions/github-script`，按隐藏标记更新固定 comment。复杂度低，推荐。
  - 方案 B：只保留 job summary，不写 PR comment。实现更简单，但 reviewer 可见性不足。
  - 方案 C：引入第三方 action 管理评论。超出最小门禁范围。
- 推荐方案：方案 A。
- 是否需要 ADR：否。
- 测试计划：
  - 先补 workflow 文本断言。
  - 运行 `python3 -m pytest -q tests/test_visual_baseline_manifest.py`
  - 运行 `python3 -m ruff check app tests`
  - 运行 `python3 -m pytest -q`

## 实施记录

- 方案摘要：
  - 在 `visual-regression-e2e.yml` 的失败摘要 step 中生成临时 summary 文件，并把路径通过 `GITHUB_OUTPUT` 传给后续步骤。
  - 对同仓库 PR 且 workflow 失败的场景，新增 `actions/github-script@v8` step，按隐藏标记更新固定 comment。
  - 同步 README、清单文档和渲染模板说明，明确失败摘要现在会进入 PR comment。
- 关键决策：
  - 复用 sync workflow 已验证过的固定 comment 模式，不再引入新的 comment 机制。
  - 失败 comment 仍然只在同仓库 PR 场景启用，fork PR 保持跳过。
  - comment 内容继续来自 `--diagnostic-summary` 的脚本输出，避免 workflow 内再维护一份 shell 拼装逻辑。
- 变更文件：
  - `.github/workflows/visual-regression-e2e.yml`
  - `tests/test_visual_baseline_manifest.py`
  - `scripts/render_visual_regression_baselines.py`
  - `README.md`
  - `docs/visual-regression-baselines.md`
  - `docs/agent-runs/2026-03-14-visual-regression-diagnostic-comment.md`
- 风险与未覆盖项：
  - 当前本地无法直接实跑 GitHub PR comment，只能通过 workflow 文本断言和全量测试间接验证。
  - 这条 comment 使用 issue comment API，不会生成逐行 review comment。
  - fork PR 仍然只会看到 artifact 和 job summary，不会收到自动 comment。
- 回滚方式：
  - 回退 visual-regression-e2e workflow 中新增的 PR comment step 与对应测试断言

## 验证结果

- `python3 scripts/render_visual_regression_baselines.py --write`：通过，已重建文档
- `python3 -m pytest -q tests/test_visual_baseline_manifest.py`：通过，`12 passed`
- `python3 -m ruff check app tests`：通过
- `python3 -m pytest -q`：通过，`42 passed`
