# 2026-03-14 视觉回归报告产物

- 任务名称：视觉回归 E2E JUnit 与摘要文件产物
- 项目类型：C 成熟项目优化 / 重构
- 次类型：B 现有项目新增功能
- 风险等级：R1

## 正式执行前说明

- 目标：
  - 让视觉回归 E2E workflow 生成可下载的 JUnit XML。
  - 在 artifact 中保留失败诊断摘要文件本身，而不只是在 GitHub UI 里显示。
  - 保持现有诊断图上传、job summary 和 PR comment 逻辑继续有效。
- 非目标：
  - 不调整视觉回归测试内容、基线或阈值。
  - 不引入外部测试报告平台。
- 约束：
  - 优先复用现有 workflow，不新增第二条视觉回归 workflow。
  - 先补 workflow 文本断言，再补 workflow 与文档。
  - 上传产物应可在离开 GitHub UI 后继续复用。
- 风险：
  - artifact 上传策略如果处理不好，可能在成功和失败场景下行为不一致。
  - JUnit XML 路径若写死在工作区，可能污染本地目录。
- 验收标准：
  - workflow 用 `--junitxml` 运行 `tests/test_e2e_visual_regression.py`。
  - workflow 会上传 JUnit XML 和失败摘要文件。
  - 相关测试与全量 pytest 通过。
- 当前项目类型：C 成熟项目优化 / 重构
- 当前风险等级：R1
- 仓库现状：
  - 已存在：独立视觉回归 E2E workflow、失败诊断图 artifact、job summary、PR comment
  - 缺失：JUnit XML artifact、失败摘要 markdown artifact
- 缺失机制清单：
  - JUnit XML 上传
  - 失败摘要文件上传
  - 对新增 artifact 行为的测试守卫
- 方案对比：
  - 方案 A：在现有 workflow 中生成 JUnit XML 到临时目录，并新增 artifact 上传 step。复杂度低，推荐。
  - 方案 B：新增专门汇总脚本，再把报告写回仓库目录。侵入性更高，不必要。
  - 方案 C：只保留 job summary / comment，不上传报告文件。不满足复用目标。
- 推荐方案：方案 A。
- 是否需要 ADR：否。
- 测试计划：
  - 先补 workflow 文本断言。
  - 运行 `python3 -m pytest -q tests/test_visual_baseline_manifest.py`
  - 运行 `python3 -m ruff check app tests`
  - 运行 `python3 -m pytest -q`

## 实施记录

- 方案摘要：
  - `visual-regression-e2e.yml` 改为使用 `pytest --junitxml` 生成 JUnit XML 到 runner 临时目录。
  - 新增一条 `if: always()` 的 artifact 上传 step，保留 JUnit XML；失败场景下再额外上传失败摘要 markdown 文件。
  - README、清单文档和渲染模板同步说明这两类可下载产物。
- 关键决策：
  - JUnit XML 选择 `always()` 上传，避免成功构建时丢失结构化测试结果。
  - 失败摘要 markdown 仍然只在失败时上传，避免空文件 artifact。
  - 产物统一写入 runner 临时目录，不污染仓库工作区。
- 变更文件：
  - `.github/workflows/visual-regression-e2e.yml`
  - `tests/test_visual_baseline_manifest.py`
  - `scripts/render_visual_regression_baselines.py`
  - `README.md`
  - `docs/visual-regression-baselines.md`
  - `docs/agent-runs/2026-03-14-visual-regression-report-artifacts.md`
- 风险与未覆盖项：
  - 当前本地无法直接实跑 GitHub artifact 上传，只能通过 workflow 文本断言和全量测试间接验证。
  - JUnit XML 目前只作为 artifact 保存，尚未接入测试报告解析或 PR check 注释。
- 回滚方式：
  - 回退 visual-regression-e2e workflow 中新增的 JUnit / 摘要 artifact 输出与对应测试断言

## 验证结果

- `python3 scripts/render_visual_regression_baselines.py --write`：通过，已重建文档
- `python3 -m pytest -q tests/test_visual_baseline_manifest.py`：通过，`12 passed`
- `python3 -m ruff check app tests`：通过
- `python3 -m pytest -q`：通过，`42 passed`
