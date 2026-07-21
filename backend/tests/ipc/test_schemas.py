"""Schema validation tests for WS IPC (D1-4 prerequisite; specs/websocket-ipc Requirement: 5 Push).

Per `analysis/08` §四 contract: every message MUST validate against its Pydantic v2
model; missing required fields MUST raise ValidationError.
"""
from __future__ import annotations

import pytest
from pydantic import ValidationError

from sddp.ipc.schemas import (
    AgentState,
    AgentStateChange,
    CostUpdate,
    DocType,
    DocumentProduced,
    ErrorCode,
    FeedbackMethod,
    FeedbackOutcome,
    FeedbackRequired,
    FlowAborted,
    FlowStarted,
    ErrorMessage,
    Ping,
    Pong,
    Severity,
    StartFlow,
    UserFeedback,
    ResumeFlow,
    AbortFlow,
    parse_message,
)


def _ts() -> str:
    return "2026-07-21T00:00:00+00:00"


# ---- 5 Push messages ----


def test_agent_state_change_valid():
    m = AgentStateChange(timestamp=_ts(), agent="requirement_officer", state=AgentState.WORKING)
    assert m.type == "agent_state_change"
    assert m.flow_id is None  # optional


def test_agent_state_change_rejects_invalid_state():
    with pytest.raises(ValidationError):
        AgentStateChange(timestamp=_ts(), agent="x", state="bogus")  # type: ignore[arg-type]


def test_document_produced_valid():
    m = DocumentProduced(
        timestamp=_ts(), agent="architect", doc_type=DocType.DELTA_SPEC,
        doc_id="delta_spec-fid-1", summary="mock",
    )
    assert m.type == "document_produced"


def test_cost_update_valid():
    m = CostUpdate(
        timestamp=_ts(), total_tokens=100, estimated_cost_usd=0.01,
        round_tokens={"requirement_officer": 50},
    )
    assert m.total_tokens == 100


def test_feedback_required_carries_method():
    m = FeedbackRequired(
        timestamp=_ts(), method=FeedbackMethod.DESIGN_CONFIRMATION,
        message="waiting", output={},
    )
    assert m.method == FeedbackMethod.DESIGN_CONFIRMATION


def test_error_message_requires_known_error_code():
    m = ErrorMessage(
        timestamp=_ts(), error_code=ErrorCode.LLM_TIMEOUT,
        message="timeout", severity=Severity.ERROR, recoverable=True,
    )
    assert m.error_code == ErrorCode.LLM_TIMEOUT

    with pytest.raises(ValidationError):
        ErrorMessage(
            timestamp=_ts(), error_code="NOT_AN_ENUM",  # type: ignore[arg-type]
            message="x",
        )


# ---- 4 RPC requests ----


def test_start_flow_requires_message_id_and_proposal():
    m = StartFlow(
        timestamp=_ts(), message_id="mid-1", proposal="do something",
        project_path="/tmp",
    )
    assert m.message_id == "mid-1"
    with pytest.raises(ValidationError):
        StartFlow(timestamp=_ts(), message_id="mid-1", proposal="x")  # type: ignore[call-arg]


def test_user_feedback_outcome_enum():
    m = UserFeedback(
        timestamp=_ts(), message_id="mid-1", flow_id="fid-1",
        feedback=FeedbackOutcome.Y,
    )
    assert m.feedback == FeedbackOutcome.Y


def test_resume_flow_and_abort_flow_minimum_fields():
    r = ResumeFlow(timestamp=_ts(), message_id="mid-1", flow_id="fid-1")
    a = AbortFlow(timestamp=_ts(), message_id="mid-1", flow_id="fid-1")
    assert r.flow_id == "fid-1"
    assert a.flow_id == "fid-1"


# ---- 4 RPC responses correlated by message_id ----


def test_flow_started_echoes_message_id():
    m = FlowStarted(timestamp=_ts(), message_id="mid-1", flow_id="fid-1")
    assert m.message_id == "mid-1"
    assert m.status.value == "running"


def test_flow_aborted_status():
    m = FlowAborted(timestamp=_ts(), message_id="mid-1", flow_id="fid-1")
    assert m.status.value == "aborted"


# ---- heartbeat ----


def test_ping_pong_shape():
    p = Ping(timestamp=_ts())
    pong = Pong(timestamp=_ts(), ping_timestamp=p.timestamp)
    assert pong.ping_timestamp == p.timestamp


# ---- error_code enum completeness (D1-4 D1-5 contract) ----


def test_error_code_enum_has_all_8_values():
    """All 8 error codes from analysis/00 §七 + DP1 PRIVACY_CONSENT_REQUIRED."""
    expected = {
        "LLM_TIMEOUT", "LLM_AUTH_FAIL", "LLM_RATE_LIMIT", "PARSE_FAILURE",
        "FLOW_STUCK", "KNOWLEDGE_GRAPH_ERROR", "SSH_CONNECTION_LOST", "PRIVACY_CONSENT_REQUIRED",
    }
    actual = {e.value for e in ErrorCode}
    assert actual == expected, f"missing: {expected - actual}; extra: {actual - expected}"


# ---- parse_message dispatch ----


def test_parse_message_dispatches_by_type():
    m = parse_message({
        "type": "agent_state_change", "timestamp": _ts(),
        "agent": "architect", "state": "working",
    })
    assert isinstance(m, AgentStateChange)


def test_parse_message_unknown_type_raises_key_error():
    with pytest.raises(KeyError):
        parse_message({"type": "bogus", "timestamp": _ts()})


def test_parse_message_missing_type_raises_key_error():
    with pytest.raises(KeyError):
        parse_message({"timestamp": _ts()})


def test_parse_message_validation_error_propagates():
    with pytest.raises(ValidationError):
        parse_message({
            "type": "agent_state_change", "timestamp": _ts(),
            "agent": "x", "state": "invalid_state_value",
        })
