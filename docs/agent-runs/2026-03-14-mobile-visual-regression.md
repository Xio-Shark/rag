# 2026-03-14 移动端视觉回归

- 任务名称：移动端 / 窄屏实验中心视觉回归
- 项目类型：B 现有项目新增功能
- 次类型：F 原型 / Demo
- 风险等级：R1
- 目标：补一条移动端 / 窄屏视觉基线，覆盖实验中心在小视口下的关键布局
- 约束：
  - 不引入外部视觉回归服务
  - 不改现有 API、数据库和 DOM 契约
  - 继续使用 `pytest + Playwright`
  - 需要屏蔽报告路径、运行时间、运行 ID 等动态字段
- 方案摘要：复用现有实验中心准备与归一化逻辑，在移动视口下单独截取实验中心区域生成基线
- 关键决策：
  - 不做整页移动端截图，只覆盖最复杂的实验中心
  - 沿用已有实验中心归一化逻辑，避免重复维护
  - 通过独立浏览器夹具控制窄屏视口，不影响现有桌面测试
- 变更文件：
  - `README.md`
  - `tests/test_e2e_visual_regression.py`
  - `tests/baselines/mobile-experiment-center.png`
- 风险与未覆盖项：
  - 这轮只覆盖一个移动视口尺寸，不覆盖平板与横屏
  - 不验证移动端下完整长页面滚动体验
- 回滚方式：
  - 删除新增测试和基线图即可

## 验证结果

- `UPDATE_VISUAL_BASELINES=1 python3 -m pytest -q tests/test_e2e_visual_regression.py -k mobile_experiment_center_visual_regression`：通过并生成基线
- `python3 -m pytest -q tests/test_e2e_visual_regression.py -k mobile_experiment_center_visual_regression`：通过
- `python3 -m ruff check app tests`：通过
- `python3 -m pytest -q`：`23 passed`
- `python3 -m pytest -q -m e2e`：`9 passed, 14 deselected`
- `python3 -m compileall app tests`：通过
- 轻量敏感词扫描：未发现硬编码密钥；命中项为正常配置字段与按钮 ID
