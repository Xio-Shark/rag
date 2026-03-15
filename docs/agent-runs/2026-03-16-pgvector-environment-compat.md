# 2026-03-16 pgvector 环境兼容收口

- 任务名称：收口本地 `pgvector` 缺失导致的全量测试环境差异
- 项目类型：C 成熟项目优化 / 重构
- 次类型：测试稳定性 / 环境兼容性
- 风险等级：R1

## 目标

- 让当前机器在缺少 `pgvector` Python 包的情况下，仍能完成全量 `pytest` 回归。
- 把“环境未安装依赖”和“代码逻辑回归”从测试信号上分离开。

## 非目标

- 不改数据库 schema。
- 不改 `EmbeddingVector` 的运行时实现。
- 不在本轮强制修改当前机器 Python 环境。

## 约束

- 仓库当前运行形态允许 `pgvector` 相关能力按环境退化。
- 修复必须保持 CI 和安装了 `pgvector` 的环境仍能继续验证距离比较器能力。

## 方案对比

### 方案 A：要求当前机器补装 `pgvector`

- 复杂度：低
- 性能：高
- 成本：低
- 侵入性：中
- 兼容性：中
- 维护成本：中
- 回滚难度：低
- 问题：这是环境修补，不是仓库自身的测试稳定性收口。

### 方案 B：在缺少 `pgvector` 时显式 skip 比较器测试

- 复杂度：低
- 性能：高
- 成本：低
- 侵入性：低
- 兼容性：高
- 维护成本：低
- 回滚难度：低
- 优势：能把环境差异转成明确测试信号，不再让全量回归误红。

## 推荐方案

- 采用方案 B。

## 是否需要 ADR

- 不需要。
- 本轮只调整测试口径，不改架构和运行时行为。

## 测试计划

1. 修改 `tests/test_database_compatibility.py`，在未安装 `pgvector` 时显式 skip 距离比较器测试。
2. 运行数据库兼容性测试和 `ruff`。
3. 运行全量 `pytest`，确认当前机器回归恢复全绿。

## 实施结果

- 已更新 `tests/test_database_compatibility.py`
- 当前 Python 环境下若 `importlib.util.find_spec("pgvector") is None`：
  - `test_embedding_vector_exposes_pgvector_distance_operator` 会显式 skip
  - skip 原因会直接说明“当前 Python 环境未安装 pgvector”

## 验证结果

- `python3 -m pytest -q tests/test_database_compatibility.py`
  - `5 passed, 1 skipped`
- `python3 -m ruff check tests/test_database_compatibility.py`
  - 通过
- `python3 -m pytest -q`
  - `108 passed, 7 skipped, 2 warnings`

## 变更文件

- `tests/test_database_compatibility.py`
- `docs/agent-runs/2026-03-16-pgvector-environment-compat.md`
- `TASK_LOG.md`

## 风险与未覆盖项

- 本轮没有验证“安装了 `pgvector` 的当前机器”上的同一条测试路径。
- 当前仓库仍未形成真正的 PostgreSQL + `pgvector` 端到端运行证据。

## 回滚方式

- 回退 `tests/test_database_compatibility.py`
- 删除 `docs/agent-runs/2026-03-16-pgvector-environment-compat.md`
- 回退 `TASK_LOG.md` 本节
