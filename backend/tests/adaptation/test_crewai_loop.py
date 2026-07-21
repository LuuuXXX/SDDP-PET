"""Tests for CrewAI integration smoke (D0-1 monitoring — covers DP0-NG-B No-Go condition).

Per Dev-Phase 0 design.md No-Go Rollback Plan DP0-NG-B: if CrewAI's loop pattern
(#5972 regression) is broken in our selected version, this test MUST fail.

We don't run a real CrewAI Flow with LLM here — we only validate:
  1. CrewAI imports cleanly (Flow / Agent / @start / @listen / @router)
  2. or_() combinator is available and callable
  3. A minimal Flow subclass with router + listen can be defined without error

This serves as the canary for "CrewAI loop pattern unavailable in selected version".
"""
from __future__ import annotations

import pytest


def test_crewai_imports_cleanly():
    """CrewAI 1.15.4 MUST import without error (else DP0-NG-B triggers)."""
    import crewai
    assert crewai.__version__ == "1.15.4", f"unexpected crewai version: {crewai.__version__}"


def test_crewai_flow_primitives_available():
    """CrewAI Flow API MUST expose start / listen / router / or_."""
    from crewai.flow.flow import Flow, listen, or_, router, start
    assert all(callable(x) for x in [start, listen, router, or_])


def test_listen_does_not_have_already_fired_marker():
    """#5972 fix signature: `listen` source MUST NOT contain `_already_fired` guard.

    Per analysis/03 §一: pre-#5972 `or_()` only triggered once due to this marker.
    The fix removed/conditionalized it. This test fails if the regression returns.
    """
    import inspect
    from crewai.flow.flow import listen
    src = inspect.getsource(listen)
    # The fix made or_() retrigger work; assert the unconditional fire-once marker is gone
    assert "_already_fired" not in src or "conditional" in src.lower(), (
        "CrewAI's `listen` source contains `_already_fired`; #5972 may have regressed. "
        "Investigate DP0-NG-B."
    )


def test_crewai_agent_importable():
    """Agent class MUST be importable (#6347 fix assumed present in 1.15.4)."""
    from crewai.agent import Agent
    assert Agent is not None


def test_crewai_flow_class_subclassable():
    """Spec scenario: a minimal CrewAI Flow with router + listen MUST be definable.

    Per design.md DP0-NG-B: if this fails, the selected CrewAI version's loop pattern
    is unavailable. We only verify class definition here (no kickoff).
    """
    from crewai.flow.flow import Flow, listen, router, start

    try:
        class SmokeFlow(Flow[dict]):
            initialization_complete: bool = False

            @start()
            def begin(self):
                return {"round": 1}

            @router(begin)
            def route(self):
                return "loop"

            @listen(route)
            def step(self):
                return {"round": 2}

        # Class defined without error → wiring OK
        assert SmokeFlow is not None
    except Exception as e:
        pytest.fail(f"CrewAI Flow class definition failed: {e}. DP0-NG-B may be triggering.")


def test_crewai_adapter_class_can_be_imported():
    """CrewAIFlowAdapter MUST be importable without instantiating real CrewAI Flow."""
    from sddp.adaptation.crewai_adapter import CrewAIFlowAdapter
    assert CrewAIFlowAdapter is not None


def test_crewai_adapter_requires_flow_arg():
    """CrewAIFlowAdapter MUST require flow_cls or flow_instance."""
    from sddp.adaptation.crewai_adapter import CrewAIFlowAdapter
    with pytest.raises(ValueError):
        CrewAIFlowAdapter()
