# RUNBOOK.md

## 1. 适用范围

本运行手册用于当前 `RAG QA Bench` 仓库的本地演示、发布前检查、故障排查和回滚。

它描述的是当前仓库已经存在的运行方式，不假设额外基础设施。

## 2. 运行模式

### 模式 A：默认本地模式

- 数据库：SQLite
- 配置来源：不创建 `.env` 时使用代码默认值
- 适用场景：最快启动、本地开发、测试

### 模式 B：Docker + `.env` 模式

- 数据库：PostgreSQL + `pgvector`
- 配置来源：复制 `.env.example` 到 `.env`
- 适用场景：更接近真实数据库行为的演示

注意：

- `docker-compose.yml` 当前只提供 PostgreSQL
- 应用本身默认数据库仍然是 `sqlite:///./rag_qa_bench.db`
- PostgreSQL 模式下应用启动时会自动尝试创建 `vector` extension
- SQLite 模式下嵌入向量会以 JSON 存储；PostgreSQL 且 `pgvector` 依赖可用时会切到 `pgvector`
- 可通过 `FEATURE_EVALS_ENABLED` 和 `FEATURE_REPLAY_EXPERIMENTS_ENABLED` 控制实验中心相关能力；当前实际状态会反映在 `/v1/health` 的 `feature_flags`

## 3. 启动步骤

### 3.1 SQLite 本地模式

```bash
python3 -m venv .venv
. .venv/bin/activate
pip install -e ".[dev]"
alembic upgrade head
python3 -m app.cli.import_docs --source-dir data/docs
uvicorn app.main:app --reload
```

### 3.2 PostgreSQL 模式

```bash
cp .env.example .env
docker compose up -d
python3 -m venv .venv
. .venv/bin/activate
pip install -e ".[dev]"
alembic upgrade head
python3 -m app.cli.import_docs --source-dir data/docs
uvicorn app.main:app --reload
```

补充说明：

- 若宿主机已经有 PostgreSQL 监听 `127.0.0.1:5432`，先不要默认信任 `docker compose.yml` 的 `5432:5432` 映射。
- 建议先执行 `lsof -nP -iTCP:5432 -sTCP:LISTEN` 确认占用；若已被本地服务占用，要么停掉本地服务，要么改用独立宿主端口（例如 `55432:5432`），并把 `DATABASE_URL` 对应改成新的端口。
- 发布检查、CLI 和 `uvicorn` 最好使用同一 `.venv` 解释器；如果通过 `scripts/release_gate.py --execute` 触发子命令，记得把 `.venv/bin` 放到 `PATH` 前面。
- `APP_LOG_LEVEL` 默认是 `INFO`，可在 `.env` 中调整。
- 所有 HTTP 响应都会返回 `X-Request-ID`；如果调用方已传该 header，服务会沿用原值。
- 当前应用日志主要输出到服务进程的 stdout/stderr，请在启动 `uvicorn` 的同一终端查看。

## 4. 基础健康检查

服务启动后，至少执行以下检查：

```bash
curl -s http://127.0.0.1:8000/v1/health
python3 -m app.cli.search --query "系统支持什么"
python3 -m app.cli.eval run --dataset baseline_v1 --snapshot default
```

预期结果：

- `/v1/health` 返回 `database_ok=true`
- `/v1/health` 中 `database_backend` 与当前模式一致，且 `embedding_storage` 与预期兼容策略一致
- `/v1/health` 中 `feature_flags` 与当前 `.env` 配置一致
- HTTP 响应头里能看到 `X-Request-ID`
- 搜索命令能返回候选证据
- 评测命令能输出 `eval_run_id` 和报告路径

如需直接查看响应头，可改用：

```bash
curl -i http://127.0.0.1:8000/v1/health
```

当前最小日志字段约定：

- 请求日志：`event`、`request_id`、`method`、`path`、`status_code`、`duration_ms`
- completion log：
  - `documents.import.completed`
  - `qa.ask.completed`
  - `eval.run.completed`
  - `eval.replay.completed`

排障建议：

- 先从客户端或 `curl -i` 拿到 `X-Request-ID`
- 再回到服务进程日志中搜索对应 `request_id`
- 如果是写操作，再继续看对应 completion log 里的 `audit_id`、`eval_run_id` 或 `experiment_id`

## 4.1 长时任务循环

如果目标是让 Codex 在本地持续推进任务数小时，不要把连续性绑定在单个聊天上下文上。

