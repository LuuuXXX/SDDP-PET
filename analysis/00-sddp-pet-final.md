# SDDP-Pet 项目可行性分析（最终版）

> 日期: 2026-07-20
> 版本: vFINAL.1 — 经3轮审查(整体合规+技术可行性+多角度深度梳理) + P0缺口补齐轮
> 本文件是唯一决策依据
> 
> **vFINAL.1 更新(2026-07-20 同日)**: 5项P0缺口已补齐(见文档02-06),MVP范围收窄,Dev-Phase 3拆分,已接受风险显式登记。本文件各章节已集成补齐结论。

---

## 文件关系

| 文件 | 用途 |
|------|------|
| research-summary.md | 桌宠技术调研原始数据 |
| technical-research-findings.md | 6项技术验证 |
| crewai-technical-research.md | CrewAI深度验证+Phase 1代码示例 |
| **01-final-review.md** | **收口审查(找出P0/P1/P2缺口)** |
| **02-code-knowledge-graph-design.md** | **G1: 知识图子系统(SCIP+tree-sitter)设计** |
| **03-crewai-version-strategy.md** | **G2: CrewAI版本锁定准则与验证流程** |
| **04-llm-provider-strategy.md** | **G3: provider能力矩阵与降级策略** |
| **05-quality-gate-flow-design.md** | **G4: Phase 3质量关卡Flow设计** |
| **06-dev-phase-dod.md** | **G5: 各Dev-Phase Definition of Done** |

---

## 一、核心结论

**项目可行, 先做有线场景MVP(已收窄: 仅本地引擎+5角色线性+CLI, 见第十节), 离线能力推迟到Dev-Phase 5**

**目标平台: Windows桌面(桌宠UI+引擎); Linux仅作为远程任务执行服务器(通过SSH配置)**

SDDP设计文档与LLM现实有4处关键差距(差距1已收口为"带置信度的权威", 见02); CrewAI Flows API中等风险(版本锁定见03); LLM无法直接扫描代码库→SCIP知识图子系统(见02); 对抗收敛依赖LLM裁决存在可靠性悖论(标注为已接受风险). **MVP锁定OpenAI为唯一provider**(见04), provider抽象层为未来降级铺路.

---

## 二、技术选型

| 技术 | 角色 | 理由 |
|------|--------|------|
| Electron | 桌宠框架 | Windows原生透明窗口+穿透点击; clawd-on-desk验证; MVP开发效率优先 |
| CrewAI(Python) | 引擎骨架 | 8/10功能对齐; Flows=Phases; Agents=角色; 版本锁定见03 |
| 双窗口 | 前端架构(Phase 1) | 事件隔离; clawd-on-desk验证 |
| PixiJS | 动画渲染 | 2D角色动画; Chromium WebGL可靠 |
| WebSocket(FastAPI) | IPC | 双向实时; 匹配@human_feedback |
| SQLite+Markdown | 数据层 | 结构化存储+人类可读 |
| **SCIP + tree-sitter** | **代码知识图(取代虚构的GitNexus/Graphify)** | **业界事实标准索引协议, 20+语言覆盖; 详见02** |
| 三层LLM保障 | 输出可靠性 | Structured Outputs(99.9%)+pydantic(85-95%)+guardrails; **MVP锁OpenAI-only, 见04** |
| MIT | 项目许可 | 兼容所有依赖; 避开Live2D GPL冲突 |
| SSH隧道 | 远程执行 | Linux服务器跑SDDP流程; 前端连localhost:8765(对前端透明) |

不选: PySide6(动画有限); 从零构建引擎(CrewAI覆盖80%); 从零造知识图(用SCIP, 见02)

可选替代: Tauri(Windows透明窗口可用, 体积/内存10x优于Electron, 常驻运行场景优势明显; 但MVP阶段开发效率优先, Phase 4可迁移)

**provider定位(vFINAL.1)**: MVP锁定OpenAI(Tier-S, Structured Outputs 99.9%); Claude/Gemini(Tier-A)/Mistral(Tier-B)/Ollama(Tier-C)经抽象层支持但可靠性降级(重试成本2-4x); 离线≠完整SDDP而是降级版。护城河是引擎可靠性, 非开源离线。详见04。

---

## 三、SDDP设计文档 vs LLM现实—3处关键差距

