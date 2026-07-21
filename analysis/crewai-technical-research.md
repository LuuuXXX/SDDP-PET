# CrewAI Technical Research: Evidence-Based Findings for SDDP

> Date: 2026-07-20
> Sources: CrewAI official docs (docs.crewai.com), GitHub issues/PRs on crewAIInc/crewAI, SDDP design doc
> CrewAI version analyzed: 1.15.x (latest as of July 2026)
>
> **⚠️ Superseded items (2026-07-20 同日, 见 00-sddp-pet-final vFINAL.1)**:
> - 第2节"代码资产管理员" backstory 中 "GitNexus/Graphify知识图" 已被 **SCIP + tree-sitter** 取代(权威设计见 02-code-knowledge-graph-design.md)。本文 backstory 代码为历史调研示例, 实现时按 02 替换技术栈表述。
> - 版本"1.15.x"为调研时占位, 实际锁定流程见 03-crewai-version-strategy.md。
> - 本文只实现 Phase 1 对抗; Phase 3 质量关卡 Flow 见 05-quality-gate-flow-design.md。

---

## 1. CrewAI Flows Real-World Reliability

### Stability Assessment: **Moderate — Active Bugs Being Fixed, API Under Rapid Refactoring**

### Known Issues (Evidence from GitHub)

