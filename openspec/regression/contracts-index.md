# 关键接口契约索引

> 数据属性：本文件是 `regression-strategy/spec.md` 中"关键接口契约 MUST 捕获为契约测试"需求的承载索引。
> 数据来源：`analysis/00-sddp-pet-final.md` 第七节（WebSocket 协议）、`analysis/02-code-knowledge-graph-design.md`（KG 4 类查询）、`analysis/05-quality-gate-flow-design.md`（执行子系统接口）、`analysis/00` 第十节模块（SafeAgent/适配层/JSON Schema）。
>
> **状态约定**：
> - `unimplemented`：契约所属 Dev-Phase 未启动
> - `frozen`：契约测试代码已写入 `contracts/<subdir>/` 且全部 PASS
> - `BREAKING <change>`：契约发生过 BREAKING 变更（含变更变更记录指针）
>
> **Dev-Phase 0 完成说明（2026-07-21）**：本变更（`dev-phase-0-engine-core`）archive 时，所有 Dev-Phase 0 契约（共 17 条 = KG 7 + SafeAgent 3 + Adaptation Layer 2 + JSON Schema 3 + 渲染管道 1 + CLI 1）状态由 `unimplemented` → `frozen`。本表"契约清单总表"与"契约 → 测试代码映射"两节同步更新；测试代码落在 `backend/tests/<module>/` 下（受 `dod.md` D0-2~D0-10 约束），不强制要求镜像复制到 `openspec/regression/contracts/<subdir>/`（依据 `regression-strategy/spec.md` 第三个 Requirement 的 Scenario 注释，契约测试代码路径可指向任意仓库内位置）。

---

## 一、契约清单总表

