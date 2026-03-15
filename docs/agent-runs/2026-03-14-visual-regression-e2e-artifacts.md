# 2026-03-14 视觉回归 E2E 诊断产物

- 任务名称：视觉回归 E2E 工作流与失败诊断产物上传
- 项目类型：C 成熟项目优化 / 重构
- 次类型：B 现有项目新增功能
- 风险等级：R2

## 正式执行前说明

- 目标：
  - 增加一条独立的 GitHub Actions workflow，运行 `tests/test_e2e_visual_regression.py`。
  - 当视觉回归失败时，自动上传 `.actual.png` 和 `.diff.png` 诊断产物，便于在 CI 中排障。
  - 保持现有轻量 sync workflow 不被重型浏览器测试拖慢。
- 非目标：
  - 不把全量 `-m e2e` 纳入这条 workflow。
  - 不修改视觉回归基线内容、阈值或 manifest 结构。
  - 不引入外部视觉回归 SaaS。
- 约束：
  - 优先新增独立 workflow，而不是继续膨胀 `visual-baseline-sync.yml`。
  - 先补 workflow 文本断言，再补 workflow 文件本身。
  - 需要覆盖 Playwright 浏览器安装与失败 artifact 上传。
- 风险：
  - 浏览器依赖和 Linux 环境差异可能让 GitHub Actions 首次运行比本地更脆弱。
  - 新增 workflow 会提高相关 PR 的 CI 成本和耗时。
  - 如果失败时没有生成诊断图，artifact step 可能上传空集，需要显式处理。
- 验收标准：
  - 仓库存在独立的视觉回归 E2E workflow。
  - workflow 会安装 Chromium 并运行 `python -m pytest -q tests/test_e2e_visual_regression.py`。
  - 失败时会上传 `tests/baselines/*.actual.png` / `*.diff.png`。
  - 相关测试与本地视觉回归测试通过。
- 当前项目类型：C 成熟项目优化 / 重构
- 当前风险等级：R2
- 仓库现状：
  - 已存在：`tests/test_e2e_visual_regression.py`、`tests/visual_regression.py`、`.github/workflows/visual-baseline-sync.yml`
  - 缺失：独立的视觉回归 E2E CI workflow、失败诊断产物 artifact 上传
- 缺失机制清单：
  - 视觉回归 E2E 独立 CI
  - 失败产物自动上传
  - 对新 workflow 的文本守卫测试
- 方案对比：
  - 方案 A：新增独立 `visual-regression-e2e.yml`，只跑视觉回归测试并在失败时上传诊断图。复杂度中等，隔离性最好，推荐。
  - 方案 B：把视觉回归 E2E 直接塞进现有 `visual-baseline-sync.yml`。实现简单，但会拖慢轻量门禁，侵入性高。
  - 方案 C：不跑 CI，只在文档中要求本地执行。成本最低，但不满足门禁目标。
- 推荐方案：方案 A。
- 是否需要 ADR：否。本轮不涉及基础设施依赖变更，只是新增仓库级 CI workflow。
- 测试计划：
  - 先新增 workflow 文本断言测试。
  - 运行 `python3 -m pytest -q tests/test_visual_baseline_manifest.py`
  - 运行 `python3 -m ruff check app tests`
  - 运行 `python3 -m pytest -q tests/test_e2e_visual_regression.py`
  - 运行 `python3 -m pytest -q`

## 实施记录

- 方案摘要：
  - 新增独立 workflow `.github/workflows/visual-regression-e2e.yml`，按相关文件路径触发视觉回归 E2E。
  - workflow 安装 Python 依赖和 Chromium，然后执行 `python -m pytest -q tests/test_e2e_visual_regression.py`。
  - 当测试失败时，自动上传 `tests/baselines/*.actual.png` 与 `*.diff.png` 作为诊断 artifact。
- 关键决策：
  - 重型浏览器测试不并入 `visual-baseline-sync.yml`，避免拖慢轻量门禁。
  - artifact 只在失败时上传，并对“无文件可传”使用 `if-no-files-found: ignore`。
  - sync workflow 的触发路径也补上了 `.github/workflows/visual-regression-e2e.yml`，避免新 workflow 变更缺少轻量守卫。
- 变更文件：
  - `.github/workflows/visual-regression-e2e.yml`
  - `.github/workflows/visual-baseline-sync.yml`
  - `tests/test_visual_baseline_manifest.py`
  - `scripts/render_visual_regression_baselines.py`
  - `README.md`
  - `docs/visual-regression-baselines.md`
  - `docs/agent-runs/2026-03-14-visual-regression-e2e-artifacts.md`
- 风险与未覆盖项：
  - 当前本地无法直接实跑 GitHub Actions 的浏览器安装与 artifact 上传，只能通过 workflow 文本断言和本地测试命令间接验证。
  - 本轮验证过程中，`test_mobile_experiment_center_visual_regression` 曾出现一次低频抖动；单测重跑后恢复通过，未在本轮代码范围内定位到新根因。
- 回滚方式：
  - 删除新增 workflow 和对应测试断言，恢复到仅保留轻量 sync workflow 的状态

## 验证结果

- `python3 scripts/render_visual_regression_baselines.py --write`：通过，已重建文档
- `python3 -m pytest -q tests/test_visual_baseline_manifest.py`：通过，`9 passed`
- `python3 -m ruff check app tests`：通过
- `python3 -m pytest -q tests/test_e2e_visual_regression.py`：通过，`6 passed`
- `python3 -m pytest -q`：最终通过，`42 passed`
