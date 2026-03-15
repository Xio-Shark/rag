# 2026-03-15 自动停机未收敛排查

- 任务名称：自动停机未收敛排查
- 项目类型：D 线上问题修复
- 次类型：C 持续任务框架状态机修复
- 风险等级：R2

## 正式执行前说明

- 目标：
  - 排查 `output/agent-loop/` 对应持续任务为什么超过截止时间后没有自动停下。
  - 修复 `scripts/continuous_task_loop.py` 在进程消失后的状态收敛逻辑，避免状态永久停留在 `running`。
  - 保持现有任务队列、handoff 与运行目录结构兼容。
- 非目标：
  - 不改业务 API、数据库、检索链路或前端功能。
  - 不重写整套循环框架，不引入新的守护基础设施。
  - 不重置当前任务队列内容。
- 约束：
  - 必须兼容现有 `state.json` 字段语义。
  - 修复前先补测试，锁定“截止时间已过 + 进程消失”的场景。
  - 代码改动后同步更新文档和任务日志。
- 风险：
  - 若终态判断边界不清，可能把应恢复的任务误标为终止，或把应终止的任务继续恢复。
  - 若修复只更新现场状态而不修代码，问题会在后续运行中复现。
  - 若状态清理不完整，可能保留过期的 `active_iteration` / PID 字段，干扰下一轮恢复。
- 验收标准：
  - 当 `deadline_at` 已过且 loop 进程不存在时，watchdog / check-once 能把状态收敛为终态，而不是继续显示 `running`。
  - 针对性测试覆盖该场景并通过。
  - 现场 `output/agent-loop/state.json` 能反映真实运行状态。
- 当前项目类型：
  - 主类型：D 线上问题修复
  - 次类型：C 持续任务框架状态机修复
- 当前风险等级：
  - R2：涉及持续运行主控脚本的终态判断、恢复逻辑和状态文件语义。

## 仓库探测

- 已存在项：
  - `README.md`
  - `ARCHITECTURE.md`
  - `IMPLEMENTATION_PLAN.md`
  - `tests/` pytest 测试框架
  - `.github/` CI 配置
  - `.env.example`
  - `output/agent-loop/` 与脚本内文件日志机制
  - `migrations/` + `alembic.ini` 迁移机制
  - `RUNBOOK.md` 回滚与运行手册
- 缺失项：
  - 仓库内未见显式特性开关机制
- 本轮必须先补齐的项：
  - 无新增基础设施缺口；本轮必须先补齐的是终态判断测试和任务日志。

## 方案与测试计划

- 缺失机制清单：
  - 进行中轮次没有把剩余运行窗纳入单轮超时计算。
  - 流式输出使用 `readline()`，在无换行长输出场景下会阻塞超时检查。
  - watchdog 在“进程已消失 + 实际已到终态”时没有主动收口 `state.json`。
- 方案对比：
  - 方案 A：只在 watchdog 上补终态收口。复杂度低、侵入性小，但无法解决进行中轮次越过运行窗的问题。
  - 方案 B：同时修 watchdog 终态收口、单轮 deadline 压缩超时、流式读取超时实现。复杂度略高，但能直接覆盖“超过 5 小时仍未停”的主路径，兼容性最好。
- 推荐方案：
  - 采用方案 B，在保留现有状态协议的前提下做增量修复。
- 是否需要 ADR：
  - 否。本轮不引入新基础设施、不改数据库结构、不改核心业务调用链。
- 方案摘要：
  - 先在 `tests/test_continuous_task_loop.py` 补充失败测试，复现“deadline 已过、PID 已失效，但状态仍为 running”的问题。
  - 再在 `scripts/continuous_task_loop.py` 中同时修正三处：
    - watchdog / check-once 在进程不存在时主动执行终态判定并写回状态。
    - 单轮 timeout 取 `min(max_seconds_per_iteration, deadline 剩余秒数)`。
    - 流式读取改为非阻塞 chunk 读取，避免 partial line 卡住 timeout。
  - 修复后同步更新现场 `state.json`、任务日志，必要时补充 README / RUNBOOK。
- 关键决策：
  - 现场运行目录以 `state.json` 为事实源，但该事实源必须能在 loop 消失后被守护逻辑纠正。
  - `deadline_reached`、`completed`、`blocked`、`queue_exhausted` 等终态不应被自动恢复。
  - 进程不存在时要同时清理过期的 `loop_pid`、`active_child_pid`、`active_iteration` 等运行态字段。
