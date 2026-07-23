"""Confrontation runner integration tests (D2-1 serve-mode wiring).

Validates ``run_confrontation_in_thread`` with MOCK agents: the flow runs to
convergence and the runner emits the expected WS Push sequence
(``agent_state_change`` with ``role`` tags + ``document_produced`` for the 3
architect outputs). The escalate path is exercised through a mock
human_feedback_handler.

This is the serve-integration core; wiring it into ``server.py``'s
``start_flow`` routing (phase='confrontation') is a follow-up that touches the
frozen DP1 handler.
"""

from __future__ import annotations

from sddp.ipc.confrontation_runner import run_confrontation_in_thread


def _mock_arch(inputs):
    return {
        "delta_spec": "spec-content",
        "delta_design": "design-content",
        "architecture_research": "research-content",
    }


def _no_criticism_critic(inputs):
    return {"criticism_points": []}  # → immediate convergence


def test_runner_emits_role_tagged_agent_state_and_documents():
    pushed: list[dict] = []
    run_confrontation_in_thread(
        proposal="加配置热重载",
        flow_id="flow-test",
        agents={
            "architect": _mock_arch,
            "critic": _no_criticism_critic,
            "empiricist": lambda i: {},
            "orchestrator": lambda i: {},
        },
        human_feedback_handler=lambda kind, payload: True,  # auto-approve converge
        broadcast_sync=pushed.append,
        critic_dimensions=["性能"],
    )

    # 1. agent_state_change Pushes carry the role tag (architect at minimum)
    state_changes = [m for m in pushed if m.get("type") == "agent_state_change"]
    assert len(state_changes) >= 1
    roles_pushed = {m.get("role") for m in state_changes}
    assert "architect" in roles_pushed

    # 2. document_produced for the 3 architect outputs
    docs = [m for m in pushed if m.get("type") == "document_produced"]
    doc_types = {m.get("doc_type") for m in docs}
    assert "architecture_research" in doc_types
    assert "delta_spec" in doc_types
    assert "delta_design" in doc_types

    # 3. all pushes carry the flow_id (non-error messages per WS contract)
    for m in pushed:
        assert m.get("flow_id") == "flow-test"


def test_runner_survives_agent_exception():
    """If an agent raises, the runner logs + returns (no exception escapes)."""

    def boom(inputs):
        raise RuntimeError("agent exploded")

    pushed: list[dict] = []
    # architect raises → flow.kickoff propagates → runner catches, no docs pushed
    run_confrontation_in_thread(
        proposal="p",
        flow_id="flow-boom",
        agents={
            "architect": boom,
            "critic": _no_criticism_critic,
            "empiricist": lambda i: {},
            "orchestrator": lambda i: {},
        },
        human_feedback_handler=lambda k, p: True,
        broadcast_sync=pushed.append,
    )
    # architect WORKING state was pushed before the explosion; no docs
    docs = [m for m in pushed if m.get("type") == "document_produced"]
    assert docs == []


def test_runner_force_converge_path_uses_feedback_handler():
    """max_rounds hit → force_convergence escalate → handler invoked with that kind."""
    escalate_kinds: list[str] = []

    def handler(kind, payload):
        escalate_kinds.append(kind)
        return True

    def high_critic(inputs):
        return {
            "criticism_points": [
                {"id": "c1", "dimension": "性能", "content": "x", "severity": "高"}
            ]
        }

    run_confrontation_in_thread(
        proposal="p",
        flow_id="flow-force",
        agents={
            "architect": _mock_arch,
            "critic": high_critic,
            "empiricist": lambda i: {"evidence": "ev"},
            "orchestrator": lambda i: {},
        },
        human_feedback_handler=handler,
        broadcast_sync=lambda m: None,
        critic_dimensions=["性能"],
        max_rounds=2,
    )
    # force_convergence escalate must have fired (high severity never converges)
    assert "force_convergence" in escalate_kinds
