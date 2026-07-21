# SDDP-PET Dev-Phase 阶段依赖图

> 数据属性：本文件是 `development-roadmap/spec.md` 中"Dev-Phase 顺序与依赖 MUST 显式声明"需求的承载表。
> 数据来源：`analysis/06-dev-phase-dod.md` 第八节（总工期重估与关键路径）。

---

## 一、阶段依赖图

下表覆盖全部 7 个 Dev-Phase（0/1/2/3a/3b/4/5）。每行的"前置阶段"列 MUST 全部 archive 后，本阶段方可创建变更。

| Dev-Phase | 前置阶段（全部 archive） | 关键路径 | 产出模块集合 | 预估工期 |
|-----------|--------------------------|----------|--------------|----------|
| `0` | （无） | ✓ 关键路径 | `safe-agent-wrapper`、`adaptation-layer`、`code-knowledge-graph`（KG-MVP）、`engine-core`（5 角色线性骨架）、`cli-runner`、JSON Schema 最小集、JSON-Markdown 渲染 | 3–4 周 |
| `1` | `0` | ✓ 关键路径 | `desktop-pet-ui`（双窗口+穿透点击）、`websocket-ipc`（5+4+4 消息+心跳）、`security-compliance`（API 密钥加密/隐私界面/代码预过滤/AI 标注/遥测禁用）、`remote-mode`、监控可观测 | 3–4 周 |
| `2` | `1` | ✓ 关键路径 | `confrontation-flow`（完整 Phase 1 对抗 Flow：1 维度 3 轮 → 3 维度 5 轮）、`desktop-pet-ui` 扩展（4 角色桌宠+动画状态机）、并发流程基础（2 flow 并发 + @persist 数据隔离） | 5–7 周 |
| `3a` | `2` | ✓ 关键路径 | `execution-subsystem`：`SandboxedExecutor` + `FileWriteProxy` + `RuleMapper` | 3–4 周 |
| `3b` | `3a` | ✓ 关键路径 | `quality-gate-flow`（Phase 3 Flow + 修复循环）、`desktop-pet-ui` 扩展（补齐 4 角色：验收/复核/规范/修缮 → 共 8 角色桌宠）、审计日志 | 2–3 周 |
| `4` | `3b` | 可选/可并行 | 高级特性（按优先级裁剪）：Live2D 可选模块、VSCode 伴侣扩展、Tauri 迁移评估、对抗回放 | 5–7 周 |
| `5` | `3b`（与 `4` 可并行） | 可选/可延后 | **前置验证必做**：Tier-C provider（Ollama）下对抗循环可行性验证。若通过：离线集成（降级版流程）、Linux 桌面支持、国际化（提示词多语言） | 4–6 周（若可行） |

**总工期（关键路径 0→1→2→3a→3b）**：18–22 周；含可选 4/5 则 21–35 周。

---

## 二、关键路径隔离规则

依据 `development-roadmap/spec.md`"关键路径外的阶段不可阻塞关键路径"需求：

1. **Dev-Phase 4 与 5 不在关键路径**：任一延期 MUST 不阻塞关键路径推进。
2. **关键路径阶段的并行限制**：关键路径上的相邻阶段 MUST 严格串行（前阶段 archive + Go 判定后才能创建后阶段变更）；不允许提前启动。
3. **可并行项**：同一 Dev-Phase 内部的模块（如 Dev-Phase 0 的 KG-MVP 与 5 角色实现）可并行实现，但 MUST 在同一变更内完成验收。

---

## 三、与 SDDP 工作流 Phase 的映射

为避免"Dev-Phase"（SDDP-PET 产品开发阶段）与"Phase 0–6"（SDDP 工作流阶段）混淆，下表显式映射：

| Dev-Phase | 实现的 SDDP 工作流 Phase | 实现的角色 |
|-----------|-------------------------|-----------|
| `0` | Phase 0（需求解析）+ Phase 2（方案执行，简化线性，0 对抗） | 需求官、调度官、架构师、实施师、代码资产管理员 |
| `1` | （无新工作流 Phase，前端化已有） | （同上，迁移到桌宠 UI） |
| `2` | Phase 1（方案对抗，1→3 维度 3→5 轮） | + 挑评师、实证师 |
| `3a` | （无新工作流 Phase，子系统支撑） | （无新角色） |
| `3b` | Phase 3（质量关卡：验收→复核→规范→修缮） | + 验收师、复核师、规范员、修缮师 |
| `4` | （高级特性，可选） | — |
| `5` | （可选，离线降级） | — |

> **注**：SDDP 工作流的 Phase 4（归档）、Phase 5（版本管理）、Phase 6（交付总结）由 `engine-core` 在 Dev-Phase 0 起逐步实现（调度官/版本管理员/交付官角色已在 Dev-Phase 0 骨架中存在），不单列 Dev-Phase。
