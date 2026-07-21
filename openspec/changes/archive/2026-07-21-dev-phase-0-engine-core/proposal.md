## Why

本变更是 SDDP-PET 项目 Dev-Phase 0 的实现，范围严格遵循 `openspec/specs/development-roadmap/phases.md` 与 `dod.md`（D0-1 ~ D0-14）。

**为什么现在做**：`setup-development-roadmap` 变更已 archive，路线图、DoD、No-Go 回退、回归基础设施就绪。Dev-Phase 0 是关键路径起点（前置阶段：无），后续所有 Dev-Phase 都依赖本阶段产出的引擎核心、知识图、SafeAgent、适配层四大基础设施。

**核心目标**（源自 `analysis/00-sddp-pet-final.md` 第十节收窄后 MVP 与 `dod.md` Dev-Phase 0 章节）：在本地用 CLI 跑通一个 5 角色线性 SDDP 引擎（无对抗、无质量关卡），输入"给这个 Python 项目加一个配置热重载功能" → 输出 proposal + delta-spec + delta-design + 知识图更新，且单流程成本 ≤ $5、延迟 ≤ 10min、Structured Outputs 合规率 ≥ 99%、连续 3 个不同 proposal 不崩溃。

## What Changes

按 `modules.md` 中归属 Dev-Phase 0 的模块清单交付：

- **新增 `safe-agent-wrapper`**：CrewAI #6380 异步静默冻结防护。所有 CrewAI Agent 调用 MUST 经此包装。
- **新增 `adaptation-layer`**：`FlowDefinition` 抽象（start/listen/router/persist 原语）+ CrewAI adapter，与 CrewAI Flows API 解耦。
- **新增 `code-knowledge-graph`（KG-MVP）**：单语言（Python）SCIP+tree-sitter 预扫描器 → SQLite 图存储 → `KnowledgeGraphQueryAPI` 4 类查询带置信度。**不含**增量更新、不含多语言、不含远程模式（推迟到 KG-v1）。
- **新增 `engine-core`**：CrewAI Flow 实现 SDDP Phase 0（需求解析）+ Phase 2（方案执行，简化线性、0 对抗）的最小骨架。5 个 Agent（需求官/调度官/架构师/实施师/代码资产管理员）；`output_pydantic` 强制 proposal + delta-spec + delta-design；内置 token 计量与 cost_report 输出。
- **新增 `cli-runner`**：`sddp run "<proposal>"` 命令；3 个用户确认点的 stdin/stdout 阻塞/恢复；@human_feedback CLI adapter；中断后从 @persist 恢复。
- **新增 `json-schema-output`**（合并到 `engine-core` spec）：proposal + delta-spec + delta-design 三种文档的 Pydantic 模型与 JSON Schema。
- **新增 `json-markdown-renderer`**（合并到 `engine-core` spec）：上述三种文档的双向 JSON ↔ Markdown 转换器。

**不包含**（推迟到后续 Dev-Phase）：对抗 Flow（Dev-Phase 2）、质量关卡（Dev-Phase 3a/3b）、桌宠 UI（Dev-Phase 1）、WebSocket IPC（Dev-Phase 1）、安全合规（Dev-Phase 1）、远程模式（Dev-Phase 1）。

## Capabilities

### New Capabilities
- `safe-agent-wrapper`: CrewAI Agent kickoff 的防护层——tenacity retry（仅对超时/连接/限流）+ asyncio timeout（默认 120s）+ SafeAgentError 区分可恢复/不可恢复错误。所有 CrewAI Agent 调用经此包装。
- `adaptation-layer`: SDDP Flow 抽象层——`FlowDefinition` 接口（start/listen/router/persist 原语）+ 默认 CrewAI adapter；至少一个 mock adapter 用于解耦测试。
- `code-knowledge-graph`: KG-MVP 子系统——Python 单语言 SCIP 索引器集成 + tree-sitter fallback + SQLite 图存储 + 4 类查询（`find_callers` / `find_file_impact` / `find_dependencies` / `get_module_api`）带 confidence + 准确性验证套件（召回率 ≥ 70%）。
- `engine-core`: 5 角色线性 CrewAI Flow（Phase 0 需求解析 → Phase 2 方案执行）+ 3 种输出文档的 Pydantic 模型 + JSON ↔ Markdown 渲染 + 内置 token 计量。
- `cli-runner`: `sddp run` 命令行入口 + @human_feedback CLI adapter + @persist 中断恢复。

### Modified Capabilities
<!-- 本变更是 Dev-Phase 0（项目首个实现变更），openspec/specs/ 中的既有 capability（development-roadmap / regression-strategy）均为规格层，无实现可改。无 Modified Capabilities。 -->

