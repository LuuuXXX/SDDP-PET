"""Tests for state.errors recording (spec requirement 2)."""
from __future__ import annotations

import pytest

from sddp.safe_agent.wrapper import ErrorKind, ErrorRecord, SafeAgent, SafeAgentError


def test_state_errors_record_has_all_required_fields():
    """ErrorRecord MUST expose agent/error_type/message/recoverable/timestamp (spec)."""
    r = ErrorRecord(agent="x", error_type="timeout", message="...", recoverable=True)
    d = r.to_dict()
    assert set(d.keys()) == {"agent", "error_type", "message", "recoverable", "timestamp"}
    assert d["agent"] == "x"
    assert d["recoverable"] is True
    assert d["error_type"] == "timeout"


def test_multiple_failures_each_recorded():
    """Each retry attempt MUST append its own record (not just the final)."""
    records: list[ErrorRecord] = []
    attempts = {"n": 0}

    def fails_twice_then_non_rec(inputs):
        attempts["n"] += 1
        if attempts["n"] <= 2:
            raise ConnectionError("transient")
        raise ValueError("bad input")

    safe = SafeAgent(
        name="multi",
        kickoff_fn=fails_twice_then_non_rec,
        timeout_seconds=5,
        max_retries=3,
        state_errors_sink=records.append,
    )
    with pytest.raises(SafeAgentError):
        safe.kickoff({})
    # 2 connection errors (recoverable, retried) + 1 ValueError (non-recoverable, raised)
    assert len(records) == 3
    assert records[0].recoverable is True
    assert records[0].error_type == ErrorKind.CONNECTION.value
    assert records[-1].recoverable is False


def test_sink_exception_does_not_break_safeagent():
    """If state_errors_sink raises, SafeAgent MUST NOT propagate the sink error."""

    def broken_sink(record):
        raise RuntimeError("sink broken")

    safe = SafeAgent(
        name="sink-broken",
        kickoff_fn=lambda i: (_ for _ in ()).throw(ValueError("x")),
        timeout_seconds=5,
        max_retries=0,
        state_errors_sink=broken_sink,
    )
    # Should raise SafeAgentError (not RuntimeError)
    with pytest.raises(SafeAgentError):
        safe.kickoff({})
