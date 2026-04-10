# 2026-03-14 视觉基线 Manifest

- 任务名称：视觉基线 manifest 自动校验
- 项目类型：C 成熟项目优化 / 重构
- 次类型：B 现有项目新增功能
- 风险等级：R1
- 目标：补一个可机器校验的视觉基线 manifest，并用测试约束 README / 清单文档同步
- 约束：
  - 不改业务代码与视觉回归逻辑
  - 先补测试，再补 manifest
  - manifest 只覆盖正式基线，不纳入 `.actual.png` / `.diff.png`
  - 继续使用现有 `pytest` 验证链路
- 方案摘要：新增 `tests/baselines/manifest.json` 作为正式基线事实源，再用单测校验 manifest、README 和清单文档是否一致
- 关键决策：
  - 正式基线以 `tests/baselines/*.png` 且排除 `.actual/.diff` 为准
  - README 里的基线数量改成阿拉伯数字，便于自动检查
  - 自动校验只约束最重要的一致性，不做复杂 Markdown 结构解析
- 变更文件：
  - `README.md`
  - `docs/visual-regression-baselines.md`
  - `tests/baselines/manifest.json`
  - `tests/test_visual_baseline_manifest.py`
  - `docs/agent-runs/2026-03-14-visual-baseline-manifest.md`
- 风险与未覆盖项：
  - 当前仍未自动清理历史诊断产物
  - 如果后续新增基线但忘记更新 manifest，测试会直接失败
- 回滚方式：
  - 删除 manifest 和新增测试，并回退 README / 文档中相关说明

## 验证结果

- `python3 -m pytest -q tests/test_visual_baseline_manifest.py`：通过
- `python3 -m pytest -q tests/test_visual_regression.py`：通过
- `python3 -m ruff check app tests`：通过
- `python3 -m pytest -q`：`30 passed`
- `python3 -m pytest -q -m e2e`：`11 passed, 19 deselected`
- `python3 -m compileall app tests`：通过
- `grep -RIn "sk-\\|api_key" app tests README.md docs`：未发现硬编码密钥；命中项为正常配置字段、鉴权头和按钮 ID
