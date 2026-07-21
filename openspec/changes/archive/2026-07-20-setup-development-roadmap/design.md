## Context

SDDP-PET 项目当前状态：技术决策已完备（`analysis/02`–`analysis/06` 五份 P0 补齐文档），但仓库内尚无任何工程产物——`/root/desktop/SDDP-Pet/` 仅含 `analysis/` 子目录，`openspec/specs/` 为空，无源码、无测试、无 CI。

项目特征：
- **体量大**：21–35 周总工期（`analysis/06-dev-phase-dod.md` 第八节）。
- **强依赖 LLM 与第三方框架**：CrewAI Flows API 重构活跃（`analysis/00` 第四节）、OpenAI vendor lock-in（`analysis/04`）、对抗收敛的 LLM 自引用悖论（`analysis/00` 差距2）。
- **多 Dev-Phase 串行关键路径**：0→1→2→3a→3b 是不可并行的核心链。
- **增量交付**：每个 Dev-Phase 完成后须冻结基线供下一阶段回归。

利益相关方：
- 项目实现者（AI/人）：需要明确的"下一步做什么"和"怎样算完成"。
- 项目验收者：需要可二元判定的 DoD 与 Go/No-Go 门槛。
- 后续维护者：需要清晰的模块边界与接口契约以理解系统。

约束：
- 工具链已选定 OpenSpec 1.6.0 + spec-driven schema（`openspec/config.yaml`）。
- 每个 Dev-Phase 实现须通过 `opsx-apply`（即 `openspec-apply-change` 工作流）驱动。
- 不允许在主分支累积未验收的中间产物。

## Goals / Non-Goals

**Goals:**
- 把 SDDP-PET 拆解为可独立验收的命名模块集合，使每模块的对外契约可被机器寻址。
- 把 6 个 Dev-Phase 固化为有序变更序列，每阶段 DoD 与 No-Go 门槛可被 `opsx-apply` 直接执行。
- 定义"Golden Demo 冻结 + 契约测试集 + 回归门控"三件套，使前阶段成果在后续阶段不被无声破坏。
- 提供统一的 Dev-Phase 变更模板，使后续 6 个 `opsx-apply` 变更结构一致、可自动化校验。
- 所有路线图决策可追溯到 `analysis/` 中的来源文档。

**Non-Goals:**
- **不**实现任何 SDDP-PET 工程代码（无 Python、无 Electron、无 WebSocket）。
- **不**修改 SDDP 设计文档（`../SDDP/SDDP智能小队设计文档.md`）。
- **不**重新评估已在 `analysis/02`–`06` 中补齐的技术决策（知识图技术栈、CrewAI 版本准则、provider 策略、Phase 3 Flow 拆分、各阶段 DoD 草案）。
- **不**覆盖 01-review 中仍开放的 P1 项（G6 快速通道、G7 PCM 解析、G8 角色动画状态机、G9 远程部署、G10 Windows 摩擦）；这些在对应 Dev-Phase 启动前各自做小分析。
- **不**承诺总工期压缩——本变更不改写 `analysis/06` 的工期估算。

## Decisions

### 决策 1：模块分解采用"角色 × 子系统"二维矩阵，而非纯角色或纯子系统
**选择**：模块按子系统维度命名（`engine-core`、`code-knowledge-graph` 等），同时维护一张"角色 → 模块"反向映射表。

**理由**：SDDP 设计以角色为中心，但 Dev-Phase 工期以子系统为单位估算（如 KG-MVP 12–15 天）。若纯按角色分模块，会出现"代码资产管理员 Agent 与预扫描器系统组件分属不同 Dev-Phase"的混乱；若纯按子系统，又会丢失 SDDP 的角色语义。二维矩阵让两者都可寻址。

**替代方案考虑**：
- 纯角色维度（13 角色 = 13 模块）：被否，因实施师/修缮师等多角色在同一 Dev-Phase 共享代码骨架。
- 纯子系统维度：被否，因 SDDP 文档以角色为单位定义约束（如"代码修改设计须先咨询代码资产管理员"），需保留角色寻址。

### 决策 2：路线图规格以机器可读子节嵌入 Markdown，而非引入新工具
**选择**：在 `development-roadmap/spec.md` 与 `regression-strategy/spec.md` 中使用固定结构表格（模块表、阶段依赖表、DoD 表、No-Go 表、Golden Demo 表、契约测试表）。可被 `grep`/`awk`/简单 Python 解析。

