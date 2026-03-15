# RAG QA Bench

面向知识库问答场景的单机演示版 RAG 系统，覆盖文档导入、切片索引、精确检索、结构化问答、引用溯源、离线评测与回归对比。

## 项目概览

- 项目名称：RAG QA Bench
- 项目简介：提供 `Markdown/TXT` 文档导入、基于证据的问答、审计记录和离线评测。
- 核心目标：优先保证可解释性、评测稳定性和演示可用性。
- 适用场景：本地演示、实习项目展示、RAG 工程化作品集。

## 项目文档

- [ARCHITECTURE.md](ARCHITECTURE.md)：当前模块分层、数据流和运行形态
- [IMPLEMENTATION_PLAN.md](IMPLEMENTATION_PLAN.md)：基于当前仓库状态的滚动实施计划
- [RUNBOOK.md](RUNBOOK.md)：启动、发布前检查、故障排查和回滚手册
- [docs/continuous-task-loop.md](docs/continuous-task-loop.md)：本地连续任务循环与跨会话 handoff
- [docs/visual-regression-baselines.md](docs/visual-regression-baselines.md)：视觉回归资产与维护流程
- [docs/agent-runs/2026-03-15-github-pr-acceptance.md](docs/agent-runs/2026-03-15-github-pr-acceptance.md)：真实 GitHub PR 验收记录与证据回填入口

## 快速开始

1. 复制环境变量模板：

   ```bash
   cp .env.example .env
   ```

2. 启动数据库：

   ```bash
   docker compose up -d
   ```

   如果不创建 `.env`，应用默认会退回到本地 `SQLite`；复制 `.env.example` 后则会使用 `PostgreSQL`。

3. 安装依赖：

   ```bash
   python3 -m venv .venv
   . .venv/bin/activate
   pip install -e ".[dev]"
   python3 -m playwright install chromium
   ```

4. 执行数据库迁移：

   ```bash
   alembic upgrade head
   ```

5. 初始化数据库并导入样例文档：

   ```bash
   python3 -m app.cli.import_docs --source-dir data/docs
   ```

6. 启动服务：

   ```bash
   uvicorn app.main:app --reload
   ```

7. 运行离线评测：

   ```bash
   python3 -m app.cli.eval run --dataset baseline_v1 --snapshot default
   ```

8. 查看某次评测与报告路径：

   ```bash
   python3 -m app.cli.eval show --eval-run-id <eval_run_id>
   ```

9. 对比两次评测结果并生成差异报告：

   ```bash
   python3 -m app.cli.eval compare --base-eval-run-id <base_id> --target-eval-run-id <target_id>
   ```

## 核心能力

