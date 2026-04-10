# 2026-03-15 项目主线增量推进

- 任务名称：项目主线增量推进
- 项目类型：B 现有项目新增功能
- 次类型：C 成熟项目优化 / 重构
- 风险等级：R1

## 正式执行前说明

- 目标：
  - 基于当前仓库状态识别最高优先级未完成项。
  - 在不扩大改动面的前提下完成一个可验证增量。
  - 补齐本轮方案、验证、风险和回滚记录。
  - 为 Alembic 迁移补一层 schema 漂移门禁，降低后续模型改动绕过迁移文件的风险。
- 非目标：
  - 不做新的 schema 设计调整。
  - 不改应用启动链路，不把运行时切到自动迁移。
  - 不尝试在当前本地环境模拟真实 GitHub PR comment / artifact 验收。
- 约束：
  - 必须先完成项目分类、风险分级、仓库探测和任务日志初始化。
  - 必须先跑必要校验，再进入下一项实现。
  - 不引入无法本地验证的大范围重构。
  - 当前工作区不是 Git 仓库，无法依赖 commit diff 或分支对比做额外校验。
- 风险：
  - 若直接把漂移检测做成高侵入启动逻辑，容易打断现有开发流。
  - GitHub Actions workflow 改动无法在当前环境直接做线上 PR 验收，只能做静态核对和本地测试。
- 验收标准：
  - 本地新增自动化校验能检测 Alembic 迁移与 SQLAlchemy metadata 是否一致。
  - 该校验被接入 GitHub Actions 的独立轻量门禁。
  - 相关文档和任务日志同步更新。
  - 相关测试在本地通过。
- 当前项目类型：
  - 主类型：B 现有项目新增功能
  - 次类型：C 成熟项目优化 / 重构
- 当前风险等级：
  - R1：低风险局部改动；若涉及 schema 或公共接口，再上调。
- 仓库探测：
  - 已存在：`README.md`、`ARCHITECTURE.md`、`IMPLEMENTATION_PLAN.md`、`RUNBOOK.md`、`.env.example`、`tests/`、`.github/workflows/`、`migrations/`、`docs/agent-runs/`
  - 缺失：统一特性开关机制、显式应用日志机制说明、本地 `.git/`
  - 本轮必须先补齐的项：无阻塞性缺口；优先补“迁移与回滚安全”的自动化门禁
- 缺失机制清单：
  - 防止 SQLAlchemy metadata 与 Alembic 迁移漂移的自动化检测
  - 面向迁移安全的独立 CI 轻量门禁
- 方案摘要：
  - 计划在现有 `tests/test_database_migrations.py` 基础上增加 `command.check()` 漂移检测，并新增一个只覆盖迁移安全的 GitHub Actions workflow。
- 关键决策：
  - 当前任务按“继续推进主线”处理，不做纯状态评估。
  - 将 `M2` 的真实 PR 环境验收视为当前环境阻塞项，先推进 `M3` 中本地可验证且更高优先级的迁移安全收口。
- 方案对比：
  - 方案 A：只补文档，记录迁移纪律。复杂度最低，但没有真实门禁，无法防止后续漂移。
  - 方案 B：补本地测试中的漂移检测，并接入独立 CI workflow。复杂度低，兼容性好，验证性强，推荐。
  - 方案 C：把应用启动前强制改成自动迁移检查。约束更强，但侵入性和误伤风险更高。
- 推荐方案：
  - 方案 B。
- 是否需要 ADR：
  - 否。本轮不引入新基础设施，只补现有 Alembic 机制的验证门禁。
- 测试计划：
  - 先运行现有基线：`python3 -m pytest -q tests/test_database_migrations.py`
  - 补测试后运行：`python3 -m pytest -q tests/test_database_migrations.py`
  - 再运行：`python3 -m ruff check app tests`
  - 如时间允许，补一轮：`python3 -m pytest -q`