### 差距1: LLM无法直接扫描代码库 ✅ 已收口(详见02)

SDDP要求角色"扫描代码库" -> LLM无文件系统访问

**收口方案(02)**: 代码资产管理员(智能体) + SCIP知识图子系统(取代此前模糊的"GitNexus/Graphify"—该名称不对应已知成熟项目)
- 知识图技术栈: **SCIP(Sourcegraph Code Intelligence Protocol) + tree-sitter**, 业界事实标准, 20+语言覆盖(Apache-2.0, MIT兼容)
- schema: 5类节点(Repository/File/Symbol/Module/Package)+8类边(DEFINES/REFERENCES/CALLS/IMPORTS/INHERITS/CONTAINS/DEPENDS_ON/DECLARED_IN_MANIFEST)+3派生视图(reverse_call_graph/file_impact_set/module_public_api)
- 4类核心查询: 影响面(Q1)/依赖方(Q2)/隐藏依赖(Q3)/对外接口(Q4), 每类返回**带置信度**结果
- 代码资产管理员(Agent)通过 KnowledgeGraphQueryAPI 唯一入口访问, 作为唯一权威代码知识来源
- SDDP全局约束: "代码修改设计须先咨询代码资产管理员", 架构师/实施师修改范围必须先获管理员确认
- 本地模式: 预扫描器扫描本地项目, 知识图存本地SQLite
- 远程模式: SSH exec远程执行扫描脚本; 知识图留在远程服务器 + 摘要回传Windows

**架构**: 预扫描器(SCIP+tree-sitter)→SQLite知识图→KnowledgeGraphQueryAPI→代码资产管理员(Agent)→其他角色查询

**关键修订—权威性是"带置信度的"**: 任何静态分析都无法100%覆盖真实代码库(动态导入/反射/eval/生成代码)。因此知识图不承诺绝对权威, 而承诺**带置信度的权威**: 每查询返回 confidence(HIGH/MEDIUM/LOW)+coverage_note; 架构师引用时须在delta-spec标注查询置信度。这把"伪权威风险"转化为"可管理的已知不确定性"。

**实施验证**: 设计层面已完整定义(02), 工期重估 **3-4.5周**(原"2-3天"严重低估, 02第八节), 分 KG-MVP(2-2.5周,够Phase0)/v1/v2 三阶段交付避免阻塞。

| 模块 | 代码资产管理员(Agent) | 预扫描器(系统组件) |
|------|--------|------|
| 需求官 | 上下文概览 | 管理员查询结果供给 |
| 架构师 | 修改影响面+隐藏依赖 | 管理员查询结果供给 |

### 差距2: 对抗收敛检测依赖LLM裁决 ⚠️ 已接受风险(非"已解决")

LLM判断LLM输出是否可靠 = 自引用验证, 0外部锚点

**缓解(部分机械化, 核心仍是LLM判断—明确标为已接受风险)**:
- 实证报告是否有量化数据->检查JSON字段(可编程)
- 严重程度评估->规则映射(高/中/低=LLM输出+规则验证)
- 高严重程度不得驳回->backstory硬编码+guardrail验证
- 收敛判据仍含"质疑维度是否达可接受"的LLM主观判断—**此为SDDP固有局限, 无纯技术解法, 接受**

**No-Go兜底**: 若对抗收敛实际无法判定(Dev-Phase 2验证暴露), 需引入外部裁决信号(如用户提早介入/基于测试通过率的客观锚点)。见06 Dev-Phase 2 No-Go条件B。

### 差距3: SDDP角色行为约束vs LLM自由度

SDDP要求"不得自行扩展职责范围/禁止假设/禁止越权" -> LLM约85-90%遵守率

解决: 约束编码为backstory(500-800t/角色)+guardrails验证

### 差距4: LLM无法直接运行代码/写文件/执行lint工具

验收师需运行代码验证→LLM无执行环境; 实施师需写文件→LLM无文件系统写入; 规范员需执行lint→LLM无工具调用能力

MVP绕过(不阻断Dev-Phase 0):
- 实施师仅产出代码建议, 不自动写文件(用户手动采纳)
- 验收师功能验证推迟到Dev-Phase 3a(代码执行代理SandboxedExecutor)
- 规范员用规则映射(静态规则→lint结果预测)而非实际执行lint

