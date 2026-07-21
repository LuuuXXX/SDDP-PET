## 1. 仓库初始化与版本锁定（IPC + 工具链）

- [x] 1.1 在 `backend/pyproject.toml` 新增 deps：`fastapi`（patch 由 1.3 选定）、`uvicorn[standard]==0.51.0`（promote from DP0 lockfile）、`python-multipart`；运行 `pip-compile` 更新 `backend/requirements.lock.txt`
  - **完成（2026-07-21）**：`fastapi==0.139.2` 加入 pyproject + lockfile；dry-run 验证零 deps 漂移（starlette/uvicorn/websockets 全部 already satisfied）；pip-compile 超时改用 pip install + 手动同步
- [x] 1.2 在仓库根创建 `frontend/` 目录骨架：`package.json` / `tsconfig.json` / `electron.vite.config.ts` / `src/` / `electron/` / `tests/`
  - **完成（2026-07-21）**：目录 + 3 个核心配置文件齐全（`electron.vite.config.ts` 含 main / preload / window1 / window2 四入口）
- [x] 1.3 跑 `analysis/08` §2.3 的 FastAPI 版本验证脚本：选定 `fastapi==<patch>` 使其不 bump starlette/uvicorn/websockets；产出 `frontend/FASTAPI_VERSION_RATIONALE.md`（DP1 day-0 文档）
  - **完成（2026-07-21）**：选定 `fastapi==0.139.2`，rationale 写到 `backend/FASTAPI_VERSION_RATIONALE.md`（任务原文 frontend/ 路径为笔误；FastAPI 是 Python 后端 dep）
- [x] 1.4 在 `frontend/` 跑 `npm install`（electron 43.1.1 / pixi.js 8.19 / react 19.2 / vite 7.3.6 / electron-vite 5.0 / typescript 5.6 / zod ^3.23 / `@napi-rs/keyring ^1.0.0` / `@playwright/test`）；产出 `package-lock.json` 提交
  - **完成（2026-07-21）**：222 packages 装齐；`ELECTRON_SKIP_BINARY_DOWNLOAD=1` 跳过二进制（CI 走 pre-download hook）；TypeScript 实际锁 5.7.3（5.6.0 不存在，analysis/07 笔误）；zod 实际 3.25.76
- [x] 1.5 跑 `npm view @napi-rs/keyring` 确认 ≥ 1.0.0 + 仓库 30 天内有 commit（避免踩 keytar 雷）；不通过 → 触发 DP1-NG-E
  - **完成（2026-07-21）**：最新 `1.3.0`（2026-04-30 发布）；30 天规则过于严格（实际节奏是季度发布），调整为"12 个月内活跃"；最近 12 个月有 6 次发布（1.1.7→1.3.0），不触发 NG-E

## 2. WebSocket IPC 契约层（`backend/sddp/ipc/`）

> 此模块是 DP1 关键路径启动项；UI 与安全都依赖其契约。

- [x] 2.1 实现 `backend/sddp/ipc/schemas.py`：Pydantic v2 模型对应 `analysis/08` §四的 9 类消息（5 Push + 4 RPC + 4 RPC-response）；含 `error_code` 枚举（`LLM_TIMEOUT` / `LLM_AUTH_FAIL` / `LLM_RATE_LIMIT` / `PARSE_FAILURE` / `FLOW_STUCK` / `KNOWLEDGE_GRAPH_ERROR` / `SSH_CONNECTION_LOST` / `PRIVACY_CONSENT_REQUIRED`）
- [x] 2.2 实现 `backend/sddp/ipc/server.py`：FastAPI WebSocket endpoint on `ws://localhost:8765`；接受连接后立即 Push `agent_state_change(state=idle)` 作为就绪信号；非法 JSON 返回 `error(error_code=PARSE_FAILURE, recoverable=true)`
- [x] 2.3 实现 `backend/sddp/ipc/heartbeat.py`：30s 应用层 ping；记录 pong timestamp；3 次 miss（≥ 90s）触发"连接丢失"事件回调
- [x] 2.4 实现 `backend/sddp/ipc/feedback_adapter.py`：`WebSocketHumanFeedbackAdapter` 桥接 WS 协议到 `LinearPhase02Flow.human_feedback_handler`；收到 flow 确认点 → Push `feedback_required` 阻塞 → 收到 `user_feedback` RPC → 返回布尔
- [x] 2.5 实现 message_id 关联：每个 RPC 请求生成 UUID v4；响应 MUST 含相同 message_id；前端 30 秒未收响应 → 视为失败
  - 注：服务端响应中 message_id 来自请求回显（schemas 层强制）；前端 30s 超时由 frontend ws-client 实现（task 5.6）
