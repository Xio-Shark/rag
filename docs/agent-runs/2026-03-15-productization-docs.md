# 2026-03-15 产品化文档补齐

- 任务名称：补齐架构文档、实施计划与运行手册
- 项目类型：C 成熟项目优化 / 重构
- 次类型：R0 文档治理
- 风险等级：R0

## 正式执行前说明

- 目标：
  - 补齐独立 `ARCHITECTURE.md`、`IMPLEMENTATION_PLAN.md` 和 `RUNBOOK.md`。
  - 明确当前仓库的模块分层、默认运行方式、发布检查项和回滚路径。
  - 让仓库从“功能可跑”推进到“可交接、可运维、可回滚”。
- 非目标：
  - 不修改业务逻辑。
  - 不新增基础设施依赖。
  - 不重写现有 README 的主体内容。
- 约束：
  - 文档必须以当前代码行为为准，不能写成未实现的理想态。
  - 必须明确“默认本地 SQLite，可按 `.env` 切换到 Postgres”的现状。
  - 继续保持单机演示优先的定位。
- 风险：
  - 若文档与代码现状不一致，会误导交接、演示和运维。
  - README 和独立文档如果边界不清，会形成重复维护。
- 验收标准：
  - 三份独立文档落地。
  - README 增加清晰入口。
  - 任务日志更新。
  - `python3 -m ruff check app tests` 和 `python3 -m pytest -q` 继续通过。
- 当前项目类型：C 成熟项目优化 / 重构
- 当前风险等级：R0
- 仓库现状：
  - 已存在：`README.md`、`.env.example`、测试框架、GitHub Actions、任务日志、视觉回归与最小门禁。
  - 缺失：独立 architecture 文档、独立 implementation plan、`RUNBOOK.md`。
- 缺失机制清单：
  - 模块分层与数据流说明
  - 发布 / 回滚 runbook
  - 面向当前仓库现状的产品化实施计划
- 方案对比：
  - 方案 A：新增独立文档，并在 README 提供入口。复杂度低、侵入性最低、维护边界清晰，推荐。
  - 方案 B：继续把所有说明堆在 README。短期改动少，但维护性差，交接成本高。
- 推荐方案：方案 A。
- 是否需要 ADR：否。
- 测试计划：
  - 运行 `python3 -m ruff check app tests`
  - 运行 `python3 -m pytest -q`
- 实施步骤：
  - 复核现有规划文档、配置、入口与数据模型
  - 产出 `ARCHITECTURE.md`
  - 产出 `IMPLEMENTATION_PLAN.md`
  - 产出 `RUNBOOK.md`
  - 更新 `README.md`
  - 跑校验并回填结果

## 实施记录

- 方案摘要：
  - 新增三份独立文档，分别承载架构说明、滚动实施计划和运行手册，避免继续把所有信息堆在 `README.md`。
  - 文档内容以当前代码为准，明确写出默认 SQLite、`.env` 切换 PostgreSQL、当前无正式迁移框架和无统一特性开关等边界。
  - README 只保留索引入口与快速开始，不再承担全部产品化说明。
- 关键决策：
  - 不重写原有 `RAG问答质量平台-项目规划.md`，而是把它当成历史规划素材，新增一份面向当前仓库现状的 `IMPLEMENTATION_PLAN.md`。
  - `RUNBOOK.md` 按当前仓库真实运行方式编写，不假设尚未存在的发布平台或线上环境。
  - `.env.example` 只补充注释说明，不改变现有 PostgreSQL 示例值，保持已有快速开始流程不变。
- 变更文件：
  - `ARCHITECTURE.md`
  - `IMPLEMENTATION_PLAN.md`
  - `RUNBOOK.md`
  - `README.md`
  - `.env.example`
  - `docs/agent-runs/2026-03-15-productization-docs.md`
- 风险与未覆盖项：
  - 本轮补的是文档与规范，不会自动引入迁移框架、特性开关或正式发布流水线。
  - `RUNBOOK.md` 中关于“恢复上一稳定版本”的步骤依赖外部版本管理或备份体系，当前工作区本地并不直接提供这部分能力。
  - 当前 warnings 仍来自现有 `websockets/uvicorn` 依赖链，不属于本轮变更。
- 回滚方式：
  - 删除 `ARCHITECTURE.md`、`IMPLEMENTATION_PLAN.md`、`RUNBOOK.md`。
  - 回退 `README.md` 与 `.env.example` 的文档入口和注释改动。

## 验证结果

- `python3 -m ruff check app tests`：通过
- `python3 -m pytest -q`：通过，`42 passed, 2 warnings`
