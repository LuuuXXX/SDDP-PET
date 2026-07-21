"""Tests for SafeAgent (D0-2): #6380 mitigation + retry policy + error classification."""
from __future__ import annotations

import asyncio
import os
from typing import Any

import pytest

from sddp.safe_agent.wrapper import (
    ErrorKind,
    ErrorRecord,
    FailureReason,
    SafeAgent,
    SafeAgentError,
    _classify_error,
)


def _set_env_timeout(seconds: int, monkeypatch: pytest.MonkeyPatch):
    """Override SafeAgent timeout via env (spec scenario: SDDP_SAFE_AGENT_TIMEOUT_SECONDS=5)."""
    monkeypatch.setenv("SDDP_SAFE_AGENT_TIMEOUT_SECONDS", str(seconds))


# ---- _classify_error unit tests ----


def test_classify_timeout_is_recoverable():
    kind, rec = _classify_error(asyncio.TimeoutError())
    assert kind == ErrorKind.TIMEOUT
    assert rec is True


def test_classify_connection_error_is_recoverable():
    kind, rec = _classify_error(ConnectionError("refused"))
    assert kind == ErrorKind.CONNECTION
    assert rec is True


def test_classify_value_error_is_non_recoverable():
    kind, rec = _classify_error(ValueError("bad input"))
    assert kind in (ErrorKind.VALIDATION, ErrorKind.PARSE)
    assert rec is False


def test_classify_pydantic_validation_error_is_non_recoverable():
    from pydantic import BaseModel, ValidationError

    class M(BaseModel):
        x: int

    try:
        M(x="not an int")  # type: ignore[arg-type]
    except ValidationError as e:
        kind, rec = _classify_error(e)
        assert rec is False
        assert kind == ErrorKind.VALIDATION


def test_classify_unknown_defaults_to_non_recoverable():
    class WeirdError(Exception):
        pass

    kind, rec = _classify_error(WeirdError("???"))
    assert kind == ErrorKind.UNKNOWN
    assert rec is False


# ---- SafeAgent kickoff core scenarios ----


def test_kickoff_success_returns_result():
    """Plain successful kickoff returns the result unchanged."""
    safe = SafeAgent(name="t", kickoff_fn=lambda inputs: {"out": 42}, timeout_seconds=5, max_retries=0)
    assert safe.kickoff({"x": 1}) == {"out": 42}


def test_kickoff_async_coroutine_success():
    """Wrapped kickoff_fn may be a coroutine."""

    async def good(inputs):
        await asyncio.sleep(0.01)
        return {"ok": True}

    safe = SafeAgent(name="t", kickoff_fn=good, timeout_seconds=5, max_retries=0)
    assert safe.kickoff({}) == {"ok": True}


# ---- #6380 mitigation: timeout DOES NOT freeze (D0-2) ----


def test_6380_timeout_does_not_freeze(monkeypatch: pytest.MonkeyPatch):
    """Reproduces #6380 scenario: async LLM call hangs. SafeAgent MUST abort within timeout.

    Per spec: with SDDP_SAFE_AGENT_TIMEOUT_SECONDS=5, an async kickoff that doesn't return
    MUST raise SafeAgentError within ~5s (not freeze silently).
    """
    _set_env_timeout(1, monkeypatch)  # 1s for test speed

    async def hang_forever(inputs):  # noqa: ARG001
        await asyncio.sleep(60)  # would hang if not for timeout
        return {"never": True}

    safe = SafeAgent(name="hang-test", kickoff_fn=hang_forever, max_retries=1)

    import time as _time
    t0 = _time.monotonic()
    with pytest.raises(SafeAgentError) as exc_info:
        safe.kickoff({})
    elapsed = _time.monotonic() - t0
    # Should complete well within ~10s (1 retry × ~1s timeout)
    assert elapsed < 8, f"SafeAgent froze for {elapsed:.1f}s — #6380 not mitigated"
    err = exc_info.value
    assert err.agent == "hang-test"
    assert err.error_type == ErrorKind.TIMEOUT
    assert err.reason in (FailureReason.RECOVERABLE_EXHAUSTED, FailureReason.NON_RECOVERABLE)
    assert err.attempts >= 1


def test_timeout_env_var_overrides_default(monkeypatch: pytest.MonkeyPatch):
    """Spec: env var override MUST take effect."""
    _set_env_timeout(0.3 if False else 1, monkeypatch)  # must be int; use 1s
    # Build SafeAgent without explicit timeout_seconds — env must apply
    safe = SafeAgent(name="env", kickoff_fn=lambda i: None)  # type: ignore[arg-type]
    assert safe.timeout_seconds == 1  # came from env


