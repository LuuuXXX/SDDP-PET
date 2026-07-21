## ADDED Requirements

### Requirement: 模块分解必须显式且边界可寻址

SDDP-PET 项目 MUST 被分解为命名良好的子系统模块，每个模块 MUST 声明其对外契约（接口/数据/事件）与对其他模块的依赖。模块清单 MUST 涵盖下列最小集合：`engine-core`（CrewAI 5 角色线性流）、`code-knowledge-graph`（SCIP+tree-sitter 知识图）、`safe-agent-wrapper`（#6380 防护）、`adaptation-layer`（CrewAI 解耦）、`cli-runner`（Dev-Phase 0 的人机交互入口）、`desktop-pet-ui`（双窗口桌宠）、`websocket-ipc`、`security-compliance`、`remote-mode`、`execution-subsystem`（SandboxedExecutor/FileWriteProxy/RuleMapper）、`quality-gate-flow`（Phase 3 关卡）、`confrontation-flow`（Phase 1 对抗）。模块定义 MUST 引用 `analysis/` 中对应文档作为权威来源。

#### Scenario: 任意模块可在路线图中定位边界
- **WHEN** 开发者查询某个模块（例如 `code-knowledge-graph`）的边界
- **THEN** 路线图规格 MUST 给出该模块的对外契约（输入/输出/查询接口）、上游依赖模块、下游消费模块、对应的 Dev-Phase 归属

#### Scenario: 模块集合覆盖 SDDP 设计文档全部角色流
- **WHEN** 将模块集合映射到 SDDP 工作流的 Phase 0–6（需求→交付）
- **THEN** 每个角色（需求官/调度官/架构师/挑评师/实证师/实施师/代码资产管理员/验收师/复核师/规范员/修缮师/版本管理员/交付官）MUST 至少归属一个模块；不允许存在"无模块归属"的角色

### Requirement: Dev-Phase 顺序与依赖 MUST 显式声明

路线图 MUST 声明 7 个 Dev-Phase 的严格交付顺序：`0 → 1 → 2 → 3a → 3b → 4 → 5`（其中 4 与 5 可选/可并行）。每个 Dev-Phase MUST 列出其前置 Dev-Phase（不可跳过）、关键路径归属（关键路径 / 可并行）、以及该阶段产出的模块集合。依赖关系 MUST 与 `analysis/06-dev-phase-dod.md` 第八节关键路径（0→1→2→3a→3b）一致。

#### Scenario: 阶段顺序可被自动校验
- **WHEN** 后续创建某个 Dev-Phase N 的变更时
- **THEN** 路线图 MUST 提供机器可读的依赖图，使得校验工具能判定"Dev-Phase N 的所有前置阶段已 archive"

#### Scenario: 关键路径外的阶段不可阻塞关键路径
- **WHEN** Dev-Phase 4（高级特性）或 Dev-Phase 5（离线/国际化）延期时
- **THEN** 关键路径（0→1→2→3a→3b）的推进 MUST 不受阻塞；路线图 MUST 显式标注这一隔离规则

### Requirement: 每个 Dev-Phase MUST 有可度量、二元判定的 DoD

路线图 MUST 为每个 Dev-Phase 定义 Definition of Done（DoD），DoD MUST 满足四项原则（来自 `analysis/06-dev-phase-dod.md`）：(1) 可演示（有具体 demo 场景）；(2) 可度量（关键指标有数值阈值）；(3) 二元判定（通过/不通过，无模糊）；(4) 含失败路径。每个 DoD 项 MUST 可被 `opsx-apply` 的验收阶段直接执行。

#### Scenario: DoD 项可被 opsx-apply 验收执行
- **WHEN** `opsx-apply` 在某 Dev-Phase 验收阶段读取该阶段的 DoD 清单
- **THEN** 每个 DoD 项 MUST 形如"可执行命令 / 可观察行为 + 通过阈值"，不允许出现"代码写完"这类无法判定的描述

