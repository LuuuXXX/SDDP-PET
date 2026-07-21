## 1. 回归基础设施目录搭建

- [x] 1.1 创建 `openspec/regression/golden-demos/` 目录，并写 `README.md` 说明用途（存放每个 Dev-Phase 完成时冻结的 Golden Demo，与 git tag 绑定）
- [x] 1.2 创建 `openspec/regression/contracts/` 目录，并写 `README.md` 说明用途（存放关键接口契约测试，从 Dev-Phase 1 起增量添加实际测试代码）
- [x] 1.3 在 `openspec/regression/README.md` 写顶层说明：Golden Demo 与契约测试集的关系、回归门控执行入口、已接受风险列表的位置

## 2. 模块分解数据填充

- [x] 2.1 写 `openspec/specs/development-roadmap/modules.md`：模块表（列：模块名 / 对外契约 / 上游依赖 / 下游消费 / 归属 Dev-Phase / 来源 analysis 文档），至少覆盖 spec 中列出的 12 个最小模块集合（engine-core / code-knowledge-graph / safe-agent-wrapper / adaptation-layer / cli-runner / desktop-pet-ui / websocket-ipc / security-compliance / remote-mode / execution-subsystem / quality-gate-flow / confrontation-flow）
- [x] 2.2 在 `modules.md` 末尾追加"角色 → 模块反向映射表"，覆盖全部 13 个 SDDP 角色（需求官/调度官/架构师/挑评师/实证师/实施师/代码资产管理员/验收师/复核师/规范员/修缮师/版本管理员/交付官），验证无孤儿角色
- [x] 2.3 校验每个模块的"对外契约"与"来源 analysis 文档"字段非空；不允许 TBD

## 3. 阶段依赖与 DoD 数据填充

- [x] 3.1 写 `openspec/specs/development-roadmap/phases.md`：阶段依赖图（Dev-Phase → 前置阶段列表 → 关键路径标记 → 产出模块集合 → 预估工期），覆盖 7 个 Dev-Phase（0/1/2/3a/3b/4/5），数据源自 `analysis/06-dev-phase-dod.md` 第八节
- [x] 3.2 写 `openspec/specs/development-roadmap/dod.md`：每阶段 DoD 清单，从 `analysis/06-dev-phase-dod.md` 第二节至第七节抽取，每项形如"可执行命令/可观察行为 + 通过阈值"（不允许"代码写完"类描述）；Dev-Phase 0 必须包含四个量化阈值（成本 ≤ $5、延迟 ≤ 10min、合规率 ≥ 99%、3 proposal 无崩溃）
- [x] 3.3 写 `openspec/specs/development-roadmap/no-go-rollback.md`：No-Go 回退映射表（列：Dev-Phase / No-Go 条件 / 单一回退目标 / 回退目标类型[analysis 文档/模块/spec 章节]），Dev-Phase 0 必须包含 4 项 No-Go（KG 召回率<70% / CrewAI 循环不可用 / 成本>$15 / 合规率<95%）

## 4. 回归策略数据填充

- [x] 4.1 写 `openspec/regression/golden-demos-index.md`：Dev-Phase 0–5 的 Golden Demo 槽位表（列：Dev-Phase / 输入场景 / 期望输出 / 度量阈值范围 / 运行命令占位 / git tag 占位），Dev-Phase 0 数据填实（源自 `analysis/06` DoD 演示场景），其余阶段填"待该阶段完成时冻结"
- [x] 4.2 写 `openspec/regression/contracts-index.md`：关键契约清单（列：契约名 / 类型[WebSocket/KG API/SafeAgent/适配层/JSON Schema] / 引入 Dev-Phase / 当前状态[未实现/已冻结/BREAKING 变更历史]），源自 `analysis/00` 第七节（WebSocket 5+4+4 消息）与 `analysis/02`（KG 4 类查询）
- [x] 4.3 写 `openspec/regression/accepted-risks.md`：4 项已接受风险登记（对抗收敛 LLM 自引用悖论 / OpenAI vendor lock-in / 知识图扫描置信度边界 / 离线模式可靠性降级），每项列：来源 analysis 文档 / 为何接受 / 在回归报告中如何呈现

## 5. Dev-Phase 变更模板校验脚本

- [x] 5.1 写 `scripts/validate-dev-phase-change.sh`：基于本变更 `design.md` 附录 A 的校验锚点，grep 校验给定 Dev-Phase 变更目录下 proposal.md 与 design.md 的必填章节是否齐全；缺失任一项 exit 1 并打印缺失清单
- [x] 5.2 在 `openspec/regression/README.md` 顶部"使用说明"中登记脚本调用方式：`bash scripts/validate-dev-phase-change.sh <change-dir>`
- [x] 5.3 手工构造一个最小 fixture（伪 Dev-Phase 变更目录，故意缺一个章节）验证脚本能正确报告缺失

## 6. 文档校验与变更就绪

- [x] 6.1 运行 `openspec validate --change setup-development-roadmap`，所有 error/warning 清零
- [x] 6.2 grep 校验所有 spec / 数据文件中对 `analysis/00` 至 `analysis/06` 的引用路径在 `/root/desktop/SDDP-Pet/analysis/` 下确实存在
- [x] 6.3 grep 校验 spec / 数据文件中无 "TBD" / "TODO" / "待补" 等占位词（Golden Demo 槽位中明确标注"待该阶段完成时冻结"者除外）
- [x] 6.4 运行回归门控演练：手工创建一个伪 Dev-Phase 0 变更目录，按附录 A 模板填充，验证模板章节齐全可被 `scripts/validate-dev-phase-change.sh` 通过
