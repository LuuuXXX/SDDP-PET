# Remote Mode

## Purpose

Dev-Phase 1 的远程部署模式支持。`remote-mode` 覆盖 CrewAI 引擎在 Linux 服务器、Windows 仅运行桌宠 UI 的部署场景：(1) 通过 SSH 本地端口转发（`ssh -L 8765:localhost:8765`）承载 WebSocket，前端 WebSocket 客户端连接 `ws://localhost:8765` 与本地模式完全一致（无客户端分支代码）；(2) 远程崩溃恢复通过 RPC 远程触发 —— 前端检测到连接丢失后由用户点击"重连"，前端建立新 WS 连接并发送 `resume_flow` RPC，引擎在远程 SQLite 中查到 flow_id 的 prior_state 并通过 DP0 `LinearPhase02Flow` resume 机制跳过已完成步骤，整个恢复过程对前端透明。DP1 不引入 Tailscale Funnel / cloudflared 等现代替代方案（延后到 Dev-Phase 4 评估）。对应 `dod.md` D1-16。权威来源：`analysis/00` §六、`analysis/08` §七。

## Requirements

### Requirement: 远程模式 MUST 通过 SSH 本地端口转发对前端透明

依据 `analysis/00` §六与 `analysis/08` §七、`dod.md` D1-16，远程模式（CrewAI 引擎在 Linux 服务器，Windows 仅运行桌宠 UI）MUST 通过 SSH 本地端口转发承载 WebSocket：
- 用户在 SSH 设置页填写 host / port / username / key_ref（密钥别名，实际密钥存 Credential Manager）
- 前端调用 `ssh -L 8765:localhost:8765 <user>@<host> -p <port> -i <key_path>` 建立隧道
- 前端 WebSocket 客户端连接 `ws://localhost:8765`（与本地模式完全一致，无客户端分支代码）

**说明**：经 `analysis/08` §七评估，DP1 不引入 Tailscale Funnel / cloudflared 等现代替代方案（v1 用户场景下 SSH 普适性 + 0 第三方依赖更优；替代方案延后到 Dev-Phase 4 评估）。

#### Scenario: SSH 隧道建立后前端透明连接
- **WHENT** 用户在设置页填好 SSH host/port/user 并点击"测试连接"
- **THEN** 前端 MUST 调用 `ssh -L 8765:localhost:8765 ...` 建立隧道；连接成功后 WebSocket 握手 MUST 成功；前端代码 MUST 不含"if remote then ..." 分支

#### Scenario: SSH 连接失败显示错误 + 重试按钮
- **WHENT** SSH 隧道建立失败（网络不通 / 密钥错误 / 端口占用）
- **THEN** 前端 MUST 在 SSH 设置页显示具体错误（区分"网络不通" / "认证失败" / "端口被占"）；MUST 提供"重试"按钮；MUST 不静默失败或退出应用

### Requirement: 远程模式崩溃恢复 MUST 通过 RPC 远程触发（不依赖本地 SQLite）

依据 `analysis/00` §六"远程模式崩溃恢复"，远程模式下 `@persist` SQLite 位于远程服务器，本地无法直接访问。崩溃恢复 MUST：
- 前端检测到连接丢失 → 显示"连接中断" + "重连"按钮
- 用户点击重连 → 前端建立新 WS 连接 → 发送 `resume_flow` RPC（携带 flow_id）
- 引擎在远程 SQLite 中查到该 flow_id 的 prior_state → 通过 DP0 的 `LinearPhase02Flow` resume 机制跳过已完成步骤
- 整个恢复过程对前端透明（前端只发 `resume_flow` RPC + 等待 `flow_resumed` 响应）

#### Scenario: 远程模式断线重连恢复 flow
- **WHENT** 远程模式运行中网络中断 30 秒后恢复
- **THEN** 前端 MUST 显示"连接中断"；用户点击"重连"后 MUST 自动发送 `resume_flow` RPC（携带原 flow_id）；引擎 MUST 通过远程 SQLite 的 prior_state 跳过已完成步骤；响应 `flow_resumed` 消息；前端 MUST 显示流程从断点继续
