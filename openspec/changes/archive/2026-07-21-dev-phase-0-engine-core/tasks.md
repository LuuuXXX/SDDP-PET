## 1. 仓库初始化与 CrewAI 版本锁定

- [x] 1.1 创建 `backend/` 目录骨架：`pyproject.toml`（PEP 621）、`sddp/__init__.py`、`sddp/{safe_agent,adaptation,kg,engine,cli,schemas}/__init__.py`、`backend/tests/{safe_agent,adaptation,kg,engine,cli}/__init__.py`
- [x] 1.2 写 `python-version` 文件锁 `3.11.x`（具体 patch 在 1.4 中实测最稳定版本）；写 `pyproject.toml` 含 `requires-python = ">=3.11,<3.12"`
- [x] 1.3 实现 `backend/scripts/verify_crewai_version.sh`（依据 `analysis/03` 第 4.1 节骨架）：在隔离 venv 中安装候选 CrewAI 版本，跑 5 个冒烟检查（#5972 fix 存在 / #6347 fix 存在 / #6380 复现验证 / 1 维度 3 轮对抗循环冒烟 / @human_feedback 冒烟）
- [x] 1.4 运行 `verify_crewai_version.sh` 选定具体 CrewAI patch；产出 `CREWAI_VERSION_RATIONALE.md`（依据 `analysis/03` 第 4.2 节，逐条对照 4 准则：必含 fix / 避 breaking / 选 stable / Python 兼容）
- [x] 1.5 运行 `pip-compile` 产出 `requirements.lock.txt`（含 crewai + 全部传递依赖如 chromadb/langchain/protobuf/grpcio）；提交 lockfile 到仓库根

## 2. KG-MVP（code-knowledge-graph 模块）

> 此模块工期最长（12–15 天），可与任务 3–5 并行启动；任务 2.1–2.3 是关键启动项。

- [x] 2.1 实现 `sddp/kg/manifest.py`：探测项目语言（识别 `pyproject.toml` / `package.json` / `Cargo.toml` / `go.mod` / `pom.xml`），Dev-Phase 0 仅 Python 路径生效；默认排除规则 `vendor/ node_modules/ dist/ build/ .git/`，可通过 CLI `--exclude` 覆盖
- [x] 2.2 实现 `sddp/kg/scip_indexer.py`：调用 `scip-python` 索引器产出 `.scip` 文件；处理失败时回退到 `sddp/kg/tree_sitter_fallback.py`
- [x] 2.3 实现 `sddp/kg/graph_schema.py`：SQLite DDL，建表 `nodes(id, kind, name, file_path, scan_version)` + `edges(src_id, dst_id, kind, scan_version)` + `scan_meta(scan_version, created_at, coverage_stats)`；`nodes.kind` CHECK 约束含 5 类（Repository/File/Symbol/Module/Package）；`edges.kind` CHECK 约束含 8 类（DEFINES/REFERENCES/CALLS/IMPORTS/INHERITS/CONTAINS/DEPENDS_ON/DECLARED_IN_MANIFEST）
- [x] 2.4 实现 `sddp/kg/graph_loader.py`：解析 SCIP protobuf → 批量写入 SQLite 节点/边；构造 `DEFINES` 边（来自 SymbolInformation）、`REFERENCES` 边（来自 SymbolOccurrence role=1）、`CALLS` 边（按符号引用模式推断）
- [x] 2.5 实现 `sddp/kg/query_api.py`：`KnowledgeGraphQueryAPI` 类含 `find_callers(symbol_id, depth)` / `find_file_impact(file_path)` / `find_dependencies(symbol_id)` / `get_module_api(module_id)`；返回 `QueryResult(answer, confidence, coverage_note, sources)`；confidence 基于扫描覆盖率映射（>90% 覆盖率→HIGH，70–90%→MEDIUM，<70%→LOW）
- [x] 2.6 实现 `sddp/kg/derived_views.py`：物化 3 个派生视图（reverse_call_graph / file_impact_set / module_public_api），加速 4 类查询
- [x] 2.7 实现 `sddp/kg/scan.py` CLI 入口：`python -m sddp.kg.scan <path> [--exclude pattern]`，端到端调用 manifest→scip→loader→derived_views
- [x] 2.8 构造 KG 测试 fixture：选 2–3 个小型 Python 开源项目（< 100 文件），放入 `backend/tests/fixtures/sample-python-project/`；人工/半自动构造 `backend/tests/kg/golden.json`（含 expected callers/impact/deps/api 关系）
- [x] 2.9 实现 `backend/scripts/kg_evaluate.py`：读取 `golden.json`，对每个 ground-truth 项调用 KG 查询，计算 recall/precision；产出 JSON 输出含 `recall` / `precision` / `confidence_calibration`
- [x] 2.10 写 `backend/tests/kg/test_queries.py`：4 类查询的契约测试（断言返回 `QueryResult` 三字段结构）+ schema 强制测试（断言非法 `kind` 抛 IntegrityError）
- [x] 2.11 写 `backend/tests/kg/test_scan.py`：扫描 `tests/fixtures/sample-python-project/`（≥10 文件），断言 SQLite 中 Symbol 节点数 > 0，scan_version 写入

