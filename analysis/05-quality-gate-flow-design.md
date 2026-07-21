# G4: Phase 3 质量关卡 Flow 设计

> 日期: 2026-07-20
> 状态: P0 缺口补齐
> 关联: 01-final-review.md G4; crewai-technical-research.md(仅实现 Phase 1); SDDP设计文档 Phase 3

---

## 一、问题陈述

crewai-technical-research.md 只给出了 Phase 1(方案对抗)的 CrewAI 实现。SDDP 的 Phase 3 质量关卡是**结构同样复杂、且复用相同 CrewAI 模式**的循环，但此前完全空白。被塞进"Dev-Phase 3: 4-6周"而未做可行性验证。

本文件给出 Phase 3 的 CrewAI Flow 骨架、Pydantic 模型、严重度术语处理，并明确其前置依赖。

---

## 二、Phase 3 结构分析（来自 SDDP 设计文档）

### 2.1 执行拓扑

```
实施代码
  │
  ▼
验收师(功能验收) ──▶ 验收报告
  │
  ├─ P0 全通过 ─────────────────▶ 复核师(一致性审查)
  │                                 │
  │                                 ├─ 复核通过 ──▶ 规范员(规范扫描)
  │                                 │                 │
  │                                 │                 ├─ 规范通过 ──▶ 质量判定: 通过 ✅
  │                                 │                 │
  │                                 │                 └─ 规范不通过 ─▶ 修缮师 ─▶ 二次验证(验收+复核+规范)
  │                                 │
  │                                 └─ 复核不通过 ───▶ 修缮师 ─▶ 二次验证(验收+复核)
  │
  ├─ P1/P2 不通过 ─▶ 记录,不阻断 ──┐
  │                                │
  └─ P0 不通过 ──▶ 修缮师 ─▶ 验收师二次验收 ──(通过)─▶ 复核师
                     ↺ 最多 3 轮 ↺
超出 3 轮 ──▶ 上报调度官
质量判定不通过 ──▶ 用户确认(继续修复/接受风险/回退)
```

### 2.2 与 Phase 1 的结构对比

| 维度 | Phase 1 对抗 | Phase 3 质量关卡 |
|------|------------|----------------|
| 循环类型 | 架构师↔挑评师 单环 | 验收→复核→规范 串行链 + 修缮回环 |
| 角色数 | 5(架构/挑评/实证/调度/需求) | 4(验收/复核/规范/修缮) + 调度官 |
| 最大轮数 | 5 | 每关卡 3(修复循环) |
| 收敛判据 | 质疑维度全"可接受" | 三关卡全通过 |
| 失败上报 | 用户裁决 | 调度官,再上报用户 |
| **CrewAI 模式复用** | `@router`+`or_()`+`@persist` | **完全相同** |

**关键结论**: Phase 3 复用 Phase 1 已验证的 CrewAI 循环模式，技术风险**继承但非新增**。Phase 1 冒烟通过 → Phase 3 大概率可行。

### 2.3 三套严重度术语（必须独立处理）

| 角色 | 严重度体系 | 阻断行为 |
|------|----------|---------|
| 验收师 | P0(阻断) / P1(不阻断待修) / P2(不阻断待修) | 仅 P0 触发修复回环 |
| 复核师 | P1-高 / P1-中 / P1-低 | 高阻断,中低记录 |
| 规范员 | 错误 / 警告 / 信息 | 仅"错误"阻断 |

> SDDP 设计明确: 三套术语独立,不跨角色混用。Flow 中必须用各自枚举,不可统一映射。

---

## 三、前置依赖（阻断 Phase 3 落地的硬条件）

Phase 3 的三个角色需要执行能力，这正是 00-final "差距4" 描述的 LLM 局限:

| 角色 | 需要的执行能力 | MVP 绕过(00-final 差距4) | Phase 3 真正需要的子系统 |
|------|--------------|------------------------|------------------------|
| 验收师 | 运行测试验证功能 | 推迟到 Dev-Phase 3 | **SandboxedExecutor**(安全沙箱跑测试) |
| 规范员 | 执行 lint/format/security 扫描 | 规则映射(静态预测) | **RuleMapper**(规则→lint结果) + CI 实际执行 |
| 复核师 | 读取代码做一致性检查 | (LLM 可直接做,需代码上下文) | 代码资产管理员查询 + 文件读取代理 |
| 修缮师 | 写文件修复 | 仅产出修复建议 | **FileWriteProxy**(写文件+diff确认) |

