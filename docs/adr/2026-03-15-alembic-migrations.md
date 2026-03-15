# ADR 2026-03-15: 引入 Alembic 作为正式数据库迁移机制

## 状态

已接受

## 背景

当前仓库的数据库 schema 由 `app/db/models.py` 中的 SQLAlchemy metadata 定义，并通过
`app/db/session.py` 里的 `Base.metadata.create_all()` 初始化。

这种方式适合早期演示，但存在明显问题：

- schema 变更没有显式版本历史
- 无法准确表达某次变更何时引入
- 回滚只能依赖手工备份或整库替换
- SQLite 与 PostgreSQL 两种运行模式缺少统一的 schema 演进路径

随着项目从“演示可跑”向“可交接工程样例”推进，需要正式的迁移机制。

## 决策

引入 Alembic 作为仓库的正式数据库迁移工具，并在本轮完成：

- Alembic 配置文件
- 迁移目录与 `env.py`
- 一版覆盖当前 schema 的初始迁移
- SQLite 上的 `upgrade head` 自动化测试

本轮不做的事情：

- 不立即移除 `Base.metadata.create_all()`
- 不在应用启动时自动执行 Alembic
- 不引入数据迁移或大规模 schema 调整

## 选择原因

- Alembic 与当前 SQLAlchemy 栈天然兼容
- 学习和维护成本低于自建迁移脚本
- 能为后续 schema 变更、回滚说明和发布流程提供稳定基座
- 支持按版本管理迁移文件，适合当前仓库的演进节奏

## 备选方案

### 方案 A：继续只用 `create_all()`

拒绝原因：

- 没有版本化迁移历史
- 不适合后续 schema 演进

### 方案 B：直接把启动流程切到 `alembic upgrade head`

暂不采用原因：

- 现有测试和本地启动路径依赖 `create_all()`
- 一次性切换风险过高

## 影响

正向影响：

- schema 变更开始具备正式演进路径
- 回滚和发布讨论可以基于迁移版本展开
- 后续引入正式迁移测试更容易

负向影响：

- 仓库新增 Alembic 配置与维护成本
- 需要保持迁移文件与 SQLAlchemy metadata 同步

## 回滚策略

若需要回退本决策：

1. 删除 Alembic 配置、迁移目录和相关测试。
2. 删除文档中关于正式迁移机制的说明。
3. 继续使用现有 `create_all()` 初始化方式。

## 后续动作

- 下一次 schema 变更必须以新迁移文件表达
- 评估后续是否把启动前迁移检查接入 CLI 或 CI
- 评估何时可以逐步弱化 `create_all()` 的职责
