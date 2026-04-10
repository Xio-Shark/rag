# 2026-03-15 持续循环迭代 007

- 任务名称：持续循环迭代 007
- 项目类型：C 成熟项目优化 / 重构
- 次类型：D 故障排查支撑能力增强
- 风险等级：R2

## 正式执行前说明

- 目标：
  - 为 `scripts/continuous_task_loop.py` 的失败轮次补结构化诊断产物，降低下一轮会话对人工读长日志的依赖。
  - 在不恢复真实外部连通性的前提下，把当前“后端连通性 / 端点配置异常”的排障线索沉淀为可复用的本地能力。
  - 为主 `output/agent-loop/` 队列增加一个小而明确的可交付增量，帮助下一轮更快定位真实阻塞点。
- 非目标：
  - 不直接修复外部 Codex 后端连通性、账号态或远端服务配置。
  - 不修改主业务 API、数据库 schema、前端页面或部署链路。
  - 不引入新的外部依赖、后台服务或独立诊断平台。
- 约束：
  - 仅以仓库文件与本轮命令结果为事实源，不假设上一轮聊天内容正确。
  - 当前运行环境网络受限，无法依赖真实在线请求闭环验证，只能通过脚本、测试和现有落盘产物增强诊断能力。
  - 必须先写/更新测试，再进入实现，并在结束前同步更新运行态交接文件。
- 风险：
  - 如果诊断规则过度依赖单一日志格式，后续 Codex CLI 输出变化时可能退化为误报或漏报。
  - 若把原始环境信息直接写入诊断文件，存在泄露敏感配置的风险；本轮实现必须避免记录敏感值。
  - handoff 摘要如果覆盖过多上下文，可能掩盖子会话真实最后消息，因此需要只在失败且缺少明确最终消息时做回退。
- 验收标准：
  - 失败轮次会在 `iterations/<n>/` 下生成可直接复用的结构化诊断文件。
  - 诊断结果至少能提炼错误项、传输层报错和简短摘要，并在缺少最终消息时用于 handoff 回退。
  - `tests/test_continuous_task_loop.py`、`docs/continuous-task-loop.md`、`RUNBOOK.md` 与本轮任务日志同步更新，并通过针对性验证。
- 当前项目类型：
  - 主类型：C 成熟项目优化 / 重构
  - 次类型：D 故障排查支撑能力增强
- 当前风险等级：
  - R2：改动集中在本地自动化 harness，但涉及连续循环核心失败处理与交接行为，需谨慎保持兼容。

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
  - 连续循环失败轮次的结构化诊断摘要
- 本轮必须先补齐的项：
  - 新建本轮任务日志并补齐方案对比、测试计划
  - 为失败轮次增加结构化诊断产物与最小摘要
  - 同步运行文档和运行态交接文件，避免下一轮继续手工翻长日志

## 方案对比

- 方案 A：仅补文档与运行手册，约定人工去读 `events.jsonl` 排查。
  - 复杂度：最低
  - 性能：无运行时影响
  - 成本：低
  - 侵入性：低
  - 兼容性：高
  - 维护成本：中，后续仍依赖人工总结
  - 回滚难度：低
- 方案 B：在失败轮次中自动生成结构化诊断文件，并把摘要接入 handoff 回退。
  - 复杂度：低到中
  - 性能：低，仅在单轮结束时额外解析已落盘输出
  - 成本：低
  - 侵入性：低，限定在连续循环 harness 内部
  - 兼容性：高，成功路径只新增产物不改既有契约
  - 维护成本：低，后续排障复用价值更高
  - 回滚难度：低，回退脚本和文档即可
- 推荐方案：
  - 采用方案 B，把现有手工排查经验沉淀为脚本内的轻量诊断能力，同时保持改动边界收敛在 harness 内。
- 是否需要 ADR：
  - 否。本轮不引入基础设施依赖，不改数据库、认证授权或核心业务调用链。

## 测试计划

1. 先补单元测试，覆盖诊断解析逻辑：错误事件、传输层报错与摘要生成。
2. 再补 non-dry-run 失败场景测试，确认失败轮次会落盘结构化诊断文件，并在缺少最终消息时用于 handoff 摘要。
3. 实现脚本改动后运行 `python3 -m pytest -q tests/test_continuous_task_loop.py`。
4. 通过后运行 `python3 -m ruff check scripts/continuous_task_loop.py tests/test_continuous_task_loop.py` 与 `PYTHONPYCACHEPREFIX=/tmp/rag-pyc python3 -m compileall scripts tests`。

