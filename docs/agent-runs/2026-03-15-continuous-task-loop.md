# 2026-03-15 持续任务循环

- 任务名称：持续任务循环
- 项目类型：B 现有项目新增功能
- 次类型：C 成熟项目工具化增强
- 风险等级：R2

## 正式执行前说明

- 目标：
  - 为当前仓库增加一个本地连续任务循环 harness。
  - 支持长时间持续执行任务，并在每轮结束后落盘状态。
  - 支持上下文过长时自动切换到新会话继续，而不是依赖单个对话无限增长。
- 非目标：
  - 不改业务 API、数据库 schema 或前端主流程。
  - 不接入外部调度平台、队列或数据库。
  - 不承诺在 Chat 界面里直接自动打开新窗口；改为生成可恢复的下一轮输入并由脚本发起新 `codex exec` 会话。
- 约束：
  - 继续保持 Python 3.9 兼容。
  - 优先使用标准库，不引入新依赖。
  - 运行状态与日志必须可落盘，可人工接管。
- 风险：
  - 自动循环工具如果提示词或停止条件设计不当，会出现空转、重复重试或误修改。
  - `codex exec` 属于真实代理执行，成本和执行范围必须有硬性边界。
  - 仓库当前不是 Git worktree，无法依赖 Git 提交边界做保护。
- 验收标准：
  - 提供可执行脚本或命令入口。
  - 支持状态文件、任务队列、下一轮接续 prompt/brief 生成。
  - 支持“每轮新会话”或达到阈值后轮换到新会话。
  - 具备 dry-run 和基础测试。
- 当前项目类型：B 现有项目新增功能
- 当前风险等级：R2
- 仓库现状：
  - 已存在：`README.md`、`ARCHITECTURE.md`、`IMPLEMENTATION_PLAN.md`、`RUNBOOK.md`、测试框架、CI、`.env.example`、迁移机制、任务日志。
  - 缺失：面向 Codex 的长时循环 harness、落盘状态模板、跨会话交接模板。
  - 本轮必须先补齐的项：测试计划、状态文件约定、停止条件和回滚说明。
- 缺失机制清单：
  - 长时循环控制
  - 跨会话 handoff
  - 空转 / 卡死 / 连续失败的停止规则
  - 面向该工具的运行文档
- 方案对比：
  - 方案 A：纯 shell `while` 循环直接反复调用 `codex exec`。复杂度低，成本低，但状态管理弱，恢复能力差，难做阈值控制和结构化日志。
  - 方案 B：Python harness，统一管理配置、状态、队列、轮换策略和 handoff 文件。复杂度中等，维护成本更低，恢复和测试更好。
- 推荐方案：
  - 采用方案 B。
  - 脚本按顺序循环执行，每轮都生成新的 `codex exec` 会话，天然规避单会话上下文持续膨胀。
  - 通过落盘状态和 handoff prompt 支持脚本自动继续或人工切到新对话继续。
- 是否需要 ADR：否。
- 测试计划：
  - 先写脚本级单测，覆盖配置加载、状态初始化、prompt 生成、停止条件、命令拼装和 dry-run。
  - 再实现脚本与模板文件。
  - 之后补 README / RUNBOOK 使用说明，并跑 `pytest`、`ruff`、`compileall`。
- 实施步骤：
  - 定义目录与状态文件约定
  - 先写测试
  - 实现循环脚本
  - 增加文档和示例模板
  - 跑验证

## 实施记录

- 方案摘要：
  - 用顺序循环而不是无限上下文。
  - 每轮由外层脚本调用一个新的 `codex exec` 会话，并把状态、任务队列、上一轮结果和下一步要求写入文件。
  - 当达到轮换阈值或单轮结束时，直接用新会话继续，避免对单一上下文容量做高风险假设。
- 关键决策：
  - 不依赖 `resume` 维持一个越来越长的上下文，而是默认“新会话 + 文件状态”。
  - 保留 dry-run，避免首次配置时直接启动长跑代理。
  - 运行态文件放到 `output/agent-loop/`，文档模板放在仓库可跟踪位置。
