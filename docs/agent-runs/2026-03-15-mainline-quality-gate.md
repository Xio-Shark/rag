# 2026-03-15 通用 CI 质量门禁

- 任务名称：开始优化完成进度
- 任务聚焦：补仓库缺失的通用 CI 质量门禁
- 项目类型：C 成熟项目优化 / 重构
- 次类型：F 原型 / Demo 的产品化治理收口
- 风险等级：R3

## 正式执行前说明

- 目标：
  - 为当前仓库补一个覆盖通用回归的 GitHub Actions workflow。
  - 让 `ruff`、全量 `pytest` 和 `compileall` 形成持续门禁，而不是只停留在本地命令和 runbook。
  - 同步 README、实施计划、运行手册和任务日志，保持文档口径一致。
- 非目标：
  - 不修改业务逻辑。
  - 不调整数据库 schema、API 契约或前端交互。
  - 不重构现有视觉回归和迁移专用 workflow。
- 约束：
  - 必须复用现有 Python 3.9、`pip install -e ".[dev]"` 和 Playwright/Chromium 运行方式。
  - 必须避免和现有视觉回归 workflow 的职责产生明显冲突。
  - 变更后需要保留清晰回滚路径。
- 风险：
  - CI 门禁会直接影响 PR / main 分支反馈速度和通过条件。
  - 如果路径过滤过窄，可能漏掉真实代码变更；如果过宽，会增加运行成本。
  - 全量 `pytest` 依赖浏览器环境，workflow 若缺少 Chromium 安装会导致假失败。
- 验收标准：
  - 存在一个新的通用质量门禁 workflow。
  - workflow 至少执行 `python -m ruff check app tests`、`python -m pytest -q`、`python -m compileall app tests`。
  - 相关文档说明与当前 CI 结构一致。
  - 本地测试与静态校验通过。
- 当前项目类型：C 成熟项目优化 / 重构
- 当前风险等级：R3
- 仓库现状：
  - 已存在 Schema Migration Guard、Visual Baseline Sync、Visual Regression E2E 三个专项 workflow。
  - 运行手册已经给出发布前检查命令，但仓库缺少覆盖常规回归的通用 quality gate。
  - 全量 `pytest` 已可在本地通过，结果为 `94 passed, 2 warnings`。
- 缺失机制清单：
  - 通用 CI 质量门禁
  - 真实 PR 环境验收记录
  - 显式特性开关
  - 更完整的发布流水线
- 方案对比：
  - 方案 A：新增单独的通用质量门禁 workflow。复杂度低、侵入性低、回滚容易，但会与专项 workflow 产生部分重叠。
  - 方案 B：直接合并现有 workflow，重做成统一流水线。重复更少，但复杂度高、侵入性高、回滚成本高。
- 推荐方案：
  - 采用方案 A，先补缺失的通用 gate，再视真实运行成本决定是否整合。
- 是否需要 ADR：
  - 否。本轮不引入新基础设施，不改核心调用链，只补 CI workflow。
- 测试计划：
  - 先补 workflow 契约测试，锁定新 gate 的关键命令。
  - 执行 `python3 -m pytest -q tests/test_ci_quality_gate.py`
  - 执行 `python3 -m ruff check app tests`
  - 执行 `python3 -m pytest -q`
  - 执行 `PYTHONPYCACHEPREFIX=/tmp/pycache python3 -m compileall app tests`
- 实施步骤：
  - 新增 workflow 契约测试
  - 新增 `.github/workflows/mainline-quality-gate.yml`
  - 更新 `README.md`
  - 更新 `RUNBOOK.md`
  - 更新 `IMPLEMENTATION_PLAN.md`
  - 更新 `TASK_LOG.md`

## 方案摘要

- 用最小增量方式补齐一个通用质量门禁，不动现有专项 workflow 的职责。
- 新 workflow 直接复用仓库当前发布前检查里的核心命令。
- 用独立测试文件锁定 workflow 内容，避免后续文档与 CI 再次漂移。

## 关键决策

- 风险按 `R3` 记录，因为变更会直接影响 PR / main 的持续集成门禁。
- 通用 gate 先保持“验证型”职责，不承担评论、artifact 诊断或发布动作。
- 视觉回归与迁移守卫继续保留专项 workflow，不在本轮合并。

## 变更文件

- `.github/workflows/mainline-quality-gate.yml`
- `tests/test_ci_quality_gate.py`
- `README.md`
- `RUNBOOK.md`
- `IMPLEMENTATION_PLAN.md`
- `TASK_LOG.md`
- `docs/agent-runs/2026-03-15-mainline-quality-gate.md`

## 风险与未覆盖项

- 尚未在真实 GitHub PR 页面验证新 workflow 的展示效果与运行耗时。
- 不覆盖真实 release pipeline 或部署动作。

## 回滚方式

- 删除新增 workflow 与对应测试。
- 回退 README、RUNBOOK、IMPLEMENTATION_PLAN、TASK_LOG 的本轮改动。

## 实现结果

- 已新增 `.github/workflows/mainline-quality-gate.yml`，在核心代码、测试、脚本、迁移和 gate 自身变更时运行。
- 新 gate 已覆盖 `ruff`、全量 `pytest`、`compileall`，并安装 Chromium 以支撑现有浏览器级测试。
- 已新增 `tests/test_ci_quality_gate.py`，锁定 workflow 的关键命令与路径触发范围。
- 已同步更新 README、RUNBOOK、IMPLEMENTATION_PLAN，说明新 gate 与现有专项 workflow 的职责边界。

## 验证结果

- `python3 -m pytest -q tests/test_ci_quality_gate.py`：通过，`1 passed`
- `python3 -m ruff check app tests`：通过
- `python3 -m pytest -q`：通过，`95 passed, 2 warnings`
- `python3 -m compileall app tests`：通过
- 已知告警：
  - `websockets.legacy is deprecated`
  - `websockets.server.WebSocketServerProtocol is deprecated`

## 后续建议

1. 在真实 GitHub PR 上观察一次新增 gate 的耗时和 reviewer 体验，确认是否需要拆分更细粒度 job。
2. 如果后续发现和视觉专项 workflow 重复过多，再考虑把 `pytest -m e2e` 或视觉部分拆成更清晰的职责边界。
3. 下一步可以继续推进特性开关或真实 PR 验收记录，这两项仍是当前完成度的主要缺口。
