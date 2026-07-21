## Why

SDDP-PET 是一个 21–35 周量级的大型项目（依据 `analysis/06-dev-phase-dod.md` 与 `analysis/00-sddp-pet-final.md`）。若直接进入 Dev-Phase 0 编码，会面临两个风险：(1) 一次性生成过多内容导致质量失控；(2) 增量开发中后期变更破坏前期已验证的能力而无法及时察觉。现有分析已具备技术决策（02–06 文档），但缺少**项目级的模块划分、阶段交付顺序、阶段验收门槛（DoD）和跨阶段回归验证策略**这一层组织规格。本变更补齐这一层，使后续每个 Dev-Phase 都能作为独立的 `opsx-apply` 变更按顺序实现并单独验收。

## What Changes

- **新增**：项目模块分解（Module Decomposition），把 SDDP-PET 拆为可独立验收的子系统模块（引擎核心、知识图、桌宠前端、执行子系统、质量关卡、安全合规、远程模式等），每个模块定义清晰边界与对外契约。
- **新增**：阶段化开发路线（Phased Roadmap），将 6 个 Dev-Phase（0/1/2/3a/3b/4/5）固化为有序变更序列；每个 Dev-Phase 对应一个后续 `opsx-apply` 变更。
- **新增**：每阶段 Definition of Done（DoD）与 Go/No-Go 门槛，使其可在 `opsx-apply` 验收阶段二元判定（通过 / 回退），含失败回退路径。
- **新增**：跨阶段回归与向后兼容验证策略（Regression & Backward-Compat Strategy）：冻结每阶段完成时的"黄金演示场景（Golden Demo）"+ 关键契约测试集，作为后续阶段交付的前置回归基线。
- **新增**：阶段间变更模板（Phase Change Template），规定每个 Dev-Phase 变更的 proposal/design/specs/tasks 必填章节，使其与路线图对齐。
- **不变**：不修改 SDDP 设计文档（`../SDDP/SDDP智能小队设计文档.md`）本身，也不实现任何 SDDP-PET 代码；本变更交付物仅为规格与计划文档。

## Capabilities

### New Capabilities
- `development-roadmap`: SDDP-PET 项目阶段化开发路线图——模块分解、Dev-Phase 0–5 的交付顺序、每阶段 DoD 与 Go/No-Go 门槛、阶段间依赖与失败回退路径。
- `regression-strategy`: 跨阶段回归与向后兼容验证策略——Golden Demo 场景冻结、关键契约测试集、阶段交付前回归门控、阶段间接口兼容性矩阵。

### Modified Capabilities
<!-- 本变更是项目初始规划，openspec/specs/ 目前为空，无既有 capability 需修改。 -->

## Impact

- **新增文档**（位于 `openspec/specs/` 下）：
  - `development-roadmap/spec.md` — 阶段化路线图主规格
  - `regression-strategy/spec.md` — 回归与向后兼容策略规格
- **新增模板**（位于本 change 目录或 `openspec/templates/` 下）：
  - Dev-Phase 变更模板（proposal/design/specs/tasks 各章节骨架）
- **后续变更影响**：本变更合并后，每个 Dev-Phase 必须按 `development-roadmap` 规定的顺序、DoD、回归基线创建独立 OpenSpec 变更并通过 `opsx-apply` 验收。
- **不受影响**：`analysis/` 目录现有技术分析文档（02–06）保持不变，仅作为路线图的输入依据被引用。
- **依赖输入**：`analysis/00-sddp-pet-final.md`（决策汇总）、`analysis/06-dev-phase-dod.md`（DoD 草案）、`analysis/02-code-knowledge-graph-design.md`（KG 模块边界）、`analysis/05-quality-gate-flow-design.md`（Phase 3 拆分）。
