# 2026-03-15 持续循环迭代 015

- 任务名称：持续循环迭代 015
- 项目类型：C 成熟项目优化 / 重构
- 次类型：B 现有项目新增连续循环状态可读性增量
- 风险等级：R2

## 正式执行前说明

- 目标：
  - 在不依赖外部 Codex 网络恢复的前提下，把 `python3 scripts/project_autopilot.py status --json` 扩展成“单命令即可读取当前活动轮次 + 最新失败诊断摘要”的巡检入口。
  - 降低下一轮会话或人工接管者在 `active_iteration_state`、`diagnostics.json`、`recovery_hints` 之间来回切文件的成本。
- 非目标：
  - 不在本轮修复外部 Codex 端点、代理、DNS 或 WebSocket Upgrade 问题。
  - 不在本轮引入新的自动恢复流程、守护策略或运行态 schema 迁移。
- 约束：
  - 仅以仓库文件和本地命令输出作为事实源。
  - 先补测试，再写实现，遵循 `tdd-workflow`。
  - 改动完成后必须同步更新任务日志、相关文档，以及 `output/agent-loop/` 交接文件。
- 风险：
  - `status` 输出是巡检入口，若新字段选择或语义错误，会误导下一轮优先级判断。
  - 失败诊断来源同时受 `state.json/history` 与磁盘 `iterations/<n>/diagnostics.json` 影响，若选错“最新失败”会把旧证据误报为当前问题。
- 验收标准：
  - `project_autopilot.py status --json` 能输出最新失败诊断的路径和核心摘要。
  - 新输出至少覆盖 `failure_category`、`summary`、`recovery_hints`，且能兼容 state 落后于磁盘产物的场景。
  - 文档说明新的 `status` 读取顺序，并保留旧字段兼容。

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
  - 单命令读取“当前活动轮次 + 最新失败诊断”的状态聚合视图
- 本轮必须先补齐的项：
  - 为 `status` 命令补充最新失败诊断聚合字段，并记录测试计划与回滚方式。

## 当前项目类型 / 当前风险等级

- 当前项目类型：`C 成熟项目优化 / 重构`
- 当前风险等级：`R2`

## 仓库现状

- `scripts/continuous_task_loop.py` 已能生成 `diagnostics.json`，包含 `failure_category`、`transport_error_groups`、`recovery_hints`。
- `scripts/project_autopilot.py status --json` 当前仅暴露 `active_iteration_state` 等活动轮次状态，不会直接带出最新失败诊断摘要。
- 真实运行态里，接管者现在仍需要先跑 `status` 看 `active_iteration_state`，再手动打开 `iterations/<n>/diagnostics.json` 读取失败分类和提示。

## 缺失机制清单

- 缺少 `latest_failure_diagnostics_path`，导致 `status` 结果无法直接定位最新失败证据。
- 缺少 `latest_failure_category` / `latest_failure_summary` / `latest_failure_recovery_hints`，导致巡检信息仍然分散在多个文件。
- 缺少面向 `status` 的回归测试，无法锁定“state 落后于磁盘产物”时的失败诊断选择逻辑。

## 方案对比

- 方案 A：保持 `status` 现状，只在 `NEXT_ACTION.md` 和文档里继续提示“先跑 status，再手动打开 diagnostics”。
  - 复杂度：低
  - 性能：无新增开销
  - 成本：低
  - 侵入性：低
  - 兼容性：高
  - 维护成本：中，巡检步骤继续分散
  - 回滚难度：低
- 方案 B：在 `collect_status()` 中聚合最新失败诊断元数据，并补测试与文档。
  - 复杂度：低到中
  - 性能：低，仅在读状态时读取一个本地 JSON 文件
  - 成本：低
  - 侵入性：低，属于 status 输出的向后兼容扩展
  - 兼容性：高，旧消费方可忽略新增字段
  - 维护成本：低，巡检入口统一
  - 回滚难度：低
- 推荐方案：
  - 采用方案 B，用最小的读侧聚合改动缩短排障路径。
- 是否需要 ADR：
  - 否。本轮不新增基础设施、不改数据库、不改核心调用链。

## 测试计划

- 用户旅程：
  - 作为接管连续循环的维护者，我希望运行一次 `status --json` 就能同时知道当前是否还有 live/stale 活动轮次，以及最近一次失败该优先排查什么。
- 验收测试：
  1. 当最新失败已经落盘到 `iterations/<n>/diagnostics.json` 时，`collect_status()` 输出路径、失败分类、摘要和提示。
  2. 当存在 stale `active_iteration` 时，`collect_status()` 仍能暴露最新失败诊断，而不是只返回 stale 状态。
- 回归测试：
  3. 当 `state.json/history` 落后于磁盘产物时，`collect_status()` 仍选择最新 on-disk 的失败诊断。
  4. 现有 `active_iteration_state` 相关断言继续成立，不破坏已有状态输出。
- 边界测试：
  5. 当不存在失败诊断文件时，新字段保持空值或空列表，不抛异常。
