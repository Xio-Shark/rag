# 2026-03-14 报告面板视觉回归

- 任务名称：报告查看 + 报告导航 + 恢复完整报告视觉回归
- 项目类型：B 现有项目新增功能
- 次类型：F 原型 / Demo
- 风险等级：R1
- 目标：补第三张视觉基线，覆盖报告卡片在“已定位 case、可恢复完整报告”状态下的界面
- 约束：
  - 不引入外部视觉回归服务
  - 不改现有 API、数据库和 DOM 契约
  - 继续使用 `pytest + Playwright`
  - 需要屏蔽报告路径、运行时间、运行 ID 等动态字段
- 方案摘要：复用现有视觉回归基础设施，对报告卡片做单卡截图，并在测试中归一化动态文本
- 关键决策：
  - 不做整页截图，只覆盖报告卡片
  - 通过报告导航聚焦到稳定 case，确保“恢复完整报告”按钮处于可用状态
  - 沿用本地基线图策略，不新增外部依赖平台
- 变更文件：
  - `README.md`
  - `tests/test_e2e_visual_regression.py`
  - `tests/baselines/report-panel.png`
- 风险与未覆盖项：
  - 不同 OS / 字体环境下仍可能出现轻微像素差异
  - 这轮只覆盖 Markdown 报告的稳定态，不覆盖 JSON 报告态
- 回滚方式：
  - 删除新增测试和基线图即可

## 验证结果

- `UPDATE_VISUAL_BASELINES=1 python3 -m pytest -q tests/test_e2e_visual_regression.py -k report_panel_visual_regression`：通过并生成基线
- `python3 -m pytest -q tests/test_e2e_visual_regression.py -k report_panel_visual_regression`：通过
- `python3 -m ruff check app tests`：通过
- `python3 -m pytest -q`：`22 passed`
- `python3 -m pytest -q -m e2e`：`8 passed, 14 deselected`
- `python3 -m compileall app tests`：通过
- 轻量敏感词扫描：未发现硬编码密钥；命中项为正常配置字段与按钮 ID
