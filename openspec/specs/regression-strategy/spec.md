# Regression Strategy

## Purpose

为 SDDP-PET 项目定义跨 Dev-Phase 的回归策略：每个完成的 Dev-Phase 冻结一份 Golden Demo，关键接口契约捕获为可执行契约测试，跨阶段接口变更登记并向后兼容评估，回归门控作为 opsx-apply 验收的强制前置，回归基线与 Dev-Phase 完成时刻版本对齐，并显式标注已接受风险的不回归项。

## Requirements

### Requirement: 每个完成的 Dev-Phase MUST 冻结一份 Golden Demo

回归策略 MUST 规定：每当一个 Dev-Phase 通过验收（Go 判定），该阶段 MUST 冻结一份 Golden Demo。Golden Demo MUST 包含：(a) 一个具体的输入场景（自然语言需求或命令）；(b) 期望的端到端输出（文档/代码/状态变更）；(c) 期望的度量值范围（成本/延迟/合规率）；(d) 运行该 demo 的可执行命令或脚本路径。Golden Demo 一经冻结，MUST 不允许在该 Dev-Phase 内修改；后续修改需作为新一阶段变更的"基线升级"。

#### Scenario: Dev-Phase 0 完成时冻结其 Golden Demo
- **WHEN** Dev-Phase 0 通过 Go 判定（依据 `analysis/06-dev-phase-dod.md` DoD 演示场景）
- **THEN** 回归策略 MUST 冻结该 demo（输入："给这个 Python 项目加一个配置热重载功能"；输出：proposal → delta-spec + delta-design → 知识图更新；阈值：成本 ≤ $5、耗时 ≤ 10min、无崩溃）作为 Dev-Phase 0 的 Golden Demo

#### Scenario: 后续阶段启动前先重放历史 Golden Demo
- **WHEN** Dev-Phase N（N > 0）启动 `opsx-apply` 实现阶段之前
- **THEN** 回归策略 MUST 要求先重放所有 N−1 个历史 Golden Demo；任一历史 demo 不通过 MUST 阻断 Dev-Phase N 启动

### Requirement: 关键接口契约 MUST 捕获为契约测试

回归策略 MUST 维护一份"关键契约测试集"，将跨模块接口（WebSocket Push/RPC 消息、KnowledgeGraphQueryAPI、SafeAgent wrapper 接口、适配层 Flow 抽象、JSON Schema 输出）捕获为可执行的契约测试。每个 Dev-Phase 完成时 MUST 增量更新该测试集（新增本阶段引入的契约；不允许删除已有契约）。

#### Scenario: WebSocket 协议契约可被自动验证
- **WHEN** Dev-Phase 1 引入完整的 WebSocket IPC（依据 `analysis/00-sddp-pet-final.md` 第七节）
- **THEN** 回归策略 MUST 把 5 种 Push 消息 + 4 种 RPC 请求 + 4 种 RPC 响应 + 心跳 + message_id 关联机制编码为契约测试，并加入测试集

#### Scenario: 契约测试集单调增长
- **WHEN** 比较任意两个时刻 T1 < T2 的契约测试集
- **THEN** T2 时刻的测试集 MUST 是 T1 时刻的超集（只允许新增，不允许删除）；如需删除/变更某契约，MUST 走"接口变更登记"流程并标注 BREAKING

### Requirement: 跨阶段接口变更 MUST 登记并向后兼容评估

回归策略 MUST 维护一份"接口变更登记表"。任何 Dev-Phase 变更若修改了已被前一阶段冻结的接口（消息字段/契约 API/JSON Schema/文件格式），MUST 在该变更的 design 文档中登记：(a) 变更的接口名；(b) 变更类型（新增字段 / 修改字段 / 删除字段 / 语义变更）；(c) 向后兼容性评估（旧调用方是否仍可用）；(d) 迁移路径。BREAKING 变更 MUST 触发"前阶段 Golden Demo 升级"流程。

