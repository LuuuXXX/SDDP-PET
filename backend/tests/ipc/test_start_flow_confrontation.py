"""DP2 server confrontation routing — component tests (additive wiring).

Validates the additive confrontation wiring without the complexity of a live WS
round-trip: (1) StartFlow schema accepts phase='confrontation'; (2) phase
defaults to 'linear' (DP1 back-compat); (3) create_app accepts + stores
confrontation_agents_factory. The live WS routing (start_flow phase=confrontation
→ run_confrontation_in_thread) is exercised in test_confrontation_runner.py
(the runner itself) — here we verify the server wiring accepts it.
"""

from __future__ import annotations

from sddp.ipc.schemas import StartFlow, parse_message
from sddp.ipc.server import create_app


def test_start_flow_accepts_confrontation_phase() -> None:
    msg = parse_message(
        {
            "type": "start_flow",
            "timestamp": "t",
            "message_id": "m1",
            "proposal": "p",
            "project_path": ".",
            "phase": "confrontation",
        }
    )
    assert isinstance(msg, StartFlow)
    assert msg.phase == "confrontation"


def test_start_flow_phase_defaults_linear() -> None:
    """DP1 clients omit phase → 'linear' (linear path unchanged)."""
    msg = parse_message(
        {
            "type": "start_flow",
            "timestamp": "t",
            "message_id": "m1",
            "proposal": "p",
            "project_path": ".",
        }
    )
    assert msg.phase == "linear"


def test_create_app_accepts_confrontation_agents_factory() -> None:
    factory_called = {"n": 0}

    def factory() -> dict:
        factory_called["n"] += 1
        return {"architect": lambda i: {}}

    app = create_app(confrontation_agents_factory=factory)
    assert app.state.confrontation_agents_factory is factory
    agents = app.state.confrontation_agents_factory()
    assert "architect" in agents
    assert factory_called["n"] == 1


def test_create_app_default_factory_is_none() -> None:
    """Without wiring, confrontation mode is unavailable (start_flow would error)."""
    app = create_app()
    assert app.state.confrontation_agents_factory is None
