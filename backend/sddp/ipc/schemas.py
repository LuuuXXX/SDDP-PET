"""Pydantic v2 schemas for the WebSocket IPC contract (Dev-Phase 1).

Mirrors the TypeScript contract documented in `analysis/08-websocket-ipc-contract.md` §三.
All 9 message types (5 Push + 4 RPC requests) + 4 RPC responses + error_code enum.

Per `specs/websocket-ipc/spec.md`:
  - Every message MUST carry `type` and `timestamp` (ISO 8601 UTC).
  - Non-error messages MUST carry `flow_id`.
  - RPC requests MUST carry `message_id` (UUID v4); RPC responses echo the same `message_id`.
"""

from __future__ import annotations

from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


# ---- error_code enum (specs/websocket-ipc/spec.md Requirement: 5 Push messages) ----


class ErrorCode(str, Enum):
    """Enumerated error codes (analysis/00 §七 + DP1 additions).

    Aligned with DP0 `SafeAgentError` recoverable/non_recoverable distinction.
    """

    LLM_TIMEOUT = "LLM_TIMEOUT"
    LLM_AUTH_FAIL = "LLM_AUTH_FAIL"
    LLM_RATE_LIMIT = "LLM_RATE_LIMIT"
    PARSE_FAILURE = "PARSE_FAILURE"
    FLOW_STUCK = "FLOW_STUCK"
    KNOWLEDGE_GRAPH_ERROR = "KNOWLEDGE_GRAPH_ERROR"
    SSH_CONNECTION_LOST = "SSH_CONNECTION_LOST"
    PRIVACY_CONSENT_REQUIRED = "PRIVACY_CONSENT_REQUIRED"  # DP1 new (D1-10)


class Severity(str, Enum):
    CRITICAL = "critical"
    ERROR = "error"
    WARNING = "warning"


class AgentState(str, Enum):
    WORKING = "working"
    IDLE = "idle"
    WAITING = "waiting"
    ERROR = "error"


class DocType(str, Enum):
    PROPOSAL = "proposal"
    DELTA_SPEC = "delta_spec"
    DELTA_DESIGN = "delta_design"
    ARCHITECTURE_RESEARCH = "architecture_research"
    CODE_SUGGESTIONS = "code_suggestions"


class FeedbackMethod(str, Enum):
    """Confirmation points (specs/cli-runner). DP1: 3 linear points; DP2 adds force-convergence."""

    REQUIREMENT_CONFIRMATION = "requirement_confirmation"
    DESIGN_CONFIRMATION = "design_confirmation"
    TASK_CONFIRMATION = "task_confirmation"
    FORCE_CONVERGENCE = "force_convergence"  # DP2 additive (D2-2): max_rounds escalate


class FlowStatus(str, Enum):
    RUNNING = "running"
    RESUMING = "resuming"
    ABORTED = "aborted"
    COMPLETED = "completed"


class FeedbackOutcome(str, Enum):
    Y = "y"  # approve
    N = "n"  # reject
    E = "e"  # edit


# ---- shared base ----


class _WSMessage(BaseModel):
    """Base: every WS message carries `type` + `timestamp`."""

    model_config = ConfigDict(populate_by_name=True)

    type: str = Field(description="Message type discriminator")
    timestamp: str = Field(description="ISO 8601 UTC timestamp")
    flow_id: str | None = Field(
        default=None,
        description="Associated flow (None only for connection-level errors)",
    )


# ---- 5 Push messages (engine → frontend) ----


class AgentStateChange(_WSMessage):
    type: Literal["agent_state_change"] = "agent_state_change"
    agent: str = Field(
        description="Role name: requirement_officer / orchestrator / architect / executor / code_asset_manager"
    )
    state: AgentState
    phase: str | None = Field(default=None, description="SDDP Phase 0/1/2/3")
    round: int | None = Field(default=None, description="Confrontation round (DP2+)")
    role: str | None = Field(
        default=None,
        description="DP2 additive: architect/critic/empiricist/orchestrator (None in linear flow)",
    )
    detail: str | None = None


class DocumentProduced(_WSMessage):
    type: Literal["document_produced"] = "document_produced"
    agent: str
    doc_type: DocType
    doc_id: str = Field(
        description="Stable identifier (e.g. 'proposal-<flow_id>-<timestamp>')"
    )
    summary: str = Field(
        default="", description="One-paragraph summary for the UI document list"
    )


class CostUpdate(_WSMessage):
    type: Literal["cost_update"] = "cost_update"
    total_tokens: int
    estimated_cost_usd: float
    round_tokens: dict[str, int] = Field(
        default_factory=dict, description="Per-agent token breakdown"
    )


class FeedbackRequired(_WSMessage):
    type: Literal["feedback_required"] = "feedback_required"
    method: FeedbackMethod
    message: str = Field(description="Short prompt to display in window1 bubble")
    output: dict[str, Any] = Field(
        description="Full content awaiting confirmation (passed to window2 ConfirmPanel)"
    )


