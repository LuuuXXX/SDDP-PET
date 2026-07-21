# SDDP-PET 模块分解（Module Decomposition）

> 数据属性：本文件是 `development-roadmap/spec.md` 中"模块分解必须显式且边界可寻址"需求的承载表。
> 数据来源：`analysis/00-sddp-pet-final.md`（技术选型与差距）、`analysis/06-dev-phase-dod.md`（Dev-Phase 与模块归属）、`analysis/02-code-knowledge-graph-design.md`（KG 子系统）。

---

## 一、模块清单

下表覆盖 SDDP-PET 全部 12 个最小模块集合。每个模块的"对外契约 / 上游依赖 / 下游消费 / 归属 Dev-Phase / 来源 analysis 文档"字段 MUST 非空。

| 模块名 | 对外契约 | 上游依赖 | 下游消费 | 归属 Dev-Phase | 来源 analysis 文档 |
|--------|----------|----------|----------|----------------|---------------------|
| `engine-core` | CrewAI Flow kickoff 接口；5 角色 Agent 入口（需求官/调度官/架构师/实施师/代码资产管理员）；output_pydantic 输出（proposal/delta-spec/delta-design） | `safe-agent-wrapper`、`adaptation-layer`、`code-knowledge-graph`（经由代码资产管理员） | `cli-runner`（Dev-Phase 0）、`desktop-pet-ui`（Dev-Phase 1+，经 `websocket-ipc`） | Dev-Phase 0 | `analysis/00` 第十节 MVP 范围；`analysis/06` 第二节 D0-3 |
| `code-knowledge-graph` | `KnowledgeGraphQueryAPI`：`find_callers(symbol_id, depth)` / `find_file_impact(file_path)` / `find_dependencies(symbol_id)` / `get_module_api(module_id)`，每查询返回 `{result, confidence, coverage_note}` | 无（独立预扫描器，输入为本地或远程代码库路径） | `engine-core`（代码资产管理员 Agent 通过此 API 提供权威代码知识） | Dev-Phase 0（KG-MVP：单语言 Python，无增量） | `analysis/02-code-knowledge-graph-design.md` 全文；`analysis/00` 第三节差距1 |
| `safe-agent-wrapper` | `SafeAgent.kickoff(input)` 同步接口；内部封装 tenacity retry + timeout；超时/失败抛出 `SafeAgentError` | 无（依赖 CrewAI 与 tenacity） | `engine-core`、`confrontation-flow`、`quality-gate-flow`（所有 CrewAI Agent 必须经此包装） | Dev-Phase 0（模块 3） | `analysis/00` 第四节 #6380；`analysis/03-crewai-version-strategy.md` |
| `adaptation-layer` | `FlowDefinition` 抽象（start/listen/router/persist 原语），与 CrewAI Flows API 解耦；底层 adapter 实现 CrewAI 适配 | 无 | `engine-core`、`confrontation-flow`、`quality-gate-flow` | Dev-Phase 0（模块 8） | `analysis/00` 第十节模块 8；`analysis/06` D0-1 |
| `cli-runner` | 命令行入口：`sddp run "<proposal>"`；3 个用户确认点的 stdin/stdout 交互；@human_feedback CLI adapter | `engine-core` | 终端用户 | Dev-Phase 0（模块 9） | `analysis/06` D0-3、D0-4 |
| `desktop-pet-ui` | Electron 双窗口：窗口1（透明，PixiJS 桌宠 + 气泡）；窗口2（不透明，React 状态面板/诊断面板/确认按钮/SSH 设置页）；穿透点击事件 | `websocket-ipc`（消息消费者） | 终端用户 | Dev-Phase 1（D1-1）；Dev-Phase 2 扩展（多角色桌宠 D2-3）；Dev-Phase 3b 扩展（8 角色桌宠 D3b-2） | `analysis/00` 第六节；`analysis/06` 第三节 D1-1、第四节 D2-3 |
| `websocket-ipc` | 5 种 Push 消息（agent_state_change/document_produced/cost_update/feedback_required/error）；4 种 RPC 请求（start_flow/user_feedback/resume_flow/abort_flow）；4 种 RPC 响应；心跳（30s ping）；message_id 关联 | FastAPI + CrewAI（`engine-core`） | `desktop-pet-ui`、`remote-mode`（远程时承载于 SSH 隧道） | Dev-Phase 1（D1-2） | `analysis/00` 第七节 WebSocket 通信协议 |
| `security-compliance` | API 密钥加密存储接口；隐私同意界面回调；代码预过滤管道（输入代码 → 脱敏摘要）；遥测禁用开关 | 系统密钥存储（Windows Credential Manager） | `engine-core`（密钥供给）、`desktop-pet-ui`（隐私界面）、`remote-mode`（脱敏） | Dev-Phase 1（D1-4） | `analysis/00` 第八节合规性要求 |
| `remote-mode` | SSH 隧道端口转发（localhost:8765）；远程 resume_flow RPC；远程引擎部署/更新/回滚（systemd/Docker） | `websocket-ipc`、`security-compliance`（API key 分发） | `desktop-pet-ui`（对前端透明，仍连 localhost:8765） | Dev-Phase 1（从 Dev-Phase 0 推迟，`analysis/06` 第二节 vFINAL.1 范围收窄） | `analysis/00` 第六节执行模式；`analysis/01` G9 |
| `execution-subsystem` | `SandboxedExecutor.run_test(test_spec)` → 结构化结果；`FileWriteProxy.write(diff)` → 用户可拒绝；`RuleMapper.predict(rule_set)` → 预测 lint 结果 | 无（沙箱独立） | `quality-gate-flow`（验收师/实施师/规范员通过此子系统执行） | Dev-Phase 3a | `analysis/05-quality-gate-flow-design.md`；`analysis/00` 第三节差距4 |
| `confrontation-flow` | `ConfrontationFlow`：架构师 ↔ 挑评师 ↔ 实证师多轮对抗；收敛检测（严重度规则映射 + max_rounds + escalate_to_user）；对抗记录文档输出 | `safe-agent-wrapper`、`adaptation-layer`、`code-knowledge-graph`（实证师验证依据） | `engine-core`（Dev-Phase 2 起接入，作为 SDDP 工作流 Phase 1 的实现） | Dev-Phase 2（D2-1、D2-2） | `analysis/00` 第十节 Dev-Phase 2；`analysis/crewai-technical-research.md` 第八节 |
| `quality-gate-flow` | `QualityGateFlow`：串行链 验收师→复核师→规范员；修复循环（最多 3 轮）；三种严重度术语（P0/P1/P2、P1-高/中/低、错误/警告/信息）；质量判定输出 | `safe-agent-wrapper`、`adaptation-layer`、`execution-subsystem` | `engine-core`（Dev-Phase 3b 起接入，作为 SDDP 工作流 Phase 3 的实现） | Dev-Phase 3b（D3b-1、D3b-2） | `analysis/05-quality-gate-flow-design.md`；`analysis/06` 第五节 |

