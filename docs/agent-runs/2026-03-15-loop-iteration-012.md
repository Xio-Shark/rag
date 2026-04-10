# 2026-03-15 持续循环迭代 012

- 任务名称：持续循环迭代 012
- 项目类型：C 成熟项目优化 / 重构
- 次类型：D 故障排查支撑能力增强
- 风险等级：R2

## 正式执行前说明

- 目标：
  - 基于当前 `output/agent-loop/` 的真实运行态与队列，完成一个最小但有价值的连续循环可观测性/恢复性增量。
  - 优先减少“活动轮次长期不收尾”场景下的人肉排障成本，为下一轮会话提供更清晰的事实源。
- 非目标：
  - 不修复外部网络、DNS、代理或 Codex 端点连通性。
  - 不重写连续循环架构，不引入新的守护进程或外部依赖。
- 约束：
  - 仅以仓库文件与本地命令结果为事实源。
  - 必须先完成方案、测试计划，再进入实现。
  - 结束前必须更新 `output/agent-loop/TASK_QUEUE.md`、`output/agent-loop/NEXT_ACTION.md`、`output/agent-loop/LOOP_MEMORY.md`。
- 风险：
  - 改动位于连续循环控制面，若状态机判断错误，可能影响恢复链路与交接信息。
  - 当前真实运行态可能来自旧进程，新增逻辑需要重启或下一次恢复后才会完全生效。
- 验收标准：
  - 本轮选定增量有明确测试覆盖。
  - 文档、任务日志与交接文件同步更新。
  - 验证命令与改动范围匹配，并记录结果。

## 仓库探测结果

- 已存在项：
  - README：`README.md`
  - 架构文档：`ARCHITECTURE.md`
  - 实施计划：`IMPLEMENTATION_PLAN.md`
  - 测试框架：`pytest`、`tests/`
  - CI：`.github/workflows/`
  - 环境变量模板：`.env.example`
  - 日志机制：`output/agent-loop/*.log`、`output/agent-loop/iterations/*/events.jsonl`
  - 迁移机制：`migrations/`、`alembic.ini`
  - 回滚方式：`RUNBOOK.md`
- 缺失项：
  - 统一特性开关机制
  - 连续循环缺少“活动轮次最后一次进展时间”字段，导致看到 `active_iteration` 长时间存在时，难以快速区分“子会话仍在产生活动”与“主循环只是在等待/疑似卡住”
- 本轮必须先补齐的项：
  - 补全方案对比、测试计划、实现记录、验证结果与回滚说明。
  - 为活动轮次补一个轻量心跳时间戳，并把它暴露到 handoff / watch 进度摘要中。

## 运行态证据

- 已读取 `output/agent-loop/GOAL.md`、`TASK_QUEUE.md`、`NEXT_ACTION.md`、`LOOP_MEMORY.md`、`state.json`。
- 当前 `state.json` 显示：
  - `status=running`
  - `iteration_count=11`
  - `loop_pid=45759`
  - `active_iteration=12`
  - `active_child_pid=45760`
  - `active_iteration_attempt=1`
- `output/agent-loop/iterations/012/events.jsonl` 已持续写入当前会话事件，说明当前目录里的 `active_iteration=12` 对应的正是本轮正在运行的子会话，而不是上一次失败残留目录。
- 当前 sandbox 下 `ps` 不可用，但 `lsof -p 45759` 可见主循环进程仍持有 `iterations/012/events.jsonl` 文件句柄；现有状态字段已经能证明“有活跃轮次”，但还不能直接回答“最近一次有进展是什么时候”。
- 因此本轮把增量收敛为：为活动轮次增加 `active_iteration_last_progress_at`，在子会话启动和产生日志时更新，减少人工从文件 mtime 或长日志中倒推的成本。

## 方案对比

- 方案 A：仅更新任务日志 / 交接文档，记录“012 是当前活跃子会话”的新证据，不改脚本。
  - 复杂度：最低
  - 性能：无额外开销
  - 成本：低
  - 侵入性：低
  - 兼容性：高
  - 维护成本：中，后续仍需人工比对 `events.jsonl` mtime
  - 回滚难度：低
- 方案 B：在 `state.json` 中新增活动轮次最后进展时间，并在 handoff / watch 进度摘要里展示。
  - 复杂度：低到中
  - 性能：低；仅在子会话启动与产生日志行时按秒级节流落盘
  - 成本：低
  - 侵入性：低，改动限定在连续循环 harness
  - 兼容性：高，可对旧 `state.json` 自动补字段
  - 维护成本：低，字段语义直接，便于下一轮会话接手
  - 回滚难度：低
- 推荐方案：
  - 采用方案 B，以最小控制面增量显式记录“当前轮次最近一次仍在推进的时间”。
- 是否需要 ADR：
  - 否。本轮不引入新基础设施、不修改数据库、不改认证授权，也不重构核心业务链路。

## 测试计划

- 验收测试：
  1. 补充状态默认值 / 兼容回填测试，确保旧 `state.json` 会自动补 `active_iteration_last_progress_at`。
- 回归测试：
  2. 补充 handoff 测试，确保活动轮次存在时会同时展示 `attempt`、`child_pid` 与 `last_progress_at`。
  3. 补充 watch 进度摘要测试，确保进度报告会带出活动轮次最近进展时间。