**Dev-Phase 3a需子系统方案(详见05, Phase 3拆为3a+3b)**:
- 代码执行代理(SandboxedExecutor): 安全沙箱中运行验收师指定测试
- 文件写入代理(FileWriteProxy): 实施师代码建议→写入文件+diff确认
- lint规则映射器(RuleMapper): 规范员静态规则→lint结果预测+CI实际执行验证

**Dev-Phase 3拆分**: 3a(执行子系统3-4周)→3b(Phase 3 Flow+4角色2-3周)=5-7周(原"4-6周"低估)。Phase 3完全不在MVP(连骨架都不在, 因依赖执行子系统)。

---

## 四、CrewAI Flows API真实风险

| 风险 | 严重度 | 状态 | 应对 |
|------|--------|------|------|
| #6380异步静默冻结 | 极高 | 未修复 | SafeAgent wrapper(tenacity+timeout) |
| #5972 or_()循环bug | 高 | 已修复 | 锁定版本 |
| Flows API重构 | 高 | 进行中 | 适配层抽象 |
| #6347 human_input崩溃 | 高 | 已修复 | 用Flow的@human_feedback |
| #6370 router上限 | 中 | PR开放 | SDDP 5轮(20 hops)远低于100 |

验证策略: Phase 0先做简化对抗(1维度3轮), 确认可行后再完整实现

---

## 五、CrewAI Flow代码5个Bug

| Bug | 影响 | 修正 |
|------|------|------|
| 双重触发 | architect_revise_design也监听design_produced | 只监revision_needed |
| round_count双重递增 | produce+revise各递增一次 | 仅router循环入口递增 |
| 挑评师串行执行 | for循环串行kickoff() | asyncio.gather并行 |
| _parse_*未实现 | pass | output_pydantic强制结构+自定义解析 |
| FastAPI阻塞 | flow.kickoff()同步在async handler | asyncio.to_thread() |

---

## 六、架构细节

### 目标平台: Windows桌面

桌宠UI仅在Windows运行; SDDP引擎(CrewAI)可本地或远程(Linux服务器)执行.

### 执行模式

- **本地模式**: CrewAI引擎在Windows本机运行; Electron用child_process.spawn启动FastAPI+CrewAI; 需本地Python(3.10+); 进程崩溃检测+自动重启
- **远程模式**: CrewAI引擎在Linux服务器运行; Windows仅运行桌宠UI; SSH隧道端口转发(ssh -L 8765:localhost:8765)承载WebSocket; 前端连localhost:8765(对前端透明)
- 配置文件: `execution.yaml` 指定mode(local/remote), remote时填host/port/key_ref(密钥路径引用, 实际密钥存系统密钥存储)

**远程模式配置UX**: Phase 1桌宠面板中设"设置"页, 用户填写SSH host/port/用户名; 密钥通过系统密钥存储API导入; 连接失败时面板显示错误提示+重试按钮

### 本地Python环境管理

- 检测: 启动时检测python可用性+版本(3.10+)+crewai安装状态; 不满足时弹窗引导安装
- Phase 1+: 考虑打包嵌入式Python(减少用户配置负担)
- 进程管理: Electron main process spawn FastAPI子进程, 端口8765; 健康检查(定时ping /health); 崩溃重启(最多3次后提示用户)

### 远程模式崩溃恢复

本地模式: @persist SQLite在本机, 可直接from_pending恢复
远程模式: SQLite在远程服务器, 本地无法直接访问; 恢复方案: 通过RPC resume_flow指令远程恢复, 不需要本地SQLite

### 双窗口(Phase 1实现)

- 窗口1(透明): PixiJS桌宠+气泡(纯PixiJS, 0React DOM)
- 窗口2(不透明): React状态面板+诊断面板+确认按钮+成本显示+SSH设置页

为什么不用混合: PixiJS Canvas和React DOM事件系统冲突

### 穿透点击(Windows)

- 进入宠物区域: setIgnoreMouseEvents(false) -> 可交互
- 离开宠物区域: setIgnoreMouseEvents(true, {forward:true}) -> 穿透+转发

### 位置持久化

- win.getPosition()保存localStorage, 启动时win.setPosition()恢复

---

## 七、WebSocket通信协议

