# 2026-03-15 持续循环迭代 016

- 任务名称：持续循环迭代 016
- 项目类型：C 成熟项目优化 / 重构
- 次类型：B 现有项目新增连续循环状态读侧兼容性增量
- 风险等级：R2

## 正式执行前说明

- 目标：
  - 在不依赖外部 Codex 网络恢复的前提下，增强 `python3 scripts/project_autopilot.py status --json` 对旧版 `diagnostics.json` 的读侧兼容能力。
  - 让 `status --json` 直接暴露更稳定的失败指纹，减少下一轮接管者为判断 DNS / WebSocket / 尝试次数而继续翻 `diagnostics.json` 的次数。
- 非目标：
  - 不在本轮修复外部 Codex 端点、代理、DNS 或 WebSocket Upgrade 问题。
  - 不在本轮改动主循环写侧 schema、守护恢复逻辑或真实 non-dry-run 执行链路。
- 约束：
  - 仅以仓库文件和本地命令输出作为事实源。
  - 先补测试，再写实现，遵循 `tdd-workflow`。
  - 改动完成后必须同步更新任务日志、相关文档，以及 `output/agent-loop/` 交接文件。
- 风险：
  - `status --json` 是接管入口，若对旧版诊断的兜底推导不准确，会把错误分类或排障建议误报给下一轮。
  - 新增字段若命名或空值语义不稳，会影响现有脚本消费方的兼容性。
- 验收标准：
  - 当最新失败来自旧版 `diagnostics.json` 时，`status --json` 仍能输出非空的失败分类与排障提示。
  - `status --json` 额外输出稳定可解析的失败尝试次数和 transport 聚合结果，减少再次打开诊断文件的需要。
  - 文档说明新增字段和旧版诊断兼容策略，并保留旧消费方兼容。

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
  - `status --json` 对旧版 `diagnostics.json` 的结构兼容归一层
  - 单命令读取失败尝试次数与 transport 聚合结果的状态字段
- 本轮必须先补齐的项：
  - 为 `status --json` 增加对旧版诊断的兜底推导，并补稳定的失败指纹字段、测试和文档。

## 当前项目类型 / 当前风险等级

- 当前项目类型：`C 成熟项目优化 / 重构`
- 当前风险等级：`R2`

## 仓库现状

- `scripts/continuous_task_loop.py` 当前生成的新诊断文件已包含 `failure_category`、`transport_error_groups`、`recovery_hints`、`attempt`。
- 仓库中的历史产物仍混有旧版 `diagnostics.json`，例如较早失败文件只有 `transport_errors` 和 `summary`，不一定含 `failure_category` 或 `recovery_hints`。
- `scripts/project_autopilot.py status --json` 目前只会透传诊断文件里已存在的字段，对旧版文件缺少兼容推导，因此返回值可能出现空分类 / 空提示。

## 缺失机制清单

- 缺少旧版 `diagnostics.json` 的读侧归一化，导致 `status --json` 遇到历史文件时信息退化。
- 缺少 `latest_failure_attempt`，无法直接判断同编号轮次是第几次尝试失败。
- 缺少 `latest_failure_transport_error_groups`，导致用户仍需打开诊断文件查看重复 transport 报错归并结果。

## 方案对比

- 方案 A：保持 `status` 现状，仅在文档中说明“旧版 diagnostics 字段可能不全，需要手动打开文件”。
  - 复杂度：低
  - 性能：无新增开销
  - 成本：低
  - 侵入性：低
  - 兼容性：高
  - 维护成本：中，接管路径仍分裂
  - 回滚难度：低
- 方案 B：在 `collect_latest_failure_status()` 中做诊断归一化，补 `attempt` 与 `transport_error_groups` 输出，并为旧版文件做兜底推导。
  - 复杂度：低到中
  - 性能：低，只读取单个本地 JSON 并做轻量推导
  - 成本：低
  - 侵入性：低，属于读侧向后兼容扩展
  - 兼容性：高，旧消费方可忽略新增字段
  - 维护成本：低，状态入口更统一
  - 回滚难度：低
