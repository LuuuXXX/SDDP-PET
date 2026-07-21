## Context

Dev-Phase 0 已 archive（commit `50528b1`，tag `dev-phase-0-v1`），冻结了一个可工作的 SDDP 引擎：5 角色 CrewAI 线性 Flow + KG-MVP + SafeAgent wrapper + CLI runner + @persist 中断恢复。但当前唯一入口是 `sddp run` 命令行 —— 每个确认点阻塞 stdin、每个成本更新打印到 stdout、每个产出落盘到 `out/`。这只能服务开发者，无法服务 SDDP-Pet 真正的目标用户（开发者身边的同事 / 设计师 / 产品经理）。

Dev-Phase 1 的核心命题：**把引擎装进桌宠**。具体三件事：
1. **UI 化** —— Electron 双窗口 + PixiJS 桌宠 + React 面板，覆盖 D1-1~D1-8 + D1-12 + D1-15
2. **安全合规** —— API 密钥加密存储、代码预过滤脱敏、隐私同意、AI 标注、OTEL 禁用，覆盖 D1-9~D1-13
3. **远程可达** —— SSH 隧道让"Linux 服务器跑引擎 + Windows 桌面跑 UI"可行，覆盖 D1-16 + 可观测 D1-14

**关键依赖**（已就位）：
- DP0 baseline (`dev-phase-0-v1` tag)：5 角色流 + KG + cost meter + @persist
- 3 份 DP1 调研（commit `65ea40e`）：`analysis/07`（Electron/PixiJS）、`analysis/08`（WS 契约）、`analysis/09`（密钥存储）
- DP0 Golden Demo：`openspec/regression/golden-demos/dev-phase-0.md`（重放基线）

**关键约束**：
- 工具链切换：项目首次引入 TypeScript + npm（之前纯 Python）；CI/lint 策略需双语言
- 不破坏 DP0 契约：17 条 frozen 契约任一改动 → DP1 Go 阻断
- Windows 优先 + 跨平台开发：Credential Manager / Keychain / libsecret 抽象必须从 day 1 就位

## Goals / Non-Goals

**Goals:**
- 用户能通过桌宠 UI（不打开终端）跑通一个 SDDP 流程并收到 4 markdown + cost 显示
- API 密钥永不上盘（明文）；`grep -r "sk-" ~/.sddp-pet/` 返回空
- 同一份 proposal 在 CLI 与 UI 下产出相同文档集（验证 WS adapter 不破坏 DP0 流程）
- 远程模式可用：Linux 服务器跑引擎 + Windows 客户端跑 UI 经 SSH 隧道通信
- 4 项监控指标可采集 + 诊断面板可视化
- 不退化 DP0 既有能力（115 个测试全 PASS，3 个 fixture proposal 仍跑通）

**Non-Goals:**
- ❌ Live2D 桌宠渲染（DP4 可选）
- ❌ 8 角色桌宠动画状态机（DP2 引入挑评师/实证师 + DP3b 引入验收师/复核师/规范员/修缮师）
- ❌ 对抗 Flow UI（DP2 引入 Phase 1 对抗）
- ❌ SandboxedExecutor / FileWriteProxy / RuleMapper（DP3a）
- ❌ Tier-C 离线 provider / Ollama 集成（DP5）
- ❌ i18n / 多语言提示词（DP5）
- ❌ Tauri 迁移 / VSCode 扩展（DP4 评估）
- ❌ Modern SSH 替代（Tailscale Funnel / cloudflared）—— 评估结论见 `analysis/08` §七，DP1 维持原生 SSH

## Decisions

### 决策 1：双窗口分离（PixiJS vs React）而非单窗口混渲染