### Push消息(引擎→前端, 5种)
```
agent_state_change: {agent, state, phase, round, detail, timestamp}
document_produced: {agent, doc_type, doc_id, summary, timestamp}
cost_update: {total_tokens, estimated_cost_usd, round_tokens, timestamp}
feedback_required: {flow_id, method, message, output, timestamp}
error: {agent, error_type, message, timestamp}
```

### RPC请求(前端→引擎, 4种)
```
start_flow:    {message_id, proposal, pcm, project_path}
user_feedback: {message_id, flow_id, feedback, outcome}
resume_flow:   {message_id, flow_id, feedback}
abort_flow:    {message_id, flow_id}
```

### RPC响应(引擎→前端, 4种)
```
flow_started:      {message_id, flow_id, status: "running"}
feedback_accepted: {message_id, flow_id, status: "resuming"}
flow_resumed:      {message_id, flow_id, status: "running"}
flow_aborted:      {message_id, flow_id, status: "aborted"}
```

### 错误消息格式(增强)
```
error: {agent, error_type, error_code, message, severity, recoverable, timestamp}
error_code枚举: LLM_TIMEOUT / LLM_AUTH_FAIL / LLM_RATE_LIMIT / PARSE_FAILURE / FLOW_STUCK / KNOWLEDGE_GRAPH_ERROR / SSH_CONNECTION_LOST
severity: critical / error / warning
recoverable: true/false
```

### 心跳机制
- 引擎每30秒发送ping; 前端10秒内回复pong; 3次连续未回复触发连接丢失事件
- 连接丢失后: 前端显示"连接中断"提示+重连按钮; 引擎暂停flow等待重连

### 消息关联机制
- 每个RPC请求包含message_id(UUID); 引擎响应当中包含相同message_id用于请求-响应关联

CrewAI Flows同步 -> 方法前后推送working/idle; MVP不做流式(Dev-Phase 2+考虑)

### 连接方式(两种模式统一)

- 本地模式: 直连localhost:8765
- 远程模式: SSH隧道端口转发 -> 前端仍连localhost:8765
- 前端无需区分模式, 仅配置不同WebSocket URL来源

---

## 八、合规性要求

| 要求 | 实现 | 工期 |
|------|--------|------|
| MIT许可 | 项目许可=MIT | 0天 |
| Live2D GPL冲突 | 可选独立模块(不捆绑) | 0天 |
| 隐私同意界面 | 首次启动弹窗(含远程数据传输提示) | 0.5周 |
| API密钥加密 | 系统密钥存储(Windows Credential Manager/macOS Keychain) | 1-2周 |
| 代码预过滤 | 本地预扫描→脱敏→仅发送脱敏摘要(远程); 本地直接处理(本地) | 1周 |
| AI身份标注 | 桌宠气泡旁标注"AI驱动" | 0.5周 |
| 数据保留 | SQLite可配置清理(7/30/永久) | 0.5周 |
| 审计日志 | 记录所有数据发送行为 | 0.5周 |
| 遥测禁用 | OTEL_SDK_DISABLED=true | 0天 |

不做: zero-data-retention(企业级); DPA(企业级); 离线(Phase 5)

---

## 九、成本模型(二次修正)

### 场景成本(基于OpenAI Tier-S假设, 详见04)

| 场景 | 修正估算 | 成本驱动因子 |
|------|----------|------------|
| 快速通道 | **$1** | backstory+模板+历史膨胀 |
| 最小完整 | **$3** | 同上 |
| 中等(3对抗+2修复) | **$6** | 同上 |
| 复杂(5对抗+3修复) | **$12.5** | 同上 |

关键遗漏(二次修正): backstory注入(5角色×500-800t=2.5-4k/轮; 5轮累积注入约12.5-20k)+历史上下文膨胀(每轮累积prompt增加约40-60k/轮×5轮=200-300k)+代码资产管理员知识查询(约200-400t/次×3次/轮=3-5k)+实施师咨询代码资产管理员(约200-400t/次×1-2次/流程=0.4-0.8k)+@human_feedback分类(gpt-4o-mini,约0.5-1k/次×3-5次/流程=1.5-5k)+收敛裁决(调度官kickoff,约1-2k/次×1-3次/流程=1-6k)+文档模板(30-40k)=250-370k tokens/流程

### Provider维度成本对比(详见04第五节)

