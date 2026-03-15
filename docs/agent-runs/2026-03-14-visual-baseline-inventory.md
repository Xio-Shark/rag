# 2026-03-14 视觉基线清单

- 任务名称：视觉基线清单文档
- 项目类型：C 成熟项目优化 / 重构
- 次类型：B 现有项目新增功能
- 风险等级：R0
- 目标：补一份视觉基线清单文档，固定正式基线、诊断产物、更新方式和排障路径
- 约束：
  - 不改业务代码与测试逻辑
  - 文档内容必须和现有基线文件、测试函数一一对应
  - 不引入新的工具或额外依赖
- 方案摘要：新增独立文档维护视觉回归资产清单，并在 README 增加入口说明
- 关键决策：
  - 正式基线和失败诊断产物分开记录，避免继续混淆
  - README 只放入口，不把整份清单塞回首页说明
  - 文档直接引用当前测试函数和生成规则，减少后续偏差
- 变更文件：
  - `README.md`
  - `docs/visual-regression-baselines.md`
  - `docs/agent-runs/2026-03-14-visual-baseline-inventory.md`
- 风险与未覆盖项：
  - 当前仍是人工维护清单，未来新增基线时仍需要手动更新文档
  - 不自动校验文档与基线文件是否完全同步
  - 本轮首次全量校验中，`tablet-qa-evidence-workflow` 曾出现一次性视觉抖动；重复执行后未复现，当前先记录为低概率渲染波动
- 回滚方式：
  - 删除新增文档，并回退 README 中对应入口说明

## 验证结果

- `python3 -m ruff check app tests`：通过
- `python3 -m pytest -q`：`28 passed`
- `python3 -m pytest -q -m e2e`：`11 passed, 17 deselected`
- `python3 -m compileall app tests`：通过
- `grep -RIn "sk-\\|api_key" app tests README.md docs`：未发现硬编码密钥；命中项为正常配置字段、鉴权头和按钮 ID
- `python3 -m pytest -q tests/test_e2e_visual_regression.py -k tablet_qa_and_evidence_visual_regression` 连跑 3 次：均通过