依据 `analysis/07` 第三节对 `analysis/00` §六 baseline 的复核。**选择**：window1 纯 PixiJS（0 React DOM），window2 React。**理由**：PixiJS Canvas 与 React DOM 事件系统冲突，混窗口在 Electron 透明窗下事件穿透行为不稳定。**替代方案**：(a) 单窗口 React 内嵌 PixiJS Canvas —— 否决，因 hit-testing 与 React 事件委托冲突；(b) 全 PixiJS（含面板） —— 否决，因 PixiJS 写表单/列表成本高且 a11y 差。**代价**：双窗口位置需独立持久化（已在 `desktop-pet-ui` spec 落实）。

### 决策 2：WebSocket 库用 FastAPI 内置 + Electron 原生 WebSocket，不引入 socket.io /.ws 等额外抽象

依据 `analysis/08` §二。**选择**：服务端 FastAPI WebSocket（`uvicorn[standard]==0.51.0`，DP0 lockfile 既有 → promote 为直接依赖；`fastapi==<patch-TBD>` 由 `analysis/08` §2.3 验证脚本在 DP1 day-0 选定）；客户端 Electron renderer 进程的浏览器原生 `WebSocket`。**理由**：消息契约通过 Pydantic v2 + zod 双向校验，不需要 socket.io 的 room/retry/namespace 等额外能力；少一层抽象 = 少一处版本风险。**代价**：心跳/重连需手写（已在 `websocket-ipc` spec 落实）。

### 决策 3：心跳用应用层 JSON 而非 RFC 6455 协议帧

依据 `analysis/08` §5.1 实测：Starlette 的 WebSocket 包装层**不暴露**协议层 ping/pong API。**选择**：`{"type":"ping"}` / `{"type":"pong"}` 应用层消息。**代价**：协议帧本可省 100 字节/次 + 由内核维护，应用层多耗微秒级 CPU + 由 user-space 超时器维护 —— 在 30s/10s/3-miss 量级下完全可接受。**对 D1-7 DoD 文本的调整**：原文 "30s ping" 未明确协议层 vs 应用层，本变更新增 clarification 写入 `websocket-ipc` spec。

### 决策 4：密钥存储用 `@napi-rs/keyring`，弃用 `keytar`，备选 Electron `safeStorage`

依据 `analysis/09` §二。**选择**：`@napi-rs/keyring ^1.0.0` 主路径 + Electron 内置 `safeStorage` API fallback。**理由**：`keytar`（Atom org）已 archived，2026-07 不再维护；`@napi-rs/keyring` 由 napi-rs 组织维护，活跃度满足。**代价**：`@napi-rs/keyring` 在 Linux 需要 `gnome-keyring` 或 `kwallet` 运行；开发者机器若无可信 secret service，需 fallback 到 `safeStorage`。**DP1 day-0 验证**：`npm view @napi-rs/keyring` 必须 ≥ 1.0.0，且 GitHub repo 必须 30 天内有 commit（避免再次踩 keytar 雷）。

### 决策 5：代码预过滤用正则 catalog + 内存映射，不做密码学级脱敏

依据 `analysis/09` §五。**选择**：`sddp/security/prefilter.py` 用一组正则识别疑似 secret/PII → 替换为占位符 → 映射存内存 → LLM 返回后 reverse-substitute 还原。**理由**：MVP 用户场景是开发者把自有代码发给自己的 LLM；正则脱敏已能挡掉 90%+ 的"密钥意外泄漏"，复杂密码学脱敏（如 format-preserving encryption）投入产出比低。**代价**：正则脱敏对混淆/拆分/编码绕过无效（已接受风险，见 Risks）；DP4 可考虑引入 secret-scanning-as-a-service 替代。

### 决策 6：实施顺序为 IPC → 安全 → UI → 远程 → 可观测（依赖关系驱动）

