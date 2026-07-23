# Dev-Phase 2 — Implementation Tasks

> Status: **实现进行中** (D2-1/D2-2/D2-3 主体完成 + Go 阈值验证通过;桌宠 sprite 美术 +
> server start_flow 路由 + 真实 Electron 端到端待后续)。
>
> Section ordering follows the Go/No-Go de-risking sequence: the two No-Go
> conditions (CrewAI `or_()` stability + convergence decidability) were attacked
> FIRST and are now **both cleared**.

## 1. Pre-flight & No-Go de-risking (week 1)

- [x] 1.1 CrewAI `or_()` 循环稳定性（No-Go-A）
  - **完成（架构规避）**：design §1 决策对抗循环用 SDDP 自研 while-loop + `@persist`，**不依赖 CrewAI `or_()`**。1维3轮 mock 冒烟 `test_confrontation_smoke.py` 8/8 PASS 验证自研 while-loop + persist resume + flow_id 隔离无状态串扰
- [x] 1.2 收敛规则机械化设计（No-Go-B）
  - **完成**：`design.md §5` + `sddp/engine/convergence.py` severity(高/中/低) 计数判定，非 LLM 二判。`test_convergence.py` 23/23 PASS（含 guardrail 阻止高严重度无据驳回）
- [x] 1.3 DP1 回归基线锁定
  - **完成**：后端 pytest 174 passed（DP1 契约子集）；P3 基线 config-hot-reload DeepSeek $0.0092 / 15962 tok / 100% 合规

## 2. D2-1 对抗 Flow 实现

- [x] 2.1 `phase_1_confrontation.py`：自研对抗 while-loop（architect → critic 并发 → empiricist → 收敛判定 → revise/force）
- [x] 2.2 简化对抗冒烟（mock）：`test_confrontation_smoke.py` 8/8 PASS
- [x] 2.3 完整对抗跑通（3 维度 5 轮，真实 DeepSeek）：`test_confrontation_go.py` PASSED — **cost $0.0163 / 31224 tok / 0 errors / 141s**（Go 阈值 $15 的 1/920）
- [x] 2.4 prefilter 脱敏覆盖对抗 payload：`phase_1_agents.py` 所有 LLM 调用经 `scrub`/`restore`（D1-11 单 chokepoint）
  - **caveat**：4 角色 kickoff 用裸 `openai` client + tenacity-style 重试（`phase_1_agents.py`），未显式包 `SafeAgent` wrapper 类（DP0 #6380 缓解的等价语义已在 _llm_call 实现）；后续可统一包 SafeAgent

## 3. D2-2 收敛检测

- [x] 3.1 `sddp/engine/convergence.py`：severity 规则引擎（机械化计数）
- [x] 3.2 `max_rounds` 强制收敛（`check_convergence` 优先级 1：round_count >= max_rounds → FORCE_CONVERGED）
- [x] 3.3 escalate 到用户裁决：`FeedbackMethod.FORCE_CONVERGENCE`（additive）+ `WebSocketHumanFeedbackAdapter`；`ipc/confrontation_runner.py` 验证 escalate 路径
- [x] 3.4 `test_convergence.py` 23/23 PASS（机械化收敛 / max_rounds / escalate / guardrail 四路径）

## 4. D2-3 多角色桌宠

- [ ] 4.1 4 角色 sprite 资产（architect/critic/empiricist/orchestrator）接入 PixiJS
  - **待美术资产**：当前用 `STATE_COLORS`（8 色）+ `roleLabel` 前缀占位（design §6.1 "圆+label 起步，sprite 后补"）。需提供 sprite 美术或确定用 Live2D（DP4）
- [x] 4.2 `pet-state.ts` 扩展 4 → 8 态（debating/rebutted/converged/escalated）+ `role` 字段；DP1 `pet-state.test` 12/12 PASS（向后兼容）
- [~] 4.3 对抗可视化：window1 role 标签 + 8 态颜色（占位）；**rebuttal 箭头 + 角色切换动画待 sprite 资产**
- [ ] 4.4 新增可选 Push `convergence_state`（round / severity-resolved 计数）→ 诊断面板
  - **待实现**：当前 convergence 经 `agent_state_change.role/round`（additive）+ `feedback_required(force_convergence)` 暴露；独立 `convergence_state` Push 未加（design §8 可选）

## 5. D2-4 并发流程

- [x] 5.1 `@persist` 按 `flow_id` 命名空间隔离：`test_confrontation_smoke.py::test_two_flows_isolated_by_flow_id` 验证 2 flow 无串扰
- [ ] 5.2 调度官多 proposal 管理（DP3 完整调度的前置）— **DP3 范围**
- [~] 5.3 2 flow 并发冒烟：flow_id 隔离已单测；**server.py 多 in-flight flow 路由（放松 `active_flow` 单 flow 限制 + 多 feedback_adapter 路由）待实现**（改 frozen server.py，谨慎后续）

## 6. WS-IPC 向后兼容 + 回归

- [~] 6.1 `agent_state_change` 增加可选 `role`/`round`（pydantic 双侧 ✅ `schemas.py` + `test_dp2_additive.py` 5/5）；**前端 `ws-schemas.ts` zod 同步 `role` 字段待补**（derivePetUpdate 已用 `(msg as {role?}).role` 兼容读取）
- [x] 6.2 DP1 WS 契约回归：`tests/ipc/` 33/33 PASS（含 additive 不破 DP1）
- [ ] 6.3 DP1 Golden Demo 重放（config-hot-reload 在 DP2 树下 4 md + cost ±20%）— **待系统重放**

## 7. Go/No-Go 验证 + archive

- [x] 7.1 No-Go-A/B 信号复核：`or_()` 稳定性（架构规避）+ 收敛可判定性（规则消除）**双确认**
- [x] 7.2 cost ≤ $15 验证（Tier-B 实测 **$0.0163**；Tier-S 待 OPENAI_API_KEY）
- [ ] 7.3 完整 5 轮对抗**在桌宠下端到端**跑通（真实 Electron，非 CLI）— **CLI 路径 Go 通过；Electron UI 端到端待 dev 机**
- [ ] 7.4 冻结 DP2 Golden Demo → `openspec/regression/golden-demos/dev-phase-2.md` + git tag `dev-phase-2-v1` — **待 7.3（UI 端到端）后**

---

## 进展总结

**已完成（技术可行性 + Go 阈值）**：
- No-Go-A（架构）+ No-Go-B（收敛）+ §8 #1（LLM 解析）**三大风险全证伪**
- D2-1 对抗 flow 主体 + 4 真实 agent + 完整 3维5轮 Go 验证（cost $0.0163）
- D2-2 收敛引擎 23/23；D2-3 桌宠 8 态 + role（占位 sprite）；D2-4 flow_id 隔离
- WS additive 契约（role/force_convergence）DP1 兼容

**剩余（工程实现，无技术风险）**：
- D2-3 sprite 美术资产（需提供）+ rebuttal 可视化
- server.py `start_flow` 路由接入 `confrontation_runner`（phase=confrontation）+ 多 flow 并发路由
- 真实 Electron UI 端到端（dev 机）→ 然后冻结 Golden Demo + tag `dev-phase-2-v1`