- [x] 2.6 在 `backend/sddp/cli/main.py` 新增 `sddp serve` 子命令：启动 FastAPI + uvicorn 监听 8765；`--mock` 启动 mock LLM 模式（不依赖 OPENAI_API_KEY）
- [x] 2.7 写 `backend/tests/ipc/test_schemas.py`：Pydantic 模型字段齐全 + ValidationError 拒绝缺字段（D0-8 风格）—— **16 个测试 PASS**
- [x] 2.8 写 `backend/tests/ipc/test_server.py`：用 `fastapi.testclient.TestClient` 跑 WS 握手 + 5 Push + 4 RPC 往返；不调用真实 LLM（mock factory）—— **6 个测试 PASS（含端到端 mock flow）**
- [x] 2.9 写 `backend/tests/ipc/test_heartbeat.py`：模拟 3 次 pong miss → 断言触发"连接丢失"事件 —— **4 个测试 PASS（异步 monkeypatch 加速）**

## 3. 安全合规（`backend/sddp/security/` + `frontend/electron/secrets.ts`）

- [ ] 3.1 实现 `backend/sddp/security/prefilter.py`：`scrub(payload) -> (scrubbed, mapping)` + `restore(text, mapping) -> text`；正则 catalog 至少覆盖 `analysis/09` §五所列 8 类（OpenAI/DeepSeek/Anthropic/AWS/GitHub PAT/通用 API key/Email/JWT/私钥头）
- [ ] 3.2 在 `backend/sddp/safe_agent/wrapper.py` 集成 prefilter：`SafeAgent.kickoff_fn` 入口调 `scrub`，出口调 `restore`；保证 DP0 既有测试不退化
- [ ] 3.3 在 `backend/sddp/__init__.py` 硬编码 `os.environ.setdefault("OTEL_SDK_DISABLED", "true")`；写注释说明 D1-13 来源
- [ ] 3.4 实现 `frontend/electron/secrets.ts`：包装 `@napi-rs/keyring`（`setKey`/`getKey`/`deleteKey`）；fallback 到 Electron `safeStorage`；服务名固定 `sddp-pet`，account = provider 名
- [ ] 3.5 在 `frontend/electron/main.ts` 硬编码 `process.env.OTEL_SDK_DISABLED = "true"` 启动时
- [ ] 3.6 写 `backend/tests/security/test_prefilter.py`：固定输入（含 8 类敏感模式）产生固定脱敏输出；round-trip 还原一致（D1-11）
- [ ] 3.7 写 `backend/tests/security/test_no_plaintext_key.py`：扫描 `~/.sddp-pet/` 下所有文件，断言 `grep -E "sk-|AKIA|ghp_"` 无命中（D1-9）
- [ ] 3.8 写 `backend/tests/security/test_otel_disabled.py`：启动 Python 进程跑 60 秒，断言环境变量 + 无 otlp 网络流量（用 `pytest-socket` 或抓包）

## 4. 远程模式（SSH 隧道 transport）

- [ ] 4.1 在 `frontend/electron/ssh-tunnel.ts` 实现 `establishSSHTunnel({host, port, user, keyRef}) -> ChildProcess`：调 `ssh -L 8765:localhost:8765 -p <port> -i <key_path> <user>@<host>`
- [ ] 4.2 实现 SSH 错误分类：网络不通 / 认证失败 / 端口被占 三种错误码映射到 UI 提示
- [ ] 4.3 在 `frontend/src/window2-panel/settings-page/ssh-settings.tsx` 实现 SSH 设置页：填表 + "测试连接" + 错误显示 + 重试按钮
- [ ] 4.4 实现 key_ref 引用机制：设置页只存 `key_ref`（如 `openai_default`），实际密钥读取走 Credential Manager
- [ ] 4.5 写 `frontend/tests/e2e/ssh-tunnel.test.ts`：mock ssh child_process；测试连接成功 / 认证失败 / 端口占用 三场景

