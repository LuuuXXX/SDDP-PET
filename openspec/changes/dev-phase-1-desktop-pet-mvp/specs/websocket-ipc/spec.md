## ADDED Requirements

### Requirement: 引擎 MUST 在端口 8765 暴露 FastAPI WebSocket server

依据 `analysis/08` 第二节与 `dod.md` D1-4，后端 MUST 通过 FastAPI WebSocket（端口 8765）与前端双向通信。本地模式直连 `ws://localhost:8765`；远程模式经 SSH `ssh -L 8765:localhost:8765` 隧道后**前端仍连 `ws://localhost:8765`**（前端无模式分支）。

库版本锁定（`analysis/08` §二）：`uvicorn[standard]==0.51.0`（DP0 lockfile 既有，promote 为直接依赖）、`websockets==16.1.1`、`starlette==1.3.1`、`fastapi==<patch-TBD>`（DP1 day-0 用 `analysis/08` §2.3 验证脚本选定具体 patch，验证条件：不 bump starlette/uvicorn/websockets）。

#### Scenario: WebSocket 握手成功
- **WHENT** 前端发起 `ws://localhost:8765` 连接
- **THEN** FastAPI WebSocket endpoint MUST 接受连接（HTTP 101 Switching Protocols）；连接后 MUST 立即发送一条 `agent_state_change` Push 消息（state=`idle`）作为就绪信号

#### Scenario: 非法 JSON 消息被拒绝且不崩连接
- **WHENT** 前端发送一条非法 JSON（如 `{not valid`）
- **THEN** 服务端 MUST 返回一条 `error` Push 消息（`error_code=PARSE_FAILURE`，`recoverable=true`）；连接 MUST 保持开放

### Requirement: 引擎 MUST 实现 5 种 Push 消息（引擎 → 前端）

依据 `analysis/00` §七与 `analysis/08` 第三节，引擎 MUST 在状态变化时主动 Push 以下 5 类消息，每条 MUST 含 `type`、`timestamp` 字段；所有非 `error` 消息 MUST 含与流程相关的 `flow_id`：

| type | 字段（除 type/timestamp/flow_id 外） |
|------|--------------------------------------|
| `agent_state_change` | `agent` / `state`(working\|idle\|waiting\|error) / `phase` / `round` / `detail` |
| `document_produced` | `agent` / `doc_type`(proposal\|delta_spec\|delta_design\|architecture_research\|code_suggestions) / `doc_id` / `summary` |
| `cost_update` | `total_tokens` / `estimated_cost_usd` / `round_tokens` |
| `feedback_required` | `method`(requirement_confirmation\|design_confirmation\|task_confirmation) / `message` / `output` |
| `error` | `agent` / `error_code`(枚举见下) / `message` / `severity`(critical\|error\|warning) / `recoverable` |

`error_code` 枚举（与 DP0 `safe_agent` 异常类对齐 + DP1 新增）：`LLM_TIMEOUT` / `LLM_AUTH_FAIL` / `LLM_RATE_LIMIT` / `PARSE_FAILURE` / `FLOW_STUCK` / `KNOWLEDGE_GRAPH_ERROR` / `SSH_CONNECTION_LOST` / `PRIVACY_CONSENT_REQUIRED`。

#### Scenario: 5 类 Push 消息全部触发 UI 更新
- **WHENT** 运行一个完整 SDDP 流程（含至少一次错误恢复）
- **THEN** 前端 MUST 收到全部 5 种 type 的 Push 消息；每类 MUST 触发对应的 UI 更新（agent_state_change 更新状态面板；document_produced 加入文档列表；cost_update 更新成本显示；feedback_required 弹出 ConfirmPanel；error 显示错误提示）

### Requirement: 前端 MUST 能发起 4 种 RPC 请求并接收对应响应

依据 `analysis/00` §七与 `analysis/08` 第三节，前端 MUST 通过 `message_id`（UUID v4）关联 RPC 请求与响应。4 种 RPC：

| 请求 type | 字段（除 type/message_id 外） | 响应 type | 响应额外字段 |
|----------|-------------------------------|----------|--------------|
| `start_flow` | `proposal` / `pcm` / `project_path` | `flow_started` | `flow_id` / `status`="running" |
| `user_feedback` | `flow_id` / `feedback`(y\|n\|e) / `outcome` | `feedback_accepted` | `flow_id` / `status`="resuming" |
| `resume_flow` | `flow_id` / `feedback`(optional) | `flow_resumed` | `flow_id` / `status`="running" |
| `abort_flow` | `flow_id` | `flow_aborted` | `flow_id` / `status`="aborted" |

