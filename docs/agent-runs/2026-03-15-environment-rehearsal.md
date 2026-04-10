# 2026-03-15 真实环境演练证据

- 任务名称：补 PostgreSQL + feature flag + release smoke 的真实环境演练证据
- 项目类型：C 成熟项目优化 / 重构
- 次类型：F 原型 / Demo 的环境验收增强
- 风险等级：R3

## 目标

- 在本地完成一次真实 PostgreSQL + `pgvector` 运行演练。
- 验证 feature flag 在真实服务启动后的可见性与 API 行为。
- 补一份可复用的环境验证证据文档。

## 非目标

- 不伪造真实 GitHub PR 页面验收。
- 不引入新的部署平台或外部基础设施。
- 不扩大为完整自动化发布流水线建设。

## 约束

- 当前目录不是 Git worktree，无法产出真实 PR 页面证据。
- 运行验证尽量不污染现有本地 `.env` 与默认端口。
- 若演练中发现 runbook 和实际命令不一致，需要同步修正文档。

## 仓库探测

- 已存在：
  - `README.md`
  - `ARCHITECTURE.md`
  - `IMPLEMENTATION_PLAN.md`
  - `RUNBOOK.md`
  - `.env.example`
  - `tests/`
  - `.github/workflows/`
  - `migrations/`
  - 最小 feature flag
  - `scripts/release_gate.py`
  - 最小请求级 observability
- 缺失：
  - 真实 PostgreSQL + `pgvector` 运行证据
  - 真实 feature flag 切换证据
  - 发布后 smoke 的真实运行证据
- 本轮必须先补齐的项：
  - 一次真实本地环境演练
  - 明确记录命令、结果、风险和回滚方式

## 方案对比

### 方案 A：只补文档

- 复杂度：低
- 成本：低
- 侵入性：低
- 兼容性：高
- 维护成本：中
- 回滚难度：低
- 问题：没有新增运行证据。

### 方案 B：本地真实演练并沉淀证据

- 复杂度：中
- 成本：中
- 侵入性：低到中
- 兼容性：高
- 维护成本：低
- 回滚难度：低
- 优势：能直接验证当前 runbook、feature flag 和 release smoke 是否真的可执行。

## 推荐方案

- 采用方案 B。
- 先演练，再决定是否需要补文档或脚本。

## 是否需要 ADR

- 不需要。

## 测试计划

1. 启动 PostgreSQL 容器并确认健康。
2. 用临时环境变量执行迁移、导入与服务启动。
3. 验证 `/v1/health` 的数据库后端、嵌入存储、feature flags 与 `X-Request-ID`。
4. 验证关闭 feature flag 后相关 API 的 `503` 行为。
5. 执行发布后 smoke check，并记录结果。

## 实施记录

### 1. 真实 PostgreSQL 证据源

- 当前主机 `127.0.0.1:5432` 已有本地 PostgreSQL 监听，默认 `docker compose.yml` 的 `5432:5432` 无法作为干净证据源。
- 本轮改用独立证据容器 `rag-qa-bench-postgres-evidence`，宿主端口改为 `55432`。
- 验证命令：

```bash
docker exec rag-qa-bench-postgres-evidence pg_isready -U postgres -d rag_qa_bench
psql 'postgresql://postgres:postgres@127.0.0.1:55432/rag_qa_bench' -Atqc \
  "SELECT current_user, current_database();"
```

- 结果：
  - `pg_isready` 返回 `accepting connections`
  - 直连返回 `postgres|rag_qa_bench`
  - 证据采集结束后已执行 `docker rm -f rag-qa-bench-postgres-evidence` 清理临时容器

### 2. 迁移与 schema 证据

- 执行命令：

```bash
DATABASE_URL='postgresql+psycopg://postgres:postgres@127.0.0.1:55432/rag_qa_bench' \
EVAL_REPORTS_DIR='/tmp/rag-env-evidence/reports' \
.venv/bin/python -m alembic upgrade head
```

- Alembic 输出命中 `PostgresqlImpl`，升级到 `20260315_000001`。
- 数据库核对命令：

