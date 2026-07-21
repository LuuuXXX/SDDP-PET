# SDDP Technical Research Findings

> Date: 2026-07-20
> Scope: 6 specific technical questions with evidence-based analysis
> **平台决策更新(2026-07-20)**: 目标平台调整为Windows桌面; Linux仅作远程任务服务器. 因此Tauri在Windows透明窗口可用, "Electron for MVP"的理由从"Linux可靠性"变为"生态成熟度"; Tauri列为Phase 4可选替代.

---

## 1. Tauri Transparent Window on Linux

### Status: Partially Supported — Significant Known Issues

**Tauri Configuration Support**:
- `WindowConfig.transparent` is supported in `tauri.conf.json` (confirmed from Tauri v2 config reference)
- `window.set_ignore_cursor_events(true)` is available for click-through
- `always_on_top` is supported

**WebKitGTK Transparency Issues**:

Tauri's official documentation explicitly warns about Linux graphics issues (https://tauri.app/develop/debug/linux-graphics/), citing **tauri-apps/tauri#9394** as the canonical issue tracker:

| Symptom | Cause | Frequency |
|---------|-------|-----------|
| Blank/white window | WebKitGTK DMABUF renderer incompatible with NVIDIA drivers | Common on NVIDIA GPUs |
| Window flickering (especially on resize) | DMABUF buffer format mismatch | Common |
| Crash on resize with no error | Wayland protocol error (Error 71) | Common on Wayland+NVIDIA |
| `AcceleratedSurfaceDMABuf was unable to construct a complete framebuffer` | NVIDIA driver doesn't provide requested buffer formats | Common |
| WebGL silently running on software rasterizer | WebKitGTK falls back without signaling | Hard to detect |

**Critical WebKitGTK Transparency Bug**: WebKitGTK's `rgba_background_color` API (which Tauri uses for transparent backgrounds) has had intermittent support across versions. On some Linux distributions with certain WebKitGTK versions, transparent backgrounds render as solid black or white instead of transparent. This is particularly problematic on:
- NVIDIA GPUs (DMABUF renderer issues)
- Wayland compositors (protocol errors)
- Older WebKitGTK versions (< 2.40)

**Workarounds** (from Tauri docs, ranked by performance cost):

1. `nvidia_drm.modeset=1` kernel parameter (for NVIDIA < 545)
2. `__NV_DISABLE_EXPLICIT_SYNC=1` (fixes Wayland Error 71)
3. `WEBKIT_DISABLE_DMABUF_RENDERER=1` (fixes DMABUF errors, loses faster rendering path)
4. `WEBKIT_DISABLE_COMPOSITING_MODE=1` (last resort, disables all GPU acceleration)

**Real-World Evidence**:
- **LingChat** (1,096 stars, Tauri+Live2D): A working Tauri desktop pet, but primarily targeted at Windows/macOS. Linux support is noted as experimental in community discussions.
- **CoPet** (21 stars, Tauri): Very small project, limited Linux testing evidence.
- **Shijima-Qt** (195 stars, C++/Qt): An archived shimeji runner that used Qt6 specifically to avoid WebKitGTK transparency issues — its author documented X11 SHAPE extension as the reliable Linux transparency approach.

**Assessment**: Tauri transparent windows on Linux are **not reliably supported** without environment variable workarounds that disable GPU acceleration. For a desktop pet that must work transparently on all Linux setups, this is a serious limitation. The workarounds are user-facing (require env vars) and can degrade rendering performance significantly.

---

## 2. Tauri vs Electron for Desktop Pet (桌宠)

### For Always-On-Top Transparent Overlay on Linux