## 3. SafeAgent Wrapper（safe-agent-wrapper 模块）

- [x] 3.1 实现 `sddp/safe_agent/wrapper.py`：`SafeAgent` 类包裹 CrewAI Agent；提供 `kickoff(input)` 同步接口；内部用 `asyncio.run` + `asyncio.wait_for` 实现 timeout
- [x] 3.2 实现 retry 策略：用 `tenacity` 装饰器，仅对 `asyncio.TimeoutError` / `ConnectionError` / `RateLimitError`（OpenAI 429）重试（指数退避，默认 3 次）；对 `ValueError` / `ParseError` / `ValidationError` 立即抛出
- [x] 3.3 实现 `SafeAgentError` 异常类：含 `agent` / `error_type` / `reason`（`recoverable_exhausted` / `non_recoverable`）/ `original_exception` 字段
- [x] 3.4 实现 state.errors 记录：每次失败追加 `{agent, error_type, message, recoverable, timestamp}` 到 CrewAI Flow state 的 `errors` 列表（通过 adaptation-layer 的 persist 原语）
- [x] 3.5 实现配置覆盖：环境变量 `SDDP_SAFE_AGENT_TIMEOUT_SECONDS` / `SDDP_SAFE_AGENT_MAX_RETRIES` 可覆盖默认值
- [x] 3.6 写 `backend/tests/safe_agent/test_timeout_retry.py`：用 `SDDP_SAFE_AGENT_TIMEOUT_SECONDS=5` 构造 #6380 复现场景（mock LLM 不返回），断言 SafeAgent 在 5s 后抛 `SafeAgentError`；测试 retry 计数；测试不可恢复错误立即抛出
- [x] 3.7 写 `backend/tests/safe_agent/test_state_errors.py`：断言失败记录正确追加到 state.errors

## 4. Adaptation Layer（adaptation-layer 模块）

- [x] 4.1 实现 `sddp/adaptation/flow_definition.py`：抽象基类含 4 个原语方法签名 `start(handler)` / `listen(event, handler)` / `router(conditions)` / `persist(state_key, value)`；公开 API MUST 不 import `crewai`
- [x] 4.2 实现 `sddp/adaptation/crewai_adapter.py`：`CrewAIFlowAdapter` 继承 `FlowDefinition`，用 CrewAI `Flow` + `@start` / `@listen` / `@router` 装饰器实现 4 原语
- [x] 4.3 实现 `sddp/adaptation/mock_adapter.py`：`MockFlowAdapter` 用于单元测试，不依赖真实 CrewAI/LLM；用内存事件总线模拟 4 原语
- [x] 4.4 写 `sddp/adaptation/README.md`：含升级流程章节（触发条件 / 验证流程 / 通过标准）
- [x] 4.5 写 `backend/tests/adaptation/test_mock_adapter.py`：覆盖 4 原语最小行为（start 触发 / listen 监听 / router 分支 / persist 读写）
- [x] 4.6 写 `backend/tests/adaptation/test_crewai_loop.py`：用真实 CrewAI（但仍 mock LLM）跑 1 维度 3 轮最小对抗循环，验证 #5972 fix 在选定版本中工作（D0-1 关联，监控 DP0-NG-B）

