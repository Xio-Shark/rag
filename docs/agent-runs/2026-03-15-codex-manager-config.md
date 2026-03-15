# 2026-03-15 Codex Manager 配置说明核对

- 任务名称：Codex Manager 配置说明核对
- 项目类型：B 现有项目新增功能
- 次类型：F 外部工具接入与本机配置咨询
- 风险等级：R1

## 正式执行前说明

- 目标：
  - 核对 `qxcnm/Codex-Manager` 仓库当前公开安装与配置方式。
  - 结合本机已解压目录 `/Users/xioshark/Downloads/CodexManager-service-macos-arm64` 给出可执行配置步骤。
  - 明确哪些步骤可以直接在本机完成，哪些依赖仓库文档或首次启动生成。
- 非目标：
  - 不修改业务代码或反编译第三方二进制。
  - 不替用户执行高风险系统级安装、卸载或开机自启配置。
  - 不假设仓库 README 与旧发行版完全一致。
- 约束：
  - 必须先完成 `HOOK.md` 要求的分类、风险分级、仓库探测和任务日志。
  - 配置说明需同时参考公开仓库文档与本地二进制实际内容，避免只凭记忆回答。
  - 当前 `~/Desktop/rag` 仅作为任务规范容器，不是本次目标仓库的 Git worktree。
- 风险：
  - 外部仓库文档可能与当前发行包内容不完全一致。
  - 用户提供路径名包含 “dmg”，但本地实际可能是 `zip` 解压目录，需以实物为准。
  - 若配置涉及 token、端口或反向代理，遗漏细节会导致启动后不可用。
- 验收标准：
  - 明确仓库当前推荐的配置入口。
  - 明确本机目录中三个可执行文件的角色或至少指出启动入口。
  - 给出按顺序执行的配置步骤、验证方法和常见问题提示。
- 当前项目类型：
  - 主类型：B 现有项目新增功能
  - 次类型：F 外部工具接入与本机配置咨询
- 当前风险等级：
  - R1：以配置说明核对为主，仅做低风险本地检查，不改业务或系统关键路径。
- 仓库现状：
  - 规范仓库已存在：`README.md`、`ARCHITECTURE.md`、`IMPLEMENTATION_PLAN.md`、`RUNBOOK.md`、`.env.example`、`tests/`、`.github/workflows/`、`migrations/`
  - 本机已存在：`/Users/xioshark/Downloads/CodexManager-service-macos-arm64`、同名 `zip` 包、运行后生成的 `codexmanager.db*` 与 `codexmanager.rpc-token`
  - 当前规范仓库缺失：目标外部仓库的本地 checkout
- 缺失机制清单：
  - 外部仓库 README / release 说明核对
  - 本地可执行文件帮助信息核对
  - 面向用户的配置步骤整合
- 方案对比：
  - 方案 A：只依据本地二进制目录猜测启动方式。复杂度低，成本低，但准确性不足，兼容性和维护性差，回滚意义弱。
  - 方案 B：同时核对公开仓库文档与本地安装物，再输出机器可执行步骤。复杂度中等，成本适中，侵入性最低，准确性与兼容性最佳，维护成本更低。
- 推荐方案：
  - 采用方案 B。
  - 先核对仓库说明，再用本地帮助信息补齐实际落地细节。
- 是否需要 ADR：
  - 否。本轮不涉及基础设施、数据库、认证、核心调用链或高风险接口变更。
- 测试计划：
  - 验收测试：确认本地目录存在主程序与启动器。
  - 回归测试：核对仓库文档中的安装步骤与本地目录结构是否一致。
  - 边界测试：识别路径名与实际包格式不一致、首次启动生成文件等情况。
  - 集成测试：如帮助信息可用，验证启动入口支持的参数与配置方式。
- 实施步骤：
  1. 读取仓库公开 README / release 安装说明。
  2. 检查本地解压目录和文件类型。
  3. 读取二进制帮助信息或使用痕迹，确认启动顺序。
  4. 汇总为面向当前机器的配置步骤、验证命令和注意事项。

## 实施结果

- 已核对公开仓库：
  - GitHub 仓库：`qxcnm/Codex-Manager`
  - README 当前给出的发行版下载路径包含 `v0.1.8`
  - 官方文档建议直接下载 `CodexManager-service-macos-arm64.zip` 并运行 `./codexmanager-start`
  - 官方文档默认地址：service `localhost:48760`，web `http://localhost:48761`
- 已核对本机安装物：
  - 用户提供路径 `/Users/xioshark/Downloads/CodexManager-service-macos-arm64` 实际是 `zip` 解压目录，不是 `dmg` 挂载点
  - 目录内存在 `codexmanager-start`、`codexmanager-service`、`codexmanager-web`
  - 目录中已生成 `codexmanager.db`、`codexmanager.rpc-token`，说明本地至少执行过一次启动流程
- 已核对主要配置项：
  - 文档中明确的环境变量包括 `CODEXMANAGER_SERVICE_ADDR`、`CODEXMANAGER_UPSTREAM_BASE_URL`、`CODEXMANAGER_PROXY_LIST`、`CODEXMANAGER_UPSTREAM_PROXY_URL`
  - 本地二进制字符串显示还存在 `codexmanager.env` / `CodexManager.env` 文件名，推测支持同目录环境文件覆盖
  - 启动器字符串显示 `CODEXMANAGER_WEB_ADDR` 默认值为 `localhost:48761`
- 已做本地验证：
  - `codexmanager-start` 会同时拉起 service 与 web
  - 当前受限执行环境下，web 进程会在读取 macOS 网络配置时触发 `reqwest/system-configuration` panic，不能把这里的异常直接等同于用户本机必现问题
- 结论：
  - 对用户最稳妥的配置路径是：进入解压目录，先直接启动 `codexmanager-start`，再在 Web UI 的系统设置中补充后端环境变量与 API Key / 模型映射配置
  - 如需代理或公网暴露，再按文档增加 `CODEXMANAGER_SERVICE_ADDR` 与代理相关环境变量

## 风险清单

- 若公开仓库未提供完整配置项，最终说明需要明确哪些属于基于本地文件结构的推断。
- 二进制未提供真正的 `--help`；命令带 `--help` 仍会实际启动，因此排障时不能依赖帮助参数。
- 当前受限环境无法完整验证 Web 端正常渲染，只能核对启动入口、端口与配置键。

## 未覆盖项

- 未执行系统级自启、launchd 或服务托管配置。
- 未验证局域网 / 反向代理暴露方式。
- 未验证 UI 内每个高级配置项的实际保存回写格式。

## 回滚步骤

1. 本轮仅新增任务日志，无业务代码变更。
2. 若后续补充了临时配置文件，可删除新增文件并恢复原始下载目录。
