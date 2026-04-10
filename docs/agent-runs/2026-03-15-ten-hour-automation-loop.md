# 2026-03-15 十小时自动化持续运行任务

- 任务名称：十小时自动化持续运行任务
- 项目类型：B 现有项目新增功能
- 次类型：C 成熟项目工具化增强
- 风险等级：R2

## 正式执行前说明

- 目标：
  - 设计并实现一个仓库内置的自动化任务，让当前项目可持续运行约 10 小时。
  - 当 `NEXT_ACTION.md` 明确进入 `completed` 等终态时提前停止，而不是无意义地跑满时间窗。
  - 提供用户可直接操作的入口，而不是让用户手工拼接 loop / watchdog 命令。
- 非目标：
  - 不改业务 API、数据库、前端主链路。
  - 不引入外部调度平台、消息队列、系统级守护服务依赖。
  - 不处理跨机器、跨用户并发争抢同一 `state-dir` 的场景。
- 约束：
  - 必须遵守 `HOOK.md` / `STANDARDS.md` 顺序，先任务日志、方案对比、测试计划，再实现。
  - 优先复用现有 `scripts/continuous_task_loop.py`、`state.json`、`TASK_QUEUE.md`、`NEXT_ACTION.md` 约定。
  - 当前目录不是 Git worktree，不能依赖 Git diff 或 commit 作为自动回滚边界。
- 风险：
  - 如果入口层不负责 stale PID / 终态窗口刷新，用户再次启动时可能因为旧 `state.json` 直接终止。
  - 如果 stop 行为只停守护不清理 loop，容易留下脏进程和错误状态。
  - 如果只补脚本不补文档，用户仍然需要理解底层 loop/watchdog 细节才能使用。
- 验收标准：
  - 新增一个单命令后台启动入口，默认目标就是“持续约 10 小时或直到验收完成”。
  - 新增状态查看和停止能力。
  - 后台入口复用现有 `continuous_task_loop.py --watch`，而不是再造第二套 loop。
  - 当旧运行窗终态、过期或切换新目标时，能刷新新的 10 小时运行窗。
  - 补齐测试、README、RUNBOOK、连续循环文档和任务日志。
- 当前项目类型：
  - 主类型：B 现有项目新增功能
  - 次类型：C 成熟项目工具化增强
- 当前风险等级：
  - R2：涉及自动化主路径、后台守护生命周期和运行态状态语义，但不涉及数据库结构、公共接口或部署配置。
- 仓库现状：
  - 已存在：`README.md`、`ARCHITECTURE.md`、`IMPLEMENTATION_PLAN.md`、`RUNBOOK.md`、`.env.example`、`tests/`、`.github/workflows/`、`migrations/`、`scripts/continuous_task_loop.py`
  - 已存在的自动化基础：长时 loop、watchdog、handoff prompt、`state.json`
  - 缺失：面向最终用户的一键后台启动入口、统一的 `start/status/stop` 生命周期、旧运行窗刷新语义
- 缺失机制清单：
  - 单命令后台启动任务入口
  - 后台守护 PID / 日志元信息
  - 重新起跑时的运行窗刷新逻辑
  - 面向用户的 stop / status 操作
- 方案对比：
  - 方案 A：继续把能力堆进 `scripts/continuous_task_loop.py`，直接增加 daemon/start/stop/status 子能力。复杂度中等，侵入性较高，单文件继续膨胀，兼容性尚可，回滚难度中等。
  - 方案 B：新增 `scripts/project_autopilot.py` 作为用户态入口，后台启动现有 `continuous_task_loop.py --watch`，并负责 `start/status/stop` 与运行窗刷新。复杂度低到中等，复用率高，侵入性最低，兼容性最好，维护成本更可控，回滚也更直接。
- 推荐方案：
  - 采用方案 B。
  - 让 `continuous_task_loop.py` 继续专注 loop/handoff/watchdog 协议，把用户操作面和后台守护生命周期放到单独入口脚本中。
- 是否需要 ADR：
  - 否。本轮不引入基础设施依赖，不改核心业务调用链。
- 测试计划：
  - 先写测试锁定 `project_autopilot` 的命令拼装、运行窗刷新语义、start/status/stop 行为。
  - 再实现后台入口脚本。
  - 完成后运行：
    - `python3 -m pytest -q tests/test_project_autopilot.py`
    - `python3 -m pytest -q tests/test_continuous_task_loop.py`
    - `python3 -m ruff check scripts/project_autopilot.py scripts/continuous_task_loop.py tests/test_project_autopilot.py tests/test_continuous_task_loop.py`
    - `PYTHONPYCACHEPREFIX=/tmp/rag-pyc python3 -m compileall scripts tests`
- 实施步骤：
  - 先新增 `tests/test_project_autopilot.py`
  - 实现 `scripts/project_autopilot.py`
  - 更新 `README.md`、`RUNBOOK.md`、`docs/continuous-task-loop.md`
  - 跑验证并回填任务日志

## HOOK 初始化记录

- 项目分类：
  - 主类型：B 现有项目新增功能
  - 次类型：C 成熟项目工具化增强
- 风险分级：
  - R2：修改自动化主路径和后台守护行为。