- 推荐方案：
  - 采用方案 B，用最小的读侧补丁兼容历史诊断 schema，并减少手动翻文件。
- 是否需要 ADR：
  - 否。本轮不新增基础设施、不改数据库、不改核心写链路。

## 测试计划

- 用户旅程：
  - 作为接管连续循环的维护者，我希望仅运行一次 `status --json`，就能在旧版或新版诊断文件下都看到足够稳定的失败分类、尝试次数和 transport 聚合信息。
- 验收测试：
  1. 当最新失败来自旧版 `diagnostics.json` 且缺少 `failure_category` / `recovery_hints` / `transport_error_groups` 时，`collect_status()` 仍输出合理兜底值。
  2. 当最新失败来自新版 `diagnostics.json` 时，`collect_status()` 透传 `attempt` 与 `transport_error_groups`，不破坏现有字段。
- 回归测试：
  3. `state.json/history` 落后于磁盘产物时，`collect_status()` 仍选择最新 on-disk 的失败诊断。
  4. 文档联动测试继续确保 README / RUNBOOK / `docs/continuous-task-loop.md` 说明新的状态字段。
- 边界测试：
  5. 当不存在失败诊断文件时，新增字段保持空值或空列表，不抛异常。
- 实现后验证命令：
  6. `python3 -m pytest -q tests/test_project_autopilot.py -k 'latest_failure or docs_are_wired or stale_active_iteration'`
  7. `python3 -m pytest -q tests/test_project_autopilot.py tests/test_continuous_task_loop.py`
  8. `python3 -m ruff check scripts/project_autopilot.py scripts/continuous_task_loop.py tests/test_project_autopilot.py tests/test_continuous_task_loop.py`
  9. `PYTHONPYCACHEPREFIX=/tmp/rag-pyc python3 -m compileall scripts tests`

## 实施步骤

1. 先为 `collect_status()` 补旧版诊断兼容与新增状态字段测试，锁定目标语义。
2. 在 `project_autopilot.py` 中新增诊断归一化逻辑，并以最小改动接入现有 `latest_failure_*` 聚合路径。
3. 更新 `README.md`、`RUNBOOK.md`、`docs/continuous-task-loop.md` 对新增字段与旧版兼容行为的说明。
4. 运行针对性验证并更新本任务日志、`TASK_QUEUE.md`、`NEXT_ACTION.md`、`LOOP_MEMORY.md`。

## 实施记录

- 先在 `tests/test_project_autopilot.py` 中补了三类关键断言：
  - 无失败诊断时，`latest_failure_attempt` 与 `latest_failure_transport_error_groups` 保持空值，不破坏现有 stale 状态输出。
  - 新版 `diagnostics.json` 会被 `status --json` 直接透传 `attempt` 与 `transport_error_groups`。
  - 旧版 `diagnostics.json` 即使缺少 `failure_category` / `transport_error_groups` / `recovery_hints`，`status --json` 仍会基于保留的 `transport_errors`、`error_messages`、`warnings` 自动推导这些字段。
- 首轮针对性测试先失败，暴露当前 `status` 缺少 `latest_failure_attempt` 字段，完成了 TDD 的红灯确认。
- 在 `scripts/project_autopilot.py` 中新增轻量诊断归一化层：
  - 新增 `normalize_string_list()`、`normalize_transport_error_groups()`、`normalize_transport_errors()`。
  - 新增 `normalized_latest_failure_diagnostics()`，统一处理新版 / 旧版 `diagnostics.json`。
  - `collect_latest_failure_status()` 现在会输出：
    - `latest_failure_attempt`
    - `latest_failure_transport_error_groups`
  - 当旧版诊断缺字段时，会复用 `derive_failure_category()`、`summarize_transport_error_groups()`、`build_recovery_hints()`、`summarize_iteration_failure()` 做读侧兜底，不改写历史文件。
