## Why

Dev-Phase 1 shipped a working SDDP engine behind a desktop-pet UI, but the flow is still **linear and non-adversarial**: the architect produces a design, the executor implements it, and there is no agent that challenges either artifact. The defining premise of SDDP — that software quality emerges from **multi-role confrontation** (挑评师/实证师 rebutting the architect until convergence) — is therefore still unproven in product. Dev-Phase 2 closes exactly that gap: it implements the adversarial Phase-1 Flow (per `crewai-technical-research` §8), proves convergence is mechanically decidable, and makes the debate visible on the pet.

Per `openspec/specs/development-roadmap/phases.md`, DP2 is the third stop on the critical path (5–7 weeks) and the prerequisite for DP3 (quality-gate + execution). The DP1 Golden Demo (linear, ~$0.009/flow) does NOT exercise confrontation; DP2's Go threshold is a full 5-round confrontation completing under the pet at **cost ≤ $15**.

## What Changes

### New engine capabilities
- **Adversarial Flow** (D2-1) — the Phase-1 Flow from `crewai-technical-research` §8 as a real implementation (NOT a skeleton): architect proposes → critic (挑评师) + empiricist (实证师) raise findings across 3 severity dimensions → orchestrator (调度官) routes revisions. CrewAI `or_()` loop retrigger is the load-bearing primitive; SafeAgent wraps every role kickoff (DP0 #6380 mitigation still mandatory).
- **Convergence detection** (D2-2) — mechanical severity-rule mapping (critical/major/minor → required-resolved counts) + `max_rounds` forced convergence + escalate-to-user when the loop cannot self-resolve. This is the make-or-break acceptance item: if convergence is undecidable (LLM self-reference paradox), DP2 No-Go-B triggers and the design reverts to external arbitration.

### New UI capabilities
- **Multi-role pet** (D2-3) — 4 roles (architect/critic/empiricist/orchestrator) each with a distinct sprite + 8-state animation machine (extends DP1's 4-state). The confrontation renders as a visible "debate" (role bubbles, rebuttal arrows — per `01-review` G8). DP1's single-circle pet becomes role-aware.
- **Concurrent flows** (D2-4) — 2 flows run in parallel with `@persist` data isolation keyed by `flow_id` namespace; orchestrator gains multi-proposal management. (Foundation only in DP2; full scheduling is DP3.)

### Non-goals (explicitly deferred)
- ❌ Sandboxed code execution / file-write proxy (Dev-Phase 3a)
- ❌ Quality-gate Flow / 规范员/修缮师/复核师 roles (Dev-Phase 3b — DP2 ships only the 4 confrontation roles)
- ❌ Live2D rendering + adversarial replay UI (Dev-Phase 4, optional)
- ❌ Tier-C offline / Ollama (Dev-Phase 5)

## Capabilities

### New Capabilities
- `confrontation-flow`: adversarial Phase-1 Flow — architect/critic/empiricist/orchestrator; CrewAI `or_()` loop; 3-dimension × 5-round ceiling; integrates with DP1's `WebSocketHumanFeedbackAdapter` (escalate-to-user reuses the existing `feedback_required` Push)
- `convergence-detection`: severity-rule engine + `max_rounds` forced stop + escalate path; the single most acceptance-critical component (Go/No-Go-B depends on it)
- `multi-role-pet`: 4-role sprite system + 8-state machine; PixiJS role-switching; debate visualization (window1) fed by a new Push sub-stream of `agent_state_change` carrying `role` + `round`
- `concurrent-flows`: `flow_id`-namespaced `@persist` isolation; 2-flow parallel smoke

### Modified Capabilities
- `websocket-ipc` (DP1, backward-compatible additive): the existing `agent_state_change` Push gains optional `role` + `round` + `finding` fields so the pet can render the debate WITHOUT breaking DP1 consumers (fields are optional; DP1 linear flow leaves them absent). A new optional Push `convergence_state` reports round/severity-resolved counts.

## Impact

### Key risks (to be elaborated in design.md)
- **No-Go-A**: CrewAI `or_()` loop unstable under production concurrency/retries → revert adaptation layer or evaluate LangGraph. Mitigation: the SafeAgent wrapper + a mock-adapter adversarial smoke (1-dim/3-round) gates the full 3-dim/5-round run.
- **No-Go-B**: convergence undecidable (LLM self-reference: critic rubber-stamps architect). Mitigation: mechanical severity rules are NOT LLM-judged — they are deterministic counts over structured critic output; escalate-to-user is the unconditional fallback.
- **Cost ceiling $15**: 5 rounds × 4 roles × structured output is ~20× a DP1 linear flow (~$0.009). Tier-B (DeepSeek) keeps it well under; Tier-S (OpenAI) baseline TBD when key available.

### Dependencies
- Backend: CrewAI `or_()` + `router` (already locked at `1.15.4` in DP0; DP2 exercises them for real) — no version bump unless No-Go-A fires
- Frontend: PixiJS sprite-sheet assets for 4 roles (new art); animation state machine extends `pet-state.ts`
- No new OS-level dependency

### Regression Baseline
- **DP1 Golden Demo MUST replay clean** before DP2 archive: same `config-hot-reload.txt` under DP2 code tree produces the same 4 markdown + cost_report within ±20% (DP1 linear path is preserved as the non-confrontation fallback).
- **WS-IPC contract backward compatibility**: DP1's 14 frozen WS conditions MUST still pass; the DP2 additive fields are optional and do not break DP1 clients.
- archive 前冻结 DP2 Golden Demo (full 5-round confrontation under the pet, cost ≤ $15) to `openspec/regression/golden-demos/dev-phase-2.md` + git tag `dev-phase-2-v1`.

## Status

**DRAFT** — this proposal captures the DP2 scope per `analysis/06` §四. `design.md` (CrewAI `or_()` loop wiring, convergence rule catalog, sprite/animation spec, concurrent-flow isolation) + detailed `tasks.md` to be elaborated before implementation kick-off. The Go/No-Go conditions (A: CrewAI loop stability, B: convergence decidability) MUST be de-risked by the first two milestones (D2-1 smoke + D2-2 mechanical rules) before committing to the full 5-7 week spend.