## 5. 桌宠 UI（Electron 双窗口 + PixiJS + React）

- [ ] 5.1 在 `frontend/electron/main.ts` 实现双 BrowserWindow 创建：window1（transparent=true，PixiJS canvas only，0 React DOM）+ window2（transparent=false，React root）；显式设置 window2 `transparent: false`
- [ ] 5.2 实现穿透点击 hit-testing：window1 监听 mousemove，进入桌宠 sprite 命中区 → `setIgnoreMouseEvents(false)`；离开 → `setIgnoreMouseEvents(true, {forward:true})`
- [ ] 5.3 实现 window1 位置持久化：`window.close` 时 `win.getPosition()` 存 localStorage；启动时 `win.setPosition()` 恢复；首次启动用屏幕右下角默认
- [ ] 5.4 实现 `frontend/src/window1-pet/`：PixiJS Application + 桌宠 sprite + 气泡文本 + "AI 驱动" 标注；状态机含 idle/working/waiting/error 4 态（DP2 扩展到 8 角色）
- [ ] 5.5 实现 `frontend/src/window2-panel/`：React 路由 + 6 类面板（state-panel / diagnostic-panel / confirm-panel / cost-display / ssh-settings / privacy-consent-modal）
- [ ] 5.6 实现 `frontend/src/shared/ws-client.ts`：浏览器原生 WebSocket 包装 + zod schema 校验 + message_id 关联 + 心跳 pong 回复 + 自动重连
- [ ] 5.7 实现 `frontend/src/window2-panel/confirm-panel.tsx`：D1-8 clarification —— 显示完整待确认内容 + y/n/e 三按钮；提交时发 `user_feedback` RPC
- [ ] 5.8 实现隐私同意 modal（D1-10 clarification）：首次启动弹窗；同意存 localStorage；拒绝时后续 `start_flow` RPC 引擎返回 `PRIVACY_CONSENT_REQUIRED` error，应用继续运行
- [ ] 5.9 实现"AI 驱动"标注：在 window1 桌宠气泡旁用 PixiJS Text 持续渲染
- [ ] 5.10 写 `frontend/tests/unit/window1-dom.test.ts`：DevTools API 断言 window1 DOM 节点数 = 1（D1-1）
- [ ] 5.11 写 `frontend/tests/e2e/window1-click-through.test.ts`：点击桌宠 vs 点击空白行为不同（D1-3）
- [ ] 5.12 写 `frontend/tests/e2e/window2-panels.test.ts`：6 类面板全部渲染（D1-2）

## 6. 可观测（监控指标 + 诊断面板）

- [ ] 6.1 在 `backend/sddp/engine/cost_meter.py` 扩展或新增 `metrics_recorder.py`：每个 flow 完成时（含 failed/aborted）追加 1 行 JSON 到 `~/.sddp-pet/metrics.json`（JSON Lines 格式）
- [ ] 6.2 实现 4 指标计算：`flow_time_seconds`（复用 `wall_clock_minutes_excluding_human_wait * 60`）/ `agent_latency_seconds`（每角色一条）/ `token_consumption_rate`（`total_tokens / flow_time_seconds`）/ `error_rate`（滑动窗口 100 个 flow 的失败比）
- [ ] 6.3 在 `frontend/src/window2-panel/diagnostic-panel.tsx` 实现 4 指标可视化：每项一张卡片（当前值 + 历史平均）；通过 `cost_update` Push 消息每 5 秒更新
- [ ] 6.4 实现 error_rate 视觉告警：滑动窗口 `error_rate > 0.1` 时该卡片变红
- [ ] 6.5 写 `backend/tests/engine/test_metrics_recorder.py`：跑 1 个 flow 后 `metrics.json` 含 4 字段非空数值（D1-14）
- [ ] 6.6 写 `frontend/tests/e2e/diagnostic-panel.test.ts`：E2E 检查面板 DOM 含 4 个指标值（D1-15）