class ErrorMessage(_WSMessage):
    type: Literal["error"] = "error"
    agent: str | None = None
    error_code: ErrorCode
    message: str
    severity: Severity = Severity.ERROR
    recoverable: bool = True


# ---- 4 RPC requests (frontend → engine) ----


class StartFlow(_WSMessage):
    type: Literal["start_flow"] = "start_flow"
    message_id: str = Field(description="UUID v4 for request-response correlation")
    proposal: str
    pcm: dict[str, Any] | None = Field(
        default=None, description="Project Configuration Manifest; optional"
    )
    project_path: str


class UserFeedback(_WSMessage):
    type: Literal["user_feedback"] = "user_feedback"
    message_id: str
    flow_id: str
    feedback: FeedbackOutcome
    outcome: dict[str, Any] | None = Field(
        default=None, description="Optional edited payload when feedback='e'"
    )


class ResumeFlow(_WSMessage):
    type: Literal["resume_flow"] = "resume_flow"
    message_id: str
    flow_id: str
    feedback: FeedbackOutcome | None = None


class AbortFlow(_WSMessage):
    type: Literal["abort_flow"] = "abort_flow"
    message_id: str
    flow_id: str


# ---- 4 RPC responses (engine → frontend; correlated by message_id) ----


class FlowStarted(_WSMessage):
    type: Literal["flow_started"] = "flow_started"
    message_id: str
    flow_id: str
    status: Literal[FlowStatus.RUNNING] = FlowStatus.RUNNING


class FeedbackAccepted(_WSMessage):
    type: Literal["feedback_accepted"] = "feedback_accepted"
    message_id: str
    flow_id: str
    status: Literal[FlowStatus.RESUMING] = FlowStatus.RESUMING


class FlowResumed(_WSMessage):
    type: Literal["flow_resumed"] = "flow_resumed"
    message_id: str
    flow_id: str
    status: Literal[FlowStatus.RUNNING] = FlowStatus.RUNNING


class FlowAborted(_WSMessage):
    type: Literal["flow_aborted"] = "flow_aborted"
    message_id: str
    flow_id: str
    status: Literal[FlowStatus.ABORTED] = FlowStatus.ABORTED


# ---- heartbeat (application-layer, NOT RFC 6455 — Decision 3) ----


class Ping(_WSMessage):
    type: Literal["ping"] = "ping"


class Pong(_WSMessage):
    type: Literal["pong"] = "pong"
    ping_timestamp: str = Field(
        description="Echo of the ping timestamp being acknowledged"
    )


# ---- registry & parse dispatch ----


PUSH_MODELS = {
    "agent_state_change": AgentStateChange,
    "document_produced": DocumentProduced,
    "cost_update": CostUpdate,
    "feedback_required": FeedbackRequired,
    "error": ErrorMessage,
}

RPC_REQUEST_MODELS = {
    "start_flow": StartFlow,
    "user_feedback": UserFeedback,
    "resume_flow": ResumeFlow,
    "abort_flow": AbortFlow,
}

RPC_RESPONSE_MODELS = {
    "flow_started": FlowStarted,
    "feedback_accepted": FeedbackAccepted,
    "flow_resumed": FlowResumed,
    "flow_aborted": FlowAborted,
}

HEARTBEAT_MODELS = {
    "ping": Ping,
    "pong": Pong,
}

ALL_MODELS: dict[str, type[_WSMessage]] = {
    **PUSH_MODELS,
    **RPC_REQUEST_MODELS,
    **RPC_RESPONSE_MODELS,
    **HEARTBEAT_MODELS,
}


def parse_message(raw: dict[str, Any]) -> _WSMessage:
    """Parse a raw dict into the correct message subclass by `type` discriminator.

    Raises `KeyError` for unknown `type`; raises `pydantic.ValidationError` for
    structurally invalid payloads. Callers MUST catch both and emit an
    `ErrorMessage(error_code=PARSE_FAILURE, recoverable=True)` Push back to the
    client (per `specs/websocket-ipc/spec.md` "非法 JSON 消息被拒绝且不崩连接" scenario).
    """
    msg_type = raw.get("type")
    if msg_type is None:
        raise KeyError("message missing `type` field")
    cls = ALL_MODELS.get(msg_type)
    if cls is None:
        raise KeyError(f"unknown message `type`: {msg_type!r}")
    return cls.model_validate(raw)


__all__ = [
    "ErrorCode",
    "Severity",
    "AgentState",
    "DocType",
    "FeedbackMethod",
    "FlowStatus",
    "FeedbackOutcome",
    "AgentStateChange",
    "DocumentProduced",
    "CostUpdate",
    "FeedbackRequired",
    "ErrorMessage",
    "StartFlow",
    "UserFeedback",
    "ResumeFlow",
    "AbortFlow",
    "FlowStarted",
    "FeedbackAccepted",
    "FlowResumed",
    "FlowAborted",
    "Ping",
    "Pong",
    "PUSH_MODELS",
    "RPC_REQUEST_MODELS",
    "RPC_RESPONSE_MODELS",
    "HEARTBEAT_MODELS",
    "ALL_MODELS",
    "parse_message",
]
