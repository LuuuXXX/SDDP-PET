"""Convergence engine tests (Dev-Phase 2 D2-2 — No-Go-B de-risking).

Verifies the convergence logic is fully mechanical/deterministic (no LLM
re-judgment) per `design.md` §5. Covers every rule path + the high-severity
dismiss guardrail + an end-to-end arbitrate→converge cycle.

These tests ARE the No-Go-B acceptance: if they pass, convergence is decidable
without invoking the LLM a second time, and the self-reference paradox is
structurally impossible.
"""

from __future__ import annotations

from sddp.engine.convergence import (
    ConvergenceVerdict,
    apply_arbitration,
    check_convergence,
    needs_arbitration,
)
from sddp.engine.flows.phase_1_state import CriticismPoint


def _pt(
    pid: str,
    severity: str = "中",
    status: str = "unresolved",
    decision: str | None = None,
    basis: str | None = None,
    evidence: str | None = None,
) -> CriticismPoint:
    return CriticismPoint(
        id=pid,
        dimension="性能",
        content="x",
        severity=severity,
        status=status,
        arbitrator_decision=decision,
        decision_basis=basis,
        evidence_ref=evidence,
    )


class TestCheckConvergence:
    def test_force_converged_at_max_rounds(self):
        points = [_pt("p1", severity="高")]  # would normally REVISE
        assert (
            check_convergence(points, round_count=5, max_rounds=5)
            == ConvergenceVerdict.FORCE_CONVERGED
        )

    def test_max_rounds_takes_precedence_over_high_revise(self):
        points = [_pt("p1", severity="高", status="unresolved")]
        assert (
            check_convergence(points, round_count=5)
            == ConvergenceVerdict.FORCE_CONVERGED
        )

    def test_high_severity_unresolved_forces_revise(self):
        points = [_pt("p1", severity="高", status="unresolved")]
        assert check_convergence(points, round_count=1) == ConvergenceVerdict.REVISE

    def test_all_resolved_converges(self):
        points = [_pt("p1", status="resolved"), _pt("p2", status="dismissed")]
        assert check_convergence(points, round_count=1) == ConvergenceVerdict.CONVERGED

    def test_high_resolved_converges(self):
        points = [_pt("p1", severity="高", status="resolved")]
        assert check_convergence(points, round_count=2) == ConvergenceVerdict.CONVERGED

    def test_empty_points_converges(self):
        assert check_convergence([], round_count=1) == ConvergenceVerdict.CONVERGED

    def test_mixed_post_arbitration_defensively_revise(self):
        # one dismissed + one still unresolved medium → not all settled → REVISE
        points = [
            _pt("p1", status="dismissed"),
            _pt("p2", severity="中", status="unresolved"),
        ]
        assert check_convergence(points, round_count=2) == ConvergenceVerdict.REVISE


class TestNeedsArbitration:
    def test_medium_unresolved_unarbitrated_needs_arbitration(self):
        assert needs_arbitration([_pt("p1", severity="中")]) is True

    def test_low_unresolved_unarbitrated_needs_arbitration(self):
        assert needs_arbitration([_pt("p1", severity="低")]) is True

    def test_high_unresolved_does_not_need_arbitration(self):
        # high-severity bypasses the arbitrator and forces REVISE directly
        assert needs_arbitration([_pt("p1", severity="高")]) is False

    def test_already_arbitrated_does_not_need(self):
        assert needs_arbitration([_pt("p1", severity="中", decision="采纳")]) is False

    def test_resolved_does_not_need(self):
        assert needs_arbitration([_pt("p1", status="resolved")]) is False

    def test_empty_does_not_need(self):
        assert needs_arbitration([]) is False


class TestApplyArbitration:
    def test_accept_keeps_unresolved(self):
        points = [_pt("p1", severity="中")]
        apply_arbitration(points, {"p1": {"decision": "采纳", "basis": "有效质疑"}})
        assert points[0].status == "unresolved"
        assert points[0].arbitrator_decision == "采纳"

    def test_dismiss_medium_with_basis_dismisses(self):
        points = [_pt("p1", severity="中", evidence="evid-1")]
        apply_arbitration(
            points,
            {
                "p1": {
                    "decision": "驳回",
                    "basis": "实证报告 evid-1 显示无影响，依据充分",
                }
            },
        )
        assert points[0].status == "dismissed"

    def test_guardrail_refuses_dismiss_high_without_basis(self):
        points = [_pt("p1", severity="高", evidence=None)]
        errors: list[str] = []
        apply_arbitration(
            points, {"p1": {"decision": "驳回", "basis": ""}}, errors=errors
        )
        assert points[0].status == "unresolved"  # refused
        assert points[0].arbitrator_decision is None  # undone
        assert any("guardrail" in e for e in errors)

    def test_guardrail_refuses_dismiss_high_with_short_basis(self):
        points = [_pt("p1", severity="高", evidence=None)]
        apply_arbitration(points, {"p1": {"decision": "驳回", "basis": "ok"}})
        assert points[0].status == "unresolved"

    def test_guardrail_allows_dismiss_high_with_substantive_basis(self):
        points = [_pt("p1", severity="高", evidence="evid-x")]
        apply_arbitration(
            points,
            {
                "p1": {
                    "decision": "驳回",
                    "basis": "经实证报告 evid-x 验证该安全担忧不成立，KG 无相关调用路径",
                }
            },
        )
        assert points[0].status == "dismissed"

    def test_unrelated_point_untouched(self):
        points = [_pt("p1", severity="中"), _pt("p2", severity="低")]
        apply_arbitration(points, {"p1": {"decision": "采纳", "basis": "x"}})
        assert points[1].arbitrator_decision is None

    def test_accept_then_re_dismiss_path(self):
        # accepted point stays unresolved → architect addresses → resolved
        points = [_pt("p1", severity="中")]
        apply_arbitration(points, {"p1": {"decision": "采纳", "basis": "valid"}})
        assert points[0].status == "unresolved"


class TestEndToEndConvergenceCycle:
    def test_medium_arbitrate_dismiss_then_converge(self):
        points = [_pt("p1", severity="中", evidence="evid")]
        assert needs_arbitration(points) is True
        apply_arbitration(
            points,
            {
                "p1": {
                    "decision": "驳回",
                    "basis": "evid 证明该质疑不成立，详细依据在此",
                }
            },
        )
        assert check_convergence(points, round_count=1) == ConvergenceVerdict.CONVERGED

    def test_high_unresolved_bypasses_arbitration_to_revise(self):
        points = [_pt("p1", severity="高")]
        assert needs_arbitration(points) is False  # no arbitration needed
        assert check_convergence(points, round_count=1) == ConvergenceVerdict.REVISE

    def test_guardrail_violation_keeps_revise_alive(self):
        # arbitrator tries to rubber-stamp a high-severity point → guardrail
        # refuses → point stays unresolved → REVISE (loop continues correctly)
        points = [_pt("p1", severity="高", evidence=None)]
        errors: list[str] = []
        apply_arbitration(
            points, {"p1": {"decision": "驳回", "basis": ""}}, errors=errors
        )
        assert points[0].status == "unresolved"
        assert check_convergence(points, round_count=1) == ConvergenceVerdict.REVISE
        assert len(errors) == 1
