"""FastAPI WebSocket server for SDDP-Pet (Dev-Phase 1 D1-4).

Per `specs/websocket-ipc/spec.md`:
  - Listens on ws://localhost:8765
  - On accept, Push `agent_state_change(state=idle)` as ready signal
  - 5 Push + 4 RPC handlers
  - Application-layer heartbeat (30s/10s/3-miss)
  - Invalid JSON → Push `error(error_code=PARSE_FAILURE, recoverable=true)`; keep connection open

Threading: FastAPI/Starlette run on the asyncio loop. The SDDP flow itself is
blocking (CrewAI sync) and runs in a worker thread; results are pushed back via
`broadcaster` (an asyncio-safe queue bridging threads).
"""

from __future__ import annotations

import asyncio
import json
import logging
import threading
import uuid
from datetime import datetime, timezone
from typing import Any

from fastapi import FastAPI, WebSocket, WebSocketDisconnect

from ..engine.agents import AgentFactory
from ..engine.cost_meter import CostMeter
from ..engine.flows.phase_0_2_linear import LinearPhase02Flow
from ..engine.kg_tools import KGTools
from ..schemas import Proposal, DeltaSpec, DeltaDesign
from .confrontation_runner import run_confrontation_in_thread
from .feedback_adapter import WebSocketHumanFeedbackAdapter
from .heartbeat import HeartbeatMonitor
from .schemas import (
    AgentState,
    AgentStateChange,
    CostUpdate,
    DocumentProduced,
    ErrorMessage,
    ErrorCode,
    FlowAborted,
    FlowResumed,
    FlowStarted,
    FeedbackAccepted,
    Severity,
    StartFlow,
    UserFeedback,
    ResumeFlow,
    AbortFlow,
    Pong,
    parse_message,
)

