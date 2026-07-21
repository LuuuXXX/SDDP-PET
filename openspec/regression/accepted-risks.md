# 已接受风险登记（Accepted Risks）

> 数据属性：本文件是 `regression-strategy/spec.md` 中"回归策略 MUST 标注已接受风险的不回归项"需求的承载表。
> 数据来源：`analysis/00-sddp-pet-final.md` 第三节（差距2）+ 第十一节（风险矩阵）+ `analysis/01-final-review.md` 第五节（已明确标记为"已接受风险"）。
>
> **不阻断约定**：本表中的风险项 MUST 不作为回归失败的判定依据；回归报告中 MUST 显示其当前状态（持续 / 缓解 / 恶化），但不计入 Go/No-Go 判定。

---

## 一、已接受风险清单

| ID | 风险名 | 来源 analysis 文档 | 为何接受 | 在回归报告中如何呈现 |
|----|--------|---------------------|----------|---------------------|
| `AR-1` | 对抗收敛 LLM 自引用悖论 | `analysis/00-sddp-pet-final.md` 第三节差距2；`analysis/06-dev-phase-dod.md` 第四节 No-Go 条件 B | LLM 判断 LLM 输出是否可靠 = 自引用验证，0 外部锚点；核心仍是 LLM 主观判断，无纯技术解法。已部分机械化（严重度规则映射、JSON 字段检查、guardrail 验证高严重度不得驳回），但收敛判据仍含 LLM 主观成分。 | 回归报告"已接受风险"小节显示：①机械化覆盖率（已机械化的字段数 / 总字段数）；②本流程中 escalate 到用户的次数（ escalate 越多 → 越接近 No-Go 边界）；③若 Dev-Phase 2 No-Go 条件 B 触发，状态升级为"恶化-需引入外部裁决信号"。 |
| `AR-2` | Vendor lock-in OpenAI | `analysis/04-llm-provider-strategy.md` 第一节 Tier-S 决策；`analysis/00-sddp-pet-final.md` 第十一节风险矩阵；`analysis/01-final-review.md` 第五节第 3 项 | MVP 锁定 OpenAI 是经济性 + 可靠性双重最优（Structured Outputs 99.9%）；非 OpenAI 重试成本 2–4x 且可靠性降级。Provider 抽象层已为未来降级铺路。 | 回归报告"已接受风险"小节显示：①本流程 OpenAI API 调用比例（应 = 100%）；②Provider 抽象层单元测试覆盖率（应单调增长）；③若 OpenAI API 重大变更导致流程失败率 > 5%，状态升级为"恶化-需启动 provider 降级"。 |
| `AR-3` | 知识图扫描置信度边界 | `analysis/02-code-knowledge-graph-design.md` 第六节（带置信度的权威）；`analysis/00-sddp-pet-final.md` 第十一节风险矩阵 | 任何静态分析都无法 100% 覆盖真实代码库（动态导入/反射/eval/生成代码）；"权威性"承诺为"带置信度的权威"而非绝对权威。已通过 confidence(HIGH/MEDIUM/LOW) + coverage_note 贯穿设计，把伪权威风险转化为可管理的已知不确定性。 | 回归报告"已接受风险"小节显示：①本流程中代码资产管理员查询的 confidence 分布（HIGH/MEDIUM/LOW 计数）；②架构师在 delta-spec 中标注置信度的比例（应 = 100%）；③若 LOW confidence 查询比例 > 50%，状态升级为"恶化-需扩充 KG 扫描覆盖"。 |
| `AR-4` | 离线模式可靠性降级 | `analysis/04-llm-provider-strategy.md` 第六节（离线降级）；`analysis/00-sddp-pet-final.md` 第十一节风险矩阵 | 离线（Ollama Tier-C）≠ 完整 SDDP，而是降级版（可能仅支持快速通道，不支持全流程对抗）。Dev-Phase 5 前置验证（D5-pre）可能否决完整离线。已接受"离线用户被排除在完整 SDDP 之外"作为产品级取舍。 | 在 Dev-Phase 5 启动前：本风险状态为"待 D5-pre 验证"。D5-pre 完成后：①若验证通过 → 状态变为"缓解-降级版离线可行"；②若验证否决 → 状态变为"持续-仅快速通道离线"。回归报告显示 D5-pre 的实测对抗合规率与收敛可靠性数据。 |

---

## 二、风险状态转移规则

依据 `regression-strategy/spec.md` "已接受风险状态在回归报告中可见"需求，本表 4 项风险的状态 MUST 在每次回归报告中更新。状态转移规则：

```
                  ┌─ 缓解（mitigation 出现明显效果）
                  │
持续 ─┬→ 缓解 ────┤
      │           │
      ├→ 恶化 ────┴→ 升级为 No-Go（按 no-go-rollback.md 处理）
      │
      └→ 持续（默认，状态不变）
```

- **持续**：风险现象与登记时一致，无变化。
- **缓解**：通过 Dev-Phase 实施降低了风险暴露（例如 AR-1 经机械化覆盖率提升、AR-3 经 KG 扫描覆盖扩充）。
- **恶化**：风险触发条件更频繁或更严重（例如 AR-2 的 OpenAI API 失败率上升、AR-3 的 LOW confidence 比例 > 50%）→ 升级为 No-Go 条件，按 `openspec/specs/development-roadmap/no-go-rollback.md` 处理。

---

## 三、与 No-Go 的边界

| 维度 | 已接受风险（本文件） | No-Go 条件（`no-go-rollback.md`） |
|------|----------------------|------------------------------------|
| 触发时机 | 风险现象存在但可管理 | DoD 项多次重试不通过 |
| 阻断 Go 判定 | 否 | 是 |
| 处理动作 | 在回归报告中显示状态 | 执行回退目标 |
| 升级路径 | 恶化时升级为 No-Go | 触发后回退；多次失败后升级为项目级风险 |

**关键不变量**：本表 4 项风险 MUST NOT 在未经过"恶化"状态转移的情况下直接阻塞 Go 判定。
