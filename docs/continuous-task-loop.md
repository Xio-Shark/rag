# 持续任务循环

这份文档说明如何在本地用 `scripts/continuous_task_loop.py` 持续执行 Codex 任务，而不把连续性绑定在单个聊天上下文上。

核心思路：

- 外层脚本控制循环、时长、失败阈值和运行态文件。
- 每一轮都启动一个新的 `codex exec` 会话。
- 任务状态、队列、记忆和 handoff prompt 全部落盘。
- 即使单轮上下文过长、终端关闭或需要人工接管，也能从文件状态继续。

## 为什么默认每轮新会话

这条策略比“不断 resume 同一个超长对话”更稳：

- 不依赖单个会话一直保持可用
- 不让上下文无限膨胀
- 更容易人工审计每轮输入和输出
- 更适合跑数小时的顺序任务循环

如果你需要新对话继续，本工具默认已经这样做，不需要等上下文真的撑满。

## 运行态目录

默认状态目录：`output/agent-loop/`

关键文件：

- `GOAL.md`：总目标
- `TASK_QUEUE.md`：当前任务队列，使用 Markdown checkbox
- `NEXT_ACTION.md`：当前最高优先级动作，首行状态必须为 `Status: continue|completed|blocked`
- `LOOP_MEMORY.md`：跨会话最小记忆
- `HANDOFF_PROMPT.md`：给新会话或人工接管用的接续 prompt
- `state.json`：结构化状态、失败次数、截止时间、迭代历史，以及当前进行中轮次
- `autopilot.pid`：后台自动化任务的守护进程 PID
- `autopilot.log`：后台自动化任务的标准输出和错误输出
- `autopilot.json`：后台自动化任务最近一次启动命令与目标摘要
- `watchdog.log`：守护巡检唤醒出来的后台 loop 输出
- `iterations/<n>/prompt.md`：每轮实际发送给 Codex 的 prompt
- `iterations/<n>/events.jsonl`：Codex JSONL 事件与实时流式输出日志
- `iterations/<n>/diagnostics.json`：失败轮次的结构化诊断摘要，提炼错误项、传输层报错、`failure_category`、`transport_error_groups`、`recovery_hints` 和简短结论
- `iterations/<n>/last-message.md`：该轮最终消息
- `iterations/<n>/stderr.log`：命令侧错误输出

`state.json` 中与进行中轮次直接相关的字段：

- `active_iteration`：当前正在执行的轮次编号；空值表示当前没有活跃轮次
- `active_iteration_started_at`：该轮启动时间（UTC）
- `active_iteration_dir`：该轮产物目录，便于直接跳到 `iterations/<n>/`
- `active_iteration_last_progress_at`：该轮最近一次启动或产生日志输出的时间（UTC）；排查“是否仍在推进”时优先看它；若旧主循环进程尚未写入该字段，handoff / watch 会回退到活动轮次目录里 `prompt.md`、`events.jsonl`、`stderr.log` 的最新 mtime 推导最近进展时间
- `active_iteration_state`：读取侧推导出的活动轮次状态，取值为 `inactive` / `live` / `stale`；其中 `stale` 表示 `state.json` 仍保留了 `active_iteration`，但对应 loop / child pid 已不存活
- `loop_pid`：当前主循环进程 PID；守护巡检会用它判断“任务是否还在跑”
- `loop_started_at`：当前主循环进程启动时间
- `resume_count`：被守护层自动唤醒的累计次数
- `last_resume_at` / `last_resume_reason`：最近一次自动唤醒的时间和原因

## 启动命令

如果你要的是“后台自动跑约 10 小时，或直到验收完成”，优先使用自动化入口：

```bash
python3 scripts/project_autopilot.py start
```

常用配套命令：

```bash
python3 scripts/project_autopilot.py status
python3 scripts/project_autopilot.py stop
```

这个入口会后台启动 `continuous_task_loop.py --watch`，并复用同一个 `output/agent-loop/` 目录：

- 如果现有运行窗仍有效且未到终态，会继续当前 backlog
- 如果现有 `state.json` 已经终态、时间窗过期，或你提供了新的 `--goal`，会刷新为新的 10 小时运行窗
- 当 `NEXT_ACTION.md` 进入 `completed`，或命中 `deadline_reached` / `queue_exhausted` / `max_iterations_reached` 等终态后，后台守护会自行退出
- `python3 scripts/project_autopilot.py status --json` 会额外输出 `latest_failure_iteration`、`latest_failure_diagnostics_path`、`latest_failure_attempt`、`latest_failure_category`、`latest_failure_summary`、`latest_failure_transport_error_groups`、`latest_failure_recovery_hints`，方便在同一条状态结果里同时读取活动轮次和最近失败诊断

如果你需要更细粒度地控制主循环和守护模式，再直接使用下面的 `continuous_task_loop.py` 命令。

