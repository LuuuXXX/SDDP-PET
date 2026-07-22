# Dev-Phase 2 — Implementation Tasks

> Status: **DRAFT** (derived from `analysis/06-dev-phase-dod.md` §四 + `proposal.md`).
> Section ordering follows the Go/No-Go de-risking sequence: the two No-Go
> conditions (CrewAI `or_()` stability + convergence decidability) are attacked
> FIRST so a No-Go call can happen in week 1-2, not week 6.

## 1. Pre-flight & No-Go de-risking (week 1)

- [ ] 1.1 CrewAI `or_()` 循环稳定性验证：复用 `backend/scripts/verify_crewai_version.sh` 的 smoke + 新增 1 维度 3 轮 mock 对抗循环，确认 `or_()` retrigger 在并发/重试下不静默冻结（No-Go-A 早期信号）
- [ ] 1.2 收敛规则机械化设计：在 `design.md` 定稿 severity(critical/major/minor) → required-resolved 映射表；明确"收敛"是结构化计数的确定性判定，非 LLM 二次判断（回应 No-Go-B）
- [ ] 1.3 DP1 回归基线锁定：`git checkout dev-phase-1-v1 -- backend/tests/ frontend/tests/` 全绿；记录 DP1 Golden Demo cost/token 基线（本仓库 P3 实测：config-hot-reload DeepSeek $0.0092 / 15962 tok / 100%）

## 2. D2-1 对抗 Flow 实现

- [ ] 2.1 `crewai-technical-research` 第八节 Phase-1 Flow 完整实现（非骨架）：architect → critic + empiricist → orchestrator 路由，`sddp/engine/flows/phase_1_confrontation.py`
- [ ] 2.2 简化对抗冒烟（1 维度 3 轮，mock adapter）：`pytest tests/engine/test_confrontation_smoke.py` 通过
- [ ] 2.3 完整对抗跑通（3 维度 5 轮，真实 DeepSeek Tier-B）：cost 记录，校验 ≤ $15 Go 阈值的早期可达性
- [ ] 2.4 SafeAgent 包裹全部 4 角色 kickoff；`state.errors` 记录每轮失败；prefilter 脱敏覆盖对抗 payload

## 3. D2-2 收敛检测

- [ ] 3.1 `sddp/engine/convergence.py`：severity 规则引擎（结构化 critic 输出 → resolved/未 resolved 计数）
- [ ] 3.2 `max_rounds` 强制收敛：到达 5 轮未收敛 → 标记 `converged=false` + escalate
- [ ] 3.3 escalate 到用户裁决：复用 DP1 `feedback_required` Push（新增 method=`convergence_escalation`），window2 ConfirmPanel 承载
- [ ] 3.4 `tests/engine/test_convergence.py`：机械化收敛 / max_rounds / escalate 三路径单测

## 4. D2-3 多角色桌宠

- [ ] 4.1 4 角色 sprite 资产（architect/critic/empiricist/orchestrator）接入 PixiJS
- [ ] 4.2 `pet-state.ts` 扩展 4 → 8 态（增加 debating/rebutted/converged/escalated）
- [ ] 4.3 对抗可视化：window1 角色"辩论"动画（rebuttal 箭头 + 角色切换），由带 `role`+`round` 的 `agent_state_change` 驱动
- [ ] 4.4 新增可选 Push `convergence_state`（round / severity-resolved 计数）→ window2 诊断面板实时渲染

## 5. D2-4 并发流程

- [ ] 5.1 `@persist` 按 `flow_id` 命名空间隔离：2 flow 并发不串状态
- [ ] 5.2 调度官多 proposal 管理基础（DP3 完整调度的前置）
- [ ] 5.3 `tests/engine/test_concurrent_flows.py`：2 flow 并发冒烟

## 6. WS-IPC 向后兼容 + 回归

- [ ] 6.1 `agent_state_change` 增加可选 `role`/`round`/`finding` 字段（zod + pydantic 双侧，optional，DP1 客户端不破）
- [ ] 6.2 DP1 的 14 条 WS 契约回归全绿
- [ ] 6.3 DP1 Golden Demo 重放：config-hot-reload 在 DP2 树下 4 md + cost_report ±20%

## 7. Go/No-Go 验证 + archive

- [ ] 7.1 完整 5 轮对抗在桌宠下端到端跑通（真实 Electron，非 CLI），产出对抗回放产物
- [ ] 7.2 cost ≤ $15 验证（Tier-B 实测；Tier-S 待 OPENAI_API_KEY）
- [ ] 7.3 No-Go-A/B 信号复核：`or_()` 稳定性 + 收敛可判定性双确认
- [ ] 7.4 冻结 DP2 Golden Demo → `openspec/regression/golden-demos/dev-phase-2.md` + git tag `dev-phase-2-v1`
