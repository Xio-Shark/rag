# 2026-03-16 Metrics Endpoint

- 任务名称：为最小 observability 补统一指标出口
- 项目类型：C 成熟项目优化 / 重构
- 次类型：运行治理 / observability 增强
- 风险等级：R2

## 目标

- 在现有 `X-Request-ID` 和结构化日志之外，再补一个最小可读的 `/metrics` 端点。
- 为请求级指标提供统一文本出口，便于后续接 Prometheus 或做 smoke check。

## 非目标

- 不引入外部 metrics 后端或采集代理。
- 不引入 tracing 平台。
- 不在本轮补复杂 histogram、percentile 或告警系统。

## 约束

- 保持低侵入，不引入新依赖。
- 与现有 request middleware 和 observability logger 复用同一份请求完成时机。
- 保持测试、README、RUNBOOK、ARCHITECTURE、IMPLEMENTATION_PLAN 口径一致。

## 方案摘要

- 在 `app/core/observability.py` 中维护最小请求计数和耗时聚合。
- 在 `app/main.py` 暴露 `/metrics` 文本端点。
- 用 `tests/test_observability.py` 锁定输出格式和文档引用。

## 关键决策

- 先暴露最小请求指标，不直接引入外部依赖。

## 变更文件

- `app/core/observability.py`
- `app/main.py`
- `tests/test_observability.py`
- `README.md`
- `RUNBOOK.md`
- `ARCHITECTURE.md`
- `IMPLEMENTATION_PLAN.md`
- `docs/agent-runs/2026-03-16-metrics-endpoint.md`
- `TASK_LOG.md`

## 风险与未覆盖项

- 当前 `/metrics` 只覆盖请求级计数和耗时汇总，还没有直方图、业务指标或 trace。
- 指标当前保存在进程内存里，适合单进程演示，不适合作为多进程部署下的最终聚合方案。

## 回滚方式

- 回退 `app/core/observability.py`
- 回退 `app/main.py`
- 回退 `tests/test_observability.py`
- 回退 `README.md`、`RUNBOOK.md`、`ARCHITECTURE.md`、`IMPLEMENTATION_PLAN.md`
- 删除本任务文档并回退 `TASK_LOG.md`

## 实现结果

- 在 `app/core/observability.py` 中新增最小请求指标聚合：
  - `rag_http_requests_total`
  - `rag_http_request_duration_ms_count`
  - `rag_http_request_duration_ms_sum`
- 新增 `render_metrics()`、`reset_metrics()` 和 Prometheus 文本输出格式。
- 在 `app/main.py` 暴露 `/metrics` 文本端点。
- 指标记录和现有 `http.request.completed` 日志共用同一个请求完成时机，避免双重时序。
- 更新 `README.md`、`RUNBOOK.md`、`ARCHITECTURE.md`、`IMPLEMENTATION_PLAN.md` 的 observability 口径。
- 更新 `tests/test_observability.py`，锁定 `/metrics` 输出与文档引用。

## 验证结果

- `python3 -m pytest -q tests/test_observability.py`
  - `7 passed`
- `python3 -m ruff check app tests`
  - 通过
- `python3 -m pytest -q`
  - `111 passed, 7 skipped, 2 warnings`