- 仓库探测：
  - 已存在项：
    - README：`README.md`
    - 架构文档：`ARCHITECTURE.md`
    - 实施计划：`IMPLEMENTATION_PLAN.md`
    - 测试框架：`pytest`、`playwright`、`ruff`
    - CI：`.github/workflows/schema-migration-guard.yml`、`.github/workflows/visual-baseline-sync.yml`、`.github/workflows/visual-regression-e2e.yml`
    - 环境变量模板：`.env.example`
    - 日志机制：`output/agent-loop/iterations/<n>/events.jsonl`、`last-message.md`、`stderr.log`
    - 迁移机制：`migrations/`、`alembic.ini`
    - 回滚方式：`RUNBOOK.md`
  - 缺失项：
    - 显式特性开关 / 灰度机制
    - 统一应用级日志机制
    - Git worktree 元信息
  - 本轮必须先补齐的项：
    - 任务日志
    - 自动化入口与运行窗刷新语义

## 实施记录

- 方案摘要：
  - 新增 `scripts/project_autopilot.py`，提供 `start/status/stop` 三个入口。
  - `start` 会后台启动 `continuous_task_loop.py --watch`，默认目标为“连续推进当前仓库，默认不要停，直到完成队列、达到 10 小时上限或明确验收完成”。
  - 若旧 `state.json` 已终态、时间窗过期或用户提供了新的 `--goal`，入口会刷新新的 10 小时运行窗，而不是沿用旧终态直接退出。
  - `stop` 会同时终止后台守护和当前 loop，并把 `state.json` 标记为 `interrupted`，避免留下脏 PID 和 stale active iteration。
- 关键决策：
  - 复用现有 `continuous_task_loop.py --watch`，不再造第二套 loop。
  - 后台守护的用户态 PID / 日志 / 元信息分别落到 `autopilot.pid`、`autopilot.log`、`autopilot.json`。
  - 运行窗刷新时保留 backlog 文件，但重置运行计数、失败计数、活跃轮次和历史计数窗口。
- 变更文件：
  - `scripts/project_autopilot.py`
  - `tests/test_project_autopilot.py`
  - `README.md`
  - `RUNBOOK.md`
  - `docs/continuous-task-loop.md`
  - `docs/agent-runs/2026-03-15-ten-hour-automation-loop.md`

## 实施结果

- 已新增用户态自动化入口脚本：
  - `python3 scripts/project_autopilot.py start`
  - `python3 scripts/project_autopilot.py status`
  - `python3 scripts/project_autopilot.py stop`
- `start` 会后台启动守护模式，默认运行目标就是“约 10 小时或直到验收完成”。
- `status` 会展示后台自动化进程、当前 loop、队列和最近恢复信息。
- `stop` 会终止自动化守护与当前 loop，并把状态落盘为 `interrupted`。
- 文档已同步更新，不再要求用户先理解底层 `--watch` / `--check-once` 才能使用。

## 风险清单

- 自动化入口仍基于单机 PID 和本地 `state.json` 协议，不适合作为跨机器调度器。
- `stop` 依赖进程组信号终止；极端情况下若本地环境对信号处理异常，可能需要人工补清理。
- 运行窗刷新会重置本轮计数窗口；如需长期累积指标，后续可再单独补 run archive。

## 未覆盖项

- 尚未实现系统级 `launchd` / `cron` 安装器；当前只提供仓库内后台入口。
- 未提供 UI 界面的自动化任务面板；当前管理方式仍是 CLI。
- 未做多实例争抢同一 `state-dir` 的锁机制。

## 验证结果

- `python3 -m pytest -q tests/test_project_autopilot.py`
  - 通过，`5 passed`
- `python3 -m pytest -q tests/test_continuous_task_loop.py`
  - 通过，`20 passed`
- `python3 -m ruff check scripts/project_autopilot.py scripts/continuous_task_loop.py tests/test_project_autopilot.py tests/test_continuous_task_loop.py`
  - 通过，`All checks passed!`
- `PYTHONPYCACHEPREFIX=/tmp/rag-pyc python3 -m compileall scripts tests`
  - 通过
- `python3 scripts/project_autopilot.py status --state-dir /tmp/nonexistent-agent-loop --json`
  - 通过，空状态目录下也能返回稳定 JSON

## 上线检查项

- 启动前确认本机 `python3` 与 `codex` 可执行路径正确。
- 若使用默认 `output/agent-loop/`，确认该目录可写。
- 如需自定义模型、sandbox 或 goal，在 `start` 命令中显式传参。
- 首次长跑前可先执行一次 `status` 确认状态目录为空或符合预期。

## 回滚步骤

1. 删除或回退 `scripts/project_autopilot.py`
2. 删除或回退 `tests/test_project_autopilot.py`
3. 回退 `README.md`、`RUNBOOK.md`、`docs/continuous-task-loop.md` 中关于自动化入口的说明
4. 如当前运行目录中残留 `autopilot.pid` 或 `autopilot.json`，在确认无相关进程后删除
5. 保留原有 `scripts/continuous_task_loop.py` 工作流不受影响

## 后续建议

- 如果后续希望系统级开机自启，可基于 `project_autopilot.py start` 再补 `launchd` 模板生成器。
- 如果后续需要防止多实例竞争，可在自动化入口层补文件锁或 PID 签名校验。
- 若需要长期审计每次 10 小时运行窗，可把刷新前的 `state.json` 自动归档到 `output/agent-loop/runs/`。
