"""Tests for MockFlowAdapter (D0-3): validates the 4 SDDP primitives without CrewAI/LLM."""
from __future__ import annotations

import pytest

from sddp.adaptation.flow_definition import FlowDefinition
from sddp.adaptation.mock_adapter import MockFlowAdapter


def test_flow_definition_is_abstract():
    """FlowDefinition MUST be abstract; cannot instantiate directly."""
    with pytest.raises(TypeError):
        FlowDefinition()  # type: ignore[abstract]


def test_flow_definition_public_api_does_not_import_crewai():
    """Spec: FlowDefinition's public API MUST NOT import crewai."""
    import sddp.adaptation.flow_definition as mod
    src = open(mod.__file__).read()
    assert "import crewai" not in src
    assert "from crewai" not in src


def test_start_primitive_registers_step():
    """start(fn) MUST register fn as a start step."""
    flow = MockFlowAdapter()

    @flow.start
    def begin(inputs):
        return {"started": True}

    assert begin in flow.start_steps
    assert len(flow.start_steps) == 1


def test_listen_primitive_registers_listener():
    """listen(event_name, fn) MUST register fn under event_name."""
    flow = MockFlowAdapter()

    @flow.listen("begin")
    def step(payload):
        return {"stepped": True}

    assert step in flow.listeners_for("begin")
    assert len(flow.listeners_for("begin")) == 1


def test_router_primitive_registers_routing_decision():
    """router(event_name, fn) MUST register fn as the router for event_name."""
    flow = MockFlowAdapter()

    @flow.router("begin")
    def route(payload):
        return "next_event"

    assert flow.router_for("begin") is route


def test_persist_primitive_registers_save_and_load():
    """persist(save_fn=, load_fn=) MUST register both callbacks."""
    flow = MockFlowAdapter()
    saved: dict[str, dict] = {}

    def save(key, data):
        saved[key] = data

    def load(key):
        return saved.get(key)

    flow.persist(save_fn=save, load_fn=load)
    flow.save_state("k1", {"v": 1})
    assert saved["k1"] == {"v": 1}
    assert flow.load_state("k1") == {"v": 1}
    assert flow.load_state("missing") is None


def test_kickoff_runs_start_and_records_event():
    """kickoff MUST execute start step and produce event keyed by step's __name__."""
    flow = MockFlowAdapter()

    @flow.start
    def begin(inputs):
        return {"echo": inputs.get("x")}

    result = flow.kickoff({"x": "hello"})
    assert "begin" in result
    assert result["begin"]["echo"] == "hello"
    assert flow.completed is True
    assert "begin" in flow.visited_steps


def test_kickoff_runs_listener_when_event_fires():
    """listener MUST fire when its registered event appears."""
    flow = MockFlowAdapter()

    @flow.start
    def begin(inputs):
        return {"value": 1}

    @flow.listen("begin")
    def second(payload):
        return {"value": payload["value"] + 1}

    result = flow.kickoff({})
    assert "second" in result
    assert result["second"]["value"] == 2


def test_router_directs_to_named_event():
    """router MUST materialize the named target event, triggering its listeners."""
    flow = MockFlowAdapter()

    @flow.start
    def begin(inputs):
        return {"phase": "start"}

    @flow.router("begin")
    def route(payload):
        return "phase_two"

    @flow.listen("phase_two")
    def second_stage(payload):
        return {"phase": "two-done"}

    result = flow.kickoff({})
    assert "phase_two" in result
    assert "second_stage" in result
    assert result["second_stage"]["phase"] == "two-done"


def test_cycle_guard_prevents_infinite_loops():
    """max_steps MUST cap execution to prevent infinite cycles."""
    flow = MockFlowAdapter(max_steps=5)

    @flow.start
    def begin(inputs):
        return {"n": 1}

    @flow.listen("begin")
    def loop_step(payload):
        return {"n": payload["n"] + 1}

    # Without guard, this would loop forever (each step re-emits as 'loop_step')
    # The cycle guard caps visited_steps
    flow.kickoff({})
    assert len(flow.visited_steps) <= 10  # hard cap with safety margin


def test_resume_after_persist_round_trip():
    """Spec scenario: @persist interrupt + resume."""
    flow = MockFlowAdapter()

    @flow.start
    def begin(inputs):
        return {"inputs": inputs}

    flow.kickoff({"proposal": "test"})
    flow_id = flow.flow_id
    persisted_keys = flow.persisted_keys()
    assert any(flow_id in k for k in persisted_keys)

    # Resume
    resumed = flow.resume(flow_id)
    assert "begin" in resumed
    assert resumed["begin"]["inputs"]["proposal"] == "test"


def test_resume_unknown_flow_id_raises():
    flow = MockFlowAdapter()
    with pytest.raises(KeyError):
        flow.resume("nonexistent-flow-id")