**因此 Phase 3 不能在子系统就绪前实现。** 这把"Dev-Phase 3: 4-6周"重新切分为:
- Dev-Phase 3a: 子系统(SandboxedExecutor + RuleMapper + FileWriteProxy) — 3-4 周
- Dev-Phase 3b: Phase 3 Flow + 4 角色 — 2-3 周

---

## 四、Pydantic 数据模型（三种报告）

```python
# backend/models/quality_reports.py（骨架）

from pydantic import BaseModel, Field
from typing import List, Literal
from enum import Enum

# === 验收师 ===
class AcceptanceSeverity(str, Enum):
    P0 = "P0"   # 阻断
    P1 = "P1"   # 不阻断,待修
    P2 = "P2"   # 不阻断,待修

class AcceptanceCheckItem(BaseModel):
    interface: str = Field(description="接口名,delta-spec 中定义")
    expected: str
    actual: str
    severity: AcceptanceSeverity
    result: Literal["pass", "fail"]

class AcceptanceReport(BaseModel):
    contract_checks: List[AcceptanceCheckItem]      # 接口契约验证
    behavior_checks: List[AcceptanceCheckItem]       # 预期行为验证
    boundary_checks: List[AcceptanceCheckItem]       # 边界场景验证
    verification_source: Literal["PCM继承", "SDDP默认"]
    overall: Literal["pass", "fail"]
    p0_failures: List[str]                           # 阻断项
    p1_failures: List[str]                           # 待修项

# === 复核师 ===
class ReviewSeverity(str, Enum):
    P1_HIGH = "P1-高"
    P1_MED = "P1-中"
    P1_LOW = "P1-低"

class ReviewCheckItem(BaseModel):
    check_item: str
    delta_design_ref: str = Field(description="delta-design 对应章节")
    impl_status: str
    consistency: Literal["consistent", "inconsistent"]
    severity: ReviewSeverity
    note: str = ""

class ReviewReport(BaseModel):
    consistency_checks: List[ReviewCheckItem]
    logic_checks: List[ReviewCheckItem]
    missing_items: List[str]                         # 方案提及但未实现
    overall: Literal["pass", "fail"]
    blocking_failures: List[str]                     # P1-高

# === 规范员 ===
class LintSeverity(str, Enum):
    ERROR = "错误"
    WARNING = "警告"
    INFO = "信息"

class LintFinding(BaseModel):
    rule_id: str
    category: Literal["lint", "format", "security"]
    severity: LintSeverity
    file: str
    line: int
    description: str
    fix_suggestion: str

class LintReport(BaseModel):
    findings: List[LintFinding]
    lint_config_source: Literal["PCM继承", "SDDP默认"]
    error_count: int
    warning_count: int
    info_count: int
    overall: Literal["pass", "fail"]
    blocking_findings: List[LintFinding]             # "错误"级

# === 修缮师 ===
class RepairPatch(BaseModel):
    target_files: List[str]
    diff: str
    addresses: List[str] = Field(description="修复对应的失败项ID")
    round_number: int

# === 质量判定 ===
class QualityVerdict(BaseModel):
    acceptance: Literal["pass", "fail"]
    review: Literal["pass", "fail"]
    lint: Literal["pass", "fail"]
    overall: Literal["pass", "fail"]
    reason: str
    total_repair_rounds: int
```

---

## 五、CrewAI Flow 骨架

复用 Phase 1 模式: `@persist` + `@router` + `or_()` + `SafeAgent` + `@human_feedback`。

