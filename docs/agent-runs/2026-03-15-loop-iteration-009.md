# 2026-03-15 持续循环迭代 009

- 任务名称：持续循环迭代 009
- 项目类型：C 成熟项目优化 / 重构
- 次类型：B 现有项目新增功能
- 风险等级：R2

## 正式执行前说明

- 目标：
  - 基于 `output/agent-loop/` 当前运行态，修复“恢复后复用未记账轮次目录时，旧产物误导 handoff / 排障”的最小增量。
  - 降低 `state.json` / `history` 暂时落后时，下一轮会话被陈旧 `diagnostics.json`、`last-message.md` 或 `events.jsonl` 带偏的概率。
  - 保持连续循环迭代编号、守护恢复能力和现有运行态目录结构兼容。
- 非目标：
  - 不在本轮直接修复外部 Codex 端点 DNS / 代理 / 网络连通性问题。
  - 不在本轮重做迭代编号策略、引入 attempt 子目录或新增后台 supervisor。
  - 不主动终止当前仍存活的 `loop_pid=42370`，也不假设它已经完成收尾。
- 约束：
  - 仅以仓库文件、运行态文件和本地命令结果为事实源。
  - 必须在实现前完成方案与测试计划，并在结束前更新 `TASK_QUEUE.md`、`NEXT_ACTION.md`、`LOOP_MEMORY.md`。
  - 当前环境网络受限，本轮只能基于本地运行态证据、单元测试与文档同步完成增量。
- 风险：
  - 如果目录清理范围过大，可能删掉人工补充的辅助证据。
  - 如果“活动轮次仍在运行”的判定不准，handoff 可能错误压制最新失败诊断。
  - 当前真实 loop 若是在本轮修改前启动，仍不会热加载新逻辑，需后续重启后才能完全生效。
- 验收标准：
  - 当 `loop_pid` 仍存活且 `active_iteration` 尚未写回 `history` 时，handoff 优先提示查看该轮 `prompt.md` / `events.jsonl`，而不是直接引用同目录里的旧 `diagnostics.json`。
  - 当守护恢复要重试同一轮编号时，会先清理该 `iterations/<n>/` 目录中的已知旧产物，再生成新一轮产物。
  - `tests/test_continuous_task_loop.py`、`README.md`、`RUNBOOK.md`、`docs/continuous-task-loop.md` 和本轮任务日志同步更新，并通过针对性验证。
- 当前项目类型：
  - 主类型：C 成熟项目优化 / 重构
  - 次类型：B 现有项目新增功能
- 当前风险等级：
  - R2：改动局限在连续循环 harness，但涉及 handoff、守护恢复与失败诊断入口，属于接力链路关键行为。

## 仓库探测结果

- 已存在项：
  - README：`README.md`
  - 架构文档：`ARCHITECTURE.md`
  - 实施计划：`IMPLEMENTATION_PLAN.md`
  - 测试框架：`pytest`、Playwright、`tests/`
  - CI：`.github/workflows/`
  - 环境变量模板：`.env.example`
  - 日志机制：`output/agent-loop/*.log`、`output/agent-loop/iterations/*/events.jsonl`
  - 迁移机制：`migrations/`、`alembic.ini`
  - 回滚方式：`RUNBOOK.md`
- 缺失项：
  - 统一特性开关机制
  - 统一应用级结构化日志规范
  - 连续循环当前仍缺少“同一轮重试 attempt 标识”和子进程级元数据，导致恢复时难区分旧产物与新尝试
- 本轮必须先补齐的项：
  - 基于真实运行态补齐本轮方案对比、测试计划与回滚说明后再进入实现。
  - 补一个不改变迭代编号策略的最小修复，避免恢复重试时目录残留产物误导后续会话。

## 运行态证据

- `output/agent-loop/state.json` 当前显示：
  - `iteration_count=8`
  - `active_iteration=9`
  - `loop_pid=42370`
  - `active_iteration_started_at=2026-03-14T19:53:05Z`
- 同时，`output/agent-loop/iterations/009/diagnostics.json` 的本地 mtime 为 `2026-03-15T03:41:18+0800`，早于 `active_iteration_started_at` 对应的本地时间 `2026-03-15T03:53:05+0800`。
- 这说明真实目录里至少存在一次“旧的 009 失败产物先落盘，随后主循环又以同一个迭代编号继续执行”的现象；如果不处理，handoff 很容易把旧 `diagnostics.json` 当成当前活动轮次的结论。

## 方案对比

- 方案 A：只更新文档，要求人工在看到 `active_iteration` 时手动比对 `prompt.md` / `events.jsonl` 与 `diagnostics.json` 的时间关系。
  - 复杂度：最低
  - 性能：无额外开销
  - 成本：低
  - 侵入性：低
  - 兼容性：高
  - 维护成本：中，高度依赖人工判断
  - 回滚难度：低
- 方案 B：恢复后直接跳到新的迭代编号，彻底避免复用旧目录。
  - 复杂度：中到高
  - 性能：低
  - 成本：中
  - 侵入性：中，会改变 `iteration_count` / `history` / 目录编号语义
  - 兼容性：中，已有排障和文档都默认“一轮对应一个编号”
  - 维护成本：中
  - 回滚难度：中
- 方案 C：保留现有编号语义，但在重试同一轮前清理该目录中的已知旧产物，并让 handoff 在 `loop_pid` 仍存活时优先指向活动轮次的 `prompt.md` / `events.jsonl`。
  - 复杂度：低到中
  - 性能：低，仅在准备迭代目录和生成 handoff 时做少量文件检查
  - 成本：低
  - 侵入性：低，限定在连续循环 harness 内
  - 兼容性：高，不改变已有状态字段和目录编号
  - 维护成本：低，规则边界清晰
  - 回滚难度：低
