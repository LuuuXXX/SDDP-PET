"""FlowDefinition: SDDP's adapter-agnostic abstraction over CrewAI Flows API.

Per specs/adaptation-layer/spec.md:
  - Public API MUST NOT import `crewai`
  - Exposes 4 primitives: start, listen, router, persist
  - CrewAIFlowAdapter + MockFlowAdapter are concrete implementations

This abstraction is the upgrade buffer (analysis/03 §4.3): swapping CrewAI versions
or migrating to LangGraph only requires a new adapter, not engine changes.
"""
from __future__ import annotations

import abc
from dataclasses import dataclass, field
from typing import Any, Callable, Literal


@dataclass
class FlowEvent:
    """A discrete event flowing through the graph (named slot + payload)."""

    name: str
    payload: Any = None
    source: str | None = None  # which step produced this


@dataclass
class PersistedState:
    """A snapshot of Flow state, persistable for resume."""

    flow_id: str
    step: str
    data: dict[str, Any]
    errors: list[dict[str, Any]] = field(default_factory=list)


class FlowDefinition(abc.ABC):
    """Abstract Flow that SDDP engines build against.

    Subclasses register steps via the 4 primitives in their __init__ (or build()).
    The actual execution semantics differ per adapter (CrewAI vs Mock vs future).
    """

    name: str = "FlowDefinition"

    def __init__(self) -> None:
        # Step registry — populated by primitives
        self._starts: list[Callable[..., Any]] = []
        self._listeners: dict[str, list[Callable[..., Any]]] = {}
        self._routers: dict[str, Callable[..., str | list[str]]] = {}
        self._persist_handlers: list[Callable[[str, dict[str, Any]], None]] = []
        self._persist_load_handlers: list[Callable[[str], dict[str, Any] | None]] = []

    # ---- 4 primitives (call these inside subclass __init__ or build) ----

    def start(self, fn: Callable[..., Any] | None = None) -> Any:
        """Register a start step (entry point of the flow).

        Two forms supported:
          - Direct: `flow.start(fn)` or `flow.start()(fn)`
          - Decorator: `@flow.start` or `@flow.start()`
        """
        def _register(actual_fn: Callable[..., Any]) -> Callable[..., Any]:
            self._starts.append(actual_fn)
            return actual_fn

        if fn is None:
            return _register
        return _register(fn)

    def listen(self, event_name_or_fn: str | Callable[..., Any] | None = None, fn: Callable[..., Any] | None = None) -> Any:
        """Register a step that fires when event_name is produced.

        Three forms supported:
          - Direct: `flow.listen("event", fn)`
          - Decorator-with-args: `@flow.listen("event")` then `def fn(...):`
          - Bare decorator: `@flow.listen` (uses fn.__name__ as event_name)
        """
        def _register(actual_fn: Callable[..., Any], ev_name: str) -> Callable[..., Any]:
            self._listeners.setdefault(ev_name, []).append(actual_fn)
            return actual_fn

        # Form 1: direct call with both args
        if isinstance(event_name_or_fn, str) and fn is not None:
            return _register(fn, event_name_or_fn)

        # Form 2: decorator-with-args (event_name_or_fn is the event name, fn is None)
        if isinstance(event_name_or_fn, str):
            def decorator(actual_fn: Callable[..., Any]) -> Callable[..., Any]:
                return _register(actual_fn, event_name_or_fn)
            return decorator

        # Form 3: bare decorator (event_name_or_fn is the function itself, use its __name__)
        if callable(event_name_or_fn):
            return _register(event_name_or_fn, event_name_or_fn.__name__)

        # Form 4: neither (no args) — unsupported; raise to catch misuse
        raise TypeError("listen() requires at least an event name or a function")

    def router(self, event_name_or_fn: str | Callable[..., Any] | None = None, fn: Callable[..., str | list[str]] | None = None) -> Any:
        """Register a routing decision: on event_name, call fn → next event name(s).

        Same forms as `listen()`:
          - `flow.router("event", fn)`
          - `@flow.router("event")` then `def fn(...):`
          - `@flow.router` (uses fn.__name__ as event_name)
        """
        def _register(actual_fn: Callable[..., str | list[str]], ev_name: str) -> Callable[..., str | list[str]]:
            self._routers[ev_name] = actual_fn
            return actual_fn

        if isinstance(event_name_or_fn, str) and fn is not None:
            return _register(fn, event_name_or_fn)

        if isinstance(event_name_or_fn, str):
            def decorator(actual_fn: Callable[..., str | list[str]]) -> Callable[..., str | list[str]]:
                return _register(actual_fn, event_name_or_fn)
            return decorator

        if callable(event_name_or_fn):
            return _register(event_name_or_fn, event_name_or_fn.__name__)

        raise TypeError("router() requires at least an event name or a function")

    def persist(
        self,
        save_fn: Callable[[str, dict[str, Any]], None] | None = None,
        load_fn: Callable[[str], dict[str, Any] | None] | None = None,
    ) -> None:
        """Register persistence callbacks (save and/or load)."""
        if save_fn is not None:
            self._persist_handlers.append(save_fn)
        if load_fn is not None:
            self._persist_load_handlers.append(load_fn)

    # ---- helpers (used by adapters; not part of the 4 primitives) ----

    @property
    def start_steps(self) -> list[Callable[..., Any]]:
        return list(self._starts)

    def listeners_for(self, event_name: str) -> list[Callable[..., Any]]:
        return list(self._listeners.get(event_name, []))

    def router_for(self, event_name: str) -> Callable[..., str | list[str]] | None:
        return self._routers.get(event_name)

    def all_listener_events(self) -> list[str]:
        return list(self._listeners.keys())

    def all_router_events(self) -> list[str]:
        return list(self._routers.keys())

    def save_state(self, key: str, data: dict[str, Any]) -> None:
        for saver in self._persist_handlers:
            saver(key, data)

    def load_state(self, key: str) -> dict[str, Any] | None:
        for loader in self._persist_load_handlers:
            data = loader(key)
            if data is not None:
                return data
        return None

    # ---- execution (subclass-implemented) ----

    @abc.abstractmethod
    def kickoff(self, inputs: dict[str, Any] | None = None) -> Any:
        """Start the flow with inputs; return final result."""
        raise NotImplementedError

    @abc.abstractmethod
    def resume(self, flow_id: str) -> Any:
        """Resume from persisted state."""
        raise NotImplementedError
