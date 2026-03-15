# 2026-03-15 持续循环迭代 013

- 任务名称：持续循环迭代 013
- 项目类型：C 成熟项目优化 / 重构
- 次类型：B 现有项目新增连续循环控制面增量
- 风险等级：R2

## 正式执行前说明

- 目标：
  - 基于真实 `output/agent-loop/` 运行态，补齐“活动轮次到底还活着，还是状态未收口”的读侧判定，减少后续会话误把陈旧目录当 live child。
  - 保持增量修改，不改外部接口、不改状态文件 schema、不引入新依赖。
- 非目标：
  - 不在本轮解决外部 Codex 端点、DNS、代理或网络层失败根因。
  - 不在本轮新增自动恢复策略、超时阈值告警或守护进程重构。
- 约束：
  - 必须以仓库文件与本地命令结果作为唯一事实源。
  - 必须先完成方案与测试计划，再进入实现。
  - 结束前必须同步更新 `README.md`、`RUNBOOK.md`、`docs/continuous-task-loop.md`、`output/agent-loop/` 交接文件和本任务日志。
- 风险：
  - 连续循环脚本属于控制面，live/stale 判定写错会误导 handoff、watch 和状态巡检。
  - 当前仓库仍处于真实运行目录复用场景，任何“活动轮次”相关逻辑都必须兼容旧状态文件与半收口目录。
- 验收标准：
  - watch 进度摘要能明确区分 `inactive` / `live` / `stale`。
  - 当 `active_child_pid` 已退出而 `loop_pid` 仍存活或状态未收口时，不再把该轮次误判成 live。
  - `project_autopilot.py status --json` 能直接输出结构化的活动轮次状态与最近进展时间。

## 仓库探测结果

- 已存在项：
  - README：`README.md`
  - 架构文档：`ARCHITECTURE.md`
  - 实施计划：`IMPLEMENTATION_PLAN.md`
  - 测试框架：`pytest`、`tests/`
  - CI：`.github/workflows/`
  - 环境变量模板：`.env.example`
  - 日志机制：`output/agent-loop/watchdog.log`、`output/agent-loop/iterations/*/events.jsonl`
  - 迁移机制：`migrations/`、`alembic.ini`
  - 回滚方式：`RUNBOOK.md`
- 缺失项：
  - 统一特性开关机制
- 本轮必须先补齐的项：
  - 用任务日志写清方案对比、测试计划、风险、回滚和真实运行态证据。
  - 把“活动轮次 stale 判定”落实到 watch / handoff / status 这几个最常用读侧入口。

## 当前项目类型 / 当前风险等级

- 当前项目类型：`C 成熟项目优化 / 重构`
- 当前风险等级：`R2`

## 仓库现状

- 连续循环主入口是 `scripts/continuous_task_loop.py`，已有 `active_iteration*`、失败诊断、handoff 兜底和 watch 进度摘要能力。
- `scripts/project_autopilot.py status --json` 已能输出 loop、队列和 pid 状态，但此前没有结构化表达“active iteration 是否真的 live”。
- 真实运行态里已经能看到 `active_iteration_last_progress_at`，但本轮观测到一个更细的边界：`state.json` 里仍保留 `active_iteration=13` 时，pid liveness 与目录产物可能已经不再支持“该轮还活着”的判断。

## 缺失机制清单

- 缺少显式的 `active_iteration_state`，导致 watch / status 只能展示原始 `active_iteration` 数字，接管者仍需自己推断它是 live 还是 stale。
- `live_active_iteration_number()` 之前只看 `loop_pid`，没有把 `active_child_pid` 作为更精确的 live 判定依据。
- handoff 之前只会在 live 场景提示当前轮次；若状态文件残留“未收口的活动轮次标记”，不会明确告诉下一轮“这不是 live child”。

## 运行态证据