- `python -m app.cli.import_docs`：导入 `Markdown/TXT` 文档，完成去重、切片和向量入库。
- `python -m app.cli.search --query "问题"`：执行本地 exact retrieval，查看 top-k 证据块。
- `alembic upgrade head`：将数据库 schema 升级到当前迁移头。
- `POST /v1/qa/ask`：结构化问答接口，返回回答、引用、证据置信度和审计 ID。
- `GET /v1/qa/runs/{audit_id}`：查看单次问答的审计详情，包含检索候选、失败阶段、耗时、Token 和成本。
- `GET /v1/qa/runs?limit=10`：查看最近问答记录，便于回看历史审计。
- `GET /v1/documents` / `POST /v1/documents/import` / `GET /v1/documents/{document_id}` / `GET /v1/documents/chunks/{chunk_id}`：查看文档列表、触发导入、浏览整篇文档分块并钻取证据片段上下文。
- `python -m app.cli.eval run --dataset baseline_v1 --snapshot default`：加载参数快照并执行评测，输出 JSON/Markdown 报告路径。
- `python -m app.cli.eval compare --base-eval-run-id <base_id> --target-eval-run-id <target_id>`：生成两次评测的指标差值和 bad case 变化报告。
- `python3 scripts/project_autopilot.py start`：后台启动仓库自动化任务，默认持续约 10 小时，或在 `NEXT_ACTION.md` 标记 `completed` 时提前停止。
- `python3 scripts/project_autopilot.py status`：查看后台自动化任务、当前 loop 和任务队列状态。
- `python3 scripts/project_autopilot.py stop`：停止后台自动化任务和当前 loop，便于人工接管或重启新一轮运行窗。
- `python3 scripts/continuous_task_loop.py --goal "..." --duration-hours 10`：启动本地 Codex 顺序循环，每轮新会话推进任务并落盘 handoff 状态。
- `python3 scripts/continuous_task_loop.py --watch --check-interval-minutes 30`：常驻守护当前 loop；主循环因为额度、网络或人工中断停止后，会按间隔自动巡检并唤醒未完成任务。
- `python3 scripts/continuous_task_loop.py --watch --progress-report-minutes 60`：watch 模式下每 60 分钟输出一次进度摘要。
- `python3 scripts/continuous_task_loop.py --check-once`：执行一次巡检，适合配合 `cron` / `launchd` 每 30 分钟或 1 小时定时触发自动恢复。
- `python3 scripts/release_gate.py --phase pre-release --execute`：执行最小发布前 gate，收口迁移、回归、视觉检查和编译校验。
- `python3 scripts/release_gate.py --phase post-release --base-url http://127.0.0.1:8000 --execute`：执行发布后 smoke check，检查 `/v1/health`、搜索和离线评测链路。
- `.github/workflows/release-gate.yml`：正式的手动触发 release workflow，复用 `scripts/release_gate.py`，并上传发布计划与执行日志 artifact。
- `GET /v1/evals/latest` / `GET /v1/evals/runs` / `GET /v1/evals/snapshots` / `GET /v1/evals/datasets` / `GET /v1/evals/compare`：查看最近评测、运行列表、快照列表、数据集列表和回归对比结果。
- `POST /v1/evals/run` / `GET /v1/evals/{eval_run_id}/report`：通过 HTTP 运行评测并读取报告正文。
- `POST /v1/evals/replay-experiments` / `GET /v1/evals/replay-experiments` / `GET /v1/evals/replay-experiments/compare`：基于 bad case 创建带快照覆盖参数的回放实验、查看实验记录，并持续对比不同回放方案。
- `GET /v1/health`：查看数据库、模型配置、索引状态、特性开关，以及当前数据库后端 / 嵌入存储兼容模式。
- 对比报告会同时输出快照参数、指标变化和归因提示，方便判断回归是由上下文缩窄、拒答门槛提高还是候选召回减少导致。

## 运行说明

