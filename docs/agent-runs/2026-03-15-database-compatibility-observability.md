# 2026-03-15 数据库兼容策略可观测性补强

- 任务名称：数据库兼容策略可观测性补强
- 项目类型：C 成熟项目优化 / 重构
- 次类型：E 运行治理 / 兼容性收口
- 风险等级：R2

## 正式执行前说明

- 目标：
  - 识别当前主线中最高优先级且未完成、可在本地验证的增量项。
  - 将 SQLite / PostgreSQL 兼容策略从“仅文档约定”补强为“运行时可见、测试可锁定”。
  - 同步更新相关文档和任务日志，给下一轮提供明确起点。
- 非目标：
  - 不在本轮引入真实 PostgreSQL 集成环境。
  - 不改检索逻辑、不新增 schema、不调整视觉回归 workflow。
  - 不尝试在当前本地环境伪造 GitHub PR comment / artifact 真实验收。
- 约束：
  - 必须先跑必要校验，再进入实现。
  - 必须遵守 `HOOK.md` / `STANDARDS.md` 的项目分类、风险分级、仓库探测、测试计划和日志更新要求。
  - 改动必须保持增量、可回滚、可本地验证。
- 风险：
  - `/v1/health` 响应扩展字段后，需要保证兼容现有调用方。
  - 若把“兼容策略”做成过度复杂的抽象，反而会扩大改动面。
- 验收标准：
  - 运行时能明确暴露当前数据库后端和向量存储兼容模式。
  - API / 单测能锁定 SQLite 默认模式下的兼容行为。
  - README、架构/运行文档和实施计划同步反映该契约。
- 当前项目类型：
  - 主类型：C 成熟项目优化 / 重构
  - 次类型：E 运行治理 / 兼容性收口
- 当前风险等级：
  - R2：涉及健康检查公共接口的增量扩展，但不改变现有核心行为。
- 仓库现状：
  - 已存在：`README.md`、`ARCHITECTURE.md`、`IMPLEMENTATION_PLAN.md`、`RUNBOOK.md`、`.env.example`、`tests/`、`.github/workflows/`、`migrations/`、`docs/agent-runs/`
  - 缺失：SQLite / PostgreSQL 兼容模式的统一运行时暴露、对应自动化测试、显式特性开关机制、显式应用日志机制说明、真实 PR 环境验收证据
  - 本轮必须先补齐的项：数据库兼容模式的运行时可观测性与测试锁定
- 缺失机制清单：
  - 数据库后端模式（SQLite / PostgreSQL）暴露
  - 向量列兼容模式（`pgvector` / JSON 回退）暴露
  - 对上述兼容契约的 API 级测试
- 方案对比：
  - 方案 A：只补文档说明，不改代码。复杂度最低，但兼容策略仍然不可观测，也无法自动验证。
  - 方案 B：在健康检查中增加数据库兼容信息，并补 API 测试和文档。复杂度低、侵入性小、验证性强，推荐。
  - 方案 C：直接引入 PostgreSQL 集成测试或 Docker 流程。验证更强，但超出本轮约束，且当前 automation 环境没有必要先做这一步。
- 推荐方案：
  - 方案 B。
- 是否需要 ADR：
  - 否。本轮不引入新基础设施，只补现有兼容契约的可观测性。
- 测试计划：
  - 先运行现有基线：`python3 -m pytest -q tests/test_database_migrations.py`
  - 先运行现有基线：`python3 -m pytest -q`
  - 实现后运行针对性测试：`python3 -m pytest -q tests/test_qa_api.py`
  - 再运行静态检查：`python3 -m ruff check app tests`
  - 最后回归全量：`python3 -m pytest -q`
- 实施步骤：
  - 创建本轮任务日志并回填基线校验结果。
  - 在数据库层补充兼容模式判定辅助函数。
  - 扩展 `/v1/health` 响应并补测试锁定 SQLite 默认行为。
  - 同步 README、ARCHITECTURE、RUNBOOK、IMPLEMENTATION_PLAN。
  - 回填验证结果、风险、未覆盖项、回滚步骤和下一步。

## 实施记录

- 方案摘要：
  - 待实现。
- 关键决策：
  - 当前环境无法完成 `M2` 的真实 GitHub PR 链路验收，因此先推进 `M3` 中仍未完成的 SQLite / PostgreSQL 兼容策略细化。
- 变更文件：
  - `docs/agent-runs/2026-03-15-database-compatibility-observability.md`
- 风险与未覆盖项：
  - 待实现后回填。
- 回滚方式：
  - 待实现后回填精确路径。
- 下一步：
  - 在健康检查、测试和文档中统一暴露数据库兼容模式。

## 基线校验

- `python3 -m pytest -q tests/test_database_migrations.py`：通过，`3 passed`
- `python3 -m pytest -q`：通过，`45 passed, 2 warnings`
