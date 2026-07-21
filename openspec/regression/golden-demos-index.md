# Golden Demos 索引（Dev-Phase 0–5）

> 数据属性：本文件是 `regression-strategy/spec.md` 中"每个完成的 Dev-Phase MUST 冻结一份 Golden Demo"需求的承载索引。
> 数据来源：`analysis/06-dev-phase-dod.md` 各阶段"DoD 演示场景"。
>
> **状态约定**：
> - `pending`：该 Dev-Phase 未完成，槽位占位（数据需待该阶段完成时填实）
> - `frozen`：该 Dev-Phase 已通过 Go 判定，Golden Demo 已冻结（具体文件见 `golden-demos/dev-phase-<n>.md`）

---

## 一、Golden Demo 槽位总表

| Dev-Phase | 状态 | 输入场景 | 期望输出（关键字段） | 度量阈值范围 | 运行命令 | git tag |
|-----------|------|----------|---------------------|--------------|----------|---------|
| `0` | `pending` | （Dev-Phase 0 完成时填实，源自 `analysis/06` 第二节 DoD 演示场景） | proposal + 架构研究报告 + delta-spec + delta-design + 知识图 scan_version 递增 | 单流程成本 ≤ $5；端到端延迟 ≤ 10min（不含人工等待）；Structured Outputs 合规率 ≥ 99%；连续 3 proposal 无人工干预崩溃 | （Dev-Phase 0 完成时填实，例如 `sddp run "tests/fixtures/proposals/config-hot-reload.txt"`） | （Dev-Phase 0 完成时冻结，形如 `dev-phase-0-v1`） |
| `1` | `pending` | Dev-Phase 0 同一 proposal，但用户确认通过桌宠气泡（非 CLI）；启用远程模式时跑通 SSH 隧道 | Dev-Phase 0 同等文档集 + 桌宠 UI 渲染 5 种 Push 消息 + 4 种 RPC 请求可见 | Dev-Phase 0 同等阈值 + WebSocket 连接丢失 < 1 次/流程；远程模式延迟 penalty ≤ 2x 本地 | （Dev-Phase 1 完成时填实） | （Dev-Phase 1 完成时冻结） |
| `2` | `pending` | 一个需要对抗收敛的 proposal（例如"重构知识图查询接口以支持多语言"）；预期至少 2 个挑评师维度参与 | delta-spec + delta-design + 对抗记录（≥2 轮）+ 收敛判定（含 LLM 机械化字段） | 单流程成本 ≤ $15；对抗 ≤ 5 轮强制收敛或 escalate；挑评师/实证师/调度官桌宠动画顺序正确 | （Dev-Phase 2 完成时填实） | （Dev-Phase 2 完成时冻结） |
| `3a` | `pending` | 验收师指定的一个测试 spec（包含超时/资源限制场景）；实施师产出一个待写入文件 diff；规范员规则集预测 | SandboxedExecutor 结构化测试结果；FileWriteProxy 写入或用户拒绝；RuleMapper 预测 vs 实际 lint 一致率 ≥ 80% | 沙箱逃逸尝试全部拒绝；预测准确率 ≥ 80%；FileWriteProxy 拒绝路径正确 | （Dev-Phase 3a 完成时填实） | （Dev-Phase 3a 完成时冻结） |
| `3b` | `pending` | 一个含 P0/P1/P2 三种严重度问题的实施代码（fixture 构造） | 质量判定报告（验收 P0 阻断 → 修缮 → 二次验证通过；复核 P1 待修；规范 P2 警告不阻断）；审计日志含所有数据发送行为 | 修复循环 ≤ 3 轮；三种严重度术语在报告中字段独立；审计日志条目数 = 远程数据发送次数 | （Dev-Phase 3b 完成时填实） | （Dev-Phase 3b 完成时冻结） |
| `4` | `pending` | （Dev-Phase 4 按选定特性子项分别冻结；本槽位在选定具体特性前为占位） | （按子项特性填实） | （按子项特性填实） | （Dev-Phase 4 完成时按子项填实） | （按子项分别冻结，形如 `dev-phase-4-live2d-v1`） |
| `5` | `pending` | 一个快速通道级别的 proposal（仅判定为简单变更），在本地 Ollama 模型下运行 | proposal → 微任务清单 → 实施师建议 → 规范员扫描 → 简版归档；离线模式下产出 | 离线模式下端到端延迟 ≤ 30min（允许 3x OpenAI 延迟）；不要求对抗循环（已接受风险） | （Dev-Phase 5 完成时填实） | （Dev-Phase 5 完成时冻结） |

