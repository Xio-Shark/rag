# 2026-03-15 最小特性开关机制

- 任务名称：继续优化完成进度
- 任务聚焦：补显式特性开关机制
- 项目类型：C 成熟项目优化 / 重构
- 次类型：Demo 工程样例的产品化治理收口
- 风险等级：R2

## 正式执行前说明

- 目标：
  - 为当前仓库补最小可用的显式特性开关机制。
  - 让评测与回放能力可通过环境变量关闭，并在 `/v1/health` 中可观测。
  - 在工作台启动时识别开关状态，避免关闭功能后仍盲目请求接口。
- 非目标：
  - 不引入外部 feature flag 平台。
  - 不做按用户、按百分比或按环境的灰度系统。
  - 不修改数据库 schema、评测算法或前端视觉风格。
- 约束：
  - 默认行为必须完全兼容，未配置开关时现有能力保持开启。
  - 必须优先复用现有 `Settings`、`/v1/health` 和静态工作台结构。
  - 需要保留清晰回滚路径。
- 风险：
  - 会影响关键 API 和工作台初始化链路。
  - 若前后端对开关理解不一致，可能导致 UI 空白、错误提示不清或测试失效。
- 验收标准：
  - `.env.example` 和 `Settings` 中存在显式开关配置。
  - `/v1/health` 返回当前 feature flags。
  - 关闭功能时，相关 API 返回清晰错误。
  - 工作台在关闭功能时能禁用对应入口并给出提示。
  - 全量测试通过。
- 当前项目类型：C 成熟项目优化 / 重构
- 当前风险等级：R2
- 仓库现状：
  - 已有统一配置对象、健康接口、评测/回放 API、前端工作台和全量自动化测试。
  - 当前没有显式特性开关，`IMPLEMENTATION_PLAN.md` 仍把它列为缺口。
- 缺失机制清单：
  - 显式特性开关
  - 真实 GitHub PR 验收记录
  - 更完整的 release pipeline
  - 更强的 observability
- 方案对比：
  - 方案 A：只在配置和健康接口暴露 flags，不做后端/前端行为控制。复杂度低，但不能真正降低风险。
  - 方案 B：配置 + 健康暴露 + API 拦截 + 前端禁用提示。复杂度中等，但能形成最小闭环。
- 推荐方案：
  - 采用方案 B。
- 是否需要 ADR：
  - 否。本轮不引入新依赖或基础设施。
- 测试计划：
  - 先补 API 测试，覆盖 `/v1/health` 的 feature flags 暴露和禁用场景下的 503 返回。
  - 执行 `python3 -m pytest -q tests/test_database_compatibility.py tests/test_qa_api.py`
  - 执行 `python3 -m ruff check app tests`
  - 执行 `python3 -m pytest -q`
  - 执行 `python3 -m compileall app tests`
- 实施步骤：
  - 新增任务日志
  - 补 feature flag 测试
  - 实现配置、健康返回、API 拦截和前端启动兼容
  - 更新 README、ARCHITECTURE、IMPLEMENTATION_PLAN、RUNBOOK、TASK_LOG

## 方案摘要

- 用环境变量级开关实现最小闭环，不把问题扩大成独立平台建设。
- 先覆盖高价值、高成本的实验能力：评测与回放。
- 保持默认开启，降低对现有演示链路和测试稳定性的影响。

## 关键决策

- 特性开关先收敛到“环境级全开/全关”，不做复杂灰度。
- 回放实验单独配置，但在实现层按“评测关闭则回放也视为关闭”的口径处理。
- 前端用健康接口同步状态，避免在禁用场景下启动即连续报错。

## 变更文件

- `.env.example`
- `app/core/config.py`
- `app/api/deps.py`
- `app/api/routes/evals.py`
- `app/api/routes/health.py`
- `app/schemas/health.py`
- `app/static/js/shared.js`
- `app/static/js/workbench.js`
- `tests/test_database_compatibility.py`
- `tests/test_qa_api.py`
- `README.md`
- `ARCHITECTURE.md`
- `IMPLEMENTATION_PLAN.md`
- `RUNBOOK.md`
- `TASK_LOG.md`
- `docs/agent-runs/2026-03-15-feature-flags.md`

## 风险与未覆盖项

- 尚未验证真实部署环境下通过 `.env` 热切换 feature flags 的操作体验。
- 本轮不覆盖更细粒度的灰度策略。

## 回滚方式

- 删除新增 feature flag 字段与相关判断。
- 回退测试、文档和任务日志的本轮改动。

## 实现结果

- 已在 `Settings` 中新增环境变量级最小特性开关：`FEATURE_EVALS_ENABLED`、`FEATURE_REPLAY_EXPERIMENTS_ENABLED`。
- `/v1/health` 现在会返回 `feature_flags`，可直接观察当前评测与回放能力是否开启。
- 评测相关 API 已加硬性守卫：关闭后返回 `503` 和明确中文提示。
- 回放实验相关 API 已加单独守卫：可在保留评测能力时单独关闭回放实验。
- 前端工作台启动时会先读取健康状态；若相关功能被禁用，会禁用对应控件并显示提示，而不是继续盲目请求接口。
- 默认配置仍保持全开，现有演示链路和 E2E 默认兼容。

## 验证结果

- `python3 -m pytest -q tests/test_database_compatibility.py tests/test_qa_api.py`：通过，`13 passed`
- `python3 -m ruff check app tests`：通过
- `python3 -m pytest -q tests/test_e2e_visual_regression.py -k 'mobile_experiment_center or tablet_report_panel'`：通过，`2 passed, 4 deselected`
- `python3 -m pytest -q tests/test_visual_baseline_manifest.py`：通过，`12 passed`
- `python3 -m pytest -q`：通过，`98 passed, 2 warnings`
- `python3 -m compileall app tests`：通过
- 已知告警：
  - `websockets.legacy is deprecated`
  - `websockets.server.WebSocketServerProtocol is deprecated`

## 后续建议

1. 如果继续优化完成度，下一步优先补“真实 GitHub PR 验收记录”，因为本地工程闭环已经更完整了。
2. 若后续需要更接近生产，可把当前环境变量级开关进一步扩展为更细粒度灰度策略，而不是继续堆更多全局 on/off 开关。
3. 如果未来增加高成本能力，可以优先沿用当前 `/v1/health + API 守卫 + 前端禁用提示` 这一套最小模式。