- 边界测试：
  4. 补充 `mark_iteration_started()` / `clear_active_iteration()` 测试，确保新增字段启动时清空、结束时复位。
- 集成测试：
  5. 复用 fake codex 的 non-dry-run 测试，验证活动轮次运行中可以观测到 `active_iteration_last_progress_at`，结束后会清空。
- 实现后验证命令：
  6. `python3 -m pytest -q tests/test_continuous_task_loop.py`
  7. `python3 -m ruff check scripts/continuous_task_loop.py tests/test_continuous_task_loop.py`
  8. `PYTHONPYCACHEPREFIX=/tmp/rag-pyc python3 -m compileall scripts tests`

## 实施步骤

1. 先补测试与状态兼容断言，覆盖新增进展时间字段。
2. 在 `scripts/continuous_task_loop.py` 中为活动轮次新增 `active_iteration_last_progress_at`，并在子会话启动 / 流式输出时更新。
3. 把该字段接入 handoff 与 watch 进度摘要，方便人工快速判断“最近是否仍有推进”。
4. 更新 `README.md`、`RUNBOOK.md`、`docs/continuous-task-loop.md`、任务日志与运行态交接文件。

## 实施记录

- 基于当前真实运行态追加了一条关键事实：`output/agent-loop/iterations/012/events.jsonl` 中记录的正是本轮会话事件，因此当前 `active_iteration=12` 属于 live child，而非陈旧失败目录。
- 在 `scripts/continuous_task_loop.py` 中为活动轮次新增 `active_iteration_last_progress_at` 字段，并对旧 `state.json` 自动回填默认值。
- 在子会话启动与流式输出时更新该字段；同一秒内重复输出不会重复写 `state.json`，避免长日志场景过度刷盘。
- `build_handoff_prompt()` 现在会在活动轮次提示中额外展示 `last_progress_at`；`build_watch_progress_report()` 现在会输出 `active_last_progress=`。
- 已同步更新 `tests/test_continuous_task_loop.py`、`README.md`、`RUNBOOK.md`、`docs/continuous-task-loop.md`。

## 验证结果

- `python3 -m pytest -q tests/test_continuous_task_loop.py`：`29 passed`
- `python3 -m ruff check scripts/continuous_task_loop.py tests/test_continuous_task_loop.py`：通过
- `PYTHONPYCACHEPREFIX=/tmp/rag-pyc python3 -m compileall scripts tests`：通过

## 关键决策

- 不把“活动轮次看起来很久没结束”直接视为脚本缺陷；先承认当前 `state.json` 只能表达“正在运行”，再最小化补一个“最近进展时间”来减少误判。
- 不引入额外守护线程、sidecar 文件或 attempt 子目录；继续沿用 `state.json` 作为主事实源。
- 进展心跳选择秒级 UTC 时间戳而不是每行强制刷盘，兼顾可观测性与 I/O 开销。

## 变更文件

- `scripts/continuous_task_loop.py`
- `tests/test_continuous_task_loop.py`
- `README.md`
- `RUNBOOK.md`
- `docs/continuous-task-loop.md`
- `docs/agent-runs/2026-03-15-loop-iteration-012.md`
- `output/agent-loop/TASK_QUEUE.md`
- `output/agent-loop/NEXT_ACTION.md`
- `output/agent-loop/LOOP_MEMORY.md`

## 风险清单

- 进展时间若落盘过于频繁，可能让长日志轮次产生额外 I/O；实现时需做秒级节流，避免每一行都重写状态文件。
- 新字段只反映“最近一次子会话启动或输出时间”，不能替代真正的业务成功判定。
- 当前真实外部阻塞仍可能来自网络 / 端点，新增字段只能增强可观测性，不能保证主循环本身成功。

## 未覆盖项

- 未在真实可连通的 Codex 端点环境里复跑完整恢复链路。
- 当前 sandbox 仍不允许 `ps`，因此进程树级排查能力依旧受限；本轮用状态心跳降低这一限制的影响。

## 回滚步骤

1. 回退 `scripts/continuous_task_loop.py`、`tests/test_continuous_task_loop.py`、`README.md`、`RUNBOOK.md`、`docs/continuous-task-loop.md` 与本轮任务日志 / 交接文件。
2. 重新运行本轮针对性验证，确认恢复到上一稳定状态。

## 上线检查项

- 确认活动轮次开始后，`state.json` 会出现 `active_iteration_last_progress_at`。
- 确认 handoff 在活动轮次场景下会展示 `attempt`、`child_pid`、`last_progress_at`。
- 确认 watch 模式的进度摘要包含 `active_last_progress=`，便于守护场景直接判断最近是否仍有推进。

## 后续建议

- 下一轮优先在真实 `output/agent-loop/` 运行目录里观察 `active_iteration_last_progress_at` 是否随 `events.jsonl` 同步推进，确认它是否足以支撑“仍在推进 / 疑似卡住”的一线判断。
- 若外部端点恢复连通，可在新 `state-dir` 上复跑一次真实 non-dry-run 单轮/恢复链路，验证新增心跳字段在真实失败与恢复场景里的表现。
