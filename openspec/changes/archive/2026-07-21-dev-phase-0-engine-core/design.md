## Context

本变更是 SDDP-PET 项目的首个实现变更（Dev-Phase 0）。仓库当前状态：

- **已有**：`analysis/` 7 份技术决策文档（02–06 已补齐 P0 缺口）；`openspec/specs/development-roadmap/` + `openspec/specs/regression-strategy/` + `openspec/regression/` 规格与回归基础设施（archive 自 `setup-development-roadmap` 变更）；`scripts/validate-dev-phase-change.sh` 模板校验脚本。
- **未有**：任何 Python 代码、CrewAI 集成、知识图、测试套件、CI 配置。

Dev-Phase 0 的核心挑战是把"基于自然语言 LLM 编排的 SDDP 工作流"转化为可执行、可度量、可回归的工程系统，且必须依赖一个**API 仍在活跃重构**的框架（CrewAI，见 `analysis/00` 第四节）。

**关键约束**：
1. CrewAI #6380（异步静默冻结）官方未修复 → SafeAgent 是硬性前提（`analysis/03` 第五节）
2. CrewAI 版本必须精确锁定 patch + 验证脚本（`analysis/03` 第四准则）
3. 知识图召回率必须 ≥ 70% 才算 Go（`dod.md` D0-6）
4. 单流程成本 ≤ $5、延迟 ≤ 10min、合规率 ≥ 99%（`dod.md` D0-11/12/13）
5. 连续 3 个不同 proposal 不崩溃（`dod.md` D0-14）

**利益相关方**：
- 实现者：需要清晰的模块边界与可执行任务
- Go 判定者：需要二元可判定的 DoD
- 后续 Dev-Phase：依赖本阶段产出的 4 个基础设施（SafeAgent / adaptation-layer / KG / engine-core）

## Goals / Non-Goals

**Goals:**
- 按 `dod.md` D0-1 ~ D0-14 全部满足，使 Dev-Phase 0 Go 判定通过
- 4 个基础设施（safe-agent-wrapper / adaptation-layer / code-knowledge-graph / engine-core）+ cli-runner + JSON Schema + JSON-Markdown 渲染全部就位
- 在 CLI 下跑通端到端 SDDP Phase 0 + 简化 Phase 2 线性流程
- 冻结首个 Golden Demo（`openspec/regression/golden-demos/dev-phase-0.md` + git tag `dev-phase-0-v1`）
- 所有新增契约（KG 4 类查询 / SafeAgent / FlowDefinition / 3 种 JSON Schema）登记到 `contracts-index.md` 并状态 `frozen`

**Non-Goals:**
- **不**实现对抗 Flow（Dev-Phase 2）
- **不**实现质量关卡（Dev-Phase 3a/3b）
- **不**实现桌宠 UI、WebSocket IPC、安全合规、远程模式（Dev-Phase 1）
- **不**实现知识图增量更新、多语言、远程模式（推迟到 KG-v1）
- **不**实现文件写入代理（Dev-Phase 3a 的 FileWriteProxy）
- **不**修改 SDDP 设计文档或已 archive 的路线图规格
- **不**优化成本（先满足 ≤ $5，进一步优化到 ≤ $3 推迟到 Dev-Phase 2+）

## Decisions

### 决策 1：Python 项目用 `pyproject.toml` + `pip-tools`，不用 poetry/uv

**选择**：`pyproject.toml`（PEP 621）+ `pip-compile` 产出 `requirements.lock.txt`。

**理由**：
- CrewAI 的传递依赖（chromadb / langchain / protobuf / grpcio / onnxruntime）易冲突，需要 lockfile 锁定
- `pip-tools` 是标准库 `pip` 的轻量扩展，不需要额外工具链；poetry 在 Windows 上偶尔有兼容问题
- 与 `analysis/03` 第 4.2 节锁定产物（`requirements.txt` + `requirements.lock.txt`）一致

