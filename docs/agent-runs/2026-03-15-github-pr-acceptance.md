# 2026-03-15 真实 GitHub PR 验收

- 任务名称：补真实 GitHub PR 验收记录
- 项目类型：C 成熟项目优化 / 重构
- 次类型：F 原型 / Demo 的 GitHub 验收增强
- 风险等级：R3

## 目标

- 把本地目录接成真实 GitHub 仓库。
- 建立 `main` 基线并创建最小证据 PR。
- 沉淀 workflow、artifact、comment、run link 验收证据。

## 非目标

- 不伪造 PR 页面或 workflow 结果。
- 不扩大为完整 release pipeline 改造。
- 不在本轮引入新的 GitHub Actions 逻辑，优先复用现有 workflow。

## 约束

- 当前目录开始时不是 git worktree。
- 本机缺少 `gh` CLI，优先用 `git` 和 GitHub 网页/API 完成。
- PR comment 需要同仓库分支，不能依赖 fork PR。

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
  - feature flag
  - release gate
  - 最小 observability
- 缺失：
  - 真实 GitHub PR 页面验收记录
  - 正式 release workflow
- 本轮必须先补齐的项：
  - 一次真实 GitHub PR 验收

## 方案对比

### 方案 A：只建立 main

- 复杂度：低
- 成本：低
- 侵入性：中
- 兼容性：高
- 维护成本：低
- 回滚难度：低
- 问题：没有真实 PR diff，无法证明 reviewer 视角体验。

### 方案 B：先 main，再最小证据 PR

- 复杂度：中
- 成本：中
- 侵入性：中
- 兼容性：高
- 维护成本：低
- 回滚难度：低到中
- 优势：能一次性拿到 workflow、artifact、comment、run link。

## 推荐方案

- 采用方案 B。

## 是否需要 ADR

- 不需要。

## 测试计划

1. 初始化 git 并验证远端联通。
2. 推送 `main` 基线。
3. 创建最小证据分支与 PR。
4. 等待 Actions 完成并采集证据。
5. 回填文档与任务日志。

## 实施记录

- 待回填。

## 关键决策

- 优先复用现有 workflow，不新增一次性 workflow。
- 证据 PR 会包含 `README.md` 最小改动，以稳定触发 PR comment workflow。

## 变更文件

- 待回填。

## 风险与未覆盖项

- 若本机缺少 GitHub 认证，可能需要用户先完成一次登录或提供 PAT。
- 首次导入仓库只能建立基线，不能替代“历史改动当时的原生 PR 记录”。

## 回滚方式

1. 关闭未合并的证据 PR。
2. 删除远端证据分支。
3. 必要时删除仅用于触发验收的最小测试提交。
