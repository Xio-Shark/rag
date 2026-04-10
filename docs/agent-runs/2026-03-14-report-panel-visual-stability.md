# 2026-03-14 报告面板视觉回归稳定化

- 任务名称：桌面报告面板视觉回归稳定化
- 项目类型：C 成熟项目优化 / 重构
- 次类型：B 现有项目新增功能
- 风险等级：R2

## 正式执行前说明

- 目标：
  - 稳定 `test_report_panel_visual_regression`，消除桌面报告面板顶部区域的偶发视觉抖动。
  - 保持现有视觉回归门禁信号强度，不放宽全局 diff 阈值。
  - 通过重复执行单测、`-m e2e` 和全量 pytest 验证收敛效果。
- 非目标：
  - 不重写报告面板业务逻辑。
  - 不新增外部视觉回归平台或第三方快照服务。
  - 不修改全局视觉回归阈值。
- 约束：
  - 优先通过测试归一化和截图范围治理解决问题。
  - 保持 `manifest`、基线清单和现有最小 CI 契约不被削弱。
  - 不改数据库、接口、认证或部署行为。
- 风险：
  - 归一化过度会掩盖真实 UI 回归，削弱报告面板的检出价值。
  - 仅修桌面态时，可能引入平板态基线偏移。
  - 若通过裁剪截图解决，可能遗漏顶部某些真实交互回归。
- 验收标准：
  - `python3 -m pytest -q tests/test_e2e_visual_regression.py -k report_panel_visual_regression` 连续多次通过。
  - `python3 -m pytest -q -m e2e` 通过。
  - `python3 -m pytest -q` 通过。
  - 不需要修改全局 `max_diff_ratio`。
- 当前项目类型：C 成熟项目优化 / 重构
- 当前风险等级：R2
- 仓库现状：
  - 已存在：`README.md`、实施计划文档 `RAG问答质量平台-项目规划.md`、`tests/`、`.github/workflows/visual-baseline-sync.yml`、`.env.example`、任务日志目录 `docs/agent-runs/`、视觉基线清单 `docs/visual-regression-baselines.md`
  - 缺失：独立架构文档、显式迁移机制、统一特性开关机制、集中式回滚手册、明确日志机制说明、当前工作区 `.git/`
  - 本轮必须先补齐的项：本轮任务日志
- 缺失机制清单：
  - 架构文档
  - 迁移机制
  - 特性开关机制
  - 集中式回滚手册
  - 日志机制说明
- 方案对比：
  - 方案 A：继续增强 `_normalize_report_panel`，固定说明文案、按钮文本/尺寸、meta 展示，并在截图前冻结高抖动样式。复杂度低，侵入性低，兼容性最好，维护成本低，回滚简单。
  - 方案 B：缩小截图范围，只覆盖报告导航和正文区域。复杂度低，但会降低顶部交互区的视觉信号，兼容性较好，维护成本中等，回滚简单。
  - 方案 C：仅对报告面板单测放宽阈值。实现最简单，但直接削弱门禁强度，不作为首选。
- 推荐方案：
  - 先执行方案 A。
  - 若仍有稳定噪声，再谨慎叠加方案 B 的局部裁剪。
  - 明确排除方案 C，除非确认剩余差异为稳定且低价值噪声。
- 是否需要 ADR：否。本轮不涉及基础设施、数据库、认证、核心调用链或高风险接口变更。
- 测试计划：
  - 先修改现有视觉回归测试中的归一化逻辑。
  - 单独运行 `python3 -m pytest -q tests/test_e2e_visual_regression.py -k report_panel_visual_regression`
  - 重复运行同一用例验证稳定性。
  - 运行 `python3 -m pytest -q -m e2e`
  - 运行 `python3 -m pytest -q`
- 实施步骤：
  - 阅读报告面板样式、状态写入与当前归一化逻辑，确认抖动来源。
  - 收紧顶部说明文字、下拉框、按钮、meta 区的文本与样式归一化。
  - 必要时调整截图前的 DOM 固定化策略，但避免直接放宽阈值。
  - 运行目标用例、多轮重复验证，再跑 e2e 与全量测试。
  - 回填日志中的关键决策、变更文件、验证结果与风险。

## 实施记录

- 方案摘要：
  - 继续增强 `_normalize_report_panel`，把顶部说明文案替换为固定占位文案。
  - 对运行选择、格式选择、主按钮和 meta 区追加最小高度与行高固定，减少字体渲染与尺寸抖动。
  - 在截图前补一层鼠标移出和双 `requestAnimationFrame`，确保按钮与布局状态静止后再截图。
  - 在 `assert_visual_match(...)` 成功匹配或刷新基线后自动清理同名 `.actual.png` / `.diff.png`，避免遗留失败产物污染工作区认知。
- 关键决策：
  - 不放宽全局 `max_diff_ratio`，也不为报告面板单独加宽阈值。
  - 不缩掉整块顶部区域，仍然保留报告卡片顶部交互区的视觉覆盖。
  - 桌面与平板共用同一套归一化收敛逻辑，避免平台间策略漂移。
- 变更文件：
  - `tests/test_e2e_visual_regression.py`
  - `tests/test_visual_regression.py`
  - `tests/visual_regression.py`
  - `scripts/render_visual_regression_baselines.py`
  - `docs/visual-regression-baselines.md`
  - `README.md`
  - `tests/baselines/report-panel.png`
  - `tests/baselines/tablet-report-panel.png`
  - `docs/agent-runs/2026-03-14-report-panel-visual-stability.md`
- 风险与未覆盖项：
  - 报告卡片顶部说明文案现已被测试侧固定，占位文本本身不再承担视觉回归信号。
  - 自动清理仅覆盖“同名基线”的过期诊断图；历史遗留但本轮未触发的其他诊断图仍需手工清理。
  - 本轮未新增更细粒度的像素级统计，只通过重复跑测验证稳定性。
- 回滚方式：
  - 回退 `tests/test_e2e_visual_regression.py` 中新增的顶部归一化与双帧稳定逻辑。
  - 恢复 `tests/baselines/report-panel.png` 与 `tests/baselines/tablet-report-panel.png` 到修复前版本。

## 验证结果

- `UPDATE_VISUAL_BASELINES=1 python3 -m pytest -q tests/test_e2e_visual_regression.py -k report_panel_visual_regression`：通过，并重建桌面 / 平板报告基线
- `python3 -m pytest -q tests/test_e2e_visual_regression.py -k report_panel_visual_regression`：连续 5 轮通过
- `python3 -m pytest -q -m e2e`：连续 2 轮通过，`11 passed, 22 deselected`
- `python3 -m pytest -q`：通过，`33 passed`
- `python3 -m pytest -q tests/test_visual_baseline_manifest.py`：通过，`5 passed`
- `python3 -m pytest -q tests/test_visual_regression.py`：通过，`5 passed`
- `python3 -m pytest -q tests/test_e2e_visual_regression.py`：通过，`6 passed`
- `python3 -m ruff check app tests`：通过
- `python3 scripts/render_visual_regression_baselines.py --check`：通过
- `python3 -m pytest -q`：最终通过，`35 passed`
- `tests/baselines/`：已自动清理过期诊断产物，当前仅保留正式基线和 `manifest.json`