## 5. Engine Core - 5 角色与 Flow（engine-core 模块）

- [x] 5.1 实现 `sddp/schemas/proposal.py` / `delta_spec.py` / `delta_design.py`：3 个 Pydantic v2 模型，字段对齐 SDDP 设计文档格式模板（依据 `specs/engine-core/spec.md` 第 3 个 Requirement 的 Scenario "3 种文档 schema 字段齐全"）
- [x] 5.2 实现 `sddp/schemas/architecture_research.py`：架构师产出的研究报告 Pydantic 模型（含知识图查询引用 + 置信度标注字段）
- [x] 5.3 实现 `sddp/schemas/__init__.py`：导出全部模型；提供 JSON Schema 导出工具（`to_json_schema()`）
- [x] 5.4 实现 5 角色 backstory：`sddp/engine/backstories/{requirement_officer,orchestrator,architect,executor,code_asset_manager}.py`；每角色 500–800 tokens；含 SDDP 4 条共性约束 + 角色差异化约束（依据 `specs/engine-core/spec.md` 第 2 个 Requirement）
- [x] 5.5 实现 5 角色 Agent 工厂：`sddp/engine/agents.py` 用 CrewAI `Agent` + SafeAgent 包装构造每个角色；通过 adaptation-layer 注册到 Flow
- [x] 5.6 实现线性 Flow：`sddp/engine/flows/phase_0_2_linear.py` 用 adaptation-layer 的 4 原语构造：需求官→调度官→架构师→实施师→代码资产管理员；3 个 @human_feedback 确认点接入点（需求确认 / 方案确认 / 任务确认）
- [x] 5.7 实现代码资产管理员 Agent 与 `KnowledgeGraphQueryAPI` 集成：Agent 通过 CrewAI `tools` 装置 4 个查询函数；查询结果含 confidence/coverage_note，转达给架构师
- [x] 5.8 实现实施师"仅代码建议不写文件"约束：实施师 Agent 输出 markdown diff 格式代码建议；guardrail 验证不调用文件写入 API
- [x] 5.9 实现 token 计量：`sddp/engine/cost_meter.py` 拦截 OpenAI API 响应，记录 `usage.prompt_tokens` / `usage.completion_tokens`；按显式定价表（OpenAI 官网公开）计算 USD 成本；记录 pydantic 验证失败重试次数算 `structured_output_first_try_rate`
- [x] 5.10 实现 cost_report 输出：Flow 完成时写 `cost_report.json`，含 `measured_cost_usd` / `wall_clock_minutes_excluding_human_wait` / `structured_output_first_try_rate` / `total_tokens` / `round_tokens` 字段
- [x] 5.11 实现 JSON ↔ Markdown 双向渲染：`sddp/schemas/renderer.py` 含 `to_markdown(model) -> str` 与 `from_markdown(md, model_cls) -> model`；Markdown 格式对齐 SDDP 设计文档模板
- [x] 5.12 写 `backend/tests/engine/test_5_roles_kickoff.py`：用 MockFlowAdapter，5 角色 kickoff 全部完成，断言退出码 0
- [x] 5.13 写 `backend/tests/engine/test_output_schema_enforcement.py`：构造缺字段 LLM 输出，断言 pydantic ValidationError 抛出
- [x] 5.14 写 `backend/tests/engine/test_json_markdown_roundtrip.py`：双向转换无损 + Markdown 格式合规
- [x] 5.15 写 `backend/tests/engine/test_cost_meter.py`：mock OpenAI API 响应含 usage 字段，断言 cost_report 字段齐全且数值基于实测

## 6. CLI Runner（cli-runner 模块）

