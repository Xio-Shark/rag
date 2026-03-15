# 2026-03-15 Release Gate 收口

- 任务名称：把发布检查收口为可执行的最小 release gate
- 项目类型：C 成熟项目优化 / 重构
- 次类型：F 原型 / Demo 的发布治理增强
- 风险等级：R2

## 目标

- 把当前仓库的发布检查从零散文档命令收口成分阶段、可执行的最小 release gate。
- 在 `RUNBOOK.md` 中明确发布前、发布中、发布后的检查路径。
- 让 README、实施计划和运行手册对齐同一套口径。

## 非目标

- 不补真实 GitHub PR 页面验收记录。
- 不引入外部发布平台、灰度平台或统一 observability 平台。
- 不修改业务接口、数据库 schema 或前端功能。

## 约束

- 当前目录不是 Git worktree，无法依赖真实分支、PR 或 commit 状态做发布验收。
- 只能做本地可验证、低侵入的增量治理。
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
  - 最小 feature flag 与回滚说明
- 缺失：
  - 真实 GitHub PR 验收记录
  - 正式 release pipeline
  - 更细粒度 rollout
  - 统一 observability 约定
  - 可本地直接执行的 release gate 入口
- 本轮必须先补齐的项：
  - 分阶段 release gate 入口
  - 对应测试契约
  - 运行手册与 README 的统一口径

## 方案对比

### 方案 A：只补文档

- 复杂度：低
- 成本：低
- 侵入性：低
- 兼容性：高
- 维护成本：中
- 回滚难度：低
- 问题：执行性弱，后续容易再次与实际检查命令漂移。

### 方案 B：补最小脚本并让文档引用它

- 复杂度：中
- 成本：中低
- 侵入性：低
- 兼容性：高
- 维护成本：低于纯文档方案
- 回滚难度：低
- 优势：把阶段、命令和执行路径固化为一个事实源。

## 推荐方案

- 采用方案 B。
- 先补测试锁定阶段和关键命令，再实现脚本，最后更新文档。

## 是否需要 ADR

- 不需要。
- 本轮不新增基础设施依赖，不修改数据库结构、认证授权或核心调用链。

## 测试计划

1. 新增 release gate 脚本测试，锁定阶段名称、关键命令和 dry-run 输出。
2. 实现脚本后运行新增测试。
3. 运行 `python3 -m ruff check app tests scripts`。
4. 运行 `python3 -m compileall app tests scripts`。
5. 执行一次 release gate dry-run 作为人工验收。

## 实施步骤

1. 补任务日志。
2. 新增 release gate 测试。
3. 实现脚本。
4. 更新 `RUNBOOK.md`、`README.md`、`IMPLEMENTATION_PLAN.md`。
5. 跑验证并回填结果、风险和回滚说明。

## 关键决策

- 优先补“可本地执行的最小 release gate”，不假设已经拥有正式发布平台。
- 保持与现有 CI、Alembic、feature flag 和健康检查能力对齐，不再新增分叉入口。
- 既然新增脚本落在 `scripts/`，就同步把 mainline quality gate 的 `ruff` 和 `compileall` 覆盖范围扩到 `scripts/`，避免 CI 漏检。

## 实现结果

- 新增 `scripts/release_gate.py`，把发布流程收口为 `pre-release`、`release`、`post-release` 三个阶段。
- 新增 `tests/test_release_gate.py`，锁定阶段划分、关键命令、health check 和文档同步口径。
- 更新 `.github/workflows/mainline-quality-gate.yml` 与 `tests/test_ci_quality_gate.py`，让 `ruff` 和 `compileall` 继续门禁 `scripts/`。
- 更新 `README.md`、`RUNBOOK.md`、`IMPLEMENTATION_PLAN.md`，统一 release gate 入口、执行方式和 M2 进展描述。
- 为通过新的 `ruff` 范围，顺手修正了 `scripts/export_resume_pdfs.py` 的 import 排序。

## 变更文件

- `scripts/release_gate.py`
- `tests/test_release_gate.py`
- `.github/workflows/mainline-quality-gate.yml`
- `tests/test_ci_quality_gate.py`
- `README.md`
- `RUNBOOK.md`
- `IMPLEMENTATION_PLAN.md`
- `TASK_LOG.md`
- `docs/agent-runs/2026-03-15-release-gate.md`
- `scripts/export_resume_pdfs.py`

## 验证结果

- `python3 -m pytest -q tests/test_release_gate.py tests/test_ci_quality_gate.py`：`6 passed`
- `python3 -m ruff check app tests scripts`：通过
- `python3 -m compileall app tests scripts`：通过
- `python3 scripts/release_gate.py`：dry-run 输出通过，能展示三阶段 release gate 计划

## 风险与未覆盖项

- 真实 GitHub PR 页面、artifact 和 comment 生命周期仍无法在本地直接验收。
- 本轮没有对 `python3 scripts/release_gate.py --phase release --execute` 做真实目标环境演练。
- 本轮没有对 `python3 scripts/release_gate.py --phase post-release --execute` 做 live service 验证；如果本地未启动服务或未准备样例数据，发布后 smoke check 仍只能验证命令路径。

## 回滚方式

1. 删除新增的 `scripts/release_gate.py` 与 `tests/test_release_gate.py`。
2. 回退 `.github/workflows/mainline-quality-gate.yml` 与 `tests/test_ci_quality_gate.py` 中对 `scripts/` 的门禁覆盖。
3. 回退 `README.md`、`RUNBOOK.md`、`IMPLEMENTATION_PLAN.md`。
4. 如无需保留格式化结果，回退 `scripts/export_resume_pdfs.py` 的 import 排序改动。
5. 回退本任务日志和 `TASK_LOG.md` 对应节。
