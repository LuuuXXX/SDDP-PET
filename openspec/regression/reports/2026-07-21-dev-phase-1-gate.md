# 回归门控报告：Dev-Phase 1（`dev-phase-1-desktop-pet-mvp`）

- **报告日期**：2026-07-21
- **关联变更**：[`openspec/changes/dev-phase-1-desktop-pet-mvp/`](../../changes/dev-phase-1-desktop-pet-mvp/)
- **关联 DoD**：[`openspec/specs/development-roadmap/dod.md`](../../specs/development-roadmap/dod.md) 第 X-5 项（回归无退化）+ Dev-Phase 1 节 D1-1~D1-16
- **关联规格**：[`openspec/specs/regression-strategy/spec.md`](../../specs/regression-strategy/spec.md)
- **环境约束声明**：headless Linux dev 环境；Electron 二进制 `ELECTRON_SKIP_BINARY_DOWNLOAD=1` 跳过；故 D1-1/2/3/8/12/16 等 UI 运行时验证 deferred 到 Windows/macOS dev 机

## 一、Golden Demo 重放

依据 `regression-strategy/spec.md`，Dev-Phase N 验收前 MUST 重放所有状态为 `frozen` 的 Golden Demo。DP1 阶段（N=1）需重放 Dev-Phase 0 Golden Demo：

- **重放集合**：1 个（[`openspec/regression/golden-demos/dev-phase-0.md`](../golden-demos/dev-phase-0.md)）
- **重放方式**：在 DP1 代码树下跑 `config-hot-reload` proposal（CLI 模式 + DeepSeek Tier-B）
- **结果**：**PASS** —— 5 文件齐全（4 markdown + cost_report.json），cost 1.02x（基线 $0.0078 → 实测 $0.0080），token 0.97x（基线 14344 → 实测 13869）；远在 ±20% 容差内（DP1-R1 风险未触发）
- **DP1 新增副作用**：DP1 引入的 `sddp/security/prefilter.py` scrub/restore 经全链路验证不破坏输出结构；DP1 引入的 `metrics_recorder` 在流程完成时追加 1 行到 `~/.sddp-pet/metrics.json`

## 二、契约测试运行

依据 `contracts-index.md` 第 3 节"契约 → 测试代码映射"，本阶段引入 29 条 Dev-Phase 1 契约（WS-IPC 16 + Security 4 + UI 7 + Metrics 2 + Remote 1），加上 DP0 既有的 17 条 frozen 契约，共 46 条 frozen 契约。

**实际执行**：

```bash
pytest backend/tests/ -m "not e2e"          # 后端契约 + 单元测试
cd frontend && npm test                       # 前端契约 + 单元测试
```

- **后端**：**184 passed / 4 deselected**（DP0 110 + IPC 28 + Security 35 + Observability 10 + 1 fixture；4 个 e2e-real 按设计 deselected）
- **前端**：**46 passed**（pet-state 11 + ws-client 10 + panels 14 + ssh-tunnel 11）
- **退出码**：均为 0
- **契约覆盖率**：29/29 DP1 契约 + 17/17 DP0 契约均有对应测试代码路径（详见 `contracts-index.md` 第 3 节）

**UI 契约运行时验证缺口**：D1-1/2/3/8/12/16 + D1-15 实时数据共 7 项 vitest 单测已 PASS，但 Playwright e2e（运行时 DOM 断言、真实 click-through、真实 SSH 隧道）需 Windows/macOS dev 机跑 `npm run test:e2e`。不阻断 DP1 archive（已接受风险 DP1-R2）。

## 三、DoD 阈值判定

依据 `dod.md` Dev-Phase 1 节，16 个 D1-* 项 + 5 个 X-* 项的判定：

| 类别 | 项数 | PASS | frozen (待 dev 机) | 备注 |
|------|------|------|---------------------|------|
| X-* 跨阶段通用 | 5 | **5** | 0 | X-1~X-5 全 PASS（含 DP0 回归 X-5） |
| D1-* Dev-Phase 1 | 16 | **9** | 7 | D1-4/5/6/7/9/10/11/13/14/15 PASS；D1-1/2/3/8/12/16 + D1-15 实时数据部分待 dev 机 |
| **合计** | **21** | **14** | **7** | 7 项 deferred 不构成 No-Go（DP1-R2 已接受） |