## 实施步骤

1. 记录本轮正式执行前说明与方案对比。
2. 先补测试，锁定失败诊断文件与 handoff 回退行为。
3. 在 `scripts/continuous_task_loop.py` 中实现结构化诊断提取与落盘。
4. 更新 `docs/continuous-task-loop.md`、`RUNBOOK.md` 和运行态交接文件。

## 实施记录

- 方案摘要：
  - 先补了失败诊断相关测试，覆盖传输层报错解析、诊断摘要生成，以及 non-dry-run 失败轮次的 `diagnostics.json` / handoff 行为。
  - 在 `scripts/continuous_task_loop.py` 中新增失败诊断提取逻辑：从 `events.jsonl` 输出里提炼 `item.error`、`codex_api::endpoint::*` 传输层错误，并在失败轮次下落盘 `iterations/<n>/diagnostics.json`。
  - 当子会话失败且 `last-message.md` 为空时，handoff 现在会回退到结构化诊断摘要，并附上 `diagnostics.json` 路径，方便下一轮直接定位。
- 关键决策：
  - 不去猜测外部配置来源，也不读取仓库外配置文件；仅根据仓库内已有失败日志与当前轮脚本输出生成诊断，保持事实源收敛。
  - 不把敏感环境变量快照写入诊断文件，只保留线程号、返回码、错误项、传输层报错和摘要，兼顾排障价值与安全边界。
  - 诊断产物仅在失败轮次生成，避免为成功路径引入不必要噪音。
- 变更文件：
  - `scripts/continuous_task_loop.py`
  - `tests/test_continuous_task_loop.py`
  - `docs/continuous-task-loop.md`
  - `RUNBOOK.md`
  - `README.md`
  - `docs/agent-runs/2026-03-15-loop-iteration-007.md`
  - `output/agent-loop/TASK_QUEUE.md`
  - `output/agent-loop/NEXT_ACTION.md`
  - `output/agent-loop/LOOP_MEMORY.md`

## 验证结果

- `python3 -m pytest -q tests/test_continuous_task_loop.py`
  - 结果：通过（`22 passed in 4.14s`）
- `python3 -m ruff check scripts/continuous_task_loop.py tests/test_continuous_task_loop.py`
  - 结果：通过
- `PYTHONPYCACHEPREFIX=/tmp/rag-pyc python3 -m compileall scripts tests`
  - 结果：通过

## 风险清单

- 诊断规则目前基于当前已观测到的 `codex_api::endpoint::*` 输出模式；如果未来 Codex CLI 的错误格式变化，摘要质量可能下降，但不会影响主循环成功路径。
- 当前仓库内可复核的失败证据显示 `wss://aixj.vip/responses` 返回 `HTTP 426 Upgrade Required`，并伴随 unstable feature warning；真正的外部端点根因仍未在本轮闭环。

## 未覆盖项

- 尚未在可连通的真实环境中复跑“新建 `state-dir` 首轮交接验证”，因此 `diagnostics.json` 目前只通过 fake `codex` 自动化测试覆盖。
- 尚未为 timeout 场景单独生成结构化诊断文件；当前 timeout 仍主要依赖 `events.jsonl` 和 `stderr.log`。

## 回滚步骤

1. 回退 `scripts/continuous_task_loop.py`、`tests/test_continuous_task_loop.py`、`docs/continuous-task-loop.md`、`RUNBOOK.md`、`README.md` 的本轮改动。
2. 删除或恢复本轮更新的 `docs/agent-runs/2026-03-15-loop-iteration-007.md` 与 `output/agent-loop/` 交接文件内容。
3. 重新运行 `python3 -m pytest -q tests/test_continuous_task_loop.py`，确认回到上一稳定状态。

## 上线检查项

- 确认后续真实 short run 失败时，`iterations/<n>/diagnostics.json` 会随失败轮次一并落盘。
- 确认接手会话优先读取 `diagnostics.json`，而不是继续依赖人工翻长日志。

## 后续建议

- 下一轮优先在真实失败场景中使用新的 `diagnostics.json`，确认当前阻塞到底是 websocket 升级、错误 endpoint 还是外部代理配置问题。
- 如果后续还要处理 timeout / 中断类失败，可沿用同一模式为 timeout 场景补诊断摘要，但这已超出本轮最小范围。
