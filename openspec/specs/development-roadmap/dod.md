# SDDP-PET 各 Dev-Phase Definition of Done (DoD)

> 数据属性：本文件是 `development-roadmap/spec.md` 中"每个 Dev-Phase MUST 有可度量、二元判定的 DoD"需求的承载表。
> 数据来源：`analysis/06-dev-phase-dod.md` 第二至第七节 + 第九节（跨阶段通用 DoD）。
>
> **格式约束**：每项 DoD 形如"可执行命令/可观察行为 + 通过阈值"；不允许"代码写完"类描述。`opsx-apply` 验收阶段直接读取本文件执行。

---

## 跨阶段通用 DoD（依据 `analysis/06` 第九节，所有 Dev-Phase 都必须满足）

| ID | DoD 项 | 通过阈值 | 验证方式 |
|----|--------|----------|----------|
| X-1 | 文档更新 | 本阶段涉及的分析/架构/规格文档同步更新，无悬挂引用 | `grep -r "TBD\|TODO\|待补" openspec/` 在本阶段范围内无新增命中（已接受风险槽位除外） |
| X-2 | 测试通过 | 单元 + 集成 + E2E 全部通过 | `pytest tests/`（Dev-Phase 0 起）+ Electron E2E（Dev-Phase 1 起）退出码 0 |
| X-3 | 成本实测 | 本阶段涉及流程的 token 成本已计量（非估算） | 内置 token 计量器输出 `cost_report.json`，含 `measured_cost_usd` 字段 |
| X-4 | 已知风险登记 | 新发现风险写入 `analysis/00-sddp-pet-final.md` 风险矩阵 | diff 校验：本阶段 archive 前后风险矩阵行数单调增长或维持 |
| X-5 | 回归无退化 | 此前所有阶段的 Golden Demo 仍跑通 | 重放 `openspec/regression/golden-demos/*.md` 全部为 PASS |

---

## Dev-Phase 0: 引擎核心验证（收窄后 MVP）

> 范围：本地引擎 + 5 角色线性 + CLI + 成本计量。安全合规/远程/隐私推迟到 Dev-Phase 1。

| ID | DoD 项 | 通过阈值 | 验证方式 |
|----|--------|----------|----------|
| D0-1 | CrewAI 版本选定并锁定到精确 patch | 4 准则选型记录存在（必含 fix / 避 breaking / 选 stable / 精确 patch）；`requirements.txt` 或 `pyproject.toml` 含 `crewai==<exact-patch>` | `pip show crewai` 输出的 Version 与 lockfile 完全一致 |
| D0-2 | SafeAgent wrapper 实现 | #6380 复现测试存在并 PASS（异步失败场景下 wrapper 不卡死，超时后抛出 `SafeAgentError`） | `pytest tests/safe-agent/test_timeout_retry.py` 退出码 0；测试含"30s 超时触发"断言 |
| D0-3 | 适配层抽象就位 | `FlowDefinition` 抽象存在；至少一个非 CrewAI 的 mock adapter 通过冒烟测试 | `pytest tests/adaptation-layer/test_mock_adapter.py` 退出码 0 |
| D0-4 | KG-MVP 单语言（Python）预扫描器跑通 | SCIP 索引 → SQLite 图存储的 pipeline 在一个真实 Python 项目（≥10 文件）上产出非空图 | `python -m sddp.kg.scan <path>` 退出码 0；SQLite 中 Symbol 节点数 > 0 |
| D0-5 | KG-MVP 4 类查询带置信度返回 | `find_callers` / `find_file_impact` / `find_dependencies` / `get_module_api` 全部返回 `{result, confidence, coverage_note}` 三字段结构 | `pytest tests/kg/test_queries.py` 含 4 个查询的契约测试，全部 PASS |
| D0-6 | KG-MVP 准确性验证套件就位 | 召回率（recall）+ 精确率（precision）可跑出数值；准确性 ≥ 70% 召回率（D0-Go/No-Go 阈值） | `python -m sddp.kg.evaluate --gold tests/kg/golden.json` 输出 JSON 含 `recall >= 0.70` |
| D0-7 | 5 角色 Agent 可 kickoff | 需求官/调度官/架构师/实施师/代码资产管理员 5 个 Agent 在不调用真实下游的情况下可完成 kickoff（LLM mock 即可） | `pytest tests/engine/test_5_roles_kickoff.py`（含 LLM mock fixture）退出码 0 |
| D0-8 | output_pydantic 强制三种输出 | proposal + delta-spec + delta-design 三种输出在不符合 schema 时被拒绝（pydantic ValidationError） | `pytest tests/engine/test_output_schema_enforcement.py` 退出码 0 |
| D0-9 | CLI 端到端跑通 | 输入"给这个 Python 项目加一个配置热重载功能" → 输出 proposal →（用户 CLI 确认）→ delta-spec + delta-design →（用户 CLI 确认）→ 知识图更新 | 手工运行 `sddp run "..."`，产出 3 个 markdown 文档 + 知识图 scan_version 递增 |
| D0-10 | @human_feedback CLI 阻塞/恢复 | 3 个用户确认点（需求确认/方案确认/...）在 CLI 下能阻塞等待 stdin 并恢复；中断后可从 @persist 恢复 | 手工运行：流程启动 → Ctrl+C 中断 → 重启 → 流程从上次 @persist 状态恢复 |
| **D0-11** | **单流程成本 ≤ $5** | **实测，非估算**；内置 token 计量器输出 `measured_cost_usd <= 5.0` | `cost_report.json` 字段 `measured_cost_usd` 数值 ≤ 5.0 |
| **D0-12** | **端到端延迟 ≤ 10 分钟** | **无人工等待时间**（用户确认点等待不计入） | `cost_report.json` 字段 `wall_clock_minutes_excluding_human_wait` ≤ 10.0 |
| **D0-13** | **Structured Outputs 合规率 ≥ 99%** | **实测**：所有 LLM 调用中一次性 schema 合规的比例 ≥ 99% | `cost_report.json` 字段 `structured_output_first_try_rate >= 0.99` |
| **D0-14** | **无人工干预不崩溃** | **连续跑 3 个不同 proposal**，全程无需人工介入 | 手工运行 3 个固定 proposal（`tests/fixtures/proposals/p1.txt`/p2/p3）；3 次全部成功产出文档 |