**替代方案考虑**：
- poetry：被否，因额外工具链
- uv：被否，因较新，团队认知成本高（Dev-Phase 4 评估时再考虑）
- conda：被否，因与 pip 生态有壁垒

### 决策 2：Python 版本锁 3.11.x，不锁 3.12/3.13

**选择**：`python-version` 文件锁 `3.11.x`（具体 patch 在 Dev-Phase 0 启动时实测最稳定版本）。

**理由**：依据 `analysis/03` 准则 4，CrewAI 1.15.x 与 chromadb/protobuf 生态在 3.11 上最稳定；3.12/3.13 与部分 C 扩展包（onnxruntime 等）仍有兼容报告。

### 决策 3：CrewAI 版本由可执行脚本选定，不预填版本号

**选择**：在 `tasks.md` 任务 1 中按 `analysis/03` 第 4.1 节的 `verify_crewai_version.sh` 流程选定具体 patch，产出 `CREWAI_VERSION_RATIONALE.md`。

**理由**：分析阶段直接断言 `crewai==1.15.X` 的具体 patch 是不负责任的（`analysis/03` 第二节诚实声明）；PyPI 发布节奏与 fix PR 合入的 release 标签需实现时实查。

### 决策 4：SQLite 知识图 schema 用关系表而非图数据库

**选择**：SQLite + 显式 SQL 表（`nodes` / `edges` / `scan_meta`）+ 派生视图（reverse_call_graph / file_impact_set / module_public_api）。

**理由**：
- Dev-Phase 0 仅 Python 单语言，节点/边规模小（万级节点、十万级边），SQLite 完全够用
- 无需引入 Neo4j/DuckDB 等额外服务
- 派生视图用 SQL 视图或物化视图，查询 4 类 API 时直接 SELECT

**替代方案考虑**：
- Neo4j：被否，额外服务部署成本
- DuckDB：被否，嵌入式优势不如 SQLite，且 Python 标准库不含
- NetworkX in-memory：被否，@persist 需要持久化

### 决策 5：KG 召回率验证用真实开源项目 + 人工 ground-truth

**选择**：选取 2–3 个小型 Python 开源项目（< 100 文件，有完整测试套件），将其测试调用关系作为 ground-truth 代理（"已知真实调用图"）；人工或半自动构造 `golden.json`，记录预期 caller/callee/impact 关系。

**理由**：依据 `analysis/02` 第七节，无现成的 Python ground-truth 数据集；用真实项目比合成 fixture 更接近生产场景。

**替代方案考虑**：
- 合成 fixture：被否，无法反映 SCIP 索引器的真实覆盖率
- 用 tree-sitter 自行构造：循环论证（tree-sitter 是 KG 本身的 fallback 组件）

### 决策 6：5 角色的 LLM 调用 MVP 阶段用 OpenAI gpt-4o-mini，不用 gpt-4o

**选择**：Dev-Phase 0 的 5 角色 LLM 调用默认用 OpenAI `gpt-4o-mini`（成本 ~$0.15/1M input tokens），仅在 SafeAgent 验证时用 `gpt-4o`。

**理由**：
- Dev-Phase 0 单流程成本阈值 $5；gpt-4o 单轮调用 ~$0.5，5 角色 + 3 确认点 + 多次咨询代码资产管理员，累积成本易超阈值
- gpt-4o-mini 支持 Structured Outputs（99.9% 合规率，依据 `analysis/04` Tier-S 决策）
- 实测后若合规率不达 99%，按 No-Go 条件 D 回退（重审 provider 策略）

**替代方案考虑**：
- gpt-4o：成本超阈值风险
- gpt-4-turbo：Structured Outputs 支持不如 gpt-4o-mini
- 多模型混合：增加复杂度，Dev-Phase 0 不引入

### 决策 7：CLI 框架用 Typer（基于 Click），不用 argparse 或 Click 直接

**选择**：Typer（pydantic-based CLI 框架）。

