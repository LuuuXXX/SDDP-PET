# Dev-Phase 2 Design — 对抗验证 + 多角色桌宠

> Status: **DRAFT** (elaborates `proposal.md`; references `analysis/06` §四,
> `analysis/crewai-technical-research.md` §8, DP0/DP1 specs).

## 1. 核心架构决策:SDDP 自研 flow 引擎 vs CrewAI Flow

`crewai-technical-research.md` §8 给出了基于 **CrewAI Flow**(`@router` + `or_()` self-loop)的对抗循环参考实现。但 DP0 落地的 `sddp/engine/flows/phase_0_2_linear.py`(217 行)证明 SDDP **自研 flow 引擎**(`@persist` + 手动步骤编排 + 裸 `openai` client 经 `SafeAgent`)已经能稳定承载 5 角色线性流程。

**决策:Phase 2 对抗循环采用 SDDP 自研引擎,不依赖 CrewAI Flow 的 `@router/or_()`。**

理由(直接化解 No-Go-A):
- CrewAI Flows API 仍处活跃重构(`#5972`/`#6370`/`#6405`/`#6084`),`or_()` self-loop 的稳定性是 §8 列出的 **High 风险**。自研 while-loop + 显式状态机把对抗循环从"框架黑盒"变成"可测的确定性代码"。
- 收敛判定必须机械化(No-Go-B)—— 用 `if/else` over 结构化 `CriticismPoint.status` 比塞进 CrewAI `@router` 返回值更透明、更易单测。
- `adaptation/crewai_adapter.py`(DP0 已存在)保留为**可选实验路径**:若未来要切回 CrewAI Flow,adapter 层是切换点,不污染 engine 核心。

**代价**:放弃 CrewAI Flow 的声明式编排,手动管理循环/状态/恢复。但这正是 DP0 已验证的能力(`@persist` resume 已在 phase_0_2_linear 工作)。

## 2. 去风险策略(Week 1,No-Go 前置)

按 `tasks.md` §1,两个 No-Go 条件在动工前 1-2 周内证伪:

| No-Go | 触发条件 | Week-1 验证 |
|-------|----------|-------------|
| **A** CrewAI `or_()` 不稳 | 循环在生产并发下静默冻结 | **本设计已规避**(自研引擎不用 `or_()`);仍跑 1 维度 3 轮 mock 冒烟确认 SDDP while-loop + `@persist` resume 在对抗往返下无状态串扰 |
| **B** 收敛不可判定 | LLM 自引用悖论(挑评师橡皮图章架构师) | 收敛规则是**结构化计数的确定性判定**(§5),不请 LLM 二次判断;escalate-to-user 是无条件兜底 |

No-Go-A 在架构层已消除;No-Go-B 在规则层(§5)消除。剩余风险降到"工程实现"而非"方法可行"。

## 3. State 模型(基于 §8 Step 1,适配 SDDP)

```python
# sddp/engine/flows/phase_1_state.py
class CriticismPoint(BaseModel):
    id: str
    dimension: str            # 安全性/性能/可维护性
    content: str
    severity: str             # 高/中/低
    evidence_ref: str | None  # 实证师验证报告
    architect_response: str | None
    arbitrator_decision: str | None   # 采纳/驳回
    decision_basis: str | None
    status: str = "unresolved"        # unresolved/resolved/dismissed

class Phase1ConfrontationState(BaseModel):
    flow_id: str = ""                # D2-4 并发隔离键
    proposal: str = ""
    architecture_research: str | None = None
    current_delta_spec: str | None = None
    current_delta_design: str | None = None
    criticism_points: list[CriticismPoint] = []
    evidence_reports: list[str] = []
    round_count: int = 0
    max_rounds: int = 5
    converged: bool = False
    errors: list[str] = []
```

与 §8 的差异:加 `flow_id`(D2-4);移除 DP0 线性专有字段。State 经 `@persist` 落 `flow_state.db`,key = `flow_id`(命名空间隔离)。

## 4. 对抗循环拓扑(SDDP 自研)

不使用 CrewAI `@router/or_()`,而是 DP0 同款的手动编排 + `@persist`:

```
start → architecture_research → architect_produce_design
   ↙________________________________________↙
  critics_challenge (并发: 安全/性能[/可维护性] 维度)
   ↓
  empiricist_verify (仅 高/中 severity)
   ↓
  convergence_check (§5 机械化判定) ── revise ──→ architect_revise_design ↗
   │                                            (把 criticism/arbitration 注入 architect)
   ├── converged → user_confirm (feedback_required)
   └── force_converged (max_rounds) → user_force_confirm
```

关键点:
- **循环 = while + 状态机**,不是 CrewAI router。`convergence_check` 返回 `revise | converged | force_converged`,驱动下一步。
- **architect 修订路径**:`architect_revise_design` 接收完整 `criticism_points` + `arbitration_results` 历史(解决 §8 edge case "agent memory not persisted across rounds")。
- **critics 并发**:用 `asyncio.gather` over SafeAgent(§8 Step 3 `critics_challenge` 模式),但收敛判定在其后串行。
- **resume**:`@persist` 在每个 agent kickoff 边界 checkpoint;断点续跑按 `flow_id` 从 `flow_state.db` 恢复(复用 DP0 的 `LinearPhase02Flow` resume 机制)。

## 5. 收敛规则目录(No-Go-B 的机械化判定)

收敛 = **结构化计数的确定性判定**,不调 LLM 二次判断(回应自引用悖论):

| 条件 | 判定 | 动作 |
|------|------|------|
| 存在 `severity=高` 且 `status=unresolved` | 未收敛 | `revise`(高严重度必须解决) |
| 所有点 `status ∈ {resolved, dismissed}` | **收敛** | `converged` → user_confirm |
| `round_count >= max_rounds(5)` | 强制收敛 | `force_converged` → user 裁决 |
| 其余(中/低 unresolved) | orchestrator 裁决 | 采纳→`unresolved`(必须改);驳回→`dismissed`(需 evidence,见 guardrail) |

**Guardrail(防 LLM 作弊)**:orchestrator 不得对 `severity=高` 输出 `驳回` 除非 `decision_basis` 非空且引用 `evidence_ref` 或 KG citation。该规则在 `_parse_arbitration` 后代码层强制(违反 → 标记 error + 回退为 `unresolved`)。这是 §8 edge case "All criticisms dismissed but high severity exists" 的硬编码兜底。

**escalate-to-user**:`converged` / `force_converged` / `rejected` 三路径都经 `feedback_required` Push(复用 DP1 WS 契约,新增 `method="convergence_escalation"`),window2 `ConfirmPanel` 承载 —— 与 DP1 D1-8 气泡确认同一 UI 通道。

## 6. 多角色桌宠(D2-3)

### 6.1 角色映射(4 角色,对应 §8 agents)
| SDDP 角色 | 桌宠形象 | 主职责 |
|-----------|----------|--------|
| architect 架构师 | (sprite A) | 产出/修订 delta-spec + delta-design |
| critic 挑评师 | (sprite B) | 多维度质疑(安全/性能/可维护性) |
| empiricist 实证师 | (sprite C) | 为质疑提供证据(原型/基准/依赖分析) |
| orchestrator 调度官 | (sprite D) | 裁决未收敛点 + 推进流程 |

> 注:§8 把 critic 拆成 3 个子 agent(安全/性能/可维护性),DP2 桌宠只渲染**一个"挑评师"形象**,其维度切换通过 bubble 文案表达(不增角色数,控成本)。

### 6.2 动画状态机扩展(DP1 的 4 态 → 8 态)
```
idle / working / waiting / error          (DP1 已有)
+ debating / rebutted / converged / escalated   (DP2 新增,对抗专用)
```
`pet-state.ts` 的 `TRANSITIONS` 表扩展;`derivePetUpdate` 增加对带 `role`+`round` 的 `agent_state_change` 的映射(architect working→working;critic 发声→debating;architect 修订→rebutted;converged→converged;escalated→escalated)。