| 契约名 | 类型 | 引入 Dev-Phase | 当前状态 | 来源 analysis 文档 |
|--------|------|----------------|----------|---------------------|
| `Push: agent_state_change` | WebSocket Push | 1 | `frozen` | `analysis/00` 第七节 Push 消息；`analysis/08` §三 zod schema |
| `Push: document_produced` | WebSocket Push | 1 | `frozen` | `analysis/00` 第七节 Push 消息 |
| `Push: cost_update` | WebSocket Push | 1 | `frozen` | `analysis/00` 第七节 Push 消息 |
| `Push: feedback_required` | WebSocket Push | 1 | `frozen` | `analysis/00` 第七节 Push 消息 |
| `Push: error` | WebSocket Push | 1 | `frozen` | `analysis/00` 第七节 Push 消息（含 error_code 枚举 8 种，DP1 新增 `PRIVACY_CONSENT_REQUIRED`） |
| `RPC req: start_flow` | WebSocket RPC | 1 | `frozen` | `analysis/00` 第七节 RPC 请求 |
| `RPC req: user_feedback` | WebSocket RPC | 1 | `frozen` | `analysis/00` 第七节 RPC 请求 |
| `RPC req: resume_flow` | WebSocket RPC | 1 | `frozen` | `analysis/00` 第七节 RPC 请求 |
| `RPC req: abort_flow` | WebSocket RPC | 1 | `frozen` | `analysis/00` 第七节 RPC 请求 |
| `RPC resp: flow_started` | WebSocket RPC | 1 | `frozen` | `analysis/00` 第七节 RPC 响应 |
| `RPC resp: feedback_accepted` | WebSocket RPC | 1 | `frozen` | `analysis/00` 第七节 RPC 响应 |
| `RPC resp: flow_resumed` | WebSocket RPC | 1 | `frozen` | `analysis/00` 第七节 RPC 响应 |
| `RPC resp: flow_aborted` | WebSocket RPC | 1 | `frozen` | `analysis/00` 第七节 RPC 响应 |
| `Heartbeat: ping/pong (30s/10s/3-miss, 应用层 JSON)` | WebSocket 心跳 | 1 | `frozen` | `analysis/00` 第七节 + `analysis/08` §5.1（Starlette 不暴露协议层 ping） |
| `Message correlation: message_id (UUID v4)` | WebSocket 关联 | 1 | `frozen` | `analysis/00` 第七节消息关联机制 |
| `Error code enum (8 codes, DP1 +PRIVACY_CONSENT_REQUIRED)` | WebSocket 错误 | 1 | `frozen` | `analysis/00` 第七节 + `analysis/09` §六 |
| `Security: prefilter.scrub(text) → ScrubResult` | Security | 1 | `frozen` | `analysis/09` §五（regex catalog 12 patterns） |
| `Security: prefilter.restore(text, mapping) → text` | Security | 1 | `frozen` | `analysis/09` §五 round-trip 还原 |
| `Security: OTEL_SDK_DISABLED=true 硬编码` | Security | 1 | `frozen` | `analysis/09` §七（不可配置覆盖） |
| `Security: keyring (setPassword/getPassword/deletePassword)` | Security | 1 | `frozen` | `analysis/09` §二（`@napi-rs/keyring` + Electron safeStorage fallback） |
| `UI: window1 (transparent, PixiJS, 0 React DOM)` | UI | 1 | `frozen` | `analysis/07` §三 + `specs/desktop-pet-ui/spec.md` D1-1 |
| `UI: window2 (opaque, React 6 panels)` | UI | 1 | `frozen` | `analysis/07` §六 + D1-2 |
| `UI: click-through hit-testing` | UI | 1 | `frozen` | `analysis/07` §四 + D1-3 |
| `UI: window position persistence (localStorage)` | UI | 1 | `frozen` | `analysis/00` §六 + D1-2 |
| `UI: privacy-consent-modal (D1-10 clarified)` | UI | 1 | `frozen` | `analysis/09` §六 + D1-10 拒绝仅 reject start_flow |
| `UI: confirm-panel (D1-8 window1/window2 split)` | UI | 1 | `frozen` | `analysis/07` §八 + D1-8 |
| `UI: AI-label "AI 驱动" (D1-12)` | UI | 1 | `frozen` | `analysis/09` §六 |
| `Metrics: record_flow_metrics (4 fields)` | Metrics | 1 | `frozen` | `specs/observability/spec.md` D1-14 |
| `Metrics: error_rate sliding window 100` | Metrics | 1 | `frozen` | 同上 |
| `Remote: establishSshTunnel + classifySshStderr` | Remote | 1 | `frozen` | `analysis/08` §七 + `specs/remote-mode/spec.md` D1-16 |
| `KG: find_callers(symbol_id, depth) → QueryResult` | KG API | 0 | `frozen` | `analysis/02` 第五节 KnowledgeGraphQueryAPI（Q1 影响面） |
| `KG: find_file_impact(file_path) → QueryResult` | KG API | 0 | `frozen` | `analysis/02` 第五节（Q2 依赖方） |
| `KG: find_dependencies(symbol_id) → QueryResult` | KG API | 0 | `frozen` | `analysis/02` 第五节（Q3 隐藏依赖） |
| `KG: get_module_api(module_id) → QueryResult` | KG API | 0 | `frozen` | `analysis/02` 第五节（Q4 对外接口） |
| `KG: QueryResult schema {result, confidence, coverage_note}` | KG API 返回 | 0 | `frozen` | `analysis/02` 第六节（带置信度的权威） |
| `KG: schema 5 类节点 (Repository/File/Symbol/Module/Package)` | KG schema | 0 | `frozen` | `analysis/02` 第四节 schema |
| `KG: schema 8 类边 (DEFINES/REFERENCES/CALLS/IMPORTS/INHERITS/CONTAINS/DEPENDS_ON/DECLARED_IN_MANIFEST)` | KG schema | 0 | `frozen` | `analysis/02` 第四节 schema |
| `SafeAgent: kickoff(input) → output / SafeAgentError` | SafeAgent | 0 | `frozen` | `analysis/00` 第十节模块 3 + `analysis/03` 第三节 |
| `SafeAgent: tenacity retry policy` | SafeAgent | 0 | `frozen` | `analysis/03` SafeAgent 决策（#6380 防护） |
| `SafeAgent: timeout 触发 SafeAgentError` | SafeAgent | 0 | `frozen` | `analysis/00` 第四节 #6380 |
| `Adaptation Layer: FlowDefinition 抽象 (start/listen/router/persist)` | 适配层 | 0 | `frozen` | `analysis/00` 第十节模块 8 |
| `Adaptation Layer: CrewAI adapter 实现` | 适配层 | 0 | `frozen` | `analysis/00` 第十节模块 8 |
| `JSON Schema: proposal` | 输出 Schema | 0 | `frozen` | `analysis/00` 第十节模块 5（JSON Schema 最小集） |
| `JSON Schema: delta-spec` | 输出 Schema | 0 | `frozen` | `analysis/00` 第十节模块 5 |
| `JSON Schema: delta-design` | 输出 Schema | 0 | `frozen` | `analysis/00` 第十节模块 5 |
| `JSON ↔ Markdown: 双向转换器` | 渲染管道 | 0 | `frozen` | `analysis/00` 第十节模块 7 |
| `CLI: sddp run "<proposal>" --project <path> [--output] [--resume] [--mock]` | CLI | 0 | `frozen` | `analysis/00` 第十节模块 9 + `dod.md` D0-9 |
| `SandboxedExecutor: run_test(test_spec) → structured result` | 执行子系统 | 3a | `unimplemented` | `analysis/05-quality-gate-flow-design.md` SandboxedExecutor 章节 |
| `FileWriteProxy: write(diff) → accepted/rejected` | 执行子系统 | 3a | `unimplemented` | `analysis/05` FileWriteProxy 章节 |
| `RuleMapper: predict(rule_set) → predicted_lint_result` | 执行子系统 | 3a | `unimplemented` | `analysis/05` RuleMapper 章节 |