- 测试计划：
  - 新增单测覆盖：`deadline_at` 已过且 `loop_pid` 对应进程不存在时，`run_watchdog_check_once(...)` 将状态写成 `deadline_reached`。
  - 视实现情况补充相邻终态场景，避免 stale running 在其他终止条件下也不收敛。
  - 完成后运行：
    - `python3 -m pytest -q tests/test_continuous_task_loop.py`
    - `python3 -m ruff check scripts/continuous_task_loop.py tests/test_continuous_task_loop.py`
    - `PYTHONPYCACHEPREFIX=/tmp/rag-pyc python3 -m compileall scripts tests`
- 实施步骤：
  - 先补失败测试，锁定 deadline / stale running / partial output timeout 三个场景。
  - 再修改主脚本的 timeout 与 watchdog 行为。
  - 更新 README、RUNBOOK、`docs/continuous-task-loop.md`。
  - 对真实 `output/agent-loop` 执行一次 `--check-once`，确认现场状态不再被错误恢复。

## 实施记录

- 变更文件：
  - `scripts/continuous_task_loop.py`
  - `tests/test_continuous_task_loop.py`
  - `README.md`
  - `RUNBOOK.md`
  - `docs/continuous-task-loop.md`
  - `docs/agent-runs/2026-03-15-auto-stop-debug.md`
- 根因结论：
  - 主循环的整体 deadline 只在轮次边界判断，进行中的子会话不会被 deadline 主动打断。
  - 原流式读取依赖 `readline()`；当子会话输出没有换行的长片段时，`readline()` 会阻塞，导致 `max_seconds_per_iteration` 也可能失效。
  - watchdog 在 loop 进程消失后，只会决定“是否恢复”，不会把已满足终态条件的 `running` 状态收口为 `deadline_reached` 等真实终态。
- 方案摘要：
  - 增加 `resolve_iteration_timeout_seconds(...)`，把单轮 timeout 压到剩余运行窗以内。
  - 将 `run_command_streaming(...)` 改为基于 `selectors + os.read` 的非阻塞 chunk 读取，持续检查绝对超时。
  - 在 `run_watchdog_check_once(...)` 中，当 loop 不存在且已满足终态条件时，直接写回终态并清理活动运行字段。
- 关键决策：
  - deadline 命中而主动停止子会话时，视为预期停机，返回 `deadline_reached`，不再把这类停止算作连续失败。
  - 文档明确声明 `duration-hours` 会约束单轮 timeout，watch / check-once 会收口 stale `running`。
- 风险与未覆盖项：
  - 本轮没有引入 PID 命令行签名校验，仍按“单机单目录独占”假设判断 liveness。
  - 未改 `load_or_create_state(...)` 的 `duration_hours` / `deadline_at` 继承策略；已有运行目录改时长仍需要显式更新时间窗。
- 回滚方式：
  - 回退 `scripts/continuous_task_loop.py`、`tests/test_continuous_task_loop.py` 及相关文档改动，并将现场 `state.json` 恢复到修复前状态。

## 验证结果

- `python3 -m pytest -q tests/test_continuous_task_loop.py`
  - 通过，`37 passed`
- `python3 -m ruff check scripts/continuous_task_loop.py tests/test_continuous_task_loop.py`
  - 通过
- `PYTHONPYCACHEPREFIX=/tmp/rag-pyc python3 -m compileall scripts tests`
  - 通过
- `python3 scripts/continuous_task_loop.py --state-dir output/agent-loop --check-once`
  - 返回 `No resume needed: terminal status=deadline_reached`
- 现场状态：
  - `output/agent-loop/state.json` 当前为 `status=deadline_reached`
  - `last_stop_reason=deadline_reached`
  - `duration_hours=5.0`

## 交付结论

- 风险清单：
  - 旧运行目录动态改时长的语义仍然依赖显式更新时间窗。
  - 多实例竞争同一 `state-dir` 仍不在本轮修复范围内。
- 未覆盖项：
  - 没有新增跨机器 / 多用户协调机制。
  - 没有为 PID 复用增加命令行签名校验。
- 上线检查项：
  - 若继续复用 `output/agent-loop`，先确认 `state.json` 中的 `deadline_at` 与本轮目标时间窗一致。
  - 若需要重新开新一轮 5 小时窗口，优先用新 `state-dir` 或显式更新时间窗后再启动。
- 回滚步骤：
  1. 回退上述脚本、测试和文档文件。
  2. 恢复修复前的 `state.json` / 运行策略。
  3. 如有需要，重新以人工方式管理 loop 停止与恢复。
- 后续建议：
  - 单独补一个正式的“retime / refresh window”能力，避免运行中手改 `state.json`。
  - 如后续还要增强鲁棒性，可再补 `PID + 命令行签名` 双重校验，降低极端 PID 复用误判。