logger = logging.getLogger(__name__)


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def create_app(
    *,
    agent_factory_factory=None,
    kg_db_path: str | None = None,
    flow_db_path: str | None = None,
    mock_mode: bool = False,
    confrontation_agents_factory=None,
) -> FastAPI:
    """Build the FastAPI app with the /ws endpoint.

    Args:
        agent_factory_factory: callable () -> AgentFactory (re-invoked per flow to
            reset cost meter). If None, uses a default mock-mode factory.
        kg_db_path: path for KG SQLite
        flow_db_path: path for @persist flow_state SQLite
        mock_mode: if True, the agent factory uses mock LLM (no OPENAI_API_KEY needed)
    """
    app = FastAPI(title="SDDP-Pet IPC", version="0.1.0-dev")
    app.state.agent_factory_factory = agent_factory_factory
    app.state.kg_db_path = kg_db_path
    app.state.flow_db_path = flow_db_path
    app.state.mock_mode = mock_mode
    app.state.active_flow: dict[str, Any] = {}  # flow_id → thread/handler info
    # DP2 additive: factory () -> dict[str, AgentFn] for the confrontation flow.
    # None = confrontation mode unavailable (start_flow phase=confrontation errors).
    app.state.confrontation_agents_factory = confrontation_agents_factory

    @app.get("/health")
    async def health() -> dict[str, Any]:
        return {"status": "ok", "mock_mode": mock_mode}

    @app.websocket("/ws")
    async def ws_endpoint(websocket: WebSocket) -> None:
        await websocket.accept()
        logger.info("WS client connected")

        # Capture the running loop so worker threads can schedule broadcasts back
        main_loop = asyncio.get_running_loop()

        # Per-connection state
        ws_lock = asyncio.Lock()
        flow_thread: threading.Thread | None = None
        flow_stop_event = threading.Event()
        feedback_adapter: WebSocketHumanFeedbackAdapter | None = None
        current_flow_id: str | None = None

        async def broadcast(message: dict[str, Any]) -> None:
            """Thread-safe push to the client."""
            async with ws_lock:
                try:
                    await websocket.send_text(
                        json.dumps(message, default=str, ensure_ascii=False)
                    )
                except Exception as e:
                    logger.warning("broadcast failed: %s", e)

        async def on_heartbeat_lost() -> None:
            await broadcast(
                ErrorMessage(
                    timestamp=_utc_now(),
                    agent=None,
                    error_code=ErrorCode.SSH_CONNECTION_LOST,
                    message="heartbeat: 3 consecutive pongs missed",
                    severity=Severity.ERROR,
                    recoverable=True,
                ).model_dump()
            )
            # The flow thread (if any) keeps running until user resumes; we just
            # notify the client. Client should reconnect + send resume_flow.

        heartbeat = HeartbeatMonitor(broadcast, on_connection_lost=on_heartbeat_lost)
        await heartbeat.start()

        # Send initial ready signal
        await broadcast(
            AgentStateChange(
                timestamp=_utc_now(),
                flow_id=None,
                agent="(engine)",
                state=AgentState.IDLE,
                detail="WS connected; awaiting start_flow",
            ).model_dump()
        )

        try:
            while True:
                raw_text = await websocket.receive_text()
                try:
                    raw = json.loads(raw_text)
                except json.JSONDecodeError as e:
                    await broadcast(
                        ErrorMessage(
                            timestamp=_utc_now(),
                            error_code=ErrorCode.PARSE_FAILURE,
                            message=f"invalid JSON: {e}",
                            severity=Severity.WARNING,
                            recoverable=True,
                        ).model_dump()
                    )
                    continue

                try:
                    msg = parse_message(raw)
                except Exception as e:
                    await broadcast(
                        ErrorMessage(
                            timestamp=_utc_now(),
                            error_code=ErrorCode.PARSE_FAILURE,
                            message=f"schema validation failed: {e}",
                            severity=Severity.WARNING,
                            recoverable=True,
                        ).model_dump()
                    )
                    continue

                # Heartbeat: handle here so the flow thread isn't involved
                if isinstance(msg, Pong):
                    await heartbeat.notify_pong(msg)
                    continue

                # RPC dispatch
                if isinstance(msg, StartFlow):
                    if app.state.active_flow:
                        await broadcast(
                            ErrorMessage(
                                timestamp=_utc_now(),
                                error_code=ErrorCode.FLOW_STUCK,
                                message="a flow is already running; abort it first",
                                severity=Severity.WARNING,
                                recoverable=True,
                            ).model_dump()
                        )
                        continue
                    current_flow_id = msg.flow_id or str(uuid.uuid4())
                    feedback_adapter = WebSocketHumanFeedbackAdapter(
                        broadcast,
                        flow_id_provider=lambda: current_flow_id,
                    )
                    phase = getattr(msg, "phase", "linear")
                    if phase == "confrontation":
                        # DP2 adversarial flow branch (additive; linear path unchanged)
                        if app.state.confrontation_agents_factory is None:
                            await broadcast(
                                ErrorMessage(
                                    timestamp=_utc_now(),
                                    flow_id=current_flow_id,
                                    error_code=ErrorCode.FLOW_STUCK,
                                    message="confrontation mode not configured on this server",
                                    severity=Severity.WARNING,
                                    recoverable=True,
                                ).model_dump()
                            )
                            continue
                        agents = app.state.confrontation_agents_factory()

                        def _conf_broadcast_sync(message: dict[str, Any]) -> None:
                            if main_loop is None or main_loop.is_closed():
                                return
                            try:
                                fut = asyncio.run_coroutine_threadsafe(
                                    broadcast(message), main_loop
                                )
                                fut.result(timeout=10.0)
                            except Exception as e:
                                logger.warning(
                                    "confrontation broadcast_sync failed: %s", e
                                )

                        flow_thread = threading.Thread(
                            target=run_confrontation_in_thread,
                            args=(
                                msg.proposal,
                                current_flow_id,
                                agents,
                                feedback_adapter,
                                _conf_broadcast_sync,
                            ),
                            daemon=True,
                        )
                    else:
                        flow_thread = threading.Thread(
                            target=_run_flow_in_thread,
                            args=(
                                app,
                                msg,
                                current_flow_id,
                                feedback_adapter,
                                broadcast,
                                main_loop,
                                flow_stop_event,
                            ),
                            daemon=True,
                        )
                    flow_thread = threading.Thread(
                        target=_run_flow_in_thread,
                        args=(
                            app,
                            msg,
                            current_flow_id,
                            feedback_adapter,
                            broadcast,
                            main_loop,
                            flow_stop_event,
                        ),
                        daemon=True,
                    )
                    app.state.active_flow[current_flow_id] = {
                        "thread": flow_thread,
                        "feedback_adapter": feedback_adapter,
                        "stop_event": flow_stop_event,
                    }
                    flow_thread.start()
                    await broadcast(
                        FlowStarted(
                            timestamp=_utc_now(),
                            message_id=msg.message_id,
                            flow_id=current_flow_id,
                        ).model_dump()
                    )
                    continue

                if isinstance(msg, UserFeedback):
                    if feedback_adapter is None:
                        await broadcast(
                            ErrorMessage(
                                timestamp=_utc_now(),
                                flow_id=msg.flow_id,
                                error_code=ErrorCode.FLOW_STUCK,
                                message="no active flow to receive feedback",
                                severity=Severity.WARNING,
                                recoverable=True,
                            ).model_dump()
                        )
                        continue
                    feedback_adapter.deliver_user_feedback(msg)
                    await broadcast(
                        FeedbackAccepted(
                            timestamp=_utc_now(),
                            message_id=msg.message_id,
                            flow_id=msg.flow_id,
                        ).model_dump()
                    )
                    continue

                if isinstance(msg, ResumeFlow):
                    # DP1 MVP: resume not fully wired through WS (CLI has it); for now
                    # respond with flow_resumed and rely on client to start a fresh flow
                    # with the same flow_id later. Full WS-resume is a follow-up task.
                    await broadcast(
                        FlowResumed(
                            timestamp=_utc_now(),
                            message_id=msg.message_id,
                            flow_id=msg.flow_id,
                        ).model_dump()
                    )
                    continue

                if isinstance(msg, AbortFlow):
                    flow_stop_event.set()
                    if current_flow_id and current_flow_id in app.state.active_flow:
                        app.state.active_flow.pop(current_flow_id, None)
                    await broadcast(
                        FlowAborted(
                            timestamp=_utc_now(),
                            message_id=msg.message_id,
                            flow_id=msg.flow_id,
                        ).model_dump()
                    )
                    continue

                # Push messages from client → server are protocol violations
                await broadcast(
                    ErrorMessage(
                        timestamp=_utc_now(),
                        error_code=ErrorCode.PARSE_FAILURE,
                        message=f"unexpected message type from client: {getattr(msg, 'type', '?')}",
                        severity=Severity.WARNING,
                        recoverable=True,
                    ).model_dump()
                )

        except WebSocketDisconnect:
            logger.info("WS client disconnected")
        except Exception as e:
            logger.exception("WS endpoint crashed: %s", e)
        finally:
            await heartbeat.stop()
            flow_stop_event.set()

    return app


