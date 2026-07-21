## ADDED Requirements

### Requirement: engine-core MUST 实现 5 角色 CrewAI 线性 Flow

依据 `analysis/00` 第十节 MVP 线性流程与 `dod.md` D0-7、D0-9，engine-core MUST 实现一个 CrewAI Flow（经 `adaptation-layer`），驱动 5 个角色线性流转：需求官（解析 proposal + 查询知识图上下文）→ 调度官（可行性门控 + 3 用户确认点推进）→ 架构师（咨询代码资产管理员确认修改范围 + delta-spec + delta-design）→ 实施师（代码建议，不写文件）→ 代码资产管理员（知识图更新）。**Dev-Phase 0 范围**：跳过挑评师/实证师（Dev-Phase 2 引入对抗）；跳过验收师/复核师/规范员/修缮师（Dev-Phase 3 引入质量关卡）。

#### Scenario: 5 角色 Agent 可 kickoff
- **WHEN** 运行 `pytest tests/engine/test_5_roles_kickoff.py`（使用 MockFlowAdapter，不调用真实 LLM）
- **THEN** 5 个 Agent（需求官/调度官/架构师/实施师/代码资产管理员）MUST 全部能完成 kickoff；测试 MUST 退出码 0

#### Scenario: 线性 Flow 端到端跑通（CLI）
- **WHEN** 运行 `sddp run "给这个 Python 项目加一个配置热重载功能" --project tests/fixtures/sample-python-project/`
- **THEN** 命令 MUST 产出 proposal.md + 架构研究报告 + delta-spec.md + delta-design.md 4 个 markdown 文档；知识图 `scan_version` MUST 递增

### Requirement: 5 角色 MUST 有 backstory 编码 SDDP 行为约束

依据 `analysis/00` 第三节差距3，SDDP 角色行为约束（"不得自行扩展职责范围 / 禁止假设 / 禁止越权 / 代码修改设计须先咨询代码资产管理员"）MUST 编码为每个角色的 backstory（500–800 tokens/角色）。

#### Scenario: Backstory 含 SDDP 共性约束
- **WHEN** 审查 5 个角色的 backstory 内容
- **THEN** 每个 backstory MUST 显式包含 4 条共性约束（不扩展职责 / 引用上游 / 禁止假设 / 不越权）；MUST 引用 SDDP 设计文档相应章节作为来源

#### Scenario: 架构师 backstory 含"先咨询代码资产管理员"
- **WHEN** 审查架构师 backstory
- **THEN** backstory MUST 明确要求"修改范围须先咨询代码资产管理员确认影响面和隐藏依赖方"，对应 SDDP 全局约束第 5 条

### Requirement: output_pydantic MUST 强制 3 种输出文档结构化

依据 `dod.md` D0-8 与 `analysis/00` 第十节模块 5，engine-core MUST 使用 CrewAI `output_pydantic` 强制 3 种输出文档的 Pydantic 模型：`Proposal` / `DeltaSpec` / `DeltaDesign`。不符合 schema 的输出 MUST 被 pydantic 拒绝（抛 `ValidationError`）。

#### Scenario: 不符合 schema 的输出被拒绝
- **WHEN** 运行 `pytest tests/engine/test_output_schema_enforcement.py`，测试构造一个故意缺字段的 LLM 输出
- **THEN** pydantic MUST 抛出 `ValidationError`；测试 MUST 通过（断言 ValidationError 被抛出）

#### Scenario: 3 种文档 schema 字段齐全
- **WHEN** 审查 `sddp/schemas/proposal.py` / `delta_spec.py` / `delta_design.py`
- **THEN** `Proposal` MUST 含 SDDP proposal 格式模板的章节（需求背景/需求解析/变更范围预估/约束与风险/资源需求清单/流程建议/PCM）；`DeltaSpec` MUST 含（变更范围/接口契约/影响面分析/约束条件）；`DeltaDesign` MUST 含（架构决策/数据流/关键算法/模块划分/异常处理/编码参照）

### Requirement: engine-core MUST 提供 JSON ↔ Markdown 双向渲染

依据 `analysis/00` 第十节模块 7，engine-core MUST 提供 Pydantic 模型与 Markdown 文档的双向转换器：`to_markdown(model) -> str` 与 `from_markdown(md, model_cls) -> model`。Markdown 格式 MUST 与 SDDP 设计文档定义的格式模板一致（见 `../SDDP/SDDP智能小队设计文档.md` 第十节 PCM 章节及之后各 Phase 阶段输出格式）。

#### Scenario: 双向转换无损
- **WHEN** 给定一个 `Proposal` 实例，调用 `to_markdown` 再调用 `from_markdown`
- **THEN** 返回的 `Proposal` 实例 MUST 与原实例在所有字段上等价（除 Markdown 格式特有的空白字符外）

#### Scenario: Markdown 输出符合 SDDP 模板
- **WHEN** 审查 `to_markdown(Proposal(...))` 产出的 Markdown
- **THEN** 输出 MUST 含 SDDP proposal 格式模板的全部章节标题（`## 需求背景` / `## 需求解析` 等），章节顺序与 SDDP 设计文档一致

### Requirement: engine-core MUST 内置 token 计量与 cost_report 输出

依据 `dod.md` D0-11 / D0-12 / D0-13 与 `analysis/06` X-3（成本实测），engine-core MUST 在每次 Flow 执行时内置 token 计量，产出 `cost_report.json`，含字段：`measured_cost_usd` / `wall_clock_minutes_excluding_human_wait` / `structured_output_first_try_rate` / `total_tokens` / `round_tokens`。

#### Scenario: cost_report 含必需字段
- **WHEN** 任一 Flow 执行完成
- **THEN** `cost_report.json` MUST 写入；JSON MUST 含 `measured_cost_usd`（数值）、`wall_clock_minutes_excluding_human_wait`（数值）、`structured_output_first_try_rate`（0.0–1.0 数值）

#### Scenario: 度量值是实测非估算
- **WHEN** 审查 cost_report 生成代码
- **THEN** `measured_cost_usd` MUST 基于 OpenAI API 实际返回的 `usage.prompt_tokens` / `usage.completion_tokens` 与显式定价表计算（不允许基于轮次估算）；`structured_output_first_try_rate` MUST 基于 pydantic 验证失败重试次数实测

### Requirement: 实施师 MUST 仅产出代码建议不自动写文件

依据 `analysis/00` 第三节差距4（LLM 无法直接写文件），Dev-Phase 0 MVP 绕过策略：实施师 MUST 仅产出代码建议（markdown diff 形式），不自动写入用户文件系统。文件写入代理 `FileWriteProxy` 推迟到 Dev-Phase 3a。

#### Scenario: 实施师产出代码建议而非写文件
- **WHEN** 实施师 Agent kickoff 完成
- **THEN** 输出 MUST 是 markdown 格式的代码建议（含文件路径 + diff）；MUST NOT 调用任何文件写入 API（`open()` write 模式、`pathlib.Path.write_text` 等）

#### Scenario: 用户手动采纳建议
- **WHEN** CLI 显示实施师产出的代码建议
- **THEN** 用户 MUST 手动复制/应用建议到目标文件；引擎 MUST NOT 自动应用