- 默认使用 `hash` 嵌入后端，便于轻量本地验证；如需本地模型，可安装 `sentence-transformers` 并把 `EMBEDDING_BACKEND` 调整为 `sentence-transformers`。
- 如果你的目标是“一条命令让仓库后台自动跑约 10 小时，或者直到验收完成”，优先使用 `scripts/project_autopilot.py start`；它会后台启动 `continuous_task_loop.py --watch`，并在旧运行窗已终态或过期时自动刷新新的 10 小时时间窗。
- `python3 scripts/project_autopilot.py status --json` 会额外输出 `active_iteration_state`（`inactive` / `live` / `stale`）、推导后的 `active_iteration_last_progress_at`，以及最新失败诊断聚合字段：`latest_failure_iteration`、`latest_failure_diagnostics_path`、`latest_failure_attempt`、`latest_failure_category`、`latest_failure_summary`、`latest_failure_transport_error_groups`、`latest_failure_recovery_hints`。
- 如果希望把任务连续推进数小时，不要依赖单个聊天上下文一直增长；优先使用 `scripts/continuous_task_loop.py`，它会把目标、队列、记忆和 handoff prompt 落盘到 `output/agent-loop/`，并在每轮启动新的 `codex exec` 会话继续。
- `--watch` 模式现在默认每 60 分钟输出一次进度摘要；如需调整频率，可传 `--progress-report-minutes`。
- `--duration-hours` 现在会作为整个运行窗的硬上限参与单轮超时计算；如果离截止时间只剩几分钟，当前轮不会再按完整 `--max-seconds-per-iteration` 继续跑到超窗。
- 如果某一轮 `codex exec` 失败，优先查看对应 `output/agent-loop/iterations/<n>/diagnostics.json`；它会把关键错误、传输层报错和简短结论先提炼出来。
- `diagnostics.json` 现在会额外记录该轮 `iteration`、`attempt`、`child_pid`、`failure_category`、`transport_error_groups` 和 `recovery_hints`，方便区分“同编号第几次尝试”、快速识别失败类型，并直接读取下一步排障提示。
- 即使最新失败指向的是旧版 `diagnostics.json`，`status --json` 也会基于其中保留的 `transport_errors` / `error_messages` / `warnings` 兜底推导 `latest_failure_category`、`latest_failure_transport_error_groups` 和 `latest_failure_recovery_hints`，尽量维持单命令可读性。
- 推荐巡检顺序是先跑 `python3 scripts/project_autopilot.py status --json`：若 `active_iteration_state=live`，优先跟进当前活动轮次；若为 `stale` 或 `inactive`，再直接读取 `latest_failure_summary` / `latest_failure_recovery_hints`，必要时打开 `latest_failure_diagnostics_path` 查看完整证据。
- `transport_error_groups` 会把重复的 transport 日志按类型 / 组件 / URL 聚合计数；`recovery_hints` 只提供保守的排查方向，不会把 warning 或单条现象直接当作已确认根因。
- `state.json` 中的 `active_iteration_last_progress_at` 会在子会话启动和输出新日志时更新；如果当前活动轮次来自尚未热加载该字段的旧主循环进程，handoff / watch 也会回退到活动轮次目录里 `prompt.md`、`events.jsonl`、`stderr.log` 的最新 mtime 作为最近进展时间。
- watch 进度摘要现在还会输出 `active_state=inactive|live|stale`；`stale` 表示状态文件仍保留了 `active_iteration`，但对应 loop / child pid 已不存活，不应继续把它当成 live child。
- 如果 `state.json` / `history` 一时落后于磁盘中的迭代产物，handoff 也会优先引用更高编号失败轮次的 `diagnostics.json`；若更新轮次没有失败诊断，则不会错误回退到更旧失败。
- 如果守护层恢复了一个尚未写回 `history` 的轮次，脚本会在重试前清理该 `iterations/<n>/` 目录里的已知旧产物，避免陈旧 `diagnostics.json`、`last-message.md` 或 `events.jsonl` 混入新一轮证据。
- 如果 `loop_pid` 对应的主循环仍在运行，handoff 会优先提示查看当前 `active_iteration` 的 `prompt.md` / `events.jsonl`，并补充 `attempt` / `child_pid` / `last_progress_at` 线索，而不会把同目录里可能残留的旧失败诊断误当成最新结论。
- 如果 handoff 明确提示“未收口的活动轮次标记”，表示状态文件里还留着轮次编号，但 pid liveness 已不支持“仍在运行”的判断；这时应优先查看失败诊断或等待恢复逻辑接管。
- 如果担心主循环因额度、网络或终端关闭而中断，可以额外启用 `--watch` 常驻巡检，或用 `--check-once` 配合系统定时器定期检查 `output/agent-loop/state.json`；只要任务还没结束且当前没有 loop 进程，守护层会自动唤醒并继续未完成事项。
- 当主循环已经退出、但 `state.json` 还停留在 `running` 时，watch / check-once 现在会重新计算终态并把状态收口到 `deadline_reached` / `completed` / `queue_exhausted` 等真实结果，而不是一直保留 stale running。
- SQLite 模式下，`chunks.embedding` 会以 JSON 形式存储；PostgreSQL 且 `pgvector` 依赖可用时，会切到 `pgvector` 列类型。可通过 `/v1/health` 的 `database_backend` 与 `embedding_storage` 字段直接确认当前实际模式。
- 当前已补最小特性开关：`FEATURE_EVALS_ENABLED=false` 可关闭评测/回归相关 API 与工作台入口；`FEATURE_REPLAY_EXPERIMENTS_ENABLED=false` 可单独关闭 bad case 回放实验。当前实际生效状态会直接出现在 `/v1/health` 的 `feature_flags` 字段里。
- 当前已补最小请求级 observability：所有 HTTP 响应都会带 `X-Request-ID`；如果调用方已传该 header，服务会沿用原值，便于把客户端、服务端和后续排障记录串起来。
- 当前请求日志消息体为 JSON，最小字段包括 `event`、`request_id`、`method`、`path`、`status_code`、`duration_ms`；核心写操作还会额外输出 `documents.import.completed`、`qa.ask.completed`、`eval.run.completed`、`eval.replay.completed` 这类 completion log。
- `APP_LOG_LEVEL` 控制应用日志级别，默认 `INFO`；当前最小 observability 仍主要面向本地 stdout/stderr，不包含外部集中采集、告警或 trace 平台。
- 当配置 `OPENAI_API_KEY` 时，生成层优先调用线上模型；否则自动回退到可解释的抽取式回答生成器。
- 小规模数据集默认使用精确检索，不启用近似索引，便于评测稳定和参数回归。
- 评测快照放在 `data/evals/snapshots/`，评测产物默认输出到 `output/evals/<eval_run_id>/report.json` 和 `report.md`。
- 对比报告默认输出到 `output/evals/compare/<base_id>__vs__<target_id>/`。
- 首页现在支持直接导入文档、执行评测、读取报告和查看回归对比，不再只依赖 CLI。
- 前端工作台脚本已继续拆成 `app/static/index.js` + `app/static/js/shared.js` + `app/static/js/eval-renderers.js` + `app/static/js/knowledge-renderers.js` + `app/static/js/replay-renderers.js` + `app/static/js/renderers.js` + `app/static/js/knowledge.js` + `app/static/js/evals.js` + `app/static/js/replay.js` + `app/static/js/report.js` + `app/static/js/workbench.js`，其中 `renderers.js` 只做聚合导出，`workbench.js` 只负责组装启动，后续继续扩展实验面板时更容易维护。
- 首页布局已按“问答工作流 / 实验中心 / 证据浏览”三段重新组织，并为每张卡片补了操作提示，减少单页里信息堆叠时的阅读压力。
- 报告查看卡片现在支持标题导航、按 case 片段定位以及一键恢复完整报告，适合在回归钻取和回放实验之间来回切换。
- 评测对比和实验对比现在都会先展示“实验摘要”卡，把总体结论、关键变化、bad case 变化和参数变化压到首屏。
- 实验摘要卡现在会根据当前结论给出“去看 bad case / 查看审计 / 恢复完整报告 / 查看参数差异”等建议动作，把摘要直接变成下一步入口。
- 对比页支持点击 bad case 钻取回归用例，页面会同步展示基线/对比答案差异，并把右侧报告面板定位到对应报告片段。
- 回归钻取卡片支持从 bad case 直接跳到对应问答审计，形成“评测 -> bad case -> 审计 -> 证据片段”的闭环。
- Bad Case 工作台现在支持选择回放快照、覆盖 `top_k`、覆盖拒答阈值，并把每次回放落成可持续查看的实验记录。
- 实验记录卡片支持连续选择两次回放实验做对比，直接查看参数差异、答案变化、引用重叠和归因提示。
- 浏览器级端到端测试已覆盖“评测运行 -> 回归钻取 -> bad case 回放 -> 实验记录 -> 实验对比”“回归钻取 -> 报告面板联动”“先读报告 -> 回归钻取 -> 审计联动”以及“问答 -> 审计 -> 证据片段 -> 文档浏览”四条主链路。
- 当前已补 6 条视觉回归测试，分别覆盖桌面端“实验中心”“问答工作流 + 证据浏览”“报告查看 + 报告导航 + 恢复完整报告”、移动端“实验中心”、平板视口“问答工作流 + 证据浏览”以及平板视口“报告查看 + 报告导航 + 恢复完整报告”主链路；正式基线当前以 GitHub Actions Linux 环境为准，非 Linux 本机默认跳过这组像素级对比；如需强制在本机执行，可设置 `ALLOW_NON_LINUX_VISUAL_REGRESSION=1`，更新基线命令仍为 `UPDATE_VISUAL_BASELINES=1 python3 -m pytest -q tests/test_e2e_visual_regression.py`。
- 当视觉回归失败时，当前会额外输出 `.actual.png` 和 `.diff.png` 诊断产物，便于快速定位像素差异；同名用例重新通过或刷新基线后，过期诊断产物会自动清理；这些产物已加入 `.gitignore`。
- `tests/test_visual_baseline_manifest.py` 现在还会直接校验 `tests/baselines/` 目录中没有残留 `.actual.png` / `.diff.png`，把这条约束纳入最小门禁。
- `scripts/render_visual_regression_baselines.py` 现在支持 `--summary` 和 `--path`，可在本地或 CI 打印基线变更摘要，直接看到图片对应的测试、视口和覆盖链路。
- GitHub Actions 里的视觉基线同步 workflow 会把这段摘要同时输出到 step 日志和 job summary，方便 reviewer 直接查看。
- 对于同仓库 PR，这段摘要还会被更新到一条固定 PR comment；fork PR 会跳过评论步骤，避免只读 `GITHUB_TOKEN` 失败。
- 仓库还新增了独立的 `.github/workflows/visual-regression-e2e.yml`，会在相关文件变更时运行 `tests/test_e2e_visual_regression.py`，失败时自动上传 `.actual.png` / `.diff.png` 诊断产物。
- 当这条视觉回归 E2E workflow 失败时，还会把诊断图关联回正式基线、视口、覆盖链路和测试名，并写入 job summary。
- 对于同仓库 PR，这段失败诊断摘要也会被更新到固定 PR comment；fork PR 会跳过评论步骤。
- 这条 workflow 还会上传 `pytest` 生成的 JUnit XML，以及失败诊断摘要 markdown 文件本身，便于离开 GitHub UI 后继续复用。
- 对于同仓库 PR，失败 comment 现在还会带上这些 artifact 的可点击链接，方便直接跳到 JUnit、摘要或诊断图下载页。
- 当后续运行恢复通过时，这条固定失败 comment 会自动更新为“已恢复通过”，避免 PR 页面残留过期告警。
- 失败或恢复 comment 现在还会带上本次 GitHub Actions run 的直达链接和 run 编号，方便 reviewer 直接跳转到对应构建。
- 正式基线、诊断产物、更新方式和排障路径已整理到 [docs/visual-regression-baselines.md](/Users/xioshark/Desktop/rag/docs/visual-regression-baselines.md)，后续新增视觉基线时可先更新 `tests/baselines/manifest.json`，再执行 `python3 scripts/render_visual_regression_baselines.py --write` 重建清单。
- 仓库已补最小 GitHub Actions：`.github/workflows/visual-baseline-sync.yml` 会在相关文件变更时检查 manifest 测试、文档同步状态和 `app/tests` 轻量 lint。
- 仓库已补通用质量门禁：`.github/workflows/mainline-quality-gate.yml` 会在核心代码、测试、脚本、迁移或 workflow 变更时运行 `ruff`、全量 `pytest` 和 `compileall`，把本地常规回归转成持续门禁。
- 问答页支持自动加载审计详情，直接回看检索候选、失败阶段和运行元数据。
- 问答页支持刷新最近问答记录，点击历史问题即可回看对应审计详情。
- 问答页支持点击检索候选钻取证据片段，并显示当前 chunk 的前后相邻上下文。
- 文档浏览卡片会展示整篇文档的分块时间线，并在从证据片段进入时自动高亮命中的 chunk。
- 文档浏览支持按当前问题或自定义关键词过滤 chunk，便于快速定位命中证据在整篇文档中的位置。