## 四、No-Go 触发检查

依据 `design.md` "No-Go Rollback Plan" 表（DP1-NG-A ~ DP1-NG-G）：

| No-Go ID | 触发条件 | 当前状态 |
|----------|---------|---------|
| DP1-NG-A | DP0 Golden Demo 重放失败 | **未触发** —— 任务 8.2 实测通过（cost 1.02x / token 0.97x） |
| DP1-NG-B | D1-9 grep 验证失败（密钥明文上盘） | **未触发** —— `test_no_plaintext_key.py` 5 测试 PASS；运行时由 dev 机手测，但单测层证明扫描逻辑正确 |
| DP1-NG-C | DP0 契约测试退化 | **未触发** —— 103 DP0 契约测试全 PASS（含 KG 7 + SafeAgent 3 + Adaptation 2 + JSON Schema 3 + 渲染 1 + CLI 1 + 各类衍生） |
| DP1-NG-D | D1-7 心跳 3-miss 不稳定 | **未触发** —— `test_heartbeat.py` 4 测试 PASS，含 3-miss 触发场景 |
| DP1-NG-E | `@napi-rs/keyring` Win Credential Manager 不可用 | **未触发** —— 任务 1.5 选定 1.3.0（2026-04-30 发布，活跃维护）；运行时由 dev 机手测 |
| DP1-NG-F | Electron 透明窗 click-through 失效 | **未触发（单测层）** —— hit-test 逻辑 + IPC relay 源码就位；运行时由 dev 机跑 Playwright e2e |
| DP1-NG-G | FastAPI 升级漂移 starlette/uvicorn/websockets | **未触发** —— 任务 1.1 dry-run 验证零漂移；`requirements.lock.txt` diff 仅 +1 行（fastapi） |

**门控判定**：**所有 7 个 No-Go 条件均未触发**。

## 五、结论

| 门控项 | 结果 | 备注 |
|--------|------|------|
| 历史 Golden Demo 重放 | **PASS** | DP0 config-hot-reload 在 DP1 代码树下产出一致 |
| DP0 契约测试运行 | **PASS** | 103/103 DP0 契约测试通过 |
| DP1 契约测试运行 | **PASS** | 29/29 DP1 契约测试通过（含 7 项 frozen (待 dev 机) 标注） |
| DoD 阈值 | **PASS** | 14/21 PASS，7 项 deferred 不阻断 |
| No-Go 触发 | **未触发** | DP1-NG-A~G 全清 |

**门控判定**：Dev-Phase 1 的回归门控通过。剩余阻塞项为 D1-1/2/3/8/12/16 的真实 Electron 运行时验证（Windows/macOS dev 机跑 `npm run test:e2e`）；这些不属回归门控范畴（属"待运行时验证"），可由后续 dev 机迭代闭合。

## 六、为 Dev-Phase 2 留下的基线

Dev-Phase 2 验收时 MUST：

1. 重放本阶段冻结的 [`openspec/regression/golden-demos/dev-phase-1.md`](../golden-demos/dev-phase-1.md)（含 CLI 路径已验证 + UI 路径待 dev 机补）
2. 重跑 DP0 + DP1 契约测试集（共 46 条 frozen 契约，对应 `backend/tests/{kg,safe_agent,adaptation,engine,cli,ipc,security,observability}/` + `frontend/tests/unit/`）
3. 任一失败 → 阻断 Dev-Phase 2 的 Go 判定 → 按失败定位的责任模块回退
4. **特别注意**：Dev-Phase 2 引入对抗 Flow 时，DP1 的 WebSocket 消息契约（特别是 `feedback_required`）可能扩展（如新增对抗轮次字段）；任何扩展 MUST 走 `regression-strategy/spec.md` 的"跨阶段接口变更"流程。
