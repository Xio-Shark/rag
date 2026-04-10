# 2026-03-15 持续循环迭代 010

- 任务名称：持续循环迭代 010
- 项目类型：C 成熟项目优化 / 重构
- 次类型：D 故障排查支撑能力增强
- 风险等级：R2

## 正式执行前说明

- 目标：
  - 基于 `output/agent-loop/` 的最新真实运行态，为连续循环补“尝试级别”的可观测性，降低恢复链路排障时的歧义。
  - 在不改变迭代编号语义的前提下，显式记录“当前是同编号第几次尝试”以及“当前子会话 pid 是谁”，帮助区分“子会话仍在跑”与“外层 loop 卡在收尾”。
  - 让失败诊断、handoff 和 `state.json` 能把同一轮编号下的不同尝试区分开，便于下一轮会话接力。
- 非目标：
  - 不直接修复 `wss://aixj.vip/responses` / `https://aixj.vip/responses` 的 DNS 或网络连通性问题。
  - 不重做 watchdog / supervisor 机制，不新增外部依赖，也不调整迭代编号策略。
  - 不在本轮引入新守护进程、数据库、队列或 attempt 子目录结构。
- 约束：
  - 仅以仓库文件、运行态文件和本地命令结果为事实源，不假设上一轮聊天上下文。
  - 必须先写清方案对比、测试计划和回滚方式，再进入实现。
  - 结束前必须同步更新 `output/agent-loop/TASK_QUEUE.md`、`output/agent-loop/NEXT_ACTION.md`、`output/agent-loop/LOOP_MEMORY.md`。
  - 当前环境网络受限，真实 loop 复跑很可能继续命中传输层失败；本轮以本地测试与当前运行态证据为主。
- 风险：
  - 新增状态字段后，必须兼容已有 `state.json`，避免旧运行目录无法恢复。
  - 如果 attempt 计数规则设计不当，可能把旧目录残留误判成新的多次重试。
  - 如果 `active_child_pid` 清理不完整，handoff 可能错误提示一个已经结束的子进程。
- 验收标准：
  - `state.json` 在活动轮次期间能落盘 `active_iteration_attempt` 与 `active_child_pid`，轮次结束后会清空活动字段。
  - 同编号目录存在旧产物而再次启动时，新的尝试编号会递增，不再只有“同编号”而缺少 attempt 维度。
  - 失败轮次的 `diagnostics.json` 与 `history` 记录包含尝试编号；handoff 对活动轮次至少能展示 attempt / child pid 线索。
  - `tests/test_continuous_task_loop.py`、`README.md`、`RUNBOOK.md`、`docs/continuous-task-loop.md` 与本轮任务日志同步更新，并通过针对性验证。
- 当前项目类型：
  - 主类型：C 成熟项目优化 / 重构
  - 次类型：D 故障排查支撑能力增强
- 当前风险等级：
  - R2：改动集中在 `scripts/continuous_task_loop.py`，但涉及恢复链路、handoff 和状态兼容，属于关键控制面逻辑。

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
  - 连续循环仍缺少尝试级 attempt 元数据与子会话 pid 元数据，导致恢复排障只能看到“轮次编号”，很难区分同编号重试
- 本轮必须先补齐的项：
  - 把本轮方案对比、测试计划、风险与回滚写入任务日志。
  - 为连续循环补一个不改变目录结构的最小状态增强，让“同编号重试”至少能在状态、诊断和 handoff 中留下 attempt / pid 线索。

## 运行态证据

- 重新读取 `output/agent-loop/state.json` 后，当前真实运行态已不再停留在旧的 `active_iteration=9` / `loop_pid=42370`：
  - `status=too_many_failures`
  - `iteration_count=11`
  - `consecutive_failures=3`
  - `loop_pid=null`
  - `active_iteration=null`
- `output/agent-loop/iterations/010/diagnostics.json` 与 `iterations/011/events.jsonl` 说明旧的“疑似未收尾”现象后来继续推进成了 010、011 两轮失败，而不是永久卡死在 009。
- 但从诊断产物来看，当前仍缺少两个关键线索：
  - 同一轮编号到底是第几次尝试
  - 若再次出现活动轮次，当前子会话 pid 是谁
- 因此本轮把目标从“继续猜测 009 是否挂住”收敛为“补元数据，让下一次真实恢复时更容易判断进程状态”。

## 方案对比

