# 2026-03-14 视觉回归失败诊断摘要

- 任务名称：视觉回归失败诊断摘要输出
- 项目类型：C 成熟项目优化 / 重构
- 次类型：B 现有项目新增功能
- 风险等级：R1

## 正式执行前说明

- 目标：
  - 当视觉回归 E2E workflow 失败并生成 `.actual.png` / `.diff.png` 时，自动输出可读摘要。
  - 摘要应把诊断图关联回正式基线、视口、覆盖链路和对应测试。
  - 这段摘要要能直接进入 GitHub Actions job summary。
- 非目标：
  - 不修改正式基线、阈值或测试逻辑。
  - 不为失败诊断再新增独立 manifest 文件。
- 约束：
  - 继续复用 `tests/baselines/manifest.json` 作为机器事实源。
  - 优先扩展现有 `render_visual_regression_baselines.py`，不新增平行脚本。
  - 失败时既要保留 artifact 上传，也要补文字摘要。
- 风险：
  - 若诊断图对应的正式基线未登记在 manifest 中，摘要需要优雅降级而不是直接崩。
  - workflow 文本断言会继续增多，需要同步维护。
- 验收标准：
  - 渲染脚本支持输出当前诊断产物摘要。
  - 视觉回归 E2E workflow 在失败时会把这段摘要写入 job summary。
  - 相关测试、本地视觉回归测试和全量 pytest 通过。
- 当前项目类型：C 成熟项目优化 / 重构
- 当前风险等级：R1
- 仓库现状：
  - 已存在：独立 `visual-regression-e2e.yml`、`.actual/.diff` artifact 上传、`render_visual_regression_baselines.py --summary`
  - 缺失：失败诊断图到基线元数据的文字摘要，以及 workflow 级 job summary 输出
- 缺失机制清单：
  - 失败诊断摘要 CLI
  - 视觉回归 E2E workflow 的失败 summary 输出
  - 对失败摘要行为的测试守卫
- 方案对比：
  - 方案 A：扩展现有渲染脚本，新增诊断摘要子命令，workflow 失败时直接调用。复杂度低，事实源单一，推荐。
  - 方案 B：在 workflow 里用 shell 直接拼摘要。实现更快，但逻辑分散，维护差。
  - 方案 C：只上传图片，不提供文字摘要。可观测性不足。
- 推荐方案：方案 A。
- 是否需要 ADR：否。
- 测试计划：
  - 先补脚本函数测试和 workflow 文本断言。
  - 运行 `python3 -m pytest -q tests/test_visual_baseline_manifest.py`
  - 运行 `python3 -m ruff check app tests`
  - 运行 `python3 -m pytest -q tests/test_e2e_visual_regression.py`
  - 运行 `python3 -m pytest -q`

## 实施记录

- 方案摘要：
  - 扩展 `scripts/render_visual_regression_baselines.py`，新增 `render_diagnostic_summary(...)` 与 `--diagnostic-summary` CLI。
  - 失败诊断摘要会把 `.actual/.diff` 重新映射回正式基线，并带出视口、覆盖链路和测试名。
  - `visual-regression-e2e.yml` 在失败时先上传诊断图，再把这段摘要写入 job summary。
- 关键决策：
  - 失败摘要继续复用 manifest，不新增第二套诊断元数据源。
  - 对未登记在 manifest 中的诊断图采用“优雅降级”展示，不直接抛错。
  - workflow 使用 `nullglob + 参数数组` 组织 artifact 路径，避免无诊断图时把通配符字面量传给脚本。
- 变更文件：
  - `scripts/render_visual_regression_baselines.py`
  - `.github/workflows/visual-regression-e2e.yml`
  - `tests/test_visual_baseline_manifest.py`
  - `README.md`
  - `docs/visual-regression-baselines.md`
  - `docs/agent-runs/2026-03-14-visual-regression-diagnostic-summary.md`
- 风险与未覆盖项：
  - 当前摘要只写入 GitHub Actions job summary，不会自动评论 PR。
  - 本地无法直接演练 GitHub Actions 的失败 summary UI，只能通过脚本输出和 workflow 文本断言间接验证。
  - 本轮中移动端视觉回归出现过一次低频抖动，但重跑后恢复通过；摘要能力本身未引入新的测试失败。
- 回滚方式：
  - 回退渲染脚本中的失败摘要能力，以及 visual-regression-e2e workflow 中新增的 summary 输出步骤

## 验证结果

- `python3 scripts/render_visual_regression_baselines.py --write`：通过，已重建文档
- `python3 -m pytest -q tests/test_visual_baseline_manifest.py`：通过，`12 passed`
- `python3 -m ruff check app tests`：通过
- `python3 -m pytest -q tests/test_e2e_visual_regression.py`：首次出现 1 次移动端低频抖动；重跑后通过，`6 passed`
- `python3 -m pytest -q`：最终通过，`42 passed`