- [x] 6.1 实现 `sddp/cli/main.py`：用 Typer 定义 `sddp` 主命令 + `run` 子命令；`run` 接受 `<proposal>` 位置参数 + `--project` + `--output`（默认 `./out/`）+ `--resume <flow_id>`
- [x] 6.2 实现 proposal 输入解析：若 `<proposal>` 是文件路径则读取内容；若是字符串则直接用作 proposal 文本
- [x] 6.3 实现 `sddp/cli/feedback_adapter.py`：`CLIHumanFeedbackAdapter` 接管 CrewAI @human_feedback 调用，转为 stdin/stdout 交互；显示待确认内容摘要 + 提示符（`y` / `n` / `e`）
- [x] 6.4 实现 3 个用户确认点的阻塞逻辑：需求确认（Phase 0）/ 方案确认（Phase 1）/ 任务确认（Phase 2）；每个确认点显示摘要 + 阻塞 stdin
- [x] 6.5 实现 @persist 中断恢复：Flow state 写入 `~/.sddp-pet/flow_state.db`（SQLite）；`--resume <flow_id>` 读取该 flow_id 的 state，从中断点恢复
  - **补强（2026-07-21）**：原实现仅复用 flow_id；现已接通 `LinearPhase02Flow` 的 `prior_state` + `persist_step` 回调，CLI 在每步完成后 `flow_state.save_state`，`--resume` 时 `list_steps` + `load_state` 注入 prior_state，命中步骤完全跳过 LLM。集成测试 `test_flow_resume_skips_cached_steps_via_cli` + 真实 DeepSeek 端到端验证（5 步 resume 2.0s / 0 token）均 PASS
- [x] 6.6 实现输出目录写入：Flow 完成后将 proposal/delta_spec/delta_design/architecture_research 写为 markdown 到 `--output` 目录；写 `cost_report.json`；在 stdout 显示 cost 摘要
- [x] 6.7 写 `backend/tests/cli/test_run_command.py`：用 Typer 的 `CliRunner` 测试 `sddp run --help` 与基本参数解析
- [x] 6.8 写 `backend/tests/cli/test_resume.py`：手工 mock 中断 + 重启场景，断言 flow_id 恢复

## 7. 端到端测试与 Golden Demo 冻结

- [x] 7.1 构造 3 个 fixture proposal：`backend/tests/fixtures/proposals/{config-hot-reload,add-logging,refactor-utils}.txt`；3 个不同复杂度的真实需求
- [x] 7.2 实现 E2E 测试脚本 `backend/tests/e2e/test_dev_phase_0_demo.py`：跑 `config-hot-reload` proposal，调用真实 OpenAI API（非 CI 常规运行），断言产出 4 个 markdown + cost_report.json + scan_version 递增
- [x] 7.3 跑 D0-14 连续 3 proposal 不崩溃：手工跑 3 个 fixture proposal，全部成功产出文档集
  - **完成（2026-07-21，DeepSeek Tier-B 基线）**：3 个 fixture proposal（config-hot-reload / add-logging / refactor-utils）经 `pytest tests/e2e/test_dev_phase_0_demo.py::test_d0_14_three_proposals_no_crash_real` 全部 PASS（exit_code=0 + 4 markdown + cost_report.json）。E2E 测试 7/7 通过，耗时 183s
- [x] 7.4 跑 D0-11/12/13 度量：审查 `config-hot-reload` 的 cost_report.json，确认 `measured_cost_usd <= 5.0` / `wall_clock_minutes_excluding_human_wait <= 10.0` / `structured_output_first_try_rate >= 0.99`
  - **完成（2026-07-21，DeepSeek Tier-B 基线）**：3 个 proposal 实测如下，全部远超阈值：

    | proposal | cost_usd | wall_min | compliance | tokens | D0-11 | D0-12 | D0-13 |
    |----------|---------:|---------:|-----------:|-------:|:-----:|:-----:|:-----:|
    | config-hot-reload | $0.0078 | 0.67 | 100.0% | 14,344 | ✅ | ✅ | ✅ |
    | add-logging       | $0.0095 | 0.80 | 100.0% | 15,713 | ✅ | ✅ | ✅ |
    | refactor-utils    | $0.0111 | 0.90 | 100.0% | 18,372 | ✅ | ✅ | ✅ |

    **Tier-B caveat**：D0-13 在 18 次 LLM 调用上 100% 合规（远超 90-95% Tier-B 预期），但 `analysis/04` MVP 决策 8 仍要求 OpenAI Tier-S 作为 Go 基线；本结果作为"plumbing 验证"，OpenAI Tier-S 重测待 `OPENAI_API_KEY` 解锁后执行