#### Scenario: 非 BREAKING 字段新增免升级
- **WHEN** 某 Dev-Phase 变更仅在已有 WebSocket Push 消息中新增可选字段
- **THEN** 该变更 MUST 在接口变更登记表中登记为"新增字段-向后兼容"，且无需升级前阶段 Golden Demo

#### Scenario: BREAKING 变更触发基线升级
- **WHEN** 某 Dev-Phase 变更修改了 KnowledgeGraphQueryAPI 的返回 schema（例如移除 `confidence` 字段）
- **THEN** 该变更 MUST 在登记表中标注 BREAKING、提供迁移路径，并 MUST 同时升级所有引用该 API 的历史 Golden Demo（保持其可重放）

### Requirement: 回归门控 MUST 作为 opsx-apply 验收的强制前置

回归策略 MUST 规定：任何 Dev-Phase 变更的 `opsx-apply` 验收阶段 MUST 在执行本阶段 DoD 之前先运行"历史回归套件"（Golden Demo 重放 + 契约测试集）。历史回归套件存在失败时 MUST 阻断验收，不允许"先合并再修"。

#### Scenario: 历史回归失败阻断验收
- **WHEN** Dev-Phase 3a 验收阶段运行历史回归套件时发现 Dev-Phase 0 的 Golden Demo 不通过
- **THEN** 回归门控 MUST 报告"回归失败"，阻断 Dev-Phase 3a 的 Go 判定，并 MUST 指向失败的 Golden Demo 与最可能的责任模块

#### Scenario: 回归套件执行时间有上限
- **WHEN** 历史回归套件累积到 5 个以上 Golden Demo
- **THEN** 套件 MUST 能在 30 分钟内（含 LLM 调用成本上限 $20）并行重放完成；超出时策略 MUST 提供"代表性子集回归"作为快速通道（不替代完整回归，仅用于早期反馈）

### Requirement: 回归基线 MUST 与 Dev-Phase 完成时刻版本对齐

回归策略 MUST 规定：每个 Dev-Phase 的 Golden Demo 与契约测试集 MUST 与该阶段完成时刻的 git tag / commit 对齐存储。后续阶段若需重放，MUST 明确声明是"在当前 HEAD 重放"还是"在历史 tag 重放"，以避免基线漂移。

#### Scenario: Golden Demo 与版本 tag 绑定
- **WHEN** Dev-Phase 1 通过验收
- **THEN** 回归策略 MUST 在该阶段 archive 时打上形如 `dev-phase-1-v1` 的 git tag，并将 Golden Demo 与该 tag 绑定

#### Scenario: 重放显式声明基线
- **WHEN** Dev-Phase 2 验收前重放 Dev-Phase 0 的 Golden Demo
- **THEN** 重放报告 MUST 显式记录"重放基线 = `dev-phase-0-v1` tag"和"重放目标 = 当前 HEAD"；两者差异 MUST 列入报告

### Requirement: 回归策略 MUST 标注已接受风险的不回归项

回归策略 MUST 明确列出"已接受风险"项（依据 `analysis/00-sddp-pet-final.md` 与 `analysis/01-final-review.md`）：对抗收敛 LLM 自引用悖论、vendor lock-in OpenAI、知识图扫描置信度边界、离线模式可靠性降级。这些项 MUST 不作为回归失败的判定依据（即不强制"修复"这些风险），但 MUST 在每次回归报告中显示其当前状态。

#### Scenario: 已接受风险不阻断验收
- **WHEN** 回归报告显示"对抗收敛 LLM 自引用悖论"仍存在
- **THEN** 该状态 MUST 标注为"已接受风险-不阻断"，不计入 Go/No-Go 判定

#### Scenario: 已接受风险状态在回归报告中可见
- **WHEN** 审查任一 Dev-Phase 的回归报告
- **THEN** 报告 MUST 包含"已接受风险"小节，列出四项已接受风险的当前观测状态（持续 / 缓解 / 恶化）
