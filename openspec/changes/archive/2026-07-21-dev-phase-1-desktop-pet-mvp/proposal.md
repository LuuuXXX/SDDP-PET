## Why

Dev-Phase 0 froze a working SDDP engine (5-role linear flow + KG-MVP + CLI runner) but only developers can drive it — every confirmation point blocks on stdin, every cost update is a stdout table, every output is a markdown file in `out/`. Dev-Phase 1 closes that gap: it ships the **user-facing desktop pet UI + the security compliance** required for any real user to safely hand the engine their LLM API key. Without DP1, SDDP-Pet is a library; with DP1, it is a product.

Per `openspec/specs/development-roadmap/phases.md`, DP1 is the second stop on the critical path (3–4 weeks) and the prerequisite for DP2 (confrontation flow + 8-role pets).

## What Changes

### New user-facing capabilities
- **Dual-window Electron shell** (transparent PixiJS pet window + opaque React panel window) with click-through hit-testing and position persistence
- **WebSocket IPC** between the Python engine and Electron UI — 5 Push + 4 RPC + 4 RPC-response + application-layer heartbeat (30s/10s/3-miss)
- **Encrypted API key storage** via OS-native credential manager (Windows Credential Manager primary; `@napi-rs/keyring` for cross-platform dev) — no plaintext key ever touches disk
- **Code pre-filter** that desensitizes source code (regex-based secret/PII/key redaction) before it leaves the local process for the LLM
- **Privacy consent + AI labeling + OTEL hard-disable** — first-launch consent modal, persistent "AI 驱动" badge on pet bubble, `OTEL_SDK_DISABLED=true` hardcoded
- **Remote mode** via SSH local port forwarding (`ssh -L 8765:localhost:8765`) — transparent to frontend
- **Observability** — 4 metrics (flow execution time / agent latency / token consumption rate / error rate) written to `metrics.json` and rendered in the diagnostic panel

### D1-DoD scope clarifications (incorporated into specs/)
Three DP1 DoD items surfaced ambiguities during the prerequisite research (see `analysis/07`/`08`/`09`, commit `65ea40e`); this change pins them:
- **D1-7 心跳** — clarify "ping" means application-layer JSON `{"type":"ping"}`, not RFC 6455 protocol frames (Starlette's WS wrapper doesn't expose the latter)
- **D1-8 气泡确认** — split responsibility: window1 PixiJS bubble shows prompt + pet animation; **window2 React `ConfirmPanel`** holds the y/n/e buttons (resolves tension with D1-1's "0 React DOM in window1")
- **D1-10 拒绝语义** — "用户拒绝则不启动流程" means `start_flow` RPC is rejected; the app stays running for history review / settings editing (no exit)

### Non-goals (explicitly deferred)
- ❌ Live2D pet rendering (deferred to Dev-Phase 4 as optional)
- ❌ 8-role pet animation state machine (Dev-Phase 2/3b responsibility)
- ❌ Confrontation flow UI (Dev-Phase 2)
- ❌ Sandboxed code execution / file-write proxy (Dev-Phase 3a)
- ❌ Tier-C offline / Ollama provider (Dev-Phase 5)
- ❌ Internationalization (Dev-Phase 5)

## Capabilities

### New Capabilities
- `desktop-pet-ui`: Electron dual-window shell — transparent PixiJS pet window (window1) + opaque React panel window (window2); click-through hit-testing; position persistence; first-launch privacy consent modal; "AI 驱动" badge; ConfirmPanel for human feedback points
- `websocket-ipc`: FastAPI WebSocket server (port 8765) + TypeScript client contract; 5 Push messages (agent_state_change / document_produced / cost_update / feedback_required / error) + 4 RPC requests (start_flow / user_feedback / resume_flow / abort_flow) + 4 RPC responses; application-layer heartbeat (30s ping / 10s pong / 3-miss disconnect); `WebSocketHumanFeedbackAdapter` bridges to DP0's `LinearPhase02Flow` and its `@persist` resume (replacing CLI's `CLIHumanFeedbackAdapter`)
- `security-compliance`: OS-native encrypted key storage (`@napi-rs/keyring` + Electron `safeStorage` fallback); code pre-filter regex catalog (`sddp/security/prefilter.py`) wrapping `SafeAgent.kickoff`; AI identity labeling; OTEL hard-disable; `grep -r "sk-" ~/.sddp-pet/` MUST return empty
- `remote-mode`: SSH local port forwarding transport; frontend connects to `localhost:8765` in both local and remote modes (no client-side branching); connection failure → UI retry button
- `observability`: 4 metrics collection (flow_time_seconds / agent_latency_seconds / token_consumption_rate / error_rate) → `metrics.json`; diagnostic panel renders live values