**理由**：项目已有 OpenSpec 工具链，无需引入额外 YAML/JSON 工具；Markdown 表格对人类与机器都友好。

**替代方案考虑**：
- 单独 YAML/JSON 文件 + Markdown 渲染：被否，因增加同步开销且 OpenSpec 已以 Markdown 为主。
- 全部用 spec scenarios 表达（即不写表格）：被否，因路线图本身就是结构化数据，scenarios 适合行为描述而非数据查询。

### 决策 3：Golden Demo 与契约测试集物理放在 `openspec/regression/` 下，而非 `tests/`
**选择**：新建 `openspec/regression/golden-demos/<dev-phase>.md`（场景描述+阈值+运行命令）和 `openspec/regression/contracts/` 目录（后续阶段实际测试代码）。Golden Demo 与 git tag 绑定。

**理由**：Golden Demo 是规格的一部分（描述"何为正确"），而非实现细节；放 `openspec/` 与其他规格同根，便于 `opsx-apply` 在验收阶段定位。实际执行代码（pytest/playwright）放在 Dev-Phase 1 起的 `tests/` 下，由规格引用路径。

**替代方案考虑**：
- 全部放 `tests/golden/`：被否，因 Dev-Phase 0 完成时还没有 `tests/` 目录结构。
- 嵌入各 Dev-Phase 变更目录：被否，因后续阶段需引用历史 demo，跨变更引用会复杂化。

### 决策 4：Dev-Phase 变更模板嵌入本变更的 design.md（作为附录），而非单独文件
**选择**：在本 `design.md` 末尾以"附录 A：Dev-Phase 变更模板"形式给出模板骨架。模板的"必填章节校验"由 `openspec validate` 配合简单 grep 规则完成。

**理由**：模板是路线图的组成部分，单独文件容易被遗忘；嵌入 design 让它作为决策的一部分被 review。

**替代方案考虑**：
- 单独 `openspec/templates/dev-phase-change.md`：作为后续可选项保留，但当前先嵌入 design.md。
- 用 OpenSpec 的 custom schema 强制模板：被否，因 spec-driven schema 已够用且 custom schema 学习成本高。

### 决策 5：阶段顺序与 No-Go 回退目标编码为"依赖图 + 回退映射表"两张表
**选择**：
- 阶段依赖图：Dev-Phase → [前置 Dev-Phase 列表] → 关键路径标记
- No-Go 回退映射表：No-Go 条件 → 单一回退目标（具体 `analysis/` 路径或具体模块名）

**理由**：`analysis/06` 已给出 DoD 与 Go/No-Go，但回退目标散落在文字中。把它固化为表使得"出现 No-Go 时去哪里"无歧义。

**替代方案考虑**：用决策树图：被否，因表格对 `opsx-apply` 更友好。

### 决策 6：回归门控的"快速通道"使用代表性子集而非全量
**选择**：当历史 Golden Demo 累积 >5 时，允许在 Dev-Phase 实现期间（非验收时刻）运行"代表性子集"（每个历史阶段抽 1 个最关键 demo）；验收时刻 MUST 运行全量。

**理由**：完整重放一个 LLM 流程成本约 $1–12.5（`analysis/00` 第九节）；累积 5+ demo 全量重放成本与时间不可控。

**替代方案考虑**：始终全量重放：被否，因单次回归 >$50 不现实。

### 决策 7：已接受风险显式登记为"非回归项"，每次回归报告显示状态
**选择**：在回归策略 spec 中明确列出 4 项已接受风险（对抗收敛悖论 / OpenAI lock-in / 知识图置信度边界 / 离线降级），标注为"不阻断 Go 判定"。

**理由**：`analysis/00` 与 `analysis/01` 已显式接受这些风险；若回归策略不显式排除，每次回归都会被它们阻塞。

## Risks / Trade-offs

