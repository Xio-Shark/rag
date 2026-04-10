# 2026-03-14 视觉基线轻量质量门禁

- 任务名称：视觉基线轻量质量门禁
- 项目类型：C 成熟项目优化 / 重构
- 次类型：B 现有项目新增功能
- 风险等级：R1
- 目标：把 `ruff check app tests` 纳入最小 GitHub Actions，并继续压实视觉基线同步门禁
- 约束：
  - 不改业务代码与接口契约
  - 先补测试，再补 workflow
  - 继续保持最小门禁，不把全量 E2E 纳入这个 workflow
  - 当前目录不是 git 仓库，只能做仓库级 CI 文件，不做本地 git hook
- 方案摘要：扩展现有 `visual-baseline-sync.yml`，在 manifest / 文档同步检查之外再加一条 `ruff check app tests`
- 关键决策：
  - 只纳入 `app tests`，不把整个 `scripts/` 目录带进 workflow，避免被既有脚本 lint 问题拖住
  - 本轮出现的报告面板视觉抖动先在测试归一化层修复，不把锅转给 CI
  - workflow 文本继续由测试约束，避免 CI 文件和本地事实脱节
- 变更文件：
  - `README.md`
  - `.github/workflows/visual-baseline-sync.yml`
  - `tests/test_visual_baseline_manifest.py`
  - `tests/test_e2e_visual_regression.py`
  - `tests/baselines/report-panel.png`
  - `tests/baselines/tablet-report-panel.png`
  - `docs/agent-runs/2026-03-14-visual-baseline-quality-gate.md`
- 风险与未覆盖项：
  - workflow 仍然只会在 GitHub 上实际生效
  - 当前仍未把 `scripts/` 全目录纳入 lint
  - 视觉回归仍可能有低概率渲染波动，但报告面板这次已做定向收敛
  - 停止条件已触发：`test_report_panel_visual_regression` 在最终 `pytest -m e2e` 中再次出现视觉回归失败
- 回滚方式：
  - 回退 workflow 中新增的 lint 步骤与对应测试断言；若需要，一并回退报告面板归一化修复和两张基线

## 验证结果

- `python3 -m pytest -q tests/test_visual_baseline_manifest.py`：`5 passed`
- `python3 scripts/render_visual_regression_baselines.py --check`：通过
- `python3 -m ruff check app tests`：通过
- `python3 -m ruff check scripts/render_visual_regression_baselines.py`：通过
- `python3 -m pytest -q`：`33 passed`
- `python3 -m pytest -q -m e2e`：失败，`test_report_panel_visual_regression` 命中视觉回归差异
- `python3 -m compileall app tests scripts`：通过
- `grep -RIn "sk-\\|api_key" app tests scripts README.md docs`：未发现硬编码密钥；命中项为正常配置字段、鉴权头和按钮 ID

## 当前 bug

- 用例：`tests/test_e2e_visual_regression.py::test_report_panel_visual_regression`
- 表现：视觉回归差异超阈值，`ratio=0.5655%`，超过 `max=0.2000%`
- 产物：
  - `tests/baselines/report-panel.actual.png`
  - `tests/baselines/report-panel.diff.png`
- 观察：差异主要集中在报告面板顶部说明文字和“读取报告正文”按钮区域，属于桌面报告面板归一化仍未完全稳定