| Issue/PR | Severity | Status | Impact on SDDP |
|----------|----------|--------|----------------|
| [#5972] `@listen(or_(A,B,C))` only fires once, blocking cyclic re-triggering | **Critical** | Fixed (#5994/#5974) | Directly impacts Phase 1 adversarial loop (架构师→挑评师→调度官→back to 架构师). This bug would have prevented the adversarial cycle from working. Fixed in recent versions. |
| [#6370] No hard ceiling on router hops — infinite loop possible | **High** | Open PR | `MAX_ROUTER_HOPS=100` proposed. Without this, an adversarial loop without convergence detection would hang indefinitely. SDDP's 5-round limit must be explicitly implemented. |
| [#6219] Feature request for LoopHalter (automatic infinite loop detection) | Medium | Open | No native loop detection. SDDP must implement its own convergence logic. |
| [#6380] Async task LLM failure silently freezes flow | **High** | Open (#6407) | When an agent's LLM call fails (timeout, rate limit, 500), the async executor catches the exception but never propagates it. The task stays in "running" state, downstream agents wait indefinitely. **This is a production footgun.** |
| [#6347] `Task(human_input=True)` crashes with AttributeError in 1.15.0 | **High** | Fixed (#6372) | The default executor was silently swapped from `CrewAgentExecutor` to experimental `AgentExecutor`, which lacks 3 required `ExecutorContext` methods. Workaround: explicitly set `executor_class=CrewAgentExecutor`. |
| [#6065] Same human_input crash, earlier report | **High** | Fixed | Same root cause as #6347. |

### API Refactoring Activity (Last 30 Days)

Recent PRs show the Flows API is undergoing **major structural changes**:

| PR | Description | Impact |
|----|-------------|--------|
| #6071 | Migrate `@start` to read from `FlowDefinition` | Internal restructuring |
| #6084 | Migrate `@listen/@router` runtime to read from `FlowDefinition` | Internal restructuring |
| #6097 | Simplify flow condition evaluation to be stateless per event | Breaking change potential |
| #6104 | Run flows from a definition without a Python subclass | New capability |
| #6288 | Allow `@router()` as start method of a flow | New capability |
| #6393 | Add generated Flow Definition authoring skill | Tooling |
| #6405 | Reject self-listening flow methods | Safety guard |

**Assessment**: The Flows API is in active refactoring. The core decorators (`@start/@listen/@router`) work, but the underlying runtime is being rewritten. **Not production-stable for mission-critical workflows yet**, but rapidly improving. SDDP should pin to a specific CrewAI version and test thoroughly.

### Production Deployment Evidence

No documented production deployments using CrewAI Flows with adversarial/cyclic patterns were found. The official examples (email_auto_responder_flow, lead-score-flow, write_a_book_flow, meeting_assistant_flow) are demonstration projects, not production systems. CrewAI Enterprise (AMP Suite) offers managed deployment, but its Flows usage in production is not publicly documented.

**Risk for SDDP**: SDDP's adversarial mechanism (multi-round architect→critic→arbitrator loop) is more complex than any documented CrewAI Flow example. This is essentially uncharted territory.

---

## 2. @human_feedback Mechanism

### How It Works

**Default behavior: Blocking console input**

```python
@start()
@human_feedback(message="Do you approve this content?")
def generate_content(self):
    return "Content to be reviewed..."
```

When `kickoff()` is called, execution **pauses** at the `@human_feedback` method, displays the output in a Rich panel, and waits for the user to type feedback on the console. This is a **blocking call** — the entire flow thread is suspended until input is received.

**With `emit` parameter: LLM-collapsed routing**

```python
@human_feedback(
    message="Approve or request changes?",
    emit=["approved", "rejected", "needs_revision"],
    llm="gpt-4o-mini",
    default_outcome="needs_revision",
)
@listen(or_("generate_draft", "needs_revision"))
def review_draft(self):
    return self.state.draft
```

The human's free-form feedback text is passed to an LLM which collapses it into one of the specified `emit` outcomes using structured outputs (function calling). The outcome then triggers the corresponding `@listen("outcome")` decorator. This enables routing without manual outcome classification.

### Integration with WebSocket-based Desktop Pet UI

**The `HumanFeedbackProvider` abstraction is the key mechanism.**

```python
from crewai.flow.human_feedback import HumanFeedbackProvider, HumanFeedbackPending, PendingFeedbackContext

class WebSocketProvider(HumanFeedbackProvider):
    def __init__(self, ws_url: str):
        self.ws_url = ws_url

    def request_feedback(self, context: PendingFeedbackContext, flow: Flow) -> str:
        # Notify Electron frontend via WebSocket
        self.send_to_frontend(context)
        # Pause execution - framework handles persistence automatically
        raise HumanFeedbackPending(
            context=context,
            callback_info={"ws_url": f"{self.ws_url}/{context.flow_id}"}
        )
```

When `HumanFeedbackPending` is raised:
1. **The flow automatically persists its state** (SQLite by default)
2. **`kickoff()` returns a `HumanFeedbackPending` object** (not an exception)
3. **The frontend can resume the flow** when user input arrives:

```python
# In your WebSocket handler:
async def handle_user_feedback(flow_id: str, feedback: str):
    flow = ReviewFlow.from_pending(flow_id)
    result = await flow.resume_async(feedback)  # Resumes from persisted state
    return result
```

### Architecture for SDDP Desktop Pet

```
Electron Frontend                Python CrewAI Backend
┌──────────────┐                ┌──────────────────┐
│  Desktop Pet │◄──WebSocket──►│  FastAPI Server   │
│  UI (PixiJS) │                │  + CrewAI Flow    │
│              │                │                   │
│ User clicks  │───feedback────►│  flow.resume()    │
│ "确认/否决"  │                │  or               │
│              │◄──state update─│  flow.kickoff()   │
└──────────────┘                └──────────────────┘
```

**Critical caveat**: Bug #6347 shows that `human_input=True` on Tasks crashes with the new default `AgentExecutor`. The `@human_feedback` decorator on Flows is a separate mechanism and does NOT have this bug. **Use `@human_feedback` on Flow methods, NOT `human_input=True` on Tasks**, for SDDP's 8 user confirmation points (6 mandatory + 1 optional + 1 conditional).

---

## 3. @router for Adversarial Loops

### Can @router Create a Loop?

**Yes, but with caveats.**

The CrewAI docs explicitly document the self-loop pattern for revision cycles:

```python
@human_feedback(
    message="Approve or request changes?",
    emit=["revise", "approved"],
    llm="gpt-4o-mini",
)
@listen(or_("generate", "revise"))
def review(self):
    return "content"
```

The flow engine **exempts routers from the "fire once" rule**, allowing them to re-execute on each loop iteration. This means a `@router` can cycle back to its own listener via `or_()`.

### SDDP Phase 1 Adversarial Loop Implementation

```python
from crewai.flow.flow import Flow, listen, router, start, or_
from crewai.flow.human_feedback import human_feedback, HumanFeedbackPending
from pydantic import BaseModel

class AdversarialState(BaseModel):
    proposal: str = ""
    current_design: str = ""
    criticism_points: list = []
    evidence_reports: list = []
    arbitration_results: list = []
    round_count: int = 0
    max_rounds: int = 5
    converged: bool = False

class AdversarialFlow(Flow[AdversarialState]):
    @start()
    def init_phase1(self):
        self.state.proposal = "Initial proposal text"
        return "start_adversarial"

    @listen("start_adversarial")
    def architect_design(self):
        # Architect produces/revises delta-spec + delta-design
        self.state.round_count += 1
        # ... LLM call to generate design ...
        return self.state.current_design

    @listen(architect_design)
    def critic_challenge(self):
        # Critic identifies risks, produces criticism points
        # ... LLM call to generate criticism ...
        return self.state.criticism_points

    @listen(critic_challenge)
    def empiricist_verify(self):
        # Empiricist provides evidence for criticism
        # ... LLM call + tool execution ...
        return self.state.evidence_reports

    @router(empiricist_verify)
    def arbitrator_decide(self):
        # Orchestrator/arbitrator makes routing decision
        if self.state.converged or self.state.round_count >= self.state.max_rounds:
            return "converged"
        # Check if all criticism dimensions are "acceptable"
        all_resolved = self._check_convergence()
        if all_resolved:
            return "converged"
        return "revise"  # Loop back to architect

    @listen("revise")
    def trigger_revision(self):
        # Re-triggers architect for next adversarial round
        return "revision_needed"

    @listen(or_("start_adversarial", "revision_needed"))
    def architect_design_loop(self):
        # This fires both initially and on each revision
        self.state.round_count += 1
        # ... revise design based on arbitration + evidence ...
        return self.state.current_design

    @listen("converged")
    @human_feedback(
        message="方案已收敛，确认 delta-spec + delta-design?",
        emit=["approved", "rejected"],
        llm="gpt-4o-mini",
        default_outcome="rejected",
    )
    def user_confirm_design(self):
        return self.state.current_design

    @listen("approved")
    def phase1_complete(self, result):
        self.state.converged = True
        return "Phase 1 complete"

    def _check_convergence(self):
        # Custom convergence logic
        # Each criticism dimension must be "acceptable"
        for point in self.state.criticism_points:
            if point["status"] != "resolved":
                return False
        return True
```

### Known Issues with @router Loops

1. **Bug #5972 (fixed)**: `@listen(or_(A,B))` only fired once, preventing cyclic re-triggering. This was fixed in PRs #5994/#5974.

2. **No built-in convergence detection**: CrewAI has no mechanism to detect "the loop should stop because conditions are met." SDDP must implement its own convergence check in the router method (`_check_convergence()`).

3. **MAX_ROUTER_HOPS ceiling (PR #6370)**: A proposed `MAX_ROUTER_HOPS=100` would raise `RuntimeError` if exceeded. SDDP's 5-round adversarial limit (each round = ~3-4 router hops) would stay well under 100. **But if the router chain is architect→critic→empiricist→arbitrator (4 hops per round × 5 rounds = 20 hops), this is safe.** However, the CodeRabbit review on PR #6370 noted that the 100-hop limit may be too low for valid experimental agent loops. This PR is still open.

4. **Self-listening rejection (PR #6405)**: A merged PR rejects flow methods that listen to themselves (`@listen(self_method)`). This doesn't affect SDDP's pattern since the loop uses `@listen(or_("trigger", "revision_outcome"))` rather than direct self-listening.

### Convergence Detection Implementation

SDDP must implement convergence in the `@router` method. The design doc specifies:

> 收敛标准：每个质疑维度均达到"可接受"状态

Recommended implementation:

```python
@router(empiricist_verify)
def arbitrator_decide(self):
    if self.state.round_count >= self.state.max_rounds:
        # Force convergence after 5 rounds, submit to user
        return "force_converged"

    unresolved_high = [
        p for p in self.state.criticism_points
        if p["severity"] == "high" and p["status"] != "resolved"
    ]
    if unresolved_high:
        return "revise"  # High-severity unresolved → must continue

    unresolved_medium_low = [
        p for p in self.state.criticism_points
        if p["severity"] in ["medium", "low"] and p["status"] != "resolved"
    ]
    if not unresolved_medium_low:
        return "converged"  # All resolved → converge

    # Medium/low unresolved → arbitrator can dismiss with evidence
    return "partial_converged"
```

---

## 4. CrewAI Dynamic Agent Scaling

### Answer: **Agents must be predefined before a Flow starts. No native dynamic scaling.**

CrewAI's architecture requires agents to be defined before Flow execution:

```python
class MarketResearchFlow(Flow[MarketResearchState]):
    @listen(initialize_research)
    async def analyze_market(self):
        analyst = Agent(
            role="Market Research Analyst",
            goal=f"Analyze the market for {self.state.product}",
            backstory="...",
            tools=[SerperDevTool()],
        )
        result = await analyst.kickoff_async(query, response_format=MarketAnalysis)
```

**Key finding**: Agents can be **created inside Flow methods** (as shown above in the docs), but this is creation-at-invocation, not dynamic scaling of existing agent pools. Each method invocation creates a fresh agent instance.

### What This Means for SDDP

SDDP's design requires "≥1 动态" instances for several roles (架构师, 挑评师, 实证师, etc.). In CrewAI, this can be implemented as:

```python
class SDDPFlow(Flow[SDDPState]):
    @listen("start_adversarial")
    def adversarial_round(self):
        # Create N critic instances based on load
        num_critics = self._determine_critic_count()
        critics = [
            Agent(
                role=f"挑评师-{dimension}",
                goal=f"从{dimension}维度质疑方案",
                backstory=f"你是专门从{dimension}维度审查方案的专家...",
            )
            for dimension in self.state.criticism_dimensions[:num_critics]
        ]
        # Run each critic and collect results
        for critic in critics:
            result = critic.kickoff(inputs={"design": self.state.current_design})
            self.state.criticism_points.append(result)
```

**Limitations**:
- No native load-based scaling — SDDP must implement `_determine_critic_count()` manually
- No agent pool management — agents are created and discarded each round
- No reuse of agent state/memory across rounds — each `Agent()` instantiation starts fresh
- This pattern increases LLM API costs since each new agent instance pays the full prompt cost

**Recommendation for SDDP**: Pre-define a fixed set of role-specific agents at Flow initialization, and use `or_()`/`and_()` to coordinate them. For "dynamic scaling," implement a scaling decision method inside the Flow that selects how many pre-defined agent variants to invoke.

```python
class SDDPFlow(Flow[SDDPState]):
    # Pre-defined agents at Flow init
    architect = Agent(role="架构师", ...)
    critic_security = Agent(role="挑评师-安全维度", ...)
    critic_performance = Agent(role="挑评师-性能维度", ...)
    critic_maintainability = Agent(role="挑评师-可维护性维度", ...)
    empiricist = Agent(role="实证师", ...)
    orchestrator = Agent(role="调度官", ...)

    def _select_critics(self):
        # Dynamic selection from pre-defined pool
        if self.state.round_count == 1:
            return [self.critic_security, self.critic_performance]
        else:
            return [self.critic_security, self.critic_performance, self.critic_maintainability]
```

---

## 5. CrewAI Error Handling and Recovery

### What Happens When an Agent Fails?

**Critical bug #6380**: Async task LLM failures **silently freeze the entire flow**.

When an agent's LLM call fails (timeout, rate limit, API error):
- In **sync execution**: The exception propagates and the flow crashes
- In **async execution**: The exception is caught internally but **never propagated**. The task stays in "running" state indefinitely. Downstream agents that depend on its output wait forever. **No exception, no log, the process just hangs.**

This is a **confirmed production bug** with no official fix yet (PR #6407 is open).

### Does the Flow Crash? Can It Resume?

Without `@persist`: **Yes, the flow crashes.** All state is lost.

With `@persist`: **The flow can resume from the last successful state.**

```python
@persist  # SQLiteFlowPersistence by default
class SDDPFlow(Flow[SDDPState]):
    @start()
    def init_phase1(self):
        self.state.proposal = "..."
```

**Resume mechanisms**:
1. `kickoff(inputs={"id": <uuid>})` — **resume**: Load the latest snapshot and continue under the same `flow_uuid`. History extends.
2. `kickoff(restore_from_state_id=<uuid>)` — **fork**: Load snapshot, hydrate with a fresh `state.id`. New run writes under new ID; source history preserved.

**Limitations of @persist for crash recovery**:
- State is persisted **after each method completes**, not during execution
- If an agent crashes mid-LLM-call, the state from the **last completed method** is recoverable, but the current method's partial output is lost
- No automatic retry mechanism — you must manually call `kickoff(inputs={"id": ...})` to resume
- The SQLite backend is local-only; no distributed crash recovery

### Recommended Error Handling for SDDP

```python
import asyncio
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

class SafeAgent:
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(min=10, max=60),
        retry=retry_if_exception_type((TimeoutError, ConnectionError)),
    )
    async def safe_kickoff(self, agent, inputs):
        try:
            return await asyncio.wait_for(
                agent.kickoff_async(inputs=inputs),
                timeout=120
            )
        except asyncio.TimeoutError:
            raise RuntimeError(f"Agent {agent.role} timed out after 120s")
        except Exception as e:
            raise RuntimeError(f"Agent {agent.role} failed: {type(e).__name__}: {e}")

@persist
class SDDPFlow(Flow[SDDPState]):
    @listen("start_phase1")
    async def architect_design(self):
        safe_agent = SafeAgent()
        try:
            result = await safe_agent.safe_kickoff(self.architect, {"proposal": self.state.proposal})
            self.state.current_design = result.raw
        except RuntimeError as e:
            self.state.errors.append(str(e))
            return "error"  # Route to error handling

    @listen("error")
    def handle_error(self):
        # Notify user, offer retry/skip/abort
        pass
```

---

## 6. CrewAI + Electron IPC Architecture

### Recommended Architecture: **WebSocket Server (FastAPI) + Electron Frontend**

This is the pattern that aligns with CrewAI's `@human_feedback` async provider mechanism and is used by similar projects.

### Architecture Diagram

```
┌─────────────────────────────────┐     ┌──────────────────────────────┐
│        Electron Frontend         │     │     Python Backend           │
│  ┌──────────────────────────┐   │     │  ┌────────────────────────┐  │
│  │  PixiJS Desktop Pet UI   │   │     │  │  FastAPI WebSocket     │  │
│  │  (transparent overlay)   │   │◄──WS─►│  │  /ws/flow-status       │  │
│  │                          │   │     │  │                        │  │
│  │  - Role animations       │   │     │  │  /ws/human-feedback    │  │
│  │  - Phase progress        │   │     │  │                        │  │
│  │  - Document cards        │   │     │  └────────────────────────┘  │
│  │  - Confirmation dialogs  │   │     │  ┌────────────────────────┐  │
│  └──────────────────────────┘   │     │  │  CrewAI Flow Engine    │  │
│                                  │     │  │  (SDDPFlow instance)   │  │
│  IPC: Main ↔ Renderer process   │     │  │  @persist + @feedback  │  │
│  (Electron IPC native)          │     │  └────────────────────────┘  │
└─────────────────────────────────┘     │  ┌────────────────────────┐  │
                                         │  │  SQLite Persistence    │  │
                                         │  │  (flow state + docs)   │  │
                                         │  └────────────────────────┘  │
                                         └──────────────────────────────┘
```

### Why WebSocket, Not HTTP REST or gRPC

| Option | Pros | Cons | SDDP Fit |
|--------|------|------|----------|
| **WebSocket** | Bidirectional, real-time state updates, matches `@human_feedback` async provider pattern, low latency | Connection management complexity | **Best fit** — SDDP needs real-time state push (agent working→idle transitions) and bidirectional feedback (user confirmation→flow resume) |
| **HTTP REST** | Simple, well-understood, easy debugging | No real-time push (must poll), latency for state updates | Poor fit — SDDP needs real-time visualization of 12 agents' state changes |
| **gRPC** | High performance, strong typing, bidirectional streaming | Complex setup, Python gRPC tooling less mature, overkill for this use case | Overkill — SDDP's data volume is small (text documents, not streaming video) |

### Implementation Pattern

**Backend (FastAPI + CrewAI)**:

```python
from fastapi import FastAPI, WebSocket
from crewai.flow.human_feedback import HumanFeedbackPending, PendingFeedbackContext

app = FastAPI()
active_flows = {}

@app.websocket("/ws/sddp")
async def sddp_websocket(ws: WebSocket):
    await ws.accept()
    while True:
        data = await ws.receive_json()
        if data["type"] == "start_flow":
            flow = SDDPFlow()
            result = flow.kickoff()
            if isinstance(result, HumanFeedbackPending):
                active_flows[result.context.flow_id] = flow
                await ws.send_json({
                    "type": "feedback_required",
                    "flow_id": result.context.flow_id,
                    "message": result.context.message,
                    "output": result.context.method_output,
                })
            else:
                await ws.send_json({"type": "flow_complete", "result": str(result)})
        elif data["type"] == "user_feedback":
            flow = active_flows[data["flow_id"]]
            result = await flow.resume_async(data["feedback"])
            await ws.send_json({"type": "flow_resumed", "result": str(result)})
```

**Frontend (Electron + WebSocket client)**:

```javascript
// In Electron renderer process
const ws = new WebSocket('ws://localhost:8765/ws/sddp');

ws.onmessage = (event) => {
    const data = JSON.parse(event.data);
    if (data.type === 'feedback_required') {
        // Show desktop pet confirmation bubble
        showConfirmationBubble(data.message, data.output);
        // On user click "确认/否决":
        ws.send(JSON.stringify({
            type: 'user_feedback',
            flow_id: data.flow_id,
            feedback: userResponse
        }));
    } else if (data.type === 'state_update') {
        // Update pet animations based on agent states
        updatePetState(data.agent_states);
    }
};
```

### Real-World Pattern Evidence

Similar projects using this pattern:
- **openpets** (Electron): Uses Electron IPC + HTTP for agent communication
- **CoPet** (Tauri): Uses Tauri's native event system for bidirectional communication
- **LingChat** (Tauri): Uses Tauri events + WebSocket for AI chat streaming
- **clawd-on-desk** (Electron): Uses Electron IPC between main/renderer for agent state

**No project** was found that specifically connects CrewAI Python backend to Electron frontend via WebSocket. This is a novel integration pattern for SDDP.

---

## 7. JSON Schema Enforcement with CrewAI

### Does `output_pydantic` Enforce 100% Structural Compliance?

**No. It is post-validation, not pre-enforcement.**

CrewAI's `output_pydantic` mechanism works as follows:

1. The LLM generates a raw text output
2. CrewAI attempts to parse the output into the specified Pydantic model
3. If parsing succeeds → the structured model is returned
4. If parsing fails → CrewAI retries (up to `guardrail_max_retries`, default 3)

**This is NOT the same as OpenAI's Structured Outputs API**, which uses JSON Schema enforcement via function calling to guarantee 100% structural compliance at generation time.

### Enforcement Levels Comparison

| Mechanism | Enforcement Type | Compliance Rate | Retry Cost |
|-----------|-----------------|-----------------|------------|
| **CrewAI `output_pydantic`** | Post-validation + retry | ~85-95% on first attempt (depends on LLM) | Each retry = full LLM call (~$0.01-0.10) |
| **OpenAI Structured Outputs API** | Pre-enforcement (JSON Schema in function calling) | ~99.9% | 0 retries needed |
| **CrewAI `output_pydantic` + OpenAI Structured Outputs** | Pre-enforcement + post-validation | ~99.9% | Near-zero retries |
| **CrewAI `guardrail` functions** | Post-validation + retry with feedback | Variable (depends on guardrail quality) | Each retry = full LLM call + guardrail execution |
| **Pure Markdown template** | No enforcement | ~80-85% | Manual review needed |

### How Many Retries Are Typically Needed?

Based on community reports and the SDDP technical research findings:

| Output Type | First-Attempt Success Rate | Avg Retries Needed | Total LLM Calls |
|-------------|--------------------------|-------------------|-----------------|
| Simple Pydantic (2-3 fields, basic types) | ~90-95% | 0-1 | 1-2 |
| Complex Pydantic (5+ fields, nested objects) | ~75-85% | 1-2 | 2-3 |
| Markdown template compliance | ~80-85% | 1-3 (if using guardrail) | 2-4 |
| OpenAI Structured Outputs | ~99.9% | 0 | 1 |

### Recommendation for SDDP

SDDP's design documents (delta-spec, delta-design, 对抗记录, etc.) have complex nested structures. The recommended approach from the existing research findings:

1. **Define Pydantic models** for each SDDP document type
2. **Use `output_pydantic`** on all Tasks
3. **Use OpenAI models with Structured Outputs** as the primary LLM (guarantees ~99.9% compliance)
4. **Add `guardrails`** for domain-specific validation (e.g., "所有文件路径必须引用代码库实际文件")
5. **Set `guardrail_max_retries=3`** as safety net
6. **Render validated Pydantic → Markdown** for human readability

Example:

```python
from pydantic import BaseModel, Field
from typing import List

class CriticismPoint(BaseModel):
    id: str = Field(description="质疑ID，格式Q-NNN")
    dimension: str = Field(description="质疑维度：安全性/性能/可维护性/边界情况/依赖兼容性")
    content: str = Field(description="质疑内容描述")
    severity: str = Field(description="严重程度：高/中/低")
    evidence_source: str = Field(description="证据来源：实证报告#X / 代码引用")
    status: str = Field(default="unresolved", description="状态：unresolved/resolved/dismissed")

class AdversarialRecord(BaseModel):
    round_number: int
    criticisms: List[CriticismPoint]
    architect_responses: List[str]
    arbitration_results: List[str]
    converged: bool

class ArchitectAgentOutput(BaseModel):
    delta_spec: str = Field(description="变更规格，包含变更范围、接口契约、影响面、约束条件")
    delta_design: str = Field(description="变更设计，包含架构决策、数据流、关键算法、模块划分")

task = Task(
    description="基于架构研究报告和proposal，产出delta-spec和delta-design",
    expected_output="完整的delta-spec和delta-design文档",
    agent=architect_agent,
    output_pydantic=ArchitectAgentOutput,
    guardrails=[
        "所有文件路径必须引用代码库实际存在的文件",
        "所有接口名必须与代码库实际一致，不得虚构",
    ],
    guardrail_max_retries=3,
)
```

---

## 8. SDDP Phase 1 Adversarial Mechanism: CrewAI Implementation Walkthrough

### Implementation Steps

#### Step 1: Define State Model (~30 min)

```python
from pydantic import BaseModel, Field
from typing import List, Optional

class CriticismPoint(BaseModel):
    id: str
    dimension: str  # 安全性/性能/可维护性/边界情况/依赖兼容性
    content: str
    severity: str   # 高/中/低
    evidence_ref: Optional[str] = None
    architect_response: Optional[str] = None
    arbitrator_decision: Optional[str] = None  # 采纳/驳回
    decision_basis: Optional[str] = None
    status: str = "unresolved"  # unresolved/resolved/dismissed

class Phase1State(BaseModel):
    id: str = ""
    proposal: str = ""
    pcm: Optional[str] = None
    architecture_research: Optional[str] = None
    current_delta_spec: Optional[str] = None
    current_delta_design: Optional[str] = None
    criticism_points: List[CriticismPoint] = []
    evidence_reports: List[str] = []
    round_count: int = 0
    max_rounds: int = 5
    converged: bool = False
    feasibility_confirmed: bool = False
    errors: List[str] = []
```

#### Step 2: Define Agents (~1 hour)

```python
from crewai import Agent, LLM

requirements_officer = Agent(
    role="需求官",
    goal="解析用户原始需求，产出结构化proposal和上下文概览，判定流程路径",
    backstory="你是需求分析专家，必须结构化解析需求、向代码资产管理员查询代码库上下文、判定全流程/快速通道/拒绝。每项判定必须基于代码资产管理员查询结果，不得凭直觉。",
    llm=LLM(model="openai/gpt-4o"),
)

code_asset_admin = Agent(
    role="代码资产管理员",
    goal="维护代码知识图，作为唯一权威代码知识来源响应其他角色查询",
    backstory="你是代码资产守护者，维护GitNexus/Graphify知识图。其他角色查询代码结构知识必须通过你。每项答复必须标注数据来源（知识图/补充扫描）。不得做设计决策。",
    llm=LLM(model="openai/gpt-4o"),
)

architect = Agent(
    role="架构师",
    goal="基于代码库研究和对抗反馈，产出经得起检验的delta-spec和delta-design",
    backstory="你是经验丰富的架构师，必须遵循研究方法论：咨询代码资产管理员→补充扫描→依赖追踪→现状记录→约束提取→PCM架构决策引用。你的每项决策必须标注理由和依据来源。修改范围须先咨询代码资产管理员确认影响面和隐藏依赖方。",
    llm=LLM(model="openai/gpt-4o"),
)

# SafeAgent wrapper (bug #6380 mitigation: timeout+retry)
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

class SafeAgent:
    TIMEOUT = 120  # seconds
    MAX_RETRIES = 3
    
    def __init__(self, agent: Agent):
        self.agent = agent
    
    @retry(stop=stop_after_attempt(MAX_RETRIES), wait=wait_exponential(min=10, max=60),
           retry=retry_if_exception_type((TimeoutError, Exception)))
    async def kickoff_async(self, inputs: dict) -> any:
        import asyncio
        return await asyncio.wait_for(self.agent.kickoff_async(inputs=inputs), timeout=self.TIMEOUT)
    
    @retry(stop=stop_after_attempt(MAX_RETRIES), wait=wait_exponential(min=10, max=60),
           retry=retry_if_exception_type((TimeoutError, Exception)))
    def kickoff(self, inputs: dict) -> any:
        return self.agent.kickoff(inputs=inputs)

    safe_architect = SafeAgent(architect)
    safe_requirements_officer = SafeAgent(requirements_officer)
    safe_code_asset_admin = SafeAgent(code_asset_admin)
    safe_critic_security = SafeAgent(critic_security)
    safe_critic_performance = SafeAgent(critic_performance)
    safe_critic_maintainability = SafeAgent(Agent(role="挑评师-可维护性维度", ...))
    safe_empiricist = SafeAgent(empiricist)
    safe_orchestrator = SafeAgent(orchestrator_arbitrator)

critic_security = Agent(
    role="挑评师-安全维度",
    goal="从安全性维度质疑架构师方案，必须有据质疑",
    backstory="你是安全专家，专注于识别安全隐患、权限漏洞、数据泄露风险。你的每条质疑必须附带代码库风险点引用或实证师验证报告。只质疑不提案。",
    llm=LLM(model="openai/gpt-4o"),
)

critic_performance = Agent(
    role="挑评师-性能维度",
    goal="从性能维度质疑架构师方案，必须有据质疑",
    backstory="你是性能专家，专注于识别性能瓶颈、资源浪费、并发风险。你的质疑必须附带量化数据或实证师基准测试报告。",
    llm=LLM(model="openai/gpt-4o"),
)

empiricist = Agent(
    role="实证师",
    goal="为挑评师质疑提供证据支撑：快速原型验证、边界测试、依赖分析",
    backstory="你是验证专家，根据挑评师质疑点执行实证验证。你使用PCM验证方案域中的工具执行验证。",
    llm=LLM(model="openai/gpt-4o"),
)

orchestrator_arbitrator = Agent(
    role="调度官",
    goal="裁决对抗中未收敛的质疑点，推进流程",
    backstory="你是唯一决策点。裁决必须引用实证报告或代码库证据。高严重程度质疑不得单方面驳回。",
    llm=LLM(model="openai/gpt-4o"),
)
```

#### Step 3: Define Flow with Adversarial Loop (~2-3 hours)

```python
import asyncio
import json
from crewai.flow.flow import Flow, listen, router, start, or_
from crewai.flow.human_feedback import human_feedback
from crewai.flow.persistence import persist

@persist
class Phase1AdversarialFlow(Flow[Phase1State]):
    architect = safe_architect
    critic_security = safe_critic_security
    critic_performance = safe_critic_performance
    empiricist = safe_empiricist
    orchestrator = safe_orchestrator

    @start()
    def init_phase1(self):
        if not self.state.feasibility_confirmed:
            self.state.feasibility_confirmed = True
        return "start_research"

    @listen("start_research")
    def architecture_research(self):
        result = self.architect.kickoff(
            inputs={
                "proposal": self.state.proposal,
                "pcm": self.state.pcm or "无PCM，使用SDDP默认方案",
                "task": "咨询代码资产管理员→补充扫描→依赖追踪→现状记录→约束提取→PCM架构决策引用，产出架构研究报告",
            }
        )
        self.state.architecture_research = result.raw
        return "research_complete"

    @listen("research_complete")
    def architect_produce_design(self):
        result = self.architect.kickoff(
            inputs={
                "proposal": self.state.proposal,
                "research": self.state.architecture_research,
                "existing_design": self.state.current_delta_spec or "",
                "criticism_feedback": str(self.state.criticism_points) if self.state.criticism_points else "首轮设计，无前轮质疑",
                "task": "产出delta-spec和delta-design",
            }
        )
        self.state.current_delta_spec = result.raw.split("---DELTA-SPEC---")[0] if "---DELTA-SPEC---" in result.raw else result.raw
        self.state.current_delta_design = result.raw.split("---DELTA-DESIGN---")[1] if "---DELTA-DESIGN---" in result.raw else result.raw
        return "design_produced"

    @listen("design_produced")
    async def critics_challenge(self):
        selected_critics = self._select_critics()
        results = await asyncio.gather(*[
            critic.kickoff_async(
                inputs={
                    "design": self.state.current_delta_design,
                    "proposal": self.state.proposal,
                    "task": f"从{critic.role.split('-')[1]}维度质疑方案",
                }
            )
            for critic in selected_critics
        ])
        criticisms = []
        for result in results:
            points = self._parse_criticisms(result.raw)
            criticisms.extend(points)
        self.state.criticism_points = criticisms
        return "criticism_produced"

    @listen("criticism_produced")
    def empiricist_verify(self):
        for point in self.state.criticism_points:
            if point.severity in ["高", "中"]:
                result = self.empiricist.kickoff(
                    inputs={
                        "criticism_point": point.content,
                        "dimension": point.dimension,
                        "design": self.state.current_delta_design,
                        "task": f"为质疑{point.id}提供实证验证",
                    }
                )
                point.evidence_ref = result.raw
                self.state.evidence_reports.append(result.raw)
        return "evidence_produced"

    @router(evidence_produced)
    def arbitrator_decide(self):
        self.state.round_count += 1  # Increment only at router entry
        # Convergence check per SDDP rules
        if self.state.round_count >= self.state.max_rounds:
            return "force_converged"

        high_unresolved = [
            p for p in self.state.criticism_points
            if p.severity == "高" and p.status == "unresolved"
        ]
        if high_unresolved:
            # High severity must be addressed
            return "revise"

        all_resolved = all(
            p.status in ["resolved", "dismissed"]
            for p in self.state.criticism_points
        )
        if all_resolved:
            return "converged"

        # Some medium/low unresolved — arbitrator can dismiss with evidence
        result = self.orchestrator.kickoff(
            inputs={
                "criticism_points": str(self.state.criticism_points),
                "evidence_reports": str(self.state.evidence_reports),
                "task": "对未收敛质疑点做出采纳/驳回裁决，裁决必须引用实证报告或代码库证据",
            }
        )
        decisions = self._parse_arbitration(result.raw)
        for point_id, decision in decisions.items():
            for point in self.state.criticism_points:
                if point.id == point_id:
                    point.arbitrator_decision = decision["decision"]
                    point.decision_basis = decision["basis"]
                    if decision["decision"] == "采纳":
                        point.status = "unresolved"  # Must be addressed
                    elif decision["decision"] == "驳回":
                        point.status = "dismissed"

        remaining_unresolved = [
            p for p in self.state.criticism_points if p.status == "unresolved"
        ]
        if remaining_unresolved:
            return "revise"
        return "converged"

    @listen("revise")
    def trigger_revision(self):
        return "revision_needed"

    # Self-loop: architect only revises on revision_needed (not on initial design_produced)
    @listen("revision_needed")
    def architect_revise_design(self):
        # Architect revises based on arbitration results
        result = self.architect.kickoff(
            inputs={
                "proposal": self.state.proposal,
                "research": self.state.architecture_research,
                "current_design": self.state.current_delta_design,
                "criticism_points": str(self.state.criticism_points),
                "arbitration_results": str([
                    {"id": p.id, "decision": p.arbitrator_decision, "basis": p.decision_basis}
                    for p in self.state.criticism_points
                    if p.arbitrator_decision
                ]),
                "task": "根据裁决结果修订delta-spec和delta-design",
            }
        )
        self.state.current_delta_spec = result.raw.split("---DELTA-SPEC---")[0] if "---DELTA-SPEC---" in result.raw else result.raw
        self.state.current_delta_design = result.raw.split("---DELTA-DESIGN---")[1] if "---DELTA-DESIGN---" in result.raw else result.raw
        return "design_revised"

    @listen("converged")
    @human_feedback(
        message="方案已收敛，请确认 delta-spec + delta-design?",
        emit=["approved", "rejected"],
        llm="gpt-4o-mini",
        default_outcome="rejected",
    )
    def user_confirm_design(self):
        return self.state.current_delta_design

    @listen("approved")
    def phase1_complete(self, result):
        self.state.converged = True
        return {"delta_spec": self.state.current_delta_spec, "delta_design": self.state.current_delta_design}

    @listen("rejected")
    @human_feedback(
        message="用户否决方案，请选择: 修订方案(回退对抗) 或 终止流程?",
        emit=["revision_needed", "abort_flow"],
        llm="gpt-4o-mini",
        default_outcome="revision_needed",
    )
    def handle_rejection(self, result):
        return "revision_needed"  # Loop back

    @listen("force_converged")
    @human_feedback(
        message="对抗已达5轮上限，强制提交当前最优方案，用户裁决?",
        emit=["approved", "rejected", "extend"],
        llm="gpt-4o-mini",
        default_outcome="rejected",
    )
    def user_force_converged(self):
        return self.state.current_delta_design

    def _select_critics(self):
        if self.state.round_count <= 1:
            return [self.critic_security, self.critic_performance]
        return [self.critic_security, self.critic_performance, self.critic_maintainability]

    def _parse_criticisms(self, raw_output):
        try:
            data = json.loads(raw_output)
            return [
                CriticismPoint(
                    id=item["id"],
                    content=item["content"],
                    dimension=item["dimension"],
                    severity=item["severity"],
                    status=item.get("status", "unresolved"),
                )
                for item in data.get("criticism_points", [])
            ]
        except (json.JSONDecodeError, KeyError):
            return [CriticismPoint(
                id="fallback-1",
                content=raw_output,
                dimension="未分类",
                severity="中",
                status="unresolved",
            )]

    def _parse_arbitration(self, raw_output):
        try:
            data = json.loads(raw_output)
            return {
                item["id"]: {"decision": item["decision"], "basis": item["basis"]}
                for item in data.get("decisions", [])
            }
        except (json.JSONDecodeError, KeyError):
            return {}
```

#### Step 4: Integrate with Electron Desktop Pet (~3-5 hours)

```python
# backend/server.py
import asyncio
from fastapi import FastAPI, WebSocket
from phase1_flow import Phase1AdversarialFlow, Phase1State
from crewai.flow.human_feedback import HumanFeedbackPending

app = FastAPI()

@app.websocket("/ws/sddp")
async def sddp_ws(ws: WebSocket):
    await ws.accept()
    while True:
        data = await ws.receive_json()
        if data["type"] == "start_phase1":
            flow = Phase1AdversarialFlow()
            result = await asyncio.to_thread(flow.kickoff, inputs={"proposal": data["proposal"]})
            if isinstance(result, HumanFeedbackPending):
                await ws.send_json({
                    "type": "feedback_required",
                    "flow_id": result.context.flow_id,
                    "method": result.context.method_name,
                    "message": result.context.message,
                    "output": str(result.context.method_output),
                })
            else:
                await ws.send_json({"type": "flow_complete", "result": str(result)})
        elif data["type"] == "user_feedback":
            flow = Phase1AdversarialFlow.from_pending(data["flow_id"])
            result = await flow.resume_async(data["feedback"])
            # Continue flow...
```

### Edge Cases

| Edge Case | Risk | Mitigation |
|-----------|------|------------|
| LLM timeout during architect design | Flow freezes (bug #6380) | Wrap in `asyncio.wait_for()` + retry with tenacity |
| Critic produces no valid criticism | No `@listen` trigger fires | Add default "no criticism" path in router |
| Arbitrator LLM produces invalid JSON | Parsing fails, state corrupted | Use `output_pydantic` on arbitrator task |
| All criticisms dismissed but high severity exists | SDDP rule violation (高严重程度不得驳回) | Validate in guardrail: reject arbitrator output that dismisses high-severity without evidence |
| 5 rounds exceeded without convergence | Force converged path | Explicit `max_rounds` check in router |
| `or_()` listener fire-once bug resurfaces | Adversarial loop breaks | Pin CrewAI version where #5972 fix is included |
| Agent instance memory not persisted across rounds | Architect loses context from previous rounds | Inject full criticism history in task inputs |
| Concurrent critic runs produce conflicting evidence | Race condition in state | Use `and_()` to synchronize critic completion before empiricist |

### Realistic Implementation Time Estimate

| Component | Estimated Time | Confidence |
|-----------|---------------|------------|
| Pydantic state + output models | 2-4 hours | High |
| Agent definitions (5 agents) | 2-3 hours | High |
| Flow structure with adversarial loop | 4-8 hours | Medium (depends on #5972 fix stability) |
| Convergence detection logic | 2-4 hours | Medium |
| Parsing helpers (_parse_criticisms, _parse_arbitration) | 3-6 hours | Low (LLM output parsing is fragile) |
| @human_feedback + WebSocket provider | 4-6 hours | Medium |
| Error handling + retry wrapper | 2-3 hours | High |
| Integration testing (end-to-end) | 8-16 hours | Low (many edge cases) |
| **Total Phase 1 implementation** | **25-45 hours** | **Medium confidence** |

**Key risk factors**:
1. LLM output parsing fragility (the `_parse_*` methods) — this is where most bugs will appear
2. CrewAI Flows API stability — pin to a specific version, test thoroughly
3. Async error propagation — must implement safe_llm_call wrapper until bug #6380 is fixed
4. The `or_()` cyclic listener pattern — verify it works with the pinned CrewAI version

**Recommended approach**: Start with a **simplified adversarial flow** (1 critic dimension, 3-round limit) and validate the loop mechanism works before implementing the full 5-round multi-dimension design.

---

## Summary of All Findings

| Question | Finding | Risk Level | SDDP Impact |
|----------|---------|------------|-------------|
| 1. Flows reliability | Moderate — active bugs, rapid API refactoring | **High** | Pin CrewAI version, test thoroughly |
| 2. @human_feedback | Blocking by default; async via custom provider; WebSocket integration possible | **Low** | Use `@human_feedback` on Flow methods, NOT `human_input=True` on Tasks |
| 3. @router loops | Possible with `or_()` self-loop pattern; bug #5972 fixed; convergence must be manual | **Medium** | Implement explicit convergence + max_rounds in router |
| 4. Dynamic scaling | No native scaling; agents can be created in methods but not pooled | **Medium** | Pre-define agents, select subset dynamically |
| 5. Error handling | Async failures silently freeze (bug #6380); @persist enables resume | **High** | Must implement retry/timeout wrapper |
| 6. Electron IPC | WebSocket (FastAPI) is recommended pattern; matches @human_feedback provider | **Low** | FastAPI WebSocket + Electron WebSocket client |
| 7. JSON Schema | output_pydantic is post-validation + retry (~85-95% first attempt); OpenAI Structured Outputs ~99.9% | **Medium** | Use OpenAI Structured Outputs + output_pydantic + guardrails |
| 8. Phase 1 implementation | 25-45 hours; key risks: LLM output parsing, Flows API stability, async errors | **Medium** | Start with simplified 1-dimension 3-round flow first |