依据 5 个 capability 的依赖关系。**选择顺序**：
1. **IPC**（`backend/sddp/ipc/`）：消息契约 + Pydantic 模型 + WS server + WebSocketHumanFeedbackAdapter —— 先把契约钉死，UI 与安全都依赖它
2. **安全**（`backend/sddp/security/` + `frontend/electron/secrets.ts`）：prefilter + keyring —— 可与 IPC 并行；prefilter 必须在 IPC 集成前完成
3. **UI**（`frontend/`）：Electron 双窗口 + PixiJS + React 面板 + ConfirmPanel —— 依赖 IPC 契约 + keyring API
4. **远程**：SSH 隧道 —— 收尾，依赖 UI 设置页
5. **可观测**：metrics.json + 诊断面板 —— 收尾，依赖 UI

**理由**：契约先行避免 IPC/UI/安全三方相互返工；安全先于 UI 是因 prefilter 在 IPC 集成点必须就位。**代价**：UI 工程量最大却最晚启动 —— 但 UI 不阻塞契约验证（前端可用 mock WS server 独立开发）。

### 决策 7：测试策略——IPC/UI 双层 mock + DP0 契约回归不放松

依据 `analysis/03` §九 测试策略延展。**选择**：
- **IPC 契约层**：纯 Python，用 `fastapi.testclient` + 真实 WS 握手；不调用真实 LLM（DP0 mock factory 复用）
- **UI 层**：Electron 用 `@playwright/test` + 模拟 WS server；不启动真实 Python 引擎
- **E2E 真实联调**：仅 1 个测试 `tests/e2e/test_dev_phase_1_demo_real.ts` —— 启动真实 Python + 真实 Electron + DeepSeek，跑 `config-hot-reload.txt`，断言 4 markdown 产出
- **DP0 回归不放松**：archive 前 MUST 跑 `pytest backend/tests/ -m "not e2e"` 全 PASS（115 个测试）+ 重放 DP0 Golden Demo

**代价**：UI 测试覆盖率不会太高（Electron 测试慢 + flaky）；E2E 真实联调单点（与 DP0 同样策略，可控）。

### 决策 8：DP1 验证基线继续用 DeepSeek Tier-B（继承 DP0 决定），不要求 Tier-S

依据 `analysis/04` + DP0 经验（DP0 在 DeepSeek 下 18/18 合规 = 100%）。**选择**：DP1 Go 判定继续接受 DeepSeek Tier-B provisional baseline；OpenAI Tier-S 仍为官方基线但**不阻断** DP1 archive。**理由**：DP1 引入的新 LLM 调用极少（基本是把 DP0 的 5 角色流包到 WS 后面），D1-13 (DP0 的合规率) 在 DP1 上仍由 DP0 测试覆盖。**代价**：DP0 已标注的 Tier-B provisional caveat 在 DP1 持续。

## Risks / Trade-offs

| ID | 风险 | 缓解 |
|----|------|------|
| DP1-R1 | `@napi-rs/keyring` 在某些 Linux 桌面（无 `gnome-keyring`）下不可用 | fallback 到 Electron `safeStorage`；启动时探测并日志告警；CI 跑 macOS + Windows + Ubuntu 三平台 |
| DP1-R2 | Electron 透明窗 + click-through 在 Linux 下行为与 Windows 不一致（X11 vs Wayland） | Windows 是主目标，Linux/macOS 仅作开发支持；D1-3 测试场景在 Windows 上严格断言，Linux 上仅冒烟 |
| DP1-R3 | 正则 prefilter 被绕过（混淆/编码/拆分）导致真实密钥泄漏到 LLM provider | 文档明示"非密码学级脱敏"（已接受风险）；regex catalog 维护 gitleaks 公开规则集更新；DP4 评估 secret-scanning service |
| DP1-R4 | FastAPI 版本升级 bump starlette/uvicorn/websockets 导致 DP0 lockfile 漂移 | `analysis/08` §2.3 验证脚本在 DP1 day-0 必须跑通；`requirements.lock.txt` diff 在 PR 审查时强制 review |
| DP1-R5 | WS 消息契约冻结后发现需新增字段（如 DP2 加对抗维度） → breaking change | archive 时契约 frozen；后续变更走 `openspec/specs/regression-strategy/spec.md` 的"跨阶段接口变更"流程，含迁移期 |
| DP1-R6 | 远程 SSH 隧道在 NAT/防火墙后不稳定 | 文档明示"需要 SSH 可达"；连接失败显示具体错误 + 重试；不引入额外穿透工具 |
| DP1-R7 | Electron + React + PixiJS + Vite 多工具链首次组装，版本冲突可能严重 | `analysis/07` 已锁定 5 个核心版本；DP1 day-0 必须先 `npm install && npm run build` 通过再开始 feature 开发 |
| DP1-R8 | 双窗口位置在某些显示器切换 / DPI 变化下错位 | localStorage 保存 logical 坐标；启动时做边界检查（坐标出屏 → 复位到默认） |

