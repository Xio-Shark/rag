# 2026-03-14 视觉诊断产物门禁

- 任务名称：视觉诊断产物残留门禁
- 项目类型：C 成熟项目优化 / 重构
- 次类型：B 现有项目新增功能
- 风险等级：R1

## 正式执行前说明

- 目标：
  - 把 `tests/baselines/` 目录下不应残留 `.actual.png` / `.diff.png` 变成显式可校验规则。
  - 让视觉回归工具层、manifest 测试和最小 CI 形成一致约束。
- 非目标：
  - 不新增全量 E2E 到 GitHub Actions。
  - 不改正式基线数量、命名或覆盖范围。
- 约束：
  - 继续复用现有 `tests/test_visual_baseline_manifest.py` 与 `visual-baseline-sync.yml`。
  - 先补测试和 workflow 约束，再补实现或文档。
- 风险：
  - 若开发者本地刚跑出失败诊断图但未清理，新的门禁会直接失败。
  - workflow 路径触发范围扩大后，相关文件修改会更频繁触发 GitHub Actions。
- 验收标准：
  - manifest 测试能直接断言当前工作区没有残留诊断产物。
  - workflow 会在相关工具文件变化时触发该门禁。
  - `python3 -m pytest -q` 与门禁相关测试通过。
- 当前项目类型：C 成熟项目优化 / 重构
- 当前风险等级：R1
- 仓库现状：
  - 已存在：`tests/baselines/manifest.json`、`tests/test_visual_baseline_manifest.py`、`tests/visual_regression.py`、`.github/workflows/visual-baseline-sync.yml`
  - 缺失：对残留诊断产物的显式测试守卫、对工具层文件变更的 workflow 触发覆盖
- 方案对比：
  - 方案 A：在 manifest 测试里增加“无残留诊断产物”断言，并扩展 workflow 路径触发。复杂度低，侵入性低，推荐。
  - 方案 B：单独新增脚本检查残留产物，再让 workflow 调脚本。更灵活，但维护面更大。
  - 方案 C：只在 README / 文档写约定，不做机器校验。不满足门禁目标。
- 推荐方案：方案 A。
- 是否需要 ADR：否。
- 测试计划：
  - 先补 manifest 测试与 workflow 断言。
  - 运行 `python3 -m pytest -q tests/test_visual_baseline_manifest.py`
  - 运行 `python3 -m ruff check app tests`
  - 运行 `python3 -m pytest -q`

## 实施记录

- 方案摘要：
  - 在 `tests/test_visual_baseline_manifest.py` 中新增“当前工作区无 `.actual.png` / `.diff.png` 残留”的断言。
  - 扩大 `.github/workflows/visual-baseline-sync.yml` 的路径触发范围，把 `tests/visual_regression.py`、`tests/test_visual_regression.py`、`tests/test_e2e_visual_regression.py` 纳入。
  - 同步 README、清单文档和渲染脚本说明，明确这条门禁已变成机器校验。
- 关键决策：
  - 不新增独立脚本，继续复用 manifest 测试作为最小守卫承载点。
  - 不把清理命令塞进 workflow，而是让 workflow 只做失败暴露，不做隐式修复。
  - 触发范围覆盖工具层与 E2E 入口文件，避免改了视觉回归基础设施却不触发同步门禁。
- 变更文件：
  - `tests/test_visual_baseline_manifest.py`
  - `.github/workflows/visual-baseline-sync.yml`
  - `README.md`
  - `docs/visual-regression-baselines.md`
  - `scripts/render_visual_regression_baselines.py`
  - `docs/agent-runs/2026-03-14-visual-diagnostic-artifact-gate.md`
- 风险与未覆盖项：
  - 这条门禁只覆盖 `tests/baselines/` 目录，不扫描其他潜在临时输出目录。
  - 开发者本地若刻意保留失败诊断图做比对，新的 manifest 测试会直接失败，需要先挪走或清理。
- 回滚方式：
  - 回退 manifest 测试中新增的残留产物守卫与 workflow 路径扩展

## 验证结果

- `python3 -m pytest -q tests/test_visual_baseline_manifest.py`：通过，`6 passed`
- `python3 scripts/render_visual_regression_baselines.py --check`：通过
- `python3 -m ruff check app tests`：通过
- `python3 -m pytest -q`：通过，`36 passed`
