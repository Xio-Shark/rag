# 2026-03-15 持续循环迭代 006

- 任务名称：持续循环迭代 006
- 项目类型：C 成熟项目优化 / 重构
- 次类型：B 现有项目新增功能
- 风险等级：R2

## 正式执行前说明

- 目标：
  - 在隔离的新 `state-dir` 中执行一次真实 non-dry-run 单轮短跑，验证 `active_iteration*` 生命周期。
  - 同时确认首轮生成或预置的 `TASK_QUEUE.md`、`NEXT_ACTION.md`、`LOOP_MEMORY.md`、`HANDOFF_PROMPT.md` 能支撑顺畅交接。
  - 在不扩大范围的前提下，为主 `output/agent-loop/` 队列关闭至少一个待办项。
- 非目标：
  - 不修改主业务 API、数据库、前端页面或发布链路。
  - 不把当前主 `output/agent-loop/` 目录直接切到真实长跑。
  - 不在本轮引入新的调度器、基础设施或外部依赖。
- 约束：
  - 仅以仓库文件和本轮实际命令结果为事实源，不假设上一轮聊天上下文。
  - 必须遵守 `HOOK.md` / `STANDARDS.md`，先完成方案对比、测试计划和任务日志，再进入实际验证。
  - 当前环境无法依赖 `ps` 等受限系统命令判断外层进程状态，验证应以隔离 `state-dir` 和落盘状态文件为准。
- 风险：
  - 真实 `codex exec` 子会话具备仓库写权限，如果提示不够收敛，可能带来超出预期的改动。
  - 若本机当前登录态或嵌套 `codex exec` 能力不可用，真实 short run 可能失败，从而无法完成待验证项。
  - 如果仅依赖运行结束后的 `state.json`，可能遗漏“运行中 active_iteration 已落盘”的生命周期证据。
- 验收标准：
  - 隔离 short run 中能实际观察到 `state.json` 的 `active_iteration=1`、`active_iteration_started_at`、`active_iteration_dir` 非空。
  - short run 结束后 `active_iteration*` 被清空，`history`、`last_thread_id`、`HANDOFF_PROMPT.md`、`iterations/001/*` 产物完整。
  - 本轮以任务日志和主 `output/agent-loop/` 交接文件记录结论，明确是否可勾选现有 backlog。
- 当前项目类型：
  - 主类型：C 成熟项目优化 / 重构
  - 次类型：B 现有项目工具化增强
- 当前风险等级：
  - R2：本轮不改业务功能，但要真实触发自动化 harness 与嵌套 `codex exec`，不确定性高于普通文档改动。

## 仓库探测结果

- 已存在项：
  - README：`README.md`
  - 架构文档：`ARCHITECTURE.md`
  - 实施计划：`IMPLEMENTATION_PLAN.md`
  - 测试框架：`pytest`、Playwright / 视觉回归相关目录、`tests/`
  - CI：`.github/workflows/`
  - 环境变量模板：`.env.example`
  - 日志机制：`output/agent-loop/*.log`、迭代目录 `events.jsonl`
  - 迁移机制：`migrations/`、`alembic.ini`
  - 回滚方式：`RUNBOOK.md`
- 缺失项：
  - 统一特性开关机制
  - 统一应用级结构化日志规范
  - 可用的 Git 元信息 / worktree 审计能力
- 本轮必须先补齐的项：
  - 新建本轮任务日志并补齐方案对比、测试计划
  - 读取 `output/agent-loop/` 当前运行态并据此选择最小增量
  - 用隔离 short run 获取真实生命周期证据

## 方案对比

- 方案 A：直接用默认模板启动新的真实 `state-dir`，不预置约束，跑一次 `--max-iterations 1`。
  - 复杂度：最低
  - 性能：接近真实
  - 成本：低
  - 侵入性：中到高，子会话可能自行扩大修改范围
  - 兼容性：高
  - 维护成本：低
  - 回滚难度：中，需清理潜在额外改动
- 方案 B：预置隔离 `state-dir` 的 queue / next action / memory，把真实 short run 限定为“只修改该 `state-dir` 与任务日志”。
  - 复杂度：低
  - 性能：同样接近真实，仅多一步准备文件
  - 成本：低
  - 侵入性：低，副作用更可控
  - 兼容性：高，与现有脚本契约一致
  - 维护成本：低
  - 回滚难度：低，删除临时目录即可
- 推荐方案：
  - 采用方案 B，在真实 non-dry-run 前先收紧运行态指令，降低嵌套会话意外改仓库的概率。
- 是否需要 ADR：
  - 否。本轮不引入基础设施，不改数据库结构、认证授权或核心业务调用链。

## 测试计划