```bash
psql 'postgresql://postgres:postgres@127.0.0.1:55432/rag_qa_bench' -Atqc \
  "SELECT extname FROM pg_extension WHERE extname='vector';"
psql 'postgresql://postgres:postgres@127.0.0.1:55432/rag_qa_bench' -Atqc \
  "SELECT version_num FROM alembic_version;"
psql 'postgresql://postgres:postgres@127.0.0.1:55432/rag_qa_bench' -Atqc \
  "SELECT table_name, column_name, udt_name FROM information_schema.columns
   WHERE table_name='chunks' AND column_name='embedding';"
```

- 结果：
  - `vector`
  - `20260315_000001`
  - `chunks|embedding|vector`

### 3. 文档导入证据

- 执行命令：

```bash
DATABASE_URL='postgresql+psycopg://postgres:postgres@127.0.0.1:55432/rag_qa_bench' \
EVAL_REPORTS_DIR='/tmp/rag-env-evidence/reports' \
.venv/bin/python -m app.cli.import_docs --source-dir data/docs
```

- 结果：
  - `imported_count=3`
  - `chunk_count=9`
  - 数据库复核：`documents=3`、`chunks=9`

### 4. 服务启动与 flags=on 证据

- 启动命令：

```bash
DATABASE_URL='postgresql+psycopg://postgres:postgres@127.0.0.1:55432/rag_qa_bench' \
EVAL_REPORTS_DIR='/tmp/rag-env-evidence/reports' \
APP_LOG_LEVEL='INFO' \
FEATURE_EVALS_ENABLED='true' \
FEATURE_REPLAY_EXPERIMENTS_ENABLED='true' \
.venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 8010
```

- 健康检查：

```bash
curl -i -s -H 'X-Request-ID: env-proof-health-on' \
  http://127.0.0.1:8010/v1/health
```

- 结果：
  - HTTP `200`
  - header 返回 `x-request-id: env-proof-health-on`
  - payload 关键字段：
    - `database_backend=postgresql`
    - `embedding_storage=pgvector`
    - `feature_flags={"evals": true, "replay_experiments": true}`
    - `document_count=3`
    - `chunk_count=9`

- 正常路径 API：

```bash
curl -i -s -H 'X-Request-ID: env-proof-evals-on' \
  http://127.0.0.1:8010/v1/evals/datasets
curl -i -s -H 'X-Request-ID: env-proof-replay-on' \
  'http://127.0.0.1:8010/v1/evals/replay-experiments?limit=10'
```

- 结果：
  - `/v1/evals/datasets` 返回 `200`，payload `{"items":["baseline_v1"]}`
  - `/v1/evals/replay-experiments` 返回 `200`，payload `{"items":[]}`

### 5. post-release smoke 证据

- 执行命令：

```bash
PATH='/Users/xioshark/Desktop/rag/.venv/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin' \
DATABASE_URL='postgresql+psycopg://postgres:postgres@127.0.0.1:55432/rag_qa_bench' \
EVAL_REPORTS_DIR='/tmp/rag-env-evidence/reports' \
python3 scripts/release_gate.py \
  --phase post-release \
  --base-url http://127.0.0.1:8010 \
  --execute
```

- 结果：
  - health check 通过
  - 搜索烟雾检查通过，返回候选证据
  - 离线评测烟雾检查通过
  - 真实 `eval_run_id`：`02eb82af-6b9e-4f88-8cae-7b984a95bffc`
  - 报告路径：
    - `/private/tmp/rag-env-evidence/reports/02eb82af-6b9e-4f88-8cae-7b984a95bffc/report.json`
    - `/private/tmp/rag-env-evidence/reports/02eb82af-6b9e-4f88-8cae-7b984a95bffc/report.md`

### 6. flags=off 证据

- 重启命令：

```bash
DATABASE_URL='postgresql+psycopg://postgres:postgres@127.0.0.1:55432/rag_qa_bench' \
EVAL_REPORTS_DIR='/tmp/rag-env-evidence/reports' \
APP_LOG_LEVEL='INFO' \
FEATURE_EVALS_ENABLED='false' \
FEATURE_REPLAY_EXPERIMENTS_ENABLED='false' \
.venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 8010
```

- 验证命令：

```bash
curl -i -s -H 'X-Request-ID: env-proof-health-off' \
  http://127.0.0.1:8010/v1/health
curl -i -s -H 'X-Request-ID: env-proof-evals-off' \
  http://127.0.0.1:8010/v1/evals/datasets
curl -i -s -H 'X-Request-ID: env-proof-replay-off' \
  'http://127.0.0.1:8010/v1/evals/replay-experiments?limit=10'
```

