# 2026-03-14 视觉基线文档渲染器

- 任务名称：视觉基线 Markdown 渲染器
- 项目类型：C 成熟项目优化 / 重构
- 次类型：B 现有项目新增功能
- 风险等级：R1
- 目标：补一个从 manifest 自动生成视觉基线清单 Markdown 的脚本，减少手工同步
- 约束：
  - 不改业务代码与视觉回归逻辑
  - 先补测试，再补脚本
  - manifest 继续作为正式基线唯一事实源
  - 脚本输出需要和当前文档结构保持一致
- 方案摘要：新增渲染脚本，根据 `tests/baselines/manifest.json` 输出 `docs/visual-regression-baselines.md`，并用单测校验渲染结果
- 关键决策：
  - 不做复杂 CLI，只保留 `--stdout` / `--write` / `--check`
  - 先以当前 Markdown 结构为模板，避免无意义格式变动
  - 继续把诊断产物与正式基线分开渲染
- 变更文件：
  - `README.md`
  - `docs/visual-regression-baselines.md`
  - `scripts/render_visual_regression_baselines.py`
  - `tests/test_visual_baseline_manifest.py`
  - `docs/agent-runs/2026-03-14-visual-baseline-doc-renderer.md`
- 风险与未覆盖项：
  - 当前仍需手动执行脚本，不是自动生成
  - 若后续想改文档版式，需要同步调整测试期望
  - 如果未来要把整个 `scripts/` 目录都纳入 `ruff`，当前 `scripts/export_resume_pdfs.py` 还存在一条既有导入排序问题，本轮未处理
- 回滚方式：
  - 删除新增脚本和测试扩展，并回退 README / 文档中对应说明

## 验证结果

- `python3 -m pytest -q tests/test_visual_baseline_manifest.py`：`4 passed`
- `python3 scripts/render_visual_regression_baselines.py --check`：通过
- `python3 -m ruff check app tests`：通过
- `python3 -m ruff check scripts/render_visual_regression_baselines.py`：通过
- `python3 -m pytest -q`：`32 passed`
- `python3 -m pytest -q -m e2e`：`11 passed, 21 deselected`
- `python3 -m compileall app tests scripts`：通过
- `grep -RIn "sk-\\|api_key" app tests scripts README.md docs`：未发现硬编码密钥；命中项为正常配置字段、鉴权头和按钮 ID
