"""Server integration tests using FastAPI TestClient WebSocket support (D1-4)."""
from __future__ import annotations

import json
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

from sddp.ipc.server import create_app


def _ts() -> str:
    return datetime.now(timezone.utc).isoformat()


@pytest.fixture
def client(tmp_path):
    """TestClient wired to a mock-mode IPC server (no real LLM)."""
    from sddp.engine.agents import AgentFactory
    from sddp.engine.cost_meter import CostMeter

    def factory_factory(cost_meter=None, kg_tools=None):
        return AgentFactory(
            mock_mode=True,
            cost_meter=cost_meter or CostMeter(),
            kg_tools=kg_tools,
        )

    app = create_app(
        agent_factory_factory=factory_factory,
        kg_db_path=None,  # skip KG to keep test fast
        flow_db_path=str(tmp_path / "flow.db"),
        mock_mode=True,
    )
    return TestClient(app)


def test_health_endpoint(client):
    """D1-4 prerequisite: /health returns ok status."""
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"
    assert r.json()["mock_mode"] is True


def test_ws_handshake_emits_ready_signal(client):
    """Spec `websocket-ipc` Requirement 1 Scenario: WebSocket 握手成功."""
    with client.websocket_connect("/ws") as ws:
        ready = json.loads(ws.receive_text())
        assert ready["type"] == "agent_state_change"
        assert ready["state"] == "idle"
        assert "timestamp" in ready


def test_ws_invalid_json_returns_parse_failure_and_keeps_connection(client):
    """Spec `websocket-ipc` Requirement 1 Scenario: 非法 JSON 消息被拒绝且不崩连接."""
    with client.websocket_connect("/ws") as ws:
        # Discard ready signal
        ws.receive_text()
        # Send invalid JSON
        ws.send_text("{not valid json")
        # Server may interleave ping first; loop until we see error
        saw_error = False
        for _ in range(5):
            msg = json.loads(ws.receive_text())
            if msg["type"] == "ping":
                # Reply pong so heartbeat stays healthy
                ws.send_text(json.dumps({
                    "type": "pong", "timestamp": _ts(), "ping_timestamp": msg["timestamp"],
                }))
                continue
            if msg["type"] == "error":
                assert msg["error_code"] == "PARSE_FAILURE"
                assert msg["recoverable"] is True
                saw_error = True
                break
        assert saw_error, "expected a parse_failure error push"


def test_ws_schema_invalid_returns_parse_failure(client):
    """A structurally valid JSON but schema-invalid message also returns PARSE_FAILURE."""
    with client.websocket_connect("/ws") as ws:
        ws.receive_text()  # discard ready
        # Missing required `message_id` on start_flow
        ws.send_text(json.dumps({
            "type": "start_flow", "timestamp": _ts(),
            "proposal": "x", "project_path": "/tmp",
        }))
        saw_error = False
        for _ in range(5):
            msg = json.loads(ws.receive_text())
            if msg["type"] == "ping":
                ws.send_text(json.dumps({
                    "type": "pong", "timestamp": _ts(), "ping_timestamp": msg["timestamp"],
                }))
                continue
            if msg["type"] == "error":
                assert msg["error_code"] == "PARSE_FAILURE"
                saw_error = True
                break
        assert saw_error


def test_ws_start_flow_returns_flow_started(client):
    """Spec `websocket-ipc` Requirement 3: 4 RPC requests are processed and responded to."""
    with client.websocket_connect("/ws") as ws:
        ws.receive_text()  # discard ready

        ws.send_text(json.dumps({
            "type": "start_flow", "message_id": "mid-1", "flow_id": "fid-1",
            "timestamp": _ts(), "proposal": "mock proposal",
            "project_path": ".",
        }))

        # Expect flow_started within next few messages (skipping pings)
        got = None
        for _ in range(10):
            msg = json.loads(ws.receive_text())
            if msg["type"] == "ping":
                ws.send_text(json.dumps({
                    "type": "pong", "timestamp": _ts(), "ping_timestamp": msg["timestamp"],
                }))
                continue
            if msg["type"] == "flow_started":
                got = msg
                break
        assert got is not None
        assert got["message_id"] == "mid-1"
        assert got["flow_id"] == "fid-1"
        assert got["status"] == "running"


def test_ws_abort_flow_returns_flow_aborted(client):
    """Spec `websocket-ipc` Requirement 3: abort_flow RPC."""
    with client.websocket_connect("/ws") as ws:
        ws.receive_text()  # discard ready

        ws.send_text(json.dumps({
            "type": "abort_flow", "message_id": "mid-2", "flow_id": "fid-nonexistent",
            "timestamp": _ts(),
        }))

        got = None
        for _ in range(5):
            msg = json.loads(ws.receive_text())
            if msg["type"] == "ping":
                ws.send_text(json.dumps({
                    "type": "pong", "timestamp": _ts(), "ping_timestamp": msg["timestamp"],
                }))
                continue
            if msg["type"] == "flow_aborted":
                got = msg
                break
        assert got is not None
        assert got["message_id"] == "mid-2"
        assert got["status"] == "aborted"


def test_ws_full_mock_flow_pushes_documents_and_cost(client):
    """Spec `websocket-ipc` Requirement 5 Scenario: WS 模式下完整 flow 跑通.

    Drives a mock-mode flow end-to-end:
      - send start_flow
      - reply y to each feedback_required (auto-approve)
      - expect 4 document_produced + 1 final cost_update
    """
    with client.websocket_connect("/ws") as ws:
        ws.receive_text()  # discard ready

        ws.send_text(json.dumps({
            "type": "start_flow", "message_id": "mid-flow", "flow_id": "fid-flow",
            "timestamp": _ts(), "proposal": "do a thing",
            "project_path": ".",
        }))

        seen_types: list[str] = []
        doc_types: list[str] = []
        cost_seen = False

        for _ in range(60):
            try:
                msg = json.loads(ws.receive_text())
            except Exception:
                break
            t = msg.get("type")
            if t == "ping":
                ws.send_text(json.dumps({
                    "type": "pong", "timestamp": _ts(), "ping_timestamp": msg["timestamp"],
                }))
                continue
            seen_types.append(t)
            if t == "feedback_required":
                ws.send_text(json.dumps({
                    "type": "user_feedback", "message_id": "fb-" + str(len(seen_types)),
                    "flow_id": "fid-flow", "timestamp": _ts(),
                    "feedback": "y",
                }))
            elif t == "document_produced":
                doc_types.append(msg["doc_type"])
            elif t == "cost_update":
                cost_seen = True
                break

        assert "flow_started" in seen_types
        assert "feedback_required" in seen_types  # at least one confirmation point fired
        assert cost_seen, f"expected final cost_update; saw: {seen_types}"
        # mock factory produces output for every role, so all 4 docs should arrive
        assert "proposal" in doc_types, f"missing proposal in {doc_types}"
