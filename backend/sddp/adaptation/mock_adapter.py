"""MockFlowAdapter: implements FlowDefinition WITHOUT CrewAI or real LLMs.

Per specs/adaptation-layer/spec.md scenario "Mock adapter 用于 5 角色 kickoff 测试":
engine unit tests use this adapter to drive 5-role kickoff without real CrewAI Flows
or OpenAI API calls.

Execution model: in-memory event bus. `start` step produces an initial event;
`router` steps dispatch on events; `listen` steps consume events. `persist` saves to
an in-memory dict (optionally backed by a temp file for resume tests).
"""
from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass, field
from typing import Any, Callable

from .flow_definition import FlowDefinition

logger = logging.getLogger(__name__)


@dataclass
class _MockRunState:
    """In-memory state of one MockFlowAdapter execution."""

    inputs: dict[str, Any] = field(default_factory=dict)
    events: dict[str, Any] = field(default_factory=dict)  # event_name → last payload
    visited_steps: list[str] = field(default_factory=list)
    persisted: dict[str, dict[str, Any]] = field(default_factory=dict)
    final_result: Any = None
    flow_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    completed: bool = False
    max_steps: int = 100  # cycle guard


class MockFlowAdapter(FlowDefinition):
    """Adapter that runs FlowDefinition primitives in-memory.

    Usage in tests:
        flow = MockFlowAdapter()

        @flow.start
        def begin(inputs):
            return {"round": 1}

        @flow.listen("begin", "next_event")  # alternative 2-arg form
        def step(payload):
            return {"round": 2}

        result = flow.kickoff({"proposal": "..."})
    """

    def __init__(self, *, max_steps: int = 100) -> None:
        super().__init__()
        self._state = _MockRunState(max_steps=max_steps)
        self._inputs: dict[str, Any] = {}
        # Register self.persist as both save+load to the in-memory dict
        # (tests can replace with file-backed persistence as needed)
        self.persist(save_fn=self._save_in_memory, load_fn=self._load_in_memory)

    # ---- persist callbacks (in-memory) ----

    def _save_in_memory(self, key: str, data: dict[str, Any]) -> None:
        self._state.persisted[key] = data

    def _load_in_memory(self, key: str) -> dict[str, Any] | None:
        return self._state.persisted.get(key)

    # ---- 2-arg listen helper for cleaner test wiring ----

    def listen_2arg(self, source_event: str, target_event: str, fn: Callable[..., Any]) -> Callable[..., Any]:
        """Convenience: listen to source_event, route result to target_event."""
        def wrapped(*args, **kwargs):
            result = fn(*args, **kwargs)
            self._state.events[target_event] = result
            self._state.visited_steps.append(target_event)
            return result

        self._listeners.setdefault(source_event, []).append(wrapped)
        return fn

    # ---- FlowDefinition abstract impl ----

    def kickoff(self, inputs: dict[str, Any] | None = None) -> Any:
        """Run the flow synchronously in-memory.

        Execution algorithm:
          1. Run each registered start step (in registration order) with `inputs`.
             Each start step's return value becomes the event whose name is the
             function's __name__.
          2. For each new event produced, fire any listeners + the router.
             Router returns the name of the next event(s) to emit; we materialize
             those events by running the corresponding listeners.
          3. Stop when no more events fire or max_steps hit.
        """
        self._inputs = dict(inputs or {})
        self._state = _MockRunState(max_steps=self._state.max_steps, flow_id=self._state.flow_id)
        self._state.inputs = self._inputs

        steps_taken = 0
        # Fire starts
        for start_fn in self._starts:
            if steps_taken >= self._state.max_steps:
                break
            try:
                result = start_fn(self._inputs)
            except TypeError:
                result = start_fn()
            event_name = start_fn.__name__
            self._state.events[event_name] = result
            self._state.visited_steps.append(event_name)
            steps_taken += 1

        # Propagate through listeners + routers (BFS)
        pending: list[str] = list(self._state.events.keys())
        while pending and steps_taken < self._state.max_steps:
            current = pending.pop(0)
            payload = self._state.events[current]

            # Fire listeners
            for listener in self._listeners.get(current, []):
                try:
                    result = listener(payload)
                except TypeError:
                    result = listener()
                event_name = listener.__name__
                self._state.events[event_name] = result
                self._state.visited_steps.append(event_name)
                pending.append(event_name)
                steps_taken += 1
                if steps_taken >= self._state.max_steps:
                    break

            # Fire router if any
            router_fn = self._routers.get(current)
            if router_fn is not None:
                try:
                    route_result = router_fn(payload)
                except TypeError:
                    route_result = router_fn()
                targets = [route_result] if isinstance(route_result, str) else list(route_result or [])
                # Materialize target events as "fired" so their listeners trigger
                for target in targets:
                    if target not in self._state.events:
                        self._state.events[target] = {"routed_from": current}
                        pending.append(target)

        # Persist the final state (in-memory)
        self.save_state(f"flow:{self._state.flow_id}", {
            "inputs": self._inputs,
            "events": {k: (v if isinstance(v, (str, int, float, bool, list, dict, type(None))) else str(v)) for k, v in self._state.events.items()},
            "visited_steps": self._state.visited_steps,
        })
        self._state.completed = True
        self._state.final_result = self._state.events
        return self._state.final_result

    def resume(self, flow_id: str) -> Any:
        """Resume from in-memory persisted state (re-runs from inputs)."""
        saved = self.load_state(f"flow:{flow_id}")
        if saved is None:
            raise KeyError(f"no persisted state for flow_id={flow_id!r}")
        # Re-run with same inputs
        return self.kickoff(saved.get("inputs", {}))

    # ---- test introspection ----

    @property
    def events(self) -> dict[str, Any]:
        return dict(self._state.events)

    @property
    def visited_steps(self) -> list[str]:
        return list(self._state.visited_steps)

    @property
    def flow_id(self) -> str:
        return self._state.flow_id

    @property
    def completed(self) -> bool:
        return self._state.completed

    def persisted_keys(self) -> list[str]:
        return list(self._state.persisted.keys())
