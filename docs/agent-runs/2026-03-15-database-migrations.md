# 2026-03-15 数据库迁移机制接入

- 任务名称：引入正式数据库迁移机制
- 项目类型：C 成熟项目优化 / 重构
- 次类型：基础设施治理
- 风险等级：R3

## 正式执行前说明

- 目标：
  - 引入正式数据库迁移机制，结束仅靠 `Base.metadata.create_all()` 初始化 schema 的状态。
  - 为当前 SQLAlchemy schema 落地一版初始迁移。
  - 提供最小可执行的迁移验证路径。
- 非目标：
  - 不调整现有 schema 设计。
  - 不重构业务逻辑。
  - 不在本轮彻底移除 `create_all()`。
- 约束：
  - 必须兼容当前 SQLite 测试流。
  - 必须兼容 PostgreSQL + `pgvector` 场景的文档与迁移说明。
  - 新增基础设施依赖，必须补 ADR。
- 风险：
  - 迁移脚本若与 metadata 不一致，会形成后续 schema 漂移。
  - 若直接改动应用启动初始化链路，容易打断现有测试和本地开发。
- 验收标准：
  - Alembic 配置和初始迁移落地。
  - 至少一条测试验证 SQLite 上 `upgrade head` 能跑通。
  - 相关文档、ADR 和任务日志同步。
  - `ruff` 与 `pytest` 通过。
- 当前项目类型：C 成熟项目优化 / 重构
- 当前风险等级：R3
- 仓库现状：
  - 已存在：README、ARCHITECTURE、IMPLEMENTATION_PLAN、RUNBOOK、SQLAlchemy 模型、SQLite 默认运行、PostgreSQL 可选配置。
  - 缺失：正式迁移机制、迁移验证测试、迁移 ADR。
- 缺失机制清单：
  - Alembic 脚手架
  - 初始 schema 迁移
  - 迁移一致性测试
  - 迁移 ADR
- 方案对比：
  - 方案 A：引入 Alembic、补初始迁移和测试，但暂不移除 `create_all()`。侵入性低，兼容性最好，推荐。
  - 方案 B：引入 Alembic 并立即改为启动时执行迁移。更彻底，但风险明显更高。
  - 方案 C：继续维持现状，只补文档。无法真正解决 schema 治理缺口。
- 推荐方案：方案 A。
- 是否需要 ADR：需要。原因是新增基础设施依赖。
- 测试计划：
  - 先补迁移测试。
  - 运行 `python3 -m pytest -q tests/test_database_migrations.py`
  - 运行 `python3 -m ruff check app tests`
  - 运行 `python3 -m pytest -q`
  - 运行 `python3 -m compileall app tests`
- 实施步骤：
  - 补任务日志与 ADR
  - 先写迁移测试
  - 实现 Alembic 配置与初始迁移
  - 更新文档
  - 跑校验并回填结果

## 实施记录

- 方案摘要：
  - 引入 Alembic，新增 `alembic.ini`、`migrations/env.py`、脚本模板和一版初始 schema 迁移。
  - 先用测试锁定“SQLite 上 `upgrade head` / `downgrade base` 能跑通”的最低验收线，再补实现。
  - 保持 `app/db/session.py` 的 `create_all()` 兼容层不动，只补注释明确正式 schema 演进应以 Alembic 为准。
- 关键决策：
  - 本轮不把应用启动链路切到自动迁移，避免打断当前本地开发和测试基线。
  - 初始迁移直接覆盖当前六张核心业务表，并在 PostgreSQL 下显式创建 `vector` extension。
  - 通过 ADR 记录“为什么先引入 Alembic、但暂不移除 `create_all()`”。
- 变更文件：
  - `alembic.ini`
  - `migrations/env.py`
  - `migrations/script.py.mako`
  - `migrations/versions/20260315_000001_initial_schema.py`
  - `tests/test_database_migrations.py`
  - `pyproject.toml`
  - `app/db/session.py`
  - `README.md`
  - `ARCHITECTURE.md`
  - `IMPLEMENTATION_PLAN.md`
  - `RUNBOOK.md`
  - `docs/adr/2026-03-15-alembic-migrations.md`
  - `docs/agent-runs/2026-03-15-database-migrations.md`
- 风险与未覆盖项：
  - 应用启动仍保留 `create_all()` 兼容层，意味着运行时还没有完全强制“只能通过迁移演进”。
  - 新迁移主要在 SQLite 上做了自动化验证；PostgreSQL + `pgvector` 真实升级链路本轮未在当前环境实跑。
  - 当前 `websockets/uvicorn` 依赖链 warnings 仍然存在，不属于本轮变更。
- 回滚方式：
  - 删除 `alembic.ini`、`migrations/` 和 `tests/test_database_migrations.py`。
  - 回退 `pyproject.toml` 中的 Alembic 依赖。
  - 回退 `README.md`、`ARCHITECTURE.md`、`IMPLEMENTATION_PLAN.md`、`RUNBOOK.md` 和 ADR 中与迁移机制相关的说明。

## 验证结果

- `python3 -m pytest -q tests/test_database_migrations.py`：通过，`2 passed`
- `python3 -m ruff check app tests`：通过
- `python3 -m compileall app tests`：通过
- `python3 -m pytest -q`：通过，`44 passed, 2 warnings`
