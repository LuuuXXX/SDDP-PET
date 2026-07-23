"""Convergence detection for the Phase 1 adversarial flow (Dev-Phase 2 D2-2).

Per `design.md` §5. Convergence is a **MECHANICAL, deterministic** judgment over
structured ``CriticismPoint.status`` — it does NOT ask the LLM to re-judge. This
is the direct mitigation of **No-Go-B** (the LLM self-reference paradox: a critic
that rubber-stamps the architect). The arbitrator LLM only ever runs on
medium/low-severity unresolved points, and even its output is guardrail-checked:
it may not dismiss a high-severity point without a substantive evidence basis.

Three pure functions form the contract:
    - needs_arbitration(points) — does the flow need to invoke the arbitrator?
    - apply_arbitration(points, decisions, errors) — apply + guardrail
    - check_convergence(points, round_count, max_rounds) — next verdict
"""

from __future__ import annotations

from enum import Enum

from .flows.phase_1_state import CriticismPoint


class ConvergenceVerdict(str, Enum):
    REVISE = "revise"
    CONVERGED = "converged"
    FORCE_CONVERGED = "force_converged"


# Minimum substantive length for an evidence basis (guards against "ok"/"yes").
# Per design §5 the basis must reference evidence_ref or a KG citation; we
# enforce a non-trivial length as a pragmatic floor.
_MIN_BASIS_LEN = 10


def needs_arbitration(points: list[CriticismPoint]) -> bool:
    """True if any medium/low-severity point is unresolved AND not yet arbitrated.

    High-severity unresolved points do NOT go to the arbitrator — they force
    ``REVISE`` directly (the architect MUST address them). Only medium/low points
    may be dismissed by the arbitrator, and only with an evidence basis.
    """
    return any(
        p.severity in ("中", "低")
        and p.status == "unresolved"
        and p.arbitrator_decision is None
        for p in points
    )


def check_convergence(
    points: list[CriticismPoint],
    round_count: int,
    max_rounds: int = 5,
) -> ConvergenceVerdict:
    """Decide the next flow step. Call AFTER arbitration has been applied.

    Precedence (order matters):
      1. ``max_rounds`` ceiling → ``FORCE_CONVERGED`` (unconditional; escalates
         to the user so a non-converging loop can never hang indefinitely —
         mitigates CrewAI issue #6370 at the SDDP layer).
      2. any high-severity still unresolved → ``REVISE``.
      3. all points resolved/dismissed → ``CONVERGED``.
      4. otherwise (mixed state post-arbitration) → ``REVISE`` (defensive).
    """
    if round_count >= max_rounds:
        return ConvergenceVerdict.FORCE_CONVERGED
    if any(p.severity == "高" and p.status == "unresolved" for p in points):
        return ConvergenceVerdict.REVISE
    if all(p.status in ("resolved", "dismissed") for p in points):
        return ConvergenceVerdict.CONVERGED
    return ConvergenceVerdict.REVISE


def _has_evidence_basis(basis: str | None) -> bool:
    """A dismiss decision is evidenced only if the basis is substantive (non-empty
    and above the trivial-length floor). The arbitrator is instructed to cite the
    empiricist's evidence_ref or a KG citation; we enforce a minimum bar here."""
    return bool(basis) and len(basis.strip()) >= _MIN_BASIS_LEN


def apply_arbitration(
    points: list[CriticismPoint],
    decisions: dict[str, dict],
    errors: list[str] | None = None,
) -> list[CriticismPoint]:
    """Apply arbitrator decisions to points, enforcing the high-severity guardrail.

    ``decisions`` maps ``point_id -> {"decision": "采纳"|"驳回", "basis": str}``.

    Semantics:
      - 采纳 (accept) → status stays/resets to ``unresolved`` (the architect
        must address it in the next revision).
      - 驳回 (dismiss):
          * high-severity WITHOUT substantive basis → **GUARDRAIL VIOLATION**:
            the dismiss is refused, the point stays ``unresolved``, the
            decision is undone, and the violation is recorded in ``errors``.
          * otherwise → status ``dismissed``.

    Returns the same list (mutated in place) for convenience.
    """
    for point in points:
        dec = decisions.get(point.id)
        if dec is None:
            continue
        decision = dec.get("decision")
        basis = dec.get("basis")
        point.arbitrator_decision = decision
        point.decision_basis = basis
        if decision == "采纳":
            point.status = "unresolved"  # architect must address
        elif decision == "驳回":
            if point.severity == "高" and not _has_evidence_basis(basis):
                msg = (
                    f"guardrail: refused dismiss of high-severity point "
                    f"{point.id} without substantive evidence basis"
                )
                if errors is not None:
                    errors.append(msg)
                # undo the decision — point must be addressed
                point.arbitrator_decision = None
                point.decision_basis = None
                point.status = "unresolved"
            else:
                point.status = "dismissed"
    return points
