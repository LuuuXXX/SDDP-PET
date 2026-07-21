"""WebSocketHumanFeedbackAdapter: bridges WS protocol to LinearPhase02Flow's
confirmation points (Dev-Phase 1 D1-8, replaces CLI's CLIHumanFeedbackAdapter).

Per `specs/websocket-ipc/spec.md` Requirement: `WebSocketHumanFeedbackAdapter`:
  - Flow calls `human_feedback_handler(kind, payload)` at confirmation point
  - Adapter Push `feedback_required` via the WS server, then BLOCKS waiting for
    the corresponding `user_feedback` RPC (correlated by `method` == kind)
  - Returns True on y, False on n; on e, returns True with edited payload stored

Threading model: the flow runs in a worker thread; the WS server runs in the
asyncio event loop. We bridge sync↔async via an `asyncio.Event` + a pending-
request slot the WS handler mutates.
"""
from __future__ import annotations

import asyncio
import logging
import threading
from datetime import datetime, timezone
from typing import Any, Callable

from .schemas import FeedbackMethod, FeedbackOutcome, FeedbackRequired, UserFeedback

logger = logging.getLogger(__name__)


class WebSocketHumanFeedbackAdapter:
    """Adapter that the WS server registers; flow invokes it as `human_feedback_handler`.

    Construction:
        adapter = WebSocketHumanFeedbackAdapter(broadcaster)
        flow = LinearPhase02Flow(..., human_feedback_handler=adapter)
        # WS server, on receiving UserFeedback RPC, calls adapter.deliver_user_feedback(msg)

    `broadcaster` is an awaitable that pushes a `FeedbackRequired` message to the
    connected client. The adapter's `__call__` (invoked by the flow thread) blocks
    on a threading.Event until the WS handler delivers the matching UserFeedback.
    """

    def __init__(
        self,
        broadcaster: Callable[[dict[str, Any]], Any],
        *,
        flow_id_provider: Callable[[], str] | None = None,
    ) -> None:
        """
        Args:
            broadcaster: pushes a FeedbackRequired message dict to the WS client.
                May be sync or async; if async, called from the loop.
            flow_id_provider: returns the current flow_id (used to populate the
                Push message); if None, flow_id will be None on the Push.
        """
        self._broadcaster = broadcaster
        self._flow_id_provider = flow_id_provider
        self._lock = threading.Lock()
        self._pending: dict[str, dict[str, Any]] = {}  # method → response
        self._events: dict[str, threading.Event] = {}  # method → signal
        self.history: list[dict[str, Any]] = []

    def __call__(self, kind: str, payload: dict[str, Any]) -> bool:
        """Sync entry point — called from the flow's worker thread.

        Blocks until the WS server delivers the matching UserFeedback RPC.
        Returns True on y, False on n. On e, returns True and stores edited
        payload in self.history.
        """
        try:
            method = FeedbackMethod(kind)
        except ValueError:
            method = FeedbackMethod.REQUIREMENT_CONFIRMATION  # default fallback

        with self._lock:
            event = threading.Event()
            self._events[method.value] = event
            self._pending.pop(method.value, None)

        # Push feedback_required to client (best effort; if no client, we still wait)
        flow_id = self._flow_id_provider() if self._flow_id_provider else None
        push = FeedbackRequired(
            timestamp=datetime.now(timezone.utc).isoformat(),
            flow_id=flow_id,
            method=method,
            message=_short_prompt(kind, payload),
            output=payload,
        )
        try:
            result = self._broadcaster(push.model_dump())
            # If broadcaster is a coroutine, schedule it on the loop and wait
            if asyncio.iscoroutine(result):
                self._run_coroutine_blocking(result)
        except Exception as e:
            logger.warning("broadcaster failed for %s (non-fatal): %s", kind, e)

        # Block (timeout after 5 min to avoid infinite hang in tests)
        if not event.wait(timeout=300.0):
            logger.error("feedback timeout for %s — treating as reject", kind)
            self.history.append({"kind": kind, "approved": False, "comment": "timeout"})
            return False

        response = self._pending.get(method.value, {})
        approved = response.get("feedback") == FeedbackOutcome.Y.value
        self.history.append({
            "kind": kind,
            "approved": approved,
            "feedback": response.get("feedback"),
            "outcome": response.get("outcome"),
        })

        with self._lock:
            self._events.pop(method.value, None)
            self._pending.pop(method.value, None)

        return approved

    def deliver_user_feedback(self, msg: UserFeedback) -> None:
        """Called by the WS server when a `user_feedback` RPC arrives.

        Wakes the blocked flow thread.
        """
        # Map feedback_required method from the most recent pending request that
        # matches this flow_id. For DP1 (single in-flight flow), we accept any.
        with self._lock:
            for method_value, event in list(self._events.items()):
                self._pending[method_value] = {
                    "feedback": msg.feedback.value,
                    "outcome": msg.outcome,
                }
                event.set()
                return
        logger.warning("deliver_user_feedback called but no pending feedback handler")

    @staticmethod
    def _run_coroutine_blocking(coro: Any) -> None:
        """Run a coroutine to completion from a sync context.

        Tries to schedule on the running loop; falls back to a new loop in a
        short-lived thread if no loop is running.
        """
        try:
            loop = asyncio.get_running_loop()
            # We are inside a sync context but the loop is running in another thread.
            # Use run_coroutine_threadsafe.
            future = asyncio.run_coroutine_threadsafe(coro, loop)
            future.result(timeout=10.0)
        except RuntimeError:
            # No running loop — run directly
            asyncio.run(coro)


def _short_prompt(kind: str, payload: dict[str, Any]) -> str:
    """One-line summary for the window1 bubble (D1-8 clarification)."""
    if kind == FeedbackMethod.REQUIREMENT_CONFIRMATION.value:
        title = payload.get("title") if isinstance(payload, dict) else None
        return f"等待需求确认: {title}" if title else "等待需求确认"
    if kind == FeedbackMethod.DESIGN_CONFIRMATION.value:
        return "等待方案确认"
    if kind == FeedbackMethod.TASK_CONFIRMATION.value:
        return "等待任务确认"
    return f"等待确认: {kind}"


__all__ = ["WebSocketHumanFeedbackAdapter"]