如果你需要“后台自动运行约 10 小时，或者直到验收完成”，优先使用仓库内置的自动化任务入口：

```bash
python3 scripts/project_autopilot.py start
```

配套命令：

```bash
python3 scripts/project_autopilot.py status
python3 scripts/project_autopilot.py stop
```

运行要点：

- `start` 会后台启动 `continuous_task_loop.py --watch`，默认使用 `output/agent-loop/`
- 如果已有运行窗已经终态、达到截止时间，或你给了新的 `--goal`，它会刷新新的 10 小时时间窗
- `status` 会同时展示自动化守护进程、当前 loop、队列、最近一次恢复信息，以及最新失败诊断聚合字段
- `stop` 会停止后台守护和当前 loop，并把 `state.json` 标记为 `interrupted`，便于人工接管后再重新启动

如果你希望直接手工控制主循环本身，再使用下面的原始 loop 命令。

当前推荐方式：

```bash
python3 scripts/continuous_task_loop.py \
  --goal "连续推进当前仓库，默认不要停，直到完成队列或达到 10 小时上限" \
  --duration-hours 10 \
  --max-iterations 40 \
  --max-consecutive-failures 3 \
  --max-seconds-per-iteration 1800
```

运行要点：

- 运行态目录默认在 `output/agent-loop/`
- 每轮都会启动一个新的 `codex exec` 会话，避免单一上下文无限膨胀
- `HANDOFF_PROMPT.md` 可用于脚本自动续跑或人工切到新对话继续
- 如果某一轮失败，可优先查看对应 `iterations/<n>/diagnostics.json`，里面会提炼传输层报错、失败分类和简短摘要
- 如果 `state.json` 中存在 `active_iteration_last_progress_at`，它表示当前活动轮次最近一次启动或产生日志的时间，可用来判断“仍在推进”还是“疑似卡住”
- 如果旧主循环进程尚未写入 `active_iteration_last_progress_at`，handoff / watch 会回退到活动轮次目录里 `prompt.md`、`events.jsonl`、`stderr.log` 的最新 mtime 推导最近进展时间
- watch 进度摘要会额外输出 `active_state=inactive|live|stale`；`stale` 表示状态文件还留着 `active_iteration`，但 loop / child pid 已不存活
- 如果 `state.json` 暂时落后于 `iterations/` 中实际已落盘的失败轮次，handoff 会优先引用更高编号的 `diagnostics.json`；若更新轮次没有失败诊断，则不会误指向更旧失败
- 如果 watchdog 恢复的是一个尚未写回 `history` 的轮次，脚本会先清理该 `iterations/<n>/` 目录里的已知旧产物，再开始新的重试，避免残留 `diagnostics.json` / `events.jsonl` 混淆判断
- 如果 `loop_pid` 仍存活且 `active_iteration` 指向进行中轮次，先看该轮的 `prompt.md` 和 `events.jsonl`，再结合 `active_iteration_last_progress_at` 判断最近是否仍有输出；handoff 不会把同目录里的陈旧失败诊断误当成“最新失败”
- `python3 scripts/project_autopilot.py status --json` 现在也会输出 `active_iteration_state`、推导后的 `active_iteration_last_progress_at`，以及 `latest_failure_attempt`、`latest_failure_category`、`latest_failure_summary`、`latest_failure_transport_error_groups`、`latest_failure_recovery_hints`
- 如果最新失败对应的是旧版 `diagnostics.json`，`status --json` 会基于旧文件里的 `transport_errors` / `error_messages` / `warnings` 兜底推导失败分类、transport 聚合和排障提示
- 推荐先跑一次 `status --json`：如果 `active_iteration_state=live`，优先看当前活动轮次；如果是 `inactive` 或 `stale`，优先读 `latest_failure_summary` / `latest_failure_recovery_hints`，必要时再打开 `latest_failure_diagnostics_path`
- `--watch` 模式默认每 60 分钟输出一次进度摘要，帮助直接判断当前运行进度
- 首次使用建议先执行 `--dry-run`

如果要在不污染主运行目录的前提下验证真实 non-dry-run 路径，可先执行一次有界短跑：

```bash
python3 scripts/continuous_task_loop.py \
  --goal "验证 continuous_task_loop 的真实单轮生命周期" \
  --state-dir /tmp/agent-loop-smoke \
  --max-iterations 1 \
  --max-seconds-per-iteration 300
```