| 场景 | OpenAI(Tier-S) | Claude(Tier-A) | 本地Ollama(Tier-C) |
|------|---------------|----------------|---------------------|
| 快速通道 | $1 | $2-3(重试) | $0(电费)但延迟3-5x |
| 中等 | $6 | $12-18 | $0但单流程30-60min |
| 复杂 | $12.5 | $25-40 | $0但可能因解析失败卡死 |

**结论**: 非OpenAI不是"免费替代"而是"用延迟/失败率换金钱"。MVP选OpenAI是经济性+可靠性双重最优。成本模型待Phase0内置token计量后用实测校准(06 D0-5)。

---

## 十、MVP范围

MVP聚焦有线场景; 桌宠仅在Windows运行, Linux仅作远程服务器

> **vFINAL.1 范围收窄(01-review建议)**: Dev-Phase 0 砍掉安全合规(模块11/12/13)和远程模式(模块10), 全部推迟到 Dev-Phase 1。Dev-Phase 0 只做"本地引擎+5角色线性+CLI+成本计量", 目标是最快验证核心引擎可行。安全合规省下的工时填补知识图扩工期。

> 注: 本文档"Dev-Phase 0-5"指SDDP-Pet产品开发阶段，区别于SDDP工作流"Phase 0-6"(需求解析→方案对抗→编码→质量关卡→归档→版本→交付)

### MVP线性流程(5角色, 0对抗)

需求官(解析proposal+查询代码资产管理员获取上下文) → 调度官(可行性门控+3个用户确认点) → 架构师(咨询代码资产管理员确认修改范围+delta-spec+delta-design) → 实施师(代码建议, 不自动写文件) → 代码资产管理员(知识图更新)

跳过: 挑评师/实证师/验收师(Phase 2引入对抗); 复核师/规范员(Phase 3引入质量关卡)

### Dev-Phase 0模块及依赖顺序(收窄后)