### Modified Capabilities
<!-- None. DP1 consumes DP0 capabilities (engine-core, cli-runner, safe-agent-wrapper) as-is.
     The WebSocketHumanFeedbackAdapter is a new implementation of cli-runner's existing
     HumanFeedbackAdapter abstraction — no spec-level change to cli-runner. cli-runner
     remains the headless fallback; UI is additive. -->

## Impact

### Code layout (additive)
```
SDDP-Pet/
├── backend/
│   ├── sddp/
│   │   ├── ipc/                      # NEW: FastAPI WS server + WebSocketHumanFeedbackAdapter
│   │   │   ├── server.py
│   │   │   ├── schemas.py            # Pydantic v2 mirrors of TS contract (analysis/08)
│   │   │   ├── heartbeat.py
│   │   │   └── feedback_adapter.py   # bridges to LinearPhase02Flow.human_feedback_handler
│   │   └── security/                 # NEW: D1-11 pre-filter
│   │       ├── prefilter.py
│   │       └── patterns/             # regex catalog (sk-/AKIA/github_pat/email/...)
│   └── pyproject.toml                # + fastapi, + uvicorn[standard] promoted
├── frontend/                         # NEW: Electron + Vite + React + PixiJS
│   ├── electron/
│   │   ├── main.ts                   # dual BrowserWindow; click-through; tray
│   │   ├── preload.ts
│   │   └── secrets.ts                # @napi-rs/keyring wrapper
│   ├── src/
│   │   ├── window1-pet/              # PixiJS Application, 0 React DOM
│   │   ├── window2-panel/            # React (state / diagnostic / settings / confirm)
│   │   └── shared/ws-client.ts       # WebSocket client + zod schemas
│   ├── package.json                  # electron 43 / pixi 8 / react 19 / vite 7
│   └── electron.vite.config.ts
└── openspec/changes/dev-phase-1-desktop-pet-mvp/
```

### Dependencies
- **Backend (additions to `backend/requirements.lock.txt`)**: `fastapi==0.139.2 (选定于 DP1 day-0)`, `uvicorn[standard]==0.51.0` (already transitive → promote to direct), `python-socks` NOT introduced (SSH tunnel is OS-layer)
- **Frontend (new `frontend/package.json`, locked per `analysis/07`)**: electron `43.1.1`, pixi.js `8.19`, react/react-dom `19.2`, vite `7.3.6` (constrained by electron-vite 5), electron-vite `5.0`, typescript `5.6`, zod `^3.23`, `@napi-rs/keyring ^1.0.0`
- **Excluded**: `keytar` (Atom org archived — see `analysis/09`)

### Systems / Contracts
- **DP0 baseline replayed**: archive 时 MUST replay `openspec/regression/golden-demos/dev-phase-0.md` + run DP0 contract tests (17 conditions across `backend/tests/{kg,safe_agent,adaptation,engine,cli}/`).任一失败 → DP1 Go 阻断
- **API surface**: WebSocket JSON contract becomes a frozen inter-process contract — subsequent changes (DP2+) MUST honor backward compatibility per `openspec/specs/regression-strategy/spec.md`
- **Toolchain shift**: project now has both Python and TypeScript; lint/test commands in `backend/` and `frontend/` are independent; CI strategy deferred to Dev-Phase 2 multi-window work
- **Security boundary**: every LLM-bound payload crosses `sddp/security/prefilter.py` once; no other code path may call `SafeAgent.kickoff` without prefilter wrap

