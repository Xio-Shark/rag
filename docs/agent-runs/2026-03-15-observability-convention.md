# 2026-03-15 最小 Observability 约定

- 任务名称：补最小统一 observability 约定
- 项目类型：C 成熟项目优化 / 重构
- 次类型：F 原型 / Demo 的运行治理增强
- 风险等级：R2

## 目标

- 为当前 FastAPI 服务补一层统一、可本地验证的最小 observability 约定。
- 让请求链路具备统一请求标识和最小结构化日志字段。
- 为核心写操作补 completion log，降低故障排查只靠人工复现的成本。

## 非目标

- 不引入外部日志平台、指标平台或 trace 平台。
- 不实现完整 metrics exporter、OpenTelemetry 或分布式 tracing。
- 不修改数据库 schema、认证授权或部署架构。

## 约束

- 当前目录不是 Git worktree，无法用真实 PR 页面或部署环境验证日志消费体验。
- 必须优先本地可闭环、低侵入的增量实现。
- 本轮完成后必须同步更新任务日志和相关文档。

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
  - `/v1/health`、`audit_id`、评测报告与运行记录
- 缺失：
  - 统一请求级日志
  - 统一请求标识
  - 核心写操作 completion log
  - 显式日志字段约定
- 本轮必须先补齐的项：
  - 最小统一日志字段
  - `X-Request-ID` 关联能力
  - 文档化的最小 observability 约定

## 方案对比

### 方案 A：只补文档约定

- 复杂度：低
- 成本：低
- 侵入性：低
- 兼容性：高
- 维护成本：中
- 回滚难度：低
- 问题：没有运行时事实源，故障排查仍只能依赖现有零散输出。

### 方案 B：补请求级中间件与最小结构化日志

- 复杂度：中
- 成本：中低
- 侵入性：低
- 兼容性：高
- 维护成本：低于纯文档方案
- 回滚难度：低
- 优势：最小改动即可统一 request id、请求日志和关键域事件日志。

## 推荐方案

- 采用方案 B。
- 先补测试锁定 header、日志字段和核心事件，再补实现，最后同步文档。

## 是否需要 ADR

- 不需要。
- 本轮不新增基础设施依赖，不修改数据库结构、认证授权或核心业务调用链。

## 测试计划

1. 新增 observability 测试，锁定 `X-Request-ID`、关键日志字段和核心 completion log。
2. 实现请求级中间件和日志工具。
3. 运行新增测试。
4. 运行 `python3 -m ruff check app tests scripts`。
5. 运行 `python3 -m compileall app tests scripts`。

## 实施步骤

1. 补任务日志。
2. 新增 observability 契约测试。
3. 实现中间件、日志工具和核心路由 completion log。
4. 更新 `README.md`、`ARCHITECTURE.md`、`RUNBOOK.md`、`IMPLEMENTATION_PLAN.md`、`.env.example`。
5. 跑验证并回填结果、风险和回滚说明。

## 关键决策

- 优先补“本地可观察”的请求级 contract，而不是直接接第三方平台。
- 先统一请求和关键写操作，再决定是否需要更重的指标或 tracing 方案。

## 实现结果

- 新增 `app/core/observability.py`，统一 `X-Request-ID` 生成/透传、结构化日志 payload 和请求级埋点。
- 在 `app/main.py` 挂接请求级 observability 中间件，并通过 `APP_LOG_LEVEL` 统一日志级别。
- 为 `POST /v1/documents/import`、`POST /v1/qa/ask`、`POST /v1/evals/run`、`POST /v1/evals/replay-experiments` 增加 completion log。
- 新增 `tests/test_observability.py`，锁定 request id header、请求日志、completion log 和文档口径。
- 更新 `README.md`、`ARCHITECTURE.md`、`RUNBOOK.md`、`IMPLEMENTATION_PLAN.md`、`.env.example`，同步最小 observability 约定。

## 变更文件

- `app/core/observability.py`
- `app/core/config.py`
- `app/main.py`
- `app/api/routes/documents.py`
- `app/api/routes/qa.py`
- `app/api/routes/evals.py`
- `tests/test_observability.py`
- `.env.example`
- `README.md`
- `ARCHITECTURE.md`
- `RUNBOOK.md`
- `IMPLEMENTATION_PLAN.md`
- `TASK_LOG.md`
- `docs/agent-runs/2026-03-15-observability-convention.md`

## 验证结果

- `python3 -m pytest -q tests/test_observability.py tests/test_qa_api.py tests/test_database_compatibility.py`：`19 passed`
- `python3 -m ruff check app tests scripts`：通过
- `python3 -m compileall app tests scripts`：通过

## 风险与未覆盖项

- 本轮即使补齐最小日志约定，也仍然没有外部集中采集、告警和历史检索能力。
- 如果只做请求级和 completion log，后台脚本、CLI 与数据库内部细粒度事件仍不是统一日志流的一部分。
- 本轮没有在真实 `uvicorn` 进程或部署环境中人工验证日志消费体验，只验证了本地测试链路。
- 当前没有统一指标聚合或 trace span，`duration_ms` 仍主要体现在请求日志中。

## 回滚方式

1. 删除新增的 `app/core/observability.py` 与 `tests/test_observability.py`。
2. 回退 `app/main.py`、`app/core/config.py`、相关路由中的 completion log 埋点。
3. 回退 `README.md`、`ARCHITECTURE.md`、`RUNBOOK.md`、`IMPLEMENTATION_PLAN.md`、`.env.example`。
4. 回退本任务日志和 `TASK_LOG.md` 对应节。