- 推荐方案：
  - 采用方案 C，以最小行为改动同时处理“目录残留证据污染”和“handoff 优先级错误”两个问题。
- 是否需要 ADR：
  - 否。本轮未引入新基础设施，不修改数据库、认证授权、核心业务调用链或部署结构。

## 测试计划

1. 先补 handoff 测试，覆盖“活动轮次仍在运行，但同目录残留旧 `diagnostics.json`”时应优先指向 `prompt.md` / `events.jsonl`。
2. 再补目录清理测试，覆盖“恢复后重试同一轮编号”时只删除已知循环产物、保留无关文件。
3. 实现后运行 `python3 -m pytest -q tests/test_continuous_task_loop.py`。
4. 通过后运行 `python3 -m ruff check scripts/continuous_task_loop.py tests/test_continuous_task_loop.py` 与 `PYTHONPYCACHEPREFIX=/tmp/rag-pyc python3 -m compileall scripts tests`。

## 实施步骤

1. 读取真实 `output/agent-loop/` 运行态文件，确认 009 目录产物时间先于当前 `active_iteration_started_at`。
2. 先为 handoff 优先级和迭代目录清理补测试。
3. 在 `scripts/continuous_task_loop.py` 中实现“活动轮次提示 + 旧产物清理”。
4. 更新 `README.md`、`RUNBOOK.md`、`docs/continuous-task-loop.md` 和运行态交接文件。

## 实施记录

- 方案摘要：
  - 在 `build_handoff_prompt` 中新增“活动轮次仍在运行”提示：当 `loop_pid` 仍活着且 `active_iteration` 尚未记入 `history` 时，handoff 会优先指向该轮的 `prompt.md` 和 `events.jsonl`。
  - 在失败诊断选择逻辑中忽略“仍在运行的活动轮次”目录，避免把该目录里残留的旧 `diagnostics.json` 误当作当前最新失败。
  - 在 `prepare_iteration_directory` 中清理 `prompt.md`、`events.jsonl`、`last-message.md`、`diagnostics.json`、`stderr.log`，确保恢复后重试同一轮编号时不会混入旧证据。
- 关键决策：
  - 不改变迭代编号和 `history` 语义，避免把恢复机制升级为更高风险的状态迁移。
  - 目录清理只覆盖脚本自己生成的已知文件，保留其他未识别文件，尽量减少误删风险。
  - handoff 是否视作“活动轮次仍在运行”以 `loop_pid` 存活且 `active_iteration > latest_recorded_iteration` 为准，避免影响正常失败轮次诊断。
- 变更文件：
  - `scripts/continuous_task_loop.py`
  - `tests/test_continuous_task_loop.py`
  - `README.md`
  - `RUNBOOK.md`
  - `docs/continuous-task-loop.md`
  - `docs/agent-runs/2026-03-15-loop-iteration-009.md`
  - `output/agent-loop/TASK_QUEUE.md`
  - `output/agent-loop/NEXT_ACTION.md`
  - `output/agent-loop/LOOP_MEMORY.md`

## 验证结果

- `python3 -m pytest -q tests/test_continuous_task_loop.py`
  - 结果：通过（`26 passed in 3.88s`）
- `python3 -m ruff check scripts/continuous_task_loop.py tests/test_continuous_task_loop.py`
  - 结果：通过
- `PYTHONPYCACHEPREFIX=/tmp/rag-pyc python3 -m compileall scripts tests`
  - 结果：通过

## 风险清单

- 当前真实 `output/agent-loop/` 中 `loop_pid=42370` 仍存活，本轮只缓解了陈旧产物误导，不代表已经解释清楚它为什么尚未收尾。
- 如果当前主循环是在本轮改动前启动，它不会自动获得目录清理与 handoff 新逻辑；需要下一次重启 / 恢复后才会实际生效。
- 清理逻辑目前只针对脚本已知文件；若未来新增新的轮次级产物文件，需要同步把它加入清理白名单。

## 未覆盖项

- 尚未记录子会话 PID、attempt 序号或“这轮是第几次重试”的额外元数据，因此仍不容易完全复原恢复链路。
- 尚未直接修复 `wss://aixj.vip/responses` 的 DNS 解析失败；网络根因仍需外部配置或连通性恢复后验证。
- 尚未在真实新建 `state-dir` 的恢复场景下复跑一次“先失败再恢复重试同编号”的完整链路，只覆盖了本地单元测试。

## 回滚步骤

1. 回退 `scripts/continuous_task_loop.py`、`tests/test_continuous_task_loop.py`、`README.md`、`RUNBOOK.md`、`docs/continuous-task-loop.md` 的本轮改动。
2. 删除或恢复 `docs/agent-runs/2026-03-15-loop-iteration-009.md` 与本轮更新的 `output/agent-loop/` 交接文件。
3. 重新运行 `python3 -m pytest -q tests/test_continuous_task_loop.py`，确认回到上一稳定状态。

## 上线检查项

- 确认下一次 handoff 在 `active_iteration` 仍进行中时，会优先展示 `prompt.md` / `events.jsonl`，而不是残留的旧失败诊断。
- 确认守护恢复重试同一轮编号后，`iterations/<n>/` 下不会残留上一次尝试的 `diagnostics.json`、`last-message.md` 或 `events.jsonl`。

## 后续建议

- 下一轮继续排查真实 `loop_pid=42370` 为什么在 `active_iteration=9` 阶段长时间存活，重点区分“当前子会话仍在跑”与“外层 loop 卡在收尾逻辑”。
- 若需要进一步彻底溯源，可考虑为活动轮次补 `child_pid` 或 `attempt` 元数据，让恢复后的同编号重试与旧尝试更容易区分。
