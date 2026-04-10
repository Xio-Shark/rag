# 2026-03-15 持续循环迭代 003

- 任务名称：持续循环迭代 003
- 项目类型：B 现有项目新增功能
- 次类型：C 成熟项目优化 / 重构
- 风险等级：R1

## 正式执行前说明

- 目标：
  - 基于 `output/agent-loop/` 当前运行态选择一个最小但有价值的增量。
  - 在本轮结束前完成代码、文档、验证和运行态交接文件更新。
- 非目标：
  - 不改业务 API、数据库结构、前端工作台和主业务链路。
  - 不在本轮引入新的调度器、队列或外部基础设施。
  - 不直接把当前主 `output/agent-loop/` 切到真实长跑验证。
- 约束：
  - 仅以当前仓库文件为事实源，不假设上一轮聊天内容。
  - 严格遵守 `HOOK.md` / `STANDARDS.md` 顺序，先完成方案和测试计划再实现。
  - 当前目录不是 Git worktree，不能依赖 `git status` / `git diff` 做变更审计。
- 风险：
  - 真实 `codex exec` 子会话会以仓库根目录运行，直接拿它做非 dry-run 验证有副作用风险。
  - 若 `max_iterations_reached` 继续被当成失败退出，有界 smoke run 会持续不稳定。
- 验收标准：
  - 新增 non-dry-run 集成测试，能稳定覆盖 `active_iteration*` 生命周期、history 与 handoff 落盘。
  - `--max-iterations 1` 这类有界短跑命中上限时被视为预期停止，不再返回失败。
  - 文档、任务日志与运行态交接文件和新行为保持一致。
- 当前项目类型：
  - 主类型：B 现有项目新增功能
  - 次类型：C 成熟项目工具化增强
- 当前风险等级：
  - R1：预计优先选择局部脚本、文档、测试或运行态文件改动；若读完队列后发现涉及关键路径，会在本日志升级风险等级。

## 仓库探测结果

- 已存在项：
  - README：`README.md`
  - 架构文档：`ARCHITECTURE.md`
  - 实施计划：`IMPLEMENTATION_PLAN.md`
  - 测试框架：`pytest`、E2E、视觉回归
  - CI：`.github/workflows/`
  - 环境变量模板：`.env.example`
  - 迁移机制：`migrations/` + `alembic.ini`
  - 回滚方式：`RUNBOOK.md`
- 缺失项：
  - 统一特性开关
  - 显式统一应用日志机制
  - 当前工作区 Git 元信息
- 本轮必须先补齐的项：
  - 读取 `STANDARDS.md`
  - 读取 `output/agent-loop/` 运行态文件
  - 基于当前队列补充方案、测试计划和实现范围

## 实施记录

- 方案摘要：
  - 聚焦 `scripts/continuous_task_loop.py` 的非 dry-run 短跑可验证化。
  - 先用 fake `codex` 二进制补一条 non-dry-run 集成测试，锁定 `active_iteration*`、history、handoff 和产物目录行为。
  - 同时修正命中 `max_iterations_reached` 时的退出语义，使有界 smoke run 成为正常成功停止，而不是伪失败。
- 关键决策：
  - 不直接依赖真实 `codex exec` 做自动化验证，避免子会话在仓库里产生不可控副作用。
  - 优先通过现有 `--codex-bin` 注入点补测试，不为测试额外引入新的生产代码依赖。
  - 将真实 live run 保留为后续可选验证项，本轮先锁定脚本级非 dry-run 路径。
- 变更文件：
  - `docs/agent-runs/2026-03-15-loop-iteration-003.md`

## 方案对比

- 方案 A：直接用真实 `codex exec` + 新 `state-dir` 跑一次 `--max-iterations 1` 短跑，只记录人工验证结果。
  - 复杂度低，最贴近真实环境。
  - 但副作用高、重复性差，也无法稳定进入自动化回归。
- 方案 B：用 fake `codex` 补 non-dry-run 集成测试，并修正 `max_iterations_reached` 退出语义。
  - 复杂度低，侵入性小，可重复，可纳入自动化门禁。
  - 不能完全替代真实模型会话，但足以锁定循环 harness 的脚本责任边界。
- 推荐方案：
  - 采用方案 B。
- 是否需要 ADR：
  - 否。本轮不引入基础设施，不改数据库、认证或核心业务调用链。

## 测试计划

1. 先新增 fake `codex` 的 non-dry-run 集成测试。
2. 在测试里断言运行中 `state.json` 存在 `active_iteration*`，结束后字段被清空，并且 `history`、`HANDOFF_PROMPT.md`、`iterations/001/*` 已正确生成。
3. 增加 `max_iterations_reached` 退出码语义断言，锁定有界短跑为成功停止。
4. 完成实现后运行：
   - `python3 -m pytest -q tests/test_continuous_task_loop.py`
   - `python3 -m ruff check scripts/continuous_task_loop.py tests/test_continuous_task_loop.py`
   - `PYTHONPYCACHEPREFIX=/tmp/rag-pyc python3 -m compileall scripts tests`
   - 一次定向 non-dry-run smoke run

## 实施步骤

1. 补 `tests/test_continuous_task_loop.py`，先锁定 fake `codex` 的 non-dry-run 路径和停止语义。
2. 修改 `scripts/continuous_task_loop.py` 的停止返回逻辑。
3. 更新 `docs/continuous-task-loop.md` 与必要说明文档。
4. 运行验证并回填本任务日志与 `output/agent-loop/` 交接文件。

## 风险清单

- 当前目标是“连续推进”，但本轮仍需控制在一个清晰最小增量内，避免范围失控。
- 当前目录不是 Git worktree，收尾时只能通过文件内容和定向验证确认改动范围。

## 未覆盖项

- 待读取队列后补充。

## 回滚步骤

1. 删除本任务日志文件，或回退后续在本日志中追加的内容。
2. 对本轮实际改动的代码、文档和运行态文件执行逐项回退，具体路径待实现后补充。

## 后续建议

- 待本轮增量确定后补充。
