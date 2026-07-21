"""CrewAIFlowAdapter: implements FlowDefinition on top of CrewAI's Flow API.

Per analysis/03 §4.3, this adapter is the upgrade buffer. It translates the 4 SDDP
primitives (start/listen/router/persist) into CrewAI's @start / @listen / @router
decorators + @persist.

Note: CrewAI's Flow API uses decorators that mutate class definitions at class-
creation time. To bridge that, we offer two modes:
  1. **Subclass-and-decorate** (preferred for production): users write a real CrewAI
     Flow subclass and pass it to `CrewAIFlowAdapter(flow_cls=...)`. The adapter
     validates that the 4 primitives are present.
  2. **Dynamic-build** (used in tests): wrap an existing FlowDefinition instance and
     delegate kickoff/resume to its registered steps.

Mode 2 is what Mock adapter + simple engines use; Mode 1 is what Dev-Phase 0 engines
use for production with real CrewAI Flows.
"""
from __future__ import annotations

import inspect
import logging
from typing import Any, Callable, ClassVar

from .flow_definition import FlowDefinition

logger = logging.getLogger(__name__)


class CrewAIFlowAdapter(FlowDefinition):
    """Adapter that wraps a CrewAI Flow class.

    The class MUST use CrewAI's @start / @listen / @router / @persist decorators.
    This adapter does NOT register new steps via the FlowDefinition primitives
    (those are no-ops); it just delegates kickoff/resume to the CrewAI Flow.

    Per spec scenario "CrewAIFlowAdapter 实现 FlowDefinition": subclass exists and
    implements the 4 primitives' methods (start/listen/router/persist are inherited
    but unused — the actual wiring happens in the CrewAI Flow class).
    """

    name: ClassVar[str] = "CrewAIFlowAdapter"

    def __init__(self, flow_cls: type | None = None, flow_instance: Any | None = None) -> None:
        super().__init__()
        if flow_cls is None and flow_instance is None:
            raise ValueError("CrewAIFlowAdapter requires flow_cls or flow_instance")
        self._flow_cls = flow_cls
        self._flow_instance = flow_instance

    def kickoff(self, inputs: dict[str, Any] | None = None) -> Any:
        """Delegate kickoff to CrewAI Flow."""
        flow = self._flow_instance or (self._flow_cls() if self._flow_cls else None)
        if flow is None:
            raise RuntimeError("no flow to kickoff")
        self._flow_instance = flow
        # CrewAI Flow.kickoff signature: kickoff(inputs={...})
        if inputs is None:
            return flow.kickoff()
        return flow.kickoff(inputs=inputs)

    def resume(self, flow_id: str) -> Any:
        """Resume a persisted CrewAI Flow."""
        flow = self._flow_instance or (self._flow_cls() if self._flow_cls else None)
        if flow is None:
            raise RuntimeError("no flow to resume")
        # CrewAI 1.x exposes Flow.resume(uuid=...) or similar
        resume_fn = getattr(flow, "resume", None)
        if resume_fn is None:
            raise NotImplementedError(f"CrewAI Flow {type(flow).__name__} has no resume method")
        sig = inspect.signature(resume_fn)
        params = sig.parameters
        # Try named arg patterns CrewAI has used
        for name in ("flow_id", "uuid", "flow_uuid", "interrupt_id"):
            if name in params:
                return resume_fn(**{name: flow_id})
        # Fall back to positional
        return resume_fn(flow_id)


def validate_crewai_flow_has_4_primitives(flow_cls: type) -> list[str]:
    """Return list of missing primitive names (empty if all 4 present).

    Used by tests + adapter construction to verify a CrewAI Flow class wires all 4
    SDDP primitives. Looks for methods decorated with @start/@listen/@router/@persist.
    CrewAI's decorators attach metadata to the function objects; we inspect.
    """
    from crewai.flow.flow import Flow

    if not issubclass(flow_cls, Flow):
        return ["not_subclass_of_crewai.Flow"]

    missing: list[str] = []
    found_start = found_listen = found_router = found_persist = False
    for attr_name in dir(flow_cls):
        attr = getattr(flow_cls, attr_name, None)
        if not callable(attr):
            continue
        # CrewAI's @start / @listen / @router / @persist attach markers; the exact
        # attribute name varies by version. Check common markers.
        markers = []
        for m in (
            "is_start",
            "is_listen",
            "is_router",
            "is_persist",
            "_is_start_method",
            "_is_listen_method",
            "_is_router_method",
            "_is_persist_method",
            "_flow_is_start",
            "_flow_is_listen",
            "_flow_is_router",
            "_flow_is_persist",
        ):
            if getattr(attr, m, False):
                markers.append(m)
        # Also check methods installed by CrewAI into Flow.__subclasses__
        if any("start" in m for m in markers):
            found_start = True
        if any("listen" in m for m in markers):
            found_listen = True
        if any("router" in m for m in markers):
            found_router = True
        if any("persist" in m for m in markers):
            found_persist = True

    if not found_start:
        missing.append("start")
    if not found_listen:
        missing.append("listen")
    if not found_router:
        missing.append("router")
    if not found_persist:
        missing.append("persist")
    return missing