| 风险 | 缓解 |
|------|------|
| 路线图规格与未来实际开发漂移（开发中发现模块边界需调整） | 在 Dev-Phase 变更模板中强制"接口变更登记"；允许通过新一阶段变更显式升级路线图（标注 BREAKING + 迁移） |
| Golden Demo 在 LLM 非确定性下重放不稳定（同输入不同输出） | Golden Demo 阈值用范围（如成本 $3–$7、关键文档字段必须存在）；不要求逐字相同。Dev-Phase 0 DoD 已含"合规率 ≥ 99%"作为稳定性度量 |
| 模块分解过早僵化（Dev-Phase 3a 实际发现执行子系统应再拆） | 路线图允许"模块升级"（在 Dev-Phase 变更中提出），但 MUST 走接口变更登记流程 |
| 回归套件累积导致验收时间爆炸 | 决策 6 的代表性子集快速通道；同时回归策略 spec 要求总执行时间 ≤ 30min 上限 |
| 模板必填章节校验依赖 grep，未来 OpenSpec 版本变更可能失效 | 校验规则文档化在本 design.md 附录 A；模板变更与 OpenSpec 升级同步评估 |
| 跨 Dev-Phase 的接口变更未登记就合并 | `opsx-apply` 验收阶段 MUST 检查 design 中"接口变更登记"小节；缺失则视为 Non-Goal 范围越界 |

## Migration Plan

本变更本身**仅新增文档**，无代码迁移。

部署步骤：
1. 本变更合并后，`openspec/specs/development-roadmap/` 与 `openspec/specs/regression-strategy/` 自动成为项目规格主档。
2. 创建 `openspec/regression/golden-demos/` 与 `openspec/regression/contracts/` 空目录（含 README 占位）。
3. 后续每个 Dev-Phase 创建变更时，按本 design.md 附录 A 模板填充。

回滚策略：
- 若路线图在 Dev-Phase 0 中暴露严重设计缺陷，回滚 = 创建新变更 `revise-development-roadmap` 修订规格（不允许直接编辑 `openspec/specs/`）。
- 已 archive 的本变更不删改。

## Open Questions

- **Q1**：Dev-Phase 4（高级特性）与 5（离线/国际化）的可并行/延后特性，是否需要在路线图中明确"哪些 Dev-Phase 4 子项可与 Dev-Phase 5 子项并行"？当前决策是"两者都可选，不细化并行"；若后续需细化，作为新一阶段变更升级路线图。
- **Q2**：Golden Demo 的 LLM 调用成本由谁承担（项目预算 vs 验收预算）？影响回归套件执行频率。当前留作项目运营决策，本变更不固化。
- **Q3**：契约测试是否需要独立的 CI workflow（独立于 Dev-Phase 实现的 CI）？Dev-Phase 1 引入 CI 时决定；本变更仅规定契约测试集单调增长。

---

## 附录 A：Dev-Phase 变更模板

每个 Dev-Phase N 创建变更时（命名 `dev-phase-<n>-<short-scope>`），其文档 MUST 包含下列章节。`openspec validate` 配合本附录的"校验锚点"检查章节齐全。

### A.1 proposal.md 必填章节

```markdown
## Why
<!-- 引用 development-roadmap spec 中本 Dev-Phase 的章节作为范围依据 -->

## What Changes
<!-- 列出本阶段交付的模块（来自路线图模块表） -->

## Capabilities
<!-- 本阶段新增/修改的 capability -->

## Impact
<!-- 必填子节: 跨阶段接口变更登记（若无变更, 显式声明"无"） -->
### 跨阶段接口变更登记
| 接口名 | 变更类型 | 向后兼容 | 迁移路径 |
|--------|----------|----------|----------|

## Regression Baseline
<!-- 引用 regression-strategy spec 中本阶段所有前置阶段的 Golden Demo 列表 -->
```

**校验锚点**（grep）：`## Why`、`## What Changes`、`## Capabilities`、`## Impact`、`### 跨阶段接口变更登记`、`## Regression Baseline` 全部存在。

### A.2 design.md 必填章节

```markdown
## Context
## Goals / Non-Goals
## Decisions
## Risks / Trade-offs
## DoD Checklist
<!-- 从 development-roadmap spec 复制本阶段 DoD 清单, 每项标注实现位置 -->
## No-Go Rollback Plan
<!-- 从 development-roadmap spec 复制本阶段 No-Go 回退映射, 每项标注监控方式 -->
```

**校验锚点**：`## DoD Checklist`、`## No-Go Rollback Plan` 必须存在且非空。

### A.3 specs/<capability>/spec.md

按 OpenSpec spec-driven 标准（`## ADDED Requirements` / `### Requirement:` / `#### Scenario:`）填写。本阶段引入的每个新 capability 都需对应 spec 文件。

### A.4 tasks.md

按 OpenSpec tasks 标准填写。MUST 包含一条"回归门控"任务作为最后一条：

```markdown
- [ ] 运行历史回归套件（Golden Demo 重放 + 契约测试集）, 全部通过后方可 Go
```
