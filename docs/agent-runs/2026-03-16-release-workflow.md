# 2026-03-16 Release Workflow 收口

- 任务名称：继续完成未完成部分，补正式 release workflow
- 项目类型：C 成熟项目优化 / 重构
- 次类型：F 原型 / Demo 的发布治理增强
- 风险等级：R3

## 目标

- 把现有 `scripts/release_gate.py` 收口成正式 GitHub Actions workflow。
- 让 release gate 不再只停留在本地脚本，而是具备统一的手动触发入口和执行记录。

## 非目标

- 不直接做真实生产部署。
- 不引入新的外部发布平台或 secret 管理系统。
- 不在本轮完成 PostgreSQL + `pgvector` 的真实环境演练。

## 约束

- 优先复用现有 `scripts/release_gate.py` 与文档口径。
- 不覆盖当前 worktree 中与本轮无关的未提交改动。
- 必须先补测试，再实现 workflow。

## 方案摘要

- 采用手动触发的 GitHub Actions workflow。
- workflow 负责安装依赖、渲染 release plan、按输入执行指定 phase，并上传计划/执行日志。

## 关键决策

- 先补“正式 workflow 入口”，不把本轮扩大为完整生产发布编排。

## 变更文件

- `.github/workflows/release-gate.yml`
- `.github/workflows/mainline-quality-gate.yml`
- `tests/test_release_workflow.py`
- `tests/test_ci_quality_gate.py`
- `README.md`
- `RUNBOOK.md`
- `IMPLEMENTATION_PLAN.md`
- `docs/agent-runs/2026-03-16-release-workflow.md`
- `TASK_LOG.md`

## 风险与未覆盖项

- `release-gate.yml` 本轮新增的是手动触发 workflow，不等于已经完成真实目标环境发布演练。
- `release` / `post-release` 阶段依然依赖目标环境和人工 cutover，不会被本轮 dry-run 自动替代。
- 新增的 `workflow_dispatch` workflow 在合入默认分支前，不能直接通过 `gh workflow run release-gate.yml` 从 PR 分支触发；实测会返回 `404 workflow not found on the default branch`。

## 回滚方式

- 删除 `.github/workflows/release-gate.yml`
- 回退 `.github/workflows/mainline-quality-gate.yml`
- 回退 `tests/test_release_workflow.py`、`tests/test_ci_quality_gate.py`
- 回退 `README.md`、`RUNBOOK.md`、`IMPLEMENTATION_PLAN.md`
- 回退 `TASK_LOG.md` 和本任务文档

## 实现结果

- 新增 `.github/workflows/release-gate.yml`
- 采用 `workflow_dispatch` 手动触发模式，支持输入：
  - `phase=pre-release|release|post-release|all`
  - `execute=true|false`
  - `base_url`
- workflow 会：
  - 安装项目依赖
  - 在 `execute=true` 且阶段包含 `pre-release` 时安装 Chromium
  - 调用 `python3 scripts/release_gate.py` 渲染计划
  - 在 `execute=true` 时执行指定 release gate 阶段
  - 上传 `release-gate-plan` 和可选的 `release-gate-execution-log` artifact
- 同步更新：
  - `README.md`
  - `RUNBOOK.md`
  - `IMPLEMENTATION_PLAN.md`
  - `.github/workflows/mainline-quality-gate.yml`
- 新增测试：
  - `tests/test_release_workflow.py`
  - `tests/test_ci_quality_gate.py` 补 workflow 路径断言

## 验证结果

- `python3 -m pytest -q tests/test_release_workflow.py tests/test_release_gate.py tests/test_ci_quality_gate.py`
  - `8 passed`
- `python3 -m ruff check tests/test_release_workflow.py tests/test_release_gate.py tests/test_ci_quality_gate.py`
  - 通过
- `PYTHONPYCACHEPREFIX=/tmp/pycache python3 -m compileall tests/test_release_workflow.py tests/test_release_gate.py tests/test_ci_quality_gate.py scripts/release_gate.py`
  - 通过
- `python3 -m pytest -q`
  - `110 passed, 7 skipped, 2 warnings`
- `gh workflow run release-gate.yml --ref chore/github-pr-acceptance-evidence -f phase=pre-release -f execute=true`
  - 返回 `404 workflow not found on the default branch`
  - 结论：GitHub 要求新的 `workflow_dispatch` workflow 先进入默认分支后才能直接手动触发
- 基于提交 `27d2fe7 Add manual release gate workflow` 的 PR checks：
  - `mainline-quality-gate`：通过
  - `schema-migration-guard`：通过
  - `verify-visual-baseline-sync`：通过
  - `visual-regression-e2e`：通过