### Decision dependencies (Context)
This change incorporates by reference:
- `analysis/07-electron-dual-window-research.md` — Electron/PixiJS/React version locks + window architecture
- `analysis/08-websocket-ipc-contract.md` — full TS + Pydantic message schemas + heartbeat sequence
- `analysis/09-secret-storage-cross-platform.md` — `@napi-rs/keyring` choice + prefilter regex catalog + D1-9 grep verification
- `analysis/00-sddp-pet-final.md` §6/§7/§8 — original DP1 design baseline
- `openspec/regression/golden-demos/dev-phase-0.md` — regression baseline
- `openspec/specs/development-roadmap/dod.md` Dev-Phase 1 section (D1-1 ~ D1-16)

### 跨阶段接口变更登记

| 接口名 | 变更类型 | 向后兼容 | 迁移路径 |
|--------|----------|----------|----------|
| WebSocket JSON 消息契约（5 Push + 4 RPC + 4 RPC-response + heartbeat + error_code 枚举） | 新增（首次引入） | N/A（DP1 首个跨进程契约） | 见本变更 `specs/websocket-ipc/spec.md`；archive 时登记到 `openspec/regression/contracts-index.md` 的 `WS-IPC: *` 行（约 14 条） |
| `WebSocketHumanFeedbackAdapter` | 新增（DP0 `HumanFeedbackAdapter` 抽象的新实现） | ✅ 兼容（CLI 实现保留） | 见 `specs/websocket-ipc/spec.md`；DP0 `cli-runner` spec 不变 |
| `sddp/security/prefilter.py`（脱敏 + 还原 API） | 新增（首次引入） | N/A | 见 `specs/security-compliance/spec.md`；archive 时登记到 `Security: *` 行（约 4 条） |
| `@napi-rs/keyring` 密钥存储抽象 | 新增（首次引入） | N/A | 见 `specs/security-compliance/spec.md`；登记到 `Security: keyring-*` 行 |
| Electron 双窗口 main process API（`createWindow1/2`、click-through） | 新增（首次引入） | N/A | 见 `specs/desktop-pet-ui/spec.md`；登记到 `UI: window-*` 行 |
| 4 项监控指标 schema（`metrics.json` 行格式） | 新增（首次引入） | N/A | 见 `specs/observability/spec.md`；登记到 `Metrics: *` 行 |
| SSH 隧道 transport | 新增（首次引入） | N/A | 见 `specs/remote-mode/spec.md`；登记到 `Remote: ssh-tunnel` 行 |

本变更 archive 时，所有上述契约的状态从 `unimplemented` → `frozen`，更新到 `openspec/regression/contracts-index.md`。

**DP0 契约不变性**：本变更 MUST NOT 修改 DP0 已 frozen 的 17 条契约（`KG: *` / `SafeAgent: *` / `Adaptation Layer: *` / `JSON Schema: *` / `sddp run` CLI）；任何对 DP0 spec 的 apparent 需求 MUST 转化为"DP1 新增 capability"而非修改 DP0 capability。

## Regression Baseline

依据 `openspec/regression/golden-demos-index.md` 与 `openspec/specs/regression-strategy/spec.md`：

- **本阶段为 Dev-Phase 1**：archive 前 MUST 重放 Dev-Phase 0 的 Golden Demo（`openspec/regression/golden-demos/dev-phase-0.md`，git tag `dev-phase-0-v1`）
- **重放通过标准**：同一份 `config-hot-reload.txt` proposal 在 DP1 代码树下跑 `git checkout dev-phase-0-v1 -- backend/ && sddp run ...`，产出 4 markdown + cost_report.json 与基线一致（标题相同、KG citations 相同、cost_report 量化字段在 ±10% 浮动内）
- **DP0 契约回归**：本阶段 archive 前 MUST 跑 `pytest backend/tests/{kg,safe_agent,adaptation,engine,cli}/ -m "not e2e"`，全部 PASS（17 条契约对应的测试集）
- **archive 前冻结**：本变更 Go 判定时，MUST 冻结本阶段 Golden Demo 到 `openspec/regression/golden-demos/dev-phase-1.md`（建议输入：与 DP0 同 proposal，在桌宠 UI 下端到端跑通），并打 git tag `dev-phase-1-v1`
- **已接受风险**：本阶段引入新的已接受风险见 `design.md` Risks 章节；现有 4 项（`accepted-risks.md`）保持不变，`AR-2`（OpenAI lock-in）继续暴露，`AR-3`（KG 置信度）在 DP1 UI 下首次面向终端用户