命中 `--max-iterations`、`deadline`、`completed` 或 `queue_exhausted` 时，如果当前轮子会话成功完成，则属于预期停止并成功退出；如果子会话本身报错，即使随即命中了这些上限，命令仍视为失败退出。

补充说明：

- 单轮子会话的实际超时时间会取 `min(--max-seconds-per-iteration, 距离 deadline 的剩余秒数)`，避免最后一轮跨过运行窗后继续长时间占住会话。
- 如果子会话只输出了没有换行的长片段，流式读取也会继续按绝对时间检查超时，不会因为 `readline()` 阻塞而拖过上限。

### 4.2 守护巡检与自动唤醒

如果主循环可能因为额度、网络、终端关闭或人工中断而停止，推荐再加一层守护巡检。

方式 A：常驻守护

```bash
python3 scripts/continuous_task_loop.py \
  --state-dir output/agent-loop \
  --watch \
  --check-interval-minutes 30
```

如果你更希望一小时检查一次，只需要把间隔改为 `60`。
如果你想调整进度摘要频率，可追加 `--progress-report-minutes 60` 或其他分钟值。

方式 B：交给系统定时器做单次巡检

```bash
python3 scripts/continuous_task_loop.py \
  --state-dir output/agent-loop \
  --check-once
```

推荐行为：

- `--watch` 适合你能接受前台或独立终端里常驻一个守护进程的场景。
- `--check-once` 更适合 `cron` 或 `launchd`，即使守护进程本身退出，也会在下一次调度时重新检查并恢复。
- 巡检时如果发现 `state.json` 仍未到终态、`NEXT_ACTION.md` 不是 `completed|blocked`，且 `loop_pid` 指向的进程已经不存在，就会自动拉起新的 loop 继续原目录下的未完成任务。
- 如果巡检时发现进程已经不存在，且当前其实已经命中 `deadline_reached` / `completed` / `queue_exhausted` / `max_iterations_reached`，守护层会先把 `state.json` 收口到对应终态，不会继续保留 stale `running`。
- 被守护层拉起的 loop 输出会追加到 `output/agent-loop/watchdog.log`。
- watch 进程还会按 `--progress-report-minutes` 输出当前进度摘要；默认每 60 分钟一次。
- 如果 handoff 提示“未收口的活动轮次标记”，说明状态文件仍残留该轮次编号，但 pid liveness 已不支持“仍在运行”的判断；这时优先看失败诊断或等待恢复逻辑。

`cron` 示例：每 30 分钟巡检一次

```cron
*/30 * * * * cd /Users/xioshark/Desktop/rag && /usr/bin/python3 scripts/continuous_task_loop.py --state-dir output/agent-loop --check-once >> output/agent-loop/watchdog.log 2>&1
```

`cron` 示例：每小时巡检一次

```cron
0 * * * * cd /Users/xioshark/Desktop/rag && /usr/bin/python3 scripts/continuous_task_loop.py --state-dir output/agent-loop --check-once >> output/agent-loop/watchdog.log 2>&1
```

注意：

- 守护层不会恢复 `completed`、`blocked`、`queue_exhausted`、`deadline_reached`、`max_iterations_reached` 这些终态。
- 如果你手工编辑了 `TASK_QUEUE.md`、`NEXT_ACTION.md` 或 `LOOP_MEMORY.md`，保留原目录即可，下一次巡检会继续基于这些文件恢复。

## 5. Release Gate

当前仓库的最小 release gate 入口是：

```bash
python3 scripts/release_gate.py
```

默认只做 dry-run，输出发布前、发布中、发布后的阶段和命令，不实际执行。

### 5.1 发布前

发布前 gate 建议直接执行：

```bash
python3 scripts/release_gate.py --phase pre-release --execute
```

它会收口以下检查：

- `alembic upgrade head`
- `python3 -m pytest -q tests/test_database_migrations.py`
- `python3 -m ruff check app tests scripts`
- `python3 -m pytest -q`
- `python3 -m pytest -q -m e2e`
- `python3 -m pytest -q tests/test_e2e_visual_regression.py`
- `python3 scripts/render_visual_regression_baselines.py --check`
- `python3 -m compileall app tests scripts`

对应 CI 现状：

- `.github/workflows/mainline-quality-gate.yml` 会持续执行 `python -m ruff check app tests scripts`、`python -m pytest -q` 和 `python -m compileall app tests scripts`
- `.github/workflows/schema-migration-guard.yml` 负责独立的迁移漂移门禁
- `.github/workflows/visual-baseline-sync.yml` 与 `.github/workflows/visual-regression-e2e.yml` 继续负责视觉基线同步、视觉诊断和 PR comment

