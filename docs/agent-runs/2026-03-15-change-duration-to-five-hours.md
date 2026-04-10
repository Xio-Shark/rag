# 2026-03-15 任务持续时间改为五小时

- 任务名称：任务持续时间改为五小时
- 项目类型：B 现有项目新增功能
- 次类型：C 运行参数调整
- 风险等级：R1

## 正式执行前说明

- 目标：
  - 将当前正在运行的长时任务持续时间从 10 小时调整为 5 小时。
  - 保持现有任务队列和目标不变，只修改运行时间窗。
- 非目标：
  - 不修改业务代码。
  - 不重置任务队列、handoff、历史文档。
  - 不改变当前任务目标和验收条件。
- 约束：
  - 当前任务处于运行中，不能只改文档或下一次启动命令。
  - 需要同时更新运行态里的 `duration_hours` 与 `deadline_at`，否则会继续沿用旧窗口。
- 风险：
  - 若只重启进程不更新 `state.json`，实际截止时间不会变化。
  - 若停止 watch 后未清理当前 loop，可能残留孤儿进程继续占用同一 `state-dir`。
- 验收标准：
  - `state.json` 中 `duration_hours` 变为 `5.0`
  - `deadline_at` 变为“当前执行时刻后约 5 小时”
  - 新 loop 继续运行，且 `ps` 可见
- 当前项目类型：
  - 主类型：B 现有项目新增功能
  - 次类型：C 运行参数调整
- 当前风险等级：
  - R1：只调整现有自动任务的运行参数和运行态
- 仓库现状：
  - 已存在：`continuous_task_loop.py`、watch 模式、`state.json`、`TASK_QUEUE.md`
  - 缺失：无
- 缺失机制清单：
  - 无新增机制；本轮只做运行参数切换
- 方案对比：
  - 方案 A：只改重启命令，不改 `state.json`。实现最简单，但结果不正确。
  - 方案 B：停任务、更新 `state.json` 时间窗、按 5 小时参数重启。结果正确，风险最低。
- 推荐方案：
  - 采用方案 B。
- 是否需要 ADR：
  - 否。
- 测试计划：
  - 验证旧进程已停止
  - 验证 `state.json` 的 `duration_hours` 与 `deadline_at`
  - 验证新进程已启动并继续运行
- 实施步骤：
  - 停止当前 watch 与 loop
  - 调整 `state.json` 时间窗
  - 以 5 小时参数重启并验证

## 实施记录

- 方案摘要：
  - 停止原先按 10 小时窗口运行的 watch / loop。
  - 将 `output/agent-loop/state.json` 中的 `duration_hours` 改为 `5.0`，并把 `deadline_at` 更新为执行时刻后 5 小时。
  - 保留原有任务目标、队列和历史记录，重新以前台长会话方式启动 `continuous_task_loop.py --watch`。
- 关键决策：
  - 不重置 `history`、`iteration_count` 和任务队列，只切换运行时间窗。
  - 将当前状态先标记为 `interrupted` 并清空活动进程字段，再按 5 小时参数恢复，避免旧进程与新进程争抢同一 `state-dir`。
- 变更文件：
  - `output/agent-loop/state.json`
  - `docs/agent-runs/2026-03-15-change-duration-to-five-hours.md`

## 实施结果

- 当前任务持续时间已从 10 小时切换为 5 小时。
- 新的截止时间为 `2026-03-15T01:35:39Z`，即北京时间 `2026-03-15 09:35:39 CST`。
- 新 loop 已恢复运行，仍沿用原任务目标和队列，当前活动轮次为 `13`，尝试次数为 `2`。

## 风险清单

- 当前 `started_at` 保留了原运行窗口的历史开始时间，因此它不再等于“本次 5 小时窗口”的起点；真正的当前窗口以新的 `deadline_at` 为准。
- 如果外部 Codex 端点继续不稳定，5 小时窗口内仍可能再次触发恢复与重试。

## 未覆盖项

- 未重写 README / RUNBOOK；本轮是一次运行中的参数调整，不是默认配置变更。
- 未重置历史轮次统计，保留了已有观测数据。

## 验证结果

- 已确认旧进程 `45759` / `46342` 已停止。
- 已确认 `output/agent-loop/state.json` 中：
  - `duration_hours = 5.0`
  - `deadline_at = 2026-03-15T01:35:39Z`
  - `loop_pid = 46613`
  - `active_iteration = 13`
- 已通过 `ps` 确认新进程命令行为：
  - `python3 .../scripts/continuous_task_loop.py ... --duration-hours 5.0 ...`

## 上线检查项

- 如需继续通过 `/ps` 查看，当前应查看新的 loop PID `46613`。
- 如果后续还要调整为其他时长，建议同样采用“停旧进程 -> 改运行窗 -> 重启”的方式。

## 回滚步骤

1. 停止当前 5 小时会话。
2. 将 `output/agent-loop/state.json` 中的 `duration_hours` 和 `deadline_at` 恢复为期望值。
3. 按新的目标时长重新启动 watch / loop。

## 后续建议

- 如果后面经常需要动态改运行窗，可以考虑在 `continuous_task_loop.py` 或 `project_autopilot.py` 里补一个正式的 `retime` 子命令，而不是手动改运行态。