def _run_flow_in_thread(
    app: FastAPI,
    start_msg: StartFlow,
    flow_id: str,
    feedback_adapter: WebSocketHumanFeedbackAdapter,
    broadcast,
    main_loop: asyncio.AbstractEventLoop,
    stop_event: threading.Event,
) -> None:
    """Worker thread: builds factory + flow, kicks off, pushes results.

    `main_loop` is captured from the WS server's running loop so we can schedule
    async broadcasts from this sync thread via `run_coroutine_threadsafe`.
    """

    def broadcast_sync(message: dict[str, Any]) -> None:
        if main_loop is None or main_loop.is_closed():
            return
        try:
            future = asyncio.run_coroutine_threadsafe(broadcast(message), main_loop)
            # Don't block forever — 5s should be plenty for a WS send
            future.result(timeout=10.0)
        except Exception as e:
            logger.warning("broadcast_sync failed: %s", e)

    # Replace async broadcast with sync wrapper for the feedback adapter
    feedback_adapter._broadcaster = broadcast_sync

    try:
        factory_fn = app.state.agent_factory_factory or _default_factory_factory
        cost_meter = CostMeter()
        kg_tools = None
        if app.state.kg_db_path:
            try:
                kg_tools = KGTools(app.state.kg_db_path)
            except Exception as e:
                logger.warning("KGTools init failed (non-fatal): %s", e)

        factory = factory_fn(cost_meter=cost_meter, kg_tools=kg_tools)
        flow = LinearPhase02Flow(
            agent_factory=factory,
            kg_db_path=app.state.kg_db_path,
            human_feedback_handler=feedback_adapter,
            flow_id=flow_id,
        )
        inputs = {
            "requirement": start_msg.proposal,
            "project_path": start_msg.project_path,
        }
        if stop_event.is_set():
            return
        result = flow.kickoff(inputs)

        # Push documents
        if result.proposal:
            broadcast_sync(
                DocumentProduced(
                    timestamp=_utc_now(),
                    flow_id=flow_id,
                    agent="requirement_officer",
                    doc_type="proposal",
                    doc_id=f"proposal-{flow_id}",
                    summary=str(result.proposal.get("title", ""))[:200],
                ).model_dump()
            )
        if result.delta_spec:
            broadcast_sync(
                DocumentProduced(
                    timestamp=_utc_now(),
                    flow_id=flow_id,
                    agent="architect",
                    doc_type="delta_spec",
                    doc_id=f"delta_spec-{flow_id}",
                    summary=str(result.delta_spec.get("title", ""))[:200],
                ).model_dump()
            )
        if result.delta_design:
            broadcast_sync(
                DocumentProduced(
                    timestamp=_utc_now(),
                    flow_id=flow_id,
                    agent="architect",
                    doc_type="delta_design",
                    doc_id=f"delta_design-{flow_id}",
                    summary=str(result.delta_design.get("title", ""))[:200],
                ).model_dump()
            )
        if result.architecture_research:
            broadcast_sync(
                DocumentProduced(
                    timestamp=_utc_now(),
                    flow_id=flow_id,
                    agent="architect",
                    doc_type="architecture_research",
                    doc_id=f"architecture_research-{flow_id}",
                    summary=str(result.architecture_research.get("title", ""))[:200],
                ).model_dump()
            )

        # Final cost update
        report = cost_meter.to_report_dict()
        broadcast_sync(
            CostUpdate(
                timestamp=_utc_now(),
                flow_id=flow_id,
                total_tokens=report.get("total_tokens", 0),
                estimated_cost_usd=report.get("measured_cost_usd", 0.0),
                round_tokens=report.get("round_tokens", {}),
            ).model_dump()
        )
        broadcast_sync(
            AgentStateChange(
                timestamp=_utc_now(),
                flow_id=flow_id,
                agent="(engine)",
                state=AgentState.IDLE,
                detail=f"flow completed: {len(result.completed_steps)} steps",
            ).model_dump()
        )

        # D1-14: record 4 metrics to ~/.sddp-pet/metrics.json
        try:
            from ..observability.metrics_recorder import record_flow_metrics

            record_flow_metrics(
                flow_id=flow_id,
                status="completed",
                cost_meter=cost_meter,
            )
        except Exception as e:
            logger.warning("record_flow_metrics (completed) failed (non-fatal): %s", e)
    except Exception as e:
        logger.exception("flow thread crashed: %s", e)
        broadcast_sync(
            ErrorMessage(
                timestamp=_utc_now(),
                flow_id=flow_id,
                error_code=ErrorCode.FLOW_STUCK,
                message=f"flow crashed: {e}",
                severity=Severity.CRITICAL,
                recoverable=False,
            ).model_dump()
        )
        # D1-14: also record failed flows (status="failed")
        try:
            from ..observability.metrics_recorder import record_flow_metrics

            record_flow_metrics(
                flow_id=flow_id,
                status="failed",
                cost_meter=cost_meter,
            )
        except Exception as e2:
            logger.warning("record_flow_metrics (failed) failed (non-fatal): %s", e2)
    finally:
        app.state.active_flow.pop(flow_id, None)


def _default_factory_factory(cost_meter: CostMeter, kg_tools):
    """Default: mock-mode factory (no LLM). Production passes a real factory."""

    def factory() -> AgentFactory:
        return AgentFactory(mock_mode=True, cost_meter=cost_meter, kg_tools=kg_tools)

    return factory()


__all__ = ["create_app"]