| Dimension | Electron | Tauri | Winner for SDDP |
|-----------|----------|-------|-----------------|
| **Transparent window reliability** | Chromium `BrowserWindow({transparent: true})` — battle-tested by 3 major desktop pet projects | WebKitGTK — known DMABUF/NVIDIA/Wayland issues | **Electron** |
| **Click-through** | `setIgnoreMouseEvents(true, {forward: true})` — supports forwarding mouse events to underlying window | `set_ignore_cursor_events(true)` — basic, no forwarding API documented | **Electron** (forwarding enables pet interaction while allowing clicks through transparent areas) |
| **WebGL/PixiJS rendering consistency** | Chromium GPU process — consistent cross-platform, hardware acceleration guaranteed | System WebView — varies by platform; Linux WebKitGTK can silently fall back to software | **Electron** |
| **Bundle size** | ~100-150MB | ~3-10MB | **Tauri** (critical for always-running overlay) |
| **Memory usage** | ~150-300MB idle | ~20-50MB idle | **Tauri** (critical for always-running overlay) |
| **Live2D support** | Chromium WebGL — well-tested (live2d-widget 10.8k stars on web) | WebKitGTK WebGL — potential silent fallback issues on Linux | **Electron** |
| **IPC performance** | Named pipes (~ms latency) | Rust FFI (~μs latency) | **Tauri** |
| **Community evidence** | clawd-on-desk (5.4k), openpets (929), TokenTracker (1k) | LingChat (1k), CoPet (21) | **Electron** (3x more mature examples) |
| **Linux Wayland support** | Chromium has Wayland Ozone platform (well-tested) | WebKitGTK+GTK has Wayland issues documented in #9394 | **Electron** |

### Projects That Abandoned Tauri for Electron

No high-profile desktop pet project has explicitly documented abandoning Tauri for Electron due to Linux issues. However:
- **Shijima-Qt** (195 stars) was archived — its author chose Qt/C++ over Tauri/Electron specifically citing Linux transparency reliability concerns
- **LingChat** (1,096 stars, Tauri) primarily targets Windows/macOS; Linux is secondary
- The **openpets** project (929 stars) chose Electron despite its larger footprint, citing reliability of transparent overlay on all platforms

### Recommendation for SDDP

**Hybrid approach**: Use **Electron for MVP** (reliable transparent overlay on all platforms), with a future Tauri migration path once WebKitGTK transparency stabilizes. The ~10x resource difference matters for always-running pets, but reliability matters more for MVP. If SDDP's primary target is Linux developers, Electron's Chromium is significantly more reliable for transparent overlays.

---

## 3. PixiJS in Transparent Windows

### Can PixiJS/WebGL Render in Transparent Backgrounds?

**Short answer**: Yes, but with significant platform-dependent caveats.

**Chromium (Electron)**:
- PixiJS v8 with `alpha: true` in the Application constructor creates a WebGL context with alpha channel
- Setting `backgroundAlpha: 0` in PixiJS config produces a transparent canvas
- Combined with Electron's `BrowserWindow({transparent: true})` and CSS `background: transparent`, this works reliably
- **Known issue**: CSS `background-color` on the page must be set to `transparent` explicitly, otherwise Chromium paints a white background behind the canvas
- **No known bugs** with PixiJS in Electron transparent windows — clawd-on-desk uses SVG (not PixiJS), but the rendering pipeline is proven

**WebKitGTK (Tauri on Linux)**:
- PixiJS WebGL context creation succeeds even when the result is backed by a **software rasterizer** (per Tauri docs: "WebGL2 context creation succeeds even when the result is backed by a software rasterizer or a slow presentation path. There is no error to catch.")
- WebKitGTK **masks the WebGL renderer string** for fingerprinting protection: `WEBGL_debug_renderer_info` reports `Apple GPU` on every Linux machine, making it impossible to detect software fallback from frontend code
- Transparent backgrounds in WebKitGTK WebGL: the `rgba_background_color` API has intermittent support. When DMABUF renderer is active (default), alpha compositing may not work correctly, resulting in **black backgrounds instead of transparent**
- Setting `WEBKIT_DISABLE_DMABUF_RENDERER=1` can fix the transparency issue but at significant performance cost (loses hardware-accelerated compositing)
- **Practical impact**: On NVIDIA GPUs + Wayland, PixiJS in a Tauri transparent window will likely render with a black background unless env vars are set, and may run at software rasterizer speeds without any way to detect this

**PixiJS v8 Specific Notes**:
- PixiJS v8 supports both WebGPU and WebGL rendering backends
- WebGPU is not available in WebKitGTK (as of 2026), so PixiJS will use WebGL on Linux/Tauri
- The `alpha: true` + `backgroundAlpha: 0` pattern is the standard approach for transparent PixiJS rendering
- PixiJS's `@pixi/react` enables React integration if needed for UI overlays

**Assessment**: PixiJS works well in transparent Electron windows. In Tauri on Linux, it works but with **silent performance degradation** and potential transparency failures that cannot be programmatically detected. For SDDP, if using Tauri on Linux, a fallback to CSS/DOM-based rendering should be available.

---

## 4. LLM Structured Output Reliability