**Dev-Phase 0 DoD 演示场景**（D0-Go 判定的最终演示）：
```
输入: "给这个 Python 项目加一个配置热重载功能"
输出: proposal → (用户CLI确认) → 架构研究报告(咨询知识图) →
      delta-spec + delta-design → (用户CLI确认) → 知识图更新
度量: 成本 ≤ $5, 耗时 ≤ 10min, 全程无崩溃, 合规率 ≥ 99%
```

---

## Dev-Phase 1: 桌宠前端 MVP + 安全合规

| ID | DoD 项 | 通过阈值 | 验证方式 |
|----|--------|----------|----------|
| D1-1 | 窗口1（透明，PixiJS 桌宠 + 气泡）实现 | 0 React DOM 在窗口1；PixiJS 渲染桌宠精灵 + 气泡文本 | DevTools 检查窗口1 DOM 节点数 = 1（仅 canvas） |
| D1-2 | 窗口2（不透明，React 面板）实现 | 状态面板 + 诊断面板 + 确认按钮 + 成本显示 + SSH 设置页全部渲染 | E2E 测试 `tests/e2e/window2-panels.test.ts` 通过 |
| D1-3 | 穿透点击工作 | 鼠标进入宠物区域：`setIgnoreMouseEvents(false)`，可交互；离开区域：`setIgnoreMouseEvents(true, {forward:true})`，穿透+转发 | E2E 测试：点击宠物 vs 点击宠物旁空白区域行为不同 |
| D1-4 | FastAPI WebSocket server 对接 Electron client | 双向消息可发收；连接失败有错误提示 | `tests/e2e/websocket-roundtrip.test.ts` 通过 |
| D1-5 | 5 种 Push 消息前端正确渲染 | agent_state_change / document_produced / cost_update / feedback_required / error 全部触发 UI 更新 | 5 个 E2E 测试场景，全部 PASS |
| D1-6 | 4 种 RPC 请求前端可发 | start_flow / user_feedback / resume_flow / abort_flow 在 UI 触发后引擎收到正确消息 | 4 个 E2E 测试场景，全部 PASS |
| D1-7 | 心跳机制工作 | 30s ping；前端 10s 内回复 pong；3 次连续未回复触发连接丢失事件 | 模拟测试：手工 stop pong 响应 30s+ → 触发"连接中断"UI |
| D1-8 | CLI 确认点切换为桌宠气泡确认 | WebSocketProvider 实现；Dev-Phase 0 的 CLI demo 在桌宠 UI 下同样跑通 | 端到端：同一 proposal 在 CLI 与桌宠 UI 下产出相同文档集 |
| D1-9 | API 密钥加密存储 | 使用 Windows Credential Manager；明文密钥不出现在磁盘文件 | `grep -r "sk-" ~/.sddp-pet/` 无命中；密钥读取走 Credential Manager API |
| D1-10 | 隐私同意界面 | 首次启动弹窗（含远程数据传输提示）；用户拒绝则不启动流程 | E2E：首次启动 → 弹窗出现 → 拒绝 → 主流程不可启动 |
| D1-11 | 代码预过滤（本地脱敏） | 输入代码 → 脱敏摘要（密钥/密文/PII 替换为占位符）→ 仅发送脱敏摘要到远程 | 单元测试 `tests/security/test_prefilter.py`：固定输入产生固定脱敏输出 |
| D1-12 | AI 身份标注 | 桌宠气泡旁标注"AI 驱动" | UI 检查：标注可见 |
| D1-13 | 遥测禁用 | `OTEL_SDK_DISABLED=true` 在配置中硬编码 | 进程启动后无 OTEL 上报网络请求 |
| D1-14 | 监控可观测 4 指标可采集 | 流程执行时间 / agent 延迟 / token 消耗率 / 错误率 4 指标写入 `metrics.json` | 跑一个流程后 `metrics.json` 含 4 个字段的非空数值 |
| D1-15 | 诊断面板展示 4 指标 | 诊断面板 UI 显示上述 4 指标实时值 | E2E 检查面板 DOM 含 4 个指标值 |
| D1-16 | 远程模式 SSH 隧道工作 | `ssh -L 8765:localhost:8765` 转发；前端连 localhost:8765 透明；连接失败有重试按钮 | E2E：手工配置 SSH → 启动远程引擎 → 前端可发 RPC |

