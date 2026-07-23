"""Server-side runner for the Phase 1 confrontation flow (D2-1 serve integration).

The analogue of ``server._run_flow_in_thread`` but for ``Phase1ConfrontationFlow``.
``run_confrontation_in_thread`` wraps each injected agent to emit an
``agent_state_change`` Push (role-tagged, so window1 can render the debating
role) and emits ``document_produced`` on completion. The escalate points
(converged / force_convergence) flow through the existing
``WebSocketHumanFeedbackAdapter`` — no new feedback path needed.

Kept as a standalone module (not inlined into ``server.py``) so it is unit-
testable with mock agents WITHOUT touching the frozen DP1 WS handler.
``server.py`` wires this in via ``start_flow`` routing (``phase='confrontation'``)
as a follow-up; this module is the testable core of that integration.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Callable

from .schemas import AgentState, AgentStateChange, DocType, DocumentProduced
from ..engine.flows.phase_1_confrontation import Phase1ConfrontationFlow

logger = logging.getLogger(__name__)


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def run_confrontation_in_thread(
    proposal: str,
    flow_id: str,
    agents: dict[str, Callable[[dict[str, Any]], dict[str, Any]]],
    human_feedback_handler: Callable[[str, dict[str, Any]], bool],
    broadcast_sync: Callable[[dict[str, Any]], None],
    *,
    critic_dimensions: list[str] | None = None,
    max_rounds: int = 5,
) -> None:
    """Worker-thread entry: run ``Phase1ConfrontationFlow`` and push WS events.

    Args:
        proposal: the user's requirement text
        flow_id: correlation id (also the @persist namespace + WS flow_id)
        agents: AgentFn dict — mock for tests, ``build_real_confrontation_agents``
            for production
        human_feedback_handler: invoked at escalate points (converged/force);
            in production this is the ``WebSocketHumanFeedbackAdapter`` instance
            (it is callable: ``__call__(kind, payload) -> bool``)
        broadcast_sync: sync→loop bridge that pushes a Push message dict to the
            WS client (see ``server._run_flow_in_thread::broadcast_sync``)
        critic_dimensions: dimensions to challenge from (default 安全性/性能/可维护性)
        max_rounds: convergence ceiling
    """

    def wrap(role: str, fn: Callable[[dict[str, Any]], dict[str, Any]]):
        def wrapped(inputs: dict[str, Any]) -> dict[str, Any]:
            try:
                broadcast_sync(
                    AgentStateChange(
                        timestamp=_utc_now(),
                        flow_id=flow_id,
                        agent=role,
                        state=AgentState.WORKING,
                        role=role,
                    ).model_dump()
                )
            except Exception as e:  # broadcast failure is non-fatal
                logger.warning(
                    "broadcast agent_state(working) for %s failed: %s", role, e
                )
            return fn(inputs)

        return wrapped

    wrapped_agents = {role: wrap(role, fn) for role, fn in agents.items()}

    flow = Phase1ConfrontationFlow(
        agents=wrapped_agents,
        critic_dimensions=critic_dimensions,
        max_rounds=max_rounds,
        human_feedback_handler=human_feedback_handler,
        flow_id=flow_id,
    )
    try:
        result = flow.kickoff({"proposal": proposal})
    except Exception as e:
        logger.exception("confrontation flow crashed (flow_id=%s): %s", flow_id, e)
        return

    # Push produced documents (architecture_research / delta_spec / delta_design)
    state = result.state
    if state.architecture_research:
        _push_doc(
            broadcast_sync,
            flow_id,
            "architecture_research",
            state.architecture_research,
        )
    if state.current_delta_spec:
        _push_doc(broadcast_sync, flow_id, "delta_spec", state.current_delta_spec)
    if state.current_delta_design:
        _push_doc(broadcast_sync, flow_id, "delta_design", state.current_delta_design)


def _push_doc(
    broadcast_sync: Callable[[dict[str, Any]], None],
    flow_id: str,
    doc_type_str: str,
    content: Any,
) -> None:
    try:
        doc_type = DocType(doc_type_str)
    except ValueError:
        return
    try:
        broadcast_sync(
            DocumentProduced(
                timestamp=_utc_now(),
                flow_id=flow_id,
                agent="architect",
                doc_type=doc_type,
                doc_id=f"{doc_type_str}-{flow_id}",
                summary=str(content)[:200],
            ).model_dump()
        )
    except Exception as e:
        logger.warning("broadcast document_produced(%s) failed: %s", doc_type_str, e)


__all__ = ["run_confrontation_in_thread"]