- 实施步骤：
  - 在迁移测试中加入 Alembic `check` 漂移检测。
  - 新增轻量 workflow，把迁移安全校验接入 GitHub Actions。
  - 同步更新运行/计划文档。
  - 回填验证结果、风险、未覆盖项和下一步。
- 变更文件：
  - `docs/agent-runs/2026-03-15-mainline-increment.md`
- 风险与未覆盖项：
  - 当前工作区不是 Git 仓库，无法依赖 `git status` 或 commit diff 做回滚和变更核对。
  - GitHub Actions workflow 只能做静态更新，无法在本地模拟真实 PR 事件验收。
- 回滚方式：
  - 若仅保留日志变更，删除本文件即可。
  - 若后续产生代码改动，将在实施后补充精确回滚步骤。
- 下一步：
  - 在迁移测试和 CI workflow 上落实 schema 漂移门禁，并完成本地验证。

## 实施记录

- 方案摘要：
  - 在 `tests/test_database_migrations.py` 中新增 `command.check()` 校验，让迁移测试不仅验证 `upgrade` / `downgrade`，还验证当前 metadata 不存在待生成迁移差异。
  - 在 `migrations/env.py` 中开启 `compare_server_default=True`，让漂移检测覆盖 server default。
  - 新增 `.github/workflows/schema-migration-guard.yml`，把迁移安全门禁接入 GitHub Actions。
  - 更新 `RUNBOOK.md` 和 `IMPLEMENTATION_PLAN.md`，把新门禁同步到发布检查和滚动计划中。
- 关键决策：
  - 使用 Alembic 原生 `command.check()`，而不是自写 metadata diff 逻辑，减少维护成本并直接复用 Alembic 的 autogenerate 规则。
  - 漂移门禁仍以 SQLite 本地可跑为最低验收线；PostgreSQL + `pgvector` 真机演练留到下一步。
  - 采用独立轻量 workflow，而不是把迁移检查混进现有视觉回归 workflow，避免关注点耦合。
- 变更文件：
  - `.github/workflows/schema-migration-guard.yml`
  - `migrations/env.py`
  - `tests/test_database_migrations.py`
  - `RUNBOOK.md`
  - `IMPLEMENTATION_PLAN.md`
  - `docs/agent-runs/2026-03-15-mainline-increment.md`

## 验证结果

- `python3 -m pytest -q tests/test_database_migrations.py`：通过，`3 passed`
- `python3 -m ruff check app tests`：通过
- `python3 -m compileall app tests`：通过
- `python3 -m pytest -q`：通过，`45 passed, 2 warnings`

## 风险清单与未覆盖项

- 当前新增 workflow 只做了静态更新，未在真实 GitHub PR 上执行过。
- 迁移漂移检测目前以 SQLite 为主，尚未覆盖 PostgreSQL + `pgvector` 的真实 `upgrade/check` 演练。
- 全量测试中的 `websockets/uvicorn` 依赖 warnings 仍然存在，不属于本轮处理范围。

## 上线检查项

- 确认 `.github/workflows/schema-migration-guard.yml` 已在远端仓库生效。
- 在下一次涉及 `app/db/**` 或 `migrations/**` 的 PR 上观察该 workflow 是否正常触发。
- 若后续涉及 PostgreSQL schema 变更，补一次 Docker 模式下的 `alembic upgrade head` 与 `command.check()` 演练证据。

## 回滚步骤

1. 删除 `.github/workflows/schema-migration-guard.yml`。
2. 删除 `tests/test_database_migrations.py` 中新增的漂移检测用例。
3. 回退 `migrations/env.py` 中新增的 `compare_server_default=True`。
4. 回退 `RUNBOOK.md`、`IMPLEMENTATION_PLAN.md` 和本任务日志中的相关说明。

## 下一步建议

- 优先在 Docker PostgreSQL 模式下补一轮 Alembic `upgrade head` / `check` 演练，形成 SQLite 与 PostgreSQL 的兼容性证据。
- 若外部环境允许，再推进 `M2` 的真实 GitHub PR comment / artifact 验收，补齐发布就绪性闭环。