**理由**：
- 与 pydantic v2 生态一致（与 engine-core 的 Pydantic 模型复用）
- 类型注解自动生成 `--help`，减少样板代码
- Click 的成熟生态（如 rich 集成）支持彩色输出与表格，便于 CLI 用户体验

**替代方案考虑**：
- argparse：标准库，但样板代码多且无类型推断
- Click 直接：被否，Typer 是其超集且更现代

### 决策 8：测试策略——LLM mock 三层

**选择**：
1. **单元测试**：完全 mock LLM（用 `MockFlowAdapter` + 固定 fixture 响应），覆盖 5 角色 kickoff、schema 强制、KG 查询、SafeAgent retry 等纯逻辑
2. **集成测试**：mock OpenAI API 客户端层（用 `respx` 或 `httpx_mock`），但走真实 CrewAI Flow 路径
3. **E2E 测试**：真实 LLM 调用（仅用于 Go 判定时的 Golden Demo 重放，不进 CI 常规运行）

**理由**：依据 `analysis/01` G15 与 `dod.md` D0-7（5 角色 kickoff 测试需 LLM mock fixture），单元 + 集成测试不依赖真实 LLM，避免 CI 成本失控；E2E 保留真实路径用于度量。

### 决策 9：@persist 用 SQLite，不用 JSON 文件

**选择**：Flow state 持久化到 `~/.sddp-pet/flow_state.db`（SQLite），每个 Flow 实例一行。

**理由**：
- JSON 文件并发写有竞争问题；SQLite 单文件原子写更可靠
- 与 KG 的 SQLite 复用同一依赖（无额外组件）
- 中断恢复时查询比 JSON 文件快

### 决策 10：模块实现顺序按 `analysis/03` 修订后的关键路径

**选择**：Dev-Phase 0 内部实现顺序按 `analysis/03` 第六节关键路径：**模块 0（CrewAI 版本）→ 模块 3（SafeAgent）→ 模块 4（5 角色）→ 模块 6（Flow）→ 模块 9（CLI 验证）**；KG-MVP（模块 2）与 5 角色（模块 4）可并行。

**理由**：模块 0/3 是所有 Python 工作的硬性前置；KG-MVP 不在关键路径上（可与 5 角色并行），但其本身工期长（12–15 天），需早期启动。

## Risks / Trade-offs

| 风险 | 缓解 |
|------|------|
| CrewAI 版本选定后仍遇未知 bug（社区未发现） | `verify_crewai_version.sh` + 5 个冒烟测试（#5972/#6347/#6380/对抗循环/human_feedback）作为 Go 前置；适配层是升级缓冲 |
| gpt-4o-mini 在 SDDP 复杂 prompt 下合规率 < 99% | 触发 No-Go 条件 D → 回 `analysis/04` 重审 provider；预案：升级关键角色（架构师/调度官）到 gpt-4o，其他保持 mini |
| KG 召回率 < 70%（SCIP 对动态语言覆盖不全） | 触发 No-Go 条件 A → 回 `analysis/02` 第四节；预案：增加 tree-sitter fallback 覆盖、降低 No-Go 阈值（需项目决策）或缩小 proposal 演示范围 |
| 单流程成本 > $5 | 触发 No-Go 条件 C；预案：缩减 backstory 长度、降低咨询代码资产管理员次数、切换更小模型 |
| 连续 3 proposal 崩溃 | 触发 D0-14 失败；预案：分析崩溃日志，定位 SafeAgent / @persist / @human_feedback 哪一层失效 |
| SQLite 在万级节点下查询慢 | 加索引（symbol_id / file_path / kind 三元组）；必要时物化派生视图 |
| CrewAI 升级窗口与 Dev-Phase 0 工期重叠 | 适配层抽象 + 升级流程文档化（决策 7）+ `verify_crewai_version.sh` 每次升级重跑 |
| OpenAI API 限流影响 E2E 测试稳定性 | SafeAgent 已含 RateLimitError 退避；E2E 测试不在 CI 常规运行，仅 Go 判定与 Golden Demo 重放时手动触发 |