- 风险与未覆盖项：
  - 真实 10 小时连续运行需要用户本机网络、认证和模型可用性稳定。
  - 本轮不会真实跑满 10 小时，只验证 harness 本身。
- 回滚方式：
  - 删除新增脚本、测试、文档和 `.gitignore` 条目即可。

## 实施结果

- 已新增 `scripts/continuous_task_loop.py`
  - 支持 `--goal`、`--duration-hours`、`--max-iterations`、`--max-consecutive-failures`、`--max-seconds-per-iteration`
  - 支持 `--dry-run`
  - 默认把运行态文件落到 `output/agent-loop/`
  - 默认每轮启动新的 `codex exec` 会话，并生成 `HANDOFF_PROMPT.md`
- 已新增 `docs/continuous-task-loop.md`
  - 说明运行目录、状态约定、停止条件、接续方式和人工接管路径
- 已更新 `README.md`
  - 增加文档入口和脚本入口
- 已更新 `RUNBOOK.md`
  - 增加长时任务循环启动方式和运行要点
- 已更新 `.gitignore`
  - 忽略 `output/agent-loop/`
- 已新增 `tests/test_continuous_task_loop.py`
  - 覆盖运行态初始化、状态文件、task queue 统计、next action 状态、停止条件、handoff prompt、命令拼装、dry-run、文档连通性

## 变更文件

- `scripts/continuous_task_loop.py`
- `tests/test_continuous_task_loop.py`
- `docs/continuous-task-loop.md`
- `README.md`
- `RUNBOOK.md`
- `.gitignore`
- `docs/agent-runs/2026-03-15-continuous-task-loop.md`

## 验证结果

- `python3 -m pytest -q tests/test_continuous_task_loop.py`：通过，`11 passed`
- `python3 -m ruff check scripts/continuous_task_loop.py tests/test_continuous_task_loop.py`：通过
- `python3 scripts/continuous_task_loop.py --goal "连续推进当前仓库，默认不要停，直到完成队列或达到 10 小时上限" --dry-run`：通过，已生成 `output/agent-loop/` 运行态文件
- `python3 -m compileall scripts tests`：通过
- `python3 -m pytest -q`：通过，`60 passed, 2 warnings`

## 交付结论

- 风险清单：
  - 真实长时连续运行仍受网络、认证、模型可用性和机器稳定性影响
  - 当前没有引入外部调度与监控平台，属于本地 harness
  - 仓库不是 Git worktree，自动回滚边界只能靠状态文件和人工判断
- 未覆盖项：
  - 未真实跑满 10 小时
  - 未验证 `codex exec` 在极端网络抖动下的恢复表现
- 上线检查项：
  - 先执行一次 `--dry-run`
  - 确认 `output/agent-loop/GOAL.md`、`TASK_QUEUE.md`、`NEXT_ACTION.md`、`LOOP_MEMORY.md` 内容符合预期
  - 再启动正式循环
- 回滚步骤：
  - 停止脚本
  - 删除 `output/agent-loop/`
  - 回退本次新增的脚本、测试和文档文件
- 后续建议：
  - 如需更强治理，可继续补 session metrics、失败重试退避和人工审批点
  - 如需团队协作，可再加一份固定的任务队列模板和值班 handoff 模板

## 运行记录

- 2026-03-15 01:42 CST 已启动正式循环：
  - 命令：`python3 scripts/continuous_task_loop.py --duration-hours 10 --max-iterations 40 --max-consecutive-failures 3 --max-seconds-per-iteration 1800`
  - 外层进程：`continuous_task_loop.py`
  - 内层进程：`codex exec --json ...`
  - 当前运行态目录：`output/agent-loop/`
  - 当前首轮目录：`output/agent-loop/iterations/001/`
- 2026-03-15 01:46 CST 为满足“可见实时输出”新增流式转发：
  - `scripts/continuous_task_loop.py` 现会把内层 `codex exec` 输出实时打印到终端，并同步写入 `output/agent-loop/iterations/<n>/events.jsonl`
  - 外层脚本收到 `Ctrl-C` 时会把 `state.json` 标记为 `interrupted`
  - 变更后已重新启动正式循环并验证实时输出可见