## DoD Checklist

### 跨阶段通用 DoD（依据 `dod.md` 第一节）

- [ ] **X-1 文档更新**：本阶段涉及的 `analysis/07-09` / 各 capability spec / `contracts-index.md` 同步；`grep -r "TBD\|TODO\|待补" backend/ frontend/ openspec/` 在本变更范围内无新增命中
- [ ] **X-2 测试通过**：`pytest backend/tests/ -m "not e2e"` 退出码 0（DP0 115 测试不退化）+ `cd frontend && npm test` 退出码 0
- [ ] **X-3 成本实测**：桌宠 UI 模式下跑 `config-hot-reload.txt` 端到端，`cost_report.json.measured_cost_usd` 与 DP0 CLI 模式相差 ±20%（WS + prefilter 不应显著抬高成本）
- [ ] **X-4 已知风险登记**：本阶段新发现风险（如有）写入 `analysis/00-sddp-pet-final.md` 风险矩阵 + `accepted-risks.md`（DP1-R1~R8 中实际触发的）
- [ ] **X-5 回归无退化**：DP0 Golden Demo 重放通过（`config-hot-reload.txt` 在 DP1 代码树下跑出 4 markdown + cost_report 与基线一致）

### Dev-Phase 1 DoD（依据 `dod.md` Dev-Phase 1 节）

- [ ] **D1-1 窗口1（透明，PixiJS 桌宠 + 气泡）**：DevTools 检查 window1 DOM 节点数 = 1（仅 canvas）；"AI 驱动" 标注可见
- [ ] **D1-2 窗口2（不透明，React 面板）**：状态 / 诊断 / 确认按钮 / 成本 / SSH 设置 / 隐私同意 6 类面板全部渲染
- [ ] **D1-3 穿透点击**：E2E `tests/e2e/window1-click-through.test.ts` —— 点击桌宠 vs 空白行为不同
- [ ] **D1-4 WS server ↔ Electron client**：`tests/e2e/websocket-roundtrip.test.ts` 双向消息可发收
- [ ] **D1-5 5 Push 消息渲染**：5 个 E2E 场景全部触发 UI 更新
- [ ] **D1-6 4 RPC 请求**：4 个 E2E 场景，引擎收到正确消息
- [ ] **D1-7 心跳（应用层 JSON）**：30s ping / 10s pong / 3-miss 触发"连接丢失" —— 模拟测试通过
- [ ] **D1-8 确认点桌宠气泡化**：同一 proposal 在 CLI 与 UI 下产出相同文档集（spec clarification：window1 提示 + window2 ConfirmPanel 按钮）
- [ ] **D1-9 密钥加密存储**：`grep -r "sk-" ~/.sddp-pet/` 无命中；密钥读取走 `@napi-rs/keyring` API
- [ ] **D1-10 隐私同意界面**：首次启动弹窗 + 拒绝后应用继续运行（spec clarification：拒绝仅 reject start_flow RPC）
- [ ] **D1-11 代码预过滤**：`pytest tests/security/test_prefilter.py` 固定输入产生固定脱敏输出
- [ ] **D1-12 AI 标注**：UI 检查桌宠气泡旁"AI 驱动"标注可见
- [ ] **D1-13 OTEL 禁用**：`OTEL_SDK_DISABLED=true` 硬编码；进程启动 60s 无 otel 域名流量
- [ ] **D1-14 4 指标采集**：跑一个流程后 `metrics.json` 含 4 字段非空数值
- [ ] **D1-15 诊断面板展示**：E2E 检查面板 DOM 含 4 个指标值
- [ ] **D1-16 SSH 隧道**：手工配置 SSH → 启动远程引擎 → 前端可发 RPC；连接失败有重试按钮

