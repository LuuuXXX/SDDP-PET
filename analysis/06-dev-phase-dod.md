# G5: 各 Dev-Phase Definition of Done

> 日期: 2026-07-20
> 状态: P0 缺口补齐
> 关联: 01-final-review.md G5; 00-sddp-pet-final.md 第十节(MVP范围)、第十四节(下一步行动)

---

## 一、问题陈述

00-final 每个 Dev-Phase 只有工期，无退出标准。"Dev-Phase 0 验证成功/失败"无可度量判据，阶段无法 sign-off，也无法判断何时该回退。本文件给出每阶段**可度量、可演示**的 DoD 与 Go/No-Go 门槛。

### DoD 设计原则

1. **可演示**: 必须能用一个具体场景跑通(不是"代码写完了")
2. **可度量**: 关键指标有数值阈值(成本/延迟/成功率)
3. **二元判定**: 通过/不通过，无模糊地带
4. **含失败路径**: 明确"不通过时怎么办"

---

## 二、Dev-Phase 0: 引擎核心验证（收窄后的 MVP）

> 范围已按 01-review 建议收窄: 砍掉安全合规/远程/隐私，只验证核心引擎

### DoD（全部满足才算完成）

**D0-1 版本与基础设施**
- [ ] CrewAI 版本选定并锁定到精确 patch(03-crewai-version-strategy 第四节验证脚本通过)
- [ ] SafeAgent wrapper 实现并通过 #6380 复现测试(异步失败不卡死)
- [ ] 适配层抽象就位(Flow 定义与 CrewAI 解耦)

**D0-2 知识图 KG-MVP**
- [ ] 单语言(Python)预扫描器跑通: SCIP 索引 → SQLite 图存储
- [ ] 4 类查询(find_callers/find_file_impact/find_dependencies/get_module_api)返回带置信度结果
- [ ] 准确性验证套件就位(召回率/精确率可跑出数值)

**D0-3 五角色线性流程**
- [ ] 需求官/调度官/架构师/实施师/代码资产管理员 5 个 Agent 可 kickoff
- [ ] output_pydantic 强制 proposal + delta-spec + delta-design 三种输出
- [ ] CLI 跑通端到端: 输入原始需求 → 输出 delta-spec + delta-design + 知识图更新

**D0-4 用户确认点**
- [ ] @human_feedback 在 CLI 模式下可阻塞/恢复(3 个确认点: 需求确认/方案确认/... )
- [ ] 中断后可从 @persist 恢复

**D0-5 度量达标**
- [ ] 单流程成本 ≤ $5(实测,非估算;内置 token 计量)
- [ ] 端到端延迟 ≤ 10 分钟(无人工等待)
- [ ] Structured Outputs 一次性合规率 ≥ 99%(实测)
- [ ] 无人工干预下不崩溃(连续跑 3 个不同 proposal)

### DoD 演示场景
```
输入: "给这个 Python 项目加一个配置热重载功能"
输出: proposal → (用户CLI确认) → 架构研究报告(咨询知识图) → 
      delta-spec + delta-design → (用户CLI确认) → 知识图更新
成本: ≤$5, 耗时: ≤10min, 全程无崩溃
```