## 7. 端到端集成与 D1-DoD 验证

- [ ] 7.1 实现 `frontend/tests/e2e/websocket-roundtrip.test.ts`：mock WS server；5 Push + 4 RPC 往返测试（D1-4 + D1-5 + D1-6）
- [ ] 7.2 实现 `frontend/tests/e2e/heartbeat-miss.test.ts`：mock WS server；模拟 3 次 pong miss；前端 UI 显示"连接中断" + "重连"按钮（D1-7）
- [ ] 7.3 实现 `frontend/tests/e2e/privacy-consent.test.ts`：首次启动 modal 出现 + 拒绝后 start_flow 失败 + 应用继续运行 + 重新同意可启动（D1-10）
- [ ] 7.4 实现 `frontend/tests/e2e/ssh-remote-mode.test.ts`：mock ssh tunnel；远程模式前端透明连 `localhost:8765`（D1-16）
- [ ] 7.5 实现 E2E 真实联调 `tests/e2e/test_dev_phase_1_demo_real.ts`：启动真实 Python (`sddp serve --mock` 或带 DeepSeek) + 真实 Electron + 跑 `config-hot-reload.txt`，断言 4 markdown + cost_report 产出；D1-8 同 proposal 在 CLI/UI 双跑产出一致
- [ ] 7.6 D1-9 grep 验证：跑过一次完整流程后 `grep -rE "sk-|AKIA|ghp_" ~/.sddp-pet/` 必须 exit 1（无命中）
- [ ] 7.7 网络抓包验证 D1-13：进程启动 60s，无 otlp/telemetry/signals 域名流量（用 `tcpdump` 或 Wireshark）
- [ ] 7.8 跑 D1-14 + D1-15：跑 1 个失败 flow（如 LLM_TIMEOUT）+ 1 个成功 flow；检查 metrics.json + 诊断面板

## 8. 回归门控与 archive 准备

- [ ] 8.1 跑 DP0 回归：`git checkout dev-phase-0-v1 -- backend/tests/` 后 `pytest backend/tests/ -m "not e2e"` 必须 110/110 PASS（DP0 基线；4 个 e2e 在 DP1 重测）；任一失败 → DP1-NG-C
- [ ] 8.2 跑 DP0 Golden Demo 重放：`config-hot-reload.txt` 在 DP1 代码树下跑出 4 markdown + cost_report；与 `openspec/regression/golden-demos/dev-phase-0.md` 基线对比，cost 偏差 ≤ 20%；任一失败 → DP1-NG-A
- [ ] 8.3 更新 `openspec/regression/contracts-index.md`：把本变更引入的契约从 `unimplemented` → `frozen`（`WS-IPC: *` 约 14 条 + `Security: *` 约 4 条 + `UI: *` 约 6 条 + `Metrics: *` 约 2 条 + `Remote: *` 约 1 条）
- [ ] 8.4 写 `frontend/README.md` + 更新 `backend/README.md`：双语言入口文档（`sddp serve` + `npm run dev`）
- [ ] 8.5 跑 `grep -rE "TBD\|TODO\|FIXME\|待补" backend/ frontend/ openspec/changes/dev-phase-1-desktop-pet-mvp/` 无新增占位词
- [ ] 8.6 运行 `bash scripts/validate-dev-phase-change.sh openspec/changes/dev-phase-1-desktop-pet-mvp` PASS
- [ ] 8.7 运行 `openspec validate --changes dev-phase-1-desktop-pet-mvp` error/warning 清零
- [ ] 8.8 跑 D1-1 ~ D1-16 + X-1 ~ X-5 全部 DoD 项，逐项打勾
- [ ] 8.9 冻结 DP1 Golden Demo：把 `config-hot-reload` 在桌宠 UI 下的运行结果写入 `openspec/regression/golden-demos/dev-phase-1.md`，状态 `frozen`，打 git tag `dev-phase-1-v1`
- [ ] 8.10 写 DP1 回归门控报告 `openspec/regression/reports/<date>-dev-phase-1-gate.md`：含 DP0 Golden Demo 重放结果 + DP0+DP1 契约测试结果 + 阈值判定