---

## 二、Dev-Phase 0 Golden Demo 详细规格（数据填实）

> 本节为 Dev-Phase 0 的具体 Golden Demo 规格模板。Dev-Phase 0 完成时复制本节内容到 `golden-demos/dev-phase-0.md` 并填实"运行命令"与"git tag"。

### 输入场景
```
"给这个 Python 项目加一个配置热重载功能"
```
- 输入文件路径（Dev-Phase 0 完成时固化）：`tests/fixtures/proposals/config-hot-reload.txt`
- 目标代码库（Dev-Phase 0 完成时固化）：一个 ≥10 文件的 Python 项目（fixture 路径待定）

### 期望输出（端到端）
1. **proposal.md**：含需求背景/需求解析/变更范围预估/约束与风险/资源需求清单/流程建议/PCM 七个章节
2. **(用户 CLI 确认 — 第 1 个确认点)**
3. **架构研究报告**：引用至少 1 次知识图查询结果（含 `confidence` 字段）
4. **delta-spec.md**：含变更范围/接口契约/影响面分析/约束条件；影响面分析章节须标注查询置信度
5. **delta-design.md**：含架构决策/数据流/关键算法/模块划分/异常处理/编码参照
6. **(用户 CLI 确认 — 第 2 个确认点)**
7. **知识图更新**：scan_version 字段递增；架构师咨询的修改范围在更新后的知识图中可查询

### 度量阈值范围
| 指标 | 下限 | 上限 | 来源 |
|------|------|------|------|
| 单流程成本 (USD) | 0 | 5.0 | `dod.md` D0-11 |
| 端到端延迟 (min, 不含人工等待) | 0 | 10.0 | `dod.md` D0-12 |
| Structured Outputs 一次性合规率 | 0.99 | 1.0 | `dod.md` D0-13 |
| 连续无崩溃 proposal 数 | 3 | ∞ | `dod.md` D0-14 |

### 运行命令
```
（Dev-Phase 0 完成时填实，预期形如）
sddp run tests/fixtures/proposals/config-hot-reload.txt \
  --project tests/fixtures/sample-python-project/ \
  --output out/dev-phase-0-golden-demo/
```

### git tag
```
（Dev-Phase 0 完成时冻结，形如 dev-phase-0-v1）
```

---

## 三、回归重放规则摘要

详细规则见 `regression-strategy/spec.md` 中"回归门控 MUST 作为 opsx-apply 验收的强制前置"需求。摘要：

1. **Dev-Phase N 验收前**（N > 0）：重放所有状态为 `frozen` 的 Golden Demo（N=1 时重放 DP0；N=2 时重放 DP0+DP1；以此类推）。
2. **重放报告**：每次重放 MUST 记录"重放基线 git tag"和"重放目标 HEAD"，写入 `golden-demos/dev-phase-<n>.md` 末尾的"重放结果历史"表。
3. **失败处理**：任一历史 demo 不通过 → 阻断当前 Dev-Phase 的 Go 判定 → 按本表定位失败的责任模块（依据 `modules.md` 的"归属 Dev-Phase"列）。
4. **执行上限**：完整重放 ≤ 30min、成本 ≤ $20；累积 >5 demo 时允许"代表性子集"快速通道（每历史阶段抽 1 个最关键 demo；仅用于实现期反馈，验收时仍需全量）。