---

## Dev-Phase 2: 对抗验证 + 多角色桌宠

| ID | DoD 项 | 通过阈值 | 验证方式 |
|----|--------|----------|----------|
| D2-1 | Phase 1 对抗 Flow 完整实现 | `analysis/crewai-technical-research.md` 第八节 Phase 1 Flow 骨架在仓库中存在（非占位） | 代码审查：Flow 类 + 4 个 listener（architect/critic/empiricist/orchestrator）齐全 |
| D2-2 | 简化对抗（1 维度 3 轮）冒烟通过 | 1 个挑评师维度 × 最多 3 轮对抗 → 产出对抗记录文档 | `pytest tests/confrontation/test_smoke_1d3r.py` 退出码 0 |
| D2-3 | 完整对抗（3 维度 5 轮）跑通 | 3 个挑评师维度（安全/性能/可维护性）× 最多 5 轮 → 产出对抗记录 + 收敛判定 | `pytest tests/confrontation/test_full_3d5r.py` 退出码 0 |
| D2-4 | 机械化收敛（严重度规则映射）工作 | 高严重度不得驳回（backstory 硬编码 + guardrail 验证）；中/低严重度可被调度官驳回 | 单元测试：模拟高严重度质疑 → 调度官驳回尝试 → guardrail 拒绝 |
| D2-5 | max_rounds 强制收敛触发 | 达到 max_rounds=5 后强制标记"收敛"并产出对抗记录 | 测试：构造永不收敛场景 → 第 5 轮后强制结束 |
| D2-6 | escalate 到用户裁决工作 | 高严重度未解决且达 max_rounds → 触发 @human_feedback escalate | E2E：构造场景 → 用户 UI 看到 escalate 提示 |
| D2-7 | 4 角色桌宠独立形象 + 动画状态机 | 架构师/挑评师/实证师/调度官各有独立 PixiJS 精灵 + 状态机（idle/working/thinking/waiting-feedback/error/converged） | E2E：每个角色在每个状态下视觉可区分 |
| D2-8 | 对抗过程可视化 | 角色"辩论"动画（架构师发言 → 挑评师反驳 → 实证师举证 → 调度官裁决） | E2E：对抗轮次中角色动画顺序正确 |
| D2-9 | 2 个 flow 并发执行 | @persist 数据隔离（flow_id 命名空间）；2 flow 互不污染 | 并发测试：同时 kickoff 2 flow → 各自 @persist 状态独立 |
| D2-10 | 完整对抗（5 轮）成本 ≤ $15 | 实测；内置 token 计量器输出 | `cost_report.json` 字段 `measured_cost_usd <= 15.0` |

---

## Dev-Phase 3a: 执行子系统

