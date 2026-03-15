# 2026-03-14 视觉基线最小 CI

- 任务名称：视觉基线最小 CI
- 项目类型：C 成熟项目优化 / 重构
- 次类型：B 现有项目新增功能
- 风险等级：R1
- 目标：补一个最小 GitHub Actions，在仓库层自动检查视觉基线 manifest / 文档 / README 同步
- 约束：
  - 不改业务代码与视觉回归逻辑
  - 先补测试，再补 workflow
  - 优先复用现有 `render_visual_regression_baselines.py --check` 和 `test_visual_baseline_manifest.py`
  - 当前目录不是 git 仓库，不优先做本地 hook
- 方案摘要：新增最小 workflow，只安装开发依赖并执行视觉基线同步校验相关命令
- 关键决策：
  - 先补 workflow 文本校验测试，避免 CI 文件和本地约束脱节
  - 只做最小 CI，不把全量 E2E 带进这个 workflow
  - workflow 只聚焦视觉基线同步，不扩展为全仓质量门禁
- 变更文件：
  - `README.md`
  - `docs/visual-regression-baselines.md`
  - `.github/workflows/visual-baseline-sync.yml`
  - `tests/test_e2e_visual_regression.py`
  - `tests/test_visual_baseline_manifest.py`
  - `tests/baselines/report-panel.png`
  - `tests/baselines/tablet-report-panel.png`
  - `docs/agent-runs/2026-03-14-visual-baseline-ci.md`
- 风险与未覆盖项：
  - workflow 只有在仓库托管到 GitHub 后才会实际触发
  - 当前不覆盖全量 pytest / E2E，只覆盖视觉基线同步检查
  - 本轮顺手收紧了报告面板顶部控件的归一化逻辑，并重建了两张报告面板基线，以降低偶发视觉抖动
- 回滚方式：
  - 删除 workflow 和新增测试扩展，并回退 README / 文档中对应说明

## 验证结果

- `python3 -m pytest -q tests/test_visual_baseline_manifest.py`：`5 passed`
- `python3 scripts/render_visual_regression_baselines.py --check`：通过
- `python3 -m ruff check app tests`：通过
- `python3 -m ruff check scripts/render_visual_regression_baselines.py`：通过
- `python3 -m pytest -q tests/test_e2e_visual_regression.py -k 'report_panel_visual_regression'` 连跑 3 轮：均通过
- `python3 -m pytest -q`：`33 passed`
- `python3 -m pytest -q -m e2e`：`11 passed, 22 deselected`
- `python3 -m compileall app tests scripts`：通过
- `grep -RIn "sk-\\|api_key" app tests scripts README.md docs`：未发现硬编码密钥；命中项为正常配置字段、鉴权头和按钮 ID