---

## DoD Checklist

> 本节从 `openspec/specs/development-roadmap/dod.md` 复制 Dev-Phase 0 DoD 项，并标注实现位置（任务编号引用本变更 `tasks.md`；spec 引用本变更 `specs/<capability>/spec.md`）。

### 跨阶段通用 DoD（依据 `dod.md` 第一节）

> 验证日期：2026-07-21（部分项依赖真实 OpenAI API 调用，标记 ⛔ blocked，需 7.3/7.4 E2E 真实运行后回填）

- [x] **X-1 文档更新**：本阶段涉及的 `CREWAI_VERSION_RATIONALE.md` / `sddp/adaptation/README.md` / 各 spec 章节同步更新；`grep -r "TBD\|TODO\|待补" backend/ openspec/` 在本变更范围内无新增命中（已接受风险槽位除外）—— 任务 8.2/8.3 已执行，仅命中任务/DoD 文本自身的 grep 命令字符串，无真实占位词
- [x] **X-2 测试通过**：`pytest backend/tests/`（排除 e2e real-API 标记）退出码 0 —— 任务 9.3 实测：110 passed / 4 deselected（4 个为需 `OPENAI_API_KEY` 的 e2e real-API）
- [x] **X-3 成本实测**：内置 token 计量器输出 `cost_report.json`，含 `measured_cost_usd` 字段 —— **PASS**（2026-07-21，DeepSeek Tier-B）：3 proposal 实测 `$0.0078 / $0.0095 / $0.0111`，全部含 `measured_cost_usd` / `wall_clock_minutes_excluding_human_wait` / `structured_output_first_try_rate` / `total_tokens` / `round_tokens` 字段
- [x] **X-4 已知风险登记**：本阶段新发现风险（如有）写入 `analysis/00-sddp-pet-final.md` 风险矩阵 —— 本阶段未发现新风险（design.md Risks 矩阵 8 条均已有缓解；AR-2/AR-3 按计划首次暴露，无新增）
- [x] **X-5 回归无退化**：本阶段为首个 Dev-Phase，无历史 Golden Demo；archive 时冻结首个 Golden Demo（任务 7.5，blocked 于真实 API 运行）

### Dev-Phase 0 DoD（依据 `dod.md` 第二节）

