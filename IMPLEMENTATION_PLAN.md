# IMPLEMENTATION_PLAN.md

## 1. 文档目的

这份文档记录当前仓库从“演示可用”继续推进到“更可交接、更可发布”的实施计划。

它不是最初立项计划的复写，而是基于当前仓库真实状态的滚动实施计划。

## 2. 当前基线

当前已经完成的主能力：

- 文档导入、切片、嵌入、检索、结构化问答
- 审计记录与问答历史回看
- 离线评测、参数快照、回归对比和回放实验
- 单页工作台与报告面板
- E2E 与视觉回归
- 视觉基线 manifest、诊断图、清理机制、CI 门禁、PR 摘要与 artifact
- 通用质量门禁 workflow，覆盖 `ruff`、全量 `pytest` 与 `compileall`

当前仍然缺失的产品化能力：

- 迁移机制与运行时/CI 的进一步集成
- 更细粒度的特性开关 / 灰度策略
- 对 GitHub Actions comment / artifact 真实链路的环境验收
- 更完整的发布流水线

## 3. 推荐里程碑

### M1. 产品化文档补齐

目标：

- 补齐 `ARCHITECTURE.md`
- 补齐 `IMPLEMENTATION_PLAN.md`
- 补齐 `RUNBOOK.md`
- 让 README 成为索引页，而不是唯一说明页

验收：

- 三份文档存在且与当前代码一致
- README 有入口
- 基础校验通过

状态：本轮完成

### M2. 发布就绪性收口

当前进展：

- 已补最小 `scripts/release_gate.py` 入口，统一发布前、发布中、发布后的本地执行口径
- 已把 release gate 入口同步到 `README.md` 和 `RUNBOOK.md`
- 已完成真实 GitHub PR 环境验收
- 已补正式 `.github/workflows/release-gate.yml` 手动发布 workflow
- 剩余重点转为一次真实目标环境的 release workflow 演练

目标：

- 让 release gate 同时具备本地脚本入口和 GitHub Actions workflow 入口
- 明确 merge gate 与 release gate 的最小集合
- 把本地验证命令与 CI / release workflow 对齐

建议任务：

- 在真实目标环境执行一次 `release-gate.yml`，至少覆盖 `pre-release` 或 `post-release`
- 记录一次 workflow artifact、summary 和执行日志的验收结果
- 视需要补 `pytest -m e2e` 专用 workflow 摘要，进一步压缩主 gate 与专项 gate 的职责边界

验收：

- 至少一次真实 PR 运行被人工验收
- 至少存在正式 release workflow，可由 GitHub Actions 手动触发
- runbook 中的发布检查项可被实际执行

### M3. 数据与 schema 治理

当前进展：

- 已补 Alembic 初始迁移
- 已补本地 `tests/test_database_migrations.py` 漂移检测
- 已补独立 GitHub Actions `Schema Migration Guard` 门禁
- 已补 `/v1/health` 数据库兼容模式暴露与 `tests/test_database_compatibility.py` 自动化锁定
- 剩余重点：受控迁移演练、PostgreSQL 真实链路验收、数据清理规范

目标：

- 把已引入的 Alembic 迁移机制进一步纳入开发、发布和回滚纪律
- 降低 schema 变更和数据回滚风险

建议任务：

- 把新增 schema 变更强制收口到迁移文件
- 在真实 PostgreSQL 环境确认 `embedding_storage=pgvector` 的升级与运行链路
- 评估是否把启动前迁移检查接入 CI 或启动前脚本
- 对评测产物目录与数据库内容建立清理规范

验收：

- 新 schema 变更不再绕过迁移文件
- 至少有一次受控迁移演练

### M4. 运行治理与扩展性

当前进展：

- 已补最小请求级 observability：统一 `X-Request-ID`、请求日志和关键写操作 completion log
- 已补 `/metrics` 最小请求级指标出口
- 已补 `APP_LOG_LEVEL` 配置和运行手册中的最小排障口径
- 剩余重点仍是集中式日志/指标/trace 与更细粒度 rollout

目标：

- 为更接近生产的演示或团队协作提供治理能力

建议任务：

- 将环境变量级开关进一步收敛成更细粒度的特性开关约定
- 增加认证或最小访问控制
- 在 `/metrics` 基础上决定是否接入 Prometheus / OpenTelemetry 等外部采集链路
- 视需求再考虑队列、异步任务或多知识库

验收：

- 关键能力具备开关或访问控制
- 故障排查不再只依赖本地日志和手工观察

## 4. 优先级排序

1. 文档与发布治理
2. 迁移与回滚安全
3. 真实 PR / CI 验收
4. 认证与运行治理
5. 扩展性与规模化能力

## 5. 不建议现在就做的事

- 为了“看起来高级”提前引入 Redis、队列或复杂编排
- 在没有真实需求时把检索改成复杂 ANN 架构
- 在缺少迁移与回滚机制前做大规模 schema 重构
- 在没有访问控制策略前暴露公网服务

## 6. 完成定义

当以下条件同时满足时，可以认为项目从“演示项目”接近“可交接工程样例”：

- 核心功能、测试和视觉回归持续稳定
- 独立架构文档、实施计划和运行手册齐备
- 发布、回滚、故障排查步骤可执行
- schema 变更有正式迁移路径并被团队遵守
- 真实 CI / PR 流程至少做过一次端到端验收

## 7. 关联文档

- [README.md](README.md)
- [ARCHITECTURE.md](ARCHITECTURE.md)
- [RUNBOOK.md](RUNBOOK.md)
