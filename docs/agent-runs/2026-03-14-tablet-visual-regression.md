# 2026-03-14 平板视觉回归

- 任务名称：平板视口视觉回归
- 项目类型：C 成熟项目优化 / 重构
- 次类型：B 现有项目新增功能
- 风险等级：R2
- 目标：补一条平板视口视觉基线，覆盖中等宽度下的关键响应式布局
- 约束：
  - 不引入外部视觉回归服务
  - 不改现有 API、数据库和 DOM 契约
  - 继续使用 `pytest + Playwright`
  - 继续屏蔽运行 ID、路径、时间等动态字段
- 方案摘要：复用现有“问答工作流 + 证据浏览”准备与归一化逻辑，在平板视口下追加一条独立视觉基线
- 关键决策：
  - 优先覆盖信息密度更高的“问答工作流 + 证据浏览”，而不是重复实验中心
  - 通过独立平板浏览器夹具控制视口，避免影响桌面和移动端测试
  - 沿用现有拼接截图方式，减少新增辅助逻辑
- 变更文件：
  - `README.md`
  - `tests/test_e2e_visual_regression.py`
  - `tests/baselines/tablet-qa-evidence-workflow.png`
  - `docs/agent-runs/2026-03-14-tablet-visual-regression.md`
- 风险与未覆盖项：
  - 当前只覆盖一个平板尺寸，不覆盖横屏和平板报告视图
  - 不验证长页面滚动中的懒加载或未来动画效果
- 回滚方式：
  - 删除新增平板测试和基线图，并回退 README 对应说明

## 验证结果

- `UPDATE_VISUAL_BASELINES=1 python3 -m pytest -q tests/test_e2e_visual_regression.py -k tablet_qa_and_evidence_visual_regression`：通过并生成基线
- `python3 -m pytest -q tests/test_e2e_visual_regression.py -k tablet_qa_and_evidence_visual_regression`：通过
- `python3 -m ruff check app tests`：通过
- `python3 -m pytest -q`：`27 passed`
- `python3 -m pytest -q -m e2e`：`10 passed, 17 deselected`
- `python3 -m compileall app tests`：通过
- 轻量敏感词扫描：未发现硬编码密钥；命中项为正常配置字段、鉴权头和按钮 ID
