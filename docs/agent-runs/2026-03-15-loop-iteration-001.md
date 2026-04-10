# 2026-03-15 持续循环迭代 001

- 任务名称：持续循环迭代 001
- 项目类型：B 现有项目新增功能
- 次类型：C 成熟项目优化 / 重构
- 风险等级：R1

## 正式执行前说明

- 目标：
  - 基于 `output/agent-loop/` 当前运行态选择一个最小但有价值的增量。
  - 强化连续循环的运行态可观测性，让人工接管时不必猜“当前到底在跑哪一轮”。
  - 在本轮结束前完成代码、文档、验证和运行态交接文件更新。
- 非目标：
  - 不改业务 API、数据库结构、前端工作台。
  - 不引入外部调度、监控平台或新依赖。
  - 不尝试一次性补齐统一日志平台或统一特性开关机制。
- 约束：
  - 仅以当前仓库文件为事实源，不假设上一轮聊天内容。
  - 严格遵守 `HOOK.md` / `STANDARDS.md` 顺序，先测试计划再实现。
  - 当前目录不是 Git worktree，不能依赖 Git diff 审计。
- 风险：
  - 新增状态字段若不兼容旧 `state.json`，会让既有运行目录失效。
  - 如果单轮失败后没有正确清理进行中字段，可能误导人工接管。
- 验收标准：
  - `state.json` 能表达当前进行中轮次及其产物目录。
  - 旧状态文件会自动补齐新增字段，不破坏已有运行目录。
  - 单测、静态检查、dry-run 与编译校验通过。
- 当前项目类型：
  - 主类型：B 现有项目新增功能
  - 次类型：C 成熟项目工具化增强
- 当前风险等级：
  - R1：局部脚本、测试和文档改动，不涉及业务接口和数据库。
- 仓库现状：
  - 已存在：`README.md`、`ARCHITECTURE.md`、`IMPLEMENTATION_PLAN.md`、`RUNBOOK.md`、`.env.example`、`tests/`、`.github/workflows/`、`migrations/`、`output/agent-loop/`
  - 缺失：统一特性开关 / 灰度机制、显式统一应用日志机制、本地 Git worktree 元信息
  - 本轮必须先补齐的项：基于运行态缺口的具体方案、测试计划和任务日志
- 缺失机制清单：
  - `state.json` 缺少“进行中轮次”元数据
  - 人工接管时需要人工推断当前轮次与产物目录
- 方案对比：
  - 方案 A：只补文档，让接管者手动查看 `iterations/` 推测当前轮次。复杂度最低，但状态文件仍不自描述，恢复效率差。
  - 方案 B：在 `state.json` 增加进行中轮次字段，并在单轮结束后清理。复杂度低，侵入性小，兼容性和恢复性最好。
- 推荐方案：
  - 采用方案 B。
- 是否需要 ADR：
  - 否。本轮不引入新基础设施，不改核心业务调用链。
- 测试计划：
  - 先修改 `tests/test_continuous_task_loop.py`，覆盖默认状态、旧状态补齐和进行中轮次生命周期。
  - 再实现脚本与文档更新。
  - 完成后运行 `pytest`、`ruff`、dry-run、`compileall`。
- 实施步骤：
  - 为连续循环状态定义新增字段。
  - 先写/改测试锁定状态契约。
  - 修改 `scripts/continuous_task_loop.py` 的状态加载、单轮开始与收尾逻辑。
  - 更新 `docs/continuous-task-loop.md`。
  - 回填验证结果、风险、回滚和下一步建议。

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
  - 无额外仓库基础项；优先收敛连续循环运行态缺口

## 实施记录

- 方案摘要：
  - 为连续循环状态新增 `active_iteration`、`active_iteration_started_at`、`active_iteration_dir`。
  - 在读取旧 `state.json` 时自动回填默认值，保证兼容已有运行目录。
  - 在子会话启动前先写入进行中轮次元数据，在超时或完成后清理。
  - 同步更新连续循环文档和本轮任务日志。
- 关键决策：
  - 只增强已有 `state.json`，不新增并行状态文件，避免状态源分裂。
  - 使用“启动前落盘、结束后清理”的模式，保证人工接管时至少能看到当前轮次目录。
  - 保持当前外部命令和状态目录结构不变，降低回滚成本。
- 变更文件：
  - `scripts/continuous_task_loop.py`
  - `tests/test_continuous_task_loop.py`
  - `docs/continuous-task-loop.md`
  - `docs/agent-runs/2026-03-15-loop-iteration-001.md`

## 实施结果

- 已为 `scripts/continuous_task_loop.py` 增加进行中轮次状态字段，并在旧状态文件加载时自动补齐默认值。
- 已在单轮开始时落盘当前轮次编号、开始时间和产物目录，在超时与正常结束时清理这些字段。
- 已扩展 `tests/test_continuous_task_loop.py`，覆盖默认状态、旧状态兼容和显式开始/清理逻辑。
- 已更新 `docs/continuous-task-loop.md`，记录新增状态字段的用途。

## 验证结果

- `python3 -m pytest -q tests/test_continuous_task_loop.py`：通过，`13 passed`
- `python3 -m ruff check scripts/continuous_task_loop.py tests/test_continuous_task_loop.py`：通过
- `python3 scripts/continuous_task_loop.py --goal "连续推进当前仓库，默认不要停，直到完成队列或达到 10 小时上限" --state-dir /tmp/agent-loop-iteration-001-check --dry-run`：通过
- `PYTHONPYCACHEPREFIX=/tmp/rag-pyc python3 -m compileall scripts tests`：通过

## 风险清单

- 如果当前外层 `continuous_task_loop.py` 进程是在本轮修改前启动的，它不会热加载新逻辑；要让新增字段在真实长跑中生效，需要后续重启外层循环进程。
- 本轮只验证了 dry-run 和单测，未在真实多轮长时运行里观察 `active_iteration*` 字段的完整生命周期。

## 未覆盖项

- 未跑满 10 小时连续循环。
- 未验证旧父进程继续运行时的热更新行为；Python 脚本默认不会热替换自身代码。

## 上线检查项

- 若要让真实长跑进程使用新增字段，先保留现有 `output/agent-loop/` 目录，再重新启动 `python3 scripts/continuous_task_loop.py ...`。
- 重启后观察 `state.json` 是否在单轮执行期间写入 `active_iteration*` 字段。
- 若仍使用旧进程，继续把本轮改动视为“下次启动后生效”。

## 回滚步骤

1. 删除 `scripts/continuous_task_loop.py` 中新增的进行中轮次字段与兼容逻辑。
2. 回退 `tests/test_continuous_task_loop.py` 中对应断言。
3. 回退 `docs/continuous-task-loop.md` 与本任务日志中的新增说明。
4. 如已用新脚本生成过带 `active_iteration*` 字段的 `state.json`，可保留这些字段或删除后重新生成，均不影响旧逻辑运行。

## 后续建议

- 下一轮优先在一次真实非 dry-run 循环中观察 `state.json` 的进行中字段，形成实机证据。
- 若继续推进主线，可把运行态模板从通用待办改成更具体的 backlog，降低空转概率。