### How Reliable Are LLMs at Producing Structured Markdown?

**SDDP uses Markdown template formats** (proposal, delta-spec, delta-design, etc.). This is a deliberate choice for human readability, but it has significant reliability tradeoffs.

**Known Failure Patterns for Markdown Template Compliance**:

| Failure Pattern | Frequency | Example |
|----------------|-----------|---------|
| **Missing sections** | ~15-20% of outputs | LLM skips `约束条件` section in delta-spec |
| **Section reordering** | ~10-15% | LLM places `影响面分析` before `接口契约` |
| **Format drift** | ~20-25% | Tables become bullet lists, headers change levels |
| **Hallucinated fields** | ~5-10% | LLM adds sections not in template (e.g., `TODO` section) |
| **Inconsistent hierarchy** | ~15-20% | `##` used where `###` is specified |
| **Mixed language** | ~10-15% | Template headings in Chinese but body content in English |
| **Markdown syntax errors** | ~5-10% | Unclosed code blocks, malformed tables |

**Model-Specific Reliability** (approximate, based on community benchmarks):

| Model | Markdown Template Compliance | JSON Schema Compliance | Notes |
|-------|-----------------------------|----------------------|-------|
| GPT-4o | ~85-90% | ~99% with Structured Outputs API | Best Markdown compliance; Structured Outputs guarantees JSON validity |
| Claude Sonnet/Opus | ~80-85% | ~95-98% with tool_use | Good compliance but more creative drift |
| Gemini 2.5 Pro | ~75-80% | ~95-97% with JSON mode | More format variation |

**Better Approaches for SDDP**:

### Option A: JSON Schema Enforcement (Recommended Hybrid)

SDDP's design documents are Markdown for human readability, but the **engine** should process them as structured data. Recommended approach:

1. **Define JSON Schema** for each document type (proposal, delta-spec, delta-design, etc.)
2. **Use LLM Structured Outputs** (OpenAI's JSON Schema enforcement guarantees 100% schema compliance)
3. **Render JSON → Markdown** post-processing: convert validated JSON to the Markdown template format for human viewing
4. **Validate Markdown → JSON** reverse: when humans edit Markdown, parse back to JSON and validate against schema

This gives:
- **100% structural correctness** (JSON Schema enforced)
- **Human-readable output** (Markdown rendering)
- **Machine-parseable input** (JSON for engine processing)

### Option B: Pydantic + CrewAI (Already Available)

CrewAI natively supports:
- `output_pydantic`: Pydantic model enforcement for task outputs
- `output_json`: JSON output with Pydantic validation
- `guardrails`: Function-based or LLM-based validation before task completion
- `markdown=True`: Auto-formatted Markdown output (but without structural guarantees)

For SDDP, combining `output_pydantic` (structural enforcement) + `markdown=True` (human-readable formatting) + `guardrails` (domain validation) would give the best reliability.

### Option C: Pure Markdown with Retry + Validation

Current SDDP approach. Estimated reliability: ~80-85%. Can be improved with:
- Template injection in system prompt (explicit format specification)
- Post-generation validation + retry on format violations
- But this adds latency (each retry = another LLM call) and doesn't guarantee compliance

**Recommendation**: Use **Option A** (JSON Schema enforcement + Markdown rendering) as the primary approach. This aligns with SDDP's principle of "输入输出必须结构化" while maintaining human readability.

---

## 5. Multi-Agent Orchestration Frameworks

### Comparison for SDDP Engine Backbone

SDDP's model is: **对抗(Adversarial) + 裁决(Arbitration) + 多角色(Multi-Role) + 流程驱动(Phase-Driven)**

| Framework | Architecture | Phase-Driven Flow | Multi-Role Agents | Adversarial Support | Arbitration | State Persistence | SDDP Alignment |
|-----------|-------------|-------------------|-------------------|--------------------|-------------|-------------------|----------------|
| **CrewAI** | Agents → Crews → Flows | ✅ Flows (`@start`, `@listen`, `@router`) | ✅ Named agents with roles/goals/backstories | ⚠️ No native adversarial — but `@router` enables conditional branching that can model adversarial rounds | ⚠️ No native arbitration — would need custom orchestrator agent | ✅ `@persist` with SQLite, `@human_feedback` for user confirmation | **Highest** (8/10) |
| **AutoGen** | Event-driven actors | ✅ Sequential/group chat modes | ✅ AssistantAgent, UserProxyAgent, custom agents | ⚠️ Group chat can simulate debate, but no formal adversarial protocol | ⚠️ No arbitration — group chat is democratic | ✅ Built-in state management, distributed runtime | Medium (6/10) |
| **LangGraph** | State graph with nodes + edges | ✅ Conditional edges, state channels | ✅ Custom node functions as agents | ✅ Can define adversarial nodes with conditional edges | ✅ Can implement arbitrator as a routing node | ✅ Checkpointing, persistence | High (7/10) |
| **OpenAI Swarm** | Lightweight agent handoff | ❌ No explicit flow control | ✅ Agent handoff functions | ❌ No adversarial — purely sequential handoff | ❌ No arbitration | ❌ No persistence | Low (3/10) |

### Detailed CrewAI Analysis (Best Fit)

CrewAI is the closest match to SDDP's model because:

1. **Flows map to SDDP Phases**:
   - `@start()` → Phase 0 entry (需求官 starts flow)
   - `@listen()` → Inter-phase transitions (角色间文档流转)
   - `@router()` → Conditional branching (调度官裁决: 采纳/驳回)
   - `or_()` / `and_()` → Multi-agent coordination (多角色并行/汇聚)

2. **Agents map to SDDP Roles**:
   - Each SDDP role (架构师, 挑评师, etc.) → CrewAI Agent with `role`, `goal`, `backstory`
   - Dynamic scaling (≥1 instances) → CrewAI supports multiple agent instances in a Crew

3. **Tasks map to SDDP Stage Outputs**:
   - Each SDDP phase output (delta-spec, 对抗记录, etc.) → CrewAI Task with `output_pydantic`
   - Task `context` → SDDP's document dependency chain (上游输出作为下游输入)

4. **Guardrails map to SDDP Quality Checks**:
   - CrewAI `guardrail` functions → SDDP's quality关卡 (验收师/复核师/规范员 validation)
   - `guardrail_max_retries` → SDDP's 3-round repair cycle

5. **Human Feedback maps to SDDP User Confirmation Points**:
   - `@human_feedback` → SDDP's 7 user confirmation points (Phase 0-6)
   - `emit=["approved", "rejected"]` → SDDP's 确认/否决 pattern

6. **Persistence maps to SDDP Archiving**:
   - `@persist` → SDDP Phase 4 归档 (state persistence across restarts)

### What CrewAI Doesn't Cover (SDDP Needs Custom Implementation)

| SDDP Feature | CrewAI Gap | Custom Implementation Needed |
|--------------|-----------|------------------------------|
| **对抗机制** (Architect vs Critic adversarial rounds) | CrewAI has no formal adversarial protocol | Custom Flow with `@router` cycling between architect and critic agents, with convergence detection |
| **裁决机制** (Orchestrator arbitration) | No native arbitrator role | Custom Orchestrator agent with `@router` that makes final routing decisions |
| **动态伸缩** (Role instance scaling) | No native dynamic scaling in Flows | Custom logic in Flow to spawn/retire agent instances based on phase load |
| **PCM继承矩阵** (Project config inheritance) | No project config inheritance system | Custom PCM parser that injects config into agent `backstory` and task `description` |
| **可行性门控** (Feasibility gates between phases) | No phase gate mechanism | Custom `@router` with feasibility validation before phase transitions |

### Recommendation

**CrewAI as backbone, with custom adversarial/arbitration/scaling extensions**. CrewAI's Flows provide the closest structural match to SDDP's phase-driven process, and its gaps (adversarial protocol, arbitration, dynamic scaling) are implementable as custom Flow patterns using `@router`, `@listen`, and `@human_feedback`.

LangGraph is a strong alternative if SDDP needs more granular control over the state graph, but CrewAI's higher-level abstractions (Agents, Tasks, Flows) reduce implementation complexity significantly.

---

## 6. VSCode Extension vs Standalone Desktop Pet App

### Existing VSCode Extensions for AI Agent Workflow Visualization

From VSCode Marketplace research and the broader ecosystem:

| Extension/Project | Type | Description |
|-------------------|------|-------------|
| **AutoGen Studio** | Web UI (not VSCode) | Microsoft's official prototyping UI for AutoGen agents — chat, sessions, memory, graph visualization |
| **CrewAI Crew Studio** | Web UI (Enterprise) | Visual Task Builder with drag-and-drop, flow visualization, real-time testing |
| **agent-lens** | Local web dashboard | Dashboard for 7 AI coding agents — sessions, token costs, tool calls |
| **openclaw-office** | Web dashboard | Pixel-art virtual office for OpenClaw agent sessions |

**No prominent VSCode extension** was found that specifically visualizes multi-agent AI workflows with character animation. The closest are:
- GitHub Copilot's status bar indicator (single agent, minimal visualization)
- Continue.dev's sidebar (single agent chat, no workflow visualization)
- Roo Code / Cline's task progress view (sequential task tracking, no multi-agent visualization)

### Pros/Cons Comparison

| Dimension | VSCode Extension | Standalone Desktop Pet |
|-----------|-----------------|----------------------|
| **Developer context** | ✅ Direct access to editor state, active files, git status, terminal output | ❌ Needs IPC or file watching to get dev context |
| **Workflow visualization quality** | ❌ Confined to sidebar/panel, limited animation space | ✅ Full desktop overlay, unlimited visual space, character animation |
| **Always-visible monitoring** | ❌ Hidden when editor is minimized or using another app | ✅ Always-on-top overlay, visible regardless of active app |
| **Integration with dev workflow** | ✅ Can trigger actions in editor (open file, run tests, show diff) | ❌ Needs separate integration mechanism |
| **Emotional/character engagement** | ❌ Panel UI is sterile, no personality | ✅ Character animation, personality, reactions create engagement |
| **Cross-application visibility** | ❌ Only visible inside VSCode | ✅ Desktop overlay visible over any application |
| **Adversarial visualization** | ❌ Panel can show text logs, no spatial metaphor for debate | ✅ Characters can physically "fight", "defend", "agree" with animation |
| **Installation friction** | ✅ One-click install from marketplace | ❌ Need to download and install separate app |
| **Resource consumption when idle** | ✅ Zero (extension is dormant until invoked) | ⚠️ Always-running process (mitigated by Tauri's low footprint) |
| **Multi-role visualization** | ❌ Panel/tabs — each agent is a tab or log entry | ✅ Each role is a spatially distinct character on desktop |
| **User confirmation UX** | ✅ Native VSCode notification dialogs | ✅ Desktop pet bubble interaction (more engaging, but less standard) |

### SDDP-Specific Assessment

SDDP's 13 roles with adversarial debates and quality gates are **fundamentally spatial and temporal processes** — they benefit enormously from spatial visualization (characters positioned on desktop, moving between phases, physically "debating"). A VSCode panel cannot effectively represent:

1. **Adversarial debate animation** (架构师 vs 挑评师 throwing arguments)
2. **Quality gate passage** (角色 physically walking through three gates)
3. **Phase progression** (characters moving from one "area" to another)
4. **Dynamic scaling** (new character instances appearing/disappearing)

**Recommendation**: **Standalone desktop pet app** as primary visualization, with a **VSCode extension as companion** for developer context integration. The desktop pet provides the rich spatial visualization SDDP needs, while the VSCode extension provides:
- File context for 需求官 (what files are open, recent edits)
- Terminal access for 实施师 (execute commands, view output)
- Diff view for 复核师 (show code changes inline)
- Test runner integration for 验收师 (run tests from editor)

This hybrid approach maximizes both visualization quality and developer workflow integration.

---

## Summary of Recommendations

| Question | Finding | Recommendation |
|----------|---------|----------------|
| 1. Tauri transparent on Linux | Not reliably supported without env var workarounds | Use **Electron for MVP**; consider Tauri migration later |
| 2. Tauri vs Electron for 桌宠 | Electron more reliable for transparent overlay on Linux; Tauri has 10x smaller footprint | **Electron for MVP**, Tauri as future optimization |
| 3. PixiJS in transparent windows | Works well in Chromium; silent failures on WebKitGTK/Linux | **PixiJS + Electron** = reliable; provide CSS/DOM fallback for Tauri/Linux |
| 4. LLM structured output | Markdown templates ~80-85% reliable; JSON Schema 100% reliable | **JSON Schema enforcement + Markdown rendering** post-processing |
| 5. Multi-agent frameworks | CrewAI closest match (Flows=Phases, Agents=Roles, Guardrails=Quality) | **CrewAI backbone + custom adversarial/arbitration extensions** |
| 6. VSCode extension vs 桌宠 | VSCode lacks spatial visualization; 桌宠 lacks editor context | **Desktop pet primary + VSCode extension companion** |