```python
# backend/flows/phase3_quality_gate.py（骨架，非完整实现）

from crewai.flow.flow import Flow, listen, router, start, or_
from crewai.flow.human_feedback import human_feedback
from crewai.flow.persistence import persist
from pydantic import BaseModel, Field
from typing import List

class Phase3State(BaseModel):
    id: str = ""
    delta_spec: str = ""
    delta_design: str = ""
    implementation_files: List[str] = []
    pcm: str = ""

    # 各关卡最新报告
    acceptance_report: dict = None
    review_report: dict = None
    lint_report: dict = None

    # 修复循环计数(按关卡分别计)
    acceptance_repair_rounds: int = 0
    review_repair_rounds: int = 0
    lint_repair_rounds: int = 0
    max_rounds_per_gate: int = 3

    # 待修复项追踪
    pending_p0: List[str] = []
    pending_p1_high: List[str] = []
    pending_lint_errors: List[str] = []

    errors: List[str] = []
    escalated: bool = False                          # 上报调度官

@persist
class Phase3QualityGateFlow(Flow[Phase3State]):
    # 角色(均经 SafeAgent 包裹,见 03-crewai-version-strategy 第五节)
    acceptor = safe_acceptor
    reviewer = safe_reviewer
    linter = safe_linter
    repairer = safe_repairer

    @start()
    def init_phase3(self):
        return "start_acceptance"

    # --- 验收关卡 ---
    @listen("start_acceptance")
    def run_acceptance(self):
        # 验收师调用 SandboxedExecutor 跑测试,产出 AcceptanceReport
        result = self.acceptor.kickoff(inputs={
            "delta_spec": self.state.delta_spec,
            "impl_files": self.state.implementation_files,
            "pcm_verification": self.state.pcm,
            "task": "运行功能验收测试,产出验收报告",
        })
        self.state.acceptance_report = self._parse_report(result.raw, AcceptanceReport)
        return "acceptance_done"

    @router("acceptance_done")
    def route_acceptance(self):
        rep = self.state.acceptance_report
        if rep["overall"] == "pass":
            return "acceptance_passed"
        if rep["p0_failures"]:
            self.state.pending_p0 = rep["p0_failures"]
            if self.state.acceptance_repair_rounds >= self.state.max_rounds_per_gate:
                return "escalate"
            return "need_repair_acceptance"
        # P1/P2 不阻断,记录后进入复核
        return "acceptance_passed"

    # --- 复核关卡 ---
    @listen("acceptance_passed")
    def run_review(self):
        result = self.reviewer.kickoff(inputs={
            "delta_design": self.state.delta_design,
            "impl_files": self.state.implementation_files,
            "task": "一致性审查,产出复核报告",
        })
        self.state.review_report = self._parse_report(result.raw, ReviewReport)
        return "review_done"

    @router("review_done")
    def route_review(self):
        rep = self.state.review_report
        if rep["overall"] == "pass":
            return "review_passed"
        if rep["blocking_failures"]:                 # P1-高
            self.state.pending_p1_high = rep["blocking_failures"]
            if self.state.review_repair_rounds >= self.state.max_rounds_per_gate:
                return "escalate"
            return "need_repair_review"
        return "review_passed"

    # --- 规范关卡 ---
    @listen("review_passed")
    def run_lint(self):
        # 规范员调用 RuleMapper + CI 实际执行 lint
        result = self.linter.kickoff(inputs={
            "impl_files": self.state.implementation_files,
            "pcm_lint_config": self.state.pcm,
            "task": "lint/format/security 规范扫描",
        })
        self.state.lint_report = self._parse_report(result.raw, LintReport)
        return "lint_done"

    @router("lint_done")
    def route_lint(self):
        rep = self.state.lint_report
        if rep["overall"] == "pass":
            return "quality_passed"
        if rep["blocking_findings"]:                 # "错误"级
            self.state.pending_lint_errors = [f.rule_id for f in rep["blocking_findings"]]
            if self.state.lint_repair_rounds >= self.state.max_rounds_per_gate:
                return "escalate"
            return "need_repair_lint"
        return "quality_passed"

    # --- 修缮师(统一入口,按 pending 项路由二次验证范围) ---
    @listen(or_("need_repair_acceptance", "need_repair_review", "need_repair_lint"))
    def run_repair(self, trigger):
        # 修缮师调用 FileWriteProxy 产出修复补丁
        result = self.repairer.kickoff(inputs={
            "pending_p0": self.state.pending_p0,
            "pending_p1_high": self.state.pending_p1_high,
            "pending_lint_errors": self.state.pending_lint_errors,
            "trigger": trigger,                       # 告知修缮师本轮修哪类
            "task": "产出修复补丁",
        })
        patch = self._parse_report(result.raw, RepairPatch)
        # 递增对应关卡计数
        if trigger == "need_repair_acceptance":
            self.state.acceptance_repair_rounds += 1
            return "revalidate_acceptance"
        elif trigger == "need_repair_review":
            self.state.review_repair_rounds += 1
            return "revalidate_review"
        else:
            self.state.lint_repair_rounds += 1
            return "revalidate_lint"

    # --- 二次验证(回到对应关卡) ---
    # 注意: or_() 复用同一方法,SDDP 设计要求"规范不通过需验收+复核+规范全跑"
    @listen(or_("revalidate_acceptance", "revalidate_review", "revalidate_lint"))
    def revalidate(self, trigger):
        # 根据 trigger 决定跑哪些关卡:
        #   revalidate_acceptance → 验收(再走 route_acceptance)
        #   revalidate_review → 验收+复核
        #   revalidate_lint → 验收+复核+规范
        # 简化实现: 修复后从验收重跑(保守,多跑但安全)
        return "start_acceptance"

    # --- 终态 ---
    @listen("quality_passed")
    def quality_passed(self):
        return {"verdict": "pass", "reports": {...}}

    @listen("escalate")
    @human_feedback(
        message="质量关卡超出3轮未通过,调度官上报。用户裁决?",
        emit=["continue_repair", "accept_risk", "rollback"],
        llm="gpt-4o-mini",
        default_outcome="rollback",
    )
    def user_quality_decision(self):
        return self.state

    # --- 辅助 ---
    def _parse_report(self, raw, schema):
        # 用 output_pydantic 在 Task 层强制;此处兜底解析
        ...
```

