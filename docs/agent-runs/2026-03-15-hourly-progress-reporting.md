# 2026-03-15 每小时进度播报

- 任务名称：每小时进度播报
- 项目类型：B 现有项目新增功能
- 次类型：C 成熟项目工具化增强
- 风险等级：R2

## 正式执行前说明

- 目标：
  - 为当前长时自动循环增加每小时一次的进度播报。
  - 让用户无需手工查 `state.json`，也能从运行输出中直接看到“现在进度如何”。
- 非目标：
  - 不改变业务逻辑、数据库、API、前端。
  - 不引入外部通知通道，如邮件、Webhook、IM 机器人。
- 约束：
  - 必须遵守 `HOOK.md` / `STANDARDS.md` 顺序。
  - 复用现有 `continuous_task_loop.py --watch` 和 `watchdog.log`。
  - 先补测试，再进入实现。
- 风险：
  - 如果进度摘要内容过长，可能稀释真正的错误日志。
  - 如果只靠巡检间隔拼接摘要，可能导致小时级输出出现轻微漂移。
- 验收标准：
  - `--watch` 模式下能按配置周期输出结构化进度摘要。
  - 默认支持每 60 分钟输出一次。
  - 文档和测试同步更新。
- 当前项目类型：
  - 主类型：B 现有项目新增功能
  - 次类型：C 成熟项目工具化增强
- 当前风险等级：
  - R2：涉及 watchdog 主路径和长时日志输出行为。
- 仓库现状：
  - 已存在：长时 loop、watchdog、`state.json`、`TASK_QUEUE.md`、`NEXT_ACTION.md`、`watchdog.log`
  - 缺失：周期性进度摘要能力
- 缺失机制清单：
  - 进度摘要构造函数
  - watch 模式的摘要输出调度
  - 面向用户的配置说明
- 方案对比：
  - 方案 A：新增外部脚本定时读取 `state.json` 并打印摘要。实现简单，但会引入第二个调度点，和现有 watchdog 分离。
  - 方案 B：直接在 `continuous_task_loop.py --watch` 中增加进度播报参数与摘要输出。复用最好，侵入性最小。
- 推荐方案：
  - 采用方案 B。
- 是否需要 ADR：
  - 否。
- 测试计划：
  - 先补单测与脚本级测试，锁定摘要内容和 watch 模式输出时机。
  - 再改 `scripts/continuous_task_loop.py`。
  - 完成后运行 `pytest`、`ruff`、`compileall`。
- 实施步骤：
  - 新增任务日志。
  - 先写测试。
  - 再实现脚本和文档更新。
  - 最后重启当前 watch 会话。

## 实施记录

- 方案摘要：
  - 在 `scripts/continuous_task_loop.py` 中新增 `--progress-report-minutes`，默认值为 `60`。
  - 新增 `build_watch_progress_report(...)`，统一构造 watch 模式的小时级进度摘要。
  - 在 `run_watch_mode(...)` 中按配置周期输出摘要，内容覆盖状态、队列完成度、活跃轮次、恢复信息和截止时间。
- 关键决策：
  - 进度播报直接挂在现有 watch 模式上，不再新增第二套定时脚本。
  - 默认每 60 分钟输出一次，避免刷屏；如需更频繁输出，用户可自行传 `--progress-report-minutes`。
  - 进度摘要写到 watch 进程标准输出；直接前台运行时会显示在当前会话里，若 watch 进程被其他入口重定向，则会跟随该入口的标准输出去向。
- 变更文件：
  - `scripts/continuous_task_loop.py`
  - `tests/test_continuous_task_loop.py`
  - `README.md`
  - `RUNBOOK.md`
  - `docs/continuous-task-loop.md`
  - `docs/agent-runs/2026-03-15-hourly-progress-reporting.md`

## 实施结果

- `continuous_task_loop.py --watch` 现在会默认每 60 分钟输出一次进度摘要。
- 已支持通过 `--progress-report-minutes <minutes>` 自定义摘要频率。
- 当前长时 watch 会话已按新参数重启，启动输出明确显示 `progress_report_minutes=60`。

## 风险清单

- 进度摘要是按 watch 进程本地计时输出，不是绝对整点报时，因此相对“启动时间”会有轻微漂移。
- 如果未来摘要字段继续扩张，可能稀释真实错误日志；当前已刻意控制为 4 行摘要。

## 未覆盖项

- 未增加外部通知通道；当前只在 watch 输出和 `watchdog.log` 中可见。
- 未增加整点对齐逻辑；当前按固定周期输出。

## 验证结果

- `python3 -m pytest -q tests/test_continuous_task_loop.py`
  - 通过，`28 passed`
- `python3 -m ruff check scripts/continuous_task_loop.py tests/test_continuous_task_loop.py README.md RUNBOOK.md docs/continuous-task-loop.md`
  - 通过，`All checks passed!`
- `PYTHONPYCACHEPREFIX=/tmp/rag-pyc python3 -m compileall scripts tests`
  - 通过
- 当前运行命令已重启为：
  - `python3 scripts/continuous_task_loop.py --goal "连续推进当前仓库，默认不要停，直到完成队列或达到 10 小时上限" --state-dir /Users/xioshark/Desktop/rag/output/agent-loop --duration-hours 10 --max-iterations 40 --max-consecutive-failures 3 --max-seconds-per-iteration 1800 --codex-bin codex --sandbox workspace-write --watch --check-interval-minutes 30 --progress-report-minutes 60`

## 上线检查项

- 确认当前 watch 会话仍在运行。
- 如需用 `/ps` 查看，确认当前是 Codex 托管的前台长会话，而不是脱离会话的后台 daemon。
- 如需调整频率，可在重启命令里显式传 `--progress-report-minutes`。

## 回滚步骤

1. 回退 `scripts/continuous_task_loop.py` 中的 `--progress-report-minutes` 与摘要输出逻辑。
2. 回退 `tests/test_continuous_task_loop.py` 对进度摘要的新增断言。
3. 回退 `README.md`、`RUNBOOK.md`、`docs/continuous-task-loop.md` 中的对应说明。
4. 重启 watch 会话，移除 `--progress-report-minutes` 参数。

## 后续建议

- 如果后续希望“整点播报”而不是“每 60 分钟滚动播报”，可再补一个对齐到整点的时间调度策略。
- 如果后续希望摘要可消费，可再把同样内容落成 `progress.json` 或 `progress.md`。