---

## 二、角色 → 模块反向映射表

下表覆盖 SDDP 设计文档定义的全部 13 个角色（`../SDDP/SDDP智能小队设计文档.md` 第一节）。每个角色 MUST 至少归属一个模块；本表用于校验"无孤儿角色"。

| 角色 | 主归属模块 | 次归属模块 | 角色交付物 |
|------|-----------|-----------|-----------|
| 需求官 | `engine-core` | `cli-runner`（Dev-Phase 0）、`desktop-pet-ui`（Dev-Phase 1+） | proposal + PCM + 资源需求清单 + 流程判定 |
| 调度官 | `engine-core` | `confrontation-flow`、`quality-gate-flow` | 可行性确认、对抗裁决、任务清单、伸缩决策 |
| 架构师 | `engine-core` | `confrontation-flow` | 架构研究报告、delta-spec、delta-design |
| 挑评师 | `confrontation-flow` | — | 对抗记录（质疑维度） |
| 实证师 | `confrontation-flow` | `execution-subsystem`（Dev-Phase 3a 起验证手段增强） | 实证报告 |
| 实施师 | `engine-core` | `execution-subsystem`（FileWriteProxy，Dev-Phase 3a 起） | 实施代码（Dev-Phase 0 仅建议）、实施日志 |
| 代码资产管理员 | `code-knowledge-graph` | `engine-core`（作为 Agent 接入） | 知识图更新记录、代码资产查询结果 |
| 验收师 | `quality-gate-flow` | `execution-subsystem`（SandboxedExecutor 执行验证） | 验收报告 |
| 复核师 | `quality-gate-flow` | — | 复核报告 |
| 规范员 | `quality-gate-flow` | `execution-subsystem`（RuleMapper） | 规范报告 |
| 修缮师 | `quality-gate-flow` | `execution-subsystem`（FileWriteProxy） | 修复补丁、修复报告 |
| 版本管理员 | `engine-core` | — | 版本发布报告、变更日志、合并请求、版本标签 |
| 交付官 | `engine-core` | `desktop-pet-ui`（Dev-Phase 1+ 渲染交付报告） | 交付报告、迁移指引、反馈记录、知识沉淀记录 |

**孤儿角色校验**：13/13 角色均至少归属 1 个模块，无孤儿角色 ✓。
