"""Phase 1 Confrontation Flow state model (Dev-Phase 2 D2-1).

Per `openspec/changes/dev-phase-2-confrontation-flow/design.md` §3. This is
the adversarial flow's state: the architect / critic / empiricist / orchestrator
iterate over CriticismPoints until convergence (D2-2). Distinct from DP0's
linear flow state — this carries the per-round criticism/arbitration bookkeeping.

`flow_id` is the concurrency-isolation key (D2-4): every persisted row in
flow_state.db is namespaced by it so 2 concurrent flows never cross-talk.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class CriticismPoint(BaseModel):
    """One objection raised by a critic, tracked through resolution."""

    id: str
    dimension: str  # 安全性 / 性能 / 可维护性
    content: str
    severity: str  # 高 / 中 / 低
    evidence_ref: str | None = None
    architect_response: str | None = None
    arbitrator_decision: str | None = None  # 采纳 / 驳回
    decision_basis: str | None = None
    status: str = "unresolved"  # unresolved / resolved / dismissed


class Phase1ConfrontationState(BaseModel):
    flow_id: str = ""
    proposal: str = ""
    architecture_research: str | None = None
    current_delta_spec: str | None = None
    current_delta_design: str | None = None
    criticism_points: list[CriticismPoint] = Field(default_factory=list)
    evidence_reports: list[str] = Field(default_factory=list)
    round_count: int = 0
    max_rounds: int = 5
    converged: bool = False
    errors: list[str] = Field(default_factory=list)
