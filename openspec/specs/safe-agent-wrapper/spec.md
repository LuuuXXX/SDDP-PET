# Safe Agent Wrapper

## Purpose

应对 CrewAI issue #6380（异步 LLM 失败静默冻结 Flow，官方未修复）的防护层。所有 CrewAI Agent 的 `kickoff` / `kickoff_async` 调用 MUST 经 `SafeAgent` 包装：以 tenacity retry（指数退避）处理可恢复错误（Timeout / Connection / RateLimit），以立即抛出处理不可恢复错误（ValueError / ParseError / ValidationError），并把每次失败结构化记录到 Flow `state.errors`。retry 与 timeout 参数 MUST 可通过环境变量覆盖，便于在测试中构造 #6380 复现场景。权威来源：`analysis/03-crewai-version-strategy.md`。

## Requirements

### Requirement: SafeAgent MUST 包裹所有 CrewAI Agent kickoff 调用

由于 CrewAI #6380（异步 LLM 失败静默冻结）官方未修复（见 `analysis/03-crewai-version-strategy.md` 第一节），所有 CrewAI Agent 的 `kickoff` 与 `kickoff_async` 调用 MUST 通过 `SafeAgent` 包装类进行。`SafeAgent` MUST 提供 `kickoff(input)` 同步接口，内部封装 tenacity retry + asyncio timeout。

#### Scenario: 异步 LLM 调用超时不卡死（#6380 复现通过）
- **WHEN** SafeAgent 包裹的 CrewAI Agent kickoff 内部触发异步 LLM 调用，且该调用超过配置的 timeout（默认 120s）未返回
- **THEN** SafeAgent MUST 在 timeout 到期后抛出 `SafeAgentError`（不静默冻结）；调用方的控制流 MUST 不阻塞

#### Scenario: 可恢复错误触发 retry
- **WHEN** SafeAgent 检测到 `asyncio.TimeoutError` / `ConnectionError` / `RateLimitError`（OpenAI 429）
- **THEN** SafeAgent MUST 按 tenacity 策略重试（指数退避，默认 3 次）；retry 用尽仍失败时抛出 `SafeAgentError`

#### Scenario: 不可恢复错误不触发 retry
- **WHEN** SafeAgent 检测到 `ValueError` / `ParseError` / `ValidationError`（pydantic）
- **THEN** SafeAgent MUST 立即抛出 `SafeAgentError`（不重试），且 `SafeAgentError.reason` 字段标注 `non_recoverable`

### Requirement: SafeAgent MUST 区分错误类型并记录到 state

SafeAgent MUST 维护一个 `state.errors` 列表（与 CrewAI Flow state 集成），每次失败 MUST 追加一条记录 `{agent, error_type, message, recoverable, timestamp}`，供 UI（Dev-Phase 1 起）与 cost_report 显示。

#### Scenario: 错误记录到 state.errors
- **WHEN** SafeAgent 任一 kickoff 失败（无论可恢复或不可恢复）
- **THEN** CrewAI Flow state 的 `errors` 列表 MUST 追加一条结构化记录；记录 MUST 含 `agent` 字段（角色名）、`error_type` 枚举值、`recoverable` 布尔值

#### Scenario: 错误分类正确
- **WHEN** 审查 SafeAgent 错误分类逻辑
- **THEN** 可恢复类（`TimeoutError` / `ConnectionError` / `RateLimitError`）与不可恢复类（`ValueError` / `ParseError` / `ValidationError`）MUST 在代码中有显式分支；默认分支（未识别错误）MUST 标为 `recoverable=false` 并立即抛出

### Requirement: SafeAgent retry 策略 MUST 可配置

默认 retry 配置（3 次指数退避 + 120s timeout）MUST 可通过环境变量或构造参数覆盖，便于 Dev-Phase 0 测试场景构造（如验证 #6380 复现需缩短 timeout 至 5s）。

#### Scenario: 配置覆盖生效
- **WHEN** 通过环境变量 `SDDP_SAFE_AGENT_TIMEOUT_SECONDS=5` 启动 SafeAgent
- **THEN** 该 SafeAgent 实例的 timeout MUST 为 5s（而非默认 120s）；测试 `tests/safe_agent/test_timeout_retry.py` MUST 使用此机制构造 #6380 复现场景