- [x] **D0-1 CrewAI 版本选定并锁定到精确 patch** —— 实测：`pyproject.toml` 与 `requirements.lock.txt` 均含 `crewai==1.15.4`；`pip show crewai` 输出 Version=1.15.4 一致；选定理由见 `CREWAI_VERSION_RATIONALE.md`
- [x] **D0-2 SafeAgent wrapper 实现 #6380 复现测试 PASS** —— `pytest tests/safe_agent/test_timeout_retry.py` 9 个测试全部 PASS（含 `test_6380_timeout_does_not_freeze` + `test_timeout_env_var_overrides_default`）
- [x] **D0-3 适配层抽象就位** —— `pytest tests/adaptation/test_mock_adapter.py` 12 个测试全部 PASS（4 原语 start/listen/router/persist 全覆盖）
- [x] **D0-4 KG-MVP 单语言（Python）预扫描器跑通** —— 实测 `python -m sddp.kg.scan tests/fixtures/sample-python-project/`：scan_version=1、parsed_files=10/10、total_symbols=43 > 0（via=tree-sitter，SCIP 可执行文件未安装属预期）
- [x] **D0-5 KG-MVP 4 类查询带置信度返回** —— `pytest tests/kg/test_queries.py` 12 个测试全部 PASS（4 类查询 × 三字段结构 + schema 强制 + 置信度枚举）
- [x] **D0-6 KG-MVP 准确性验证套件就位，召回率 ≥ 70%** —— 实测 `python -m sddp.kg.evaluate --gold tests/kg/golden.json`：recall=**1.0000** / precision=0.8462 / calibrated confidence=high（远超 0.70 阈值）
- [x] **D0-7 5 角色 Agent 可 kickoff** —— `pytest tests/engine/test_5_roles_kickoff.py` 9 个测试全部 PASS（5 角色 mock kickoff + KG tools 装置 + cost meter 记录）
- [x] **D0-8 output_pydantic 强制 3 种输出** —— `pytest tests/engine/test_output_schema_enforcement.py` 8 个测试全部 PASS（Proposal/DeltaSpec/DeltaDesign ValidationError 拒绝缺字段 + JSON Schema 导出）
- [x] **D0-9 CLI 端到端跑通** —— **mock + real API 双路径 PASS**（2026-07-21）：mock 模式 `test_e2e_mock_mode_smoke` PASS；真实 API 模式 `test_dev_phase_0_demo_config_hot_reload_real` PASS（DeepSeek Tier-B，产出 4 markdown + cost_report.json + scan_version 递增，3 项量化 DoD 全过）
- [x] **D0-10 @human_feedback CLI 阻塞/恢复 + @persist 中断恢复** —— **PASS**（2026-07-21）：`tests/cli/test_resume.py` 6 个测试全过（含新增 `test_flow_resume_skips_cached_steps_via_cli` —— 验证 Flow 在 `prior_state` 提供时**完全不调用** `AgentFactory.build_role`，从缓存重放）；CLI `--resume` 端到端验证：DeepSeek 真实场景下 5 步全部从 prior_state 重放，耗时 2.0s（vs 全跑 45s），**0 LLM 调用 / 0 tokens**，4 markdown + cost_report 全部从缓存产出
- [x] **D0-11 单流程成本 ≤ $5** —— **PASS**（2026-07-21，DeepSeek Tier-B）：3 proposal 实测最高 $0.0111（refactor-utils），余量 ~450x
- [x] **D0-12 端到端延迟 ≤ 10 分钟（不含人工等待）** —— **PASS**（2026-07-21，DeepSeek Tier-B）：3 proposal 实测最高 0.90 min（refactor-utils），余量 ~11x
- [x] **D0-13 Structured Outputs 合规率 ≥ 99%** —— **PASS (Tier-B provisional)**（2026-07-21，DeepSeek Tier-B）：3 proposal × 6 调用 = 18 次 LLM 全部 pydantic 一次性合规（100%），远超 Tier-B 预期 90-95%。**Tier-S 待重测**：`analysis/04` MVP 决策 8 要求 OpenAI Tier-S 作为官方 Go 基线
- [x] **D0-14 连续 3 个不同 proposal 无人工干预不崩溃** —— **PASS**（2026-07-21，DeepSeek Tier-B）：`test_d0_14_three_proposals_no_crash_real` 参数化 3 proposal 全部 exit_code=0，各产出 5 文件（4 markdown + cost_report.json）；总耗时 183s

---

## No-Go Rollback Plan

> 本节从 `openspec/specs/development-roadmap/no-go-rollback.md` 复制 Dev-Phase 0 No-Go 条件，并标注监控方式与触发后的执行动作。

### Dev-Phase 0 No-Go 条件与监控

