# 2026-03-15 循环守护唤醒

- 任务名称：循环守护唤醒
- 项目类型：B 现有项目新增功能
- 次类型：C 成熟项目工具化增强
- 风险等级：R2

## 正式执行前说明

- 目标：
  - 为 `scripts/continuous_task_loop.py` 增加“定时检查 + 自动唤醒”机制。
  - 在主循环因为额度、网络或人工中断而停止后，只要任务未完成且当前没有运行中的 loop 进程，就能自动恢复。
  - 支持两种使用方式：
    - 常驻守护：每隔 30 分钟或 1 小时检查一次
    - 单次巡检：适合 cron / launchd 定时调用
- 非目标：
  - 不改业务 API、数据库、前端主链路。
  - 不引入外部调度平台、消息队列或守护进程依赖。
  - 不保证跨机器/跨用户的多实例协调。
- 约束：
  - 继续保持 Python 标准库实现。
  - 必须兼容现有 `output/agent-loop/state.json` 状态文件。
  - 自动唤醒只应针对“未完成但当前没在跑”的情况，不能误拉起重复 loop。
- 风险：
  - 如果进程存活判断不准，可能重复拉起多个 loop 实例。
  - 如果把 `blocked`、`completed` 这类终态也当成可恢复状态，会造成错误重试。
  - 如果恢复前不重置失败计数或中断态，可能一拉起就立即再次退出。
- 验收标准：
  - 新增 supervisor/check-once 能力。
  - 能根据状态文件与进程存活情况判断是否需要自动唤醒。
  - 能在恢复前重置合适的运行态字段，并继续复用同一 `state-dir`。
  - 补齐针对性测试、文档和任务日志。
- 当前项目类型：
  - 主类型：B 现有项目新增功能
  - 次类型：C 成熟项目工具化增强
- 当前风险等级：
  - R2：涉及主循环控制逻辑、状态文件语义和自动唤醒边界。
- 仓库现状：
  - 已存在：连续循环脚本、`state.json`、`active_iteration*` 进行中状态、非 dry-run 集成测试、handoff 文档。
  - 缺失：周期性巡检、自动唤醒、loop PID 语义、可恢复状态判断。
  - 本轮必须先补齐的项：方案对比、测试计划、恢复边界定义。
- 缺失机制清单：
  - 主循环进程存活判断
  - 单次巡检 / 常驻守护模式
  - 自动唤醒前的状态重置策略
  - 面向“额度暂停后恢复”的使用文档
- 方案对比：
  - 方案 A：单独新增一个 supervisor 脚本。优点是职责分离。缺点是状态协议分散，复用成本高，文档和测试面更大。
  - 方案 B：在 `scripts/continuous_task_loop.py` 内增加 `--check-once` / `--watch` 守护模式。优点是复用现有状态、配置和命令拼装，侵入性更小。缺点是单文件复杂度上升。
- 推荐方案：
  - 采用方案 B。
  - 用现有 `state.json` 作为事实源，再补进程存活检查和可恢复状态判断。
- 是否需要 ADR：
  - 否。本轮不引入新基础设施，也不改核心业务调用链。
- 测试计划：
  - 先补脚本级单测，锁定：
    - 进程存活判断
    - 可恢复状态判断
    - 自动唤醒前的状态重置
    - 守护模式的命令拼装
  - 再实现守护逻辑。
  - 完成后跑：
    - `python3 -m pytest -q tests/test_continuous_task_loop.py`
    - `python3 -m ruff check scripts/continuous_task_loop.py tests/test_continuous_task_loop.py`
    - `python3 -m compileall scripts tests`
- 实施步骤：
  - 先写测试，锁定 supervisor 行为
  - 再补脚本守护逻辑和状态字段
  - 更新 README / RUNBOOK / `docs/continuous-task-loop.md`
  - 运行验证并回填日志

## 实施记录

- 方案摘要：
  - 基于现有 harness 增加“巡检 + 唤醒”层，而不是新建第二套状态系统。
  - 自动唤醒的前提是：任务未完成、当前无 loop 进程、状态处于可恢复集合。
- 关键决策：
  - `completed`、`blocked`、`queue_exhausted`、`deadline_reached`、`max_iterations_reached` 视为终态，不自动恢复。
  - `interrupted`、`too_many_failures`、`iteration_timeout` 以及“状态写着 running 但进程已经消失”视为可恢复态。
  - 守护模式优先做成可前台运行的 `--watch`，同时支持定时器友好的 `--check-once`。
- 变更文件：
  - `scripts/continuous_task_loop.py`
  - `tests/test_continuous_task_loop.py`
  - `docs/continuous-task-loop.md`
  - `README.md`
  - `RUNBOOK.md`
- 风险与未覆盖项：
  - 当前只做单机单目录恢复，不处理多机器或多用户并发争抢同一 `state-dir`。
  - PID 存活检测只判断“进程是否存在”，不额外校验进程命令行签名；默认假设本地 `state-dir` 由单个 harness 独占。
  - `cron` / `launchd` 调度属于运行环境配置，仓库内只提供 `--check-once` 入口与示例，不负责代装系统级守护。
- 回滚方式：
  - 若本轮仅涉及 harness、测试与文档，回退对应文件即可；若改动状态文件语义，需要同步恢复文档与测试约束。

## 验证结果

- `python3 -m ruff check scripts/continuous_task_loop.py tests/test_continuous_task_loop.py`
  - 待本轮最终验证后补充
- `python3 -m pytest -q tests/test_continuous_task_loop.py`
  - 待本轮最终验证后补充
- `python3 -m compileall scripts tests`
  - 待本轮最终验证后补充

## 交付结论

- 风险清单：
  - 单目录 watchdog 依赖本地 `state.json` 与 `loop_pid` 一致性，不适合作为跨机器调度器。
  - 如果用户人为同时启动多个主循环并共用同一 `state-dir`，仍可能产生竞争。
- 未覆盖项：
  - 尚未提供 `launchd` plist 模板；当前只提供 `cron` 命令示例和 `--watch` 常驻模式。
- 上线检查项：
  - 确认 `output/agent-loop/` 可写。
  - 确认本机 `python3`、`codex` 路径与定时器环境一致。
  - 首次启用前先跑一次 `--dry-run` 或单轮 smoke run。
- 回滚步骤：
  - 删除 watchdog 定时任务。
  - 回退 `scripts/continuous_task_loop.py`、测试和文档到上一版本。
  - 如当前运行目录中残留 `loop_pid`，重新执行一次 `--check-once` 或手工修正 `state.json`。
- 后续建议：
  - 如果后面需要更强鲁棒性，可以再加“PID + 命令行签名”校验，避免极端 PID 复用误判。
