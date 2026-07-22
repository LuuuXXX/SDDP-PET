# Security Compliance

## Purpose

Dev-Phase 1 的安全与合规防护层。`security-compliance` 强制三件事：(1) LLM provider API 密钥（OpenAI / DeepSeek / Anthropic 等）MUST 通过 OS 原生 credential manager（Windows Credential Manager / macOS Keychain / Linux libsecret，跨平台抽象 `@napi-rs/keyring ^1.0.0`）加密存储，禁止任何形式的明文落盘；(2) 所有从 `SafeAgent.kickoff` 出发到 LLM 的 payload MUST 经过 `sddp/security/prefilter.py` 正则 catalog 脱敏（识别密钥 / PII / 凭证，替换为占位符，LLM 返回后再 reverse-substitute 还原）；(3) 所有进程 MUST 在启动时硬编码 `OTEL_SDK_DISABLED=true`，禁止任何 OpenTelemetry 上报网络请求（非配置可覆盖）。对应 `dod.md` D1-9、D1-11、D1-13。权威来源：`analysis/09`。

## Requirements

### Requirement: API 密钥 MUST 通过 OS 原生 credential manager 加密存储

依据 `analysis/09` §二、§三与 `dod.md` D1-9，LLM provider API 密钥（OpenAI / DeepSeek / 其他）MUST 通过 OS 原生 credential manager 存储：
- **Windows（主目标）**：Windows Credential Manager
- **macOS / Linux（开发者机器）**：Keychain / Secret Service（libsecret）
- 跨平台抽象：`@napi-rs/keyring ^1.0.0`（`analysis/09` §二锁定；`keytar` 已被 Atom org archived，禁止使用）
- 备选方案：Electron 内置 `safeStorage` API（在 `@napi-rs/keyring` 不可用的环境下作为 fallback）

**禁止**：任何形式的明文密钥写入磁盘（`config.json` / `.env` / `~/.sddp-pet/secrets.txt` 等均不允许）。

#### Scenario: 密钥读取走 Credential Manager API
- **WHENT** 用户在 SSH 设置页输入密钥并点击"保存"
- **THEN** 前端 MUST 通过 `@napi-rs/keyring.setPassword(service="sddp-pet", account=<provider>, password=<key>)` 写入；MUST 不写入任何磁盘文件

#### Scenario: D1-9 grep 验证通过
- **WHENT** 运行 `grep -r "sk-" ~/.sddp-pet/`
- **THEN** MUST 返回空结果（exit code 1）；MUST 不命中任何真实密钥；配置文件中 MAY 引用密钥别名（如 `key_ref: "openai_default"`）但 MUST 不含密文

#### Scenario: 密钥不可读时引导用户重新输入
- **WHENT** 用户首次启动应用且 Credential Manager 中无密钥
- **THEN** SSH 设置页 MUST 显示"未配置 API 密钥"状态 + "导入密钥"按钮；尝试启动流程 MUST 返回 `error_code=LLM_AUTH_FAIL`

### Requirement: 引擎 MUST 在调用 LLM 前对代码 payload 做正则脱敏

依据 `analysis/09` §五与 `dod.md` D1-11，所有从 `SafeAgent.kickoff` 出发到 LLM 的 payload MUST 经过 `sddp/security/prefilter.py` 包装脱敏。脱敏策略：
- 用正则 catalog 识别疑似密钥 / PII / 凭证，替换为占位符（如 `sk-abc123...` → `<REDACTED_OPENAI_KEY>`）
- 占位符映射 MUST 仅存在内存中（不写盘），LLM 返回后再 reverse-substitute 还原
- catalog 至少覆盖（参考 `gitleaks` / `truffleHog` 公开规则集）：
  - OpenAI / DeepSeek / Anthropic key 模式（`sk-`、`sk-ant-`、`deepseek-`）
  - AWS key（`AKIA...`、`aws4_request` 签名）
  - GitHub PAT（`ghp_`、`github_pat_`、`gho_`）
  - 通用 API key（`api_key=...`、`authorization: bearer ...`）
  - Email 地址、JWT（`eyJ...`）、私钥头（`-----BEGIN ... PRIVATE KEY-----`）

**集成点**：DP0 的 `SafeAgent` 包装 MUST 调用 `prefilter.scrub(payload)` 在 `kickoff_fn` 入口处；返回结果 MUST 通过 `prefilter.restore(text, mapping)` 在出口处还原。

#### Scenario: 固定输入产生固定脱敏输出
- **WHENT** 运行 `pytest tests/security/test_prefilter.py`，输入含 `sk-abc123def456` 的代码片段
- **THEN** 输出 MUST 替换为 `<REDACTED_OPENAI_KEY>`；mapping MUST 记录原文 → 占位符映射；同输入第二次运行 MUST 产生字节级相同的脱敏输出

#### Scenario: 还原后的内容与原文一致
- **WHENT** prefilter.scrub(text) → 发到 LLM → 收到响应 → prefilter.restore(response, mapping)
- **THEN** 还原后的内容 MUST 与"假设 LLM 原样返回 scrubbed text" 的 reverse 操作结果一致；mapping 中所有占位符 MUST 被正确替换回原文

#### Scenario: 不允许绕过 prefilter
- **WHENT** 审查 `backend/sddp/safe_agent/wrapper.py` 与 `backend/sddp/ipc/` 代码
- **THEN** MUST 不存在直接调用 `llm_client.chat.completions.create` 而绕过 prefilter 的代码路径；唯一入口 MUST 是 `SafeAgent.kickoff`

### Requirement: 进程 MUST 硬编码 `OTEL_SDK_DISABLED=true` 禁用遥测

依据 `analysis/09` §七与 `dod.md` D1-13，所有进程（Python 引擎 / Electron 前端 / CrewAI 子依赖）MUST 在启动时硬编码 `OTEL_SDK_DISABLED=true` 环境变量，禁止任何 OpenTelemetry 上报网络请求。

**硬编码位置**：
- Python：`backend/sddp/__init__.py` 模块加载时 `os.environ.setdefault("OTEL_SDK_DISABLED", "true")`
- Electron：`frontend/electron/main.ts` 启动时 `process.env.OTEL_SDK_DISABLED = "true"`

**验证**：进程启动 60 秒内，对外网络流量 MUST 仅包含 LLM provider 域名（`api.openai.com` / `api.deepseek.com` 等）+ SSH 隧道（远程模式）；MUST 不包含任何 `*.otlp` / `*.telemetry` / `*.signals.*` 域名。

#### Scenario: 进程启动后无 OTEL 上报网络请求
- **WHENT** 启动应用，使用网络抓包工具（如 Wireshark / tcpdump）观察 60 秒
- **THEN** MUST 不出现发往 OpenTelemetry collector 的连接（默认端口 4317/4318 或任何 `otel` 相关域名）；`OTEL_SDK_DISABLED` 环境变量 MUST = "true"

#### Scenario: 用户无法通过配置开启遥测
- **WHENT** 审查 `execution.yaml` / `config.json` / 设置页 UI
- **THEN** MUST 不存在允许用户开启遥测的配置项；`OTEL_SDK_DISABLED=true` MUST 在代码中硬编码（非配置可覆盖）
