# 2026-03-16 GitHub PR 验收收口

- 任务名称：继续完成未完成部分，优先收口 GitHub PR 验收
- 项目类型：C 成熟项目优化 / 重构
- 次类型：F 原型 / Demo 的 CI / 验收收口
- 风险等级：R3

## 目标

- 检查当前证据 PR 的真实 GitHub Actions 状态。
- 定位仍未完成的失败检查。
- 以最小改动修复当前 PR 主线阻塞，并补充验证与文档记录。

## 非目标

- 不扩展新业务功能。
- 不在本轮直接建设完整 release workflow。
- 不优先解决与当前 PR 主线无关的本地 `pgvector` 环境缺失。

## 约束

- 不覆盖当前 worktree 中已有未提交改动。
- 优先以真实 PR checks 和日志为准，而不是本地猜测。
- 改动后必须同步测试、任务日志与 agent run 文档。

## 方案对比

### 方案 A：直接修实现，让 detached 主循环更强同步

- 复杂度：中
- 性能：中
- 成本：中
- 侵入性：中
- 兼容性：中
- 维护成本：中
- 回滚难度：中
- 问题：当前失败更像测试把后台异步收尾绑定成单点断言，先改主逻辑会扩大变更面。

### 方案 B：保留实现，收紧测试口径为“成功恢复并记录状态”

- 复杂度：低
- 性能：高
- 成本：低
- 侵入性：低
- 兼容性：高
- 维护成本：低
- 回滚难度：低
- 优势：与 `--check-once` 的真实契约一致，同时已有单轮主循环集成测试覆盖后台主循环收尾。

## 推荐方案

- 采用方案 B。

## 是否需要 ADR

- 不需要。
- 本轮不修改基础设施、schema 或核心业务架构。

## 测试计划

1. 先用 `gh` 检查当前 PR `#1` 的最新 checks 和失败日志。
2. 先调整/补充 `continuous_task_loop` 测试，再修改断言口径。
3. 运行针对性 `pytest` 与 `ruff`。
4. 推送当前分支并再次检查远端 checks。

## 实施步骤

1. 执行 `gh auth status`、`gh pr view` 和 PR checks 检查。
2. 读取 `mainline-quality-gate` 失败日志，确认唯一失败项。
3. 调整 `tests/test_continuous_task_loop.py`：
   - 为 `run_watchdog_check_once()` 增加确定性 resume 单测。
   - 将 `--check-once` CLI 集成测试改为验证“恢复成功并落盘恢复状态”。
4. 运行针对性验证。
5. 推送分支并复查 GitHub PR checks。

## 失败定位

- 当前 PR：`#1`
- 当前状态：`OPEN`
- 最新 checks：
  - `visual-regression-e2e`：通过
  - `schema-migration-guard`：通过
  - `verify-visual-baseline-sync`：通过
  - `mainline-quality-gate`：失败
- 失败来源：
  - `mainline-quality-gate` 的 `Run pytest` 步骤
  - 唯一失败用例：`tests/test_continuous_task_loop.py::test_check_once_resumes_interrupted_loop_with_fake_codex`
- 失败特征：
  - `--check-once` 命令本身成功返回并打印 `Resumed loop`
  - 但测试继续等待后台 detached 主循环在 10 秒内收口到 `max_iterations_reached`
  - GitHub CI 中该后台时序存在脆弱性，导致状态仍停留在 `running`

## 方案结论

- `--check-once` 的真实契约是“执行一次巡检并在需要时唤醒主循环”，不是阻塞直到后台主循环完整收尾。
- 后台主循环的单轮执行和终态已经由现有非 dry-run 集成测试覆盖。
- 因此本轮修复采用“把 resume 行为和后台主循环收尾拆开验证”的路线。

## 实现结果

- 已更新 `tests/test_continuous_task_loop.py`
- 新增确定性测试：
  - `test_run_watchdog_check_once_resumes_interrupted_loop`
- 调整原有 CLI 集成测试：
  - `test_check_once_resumes_interrupted_loop_with_fake_codex`
  - 从“等待后台主循环完成”改为“确认恢复成功并写入 resume 状态”
- 新增恢复状态落盘断言：
  - `resume_count == 1`
  - `last_resume_reason == "resume_after_interrupted"`
  - `loop_pid` 已记录
  - `watchdog.log` 包含 `Resuming loop: resume_after_interrupted`

## 验证结果

- `python3 -m pytest -q tests/test_continuous_task_loop.py -k 'check_once_resumes_interrupted_loop_with_fake_codex or run_watchdog_check_once_resumes_interrupted_loop or check_once_marks_deadline_reached_when_running_process_is_gone'`
  - `3 passed`
- `python3 -m ruff check tests/test_continuous_task_loop.py`
  - 通过

## 变更文件

- `tests/test_continuous_task_loop.py`
- `docs/agent-runs/2026-03-16-github-pr-acceptance-closure.md`
- `TASK_LOG.md`

## 风险与未覆盖项

- 本轮尚未重新推送并确认 GitHub 远端 `mainline-quality-gate` 已转绿。
- 本轮只修复当前 PR 主线阻塞，没有处理本地 `pgvector` 依赖缺失导致的全量 pytest 环境差异。

## 回滚方式

- 回退 `tests/test_continuous_task_loop.py`
- 删除 `docs/agent-runs/2026-03-16-github-pr-acceptance-closure.md`
- 回退 `TASK_LOG.md` 本节