- 结果：
  - `/v1/health` 返回 `200`，`feature_flags={"evals": false, "replay_experiments": false}`
  - `/v1/evals/datasets` 返回 `503`，`detail="当前环境未启用评测与回归功能"`
  - `/v1/evals/replay-experiments` 返回 `503`，`detail="当前环境未启用回放实验功能"`

### 7. observability 证据

- 服务进程日志实际输出了请求级结构化日志，例如：
  - `{"event":"http.request.completed","request_id":"env-proof-health-on","path":"/v1/health","status_code":200,...}`
  - `{"event":"http.request.completed","request_id":"env-proof-evals-off","path":"/v1/evals/datasets","status_code":503,...}`

## 本轮发现并修复的运行时缺口

1. Alembic 默认忽略运行时数据库配置
   - 现象：`python -m alembic upgrade head` 会落到 `alembic.ini` 里的默认 SQLite，而不是本轮设置的 PostgreSQL。
   - 修复：更新 `migrations/env.py`，优先使用运行时 `get_settings().database_url`。
   - 测试：`tests/test_database_migrations.py::test_alembic_respects_database_url_from_settings_when_ini_uses_default`

2. PostgreSQL JSON fallback 检索路径有缺口
   - 现象：当运行时无法走 `pgvector` 比较器时，检索仍尝试走 `.cosine_distance()`，真实 smoke 会崩。
   - 修复：
     - `app/services/retrieval.py` 增加 `build_pgvector_distance_expression()` 与应用侧回退。
     - `app/db/types.py` 为 `EmbeddingVector` 显式暴露 `pgvector` comparator。
   - 测试：
     - `tests/test_retrieval.py::test_exact_retrieval_falls_back_to_application_scoring_when_postgres_uses_json`
     - `tests/test_retrieval.py::test_exact_retrieval_falls_back_when_pgvector_distance_expression_is_unavailable`
     - `tests/test_database_compatibility.py::test_embedding_vector_exposes_pgvector_distance_operator`

3. Runbook 缺少宿主机 `5432` 冲突说明
   - 现象：当前主机本地 PostgreSQL 已占用 `5432`，默认 compose 端口映射不足以提供可验证的 Docker 端口。
   - 修复：更新 `RUNBOOK.md`，明确要求先确认端口占用，必要时改用独立宿主端口。

## 验证结果

- `python3 -m pytest -q tests/test_database_compatibility.py tests/test_retrieval.py tests/test_database_migrations.py`：`13 passed`
- `python3 -m ruff check app tests scripts migrations`：通过
- `PYTHONPYCACHEPREFIX=/tmp/rag-env-evidence/pycache python3 -m compileall app tests scripts migrations`：通过
- `python3 scripts/release_gate.py --phase post-release --base-url http://127.0.0.1:8010 --execute`：通过

## 关键决策

- 优先使用临时环境变量和独立端口，避免污染用户现有 `.env`。
- `post-release` smoke 执行时把 `.venv/bin` 置于 `PATH` 前面，确保脚本内部的 `python3` 子命令使用同一解释器。
- 若 runbook 与真实演练步骤不一致，以真实可执行路径为准修正文档。

## 变更文件

- `app/db/types.py`
- `app/services/retrieval.py`
- `migrations/env.py`
- `tests/test_database_compatibility.py`
- `tests/test_retrieval.py`
- `tests/test_database_migrations.py`
- `RUNBOOK.md`
- `TASK_LOG.md`
- `docs/agent-runs/2026-03-15-environment-rehearsal.md`

## 风险与未覆盖项

- 本地真实演练不能替代真实 GitHub PR 页面验收。
- 本轮只验证了本地 Docker + FastAPI，不代表真实云部署、负载均衡和持久卷已经验收。
- rollout 仍然是环境级开关，没有更细粒度灰度。

## 回滚方式

1. 停止本轮启动的服务进程。
2. 停止并移除本轮证据容器：`docker rm -f rag-qa-bench-postgres-evidence`
3. 删除 `/tmp/rag-env-evidence/` 下的临时报告和字节码缓存。
4. 回退本轮代码、文档和任务日志改动。