- 在 `README.md`、`RUNBOOK.md`、`docs/continuous-task-loop.md` 中同步补充了新字段与“旧版 diagnostics 也能单命令巡检”的说明。
- 用真实 `output/agent-loop/` 跑 `status --json` 再次确认：当前 `active_iteration_state=live` 时，`latest_failure_*` 为空值是合理表现，不会把活动轮次误判成已完成失败。

## 验证结果

- `python3 -m pytest -q tests/test_project_autopilot.py -k 'latest_failure or stale_active_iteration'`：先失败后通过，确认新增字段确实是测试驱动补出来的。
- `python3 -m pytest -q tests/test_project_autopilot.py -k 'legacy or latest_failure or docs_are_wired or stale_active_iteration'`：通过，`4 passed`。
- `python3 -m pytest -q tests/test_project_autopilot.py tests/test_continuous_task_loop.py`：通过，`42 passed`。
- `python3 -m ruff check scripts/project_autopilot.py scripts/continuous_task_loop.py tests/test_project_autopilot.py tests/test_continuous_task_loop.py`：通过。
- `PYTHONPYCACHEPREFIX=/tmp/rag-pyc python3 -m compileall scripts tests`：通过。
- `python3 scripts/project_autopilot.py status --state-dir output/agent-loop --json`：通过；当前真实运行态为 `active_iteration_state=live`，新增字段已稳定出现在输出 schema 中。

## 关键决策

- 本轮只做读侧归一化，不回补或迁移历史 `diagnostics.json` 文件，避免触碰正在运行的主循环产物。
- 新归一化逻辑复用 `continuous_task_loop.py` 已有的失败分类和提示生成能力，避免 `status` 自己维护第二套规则。
- 对缺失尝试次数的旧版诊断保持 `latest_failure_attempt=None`，避免凭目录或历史状态做不可靠推测。

## 变更文件

- `scripts/project_autopilot.py`
- `tests/test_project_autopilot.py`
- `README.md`
- `RUNBOOK.md`
- `docs/continuous-task-loop.md`
- `docs/agent-runs/2026-03-15-loop-iteration-016.md`
- `output/agent-loop/TASK_QUEUE.md`
- `output/agent-loop/NEXT_ACTION.md`
- `output/agent-loop/LOOP_MEMORY.md`

## 风险清单

- 旧版诊断的兜底推导仍依赖历史文件里至少保留 `transport_errors`、`error_messages` 或 `warnings`；如果文件结构更早或被截断，状态输出仍可能只能给出空值。
- `latest_failure_transport_error_groups` 是读侧归一化结果；若未来写侧分组规则调整，需同步确认 status 输出和 handoff 的解释是否仍一致。

## 未覆盖项

- 尚未在外部 Codex 可连通环境里复跑真实 fresh `state-dir` 的首轮 non-dry-run。
- 本轮没有把新的失败聚合字段继续接入 watch 进度摘要；增强点仍集中在 `status --json`。

## 上线检查项

- 确认 `python3 scripts/project_autopilot.py status --json` 输出包含 `latest_failure_attempt` 与 `latest_failure_transport_error_groups`。
- 确认 README / RUNBOOK / `docs/continuous-task-loop.md` 已说明旧版 `diagnostics.json` 的兼容行为。

## 回滚步骤

1. 回退 `scripts/project_autopilot.py`、对应测试、文档和本轮交接文件。
2. 重新运行本轮验证命令，确认 `status --json` 恢复到上一稳定输出。

## 后续建议

- 下一轮若真实运行再次失败，先跑 `python3 scripts/project_autopilot.py status --state-dir output/agent-loop --json`，直接读取 `latest_failure_attempt` 与 `latest_failure_transport_error_groups`，再决定是否打开 `diagnostics.json`。
- 若外部连通性恢复，再用全新 `state-dir` 复跑一次真实 non-dry-run，验证旧版 / 新版诊断兼容逻辑在真实 fresh run 上仍然足够完成首轮交接。