### 关键设计点

1. **`@router` 三连**: 验收/复核/规范各一个 router，分别判定该关卡的通过/修复/上报
2. **`or_()` 修缮汇聚**: 三类修复需求汇入单一修缮师入口，按 trigger 区分修什么
3. **二次验证保守策略**: 修复后从验收重跑（SDDP 允许"规范不通过需三关卡全跑"，最保守实现统一从验收跑，多花成本但避免遗漏）
4. **按关卡独立计轮**: 三个 `*_repair_rounds` 计数器，符合 SDDP"每关卡最多3轮"语义
5. **escalate 统一出口**: 任一关卡超轮 → 上报调度官 → 用户裁决

---

## 六、与 Phase 1 的共享基础设施

Phase 3 不重写，直接复用 Phase 1 已建:

| 设施 | Phase 1 已建 | Phase 3 复用 |
|------|------------|------------|
| SafeAgent wrapper | ✅ | ✅ 包裹 4 个新角色 |
| @persist SQLite | ✅ | ✅ Phase3State 持久化 |
| @human_feedback WebSocketProvider | ✅ | ✅ escalate 时用 |
| Pydantic 解析兜底 | ✅ | ✅ _parse_report |
| 适配层抽象 | ✅ | ✅ Flow 定义与 CrewAI 解耦 |
| CrewAI 版本锁定 | ✅ | ✅ 同一 lockfile |

**新增成本仅在**: 4 个角色 backstory/backstory + 3 个报告 Pydantic + Flow 拓扑 + 3 个执行子系统接口。

---

## 七、风险（继承 Phase 1 + Phase 3 特有）

| 风险 | 来源 | 缓解 |
|------|------|------|
| CrewAI #5972 在三连 router 下复现 | Phase 1 已验证 or_() 循环;三连 router 是新模式 | Phase 3 落地前先跑"三关卡串行+1次修复"冒烟 |
| 修缮师修复引入新问题(回归) | 修复-二次验证循环 | 保守策略:修复后从验收重跑全链 |
| 执行子系统(SandboxedExecutor 等)不可靠 | Phase 3 特有 | 子系统独立验证(Dev-Phase 3a)先于 Flow(3b) |
| 三套严重度术语混淆 | LLM 可能跨体系混用 | output_pydantic 强制枚举 + guardrail 校验 |
| 修复循环实际超过3轮 | 复杂变更 | escalate 到用户,不强收 |

---

## 八、对 00-final 的修订项

1. 第十节 Dev-Phase 3 拆分为 **3a(执行子系统)+3b(质量关卡Flow)**，工期 5-7 周(原 4-6 周)
2. 第十节 MVP 范围明确: **Phase 3 完全不在 MVP**，连骨架都不在(因依赖执行子系统)
3. 第六节"差距4"的 Dev-Phase 2-3 子系统，细化为 3a 的核心交付物

---

## 九、验证计划（Dev-Phase 3b 启动前）

落地 Phase 3 Flow 前，先验证三关卡串行+修复循环在选定 CrewAI 版本下可行:
1. 冒烟测试: 验收(pass)→复核(pass)→规范(pass)→quality_passed，无修复
2. 冒烟测试: 验收(P0 fail)→修缮→二次验收(pass)→复核→规范，1 轮修复
3. 冒烟测试: 规范(error)→修缮→二次全链(验收+复核+规范)
4. 上限测试: 故意构造不可修复问题，验证 3 轮后 escalate

通过这 4 个冒烟才进入完整实现。
