# 2026-03-14 问答与证据视觉回归

- 任务名称：问答工作流 + 证据浏览视觉回归
- 项目类型：B 现有项目新增功能
- 次类型：F 原型 / Demo
- 风险等级：R1
- 目标：补第二张视觉基线，覆盖“提问 -> 审计 -> 证据片段 -> 文档浏览”主链路
- 约束：
  - 不引入外部视觉回归服务
  - 不改现有 API、数据库和 DOM 契约
  - 继续使用 `pytest + Playwright`
  - 需要屏蔽审计 ID、绝对路径、延迟等动态字段
- 方案摘要：复用现有视觉回归基础设施，对“问答工作流”关键卡片和“证据浏览”区域做组合截图，并提供基线更新能力
- 关键决策：
  - 不做整页截图，只覆盖真正承载主链路的卡片
  - 通过测试辅助逻辑隐藏无关卡片、归一化动态文本，降低基线抖动
  - 沿用本地基线图策略，不新增外部依赖平台
- 变更文件：
  - `README.md`
  - `tests/visual_regression.py`
  - `tests/test_e2e_visual_regression.py`
  - `tests/baselines/qa-evidence-workflow.png`
- 风险与未覆盖项：
  - 不同 OS / 字体环境下仍可能出现轻微像素差异
  - 这轮只覆盖主链路的稳定态，不覆盖拒答态和历史问答列表态
- 回滚方式：
  - 删除新增测试、辅助函数和基线图即可

## 验证结果

- `python3 -m pytest -q tests/test_e2e_visual_regression.py -k qa_and_evidence_visual_regression`：通过
- `python3 -m pytest -q tests/test_e2e_visual_regression.py`：通过
- `python3 -m ruff check app tests`：通过
- `python3 -m pytest -q`：`21 passed`
- `python3 -m pytest -q -m e2e`：`7 passed, 14 deselected`
- `python3 -m compileall app tests`：通过
- 轻量敏感词扫描：未发现硬编码密钥；命中项为正常配置字段与按钮 ID