### 6.3 对抗可视化(window1)
PixiJS 在 window1 渲染当前发言角色 sprite + bubble + "rebuttal 箭头"(角色间)。由 postMessage 从 window2(ws-client 所在)转发 `sddp:pet-update`。对抗回放(历史重放)deferred 到 DP4。

## 7. 并发 flow(D2-4)

- `flow_id`(UUID)是所有状态隔离键:`@persist` 的 `flow_state.db` row key、KG scan 的 `scan_version` 命名空间、metrics.json 的行。
- 2 flow 并发:各自 `Phase1ConfrontationFlow` 实例 + 独立 `flow_id`;`@persist` 按 key 隔离,无状态串扰。
- 调度官多 proposal 管理:DP2 只做"2 flow 并发冒烟"(D2-4 §5.1-5.3),完整调度队列是 DP3。

## 8. WS-IPC 向后兼容(DP1 契约不破)

DP1 frozen 的 14 条 WS 条件不变。DP2 **additive only**:

| 消息 | 变更 | 兼容性 |
|------|------|--------|
| `agent_state_change` | 增**可选**字段 `role`(architect/critic/empiricist/orchestrator)、`round`(int)、`finding`(str) | DP1 客户端不读这些字段,线性 flow 不发它们 → 不破 |
| **新 Push** `convergence_state` | `{round, severity_resolved_counts, status: revising|converged|forced}` | 新消息类型;DP1 客户端 `ws-schemas` zod 把未知 type 走 `onRawInvalidMessage`,不崩 |

DP1 的 `WebSocketHumanFeedbackAdapter` 直接复用(escalate 走 `feedback_required`)。

## 9. 风险登记(承袭 §8 + 本设计新增)

| 风险 | 等级 | 缓解 |
|------|------|------|
| LLM 输出解析脆弱(`_parse_criticisms`/`_parse_arbitration`) | **High** | output_pydantic 强类型 + 解析失败 fallback(§8)+ guardrail 代码校验 |
| cost 超 $15(5 轮 × 4 角色 × 结构化输出 ≈ 20× DP1) | Medium | Tier-B(DeepSeek)预计 < $1;Tier-S 待测;每轮 cost_update 推前端,超阈值预警 |
| CrewAI 版本漂移(若用 crewai_adapter 路径) | Medium | 自研主路径不依赖;adapter 路径 pin 版本(DP0 `verify_crewai_version.sh`) |
| 并发 critic 证据冲突(§8 edge case) | Low | `asyncio.gather` 后串行合并进 state;无共享可变状态 |
| 桌宠 sprite 资产未就绪阻塞 UI | Low | 先用 DP1 的彩色圆 + 角色 label 占位,sprite 后补(D2-3 §4.1 可分阶段) |

## 10. 实现顺序(对齐 tasks.md)

1. **§1-2 去风险**(week 1):1 维度 3 轮 mock 冒烟 → 证 SDDP while-loop + `@persist` 对抗往返 OK(No-Go-A 架构规避确认);收敛规则单测(No-Go-B)
2. **§3-5 引擎**(week 2-3):state + 自研对抗 flow + 收敛 + guardrail + escalate
3. **§6 桌宠**(week 3-4):8 态 + 4 角色(圆+label 起步)+ 辩论可视化
4. **§7 并发**(week 4):flow_id 隔离 + 2 flow 冒烟
5. **§8 WS 兼容 + Go 验证**(week 5):additive 字段 + DP1 回归 + 完整 5 轮桌宠端到端(cost ≤ $15)→ tag `dev-phase-2-v1`

## 11. 与 DP0/DP1 的契约关系

- **DP0 契约不变**:`KG:*` / `SafeAgent:*` / `Adaptation Layer:*` / `JSON Schema:*` / `sddp run` CLI 全部 frozen。DP2 复用 SafeAgent + KG query + cost_meter,不修改。
- **DP1 契约向后兼容**:14 条 WS 条件不变;DP2 additive 字段 + 1 个新 Push,经 DP1 回归门控(tasks.md §6.2)。
- **新 frozen 契约**(archive 时登记):`Confrontation: state-model` / `Confrontation: convergence-rules` / `Confrontation: flow-topology` / `UI: multi-role-pet`。