## Impact

### 跨阶段接口变更登记

| 接口名 | 变更类型 | 向后兼容 | 迁移路径 |
|--------|----------|----------|----------|
| `KnowledgeGraphQueryAPI` | 新增（首次引入） | N/A（首个 Dev-Phase） | 见本变更 `specs/code-knowledge-graph/spec.md`；契约登记到 `openspec/regression/contracts-index.md` 的 `KG: *` 行 |
| `SafeAgent.kickoff / kickoff_async` | 新增（首次引入） | N/A | 见 `specs/safe-agent-wrapper/spec.md`；契约登记到 `SafeAgent: *` 行 |
| `FlowDefinition` 抽象 + CrewAI adapter | 新增（首次引入） | N/A | 见 `specs/adaptation-layer/spec.md`；契约登记到 `Adaptation Layer: *` 行 |
| `proposal` / `delta-spec` / `delta-design` JSON Schema | 新增（首次引入） | N/A | 见 `specs/engine-core/spec.md`；契约登记到 `JSON Schema: *` 行 |
| `sddp run` CLI 命令 | 新增（首次引入） | N/A | 见 `specs/cli-runner/spec.md` |

本变更 archive 时，所有上述契约的状态从 `unimplemented` → `frozen`，更新到 `openspec/regression/contracts-index.md`。

### 受影响的代码/目录

新增仓库结构（Dev-Phase 0 起建立）：
```
backend/
├── pyproject.toml                # crewai==<exact-patch> + Python 3.11.x
├── requirements.lock.txt         # pip-compile 产出
├── sddp/
│   ├── __init__.py
│   ├── safe_agent/               # safe-agent-wrapper 模块
│   ├── adaptation/               # adaptation-layer 模块
│   ├── kg/                       # code-knowledge-graph (KG-MVP) 模块
│   ├── engine/                   # engine-core 模块（5 角色 + Flow）
│   ├── cli/                      # cli-runner 模块
│   └── schemas/                  # Pydantic 模型 + JSON ↔ Markdown 渲染
├── scripts/
│   ├── verify_crewai_version.sh  # 见 analysis/03 第四节
│   └── kg_evaluate.py            # KG 准确性验证套件入口
└── tests/
    ├── safe_agent/
    ├── adaptation/
    ├── kg/
    ├── engine/
    └── cli/
CREWAI_VERSION_RATIONALE.md       # 见 analysis/03 第 4.2 节
```

### 依赖

- **CrewAI**：精确 patch 锁定，按 `analysis/03-crewai-version-strategy.md` 4 准则选型（必含 #5972/#6347 fix、避开 #6097 breaking、选 stable tag、Python 3.11.x 兼容）
- **SCIP 索引器**：`scip-python`（或等价工具），Apache-2.0
- **tree-sitter**：Python grammar，MIT
- **SQLite**：标准库 `sqlite3`，无外部依赖
- **FastAPI**（Dev-Phase 0 仅作 @persist 存储后端，不暴露 WebSocket；WebSocket 推迟到 Dev-Phase 1）
- **tenacity**：retry 机制
- **pydantic**：v2（CrewAI 依赖）

### 不受影响

- `analysis/` 目录：仅作为引用源，不修改
- `openspec/specs/`：development-roadmap / regression-strategy 已 archive，本变更不修改
- `openspec/regression/`：本变更是首个 Dev-Phase，不重放历史 Golden Demo；仅 archive 时更新 `contracts-index.md` 状态 + 冻结首个 Golden Demo

## Regression Baseline

依据 `openspec/regression/golden-demos-index.md`：

- **本阶段为 Dev-Phase 0**：无历史 Golden Demo 需重放（前置阶段数为 0）
- **archive 前冻结**：本变更 Go 判定时，MUST 按 `golden-demos-index.md` Dev-Phase 0 槽位冻结首个 Golden Demo 到 `openspec/regression/golden-demos/dev-phase-0.md`，并打 git tag `dev-phase-0-v1`
- **契约测试**：本变更引入的所有契约（见上方"跨阶段接口变更登记"表）MUST 在 `openspec/regression/contracts/` 下有对应测试代码（Dev-Phase 0 完成时全部 `frozen`）
- **已接受风险**：本阶段不引入新的已接受风险；现有 4 项（`accepted-risks.md`）保持不变；其中 `AR-1`（对抗收敛悖论）和 `AR-4`（离线降级）在本阶段不触发，`AR-2`（OpenAI lock-in）和 `AR-3`（KG 置信度）首次实际暴露
