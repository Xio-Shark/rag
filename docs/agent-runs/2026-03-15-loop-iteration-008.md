# 2026-03-15 持续循环迭代 008

- 任务名称：持续循环迭代 008
- 项目类型：C 成熟项目优化 / 重构
- 次类型：D 故障排查支撑能力增强
- 风险等级：R2

## 正式执行前说明

- 目标：
  - 为 `scripts/continuous_task_loop.py` 增加“状态文件落后于磁盘迭代产物”时的 handoff 诊断兜底，降低下一轮排障时被陈旧 `state.json` 误导的概率。
  - 在不依赖外部网络恢复的前提下，把当前 `output/agent-loop/` 中已观测到的状态漂移现象沉淀为脚本级兼容能力。
  - 为下一轮真实连通性复跑提供更可靠的失败定位入口，避免只因状态滞后而看不到最新 `diagnostics.json`。
- 非目标：
  - 不直接修复外部 Codex 后端连通性、DNS、代理或远端端点配置。
  - 不在本轮引入进程锁、全量状态重建、后台 supervisor 重构或新的持久化格式。
  - 不修改主业务 API、数据库 schema、前端页面或部署链路。
- 约束：
  - 仅以仓库文件与当前命令结果为事实源，不假设上一轮聊天内容正确。
  - 当前环境网络受限，本轮只能基于现有运行态产物、单元测试与本地 fake `codex` 场景验证。
  - 必须先补测试计划和任务日志，再进入实现；完成后同步更新运行态交接文件。
- 风险：
  - 如果“最新失败”判定过度激进，可能把更早的 `diagnostics.json` 错误地展示给下一轮会话。
  - 如果扫描磁盘产物的规则过于宽松，可能把只创建了目录但未真正完成的轮次误判为最新失败。
  - handoff 逻辑是连续循环的关键恢复入口，必须保持对现有成功路径零侵入。
- 验收标准：
  - 当 `state.json` / `history` 落后于磁盘中的最新失败轮次时，handoff 仍能指向最新 `iterations/<n>/diagnostics.json`。
  - 当更高编号轮次存在但并没有失败诊断文件时，handoff 不会错误回退到更早失败，避免误导下一轮。
  - `tests/test_continuous_task_loop.py`、`docs/continuous-task-loop.md`、`RUNBOOK.md`、`README.md` 与本轮任务日志同步更新，并通过针对性验证。
- 当前项目类型：
  - 主类型：C 成熟项目优化 / 重构
  - 次类型：D 故障排查支撑能力增强
- 当前风险等级：
  - R2：改动集中在本地循环 harness，但涉及 handoff 和失败诊断入口，属于恢复链路关键行为。

## 仓库探测结果

- 已存在项：
  - README：`README.md`
  - 架构文档：`ARCHITECTURE.md`
  - 实施计划：`IMPLEMENTATION_PLAN.md`
  - 测试框架：`pytest`、Playwright、`tests/`
  - CI：`.github/workflows/`
  - 环境变量模板：`.env.example`
  - 日志机制：`output/agent-loop/*.log`、`iterations/*/events.jsonl`
  - 迁移机制：`migrations/`、`alembic.ini`
  - 回滚方式：`RUNBOOK.md`
- 缺失项：
  - 统一特性开关机制
  - 统一应用级结构化日志规范
  - 连续循环运行态与磁盘迭代产物之间的显式一致性校验机制
- 本轮必须先补齐的项：
  - 新建本轮任务日志并补齐方案对比、测试计划和回滚说明
  - 为 handoff 增加“状态滞后时读取最新失败诊断”的兜底逻辑
  - 同步 README / RUNBOOK / 连续循环文档，写清该兜底的适用场景与边界

## 方案对比

- 方案 A：只更新文档，要求人工同时查看 `state.json` 和 `iterations/` 目录，遇到漂移手工判断最新失败。
  - 复杂度：最低
  - 性能：无额外运行时开销
  - 成本：低
  - 侵入性：低
  - 兼容性：高
  - 维护成本：中，依然依赖人工识别漂移
  - 回滚难度：低
- 方案 B：在 handoff 生成时增加轻量磁盘扫描；若发现更高编号轮次已落盘 `diagnostics.json`，优先引用该失败诊断。
  - 复杂度：低到中
  - 性能：低，仅在 handoff 生成时扫描本地 `iterations/` 目录
  - 成本：低
  - 侵入性：低，限定在连续循环 harness 内
  - 兼容性：高，成功路径仍沿用现有状态文件
  - 维护成本：低，规则边界清晰
  - 回滚难度：低，回退脚本和文档即可
- 推荐方案：
  - 采用方案 B，以最小代码改动增强 handoff 对状态漂移的容错，同时避免引入新的状态字段或复杂恢复机制。
- 是否需要 ADR：
  - 否。本轮不引入基础设施依赖，不改数据库、认证授权、核心业务调用链或部署架构。

## 测试计划

