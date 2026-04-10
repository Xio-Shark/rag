# 2026-03-14 视觉差异产物

- 任务名称：视觉回归差异产物
- 项目类型：B 现有项目新增功能
- 次类型：F 原型 / Demo
- 风险等级：R1
- 目标：在视觉回归失败时额外生成 `.diff.png`，降低排查成本
- 约束：
  - 不改业务代码与页面结构
  - 不引入外部视觉回归平台
  - 继续复用现有 `tests/visual_regression.py`
  - 失败产物必须保持本地可清理
- 方案摘要：在现有 `.actual.png` 之外，增加一张高亮差异图，并补单元测试覆盖
- 关键决策：
  - 先补单元测试，不通过 E2E 才验证工具行为
  - 差异图优先强调“哪里变了”，而不是做复杂三栏对比图
  - 失败产物纳入 `.gitignore`
- 变更文件：
  - `.gitignore`
  - `README.md`
  - `tests/visual_regression.py`
  - `tests/test_visual_regression.py`
- 风险与未覆盖项：
  - 差异图只服务诊断，不作为正式基线
  - 当前不做感知式 diff，只做像素级高亮
- 回滚方式：
  - 删除新增单测、工具逻辑和忽略规则即可

## 验证结果

- `python3 -m pytest -q tests/test_visual_regression.py`：通过
- `python3 -m ruff check tests/visual_regression.py tests/test_visual_regression.py`：通过
- `python3 -m ruff check app tests`：通过
- `python3 -m pytest -q`：`26 passed`
- `python3 -m pytest -q -m e2e`：`9 passed, 17 deselected`
- `python3 -m compileall app tests`：通过
- 轻量敏感词扫描：未发现硬编码密钥；命中项为正常配置字段与按钮 ID