### Go/No-Go 门槛（Dev-Phase 0 → Dev-Phase 1）
- **Go**: 全部 DoD 满足 → 进入 Dev-Phase 1(桌宠前端)
- **No-Go 条件A**: 知识图召回率 < 70% → 架构师基于不可靠数据 → 回到 KG 设计修正
- **No-Go 条件B**: CrewAI 循环模式在选定版本下不可用(#5972 回归) → 锁定版本错误 → 回 03-strategy 重选
- **No-Go 条件C**: 单流程成本 > $15 → 成本模型严重失真 → 重审成本驱动因子
- **No-Go 条件D**: Structured Outputs 合规率 < 95% → provider 策略失效 → 回 04-strategy

### 预估工期(收窄后)
- 原 13 模块 → 砍掉模块 10(远程)/11(API密钥加密)/12(代码预过滤)/13(隐私界面)
- 剩余: 0(版本)+1(Python环境)+2(KG-MVP,扩到12-15天)+3(SafeAgent)+4(5角色)+5(JSON Schema)+6(Flow)+7(JSON-MD渲染)+8(适配层)+9(CLI验证)
- **重估: 3-4 周**(原 3.5-4.5 周，但 KG 扩工期，砍安全合规省的工时填补 KG)

---

## 三、Dev-Phase 1: 桌宠前端 MVP + 安全合规

### DoD

**D1-1 双窗口架构**
- [ ] 窗口1(透明): PixiJS 桌宠 + 气泡渲染,0 React DOM
- [ ] 窗口2(不透明): React 状态面板 + 诊断面板 + 确认按钮 + 成本显示
- [ ] 穿透点击(Windows)工作: 进入宠物区域可交互,离开区域穿透+转发

**D1-2 WebSocket 联调**
- [ ] FastAPI WebSocket server 对接 Electron client
- [ ] 5 种 Push 消息(agent_state_change/document_produced/cost_update/feedback_required/error)前端正确渲染
- [ ] 4 种 RPC 请求(start_flow/user_feedback/resume_flow/abort_flow)前端可发
- [ ] 心跳机制工作(30s ping, 3 次未响应触发连接丢失)

**D1-3 @human_feedback 桌宠化**
- [ ] CLI 确认点切换为桌宠气泡确认(WebSocketProvider 实现)
- [ ] Dev-Phase 0 的 CLI demo 在桌宠 UI 下同样跑通

**D1-4 安全合规(从 Phase 0 推迟过来)**
- [ ] API 密钥加密存储(Windows Credential Manager)
- [ ] 隐私同意界面(首次启动弹窗,含远程数据传输提示)
- [ ] 代码预过滤(本地脱敏)
- [ ] AI 身份标注(桌宠气泡旁"AI 驱动")
- [ ] 遥测禁用(OTEL_SDK_DISABLED=true)

**D1-5 监控/可观测(01-review 缺失项,提前到 Phase 1)**
- [ ] 流程执行时间/agent 延迟/token 消耗率/错误率 4 指标可采集
- [ ] 诊断面板展示上述指标

### Go/No-Go
- **Go**: Dev-Phase 0 demo 在桌宠 UI 下端到端跑通 → 进入 Dev-Phase 2
- **No-Go**: WebSocket 联调不稳定(连接丢失频繁) → 重审心跳/重连机制

### 预估工期: 3-4 周(原估值不变,加了从 Phase 0 推迟的安全合规)

---

## 四、Dev-Phase 2: 对抗验证 + 多角色桌宠

### DoD

**D2-1 Phase 1 对抗 Flow**
- [ ] crewai-technical-research 第八节的 Phase 1 Flow 完整实现(非骨架)
- [ ] 简化对抗(1 维度 3 轮)冒烟通过
- [ ] 完整对抗(3 维度 5 轮)跑通

**D2-2 收敛检测**
- [ ] 机械化收敛(严重度规则映射)工作
- [ ] max_rounds 强制收敛触发
- [ ] escalate 到用户裁决工作

**D2-3 多角色桌宠**
- [ ] 4 角色(架构师/挑评师/实证师/调度官)各有独立形象 + 动画状态机
- [ ] 对抗过程可视化(角色"辩论"动画,见 01-review G8)
- [ ] 实时状态推送渲染

**D2-4 并发流程(01-review G11)**
- [ ] 2 个 flow 并发执行,@persist 数据隔离(flow_id 命名空间)
- [ ] 调度官多 proposal 管理基础

### Go/No-Go
- **Go**: 完整对抗(5 轮)在桌宠下端到端跑通,成本 ≤ $15 → 进入 Dev-Phase 3
- **No-Go 条件A**: CrewAI or_() 循环在生产场景下不稳 → 回适配层/考虑 LangGraph
- **No-Go 条件B**: 对抗收敛实际无法判定(LLM 自引用悖论不可接受) → 重审 00-final 差距2,可能需引入外部裁决信号

### 预估工期: 5-7 周(原估值不变)

---

## 五、Dev-Phase 3: 质量关卡 + 执行子系统

> 按 05-quality-gate-flow-design 拆分为 3a + 3b

### Dev-Phase 3a: 执行子系统

**D3a-1 SandboxedExecutor**
- [ ] 安全沙箱中运行验收师指定测试
- [ ] 超时/资源限制工作
- [ ] 测试结果结构化回传

**D3a-2 FileWriteProxy**
- [ ] 实施师代码建议 → 写入文件 + diff 确认
- [ ] 用户可拒绝写入

**D3a-3 RuleMapper**
- [ ] 规范员静态规则 → lint 结果预测
- [ ] CI 实际执行验证对齐

### Dev-Phase 3b: Phase 3 Flow

**D3b-1 质量关卡 Flow**
- [ ] 05-quality-gate-design 第五节 Flow 实现
- [ ] 4 个冒烟测试(第九节)全通过

**D3b-2 八角色桌宠**
- [ ] 补齐验收师/复核师/规范员/修缮师 4 角色
- [ ] 审计日志记录所有数据发送行为

### Go/No-Go
- **Go**: 完整质量关卡(3 关卡 + 修复循环)跑通 → 进入 Dev-Phase 4
- **No-Go**: 执行子系统不可靠(SandboxedExecutor 安全/性能问题) → 重审沙箱方案

### 预估工期: 5-7 周(3a 3-4周 + 3b 2-3周,原 4-6 周低估)

---

## 六、Dev-Phase 4: 高级特性

### DoD(可选性强,按优先级裁剪)
- [ ] Live2D 可选模块(独立,不捆绑,避开 GPL 冲突)
- [ ] VSCode 伴侣扩展(文件上下文/终端/diff)
- [ ] Tauri 迁移评估(不一定要做,出评估报告即可)
- [ ] 对抗回放(历史流程可视化重放)

### Go/No-Go
- 本阶段无硬门槛,按用户反馈优先级裁剪

### 预估工期: 5-7 周(按选定特性裁剪)

---

## 七、Dev-Phase 5(可选): 离线 + 国际化

### DoD 前置验证(必须先做)
- [ ] **Tier-C provider 下对抗循环可行性验证**(04-provider-strategy 第六节)
- [ ] 结论可能是: 离线只支持快速通道,不支持全流程

### 若验证通过
- [ ] Ollama 集成(降级版流程)
- [ ] Linux 桌面支持
- [ ] 国际化(提示词多语言,见 01-review G13)

### 预估工期: 4-6 周(若可行)

---

## 八、总工期重估

| Dev-Phase | 原估 | 重估 | 变化原因 |
|-----------|------|------|---------|
| 0 | 3.5-4.5周 | 3-4周 | 砍安全合规省工时填补 KG 扩工期 |
| 1 | 3-4周 | 3-4周 | 含从Phase0推迟的安全合规 |
| 2 | 5-7周 | 5-7周 | 不变 |
| 3 | 4-6周 | 5-7周 | 拆 3a+3b,执行子系统低估 |
| 4 | 5-7周 | 5-7周 | 不变 |
| 5(可选) | 4-6周 | 4-6周 | 前置验证可能否决 |
| **合计** | **23-33周** | **21-35周** | 区间略扩,因 Phase 3 上修 |

关键路径: **0→1→2→3a→3b** (核心引擎+质量关卡),Dev-Phase 4/5 可并行或延后。

---

## 九、跨阶段通用 DoD（每阶段都必须）

不论哪个阶段,完成时必须同时满足:
- [ ] 文档更新(本阶段涉及的分析文档/架构文档同步)
- [ ] 测试通过(单元+集成+E2E,按 01-review G15 测试策略)
- [ ] 成本实测(本阶段涉及流程的 token 成本已计量,非估算)
- [ ] 已知风险登记(新发现风险写入 00-final 风险矩阵)
- [ ] 回归无退化(此前阶段 demo 仍跑通)