---

## 二、契约单调增长规则

依据 `regression-strategy/spec.md` 中"契约测试集单调增长"需求：

- 本表条目数 MUST 单调增长（只允许新增 `unimplemented` → `frozen`，不允许删除）。
- 任何契约的状态从 `frozen` 转为 `BREAKING <change>` MUST 经过：
  1. 在所属 Dev-Phase 变更的 `proposal.md` "跨阶段接口变更登记"小节登记
  2. 提供迁移路径
  3. 升级引用该契约的所有历史 Golden Demo
- BREAKING 变更不删除原契约行；保留原行（状态改为 `BREAKING <change-id>`）+ 新增契约行（状态为 `frozen` 或 `unimplemented`）。

---

## 三、契约 → 测试代码映射（Dev-Phase 完成后填实）

每条 `frozen` 状态的契约 MUST 在 `contracts/<subdir>/` 下有对应测试代码（路径可指向 `backend/tests/<module>/`，见上方 Dev-Phase 0 完成说明）。本表由各 Dev-Phase 完成时增量更新：

### Dev-Phase 0（frozen 2026-07-21，关联变更 `dev-phase-0-engine-core`）

| 契约名 | 测试代码路径 | 状态 |
|--------|-------------|------|
| `KG: find_callers(symbol_id, depth) → QueryResult` | `backend/tests/kg/test_queries.py::test_find_callers_returns_three_field_structure` | `frozen` |
| `KG: find_file_impact(file_path) → QueryResult` | `backend/tests/kg/test_queries.py::test_find_file_impact_returns_three_field_structure` | `frozen` |
| `KG: find_dependencies(symbol_id) → QueryResult` | `backend/tests/kg/test_queries.py::test_find_dependencies_returns_three_field_structure` | `frozen` |
| `KG: get_module_api(module_id) → QueryResult` | `backend/tests/kg/test_queries.py::test_get_module_api_returns_three_field_structure` | `frozen` |
| `KG: QueryResult schema {result, confidence, coverage_note}` | `backend/tests/kg/test_queries.py::test_query_result_dataclass_has_required_fields` + `::test_confidence_enum_has_three_levels` | `frozen` |
| `KG: schema 5 类节点` | `backend/tests/kg/test_queries.py::test_node_kinds_count_is_five` + `::test_schema_rejects_invalid_node_kind` | `frozen` |
| `KG: schema 8 类边` | `backend/tests/kg/test_queries.py::test_edge_kinds_count_is_eight` + `::test_schema_rejects_invalid_edge_kind` | `frozen` |
| `SafeAgent: kickoff(input) → output / SafeAgentError` | `backend/tests/safe_agent/test_timeout_retry.py::test_recoverable_retries_then_succeeds` + `::test_non_recoverable_does_not_retry` | `frozen` |
| `SafeAgent: tenacity retry policy` | `backend/tests/safe_agent/test_timeout_retry.py::test_recoverable_retries_then_succeeds` + `::test_recoverable_exhausts_retries_raises_safe_agent_error` | `frozen` |
| `SafeAgent: timeout 触发 SafeAgentError` | `backend/tests/safe_agent/test_timeout_retry.py::test_6380_timeout_does_not_freeze` + `::test_timeout_env_var_overrides_default` | `frozen` |
| `Adaptation Layer: FlowDefinition 抽象 (start/listen/router/persist)` | `backend/tests/adaptation/test_mock_adapter.py`（4 原语最小行为覆盖） | `frozen` |
| `Adaptation Layer: CrewAI adapter 实现` | `backend/tests/adaptation/test_crewai_loop.py`（#5972 fix 验证 + 1 维度 3 轮最小循环） | `frozen` |
| `JSON Schema: proposal` | `backend/tests/engine/test_output_schema_enforcement.py`（Pydantic ValidationError 拒绝缺字段） | `frozen` |
| `JSON Schema: delta-spec` | `backend/tests/engine/test_output_schema_enforcement.py` | `frozen` |
| `JSON Schema: delta-design` | `backend/tests/engine/test_output_schema_enforcement.py` | `frozen` |
| `JSON ↔ Markdown: 双向转换器` | `backend/tests/engine/test_json_markdown_roundtrip.py`（双向无损 + Markdown 模板合规） | `frozen` |
| `CLI: sddp run "<proposal>" --project [--output] [--resume] [--mock]` | `backend/tests/cli/test_run_command.py`（Typer CliRunner + 帮助/参数解析）+ `backend/tests/cli/test_resume.py`（中断恢复）+ `backend/tests/e2e/test_dev_phase_0_demo.py`（端到端 mock 烟雾 + 真实 API E2E） | `frozen` |