1. 先补测试，覆盖“状态历史落后，但磁盘上有更高编号失败诊断”时 handoff 的选择逻辑。
2. 再补边界测试，覆盖“更高编号轮次存在但没有 `diagnostics.json`”时不应错误引用旧失败。
3. 实现脚本改动后运行 `python3 -m pytest -q tests/test_continuous_task_loop.py`。
4. 通过后运行 `python3 -m ruff check scripts/continuous_task_loop.py tests/test_continuous_task_loop.py` 与 `PYTHONPYCACHEPREFIX=/tmp/rag-pyc python3 -m compileall scripts tests`。

## 实施步骤

1. 记录本轮正式执行前说明与方案对比。
2. 先补 handoff / diagnostics 相关测试，锁定状态漂移场景的预期行为。
3. 在 `scripts/continuous_task_loop.py` 中实现最新失败诊断路径的磁盘兜底。
4. 更新 `docs/continuous-task-loop.md`、`RUNBOOK.md`、`README.md` 和运行态交接文件。

## 实施记录

- 方案摘要：
  - 先为 `build_handoff_prompt` 补了两类测试：一类验证 `state.json/history` 落后时优先引用磁盘中更高编号失败轮次的 `diagnostics.json`；另一类验证当更新轮次没有失败诊断时，不会误回退到更旧失败。
  - 在 `scripts/continuous_task_loop.py` 中新增轻量扫描逻辑：识别 `iterations/` 下最新已落盘结果文件的轮次，并在它领先于状态记录时优先读取对应 `diagnostics.json`。
  - 同步更新 `README.md`、`RUNBOOK.md`、`docs/continuous-task-loop.md`，把“状态滞后时如何理解 handoff / diagnostics”的规则写明。
- 关键决策：
  - 不直接修改 `state.json` 的历史和计数，只增强 handoff 的失败诊断入口，避免在证据不足时误重建状态。
  - 对“最新轮次”采用保守判定：只有目录中已出现 `events.jsonl`、`last-message.md`、`diagnostics.json` 或 `stderr.log` 等结果文件时，才视为真正有产物可参考。
  - 当磁盘上存在更高编号轮次但没有失败诊断文件时，handoff 明确不展示更旧失败，避免把上一类错误误认为当前真实阻塞。
- 变更文件：
  - `scripts/continuous_task_loop.py`
  - `tests/test_continuous_task_loop.py`
  - `docs/continuous-task-loop.md`
  - `RUNBOOK.md`
  - `README.md`
  - `docs/agent-runs/2026-03-15-loop-iteration-008.md`
  - `output/agent-loop/TASK_QUEUE.md`
  - `output/agent-loop/NEXT_ACTION.md`
  - `output/agent-loop/LOOP_MEMORY.md`

## 验证结果

- `python3 -m pytest -q tests/test_continuous_task_loop.py`
  - 结果：通过（`24 passed in 3.78s`）
- `python3 -m ruff check scripts/continuous_task_loop.py tests/test_continuous_task_loop.py`
  - 结果：通过
- `PYTHONPYCACHEPREFIX=/tmp/rag-pyc python3 -m compileall scripts tests`
  - 结果：通过

## 风险清单

- 本轮只增强 handoff 的诊断入口，没有直接修复真实 `output/agent-loop/` 中已观察到的 `state.json` / `iterations/` 漂移根因。
- 当前仓库内最新失败证据已不只一种：旧轮次存在 `HTTP 426 Upgrade Required`，而 `output/agent-loop/iterations/008/diagnostics.json` 与 `output/agent-loop/iterations/009/diagnostics.json` 还显示 `wss://aixj.vip/responses` 的 DNS 解析失败。
- 当前 `state.json` 仍显示 `iteration_count=7`、`active_iteration=8`，但磁盘上已经存在 `iterations/009`，且 `loop_pid=42370` 仍存活；这说明真实运行态可能还有额外进程 / 退出路径问题待查。

## 未覆盖项

- 尚未实现 `state.json` 与磁盘迭代目录的一致性修复、进程锁或并发保护；本轮仅确保 handoff 优先指向较新的失败诊断。
- 尚未在真实可连通环境中复跑新建 `state-dir` 的首轮验证，因此仍未闭环“细化模板会否驱动子会话完整回写三份交接文件”。

## 回滚步骤

1. 回退 `scripts/continuous_task_loop.py`、`tests/test_continuous_task_loop.py`、`README.md`、`RUNBOOK.md`、`docs/continuous-task-loop.md` 的本轮改动。
2. 删除或恢复 `docs/agent-runs/2026-03-15-loop-iteration-008.md` 与本轮更新的 `output/agent-loop/` 交接文件内容。
3. 重新运行 `python3 -m pytest -q tests/test_continuous_task_loop.py`，确认回到上一稳定状态。

## 上线检查项

- 确认下一次生成的 `HANDOFF_PROMPT.md` 在状态滞后时会优先引用磁盘中的最新失败诊断路径。
- 确认接手会话遇到 `state.json` / `iterations/` 漂移时，先看较新 `diagnostics.json`，而不是被更旧失败误导。

## 后续建议

- 下一轮优先排查真实 `output/agent-loop/` 中的 `state.json` / `iterations/` 漂移和仍存活的 `loop_pid`，判断是否存在退出路径卡住、并发写入或状态回写覆盖问题。
- 若外部连通性恢复，再用全新 `state-dir` 复跑真实 non-dry-run 首轮 short run，确认 handoff 兜底和三份交接文件回写都符合预期。