1. 在 `/tmp` 新建隔离 `state-dir`，预置最小 queue / next action / loop memory，明确 short run 只允许修改该目录与本轮任务日志。
2. 用真实 `python3 scripts/continuous_task_loop.py --state-dir <tmp> --max-iterations 1` 启动 non-dry-run，并在进程执行期间轮询 `state.json`，捕获 `active_iteration*` 已落盘的证据。
3. 进程结束后检查 `state.json`、`HANDOFF_PROMPT.md`、`iterations/001/*`、`TASK_QUEUE.md`、`NEXT_ACTION.md`、`LOOP_MEMORY.md` 是否与预期一致。
4. 若 short run 成功，再更新主 `output/agent-loop/` 的 `TASK_QUEUE.md`、`NEXT_ACTION.md`、`LOOP_MEMORY.md` 作为交接。

## 实施步骤

1. 记录本轮正式执行前说明与方案对比。
2. 准备隔离 `state-dir` 的运行态文件。
3. 启动真实 non-dry-run short run，并在运行中/结束后采集证据。
4. 回填任务日志、更新主运行态交接文件。

## 实施记录

- 方案摘要：
  - 先在隔离 `/tmp` `state-dir` 中执行了一次真实 non-dry-run short run，确认 `active_iteration*` 能在运行中落盘并在结束后清空。
  - short run 同时暴露出一个 harness 问题：当子会话实际返回非零时，只要该轮刚好命中 `max_iterations_reached`，外层脚本仍会返回成功退出码。
  - 随后补了一条失败场景测试，修正 `scripts/continuous_task_loop.py` 的退出语义，并同步更新运行文档。
- 关键决策：
  - 保持 `state.json.status=max_iterations_reached` 不变，避免扩大状态机范围；只修正外层进程退出码，使它不再掩盖子会话失败。
  - 用 fake `codex` 失败桩补自动化测试，再复跑一次真实 short run，确认问题已被修复且不依赖人工判断。
- 变更文件：
  - `docs/agent-runs/2026-03-15-loop-iteration-006.md`
  - `scripts/continuous_task_loop.py`
  - `tests/test_continuous_task_loop.py`
  - `docs/continuous-task-loop.md`
  - `RUNBOOK.md`
  - `output/agent-loop/TASK_QUEUE.md`
  - `output/agent-loop/NEXT_ACTION.md`
  - `output/agent-loop/LOOP_MEMORY.md`

## 验证结果

- `python3 -m pytest -q tests/test_continuous_task_loop.py`
  - 结果：通过（`21 passed in 4.28s`）
- `python3 -m ruff check scripts/continuous_task_loop.py tests/test_continuous_task_loop.py`
  - 结果：通过
- `PYTHONPYCACHEPREFIX=/tmp/rag-pyc python3 -m compileall scripts tests`
  - 结果：通过
- 真实 non-dry-run short run（修复前）：
  - `state_dir=/tmp/agent-loop-real-smoke-rhqdnd0s`
  - 观察到 `active_iteration=1`、`active_iteration_started_at`、`active_iteration_dir` 已正确落盘。
  - 子会话实际 `return_code=1`，但外层进程错误地返回 `0`，暴露“`max_iterations_reached` 掩盖失败”的问题。
- 真实 non-dry-run short run（修复后）：
  - `state_dir=/tmp/agent-loop-real-smoke-fixed-1tyavbtn`
  - 观察到运行中 `active_iteration=1`，结束后字段清空，`history[-1].return_code=1`、`result=error`，`HANDOFF_PROMPT.md` 与 `iterations/001/*` 均已生成。
  - 外层进程现已返回 `1`，不再把真实失败误判为成功。
  - 当前环境下子会话失败原因来自 Codex 后端连接错误：`failed to lookup address information`，目标为 `https://aixj.vip/responses` / `wss://aixj.vip/responses`。

## 风险清单

- 当前环境的 Codex 后端连通性仍异常，导致“真实新建 `state-dir` 首轮 run 是否能顺畅完成实际交接”这一问题尚未验证闭环。
- `state.json.status` 仍会记录为 `max_iterations_reached` 等终态；本轮仅修正退出码传播语义，调用方若只看状态文件仍需结合 `history[-1].return_code` 判断最后一轮是否失败。

## 未覆盖项

- 尚未验证 `--watch` 常驻守护在真实 `codex exec` 场景下的长期恢复行为。
- 尚未在 Codex 后端恢复连通后重跑“新建 `state-dir` 首轮模板 / handoff 顺畅性”验证。
- 尚未验证主 `output/agent-loop/` 正在运行的旧进程是否需要人工重启。

## 回滚步骤

1. 删除本轮用于 smoke run 的临时 `state-dir`。
2. 若本轮更新了主 `output/agent-loop/` 交接文件或任务日志，按文件逐项回退到变更前内容。
3. 若 short run 子会话产生超预期改动，按实际文件范围人工回退。

## 后续建议

- 先在可连通 Codex 后端的环境里复跑一次新建 `state-dir` 的真实 short run，重点确认细化后的模板会驱动子会话回写 `TASK_QUEUE.md`、`NEXT_ACTION.md`、`LOOP_MEMORY.md`。
- 若后续需要进一步降低人工甄别成本，可考虑追加一个“最后一轮失败但命中终态时的状态摘要”文档或字段，但这已超出本轮最小增量范围。