## No-Go Rollback Plan

### Dev-Phase 1 No-Go 条件与监控

| No-Go ID | 触发条件 | 监控方式 | 触发后执行 |
|----------|---------|---------|-----------|
| DP1-NG-A | DP0 Golden Demo 重放失败（4 markdown 之一缺失或 cost 偏离 > 20%） | X-5 + 任务 9.5 重放测试 | 阻断 DP1 archive；定位是 IPC adapter 破坏 DP0 flow / 还是 DP0 契约被意外修改；前者修 IPC，后者按 DP0 spec 回滚 |
| DP1-NG-B | D1-9 grep 验证失败（密钥明文上盘） | 任务 7.6 + `tests/security/test_no_plaintext_key.py` | **Hard No-Go** —— 阻断 archive；定位泄漏点（配置文件 / 日志 / 临时文件）；修复后重新跑 D1-9 |
| DP1-NG-C | DP0 契约测试退化（`pytest backend/tests/` 出现 FAIL） | X-2 + 任务 9.3 | 阻断 archive；定位退化 PR；要么修复回归，要么修订 DP0 spec（后者需重启 spec 变更流程） |
| DP1-NG-D | D1-7 心跳机制无法在 3-miss 内稳定触发连接丢失 | 任务 4.5 心跳模拟测试 | 阻断 archive；评估是否需要改用协议层 ping（推翻决策 3） |
| DP1-NG-E | `@napi-rs/keyring` 在 Windows Credential Manager 上不可用 | 任务 7.1 day-0 验证 | 切换到 Electron `safeStorage` 主路径；重新跑 D1-9 |
| DP1-NG-F | Electron 透明窗在 Windows 11 上 click-through 失效 | 任务 5.3 D1-3 测试 | 阻断 archive；评估是否需要主进程原生 hook（Windows SetWindowLong）替代 `setIgnoreMouseEvents` |
| DP1-NG-G | FastAPI 升级导致 starlette/uvicorn/websockets 漂移，DP0 lockfile 损坏 | 任务 1.2 + `analysis/08` §2.3 验证脚本 | 锁定更老 FastAPI patch；若不可行则放弃 FastAPI 改用 starlette 直接 |

### 触发后的统一执行流程

1. **立即标记**：在 `design.md` 本节标注触发日期 + No-Go ID；在 `openspec/regression/reports/` 写当次报告
2. **分支策略**：在 git 上创建 `dev-phase-1-nogo-<ID>` 分支保留现场；主分支回滚到 No-Go 触发前的 commit
3. **修复窗口**：每个 No-Go 最多 3 个工作日修复；超期转为"Dev-Phase 1 范围调整"（裁剪对应 capability 或推迟到 DP2）
4. **重测**：修复后必须重跑 X-1~X-5 + 触发的 D1-* 项；通过后方可推进 archive

### 已接受风险（依据 `accepted-risks.md`，本阶段首次暴露的 2 项）

- **DP1-R3 正则 prefilter 非密码学级**：在 `accepted-risks.md` 新增项 AR-5；用户文档明示"不要发送高敏感代码到任何 LLM，包括本工具"
- **DP1-R2 Linux/macOS 桌面 UI 行为差异**：在 `accepted-risks.md` 新增项 AR-6；Windows 11 是唯一保证全 DoD 通过的平台，其他平台仅冒烟
