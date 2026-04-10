# 2026-03-15 持续循环迭代 014

- 任务名称：持续循环迭代 014
- 项目类型：C 成熟项目优化 / 重构
- 次类型：B 现有项目新增连续循环诊断可操作性增量
- 风险等级：R2

## 正式执行前说明

- 目标：
  - 在不依赖外部网络恢复的前提下，把 `iterations/<n>/diagnostics.json` 从“只有摘要”增强为“可直接指导排障”的结构化诊断。
  - 让下一轮会话或人工接管者更快区分 `HTTP 426`、DNS 解析失败等网络类阻塞，并减少被重复 transport 日志和 warning 干扰的概率。
- 非目标：
  - 不在本轮修复外部 Codex 端点、代理、DNS 或网络连通性问题。
  - 不在本轮引入新的守护进程、自动恢复策略或状态文件 schema 变更。
- 约束：
  - 必须以仓库文件和本地命令输出作为唯一事实源。
  - 必须遵循 `tdd-workflow`：先写测试，再写实现。
  - 结束前必须同步更新任务日志、连续循环文档和 `output/agent-loop/` 交接文件。
- 风险：
  - `diagnostics.json` 属于连续循环排障入口，字段语义改坏会误导 handoff 和人工接管。
  - 新增提示语若过度推断，会把“现象”错误包装成“根因”，需要坚持保守、可验证表述。
- 验收标准：
  - `diagnostics.json` 能输出稳定的失败分类字段，至少覆盖 `websocket_http_error` 与 `dns_lookup_error`。
  - 对重复 transport 错误提供压缩后的聚合视图，减少人工逐条数日志。
  - 对常见网络阻塞输出保守的排障提示，并在文档中说明如何消费这些新字段。

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
  - 面向连续循环失败诊断的结构化“下一步排障提示”
- 本轮必须先补齐的项：
  - 用任务日志固化本轮方案对比、测试计划和回滚方式。
  - 给 `diagnostics.json` 增加更适合交接消费的失败分类 / 聚合 / 提示字段。

## 当前项目类型 / 当前风险等级

- 当前项目类型：`C 成熟项目优化 / 重构`
- 当前风险等级：`R2`

## 仓库现状

- `scripts/continuous_task_loop.py` 已能为失败轮次生成 `diagnostics.json`，包含 warning、错误消息、transport 错误和摘要。
- 当前真实失败证据主要集中在 `output/agent-loop/iterations/009/diagnostics.json`、`013/diagnostics.json`、`015/diagnostics.json`，都出现了大量重复的 DNS transport 报错。
- `output/agent-loop/iterations/014/events.jsonl` 又出现了 `HTTP 426 Upgrade Required`，说明当前阻塞模式至少有两类，且 warning 与失败信息混杂在同一诊断文件里。

## 缺失机制清单

- 缺少统一的 `failure_category`，导致接管者仍需人工从 `transport_errors[0]` 里推断失败类型。
- 缺少重复 transport 错误的聚合视图，当前 `diagnostics.json` 对 DNS 场景会堆出多条几乎相同的错误。
- 缺少保守的 `recovery_hints`，导致“下一步该查 DNS、代理还是 websocket upgrade”仍依赖人工经验。

## 运行态证据

- 本轮读取了 `output/agent-loop/iterations/014/events.jsonl`，确认同一轮次里同时存在：
  - `Under-development features enabled: responses_websockets_v2`
  - `failed to connect to websocket: HTTP error: 426 Upgrade Required, url: wss://aixj.vip/responses`
- 本轮读取了 `output/agent-loop/iterations/009/diagnostics.json`、`010/diagnostics.json`、`011/diagnostics.json`、`013/diagnostics.json`、`015/diagnostics.json`，确认 DNS 失败场景会重复写入多条同类 transport 错误。

## 方案对比

- 方案 A：保持 `diagnostics.json` 现状，只在文档里补充“如何手工解读 warnings / transport_errors”。
  - 复杂度：低
  - 性能：无额外开销
  - 成本：低
  - 侵入性：低
  - 兼容性：高
  - 维护成本：中，判断逻辑继续分散在人脑和文档里
  - 回滚难度：低
- 方案 B：为 `diagnostics.json` 增加失败分类、transport 聚合视图和保守排障提示，并补测试与文档。
  - 复杂度：低到中
  - 性能：低，仅在失败轮次做本地字符串分析和聚合
  - 成本：低
  - 侵入性：低，不改外部命令接口
  - 兼容性：高，新增字段可被旧消费方忽略
  - 维护成本：低，诊断语义集中在单一 helper
  - 回滚难度：低
- 推荐方案：
  - 采用方案 B，以最小 schema 扩展换取更可操作的失败交接。
- 是否需要 ADR：
  - 否。本轮不新增基础设施、不改数据库、不改核心调用链。

## 测试计划

- 验收测试：
  1. `build_iteration_diagnostics()` 在 `HTTP 426` 场景下输出 `failure_category` 与 websocket upgrade 相关提示。
  2. `build_iteration_diagnostics()` 在重复 DNS 报错场景下输出压缩后的 transport 聚合信息与 DNS/代理相关提示。
- 回归测试：
  3. 现有 fake codex 失败场景继续生成 `diagnostics.json`，并包含新的分类 / 提示字段。
  4. 文档连通性测试继续通过，确保 README / RUNBOOK / `docs/continuous-task-loop.md` 都提到新的诊断能力。