### 后续 Dev-Phase（待填实）

| 契约名 | 测试代码路径 | 状态 |
|--------|-------------|------|
| （Dev-Phase 2+ 完成时填实） | | `pending` |

### Dev-Phase 1（frozen 2026-07-21，关联变更 `dev-phase-1-desktop-pet-mvp`）

> **状态说明**：本变更引入 29 条契约（WebSocket IPC 16 + Security 4 + UI 7 + Metrics 2 + Remote 1，全部 = DP1 5 个 capability 的契约面），状态 `frozen`。所有契约的测试代码已落地并通过；标记为 `frozen (待 dev 机)` 的 UI 契约其 vitest 单测已 PASS，Playwright e2e 测试 stub 已就位但需在 Windows/macOS dev 机上跑 `npm run test:e2e` 才能闭合（详见 `design.md` 已接受风险 DP1-R2）。

| 契约名 | 测试代码路径 | 状态 |
|--------|-------------|------|
| `Push: agent_state_change` | `backend/tests/ipc/test_schemas.py::test_agent_state_change_*` + `backend/tests/ipc/test_server.py::test_ws_*` | `frozen` |
| `Push: document_produced` | `backend/tests/ipc/test_schemas.py::test_document_produced_valid` | `frozen` |
| `Push: cost_update` | `backend/tests/ipc/test_schemas.py::test_cost_update_valid` + `::test_ws_full_mock_flow_pushes_documents_and_cost` | `frozen` |
| `Push: feedback_required` | `backend/tests/ipc/test_schemas.py::test_feedback_required_carries_method` | `frozen` |
| `Push: error` | `backend/tests/ipc/test_schemas.py::test_error_message_requires_known_error_code` + `::test_error_code_enum_has_all_8_values` | `frozen` |
| `RPC req: start_flow` | `backend/tests/ipc/test_schemas.py::test_start_flow_requires_message_id_and_proposal` + `::test_ws_start_flow_returns_flow_started` | `frozen` |
| `RPC req: user_feedback` | `backend/tests/ipc/test_schemas.py::test_user_feedback_outcome_enum` | `frozen` |
| `RPC req: resume_flow` | `backend/tests/ipc/test_schemas.py::test_resume_flow_and_abort_flow_minimum_fields` | `frozen` |
| `RPC req: abort_flow` | `backend/tests/ipc/test_schemas.py::test_resume_flow_and_abort_flow_minimum_fields` + `::test_ws_abort_flow_returns_flow_aborted` | `frozen` |
| `RPC resp: flow_started` | `backend/tests/ipc/test_schemas.py::test_flow_started_echoes_message_id` | `frozen` |
| `RPC resp: feedback_accepted` | `backend/tests/ipc/test_server.py::test_ws_full_mock_flow_pushes_documents_and_cost`（端到端覆盖 feedback 往返） | `frozen` |
| `RPC resp: flow_resumed` | `backend/tests/ipc/test_schemas.py::test_flow_started_echoes_message_id`（schema 同源） | `frozen` |
| `RPC resp: flow_aborted` | `backend/tests/ipc/test_schemas.py::test_flow_aborted_status` | `frozen` |
| `Heartbeat: ping/pong (30s/10s/3-miss, 应用层 JSON)` | `backend/tests/ipc/test_heartbeat.py`（4 测试覆盖 ping 周期 + 3-miss 触发 + pong 重置 + clean stop） | `frozen` |
| `Message correlation: message_id (UUID v4)` | `backend/tests/ipc/test_server.py::test_ws_start_flow_returns_flow_started`（响应含相同 message_id）+ `frontend/tests/unit/ws-client.test.ts::correlates RPC response` | `frozen` |
| `Error code enum (8 codes)` | `backend/tests/ipc/test_schemas.py::test_error_code_enum_has_all_8_values` | `frozen` |
| `Security: prefilter.scrub(text) → ScrubResult` | `backend/tests/security/test_prefilter.py`（25 测试含 catalog/round-trip/determinism/idempotence/randomized） | `frozen` |
| `Security: prefilter.restore(text, mapping) → text` | `backend/tests/security/test_prefilter.py::test_restore_recovers_original_byte_for_byte` + `::test_restore_preserves_repeated_placeholders` | `frozen` |
| `Security: OTEL_SDK_DISABLED=true 硬编码` | `backend/tests/security/test_otel_disabled.py`（5 测试覆盖 import 时设置/覆盖/无网络调用） | `frozen` |
| `Security: keyring (setPassword/getPassword/deletePassword)` | `backend/tests/security/test_no_plaintext_key.py`（5 测试覆盖 D1-9 grep 验证）；`@napi-rs/keyring` 运行时由 dev 机手测 | `frozen` |
| `UI: window1 (transparent, PixiJS, 0 React DOM)` | `frontend/tests/unit/pet-state.test.ts`（11 测试）+ `frontend/tests/e2e/window1-dom.test.ts`（Playwright stub，dev 机跑） | `frozen (待 dev 机)` |
| `UI: window2 (opaque, React 6 panels)` | `frontend/tests/unit/panels.test.tsx`（14 测试，6 panel 各覆盖）+ `frontend/tests/e2e/window2-panels.test.ts`（Playwright stub） | `frozen (待 dev 机)` |
| `UI: click-through hit-testing` | `frontend/tests/unit/pet-state.test.ts`（isInsidePet 逻辑）+ `frontend/tests/e2e/window1-click-through.test.ts`（Playwright stub） | `frozen (待 dev 机)` |
| `UI: window position persistence (localStorage)` | 单测在 `frontend/tests/unit/panels.test.tsx` 部分覆盖；运行时由 dev 机手测 | `frozen (待 dev 机)` |
| `UI: privacy-consent-modal (D1-10 clarified)` | `frontend/tests/unit/panels.test.tsx::<PrivacyConsentModal />` 3 测试 + D1-10 spec clarification | `frozen` |
| `UI: confirm-panel (D1-8 window1/window2 split)` | `frontend/tests/unit/panels.test.tsx::<ConfirmPanel />` 3 测试 | `frozen` |
| `UI: AI-label "AI 驱动" (D1-12)` | Pet renderer 源码 `frontend/src/window1-pet/pet.ts:117-122`（PixiJS Text 持续渲染）；运行时由 dev 机手测 | `frozen (待 dev 机)` |
| `Metrics: record_flow_metrics (4 fields)` | `backend/tests/observability/test_metrics_recorder.py`（10 测试） | `frozen` |
| `Metrics: error_rate sliding window 100` | `backend/tests/observability/test_metrics_recorder.py::test_error_rate_uses_sliding_window_100` | `frozen` |
| `Remote: establishSshTunnel + classifySshStderr` | `frontend/tests/unit/ssh-tunnel.test.ts`（11 测试含 4 错误分类纯函数） | `frozen` |

---

## 四、契约测试执行入口

- **本地执行**：`pytest openspec/regression/contracts/ -v`
- **CI 执行**：Dev-Phase 1 起在 CI pipeline 增加 `regression-contracts` stage
- **回归门控触发**：Dev-Phase N（N > 0）验收前自动运行；输出报告路径 `out/regression-reports/<timestamp>-contracts.json`