| ID | DoD 项 | 通过阈值 | 验证方式 |
|----|--------|----------|----------|
| D3a-1 | SandboxedExecutor 实现 | 安全沙箱中运行验收师指定测试；超时/资源限制工作；测试结果结构化回传 | 单元测试：`pytest tests/execution/test_sandbox_executor.py` 含超时/资源限制/结果结构 3 类断言 |
| D3a-2 | FileWriteProxy 实现 | 实施师代码建议 → 写入文件 + diff 确认；用户可拒绝写入 | E2E：实施师产出建议 → 用户拒绝 → 文件未被修改 |
| D3a-3 | RuleMapper 实现 | 规范员静态规则 → lint 结果预测；CI 实际执行验证对齐（预测准确率 ≥ 80%） | 测试：固定规则集 × 固定代码 → 预测结果 vs 实际 lint 结果一致率 ≥ 80% |
| D3a-4 | 沙箱安全性 | 沙箱不可访问网络/用户家目录/系统目录 | 安全测试：沙箱内尝试访问 `~/.ssh/` → 拒绝；尝试出站网络 → 拒绝 |

---

## Dev-Phase 3b: Phase 3 质量关卡 Flow

| ID | DoD 项 | 通过阈值 | 验证方式 |
|----|--------|----------|----------|
| D3b-1 | Phase 3 Flow 实现 | `analysis/05-quality-gate-flow-design.md` 第五节 Flow 骨架在仓库中存在 | 代码审查：3 关卡 listener + 修缮汇聚 + @persist 齐全 |
| D3b-2 | 4 个冒烟测试全通过 | `analysis/05` 第九节定义的 4 个冒烟测试（验收P0通过/验收P0失败-修缮-二次验证/复核P1失败-修缮/规范P2-警告不阻断） | `pytest tests/quality-gate/test_smoke_*.py` 4 个测试全部 PASS |
| D3b-3 | 三种严重度术语独立运行 | 验收（P0/P1/P2）/复核（P1-高/中/低）/规范（错误/警告/信息）三套枚举不混用 | 单元测试：质量判定报告中三套术语字段独立 |
| D3b-4 | 修复循环最多 3 轮 | 修复循环达 3 轮未通过 → 上报调度官（不无限循环） | 测试：构造永不修复场景 → 第 3 轮后上报 |
| D3b-5 | 4 角色桌宠补齐 | 验收师/复核师/规范员/修缮师 4 角色桌宠形象 + 状态机 | E2E：4 角色在 Phase 3 流程中可见 |
| D3b-6 | 审计日志 | 所有数据发送行为（远程模式）记录到审计日志 | 测试：远程流程跑完 → 审计日志含每次发送的目标/大小/时间戳 |

---

## Dev-Phase 4: 高级特性（可选，按优先级裁剪）

| ID | DoD 项 | 通过阈值 | 验证方式 |
|----|--------|----------|----------|
| D4-1 | Live2D 可选模块（若选） | 独立模块，不捆绑（避开 GPL 冲突）；用户可选启用 | 配置检查：默认禁用；启用时不影响主流程 |
| D4-2 | VSCode 伴侣扩展（若选） | 文件上下文 / 终端 / diff 三类集成；与桌宠并存 | E2E：VSCode 中触发命令 → 桌宠响应 |
| D4-3 | Tauri 迁移评估（若选） | 出评估报告（不一定要做迁移）；含体积/内存/兼容性对比 | 评估文档存在；含可量化的对比数据 |
| D4-4 | 对抗回放（若选） | 历史流程可视化重放；时间轴可拖动 | E2E：选历史 flow → 重放动画与原 flow 一致 |

Dev-Phase 4 无硬 Go/No-Go 门槛；按用户反馈优先级裁剪。

---

## Dev-Phase 5: 离线 + 国际化（可选，前置验证必做）

| ID | DoD 项 | 通过阈值 | 验证方式 |
|----|--------|----------|----------|
| D5-pre | Tier-C provider 对抗循环可行性验证 | 在 Ollama 本地模型下跑 Dev-Phase 2 的对抗 Flow；产出可行性结论（可能：仅支持快速通道，不支持全流程） | 验证报告存在；含实测对抗合规率/收敛判定可靠性数据 |
| D5-1 | Ollama 集成（若 D5-pre 通过） | 降级版流程（仅快速通道或简化对抗）可跑通；与 OpenAI 流程产出对比 | E2E：本地 Ollama 下跑 proposal → 产出文档 |
| D5-2 | Linux 桌面支持（若 D5-pre 通过） | Electron 在 Linux 下双窗口/穿透点击工作 | E2E：Linux 环境手工运行 |
| D5-3 | 国际化（若选） | 提示词多语言（至少英文+中文）；输出文档语言跟随用户配置 | 测试：切换语言 → 输出文档语言变化 |