先做一次 dry-run：

```bash
python3 scripts/continuous_task_loop.py \
  --goal "连续推进当前仓库，默认不要停，直到完成队列或达到 10 小时上限" \
  --dry-run
```

确认生成的运行态文件没问题后，再正式启动：

```bash
python3 scripts/continuous_task_loop.py \
  --goal "连续推进当前仓库，默认不要停，直到完成队列或达到 10 小时上限" \
  --duration-hours 10 \
  --max-iterations 40 \
  --max-consecutive-failures 3 \
  --max-seconds-per-iteration 1800
```

如果想先做一次真实 non-dry-run 的有界 smoke run，可以单独使用新的临时 `state-dir`：

```bash
python3 scripts/continuous_task_loop.py \
  --goal "验证 continuous_task_loop 的真实单轮生命周期" \
  --state-dir /tmp/agent-loop-smoke \
  --max-iterations 1 \
  --max-seconds-per-iteration 300
```

命中 `--max-iterations`、`deadline`、`completed` 或 `queue_exhausted` 时，若当前轮子会话成功完成，脚本会把它视为预期停止并返回成功退出码；如果子会话本身报错，即使紧接着命中了这些上限，命令仍会返回非零，避免把失败误判为成功。

补充说明：

- 单轮子会话的有效超时时间会自动压到“当前 `--max-seconds-per-iteration` 与剩余运行窗”中的较小值，避免最后一轮越过 `deadline` 后继续长时间运行。
- 流式采集子会话输出时，即使输出是没有换行的长片段，也会持续按绝对时间检查 timeout，不会因为阻塞在逐行读取而错过停止时机。

如果希望脚本自己常驻守护，并每隔 30 分钟检查一次主循环是否还活着：

```bash
python3 scripts/continuous_task_loop.py \
  --goal "连续推进当前仓库，默认不要停，直到完成队列或达到 10 小时上限" \
  --watch \
  --check-interval-minutes 30
```

watch 模式默认每 60 分钟输出一次进度摘要；如果你想显式指定频率，可以这样执行：

```bash
python3 scripts/continuous_task_loop.py \
  --state-dir output/agent-loop \
  --watch \
  --progress-report-minutes 60
```

如果更适合交给 `cron` 或 `launchd`，则可以按 30 分钟或 1 小时调度单次巡检：

```bash
python3 scripts/continuous_task_loop.py \
  --state-dir output/agent-loop \
  --check-once
```

可选参数：

- `--state-dir`：自定义运行态目录
- `--model`：指定 Codex 模型
- `--sandbox`：传给 `codex exec` 的 sandbox 模式
- `--search`：为子会话开启网页搜索
- `--codex-bin`：自定义 Codex CLI 可执行文件名
- `--check-once`：执行一次巡检；任务未完成且当前没有 loop 进程时自动唤醒
- `--watch`：常驻守护模式，按固定间隔反复巡检
- `--check-interval-minutes`：守护巡检间隔，默认 30 分钟
- `--progress-report-minutes`：watch 模式下进度摘要输出间隔，默认 60 分钟

运行时行为：

- 子会话输出会实时打印到当前终端
- 同一份输出也会落到 `iterations/<n>/events.jsonl`
- 当子会话失败且没有明确最终消息时，脚本会把 `diagnostics.json` 中的摘要回退到 handoff，减少人工翻长日志成本
- `diagnostics.json` 中的 `transport_error_groups` 会把重复的 transport 报错按类型 / 组件 / URL 聚合，`recovery_hints` 会给出保守的下一步排查方向，避免被 warning 或重复日志干扰
- 如果最新失败命中的是旧版 `diagnostics.json`，`project_autopilot.py status --json` 会根据文件中残留的 `transport_errors` / `error_messages` / `warnings` 兜底推导 `latest_failure_category`、`latest_failure_transport_error_groups` 和 `latest_failure_recovery_hints`
- 当 `state.json` / `history` 暂时落后于磁盘中的迭代产物时，handoff 会优先引用更高编号失败轮次的 `diagnostics.json`；如果更新轮次没有失败诊断，则不会回退到更旧失败
- 如果守护层恢复后要重试一个尚未写回 `history` 的轮次，脚本会先清理该 `iterations/<n>/` 目录里的已知旧产物，再落盘新的 `prompt.md`、`events.jsonl`、`last-message.md` 和 `diagnostics.json`
- 当 `loop_pid` 仍存活且 `active_iteration` 指向进行中轮次时，handoff 会优先提示查看该轮的 `prompt.md` / `events.jsonl`，并补充 `attempt`、`child_pid`、`active_iteration_last_progress_at` 等运行态线索，避免把同目录里残留的旧 `diagnostics.json` 误判成当前失败
- 如果活动轮次编号仍留在 `state.json`，但对应 loop / child pid 已不存活，handoff 会明确提示“未收口的活动轮次标记”，提醒接管者不要再把该目录当 live child
- 如果 watch / check-once 发现进程已经不存在，但当前已经满足 `deadline_reached` / `completed` / `queue_exhausted` / `max_iterations_reached` 等终态条件，会直接把 `state.json` 收口到真实终态，而不是继续保留 stale `running`
- 手工 `Ctrl-C` 中断外层脚本时，会把 `state.json` 标记为 `interrupted`
- 守护模式唤醒出来的后台 loop 会把输出追加到 `watchdog.log`
- watch 模式还会按 `--progress-report-minutes` 输出当前队列进度、活跃轮次、`active_state`、最近进展时间和截止时间摘要
- 推荐接管顺序是先跑 `python3 scripts/project_autopilot.py status --json`：若 `active_iteration_state=live`，优先查看活动轮次；若为 `inactive` / `stale`，先看 `latest_failure_attempt`、`latest_failure_summary`、`latest_failure_transport_error_groups` 与 `latest_failure_recovery_hints`，再按 `latest_failure_diagnostics_path` 打开完整诊断