# ---- Retry policy: recoverable vs non-recoverable ----


def test_recoverable_retries_then_succeeds():
    """TimeoutError triggers retry; success on 2nd attempt returns result."""
    calls = {"n": 0}

    def flaky(inputs):
        calls["n"] += 1
        if calls["n"] == 1:
            raise asyncio.TimeoutError()
        return {"ok": True, "attempts": calls["n"]}

    safe = SafeAgent(name="flaky", kickoff_fn=flaky, timeout_seconds=5, max_retries=2)
    result = safe.kickoff({})
    assert result["ok"] is True
    assert calls["n"] == 2


def test_recoverable_exhausts_retries_raises_safe_agent_error():
    """Persistent recoverable failure MUST exhaust retries then raise SafeAgentError."""

    def always_timeout(inputs):
        raise asyncio.TimeoutError()

    safe = SafeAgent(name="doom", kickoff_fn=always_timeout, timeout_seconds=2, max_retries=2)
    with pytest.raises(SafeAgentError) as exc_info:
        safe.kickoff({})
    err = exc_info.value
    assert err.reason == FailureReason.RECOVERABLE_EXHAUSTED
    assert err.attempts >= 2


def test_non_recoverable_does_not_retry():
    """ValueError MUST immediately raise SafeAgentError (no retries)."""
    calls = {"n": 0}

    def bad_input(inputs):
        calls["n"] += 1
        raise ValueError("bad input")

    safe = SafeAgent(name="bad", kickoff_fn=bad_input, timeout_seconds=5, max_retries=3)
    with pytest.raises(SafeAgentError) as exc_info:
        safe.kickoff({})
    err = exc_info.value
    assert err.reason == FailureReason.NON_RECOVERABLE
    assert calls["n"] == 1, f"non-recoverable MUST NOT retry; got {calls['n']} calls"


def test_pydantic_validation_error_is_non_recoverable():
    """pydantic.ValidationError MUST NOT retry."""
    from pydantic import BaseModel, ValidationError

    class M(BaseModel):
        x: int

    def bad_output(inputs):
        # Simulate CrewAI output_pydantic validation failure
        try:
            M(x="not int")  # type: ignore[arg-type]
        except ValidationError as e:
            raise e
        return None

    safe = SafeAgent(name="bad-pyd", kickoff_fn=bad_output, timeout_seconds=5, max_retries=3)
    with pytest.raises(SafeAgentError) as exc_info:
        safe.kickoff({})
    assert exc_info.value.reason == FailureReason.NON_RECOVERABLE
    assert exc_info.value.error_type == ErrorKind.VALIDATION


# ---- state.errors recording (spec requirement) ----


def test_failure_recorded_to_state_errors_sink():
    """Spec: each failure MUST append ErrorRecord to state_errors_sink."""
    records: list[ErrorRecord] = []
    safe = SafeAgent(
        name="recorded",
        kickoff_fn=lambda i: (_ for _ in ()).throw(ValueError("bad")),
        timeout_seconds=5,
        max_retries=0,
        state_errors_sink=records.append,
    )
    with pytest.raises(SafeAgentError):
        safe.kickoff({})
    assert len(records) == 1
    r = records[0]
    assert isinstance(r, ErrorRecord)
    assert r.agent == "recorded"
    assert r.recoverable is False
    assert isinstance(r.error_type, str) and r.error_type
    assert isinstance(r.timestamp, str) and r.timestamp
    # to_dict contract
    d = r.to_dict()
    assert {"agent", "error_type", "message", "recoverable", "timestamp"} == set(d.keys())


def test_recoverable_failure_also_recorded():
    """Recoverable failures MUST also be recorded (per attempt)."""
    records: list[ErrorRecord] = []

    def always_timeout(inputs):
        raise asyncio.TimeoutError()

    safe = SafeAgent(
        name="rec-timeout",
        kickoff_fn=always_timeout,
        timeout_seconds=1,
        max_retries=1,
        state_errors_sink=records.append,
    )
    with pytest.raises(SafeAgentError):
        safe.kickoff({})
    # Each retry attempt records once
    assert len(records) >= 1
    assert all(r.recoverable for r in records)
    assert all(r.error_type == ErrorKind.TIMEOUT.value for r in records)