- 实现后验证命令：
  6. `python3 -m pytest -q tests/test_project_autopilot.py tests/test_continuous_task_loop.py`
  7. `python3 -m ruff check scripts/project_autopilot.py scripts/continuous_task_loop.py tests/test_project_autopilot.py tests/test_continuous_task_loop.py`
  8. `PYTHONPYCACHEPREFIX=/tmp/rag-pyc python3 -m compileall scripts tests`

## 实施步骤

1. 先为 `collect_status()` 补失败诊断聚合测试，锁定新增字段语义。
2. 在连续循环脚本中抽一个读取最新失败诊断的 helper，并接入 `project_autopilot.py status`。
3. 更新 README / RUNBOOK / `docs/continuous-task-loop.md` 对 `status` 新字段和推荐巡检顺序的说明。
4. 运行针对性验证并更新本任务日志、`TASK_QUEUE.md`、`NEXT_ACTION.md`、`LOOP_MEMORY.md`。

## 实施记录

- 先在 `tests/test_project_autopilot.py` 中补了两类关键断言：
  - `collect_status()` 在 `state.json/history` 落后于磁盘 `iterations/<n>/diagnostics.json` 时，仍能给出最新失败诊断路径、分类、摘要和提示。
  - `collect_status()` 在 `active_iteration_state=stale` 且没有失败诊断时，新增字段保持空值，不影响现有状态字段。
- 首轮针对性测试先失败，确认当前 `status` 输出里还没有 `latest_failure_*` 字段，随后再进入实现。
- 在 `scripts/project_autopilot.py` 中新增 `collect_latest_failure_status()`，复用 `latest_failure_diagnostics_path()` 读取最新失败诊断，并把以下字段并入 `status --json`：
  - `latest_failure_iteration`
  - `latest_failure_diagnostics_path`
  - `latest_failure_category`
  - `latest_failure_summary`
  - `latest_failure_recovery_hints`
- 新实现保持向后兼容：若当前没有失败诊断文件，这些字段会返回空值或空列表，而不会抛异常。
- 在 `README.md`、`RUNBOOK.md`、`docs/continuous-task-loop.md` 中同步补充了新的巡检顺序：先看 `status --json` 的活动轮次状态，再决定是否打开 `latest_failure_diagnostics_path` 深挖完整诊断。

## 验证结果

- `python3 -m pytest -q tests/test_project_autopilot.py -k 'latest_failure or docs_are_wired or stale_active_iteration'`：先失败后通过，完成 TDD 闭环。
- `python3 -m pytest -q tests/test_project_autopilot.py tests/test_continuous_task_loop.py`：通过，`41 passed`。
- `python3 -m ruff check scripts/project_autopilot.py scripts/continuous_task_loop.py tests/test_project_autopilot.py tests/test_continuous_task_loop.py`：通过。
- `PYTHONPYCACHEPREFIX=/tmp/rag-pyc python3 -m compileall scripts tests`：通过。
- `python3 scripts/project_autopilot.py status --state-dir output/agent-loop --json`：通过，真实运行态已包含新的 `latest_failure_*` 字段。

## 关键决策

- 新能力只扩展 `status` 的读侧输出，不改 `state.json` schema，避免干扰正在运行的主循环。
- 最新失败诊断继续复用 `latest_failure_diagnostics_path()` 的选择逻辑，避免 `status` 和 handoff 各自维护一套“最新失败”判定。
- 对无失败诊断场景返回空值而不是省略字段，方便外部脚本做稳定解析。

## 变更文件

- `scripts/project_autopilot.py`
- `tests/test_project_autopilot.py`
- `README.md`
- `RUNBOOK.md`
- `docs/continuous-task-loop.md`
- `docs/agent-runs/2026-03-15-loop-iteration-015.md`
- `output/agent-loop/TASK_QUEUE.md`
- `output/agent-loop/NEXT_ACTION.md`
- `output/agent-loop/LOOP_MEMORY.md`

## 风险清单

- `latest_failure_*` 仍依赖已有“最新失败”判定逻辑；如果后续要展示“最近一次失败”而不是“最新失败轮次”，需要另行定义语义。
- 真实外部网络仍未恢复，本轮只能验证读侧聚合和交接体验，不能验证成功跑通真实新 `state-dir`。

## 未覆盖项

- 尚未在外部 Codex 可连通环境里复跑真实 fresh `state-dir` 的首轮 non-dry-run。
- 还没有把 `latest_failure_*` 接入 watch 进度摘要；本轮只补 `status` 巡检入口。

## 上线检查项

- 确认 `python3 scripts/project_autopilot.py status --json` 输出包含新的 `latest_failure_*` 字段。
- 确认 README / RUNBOOK / `docs/continuous-task-loop.md` 已说明新的巡检顺序。

## 回滚步骤

1. 回退 `scripts/project_autopilot.py`、相关测试、文档和本轮交接文件。
2. 重新运行本轮验证命令，确认 `status --json` 恢复为上一稳定输出。

## 后续建议

- 下一轮若真实运行再次失败，先跑 `python3 scripts/project_autopilot.py status --state-dir output/agent-loop --json`，直接读取 `active_iteration_state` 与 `latest_failure_*`。
- 若外部连通性恢复，再用全新 `state-dir` 复跑一次真实 non-dry-run，验证 `status --json` + `diagnostics.json` + handoff 是否足以完成首轮交接。