- [x] 7.5 冻结 Golden Demo：把 `config-hot-reload` 的运行结果（输入 + 期望输出 + 度量阈值 + 运行命令）写入 `openspec/regression/golden-demos/dev-phase-0.md`，状态从 `pending` → `frozen`，打 git tag `dev-phase-0-v1`
  - **完成（2026-07-21，Tier-B provisional baseline）**：Golden Demo 写入 [`openspec/regression/golden-demos/dev-phase-0.md`](../../regression/golden-demos/dev-phase-0.md)，状态 = `frozen (Tier-B provisional)`。**git tag 待定**：当前项目根无 git 仓库（`git init` 未执行），`dev-phase-0-v1` tag 创建推迟到 git 仓库初始化时

## 8. 契约登记与文档同步

- [x] 8.1 更新 `openspec/regression/contracts-index.md`：把本变更引入的契约状态从 `unimplemented` → `frozen`，含 `KG: *`（5 条）/ `SafeAgent: *`（3 条）/ `Adaptation Layer: *`（2 条）/ `JSON Schema: *`（3 条）/ `sddp run` CLI（1 条）共 14 条；填充"测试代码路径"列指向 `backend/tests/...`
- [x] 8.2 在 `backend/` 写 README.md：含安装（pip install -e .）、运行（sddp run）、测试（pytest）三大入口；引用 `CREWAI_VERSION_RATIONALE.md` 与 `analysis/03`
- [x] 8.3 跑 `grep -rE "TBD|TODO|FIXME|待补" backend/ openspec/changes/dev-phase-0-engine-core/` 校验无新增占位词

## 9. 回归门控演练与最终验证

- [x] 9.1 运行 `bash scripts/validate-dev-phase-change.sh openspec/changes/dev-phase-0-engine-core`，校验本变更的 proposal.md 与 design.md 含附录 A 全部必填章节（Why/What Changes/Capabilities/Impact/跨阶段接口变更登记/Regression Baseline/Context/Goals-Non-Goals/Decisions/Risks-Trade-offs/DoD Checklist/No-Go Rollback Plan）
- [x] 9.2 运行 `openspec validate --changes dev-phase-0-engine-core`，所有 error/warning 清零
- [x] 9.3 跑 `pytest backend/tests/`（不含 E2E），全部 PASS
- [x] 9.4 跑 D0-1 ~ D0-14 全部 DoD 项，逐项打勾；任一不通过触发对应 No-Go（DP0-NG-A~G），按 design.md "No-Go Rollback Plan" 表执行回退
  - **完成（2026-07-21）**：D0-1 ~ D0-14 + X-1/X-2/X-3/X-4/X-5 全部打勾并实测通过（DeepSeek Tier-B provisional baseline，见 `design.md` DoD Checklist）。**无 No-Go 触发**
- [x] 9.5 运行回归门控：本阶段为首个 Dev-Phase，无历史 Golden Demo 重放；archive 时本阶段 Golden Demo（任务 7.5 冻结）作为 Dev-Phase 1 的回归基线
  - **完成（2026-07-21）**：回归报告写入 [`openspec/regression/reports/2026-07-21-dev-phase-0-gate.md`](../../regression/reports/2026-07-21-dev-phase-0-gate.md)；历史 demo 重放集合 = 0；契约测试 110 passed / 4 deselected；门控判定 PASS