其中 `tests/test_database_migrations.py` 会同时验证：

- `upgrade head` 能创建当前 schema
- `downgrade base` 能回滚应用表
- `alembic check` 不会发现 metadata 与迁移文件之间的待生成差异

如果本轮涉及视觉基线变更，再额外执行：

```bash
python3 -m pytest -q tests/test_visual_baseline_manifest.py
```

如果需要刷新基线：

```bash
UPDATE_VISUAL_BASELINES=1 python3 -m pytest -q tests/test_e2e_visual_regression.py
python3 scripts/render_visual_regression_baselines.py --write
```

### 5.2 发布中

发布中阶段当前仍以手工 cutover 为主，建议先做 dry-run 看清步骤：

```bash
python3 scripts/release_gate.py --phase release
```

如果目标环境已经准备好，并且你就是在目标环境执行迁移，可再运行：

```bash
python3 scripts/release_gate.py --phase release --execute
```

注意：

- 这一步仍包含手工项，脚本不会替你启动长期运行的服务进程。
- 执行前先保留上一稳定代码、配置与数据库备份。
- SQLite 至少备份 `rag_qa_bench.db`；PostgreSQL 至少保留上一稳定 dump。
- PostgreSQL + `pgvector` 模式需先准备 `.env` 并确保 `docker compose up -d` 已完成。
- 手工启动服务后，再进入“发布后” smoke check。

### 5.3 发布后

服务切换完成后，执行：

```bash
python3 scripts/release_gate.py --phase post-release --base-url http://127.0.0.1:8000 --execute
```

它会执行：

- `/v1/health` 健康检查，并输出 `database_backend`、`embedding_storage` 和 `feature_flags`
- `python3 -m app.cli.search --query "系统支持什么"`
- `python3 -m app.cli.eval run --dataset baseline_v1 --snapshot default`

预期结果：

- `/v1/health` 返回 `database_ok=true`
- `database_backend`、`embedding_storage` 与目标环境一致
- `feature_flags` 与本次发布计划一致
- 搜索命令能返回候选证据
- 评测命令能输出新的 `eval_run_id`

## 6. 发布原则

- 优先小步发布，不把 UI 大改、评测逻辑和基线刷新混成一批
- 若涉及视觉基线更新，必须同步 `manifest.json`、基线清单文档和相关测试
- 若涉及 schema 变化，必须单独提交 Alembic 迁移，并说明升级与回滚路径
- 若涉及 OpenAI 生成链路，必须确认无 key 时的 extractive fallback 仍可用

## 7. 回滚步骤

如果是在执行 `scripts/release_gate.py --phase release --execute` 或切换服务后发现异常，优先按下面顺序回滚：

1. 停止当前服务进程。
2. 恢复上一稳定代码和配置。
3. 按数据库类型恢复上一稳定备份。
4. 重新启动服务。
5. 执行 `python3 scripts/release_gate.py --phase post-release --base-url http://127.0.0.1:8000 --execute`，确认环境回到健康状态。

### 7.1 代码或文档回滚

1. 停止当前服务进程。
2. 恢复到上一个稳定代码版本。
3. 重新执行基础健康检查。

### 7.2 视觉基线回滚

1. 恢复 `tests/baselines/*.png` 和 `tests/baselines/manifest.json` 到上一稳定版本。
2. 运行：

```bash
python3 scripts/render_visual_regression_baselines.py --write
python3 -m pytest -q tests/test_visual_baseline_manifest.py
python3 -m pytest -q tests/test_e2e_visual_regression.py
```

### 7.3 数据库回滚

SQLite：

1. 停服务。
2. 备份当前 `rag_qa_bench.db`。
3. 用上一稳定备份替换。
4. 重启并跑 `/v1/health`。

PostgreSQL：

1. 停服务。
2. 用上一稳定 dump 恢复数据库。
3. 重启并跑 `/v1/health`。

注意：

- 当前仓库已引入 Alembic 初始迁移
- 运行时仍保留 `Base.metadata.create_all()` 兼容层
- 任何 schema 变更都应视为高风险，必须先准备备份和回滚路径

## 8. 常见故障排查

### 8.1 服务无法启动

检查顺序：

1. `.venv` 是否激活
2. 依赖是否安装完整
3. `.env` 中 `DATABASE_URL` 是否可用
4. PostgreSQL 模式下 `docker compose ps` 是否健康