## 快照说明

- `default`：默认演示快照，平衡引用精度、groundedness 和拒答稳定性。
- `compact_context`：只保留一条证据，适合观察多事实问题的 groundedness 损失。
- `strict_guard`：提高检索阈值并要求更多证据块，适合观察保守拒答带来的召回损失。
- `recall_boost`：降低检索阈值并保留更多候选，适合观察更激进召回对稳定性的影响。

## 当前样例结果

- `default`：当前样例集可达到 `hit@5=1.0`、`citation_precision@3=1.0`、`refusal_accuracy=1.0`、`grounded_answer_rate=1.0`。
- `compact_context`：当前样例集会将 `grounded_answer_rate` 降到 `0.7143`，适合演示上下文压缩导致的多事实回答退化。
- `strict_guard`：当前样例集会将 `refusal_accuracy` 降到 `0.8571`、`grounded_answer_rate` 降到 `0.7143`，适合演示过度保守的拒答策略。

## 验证命令

如果只想看当前 release gate 计划，可先执行：

```bash
python3 scripts/release_gate.py
```

如果希望通过 GitHub Actions 手动触发正式 release workflow，可执行：

```bash
gh workflow run release-gate.yml -f phase=pre-release -f execute=true
```

如果只是想在 GitHub 上先看 dry-run 计划，把 `execute=true` 改成 `execute=false`；发布后 smoke check 场景再额外传 `-f base_url=http://目标地址`。

执行发布前检查时，优先使用最小 release gate 入口：

```bash
python3 scripts/release_gate.py --phase pre-release --execute
```

目标环境完成切换后，可用下面的命令跑发布后 smoke check：

```bash
python3 scripts/release_gate.py --phase post-release --base-url http://127.0.0.1:8000 --execute
```

如果你只想手工执行对齐 CI 的基础命令，当前 `python3 -m ruff check app tests scripts`、`python3 -m pytest -q` 和 `python3 -m compileall app tests scripts` 已与 release gate 对齐，这三项也与 `.github/workflows/mainline-quality-gate.yml` 对齐。

```bash
python3 -m ruff check app tests scripts
python3 -m pytest -q
python3 -m pytest -q -m e2e
python3 -m pytest -q tests/test_e2e_visual_regression.py
python3 scripts/render_visual_regression_baselines.py --check
python3 -m compileall app tests scripts
```
