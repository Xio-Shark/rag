# 2026-03-14 视觉回归 Comment 收敛与 Run 可追溯

- 任务名称：视觉回归失败 Comment 自动收敛与 Run 可追溯
- 项目类型：C 成熟项目优化 / 重构
- 次类型：B 现有项目新增功能
- 风险等级：R1

## 正式执行前说明

- 目标：
  - 当 visual-regression-e2e 在同仓库 PR 上从失败恢复为通过时，自动收敛旧失败 comment。
  - 避免 reviewer 在 PR 页面长期看到已过期的失败告警。
  - 让失败或恢复后的固定 comment 直接带上本次 GitHub Actions run 链接和编号。
  - 保持现有失败诊断图、job summary、artifact 和固定 comment 机制继续有效。
- 非目标：
  - 不修改视觉回归测试内容、基线或阈值。
  - 不删除现有基线同步 workflow 的摘要 comment 逻辑。
- 约束：
  - 继续复用 `actions/github-script@v8` 和固定 comment 标记。
  - fork PR 仍需跳过评论步骤。
  - 优先做“更新为已恢复状态”，不直接删除 comment。
  - run 链接必须直接从 GitHub Actions 上下文拼出，避免引入额外依赖。
- 风险：
  - 若 comment 生命周期逻辑处理不好，可能在失败和成功之间来回抖动。
  - workflow 文本断言会继续增加，需要同步维护。
  - run 链接与编号模板若拼装错误，会让 comment 可读但不可跳转。
- 验收标准：
  - visual-regression-e2e 失败时仍会更新失败摘要 comment。
  - visual-regression-e2e 成功时，若存在旧失败 comment，则会更新为已恢复状态。
  - 失败和恢复 comment 都包含 run 链接、run 编号和 attempt。
  - 相关测试与全量 pytest 通过。
- 当前项目类型：C 成熟项目优化 / 重构
- 当前风险等级：R1
- 仓库现状：
  - 已存在：失败 PR comment、artifact 链接、job summary、固定 comment 标记、成功后的自动收敛逻辑
  - 缺失：comment 内对具体构建 run 的直接可追溯入口
- 缺失机制清单：
  - comment 内 run 链接与编号模板
  - 对 run 可追溯信息的 workflow 断言
- 方案对比：
  - 方案 A：成功时更新同一条固定 comment 为“已恢复通过”，并保留必要链接。复杂度低，推荐。
  - 方案 B：成功时直接删除旧 comment。实现也可行，但历史上下文完全丢失。
  - 方案 C：不做收敛，让旧失败 comment 一直保留。会持续误导 reviewer。
- 推荐方案：方案 A。
- 是否需要 ADR：否。
- 测试计划：
  - 先补 workflow 文本断言。
  - 运行 `python3 scripts/render_visual_regression_baselines.py --write`
  - 运行 `python3 -m pytest -q tests/test_visual_baseline_manifest.py`
  - 运行 `python3 -m ruff check app tests`
  - 运行 `python3 scripts/render_visual_regression_baselines.py --check`
  - 运行 `python3 -m pytest -q`

## 实施记录

- 方案摘要：
  - 将 visual-regression-e2e 的 PR comment step 改为 `if: always()`，让它在成功和失败场景都参与 comment 生命周期管理。
  - 失败时沿用现有失败诊断摘要 + artifact 链接逻辑；成功时若存在旧失败 comment，则更新为“已恢复通过”状态。
  - 成功收敛场景下保留 JUnit 链接，便于 reviewer 直接跳到最近一次通过的结构化测试结果。
  - 在失败和恢复两类 comment 中都追加当前 run 的直达链接、run 编号和 attempt，补齐 reviewer 的跳转入口。
- 关键决策：
  - 不删除旧失败 comment，而是更新同一条固定 comment，避免上下文丢失。
  - 成功时仅在“已存在旧失败 comment”前提下更新，不主动新建成功评论。
  - fork PR 仍然跳过 comment step，避免 token 权限问题。
  - run 可追溯信息直接由 `github.run_id`、`github.run_number` 和 `github.run_attempt` 组装，保持 workflow 自包含。
- 变更文件：
  - `.github/workflows/visual-regression-e2e.yml`
  - `tests/test_visual_baseline_manifest.py`
  - `scripts/render_visual_regression_baselines.py`
  - `README.md`
  - `docs/visual-regression-baselines.md`
  - `docs/agent-runs/2026-03-14-visual-regression-comment-resolution.md`
- 风险与未覆盖项：
  - 本地无法直接实跑 GitHub PR comment 的真实生命周期，只能通过 workflow 文本断言和全量测试间接验证。
  - 成功收敛逻辑当前只处理固定标记 comment，不会清理人工评论或其他机器人评论。
  - run 链接的真实跳转体验仍然只能在 GitHub Actions 环境里最终确认。
- 回滚方式：
  - 回退 visual-regression-e2e workflow 中新增的 comment 收敛和 run 可追溯逻辑，以及对应测试断言

## 验证结果

- `python3 scripts/render_visual_regression_baselines.py --write`：通过，已重建文档
- `python3 -m pytest -q tests/test_visual_baseline_manifest.py`：通过，`12 passed`
- `python3 -m ruff check app tests`：通过
- `python3 scripts/render_visual_regression_baselines.py --check`：通过，`视觉基线清单已和 manifest 同步`
- `python3 -m pytest -q`：通过，`42 passed`
