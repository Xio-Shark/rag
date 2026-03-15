# 2026-03-15 持续循环迭代 002

- 任务名称：持续循环迭代 002
- 项目类型：B 现有项目新增功能
- 次类型：C 成熟项目优化 / 重构
- 风险等级：R1

## 正式执行前说明

- 目标：
  - 基于 `output/agent-loop/` 当前运行态选择一个最小但有价值的增量。
  - 把 `scripts/continuous_task_loop.py` 初始化生成的运行态模板从通用待办细化成更具体的 backlog。
  - 在本轮结束前完成代码、文档、验证和运行态交接文件更新。
- 非目标：
  - 不改外层循环的停止条件、超时处理或状态机。
  - 不在本轮做真实非 dry-run 长跑验证。
  - 不修改业务 API、数据库结构、前端工作台。
- 约束：
  - 仅以当前仓库文件为事实源，不假设上一轮聊天内容。
  - 严格遵守 `HOOK.md` / `STANDARDS.md` 顺序，先测试计划再实现。
  - 当前目录不是 Git worktree，不能依赖 Git diff 审计。
- 风险：
  - 模板如果写得过于死板，可能降低脚本在其他目标上的通用性。
  - 若只改脚本不改测试和文档，会导致模板契约漂移。
- 验收标准：
  - 新初始化的 `TASK_QUEUE.md`、`NEXT_ACTION.md`、`LOOP_MEMORY.md` 比当前模板更具体，可直接指导单轮执行。
  - `tests/test_continuous_task_loop.py` 能锁定关键模板结构和文案。
  - `docs/continuous-task-loop.md` 与模板保持一致。
- 当前项目类型：
  - 主类型：B 现有项目新增功能
  - 次类型：C 成熟项目工具化增强
- 当前风险等级：
  - R1：局部脚本、测试、文档和运行态文件改动，不涉及业务接口和数据库。
- 仓库现状：
  - 已存在：`README.md`、`ARCHITECTURE.md`、`IMPLEMENTATION_PLAN.md`、`RUNBOOK.md`、`.env.example`、`tests/`、`.github/workflows/`、`migrations/`、`output/agent-loop/`
  - 缺失：统一特性开关 / 灰度机制、显式统一应用日志机制、本地 Git worktree 元信息
  - 本轮必须先补齐的项：基于当前循环队列的具体方案、测试计划和任务日志
- 缺失机制清单：
  - 运行态默认模板仍偏通用，缺少“先读约束、选最小增量、补方案/测试、完成验证、更新交接”的明确骨架。
  - `LOOP_MEMORY.md` 模板没有把“当前主线 / 最近验证 / 阻塞 / 下一步建议”收敛成固定结构。
- 方案对比：
  - 方案 A：只手工更新当前 `output/agent-loop/*.md`。复杂度最低，但只修当前运行目录，后续新 `state-dir` 仍会生成旧模板。
  - 方案 B：修改 `scripts/continuous_task_loop.py` 初始化模板，并同步测试/文档；本轮再更新当前运行态文件。复杂度低，侵入性小，可复用性最好。
- 推荐方案：
  - 采用方案 B。
- 是否需要 ADR：
  - 否。本轮不引入新基础设施，不改核心业务调用链。
- 测试计划：
  - 先修改 `tests/test_continuous_task_loop.py`，锁定新的默认模板结构和关键文案。
  - 再实现脚本与文档更新。
  - 完成后运行 `pytest`、`ruff`、dry-run、`compileall`。
- 实施步骤：
  - 调整连续循环初始化模板内容。
  - 先写/改测试锁定新模板契约。
  - 修改 `scripts/continuous_task_loop.py`。
  - 更新 `docs/continuous-task-loop.md`。
  - 更新当前 `output/agent-loop/` 交接文件并回填验证、风险、回滚与后续建议。

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
  - 无额外仓库基础项；优先收敛连续循环运行态模板的可执行性

## 实施记录

- 方案摘要：
  - 调整 `scripts/continuous_task_loop.py` 初始化生成的 `TASK_QUEUE.md`、`NEXT_ACTION.md`、`LOOP_MEMORY.md` 模板。
  - 让默认运行态文件直接体现“先读约束、选最小增量、补方案/测试计划、实现后更新交接”的单轮骨架。
  - 同步更新 `tests/test_continuous_task_loop.py`、`docs/continuous-task-loop.md` 和当前 `output/agent-loop/` 交接文件。
- 关键决策：
  - 先把方案、测试计划和约束落盘，再进入测试与实现。
  - 模板细化保持“更具体但仍通用”，避免把默认 backlog 绑定到某个业务子模块。
- 变更文件：
  - `docs/agent-runs/2026-03-15-loop-iteration-002.md`
  - `scripts/continuous_task_loop.py`
  - `tests/test_continuous_task_loop.py`
  - `docs/continuous-task-loop.md`
  - `output/agent-loop/TASK_QUEUE.md`
  - `output/agent-loop/NEXT_ACTION.md`
  - `output/agent-loop/LOOP_MEMORY.md`

## 实施结果

- 已把连续循环默认模板从宽泛占位符升级成更具体的执行 backlog。
- 新模板会默认提醒下一轮先读仓库约束、写任务日志、补测试计划、先测后改、最后更新交接文件。
- 已同步更新当前运行态交接文件，使后续会话直接看到更清晰的 backlog 和下一步。

## 风险清单

- 若模板过于具体，可能限制其他目标场景下的复用；需要保持“具体但不绑定某一业务功能”的平衡。
- 本轮仍未在真实非 dry-run 子会话中验证 `active_iteration*` 字段生命周期。

## 未覆盖项

- 未启动真实非 dry-run 的连续循环子会话。
- 未验证旧外层进程在不重启的情况下会否继续沿用旧模板；按 Python 脚本行为，应视为不会热更新。

## 验证结果

- `python3 -m pytest -q tests/test_continuous_task_loop.py`：通过，`13 passed`
- `python3 -m ruff check scripts/continuous_task_loop.py tests/test_continuous_task_loop.py`：通过
- `python3 scripts/continuous_task_loop.py --goal "连续推进当前仓库，默认不要停，直到完成队列或达到 10 小时上限" --state-dir /tmp/agent-loop-iteration-002-check --dry-run --max-iterations 1`：通过
- `PYTHONPYCACHEPREFIX=/tmp/rag-pyc python3 -m compileall scripts tests`：通过

## 上线检查项

- 若要验证真实生命周期，使用新的临时 `state-dir` 启动一次非 dry-run 短跑，避免污染当前主运行目录。
- 若当前已有旧版本外层循环进程，先停止并用新脚本重启，再做真实验证。
- 真实运行后检查 `state.json`、`NEXT_ACTION.md` 和 `HANDOFF_PROMPT.md` 是否与预期一致。

## 回滚步骤

1. 回退 `scripts/continuous_task_loop.py` 中细化后的三份默认模板文案。
2. 回退 `tests/test_continuous_task_loop.py` 中新增的模板契约断言。
3. 回退 `docs/continuous-task-loop.md` 的默认 backlog 与 loop memory 说明。
4. 如需恢复当前运行态文件，回退 `output/agent-loop/TASK_QUEUE.md`、`output/agent-loop/NEXT_ACTION.md`、`output/agent-loop/LOOP_MEMORY.md`。
5. 保留或删除本任务日志均可，不影响脚本运行。

## 后续建议

- 下一轮优先做一次真实非 dry-run 的短跑循环，形成 `active_iteration*` 生命周期的实机证据。
- 验证时优先使用新的临时 `state-dir`，避免与当前主运行目录互相覆盖。