| 序号 | 模块 | 范围 | 工期 | 前置依赖 |
|------|------|--------|------|----------|
| **0** | **CrewAI版本选定+验证+lockfile**(新增, 见03) | 4准则选型+验证脚本+精确patch锁定 | 1-2天 | 无(所有Python工作第0步) |
| 1 | 本地Python环境管理 | Python检测+进程spawn+健康检查+崩溃重启 | 1-2天 | 0 |
| 2 | **知识图KG-MVP**(扩工期, 见02) | **SCIP索引+SQLite图存储+4类查询(带置信度)+单语言(Python)+静态置信度; 不含增量** | **12-15天(原2-3天)** | 0 |
| 3 | SafeAgent wrapper | tenacity retry+timeout(硬性前提,#6380未修复) | 1天 | 0 |
| 4 | CrewAI 5角色 | 需求官/调度官/架构师/实施师/代码资产管理员(简化backstory) | 2-3天 | 3 |
| 5 | JSON Schema最小集 | proposal+delta-spec(2种) | 2-3天 | 无(可与4并行) |
| 6 | Phase 0+2简化Flow | 线性流程(0对抗), CLI验证 | 3-4天 | 2,4,5 |
| 7 | JSON-Markdown渲染 | 双向转换器 | 2-3天 | 5 |
| 8 | 适配层抽象 | Flow定义与CrewAI解耦 | 1-2天 | 6 |
| 9 | CLI交互验证 | 用户确认点通过CLI | 1天 | 6,8 |
| — | ~~远程执行连接器~~ | **推迟到Dev-Phase 1** | — | — |
| — | ~~API密钥加密~~ | **推迟到Dev-Phase 1** | — | — |
| — | ~~代码预过滤~~ | **推迟到Dev-Phase 1** | — | — |
| — | ~~隐私同意界面~~ | **推迟到Dev-Phase 1** | — | — |

Dev-Phase 0工期(收窄后): **3-4周**(砍安全合规省工时填补KG扩工期)

**关键路径**: 0→3→4→6→9 (本地引擎核心链); 模块2(KG)与4(角色)可并行

### Dev-Phase后续(Phase 3拆分, 工期重估)

| Dev-Phase | 核心目标 | 工期 |
|-------|----------|------|
| 1 | 桌宠前端MVP(单角色+双窗口+AI标注+成本面板+诊断面板)+**安全合规从Phase0转来**(API密钥加密/隐私界面/代码预过滤/AI标注/遥测禁用)+**监控可观测**+**远程模式** | 3-4周 |
| 2 | 对抗验证(SDDP工作流Phase 1, 1维度3轮→3维度5轮)+4角色桌宠+动态出场+WebSocket Provider+并发流程基础 | 5-7周 |
| **3a** | **执行子系统**(SandboxedExecutor+FileWriteProxy+RuleMapper, 见05) | **3-4周** |
| **3b** | **Phase 3质量关卡Flow+4角色(验收/复核/规范/修缮)+审计日志** | **2-3周** |
| 4 | 高级特性(Live2D可选/VSCode伴侣/LangGraph备选/对抗回放/Tauri迁移评估) | 5-7周 |
| 5(可选) | 离线(Ollama, **降级版非完整SDDP**, 见04第六节)+Linux桌面+国际化; 前置须先做Tier-C可行性验证 | 4-6周 |

总工期: **21-35周(5.25-8.75个月)** Dev-Phase 5为可选; Phase 3由原4-6周上修为5-7周(3a+3b)

### Dev-Phase DoD与Go/No-Go

各Dev-Phase的可度量退出标准、Go/No-Go门槛(含失败回退路径)详见 **06-dev-phase-dod.md**。关键No-Go条件:
- 知识图召回率<70% → 回KG设计修正
- CrewAI循环在生产场景不稳 → 回03重选版本/考虑LangGraph
- 单流程成本>$15 → 重审成本驱动因子
- Structured Outputs合规率<95% → 回04 provider策略

---

## 十一、风险矩阵

| 风险 | 严重度 | 概率 | 缓解 |
|------|--------|------|------|
| CrewAI #6380异步静默冻结 | 极高 | 高 | SafeAgent wrapper(tenacity+timeout) |
| API密钥泄露 | 极高 | 中 | 系统密钥存储加密 |
| 代码泄露给LLM API | 高 | 高 | 本地预过滤+隐私同意 |
| 跨网络数据泄露 | 高 | 低 | SSH隧道天然加密+预过滤在发送端 |
| CrewAI Flow代码5bug | 高 | 确定 | 修正+锁定版本 |
| SDDP设计文档vs LLM现实差距 | 高 | 确定 | 预扫描器+机械化收敛+backstory编码 |
| **对抗收敛LLM自引用悖论(差距2)** | **中** | **确定** | **部分机械化; 核心仍是LLM判断, 标为已接受风险; No-Go时引入外部锚点(见06)** |
| **vendor lock-in OpenAI(04)** | **中** | **确定** | **MVP锁OpenAI换取可靠性; 抽象层为降级铺路; 已接受** |
| **知识图扫描置信度边界(02)** | **中** | **确定** | **带置信度的权威; coverage_note暴露给上层; 已接受** |
| LLM无法运行代码/写文件/执行lint(差距4) | 高 | 确定 | MVP绕过(仅建议不写/推迟验收/规则映射); Dev-Phase 3a子系统(见05) |
| LLM输出不可靠 | 高 | 高 | 三层保障(Structured Outputs+pydantic+guardrails) |
| CrewAI API重构 | 高 | 中 | 适配层抽象 |
| CrewAI Windows兼容性 | 中 | 中 | ProactorEventLoop+路径规范化+Windows测试 |
| SSH连接中断/远程不可达 | 中 | 中 | 重连机制+本地fallback提示 |
| 远程预扫描数据不完整 | 中 | 低 | SCP校验+重试+本地fallback缓存 |
| 速率/并发瓶颈 | 中 | 高 | 退避+队列 |
| 成本低估 | 中 | 确定 | 修正成本模型 |
| Prompt注入 | 中 | 中 | 输入验证 |
| 竞争者跟进 | 低 | 中 | 引擎壁垒 |

---

## 十二、竞争定位

**核心护城河(vFINAL.1修正): SDDP引擎的可靠性 + 对抗/裁决/质量关卡/PCM** — 而非"开源离线"(因MVP锁OpenAI, 见04)

| 层级 | 壁垒 | 模仿难度 |
|------|--------|----------|
| SDDP引擎+可靠性 | 功能壁垒+可靠性壁垒 | 高 |
| 合规安全 | 隐性壁垒 | 中 |
| 适配层 | 非显性壁垒 | 中 |
| 桌宠UI | 低壁垒 | 低 |

Windows目标对定位的影响: 用户基数更大(优势); Linux开发者通过远程模式覆盖(Dev-Phase 5补本地)

> **待补(01-review G14)**: 竞品功能对标矩阵(clawd-on-desk 5.4k★/openpets 929★)在Dev-Phase 1初期补, 用于精化定位。

---

## 十三、缺失考虑标注(P0已补齐, P1待对应Dev-Phase)

> vFINAL.1: 部分原"缺失"项已通过P0补齐(02-06)。下表更新状态。

| 考虑项 | 状态 | 待定义Dev-Phase | 说明 |
|--------|------|----------------|------|
| 测试/QA策略 | ✅部分(知识图验证套件见02) / 🔲其余待补 | Dev-Phase 0 | CrewAI agent单测(无LLM调用,需mock/fixture,01-review G15)+SDDP流程集成测试+E2E+WebSocket协议测试 |
| 监控/可观测性 | 🔲待补 | Dev-Phase 1 | 4指标(执行时间/agent延迟/token消耗率/错误率)+日志+告警+诊断面板数据源 |
| 部署/分发策略 | 🔲待补 | Dev-Phase 1 | Electron打包(asar/签名/notarization)+自动更新+安装器+CI/CD |
| 并发流程模型 | 🔲待补 | Dev-Phase 2 | 多SDDP流程并发+调度官多proposal+Flow实例隔离+@persist数据分离(01-review G11) |
| WebSocket安全 | 🔲待补 | Dev-Phase 1 | 连接认证+授权+CSRF+TLS+输入验证schema |
| 数据备份/恢复 | 🔲待补 | Dev-Phase 0 | SQLite备份+schema迁移+历史清理+归档 |
| LLM密钥管理生命周期 | ✅provider策略(04) / 🔲密钥轮换待补 | Dev-Phase 0 | 多provider密钥+轮换+配额耗尽+per-flow选择; **provider切换=可靠性降级(见04)** |
| **快速通道(Fast Track)** | 🔲待补(01-review G6) | Dev-Phase 1 | 需求官简单/复杂判定逻辑+Flow结构+桌宠视觉 |
| **PCM获取/解析机制** | 🔲待补(01-review G7) | Dev-Phase 1 | 六大配置域从真实配置文件提取(跨语言/跨工具) |
| **角色视觉/动画状态机** | 🔲待补(01-review G8) | Dev-Phase 2 | 13角色→桌宠映射+每角色动画状态空间 |
| **远程模式部署链路** | 🔲待补(01-review G9) | Dev-Phase 1 | Docker/systemd+API key分发+更新回滚(2-3周) |
| **Windows CrewAI依赖摩擦** | 🔲待补(01-review G10) | Dev-Phase 1 | 嵌入式Python+预编译wheel(可能是#1采用摩擦) |
| **国际化/提示词语言** | 🔲待补(01-review G13) | Dev-Phase 5 | 中文prompt影响输出质量与目标用户群, 是基础设计选择 |

---

## 十四、下一步行动

**P0已全部补齐(02-06), 方案完备到可进入实现。**

1. **创建OpenSpec change** 进入 Dev-Phase 0 实现。建议change范围 = 06的Dev-Phase 0 DoD(D0-1~D0-5)
2. Dev-Phase 0按收窄后的模块顺序(模块0版本选定→...→模块9 CLI验证)实现最小SDDP引擎
3. Dev-Phase 0达DoD(06 D0-1~D0-5)→Dev-Phase 1(桌宠前端+安全合规+远程模式+监控)
4. Dev-Phase 1达DoD→Dev-Phase 2(对抗验证+多角色)
5. Dev-Phase 2达DoD→Dev-Phase 3a(执行子系统)→3b(质量关卡Flow)
6. 任一Dev-Phase触发No-Go条件(06)→按回退路径修正

**P1项(G6-G10)处理时机**: 不阻塞当前启动, 在进入对应Dev-Phase前各自做一轮小分析即可。

**已接受风险(无需进一步处理, 仅登记)**:
- 对抗收敛LLM自引用悖论(差距2)
- vendor lock-in OpenAI(04)
- 知识图扫描置信度边界(02)
- 离线模式可靠性降级(04)