- 边界测试：
  5. 当只有 warning 没有 transport 错误时，不把 warning 误判成失败根因。
- 实现后验证命令：
  6. `python3 -m pytest -q tests/test_continuous_task_loop.py`
  7. `python3 -m ruff check scripts/continuous_task_loop.py tests/test_continuous_task_loop.py`
  8. `PYTHONPYCACHEPREFIX=/tmp/rag-pyc python3 -m compileall scripts tests`

## 实施步骤

1. 先补失败诊断测试，锁定新增字段和提示语义。
2. 调整 `scripts/continuous_task_loop.py` 的诊断构建逻辑，增加失败分类、transport 聚合和排障提示。
3. 更新 README / RUNBOOK / `docs/continuous-task-loop.md` 对 `diagnostics.json` 的说明。
4. 运行针对性验证并更新本任务日志、`TASK_QUEUE.md`、`NEXT_ACTION.md`、`LOOP_MEMORY.md`。

## 实施记录

- 在 `tests/test_continuous_task_loop.py` 中先补了 3 类断言：
  - `build_iteration_diagnostics()` 在 `HTTP 426` 场景下输出 `failure_category`、`transport_error_groups` 和 websocket upgrade 排障提示
  - 重复 DNS transport 报错会被聚合成单条 group，并输出 DNS / 代理方向的 `recovery_hints`
  - 文档连通性测试要求 README / RUNBOOK / `docs/continuous-task-loop.md` 都提到 `failure_category` 与 `recovery_hints`
- 首轮针对性测试先失败，确认新增字段当前不存在，随后再进入实现。
- 在 `scripts/continuous_task_loop.py` 中新增：
  - `summarize_transport_error_groups()`：按 `kind + component + url + http_status + status_reason` 聚合重复 transport 报错
  - `derive_failure_category()`：对失败轮次给出稳定的一级分类
  - `build_recovery_hints()`：基于失败分类、warning 和 transport 证据生成保守的排障提示
- `build_iteration_diagnostics()` 现在会输出：
  - `failure_category`
  - `transport_error_groups`
  - `recovery_hints`
  - 同时保留原有 `warnings`、`error_messages`、`transport_errors` 与 `summary`，保证兼容
- 在 `README.md`、`RUNBOOK.md`、`docs/continuous-task-loop.md` 中补充了 `diagnostics.json` 新字段和推荐阅读顺序。

## 验证结果

- `python3 -m pytest -q tests/test_continuous_task_loop.py -k 'build_iteration_diagnostics or docs_and_gitignore_are_wired or max_iterations_still_returns_failure_when_child_session_errors'`：先失败后通过，完成 TDD 闭环
- `python3 -m pytest -q tests/test_continuous_task_loop.py`：通过，`34 passed`
- `python3 -m ruff check scripts/continuous_task_loop.py tests/test_continuous_task_loop.py`：通过
- `PYTHONPYCACHEPREFIX=/tmp/rag-pyc python3 -m compileall scripts tests`：通过

## 关键决策

- 新增字段只扩展 `diagnostics.json`，不替换旧字段，避免已有消费方被破坏。
- `failure_category` 只做一级失败归类，不把现象直接升级成“已确认根因”。
- 用 `transport_error_groups` 压缩重复 transport 报错，但仍保留原始 `transport_errors` 数组，兼顾排障效率与原始证据。
- 对 `Under-development features enabled` 只输出“不要误判为根因”的提示，不把“静默 warning”当作本轮重点。

## 变更文件

- `scripts/continuous_task_loop.py`
- `tests/test_continuous_task_loop.py`
- `README.md`
- `RUNBOOK.md`
- `docs/continuous-task-loop.md`
- `docs/agent-runs/2026-03-15-loop-iteration-014.md`
- `output/agent-loop/TASK_QUEUE.md`
- `output/agent-loop/NEXT_ACTION.md`
- `output/agent-loop/LOOP_MEMORY.md`

## 风险清单

- 诊断提示只能描述“高概率排查方向”，不能把现象直接断言为根因。
- 新字段会扩展 `diagnostics.json` 内容，但仍需保持旧字段兼容，避免已有消费方读取失败。

## 未覆盖项

- 仍未在可连通的真实 Codex 后端环境里复跑新的 `state-dir` non-dry-run 链路。
- 本轮不会自动修复网络阻塞或 stale 状态，只提升诊断可读性与交接效率。

## 上线检查项

- 确认失败轮次生成的 `diagnostics.json` 包含新的失败分类和排障提示。
- 确认 README / RUNBOOK / `docs/continuous-task-loop.md` 已同步说明新字段用法。

## 回滚步骤

1. 回退 `scripts/continuous_task_loop.py`、相关测试、文档和本轮交接文件。
2. 重新运行本轮验证命令，确认 `diagnostics.json` 恢复到上一稳定结构。

## 后续建议

- 下一轮若继续命中真实网络失败，可优先看 `diagnostics.json` 中新增的失败分类和排障提示，再决定是查 DNS、代理还是 websocket upgrade。
- 若后续需要跨多轮比较真实失败是否同源，可在本轮新增分类字段基础上继续考虑引入失败指纹或跨轮聚合统计。