## 状态约定

`TASK_QUEUE.md` 建议保持为更具体的执行 backlog，例如：

```md
- [x] 已完成事项
- [ ] 阅读 AGENTS.md、HOOK.md、STANDARDS.md 与运行态文件，确认约束和当前主线
- [ ] 选择一个最小但有价值的增量
- [ ] 更新任务日志，写清方案对比、测试计划、风险和回滚
- [ ] 先写/更新匹配测试，再实现增量
- [ ] 运行验证并更新交接文件
```

`NEXT_ACTION.md` 必须包含状态行，例如：

```md
Status: continue
```

建议正文至少覆盖：

- 本轮首要动作
- 本轮已完成
- 下一轮首要动作
- 阻塞点（如有）

允许的状态：

- `continue`：继续下一轮
- `completed`：整体目标已完成，脚本结束
- `blocked`：出现真实阻塞，脚本结束并等待人工接管

`LOOP_MEMORY.md` 建议固定保留以下小节，方便跨会话快速恢复：

- 当前目标
- 当前主线 / 已完成事项
- 最近一次验证结果
- 风险 / 阻塞
- 下一步建议

## 停止条件

脚本命中以下任一条件时会停止：

- `NEXT_ACTION.md` 标记为 `completed`
- `NEXT_ACTION.md` 标记为 `blocked`
- 达到 `--duration-hours`
- 达到 `--max-iterations`
- 连续失败达到 `--max-consecutive-failures`
- `TASK_QUEUE.md` 中没有未完成项

其中 `completed`、`queue_exhausted`、`deadline_reached`、`max_iterations_reached` 是停止原因；只有当前轮成功完成时，它们才对应成功退出。`blocked`、`too_many_failures` 和子会话错误仍视为失败停止。

自动唤醒只针对以下情况：

- `status=interrupted`
- `status=too_many_failures`
- `status=iteration_timeout`
- `status=running` 但 `loop_pid` 指向的进程已经不存在

以下状态不会被守护层自动恢复：

- `completed`
- `blocked`
- `queue_exhausted`
- `deadline_reached`
- `max_iterations_reached`

## 新对话接续

每轮结束后脚本都会重写 `HANDOFF_PROMPT.md`。

用途有两种：

1. 脚本自动进入下一轮新 `codex exec` 会话时，继续依据这些文件状态推进。
2. 如果你想手工切到新对话，可以直接把 `HANDOFF_PROMPT.md` 内容贴给新的 Codex 会话。

## 人工接管建议

当脚本停止时，先看：

1. `python3 scripts/project_autopilot.py status --state-dir output/agent-loop --json`
2. `state.json`
3. 如果 `status --json` 显示 `active_iteration_state=live`，先看该轮的 `iterations/<n>/prompt.md` 和 `iterations/<n>/events.jsonl`
4. `status --json` 提供的 `latest_failure_diagnostics_path`（如果该轮失败；优先看 `latest_failure_category`、`latest_failure_summary` 和 `latest_failure_recovery_hints`）
5. `NEXT_ACTION.md`
6. `LOOP_MEMORY.md`
7. 最新一轮 `iterations/<n>/last-message.md`

如果需要继续：

- 修正任务队列或下一步动作
- 保留已有 `output/agent-loop/` 目录
- 重新执行 `python3 scripts/continuous_task_loop.py`
- 如果只想让守护层代为恢复，则执行 `--watch` 或定时调用 `--check-once`

如果不传 `--goal`，脚本会复用现有 `GOAL.md` 的正文。

## 限制

- 这不是外部调度平台，只是本地顺序循环 harness。
- 能否连续跑满 10 小时，仍取决于本机网络、认证、模型可用性和系统稳定性。
- 当前仓库不是 Git worktree，不能依赖 Git commit 作为自动回滚边界。