### 8.2 `/v1/health` 失败

检查：

- 数据库连接是否可达
- `rag_qa_bench.db` 是否存在且可读写
- PostgreSQL 的 `vector` extension 是否创建成功
- `/v1/health` 返回的 `database_backend` 是否符合当前 `.env` / 默认配置
- `/v1/health` 返回的 `embedding_storage` 是否符合预期（SQLite 通常为 `json`，PostgreSQL + `pgvector` 为 `pgvector`）
- `/v1/health` 返回的 `feature_flags` 是否符合当前 `FEATURE_EVALS_ENABLED` / `FEATURE_REPLAY_EXPERIMENTS_ENABLED`

### 8.3 问答全部拒答或命中率明显下降

先看：

- `data/docs/` 是否成功导入
- `/v1/qa/runs/{audit_id}` 中的 `failure_stage`
- 当前快照是否把 `retrieval_threshold` 或 `min_evidence_chunks` 调得过高

推荐动作：

- 重跑 `python3 -m app.cli.import_docs --source-dir data/docs`
- 用 `python3 -m app.cli.search --query ...` 检查检索候选
- 对比 `default` 与问题快照的参数差异

### 8.4 视觉回归失败

先看：

- `tests/baselines/*.actual.png`
- `tests/baselines/*.diff.png`
- `docs/visual-regression-baselines.md`

推荐动作：

1. 先确认是基线过期还是页面抖动。
2. 若是抖动，优先收紧测试侧归一化，不先放宽全局阈值。
3. 若是 UI 确认变更，再刷新单个或全部基线，并同步 manifest 与文档。

### 8.5 评测报告生成失败

检查：

- `data/evals/<dataset>.json` 是否存在
- `data/evals/snapshots/<snapshot>.json` 是否存在
- `output/evals/` 是否可写
- 最近 `audit_id` 是否可在 `answer_runs` 中找到

### 8.6 连续循环子会话失败

先看：

- `output/agent-loop/state.json`
- 最新失败轮次的 `output/agent-loop/iterations/<n>/diagnostics.json`
- 对应轮次的 `output/agent-loop/iterations/<n>/events.jsonl`

推荐动作：

1. 先跑 `python3 scripts/project_autopilot.py status --state-dir output/agent-loop --json`，读取 `active_iteration_state`、`latest_failure_summary`、`latest_failure_recovery_hints` 和 `latest_failure_diagnostics_path`。
2. 再用 `diagnostics.json` 中的 `failure_category`、`transport_error_groups` 和 `recovery_hints` 确认是传输层、端点、超时还是普通子会话错误。
3. 如果 `state.json` 显示 `active_iteration` 仍在运行，先看该轮的 `prompt.md` / `events.jsonl`，并结合 `active_iteration_last_progress_at` 判断最近是否仍有推进；不要直接把同目录已有的 `diagnostics.json` 当作当前轮最终结论。
4. 如果 `state.json` 的 `iteration_count` 看起来偏旧，再优先相信最新已落盘的已完成失败轮次 `iterations/<n>/diagnostics.json`，并结合 `events.jsonl` 交叉确认。
4. 如果诊断里出现 `HTTP 426` 或 websocket 升级失败，优先检查当前 endpoint / 代理是否支持 websocket 升级。
5. 如果诊断里出现地址解析失败，再检查域名、DNS 和代理配置，避免继续盲目复跑。

## 9. 监控与证据保留

当前仓库没有独立监控平台，排查主要依赖：

- `/v1/health`
- 问答审计详情接口
- 评测报告 JSON / Markdown
- 视觉回归失败产物
- GitHub Actions job summary、PR comment 和 artifact

建议保留的证据：

- 失败时的 `audit_id`
- 失败时生成的 `report.json` / `report.md`
- 视觉差异图
- 对应 workflow run 链接

## 10. 已知限制

- 当前没有正式发布流水线
- 当前只有环境变量级最小特性开关，没有更细粒度灰度
- 当前没有认证和权限保护

## 11. 关联文档

- [README.md](README.md)
- [ARCHITECTURE.md](ARCHITECTURE.md)
- [IMPLEMENTATION_PLAN.md](IMPLEMENTATION_PLAN.md)
- [docs/continuous-task-loop.md](docs/continuous-task-loop.md)
- [docs/visual-regression-baselines.md](docs/visual-regression-baselines.md)