- 方案 A：只更新交接文档，记录“009 已自然推进到 011 并停止”的新证据，不改脚本。
  - 复杂度：最低
  - 性能：无额外开销
  - 成本：低
  - 侵入性：低
  - 兼容性：高
  - 维护成本：中，下一次遇到同类问题仍缺少可机读线索
  - 回滚难度：低
- 方案 B：只增加 `active_child_pid`，用于区分当前子进程是否仍在运行。
  - 复杂度：低
  - 性能：低
  - 成本：低
  - 侵入性：低
  - 兼容性：高
  - 维护成本：中，仍无法解决“同编号第几次尝试”的歧义
  - 回滚难度：低
- 方案 C：同时增加 `active_iteration_attempt`、`active_child_pid`，并把 attempt 写入 `history` / `diagnostics.json` / handoff。
  - 复杂度：低到中
  - 性能：低，仅在迭代开始和结束时做少量状态更新
  - 成本：低
  - 侵入性：低，限定在连续循环 harness 内
  - 兼容性：高，可对旧 `state.json` 自动补字段
  - 维护成本：低，语义直接、边界清晰
  - 回滚难度：低
- 推荐方案：
  - 采用方案 C，用最小状态增强同时补足“attempt 维度”和“child pid 维度”。
- 是否需要 ADR：
  - 否。本轮未引入新基础设施、数据库变更、认证授权修改或核心业务架构调整。

## 测试计划

1. 先补状态兼容与活动轮次测试，覆盖 `active_iteration_attempt` / `active_child_pid` 的写入与清理。
2. 再补重试场景测试，覆盖“同编号目录已有旧产物时 attempt 递增”。
3. 再补失败场景测试，覆盖 `diagnostics.json` 与 `history` 包含 `attempt` 字段。
4. 实现后运行 `python3 -m pytest -q tests/test_continuous_task_loop.py`。
5. 通过后运行 `python3 -m ruff check scripts/continuous_task_loop.py tests/test_continuous_task_loop.py`。
6. 最后运行 `PYTHONPYCACHEPREFIX=/tmp/rag-pyc python3 -m compileall scripts tests`。

## 实施步骤

1. 记录本轮运行态新证据，明确旧的“009 未收尾”观察已不再是当前事实。
2. 先为状态字段、attempt 递增和失败诊断补测试。
3. 在 `scripts/continuous_task_loop.py` 中实现 attempt / child pid 元数据落盘与兼容回填。
4. 更新 `README.md`、`RUNBOOK.md`、`docs/continuous-task-loop.md` 与运行态交接文件。

## 实施记录

- 待实现。

## 验证结果

- 待实现。

## 风险清单

- 当前真实阻塞仍是外部端点 / 网络连通性，不是脚本逻辑单点可完全解决的问题。
- 如果未来有更多轮次级产物文件，需要同步评估 attempt 推断是否也应把它们纳入“已有旧尝试”的判定。
- 本轮新增的是可观测性而非根治网络失败；只能降低排障歧义，不能保证真实 run 成功。

## 未覆盖项

- 尚未在真实可连通环境中复跑新建 `state-dir` 首轮恢复链路。
- 尚未解决 `ps` 在当前 sandbox 下不可用的问题；进程树级排查仍受限。

## 回滚步骤

1. 回退 `scripts/continuous_task_loop.py`、`tests/test_continuous_task_loop.py`、`README.md`、`RUNBOOK.md`、`docs/continuous-task-loop.md` 的本轮改动。
2. 删除或恢复 `docs/agent-runs/2026-03-15-loop-iteration-010.md` 与本轮更新的 `output/agent-loop/` 交接文件。
3. 重新运行 `python3 -m pytest -q tests/test_continuous_task_loop.py`，确认恢复到上一稳定状态。

## 上线检查项

- 确认活动轮次期间 `state.json` 会写出 `active_iteration_attempt` 与 `active_child_pid`。
- 确认失败轮次的 `diagnostics.json` / `history` 能区分同编号不同尝试。
- 确认 handoff 在活动轮次时能提示 attempt / child pid 线索，便于下一轮接手。

## 后续建议

- 下一轮在真实恢复场景里验证新增 attempt / child pid 元数据是否足够解释“外层 loop 卡住还是子会话仍在跑”。
- 若网络连通性恢复，再用全新 `state-dir` 复跑 non-dry-run 恢复链路，观察 attempt 是否在同编号重试时正确递增。