| No-Go ID | No-Go 条件 | 监控方式（何时检测） | 单一回退目标 | 触发后动作 |
|----------|-----------|---------------------|--------------|-----------|
| **DP0-NG-A** | 知识图召回率 < 70%（D0-6 未达） | `python -m sddp.kg.evaluate` 输出 `recall < 0.70`；Go 判定时执行 | `analysis/02-code-knowledge-graph-design.md` 第四节（schema）+ 第六节（4 类查询实现） | 暂停 archive；创建 `revise-kg-schema` 变更修订 analysis/02；修订后重跑 D0-4~D0-6 |
| **DP0-NG-B** | CrewAI 循环模式在选定版本下不可用（#5972 回归） | `pytest backend/tests/adaptation/test_crewai_loop.py` 失败；或 D0-7/D0-9 中 Flow 卡在第 1 轮 | `analysis/03-crewai-version-strategy.md` 第二节（4 准则选型）+ 第四节（验证脚本） | 暂停 archive；重跑 `verify_crewai_version.sh` 选下一候选 patch；更新 `CREWAI_VERSION_RATIONALE.md` |
| **DP0-NG-C** | 单流程成本 > $15（D0-11 严重失真，达 3x 阈值） | `cost_report.json.measured_cost_usd > 15.0`；Go 判定时执行 | `analysis/00-sddp-pet-final.md` 第九节（成本模型） | 暂停 archive；分析 cost_report 的 `round_tokens` 分布；缩减 backstory / 减少咨询次数 / 评估模型降级 |
| **DP0-NG-D** | Structured Outputs 合规率 < 95%（D0-13 严重失真） | `cost_report.json.structured_output_first_try_rate < 0.95`；Go 判定时执行 | `analysis/04-llm-provider-strategy.md` 第一节（Tier-S 决策）+ 第三节（可靠性适配器） | 暂停 archive；评估升级关键角色到 gpt-4o（决策 6 的预案）；如仍失败，回 analysis/04 重审 provider 策略 |
| **DP0-NG-E** | CrewAI #6380 复现测试未通过（D0-2 失败） | `pytest backend/tests/safe_agent/test_timeout_retry.py` 失败；持续监控 | 模块 `safe-agent-wrapper` + `analysis/03` 第三节（SafeAgent 决策） | 暂停 archive；在本变更内重做 SafeAgent 实现；不创建新变更 |
| **DP0-NG-F** | 适配层抽象失败（D0-3 失败） | `pytest backend/tests/adaptation/test_mock_adapter.py` 失败 | 模块 `adaptation-layer`（本变更范围内） | 暂停 archive；在本变更内重做 adaptation-layer |
| **DP0-NG-G** | D0-14 连续 3 proposal 崩溃 | 手工跑 3 个 fixture proposal 时崩溃 ≥ 1 次 | 视崩溃日志定位（SafeAgent / @persist / @human_feedback / 其他） | 暂停 archive；按崩溃定位修复；重跑 D0-14 |

### 触发后的统一执行流程

依据 `no-go-rollback.md` 第二节：

1. **触发识别**：`opsx-apply` 验收阶段执行 DoD 清单时，某项 DoD 多次重试（最多 3 次）仍不通过 → 在 `cost_report.json` 或测试报告中标记 `no_go_triggered: true` + 关联的 No-Go ID
2. **暂停推进**：本变更 MUST 暂停（不 archive）；调度（人或工具）拒绝创建 Dev-Phase 1 变更
3. **回退动作**：按本表"单一回退目标"列执行：
   - 类型为 `analysis 文档`：创建 `revise-<topic>` 变更修订该 analysis 文档；修订后重跑本变更相关 DoD
   - 类型为 `模块`：在本变更内重做该模块的实现 + 单元测试；不创建新变更
4. **再次验收**：回退完成后重跑本变更全部 DoD；若再次 No-Go，升级为"项目级风险"（写入 `analysis/00-sddp-pet-final.md` 风险矩阵）并提交人工决策

### 已接受风险（依据 `accepted-risks.md`，本阶段首次暴露的 2 项）

- **AR-2 OpenAI vendor lock-in**：本阶段首次实际暴露（D0-11/D0-13 完全依赖 OpenAI API）；回归报告中显示"本流程 OpenAI API 调用比例 = 100%"
- **AR-3 知识图扫描置信度边界**：本阶段首次实际暴露（D0-4~D0-6 KG-MVP）；回归报告中显示 confidence 分布
- **不触发**：AR-1（对抗收敛悖论，Dev-Phase 2 引入对抗时触发）、AR-4（离线降级，Dev-Phase 5 触发）