- 本轮读取了 `output/agent-loop/state.json`、`TASK_QUEUE.md`、`NEXT_ACTION.md`、`LOOP_MEMORY.md`，并多次查看 `output/agent-loop/iterations/013/`。
- 一次真实观测里，`state.json` 仍保留 `active_iteration=13`，但检查 pid 时得到：
  - `loop_pid 46613 False`
  - `active_child_pid 46614 False`
- 这说明“状态文件还保留活动轮次编号”不等于“当前轮次仍在运行”；需要一个读侧显式状态把 stale 场景标出来。

## 方案对比

- 方案 A：只更新文档，要求接管者结合 `loop_pid_running`、`active_child_pid` 和目录产物手工判断。
  - 复杂度：最低
  - 性能：无额外开销
  - 成本：低
  - 侵入性：低
  - 兼容性：高
  - 维护成本：中，判断逻辑继续分散在人脑里
  - 回滚难度：低
- 方案 B：在控制面读取侧引入 `active_iteration_state`，并把 `active_child_pid` 纳入 live 判定；同步让 watch / handoff / status 展示 stale 语义。
  - 复杂度：低到中
  - 性能：低，仅本地读取状态和 pid
  - 成本：低
  - 侵入性：低，不改磁盘 schema
  - 兼容性：高，旧状态文件也能推导
  - 维护成本：低，语义集中在 helper 内
  - 回滚难度：低
- 推荐方案：
  - 采用方案 B，以最小读侧改动修正“状态残留但子会话已退出”的误判。
- 是否需要 ADR：
  - 否。本轮不新增基础设施、不改数据库结构、不改核心业务链路。

## 测试计划

- 验收测试：
  1. watch 进度摘要在活动轮次 stale 时输出 `active_state=stale`。
  2. handoff 在 stale 场景下明确提示“未收口的活动轮次标记”，而不是继续当 live child 处理。
- 回归测试：
  3. 现有 live handoff 测试继续通过，证明 `active_child_pid` 仍活着时不会误伤 live 场景。
  4. `project_autopilot.py status --json` 返回新的 `active_iteration_state` / `active_iteration_live` / `active_iteration_last_progress_at` 字段。
- 边界测试：
  5. 当 `active_iteration_last_progress_at` 为空但 stale 目录还有 `events.jsonl` 时，watch / handoff 仍能回退到磁盘 mtime。
- 实现后验证命令：
  6. `python3 -m pytest -q tests/test_continuous_task_loop.py tests/test_project_autopilot.py`
  7. `python3 -m ruff check scripts/continuous_task_loop.py scripts/project_autopilot.py tests/test_continuous_task_loop.py tests/test_project_autopilot.py`
  8. `PYTHONPYCACHEPREFIX=/tmp/rag-pyc python3 -m compileall scripts tests`
  9. `python3 scripts/project_autopilot.py status --state-dir output/agent-loop --json`

## 实施步骤

1. 先补 stale 边界测试，锁定 watch / handoff / status 的目标行为。
2. 调整 `live_active_iteration_number()`，优先用 `active_child_pid` 判断 live。
3. 为 watch / handoff / status 增加 `active_iteration_state` 和 stale 语义。
4. 更新 README / RUNBOOK / 连续循环文档、任务日志和运行态交接文件。

## 实施记录

- 在 `tests/test_continuous_task_loop.py` 中新增 stale 边界测试，覆盖：
  - watch 进度摘要输出 `active_state=stale`
  - handoff 明确提示“未收口的活动轮次标记”
  - live 场景测试改用真实存活的 `active_child_pid`
- 在 `scripts/continuous_task_loop.py` 中新增/调整：
  - `raw_active_iteration_number()`
  - `active_iteration_state()`
  - `live_active_iteration_number()`：若存在 `active_child_pid`，优先以它判定 live
  - `resolve_active_iteration_last_progress_at(..., include_stale=True)`：stale 场景也能回退到目录产物 mtime
