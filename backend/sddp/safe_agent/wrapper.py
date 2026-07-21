"""SafeAgent: wraps CrewAI Agent kickoff calls to mitigate #6380 (async silent freeze).

Per analysis/03-crewai-version-strategy.md §五: SafeAgent is a HARD prerequisite
regardless of CrewAI version, because #6380 has no upstream fix.

Contract (specs/safe-agent-wrapper/spec.md):
  - kickoff(input) sync entry; internally uses asyncio.wait_for + tenacity retry
  - Retries ONLY on TimeoutError / ConnectionError / RateLimitError (recoverable)
  - NEVER retries on ValueError / ParseError / ValidationError (non-recoverable)
  - Records every failure to state.errors (CrewAI Flow state integration)
  - Default timeout 120s, default max retries 3 — overridable via env vars
"""
from __future__ import annotations

import asyncio
import logging
import os
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable, TypeVar

from tenacity import (
    AsyncRetrying,
    RetryError,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

logger = logging.getLogger(__name__)

T = TypeVar("T")


class ErrorKind(str, Enum):
    """Categorized error kinds for state.errors entries."""

    TIMEOUT = "timeout"
    CONNECTION = "connection"
    RATE_LIMIT = "rate_limit"
    PARSE = "parse"
    VALIDATION = "validation"
    UNKNOWN = "unknown"


class FailureReason(str, Enum):
    """Why SafeAgent gave up (attached to SafeAgentError.reason)."""

    RECOVERABLE_EXHAUSTED = "recoverable_exhausted"  # retried N times, still failing
    NON_RECOVERABLE = "non_recoverable"  # not retried at all
    TIMEOUT_TOTAL = "timeout_total"  # whole call exceeded total budget


# Exception types considered recoverable (per analysis/03 §五).
# OpenAI's RateLimitError is imported lazily because openai may not be installed in unit tests.
def _recoverable_exception_types() -> tuple[type[BaseException], ...]:
    types: list[type[BaseException]] = [asyncio.TimeoutError, ConnectionError, TimeoutError]
    try:
        from openai import RateLimitError
        types.append(RateLimitError)
    except ImportError:
        # In tests without openai, fall back to a marker; SafeAgent will still
        # treat openai.RateLimitError subclasses of OpenAIError if present at runtime
        pass
    try:
        from httpx import HTTPStatusError
        # Don't blanket-retry HTTPStatusError; only 429 — checked in _classify_error.
    except ImportError:
        pass
    return tuple(types)


# Exception types considered non-recoverable.
def _non_recoverable_exception_types() -> tuple[type[BaseException], ...]:
    types: list[type[BaseException]] = [ValueError, TypeError, KeyError]
    try:
        from pydantic import ValidationError
        types.append(ValidationError)
    except ImportError:
        pass
    return tuple(types)


@dataclass
class SafeAgentError(Exception):
    """Raised when SafeAgent exhausts retries OR receives a non-recoverable error.

    Per spec: MUST expose agent / error_type / reason / original_exception.
    """

    agent: str
    error_type: ErrorKind
    reason: FailureReason
    original_exception: BaseException
    message: str = ""
    attempts: int = 0

    def __str__(self) -> str:  # pragma: no cover - trivial
        return (
            f"SafeAgentError(agent={self.agent!r}, error_type={self.error_type.value}, "
            f"reason={self.reason.value}, attempts={self.attempts}): "
            f"{self.message or type(self.original_exception).__name__}"
        )


@dataclass
class ErrorRecord:
    """One entry in state.errors (spec: MUST contain agent/error_type/message/recoverable/timestamp)."""

    agent: str
    error_type: str
    message: str
    recoverable: bool
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _classify_error(exc: BaseException) -> tuple[ErrorKind, bool]:
    """Classify an exception into (ErrorKind, recoverable). Default = unknown/non-recoverable."""
    recoverable_types = _recoverable_exception_types()
    non_recoverable_types = _non_recoverable_exception_types()

    # Check non-recoverable first (more specific)
    if isinstance(exc, non_recoverable_types):
        if isinstance(exc, Exception) and "validation" in type(exc).__name__.lower():
            return ErrorKind.VALIDATION, False
        if isinstance(exc, ValueError):
            # Pydantic raises ValueError subclasses; detect ParseError by name
            if "parse" in type(exc).__name__.lower():
                return ErrorKind.PARSE, False
            return ErrorKind.VALIDATION, False
        return ErrorKind.UNKNOWN, False

    if isinstance(exc, recoverable_types):
        if isinstance(exc, asyncio.TimeoutError) or isinstance(exc, TimeoutError):
            return ErrorKind.TIMEOUT, True
        if "rate" in type(exc).__name__.lower():
            return ErrorKind.RATE_LIMIT, True
        return ErrorKind.CONNECTION, True

    # HTTP 429 detection via openai/httpx
    exc_class_name = type(exc).__name__.lower()
    if "ratelimit" in exc_class_name:
        return ErrorKind.RATE_LIMIT, True
    if "timeout" in exc_class_name:
        return ErrorKind.TIMEOUT, True
    if "connection" in exc_class_name or "conn" in exc_class_name:
        return ErrorKind.CONNECTION, True

    # Default per spec: recoverable=False, immediately raise
    return ErrorKind.UNKNOWN, False


def _env_int(name: str, default: int) -> int:
    """Read an int from env var; fall back to default on parse failure."""
    raw = os.environ.get(name)
    if raw is None:
        return default
    try:
        return int(raw)
    except ValueError:
        logger.warning("invalid int for %s=%r; using default %d", name, raw, default)
        return default


class SafeAgent:
    """Wraps a callable (typically CrewAI Agent kickoff) with timeout + retry + error classification.

    Usage:
        safe = SafeAgent(name="architect", kickoff_fn=agent.kickoff)
        result = safe.kickoff(inputs)

    The wrapped callable may be sync or async; SafeAgent.kickoff is sync and runs the
    underlying coroutine via asyncio.run (with timeout enforced via asyncio.wait_for).

    For Dev-Phase 0, state_errors_sink is an optional callable that accepts an ErrorRecord.
    In later phases, the CrewAI Flow state's `errors` list is the sink.
    """

    DEFAULT_TIMEOUT_SECONDS = 120
    DEFAULT_MAX_RETRIES = 3

    def __init__(
        self,
        name: str,
        kickoff_fn: Callable[..., Any] | Any,
        *,
        timeout_seconds: int | None = None,
        max_retries: int | None = None,
        state_errors_sink: Callable[[ErrorRecord], None] | None = None,
    ) -> None:
        self.name = name
        self._kickoff_fn = kickoff_fn
        self.timeout_seconds = timeout_seconds if timeout_seconds is not None else _env_int(
            "SDDP_SAFE_AGENT_TIMEOUT_SECONDS", self.DEFAULT_TIMEOUT_SECONDS
        )
        self.max_retries = max_retries if max_retries is not None else _env_int(
            "SDDP_SAFE_AGENT_MAX_RETRIES", self.DEFAULT_MAX_RETRIES
        )
        self._state_errors_sink = state_errors_sink

    # ---- public ----

    def kickoff(self, inputs: Any = None) -> Any:
        """Run the wrapped kickoff with timeout + retry. Sync entry.

        Raises SafeAgentError on exhaustion or non-recoverable failure.
        """
        return self._run_sync(inputs)

    async def kickoff_async(self, inputs: Any = None) -> Any:
        """Async entry — same protection, no asyncio.run wrapping."""
        return await self._run_with_protection(inputs)

    # ---- internal ----

    def _run_sync(self, inputs: Any) -> Any:
        """Run async protection from sync context. Uses asyncio.run."""
        try:
            return asyncio.run(self._run_with_protection(inputs))
        except SafeAgentError:
            raise
        except RuntimeError as e:
            if "async event loop already running" in str(e):
                # Already in async context — caller should use kickoff_async
                raise SafeAgentError(
                    agent=self.name,
                    error_type=ErrorKind.UNKNOWN,
                    reason=FailureReason.NON_RECOVERABLE,
                    original_exception=e,
                    message="kickoff() called from running event loop; use kickoff_async() instead",
                )
            raise

    async def _run_with_protection(self, inputs: Any) -> Any:
        """Inner: tenacity retry + asyncio.wait_for timeout.

        Strategy:
          - Non-recoverable errors → raise SafeAgentError immediately (tenacity stops
            because SafeAgentError is not in retry_if_exception_type list).
          - Recoverable errors → tenacity retries; on exhaustion we catch the
            reraised original and wrap into SafeAgentError with reason=RECOVERABLE_EXHAUSTED.
        """
        recoverable_types = _recoverable_exception_types()
        attempt_counter = {"n": 0}

        try:
            async for attempt in AsyncRetrying(
                stop=stop_after_attempt(self.max_retries + 1),
                wait=wait_exponential(multiplier=1, min=1, max=10),
                retry=retry_if_exception_type(recoverable_types),
                reraise=True,
            ):
                with attempt:
                    attempt_counter["n"] += 1
                    try:
                        return await asyncio.wait_for(
                            self._invoke(inputs),
                            timeout=self.timeout_seconds,
                        )
                    except recoverable_types as exc:
                        # Recoverable: record and let tenacity decide (retry if budget left)
                        self._record_failure(exc, recoverable=True, attempt=attempt_counter["n"])
                        raise
                    except Exception as exc:
                        # Non-recoverable: record, then raise SafeAgentError (which tenacity
                        # will NOT retry because it's not in recoverable_types)
                        kind, _ = _classify_error(exc)
                        self._record_failure(exc, recoverable=False, attempt=attempt_counter["n"])
                        raise SafeAgentError(
                            agent=self.name,
                            error_type=kind,
                            reason=FailureReason.NON_RECOVERABLE,
                            original_exception=exc,
                            message=str(exc) or type(exc).__name__,
                            attempts=attempt_counter["n"],
                        ) from exc
        except recoverable_types as exc:
            # Retries exhausted; tenacity reraised the last recoverable error.
            kind, _ = _classify_error(exc)
            self._record_failure(exc, recoverable=True, attempt=attempt_counter["n"])
            raise SafeAgentError(
                agent=self.name,
                error_type=kind,
                reason=FailureReason.RECOVERABLE_EXHAUSTED,
                original_exception=exc,
                message=f"exhausted {self.max_retries} retries: {exc}",
                attempts=attempt_counter["n"],
            ) from exc

    async def _invoke(self, inputs: Any) -> Any:
        """Invoke the wrapped kickoff_fn. Handles sync vs async callables."""
        fn = self._kickoff_fn
        try:
            result = fn(inputs) if inputs is not None else fn()
        except TypeError:
            # Maybe fn takes no args
            result = fn()
        if asyncio.iscoroutine(result):
            return await result
        return result

    def _record_failure(self, exc: BaseException, *, recoverable: bool, attempt: int) -> None:
        kind, _ = _classify_error(exc)
        record = ErrorRecord(
            agent=self.name,
            error_type=kind.value,
            message=f"{type(exc).__name__}: {exc}"[:500],
            recoverable=recoverable,
        )
        if self._state_errors_sink is not None:
            try:
                self._state_errors_sink(record)
            except Exception:  # pragma: no cover
                logger.warning("state_errors_sink raised; ignoring", exc_info=True)
        logger.info(
            "SafeAgent %s failure #%d kind=%s recoverable=%s: %s",
            self.name, attempt, kind.value, recoverable, type(exc).__name__,
        )
