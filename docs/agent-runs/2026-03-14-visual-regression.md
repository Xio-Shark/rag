# 2026-03-14 视觉回归测试

- 任务名称：视觉回归测试
- 项目类型：B 现有项目新增功能
- 次类型：F 原型 / Demo
- 风险等级：R1
- 目标：为前端工作台补一条稳定的浏览器级视觉回归基线，覆盖核心演示界面
- 约束：
  - 不引入外部视觉回归服务
  - 不改现有 API、数据库和 DOM 契约
  - 继续使用 `pytest + Playwright`
  - 需要规避动态时间戳、UUID 等导致的截图抖动
- 方案摘要：在现有 E2E 基础上增加截图基线测试，并提供显式的基线更新开关
- 关键决策：
  - 采用本地基线图，不接外部平台
  - 通过前端测试辅助逻辑屏蔽动态字段，提升截图稳定性
  - 只覆盖最核心的工作台视图，不追求全站首轮全量覆盖
- 变更文件：
  - `pyproject.toml`
  - `.gitignore`
  - `README.md`
  - `tests/visual_regression.py`
  - `tests/test_e2e_visual_regression.py`
  - `tests/baselines/experiment-center.png`
- 风险与未覆盖项：
  - 不同 OS/字体环境下仍可能出现像素差异
  - 首轮只覆盖核心界面，不覆盖全部卡片状态
- 回滚方式：
  - 删除新增视觉回归测试和基线文件即可

## 验证结果

- `UPDATE_VISUAL_BASELINES=1 python3 -m pytest -q tests/test_e2e_visual_regression.py`：通过并生成基线
- `python3 -m pytest -q tests/test_e2e_visual_regression.py`：通过