- 在 `scripts/project_autopilot.py` 的 `collect_status()` 中新增：
  - `active_iteration_state`
  - `active_iteration_live`
  - `active_iteration_last_progress_at`
- 在 `README.md`、`RUNBOOK.md`、`docs/continuous-task-loop.md` 中同步记录新的 stale 语义、watch 进度摘要字段和 `status --json` 输出。

## 验证结果

- `python3 -m pytest -q tests/test_continuous_task_loop.py -k 'stale_active_iteration or live_active_iteration_number or handoff_prompt or watch_progress_report'`：`9 passed`
- `python3 -m pytest -q tests/test_project_autopilot.py -k 'stale_active_iteration or start_and_status_cover_terminal_run'`：`2 passed`
- `python3 -m pytest -q tests/test_continuous_task_loop.py tests/test_project_autopilot.py`：`39 passed`
- `python3 -m ruff check scripts/continuous_task_loop.py scripts/project_autopilot.py tests/test_continuous_task_loop.py tests/test_project_autopilot.py`：通过
- `PYTHONPYCACHEPREFIX=/tmp/rag-pyc python3 -m compileall scripts tests`：通过
- `python3 scripts/project_autopilot.py status --state-dir output/agent-loop --json`：已输出 `active_iteration_state` / `active_iteration_live` / `active_iteration_last_progress_at`

## 关键决策

- 不改状态文件 schema，只做读侧推导，降低兼容风险。
- 以 `active_child_pid` 作为更精确的 live 判定来源；没有 child pid 时才回退到 `loop_pid`。
- stale 场景保留“最近进展时间”展示，但必须同时标明 `state=stale`，避免误导为 live 心跳。

## 变更文件

- `scripts/continuous_task_loop.py`
- `scripts/project_autopilot.py`
- `tests/test_continuous_task_loop.py`
- `tests/test_project_autopilot.py`
- `README.md`
- `RUNBOOK.md`
- `docs/continuous-task-loop.md`
- `docs/agent-runs/2026-03-15-loop-iteration-013.md`
- `output/agent-loop/TASK_QUEUE.md`
- `output/agent-loop/NEXT_ACTION.md`
- `output/agent-loop/LOOP_MEMORY.md`

## 风险清单

- `active_iteration_state=stale` 仍然是读侧推导，不代表根因已经修复；它主要解决“不要误判 live”的问题。
- pid liveness 只适用于当前单机目录，不覆盖跨机器或多用户争抢同一 `state-dir` 的场景。
- 本轮没有修复外部 Codex 端点、HTTP 426、DNS 解析失败等真实网络问题。

## 未覆盖项

- 还没有在“后端恢复可连通”的真实环境里复跑全新 `state-dir` 首轮运行。
- 还没有把 stale 状态自动提升为 watchdog 恢复动作；本轮只补可观测性与交接语义。

## 上线检查项

- 确认 watch 进度摘要在 stale 场景下输出 `active_state=stale`。
- 确认 `project_autopilot.py status --json` 输出 `active_iteration_state` 和 `active_iteration_last_progress_at`。
- 确认 handoff 在 stale 场景下提示“未收口的活动轮次标记”，并继续把失败诊断作为优先排障入口。

## 回滚步骤

1. 回退 `scripts/continuous_task_loop.py`、`scripts/project_autopilot.py`、相关测试、文档和本轮交接文件。
2. 重新运行本轮验证命令，确认 watch / handoff / status 恢复到上一稳定语义。

## 后续建议

- 下一轮继续观察真实 `output/agent-loop/`：若再次出现 `active_iteration` 长时间残留，可直接看 `active_iteration_state`，不要再把纯数字状态当 live 证据。
- 若外部 Codex 后端恢复可连通，再用全新 `state-dir` 复跑 non-dry-run 链路，确认 `diagnostics.json`、stale 判定和 handoff 组合是否足以完成真实交接。
