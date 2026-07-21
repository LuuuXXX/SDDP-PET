# SDDP-PET Dev-Phase No-Go 回退映射表

> 数据属性：本文件是 `development-roadmap/spec.md` 中"每个 Dev-Phase MUST 有 Go/No-Go 门槛与回退路径"需求的承载表。
> 数据来源：`analysis/06-dev-phase-dod.md` 各阶段 Go/No-Go 章节。
>
> **格式约束**：每个 No-Go 条件 MUST 指向单一明确的回退目标（具体 analysis 文档路径 / 具体模块名 / 具体 spec 章节），不允许"重新讨论"这类无锚点的回退。

---

## 一、No-Go 回退映射

| Dev-Phase | No-Go 条件 | 单一回退目标 | 回退目标类型 |
|-----------|-----------|--------------|--------------|
| `0` | 知识图召回率 < 70%（D0-6 未达） | `analysis/02-code-knowledge-graph-design.md` 第四节（schema）+ 第六节（4 类查询实现） | analysis 文档 |
| `0` | CrewAI 循环模式在选定版本下不可用（#5972 回归） | `analysis/03-crewai-version-strategy.md` 第二节（4 准则选型）+ 第四节（验证脚本） | analysis 文档 |
| `0` | 单流程成本 > $15（D0-11 严重失真，达 3x 阈值） | `analysis/00-sddp-pet-final.md` 第九节（成本模型） | analysis 文档 |
| `0` | Structured Outputs 合规率 < 95%（D0-13 未达） | `analysis/04-llm-provider-strategy.md` 第一节（Tier-S 决策）+ 第三节（可靠性适配器） | analysis 文档 |
| `0` | CrewAI #6380 复现测试未通过（D0-2 SafeAgent wrapper 失效） | 模块 `safe-agent-wrapper`（Dev-Phase 0 模块 3） + `analysis/03` 第三节（SafeAgent 决策） | 模块 + analysis 文档 |
| `0` | 适配层抽象失败（D0-3 mock adapter 不能通过） | 模块 `adaptation-layer`（Dev-Phase 0 模块 8） | 模块 |
| `1` | WebSocket 联调不稳定（连接丢失频繁，D1-4/D1-7 失败） | 模块 `websocket-ipc` 心跳/重连机制设计 + `analysis/00-sddp-pet-final.md` 第七节心跳机制章节 | 模块 + analysis 文档 |
| `1` | API 密钥加密实现失败（D1-9 失败） | 模块 `security-compliance`（Dev-Phase 1 D1-4） | 模块 |
| `1` | 远程模式 SSH 隧道不可用（D1-16 失败） | `analysis/01-final-review.md` G9（远程模式部署链路低估） + 模块 `remote-mode` | analysis 文档 + 模块 |
| `1` | Windows 上 CrewAI 依赖安装摩擦过大（用户首次运行失败率 > 30%） | `analysis/01-final-review.md` G10（Windows CrewAI 依赖摩擦）→ 评估嵌入式 Python + 预编译 wheel | analysis 文档 |
| `2` | CrewAI or_() 循环在生产场景下不稳（D2-1/D2-2/D2-3 失败） | 模块 `confrontation-flow` 适配层 + 评估 LangGraph 备选（`analysis/00` 第十节 Dev-Phase 4 已列 LangGraph 备选） | 模块 + analysis 文档 |
| `2` | 对抗收敛实际无法判定（D2-4/D2-5/D2-6 全失效，LLM 自引用悖论不可接受） | `analysis/00-sddp-pet-final.md` 第三节差距2 + `analysis/06-dev-phase-dod.md` 第四节 No-Go 条件 B（引入外部裁决信号：用户提早介入 / 基于测试通过率的客观锚点） | analysis 文档 |
| `2` | 完整对抗成本 > $15（D2-10 未达） | `analysis/00-sddp-pet-final.md` 第九节成本模型 + 模块 `confrontation-flow`（缩减挑评师数量或轮次） | analysis 文档 + 模块 |
| `2` | 并发流程 @persist 数据污染（D2-9 失败） | 模块 `engine-core` 的 @persist flow_id 命名空间设计 + `analysis/01-final-review.md` G11 | 模块 + analysis 文档 |
| `3a` | SandboxedExecutor 安全性不足（D3a-4 失败，沙箱可逃逸） | 模块 `execution-subsystem` 沙箱方案重选（评估 Docker/gVisor/WASM 等替代） + `analysis/05-quality-gate-flow-design.md` | 模块 + analysis 文档 |
| `3a` | RuleMapper 预测准确率 < 80%（D3a-3 未达） | 模块 `execution-subsystem` RuleMapper 规则集扩充 + `analysis/05` RuleMapper 章节 | 模块 + analysis 文档 |
| `3b` | Phase 3 Flow 4 个冒烟测试不全通过（D3b-2 失败） | 模块 `quality-gate-flow`（复用 Phase 1 已验证模式）+ `analysis/05-quality-gate-flow-design.md` 第五节 Flow 骨架 | 模块 + analysis 文档 |
| `3b` | 修复循环不可终止（D3b-4 失败，达 3 轮不上报） | 模块 `quality-gate-flow` 修复循环逻辑（max_rounds 硬编码 + 调度官上报） | 模块 |
| `4` | （无硬 No-Go；按用户反馈优先级裁剪） | — | — |
| `5` | D5-pre 验证否决（Tier-C provider 对抗循环不可行） | 接受"离线只支持快速通道，不支持全流程"结论；Dev-Phase 5 缩减为仅快速通道离线 + Linux 桌面 | `analysis/04-llm-provider-strategy.md` 第六节（离线降级） |

---

## 二、No-Go 触发后的执行流程

依据 `development-roadmap/spec.md` "No-Go 触发时回退目标无歧义"需求：

1. **触发识别**：`opsx-apply` 验收阶段执行 DoD 清单时，某项 DoD 多次重试仍不通过 → 在 `cost_report.json` 或测试报告中标记 `no_go_triggered: true` + 关联的 No-Go 条件 ID。
2. **暂停推进**：当前 Dev-Phase 变更 MUST 暂停（不 archive）；调度（人或工具）拒绝创建下一 Dev-Phase 变更。
3. **回退动作**：按本表"单一回退目标"列执行：
   - 类型为 `analysis 文档`：创建 `revise-<topic>` 变更修订该 analysis 文档；修订后重跑本 Dev-Phase 验收。
   - 类型为 `模块`：在本 Dev-Phase 变更内重做该模块的实现 + 单元测试；不创建新变更。
   - 类型为 `analysis 文档 + 模块`：先修订 analysis 文档（决策层），再据此修订模块（实现层）。
4. **再次验收**：回退完成后重跑本 Dev-Phase 全部 DoD；若再次 No-Go，升级为"项目级风险"（写入 `analysis/00` 风险矩阵）并提交人工决策。

---

## 三、与已接受风险的区分

本表的 No-Go 条件 MUST 与 `openspec/regression/accepted-risks.md` 中的"已接受风险"严格区分：

- **No-Go 条件**（本表）：触发时阻断 Go 判定，必须执行回退。
- **已接受风险**：不阻断 Go 判定，仅在回归报告中显示当前状态。

当某个 No-Go 条件经过评估被认为"无法在合理工期内回退"时，可由项目决策者将其转移到 `accepted-risks.md`，但 MUST 在该文件中显式登记"转移原因 + 决策日期 + 决策者"。
