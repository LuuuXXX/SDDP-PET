# SDDP-Pet 分析收口审查（最终轮）

> 日期: 2026-07-20
> 审查范围: SDDP设计文档(源规格) + SDDP-Pet/analysis/* (4份分析)
> 审查目标: ① 找出未考虑的内容 ② 校验输出完备性 ③ 判定整体方案合理性与可行性
> 结论: **方案整体可行，但有 5 项 P0 缺口必须在进入实现前补齐；另有 2 处工期/范围判断偏乐观需修正。**
>
> **更新(2026-07-20 同日)**: 5 项 P0 缺口已全部补齐，见文档 02-06。本文档下方 P0 章节标注"✅已收口"并指向补齐文档。P1/P2 仍开放，建议在对应 Dev-Phase 初期处理。

---

## 一、总体判定

| 维度 | 判定 | 说明 |
|------|------|------|
| 技术选型 | ✅ 合理 | Electron+CrewAI+FastAPI+SQLite 选型有证据支撑，Tauri 作为后备路径清晰 |
| 架构 | ✅ 基本合理 | 双窗口/WebSocket/双模式(本地+远程)/三层LLM保障 逻辑自洽 |
| 差距识别 | ⚠️ 不完整 | 识别了 4 处 SDDP↔LLM 差距，但漏掉了若干结构性缺口（见下） |
| 工期 | ⚠️ 偏乐观 | 知识图子系统、远程部署、Windows环境 3 处低估 |
| 风险 | ⚠️ 漏报 | 顶层风险(CrewAI动荡+vendor lock-in)权重不足 |
| 输出完备性 | ⚠️ 中等 | 4 份分析覆盖调研与决策，但缺架构/数据模型/测试/部署 4 类工程产物 |

**核心判断**: 不要直接进入 Dev-Phase 0 编码。先补齐下方 P0 缺口（预计 3-5 天分析工作），可避免 Phase 0 中后期的重大返工。

---

## 二、未考虑的内容（按优先级）

### P0 — 阻塞实现，必须在 Dev-Phase 0 编码前补齐 ✅ 已全部收口(2026-07-20)

> 补齐文档: 02-code-knowledge-graph-design.md / 03-crewai-version-strategy.md / 04-llm-provider-strategy.md / 05-quality-gate-flow-design.md / 06-dev-phase-dod.md

#### G1. 代码知识图子系统规格缺失（最大单点风险）✅ 已收口 → 02-code-knowledge-graph-design.md
分析反复引用 "GitNexus/Graphify，自定义Python工具"，但：
- **这两个不是已知成熟项目**（GitHub 无对应知名仓库），等于把核心子系统建立在虚构依赖上
- 知识图 schema 完全未定义：节点是什么(文件/函数/类/模块)？边是什么(调用/继承/导入/数据流)？如何回答"依赖方/影响面/隐藏依赖"这三类 SDDP 核心查询？
- 查询接口未定义：代码资产管理员 Agent 如何向知识图提问？自然语言→图查询的转换层？
- 增量更新机制未定义：实施师改了代码后，知识图如何局部更新（而非全量重扫）？
- **工期严重低估**: "Dev-Phase 0 模块2: 2-3天"。一个能支撑"影响面/隐藏依赖"查询的代码知识图，现实工期是 **2-3 周**（含 schema 设计+解析器+查询引擎+准确性验证）

**影响**: 这是整个 SDDP "禁止假设/代码修改须先咨询管理员"原则的技术地基。地基不稳，上层所有角色的"权威代码知识"都不可靠。

**✅ 收口方案(02)**: 采用 SCIP(Sourcegraph Code Intelligence Protocol)+ tree-sitter 混合(取代虚构的 GitNexus/Graphify)；定义完整 schema(5类节点/8类边/3派生视图)；4类查询 API 带置信度返回；增量更新；准确性验证套件。工期重估 3-4.5周(原2-3天)，分 KG-MVP/v1/v2 三阶段交付避免阻塞。

#### G2. CrewAI 版本锁定缺具体版本号 ✅ 已收口 → 03-crewai-version-strategy.md
分析 7 次提到"锁定版本"但从未给出具体版本：
- Bug #5972(or_()循环)在 #5994/#5974 修复 → 需确认包含该 fix 的最小版本
- Bug #6380(异步静默冻结)未修复 → SafeAgent wrapper 是硬性前提
- Bug #6347/#6065(human_input崩溃)在 #6372 修复
- API 重构 PR #6071/#6084/#6097 等近 30 天活跃 → 选定版本必须避开 breaking change 窗口

**需补**: 一个明确的 `crewai==1.15.x`(具体 patch 号) + 选型理由(该 patch 包含哪些必要 fix、避开了哪些 breaking PR)。

**✅ 收口方案(03)**: 给出选型4准则(必含fix/避breaking/选stable/精确patch)+ 可执行验证脚本(验证 #5972/#6347 fix 存在 + 跑冒烟)+ lockfile 产物要求。诚实声明不直接给魔法版本号(分析阶段无法核实PyPI发布),改为给可执行锁定流程。新增 Dev-Phase 0 模块0(版本选定+验证,1-2天)作为所有Python工作第0步。

#### G3. 非 OpenAI provider 下三层保障失效（vendor lock-in 未充分讨论）✅ 已收口 → 04-llm-provider-strategy.md
可靠性策略核心是"OpenAI Structured Outputs (99.9%)"。但：
- Anthropic/Google/本地 Ollama **没有**等价的 100% schema 强制 API，只能退到 pydantic 后校验(85-95%)
- 这使 SDDP-Pet **硬依赖 OpenAI**，与 MIT/开源/可离线(Phase 5) 定位冲突
- "多provider密钥管理"被列为缺失项，但没点明：**provider 切换 = 可靠性降级**，这是产品级取舍而非配置问题

**需补**: 明确 MVP 是否锁定 OpenAI-only；若支持多 provider，各 provider 的可靠性等级与降级策略表。

**✅ 收口方案(04)**: 给出 provider 能力矩阵(5档: OpenAI Tier-S / Claude Gemini Tier-A / Mistral Tier-B / Ollama Tier-C / prompt-only Tier-D)。决策: MVP 锁定 OpenAI-only(可靠性是核心价值,非OpenAI重试成本2-4x)。设计 Provider 抽象层+可靠性适配器为未来降级铺路。明确离线模式≠完整SDDP而是降级版。已接受风险: vendor lock-in / 离线可靠性降级 / 非OpenAI用户被排除。

#### G4. Phase 3 质量关卡的 CrewAI 实现完全空白 ✅ 已收口 → 05-quality-gate-flow-design.md
crewai-technical-research.md 只实现了 **Phase 1 对抗循环**。但 SDDP 的 Phase 3 质量关卡是**结构同样复杂的循环**：
- 串行链: 验收师→复核师→规范员（三角色三种严重度术语 P0/P1/P2 vs 高/中/低 vs 错误/警告/信息）
- 修复循环: 任一关卡不通过→修缮师→二次验证，最多 3 轮（与对抗 5 轮同构）
- 这套循环**复用** Phase 1 的 `@router`+`or_()` 模式，因此**继承全部 CrewAI 风险**(#5972/#6380/#6370)

"完整引擎 Dev-Phase 3: 4-6周" 把这套未验证的循环塞进去，工期风险高。

**✅ 收口方案(05)**: 给出 Phase 3 Flow 完整骨架(复用 Phase 1 模式: @router三连 + or_()修缮汇聚 + @persist + SafeAgent)；3种报告 Pydantic 模型(独立严重度枚举)；明确 Phase 3 复用 Phase 1 已验证模式,技术风险继承非新增。关键: 明确前置依赖(执行子系统 SandboxedExecutor/RuleMapper/FileWriteProxy),把 Dev-Phase 3 拆为 3a(子系统3-4周)+3b(Flow 2-3周)=5-7周。给出4个冒烟测试作为落地前验证。

#### G5. 各 Dev-Phase 缺 Definition of Done（验收标准）✅ 已收口 → 06-dev-phase-dod.md
每个阶段只有工期，没有"完成即什么"：
- "Dev-Phase 0 验证成功"的判定标准？跑通一个什么样的 demo？
- "Dev-Phase 0 验证失败→回退"的失败标准？
- 没有可度量的退出准则，阶段无法 sign-off，也无法判断"是否该回退修正引擎设计"

**需补**: 每阶段的 DoD（如 Dev-Phase 0 DoD = CLI 跑通 1 个真实 proposal→5角色线性流程→产出 delta-spec+delta-design+知识图更新，且成本≤$5、无人工干预崩溃）。

**✅ 收口方案(06)**: 每阶段给可度量/可演示/二元判定的 DoD(D0-1~D0-5 等)+ Go/No-Go 门槛(含4个No-Go条件: 知识图召回率<70%/CrewAI循环不可用/成本>$15/合规率<95%)+ 失败回退路径。含 MVP 范围收窄(砍安全合规/远程到Phase1)+ 工期重估(总21-35周,Phase3上修)。

---

### P1 — 重要，影响中后期，可在对应阶段初期补

#### G6. 快速通道(Fast Track)完全未分析
SDDP 设计有"简单变更→需求官直接生成微任务→实施师，跳过 Phase 1-3"的快速通道。成本模型列了"$1 快速通道"但：
- 需求官判定"简单 vs 复杂"的分类逻辑未定义（基于什么信号？文件数？模块数？是否有接口变更？）
- 快速通道的 Flow 结构未设计
- 桌宠对快速通道的视觉表现未考虑（应区别于全流程的对抗动画）

这是 SDDP 的两条主干路径之一，不是边缘功能。

#### G7. PCM 的实际获取/解析机制未定义
设计说"需求官读取 PCM 并嵌入 proposal"。但：
- PCM 六大配置域(验证方案/规范配置/版本策略/架构决策/编码规范/CI流程)需从真实配置文件提取(.eslintrc/jest.config/.github/workflows/ADR目录)
- 谁创建 PCM？自动从项目探测？用户提供？混合？
- 各配置文件的解析器是另一个子系统（类似知识图，但是项目配置维度的）
- "PCM parser" 被一笔带过，实际是跨语言/跨工具的配置提取难题

#### G8. 角色视觉/动画状态机规格缺失
分析提到"4角色桌宠""8角色桌宠"但：
- 13个角色→桌宠如何映射？哪些角色有独立形象？哪些合并？
- 每个角色的动画状态空间未定义（idle/working/thinking/waiting-feedback/error/converged...）
- 对抗/质量关卡循环的"空间隐喻"（架构师vs挑评师"辩论"动画）只在调研里提了概念，无状态机设计
- 这是桌宠产品的核心体验，却完全在分析盲区

#### G9. 远程模式部署链路低估
"远程执行连接器 3-5天" 只覆盖了 SSH 隧道+端口转发。但完整远程部署还包括：
- Linux 服务器上 CrewAI 引擎如何部署(Docker/systemd/手动)？版本如何同步？
- LLM API key 如何安全分发到远程服务器（比本地存储风险更高）？
- 远程引擎如何更新？回滚？
- 这是一套小型部署系统，3-5 天只够打通隧道，不含部署/运维

#### G10. Windows 上 CrewAI 依赖安装摩擦
"本地Python环境管理 1-2天" 假设用户装好 Python 3.10+ 即可。但：
- CrewAI 依赖树(chromadb/langchain/protobuf/grpcio/onnxruntime...)在 Windows 上安装冲突频发
- 编译型依赖(如某些 protobuf 版本)可能缺 MSVC build tools
- 这可能是 **#1 用户首次使用摩擦点**，比桌宠透明窗口更影响采用
- 建议考虑嵌入式 Python + 预编译 wheel 包，但这本身是周级工作

---

### P2 — 次要，可延后但在路线图中标注

- **G11** 多 flow 并发的 @persist 数据隔离 — 分析列为 Dev-Phase 2 缺失，但若 Day1 不设计 flow_id 命名空间，后期是重构而非新增
- **G12** 知识图"扫描置信度"指标 — 真实代码库无法 100% 静态分析(动态导入/反射/生成代码)，"权威代码知识"的权威性有边界，应向用户标注
- **G13** 国际化/提示词语言 — 设计文档全中文，agent prompt 语言影响输出质量与目标用户群，是基础设计选择而非 Phase 5 细节
- **G14** 竞品功能对标矩阵 — clawd-on-desk(5.4k★)/openpets(929★) 的功能对标缺失，定位"护城河=SDDP引擎"偏单薄
- **G15** 测试策略中的"无LLM调用的agent单测"— 需 mock LLM/fixture 策略，是 Phase 0 前置而非可后补
- **G16** 成本模型无验证方法 — $1-12.5/flow 全是估算，Phase 0 应内置 token 计量来校准

---

## 三、现有输出完备性检查

| 已有产物 | 状态 | 缺口 |
|---------|------|------|
| research-summary.md (桌宠技术调研) | ✅ 完备 | — |
| technical-research-findings.md (6项验证) | ✅ 完备 | — |
| crewai-technical-research.md (CrewAI深验+代码) | ⚠️ 仅 Phase 1 | Phase 2/3 Flow 实现空白 |
| 00-sddp-pet-final.md (决策汇总) | ✅ 决策完备 | 但基于不完整的 CrewAI 实现 |

| 缺失的工程产物 | 建议产出阶段 |
|---------------|------------|
| 系统架构图(含数据流/进程边界) | Dev-Phase 0 启动前 |
| 数据模型/文档 schema(全 16 种文档的 Pydantic) | Dev-Phase 0(目前只有 Phase 1 的) |
| WebSocket 协议正式 spec(已有草案,需 OpenAPI/AsyncAPI 化) | Dev-Phase 0 |
| 代码知识图 schema + 查询接口 | Dev-Phase 0 启动前(P0) |
| 仓库骨架/目录结构提案 | Dev-Phase 0 启动前 |
| 测试策略文档 | Dev-Phase 0 启动前(P0 前置) |
| 各 Dev-Phase 的 DoD | 立即(P0) |

---

## 四、可行性核心风险（重排优先级）

分析的风险矩阵列了 16 项，但**顶层项目级风险权重不足**。按"可能使整个项目失败"排序：

1. **CrewAI Flows API 动荡 vs 23-33周工期**（最高）
   - 调研明确：近 30 天有 breaking-change PR(#6097 等)，API"非生产稳定"
   - 一个 6-8 个月的项目建在活跃重构的框架上，到 Phase 3 时起始版本可能已落后 2 个大版本
   - 适配层只降级不消除风险。**建议**: Phase 0 必须验证"适配层能否在 CrewAI 小版本升级下不变"，作为 Go/No-Go 门槛

2. **vendor lock-in OpenAI**（高）— 见 G3，动摇开源/离线定位

3. **代码知识图可行性**（高）— 见 G1，整个"禁止假设"原则的地基

4. **MVP 范围偏大**（中高）— Dev-Phase 0 含 13 模块(含安全合规+远程+隐私)，应砍到只验证核心引擎

5. **"对抗收敛依赖 LLM 裁决"悖论**（中）— 分析标为"差距2已部分解决"，实际只是机械化部分字段，核心收敛判断仍是 LLM 自引用。应明确标为**已接受风险**而非"已解决"

---

## 五、收口建议（进入实现前的行动清单）

### ✅ 已完成（2026-07-20）— P0 全部补齐
1. ✅ **知识图子系统设计**(G1→02): SCIP+tree-sitter, schema+查询+置信度+增量+验证, 工期重估3-4.5周
2. ✅ **CrewAI 版本锁定**(G2→03): 4准则+验证脚本+lockfile流程, 新增Dev-Phase 0模块0
3. ✅ **provider 策略表**(G3→04): 5档能力矩阵, MVP锁OpenAI-only, 抽象层铺路
4. ✅ **Phase 3 质量关卡 Flow 设计**(G4→05): 完整骨架+Pydantic, 拆3a+3b, 4个冒烟测试
5. ✅ **各 Dev-Phase 的 DoD**(G5→06): 可度量DoD+Go/No-Go门槛+MVP收窄+工期重估

### ✅ 已落实的范围调整
6. ✅ **收窄 Dev-Phase 0 MVP**: 砍掉安全合规(API密钥加密/隐私界面/代码预过滤)和远程模式到 Dev-Phase 1。Dev-Phase 0 只做"本地引擎+5角色线性+CLI+成本计量"
7. ✅ **远程模式单列**: 工期重估为 2-3 周(含部署系统), 不混在 Phase 0

### ✅ 已明确标记为"已接受风险"
8. ✅ 对抗收敛的 LLM 自引用悖论（G/差距2）
9. ✅ 知识图扫描置信度边界（G12）— 已通过置信度贯穿设计转化为可管理的不确定性
10. ✅ vendor lock-in OpenAI（G3）— MVP 明确取舍
11. ✅ 离线模式可靠性降级（G3）— 离线≠完整SDDP

### 🔲 仍开放（P1/P2，建议对应 Dev-Phase 初期处理）
- G6 快速通道(Fast Track)分析 — Dev-Phase 1 初期
- G7 PCM 获取/解析机制 — Dev-Phase 1 初期
- G8 角色视觉/动画状态机 — Dev-Phase 2 初期(桌宠多角色时)
- G9 远程模式部署链路 — Dev-Phase 1(远程模式启动时)
- G10 Windows CrewAI 依赖安装摩擦 — Dev-Phase 1(打包时)
- G11-G16 见第二节 P2 清单 — 各对应阶段

---

## 六、结论（更新后）

**方案合理且可行，且现已"完备到可进入实现"。** 5 项 P0 缺口已全部补齐(文档 02-06)，MVP 范围已收窄以加速核心验证，已接受风险已显式登记。

**下一步**: 可创建 OpenSpec change 进入 Dev-Phase 0 实现。建议 change 范围 = 06-dev-phase-dod 的 Dev-Phase 0 DoD(D0-1~D0-5)。P1 项(G6-G10)在进入对应 Dev-Phase 前各自再做一轮小分析即可，无需阻塞当前启动。

**不建议**: 不要等 P1 全部补齐再开工——P1 项依赖实现中才暴露的具体问题，提前分析收益有限。
