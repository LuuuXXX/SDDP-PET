"""DP2 WS additive contract tests (design §8 backward compatibility).

Verifies the DP2 additions are ADDITIVE: DP1 messages still parse (no `role` →
None), DP2 messages construct (`role` + `force_convergence`), and the frozen
DP1 contract is not broken. This is the Week-2 WS-integration contract prep.
"""

from __future__ import annotations

from sddp.ipc.schemas import (
    AgentState,
    AgentStateChange,
    FeedbackMethod,
    FeedbackRequired,
    parse_message,
)


def test_force_convergence_is_valid_feedback_method():
    assert FeedbackMethod("force_convergence") is FeedbackMethod.FORCE_CONVERGENCE


def test_agent_state_change_role_is_optional():
    """DP1 client sends agent_state_change without role → must still parse, role=None."""
    msg = AgentStateChange(
        type="agent_state_change",
        timestamp="t",
        agent="architect",
        state=AgentState.WORKING,
    )
    assert msg.role is None


def test_agent_state_change_with_role_round_dp2():
    msg = AgentStateChange(
        type="agent_state_change",
        timestamp="t",
        agent="critic",
        state=AgentState.WORKING,
        role="critic",
        round=2,
    )
    assert msg.role == "critic"
    assert msg.round == 2


def test_dp1_message_without_role_still_parses_via_parse_message():
    """The frozen DP1 parse path is not broken by the additive role field."""
    raw = {
        "type": "agent_state_change",
        "timestamp": "t",
        "agent": "architect",
        "state": "working",
    }
    msg = parse_message(raw)
    assert msg.role is None  # additive field absent → None (DP1 client unaffected)


def test_feedback_required_with_force_convergence_method():
    fr = FeedbackRequired(
        type="feedback_required",
        timestamp="t",
        method=FeedbackMethod.FORCE_CONVERGENCE,
        message="对抗已达上限",
        output={},
    )
    assert fr.method is FeedbackMethod.FORCE_CONVERGENCE
