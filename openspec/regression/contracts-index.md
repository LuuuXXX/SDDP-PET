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
| `Push: agent_state_change` | WebSocket Push | 1 | `unimplemented` | `analysis/00` 第七节 Push 消息 |
| `Push: document_produced` | WebSocket Push | 1 | `unimplemented` | `analysis/00` 第七节 Push 消息 |
| `Push: cost_update` | WebSocket Push | 1 | `unimplemented` | `analysis/00` 第七节 Push 消息 |
| `Push: feedback_required` | WebSocket Push | 1 | `unimplemented` | `analysis/00` 第七节 Push 消息 |
| `Push: error` | WebSocket Push | 1 | `unimplemented` | `analysis/00` 第七节 Push 消息（含 error_code 枚举 7 种） |
| `RPC req: start_flow` | WebSocket RPC | 1 | `unimplemented` | `analysis/00` 第七节 RPC 请求 |
| `RPC req: user_feedback` | WebSocket RPC | 1 | `unimplemented` | `analysis/00` 第七节 RPC 请求 |
| `RPC req: resume_flow` | WebSocket RPC | 1 | `unimplemented` | `analysis/00` 第七节 RPC 请求 |
| `RPC req: abort_flow` | WebSocket RPC | 1 | `unimplemented` | `analysis/00` 第七节 RPC 请求 |
| `RPC resp: flow_started` | WebSocket RPC | 1 | `unimplemented` | `analysis/00` 第七节 RPC 响应 |
| `RPC resp: feedback_accepted` | WebSocket RPC | 1 | `unimplemented` | `analysis/00` 第七节 RPC 响应 |
| `RPC resp: flow_resumed` | WebSocket RPC | 1 | `unimplemented` | `analysis/00` 第七节 RPC 响应 |
| `RPC resp: flow_aborted` | WebSocket RPC | 1 | `unimplemented` | `analysis/00` 第七节 RPC 响应 |
| `Heartbeat: ping/pong (30s/10s/3-miss)` | WebSocket 心跳 | 1 | `unimplemented` | `analysis/00` 第七节心跳机制 |
| `Message correlation: message_id (UUID)` | WebSocket 关联 | 1 | `unimplemented` | `analysis/00` 第七节消息关联机制 |
| `Error code enum (7 codes)` | WebSocket 错误 | 1 | `unimplemented` | `analysis/00` 第七节错误消息格式（LLM_TIMEOUT/LLM_AUTH_FAIL/LLM_RATE_LIMIT/PARSE_FAILURE/FLOW_STUCK/KNOWLEDGE_GRAPH_ERROR/SSH_CONNECTION_LOST） |
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
| （Dev-Phase 1+ 完成时填实） | | `pending` |

---

## 四、契约测试执行入口

- **本地执行**：`pytest openspec/regression/contracts/ -v`
- **CI 执行**：Dev-Phase 1 起在 CI pipeline 增加 `regression-contracts` stage
- **回归门控触发**：Dev-Phase N（N > 0）验收前自动运行；输出报告路径 `out/regression-reports/<timestamp>-contracts.json`
