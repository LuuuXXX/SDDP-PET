# SDDP-PET 回归基础设施（Regression Infrastructure）

本目录是 SDDP-PET 项目跨阶段回归与向后兼容验证的物理载体。规格定义见：
- `openspec/specs/regression-strategy/spec.md`

## 使用说明

### 创建新 Dev-Phase 变更前后的模板校验

```bash
bash scripts/validate-dev-phase-change.sh <change-dir>
```

该校验脚本基于 `openspec/changes/setup-development-roadmap/design.md` 附录 A 的必填章节锚点，对给定 Dev-Phase 变更目录的 `proposal.md` 与 `design.md` 执行 grep 校验。缺失任一章节将 exit 1 并打印缺失清单到 stderr。

**调用时机**：
- 创建新 Dev-Phase 变更后立即调用，确保模板章节齐全
- Dev-Phase 变更 archive 前再次调用，确保未删章节
- CI pipeline（Dev-Phase 1 起接入）中作为 `template-check` stage

### Dev-Phase 验收前的回归门控（Dev-Phase N > 0 必填）

1. 重放 `golden-demos/` 中所有已冻结（status = frozen）的 Golden Demo
2. 运行 `contracts/` 中所有已冻结的契约测试
3. 任一历史回归失败 → 阻断本 Dev-Phase 的 Go 判定
4. 在本 Dev-Phase 的变更 `tasks.md` 末尾"回归门控"任务中记录结果

执行上限：完整重放须 ≤ 30 分钟、LLM 调用成本 ≤ $20。累积 >5 个 demo 时允许"代表性子集"快速通道（仅用于实现期反馈，不替代验收时的全量重放）。

## 目录结构

```
openspec/regression/
├── README.md                      # 本文件
├── golden-demos-index.md          # 所有 Dev-Phase 的 Golden Demo 槽位总表
├── contracts-index.md             # 所有关键接口契约总表
├── accepted-risks.md              # 已接受风险登记（不阻断 Go 判定）
├── golden-demos/
│   ├── README.md                  # Golden Demo 文件命名与格式约定
│   └── dev-phase-0.md             # （Dev-Phase 0 完成时冻结；其余阶段同理）
└── contracts/
    ├── README.md                  # 契约测试目录组织与命名约定
    ├── websocket/                 # Dev-Phase 1 起的实际测试代码
    ├── knowledge-graph/           # Dev-Phase 0 KG-MVP 的契约测试
    └── ...
```

## 三个核心组件的关系

| 组件 | 来源 | 触发时机 | 失败后果 |
|------|------|----------|----------|
| Golden Demo | Dev-Phase 完成时冻结于 `golden-demos/<dev-phase>.md` | 下一 Dev-Phase 验收前重放 | 阻断 Go 判定 |
| 契约测试集 | 各 Dev-Phase 引入新接口时增量添加于 `contracts/` | 每次回归门控运行 | 阻断 Go 判定 |
| 已接受风险 | 登记于 `accepted-risks.md` | 每次回归报告显示状态 | 不阻断（仅显示） |

## 已接受风险

见 `accepted-risks.md`。当前登记 4 项：对抗收敛 LLM 自引用悖论 / OpenAI vendor lock-in / 知识图扫描置信度边界 / 离线模式可靠性降级。这些项在回归报告中显示状态但不阻断 Go 判定。