每条 RPC 响应 MUST 包含与请求相同的 `message_id`；前端 MUST 在 30 秒内收到响应，否则视为请求失败并提示重试。

#### Scenario: 4 类 RPC 全部被引擎正确处理
- **WHENT** 前端依次发起 4 类 RPC（start_flow → user_feedback → resume_flow → abort_flow）
- **THEN** 引擎 MUST 对每条请求返回对应响应 type；每条响应的 `message_id` MUST 与请求一致；`status` 字段 MUST 符合上表

### Requirement: 心跳 MUST 使用应用层 JSON `{"type":"ping"}`（非 RFC 6455 协议帧）

依据 `analysis/08` §五对 `dod.md` D1-7 的澄清，心跳机制 MUST 在应用层实现：
- 引擎每 30 秒发送 `{"type":"ping","timestamp":<ISO8601>}`
- 前端 MUST 在 10 秒内回复 `{"type":"pong","timestamp":<ISO8601>,"ping_timestamp":<收到的 ping timestamp>}`
- 引擎连续 3 次（≥ 90 秒）未收到 pong → 触发"连接丢失"事件：暂停当前 flow（state=`paused`），向引擎内部广播 `error` Push 消息（`error_code=SSH_CONNECTION_LOST`，`recoverable=true`）
- 前端检测到连接关闭 → window2 显示"连接中断"提示 + "重连"按钮；用户点击重连后，前端发起新 WS 连接并调用 `resume_flow` RPC（依赖 DP0 `@persist` 中断恢复，flow_id 不变）

**说明**：选择应用层 ping 而非 RFC 6455 协议帧的原因 —— Starlette 的 WebSocket 包装层不暴露协议层 ping/pong API（`analysis/08` §5.1 验证）。

#### Scenario: 心跳正常往返
- **WHENT** 引擎发送 `{"type":"ping"}`，前端 10 秒内回复 `{"type":"pong"}`
- **THEN** 连接 MUST 保持开放；流程 MUST 不被暂停

#### Scenario: 3 次未回复触发连接丢失
- **WHENT** 前端模拟停止回复 pong（≥ 90 秒）
- **THEN** 引擎 MUST 触发"连接丢失"事件；当前 flow 状态 MUST 写为 `paused`；前端 MUST 显示"连接中断"提示 + "重连"按钮

#### Scenario: 重连后 flow 恢复
- **WHENT** 用户点击"重连"按钮
- **THEN** 前端 MUST 建立新 WS 连接并发送 `resume_flow` RPC（携带原 flow_id）；引擎 MUST 通过 DP0 的 `@persist` 机制从 prior_state 恢复（跳过已完成步骤）；响应 `flow_resumed` 消息

### Requirement: `WebSocketHumanFeedbackAdapter` MUST 桥接 WS 协议到 DP0 `LinearPhase02Flow`

依据 `analysis/08` §六，DP0 的 `LinearPhase02Flow.human_feedback_handler` 抽象 MUST 有一个 WS 实现 `WebSocketHumanFeedbackAdapter`，替换 DP0 CLI 模式下的 `CLIHumanFeedbackAdapter`（见 `backend/sddp/cli/feedback_adapter.py`）。其行为：
- 收到 flow 的确认点调用（`requirement_confirmation` / `design_confirmation` / `task_confirmation`）→ 通过 WS Push `feedback_required` 消息阻塞等待
- 收到前端 `user_feedback` RPC（含 y/n/e）→ 返回对应布尔值给 flow
- 流程结束 → Push 全部 `document_produced` 消息 + 最终 `cost_update` 消息

**契约不变性**：DP0 `cli-runner` 的 spec 不变；CLI 仍是 headless 模式可用入口。WS adapter 是新增的同抽象实现。

#### Scenario: WS 模式下完整 flow 跑通
- **WHENT** 前端发送 `start_flow` RPC（携带 proposal 文本），并在每个确认点回复 `user_feedback` (y)
- **THEN** flow MUST 完成 5 步（requirement_officer / orchestrator / architect / executor / code_asset_manager）；引擎 MUST Push 至少 4 条 `document_produced` 消息（proposal / delta_spec / delta_design / architecture_research）+ 1 条最终 `cost_update`；前端 MUST 能渲染所有文档

#### Scenario: 用户拒绝确认点 → flow 中止
- **WHENT** 前端在某确认点回复 `user_feedback` (n)
- **THEN** flow MUST 中止；引擎 MUST Push `flow_aborted` 响应（`status`="aborted"）；前端 MUST 显示中止状态 + 已产出文档列表
