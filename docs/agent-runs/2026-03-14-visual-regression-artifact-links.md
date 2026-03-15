# 2026-03-14 视觉回归 Artifact 链接

- 任务名称：视觉回归失败 PR Comment Artifact 链接
- 项目类型：C 成熟项目优化 / 重构
- 次类型：B 现有项目新增功能
- 风险等级：R1

## 正式执行前说明

- 目标：
  - 让 visual-regression-e2e workflow 的失败 PR comment 直接带上可点击的 artifact 链接。
  - 链接至少覆盖 JUnit XML、失败诊断摘要 markdown，以及诊断图片 artifact。
  - 保持现有 job summary、artifact 上传和固定 comment 更新逻辑继续有效。
- 非目标：
  - 不改视觉回归测试内容、基线或阈值。
  - 不新增第三方 action 或外部报告平台。
- 约束：
  - 继续复用 `actions/upload-artifact@v4` 与 `actions/github-script@v8`。
  - 优先使用官方 action 输出，不手拼不稳定的 artifact ID 逻辑。
  - fork PR 仍需跳过评论步骤。
- 风险：
  - 如果某个 artifact step 没有执行或没有输出 URL，comment 需要优雅降级。
  - workflow 文本断言会继续增加，需要同步维护。
- 验收标准：
  - visual-regression-e2e workflow 的失败 PR comment 包含可点击 artifact 链接。
  - comment 在缺少部分 artifact URL 时仍能稳定更新。
  - 相关测试与全量 pytest 通过。
- 当前项目类型：C 成熟项目优化 / 重构
- 当前风险等级：R1
- 仓库现状：
  - 已存在：JUnit artifact、诊断图 artifact、失败摘要 artifact、固定 PR comment
  - 缺失：PR comment 内的 artifact 直接访问链接
- 缺失机制清单：
  - visual-regression-e2e artifact URL 输出接线
  - PR comment 链接拼装逻辑
  - 对 artifact 链接行为的测试守卫
- 方案对比：
  - 方案 A：利用 `actions/upload-artifact@v4` 输出的 URL，拼到固定 PR comment。复杂度低，推荐。
  - 方案 B：只在 comment 里写 artifact 名称，不给链接。实现更简单，但 reviewer 跳转成本仍高。
  - 方案 C：手写 GitHub artifact URL 模板和 artifact id 推导。脆弱，不推荐。
- 推荐方案：方案 A。
- 是否需要 ADR：否。
- 测试计划：
  - 先补 workflow 文本断言。
  - 运行 `python3 -m pytest -q tests/test_visual_baseline_manifest.py`
  - 运行 `python3 -m ruff check app tests`
  - 运行 `python3 -m pytest -q`

## 实施记录

- 方案摘要：
  - 为 `visual-regression-e2e.yml` 中的 JUnit、诊断图和失败摘要 artifact 上传 step 增加 `id`。
  - 通过 `actions/upload-artifact@v4` 的 `artifact-url` 输出，把可点击链接传给失败 PR comment 的 `actions/github-script@v8` step。
  - 在固定 comment 里追加 `Artifacts` 区块，按存在的 URL 动态渲染链接，缺少某个 URL 时自动降级。
- 关键决策：
  - 不自己拼 GitHub artifact 下载链接，直接复用官方 action 的 `artifact-url` 输出。
  - comment 里的链接区块只在 URL 存在时才展示，避免失败早期出现空链接。
  - 继续沿用固定 comment 更新模式，不创建额外评论线程。
- 变更文件：
  - `.github/workflows/visual-regression-e2e.yml`
  - `tests/test_visual_baseline_manifest.py`
  - `scripts/render_visual_regression_baselines.py`
  - `README.md`
  - `docs/visual-regression-baselines.md`
  - `docs/agent-runs/2026-03-14-visual-regression-artifact-links.md`
- 风险与未覆盖项：
  - 当前本地无法直接实跑 GitHub artifact URL 和 PR comment 发布，只能通过 workflow 文本断言与全量测试间接验证。
  - artifact URL 的稳定性依赖 `actions/upload-artifact@v4` 官方输出契约；如果 action 升级，需要同步复核。
- 回滚方式：
  - 回退 visual-regression-e2e workflow 中新增的 artifact URL 接线与 comment 链接拼装逻辑

## 验证结果

- `python3 scripts/render_visual_regression_baselines.py --write`：通过，已重建文档
- `python3 -m pytest -q tests/test_visual_baseline_manifest.py`：通过，`12 passed`
- `python3 -m ruff check app tests`：通过
- `python3 -m pytest -q`：通过，`42 passed`