#### Scenario: DoD 包含度量阈值
- **WHEN** 审查 Dev-Phase 0 的 DoD（依据 `analysis/06-dev-phase-dod.md` D0-5）
- **THEN** 路线图 MUST 至少包含四个量化阈值：单流程成本 ≤ $5、端到端延迟 ≤ 10 分钟、Structured Outputs 合规率 ≥ 99%、连续 3 个不同 proposal 无人工干预不崩溃

### Requirement: 每个 Dev-Phase MUST 有 Go/No-Go 门槛与回退路径

路线图 MUST 为每个 Dev-Phase 定义 Go/No-Go 门槛（满足 Go 条件才能进入下一阶段）和 No-Go 条件（触发回退）。每个 No-Go 条件 MUST 指向明确的回退目标（回某模块设计 / 回某分析文档 / 回 provider 策略）。No-Go 条件 MUST 与 `analysis/06-dev-phase-dod.md` 各阶段 Go/No-Go 章节一致。

#### Scenario: Dev-Phase 0 的四个 No-Go 条件齐全
- **WHEN** 审查 Dev-Phase 0 的 No-Go 清单
- **THEN** 路线图 MUST 包含至少四项：知识图召回率 < 70%（→ 回 KG 设计）、CrewAI 循环不可用（→ 回 `analysis/03`）、单流程成本 > $15（→ 重审成本驱动）、Structured Outputs 合规率 < 95%（→ 回 `analysis/04`）

#### Scenario: No-Go 触发时回退目标无歧义
- **WHEN** 某 No-Go 条件被触发
- **THEN** 路线图 MUST 指向单一明确的回退动作（具体文档路径或具体模块），不允许"重新讨论"这类无锚点的回退

### Requirement: 每个 Dev-Phase MUST 对应一个独立的 opsx-apply 变更

路线图 MUST 规定：每个 Dev-Phase 作为单独的 OpenSpec 变更（kebab-case 命名，例如 `dev-phase-0-engine-core`）创建并通过 `opsx-apply` 实现+验收。不允许在一个变更中合并多个 Dev-Phase。每个 Dev-Phase 变更的 proposal MUST 引用路线图对应章节作为范围依据。

#### Scenario: 单变更不允许多阶段合并
- **WHEN** 某个变更的 proposal 声明的范围横跨两个或更多 Dev-Phase
- **THEN** 该变更 MUST 在 review 阶段被判定为"范围越界"并被拆分

#### Scenario: Dev-Phase 变更命名遵循约定
- **WHEN** 为 Dev-Phase N 创建变更
- **THEN** 变更名 MUST 形如 `dev-phase-<n>-<short-scope>`，例如 `dev-phase-0-engine-core`、`dev-phase-3a-execution-subsystem`

### Requirement: Dev-Phase 变更 MUST 遵循统一模板

路线图 MUST 提供一个"Dev-Phase 变更模板"，规定该 Dev-Phase 变更的 proposal / design / specs / tasks 文档必须填写的章节。模板 MUST 至少包含：(a) 范围声明（引用路线图中本阶段模块清单）；(b) 前置阶段回归基线（引用回归策略中的 Golden Demo）；(c) 本阶段 DoD 清单（从路线图复制）；(d) No-Go 回退预案；(e) 跨阶段接口变更登记。

#### Scenario: 模板章节可被自动化校验
- **WHEN** 某 Dev-Phase 变更创建后
- **THEN** 模板 MUST 允许通过 grep/解析判定五个必填章节是否齐全；缺失任一章节 MUST 在 `openspec validate` 时报告

### Requirement: 路线图 MUST 标注与已有分析文档的引用关系

路线图 MUST 显式声明其每个模块、DoD、No-Go 项的来源分析文档（`analysis/00` 至 `analysis/06`）。当某项无法追溯到分析文档时，MUST 标注为"本变更新增决策"并附理由。

#### Scenario: 决策可追溯
- **WHEN** 审查路线图中任一技术决策（例如"MVP 锁 OpenAI-only"）
- **THEN** 该决策 MUST 附带来源标注（例如"源自 `analysis/04-llm-provider-strategy.md` 第五节"）或"本变更新增决策 + 理由"
