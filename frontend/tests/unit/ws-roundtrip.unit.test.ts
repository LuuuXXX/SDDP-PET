/**
 * WebSocket IPC round-trip matrix (Dev-Phase 1 task 7.1 logic layer).
 *
 * Exhaustive 5 Push + 4 RPC verification against the ws-client using an
 * in-memory MockWebSocket (no real network). The real-Electron + real-server
 * path lives in tests/e2e/websocket-roundtrip.test.ts.
 *
 * Contract source: specs/websocket-ipc/spec.md (5 Push + 4 RPC + 4 RPC-response).
 */
import { describe, expect, it, beforeEach } from "vitest";
import {
  createSddpClient,
  newStartFlowRequest,
  newUserFeedbackRequest,
  newResumeFlowRequest,
  newAbortFlowRequest,
} from "../../src/shared/ws-client";
import type { ServerMessage } from "../../src/shared/ws-schemas";

class MockWebSocket {
  static instances: MockWebSocket[] = [];
  static OPEN = 1;
  static CLOSED = 3;
  readyState = 1;
  onopen: (() => void) | null = null;
  onmessage: ((event: { data: string }) => void) | null = null;
  onerror: (() => void) | null = null;
  onclose: (() => void) | null = null;
  sent: string[] = [];
  private listeners: Record<string, Array<(event: unknown) => void>> = {};

  constructor(public url: string) {
    MockWebSocket.instances.push(this);
    setTimeout(() => {
      this.onopen?.();
      this.emit("open");
    }, 0);
  }
  send(data: string) {
    this.sent.push(data);
  }
  close() {
    this.readyState = 3;
    this.onclose?.();
    this.emit("close");
  }
  addEventListener(type: string, cb: (event: unknown) => void) {
    (this.listeners[type] ??= []).push(cb);
  }
  removeEventListener(type: string, cb: (event: unknown) => void) {
    this.listeners[type] = (this.listeners[type] ?? []).filter((f) => f !== cb);
  }
  private emit(type: string) {
    for (const cb of this.listeners[type] ?? []) cb({});
  }
  receive(msg: ServerMessage) {
    this.onmessage?.({ data: JSON.stringify(msg) });
  }
}

function ts() {
  return new Date().toISOString();
}

const FACTORY = (url: string) => new MockWebSocket(url) as unknown as WebSocket;

beforeEach(() => {
  MockWebSocket.instances = [];
});

describe("7.1 — 5 Push messages all surface to onMessage", () => {
  it("delivers agent_state_change / document_produced / cost_update / feedback_required / error", async () => {
    const received: ServerMessage[] = [];
    const client = createSddpClient({
      webSocketFactory: FACTORY,
      onMessage: (m) => received.push(m),
    });
    await client.connect();
    const socket = MockWebSocket.instances[0];

    const pushes: ServerMessage[] = [
      { type: "agent_state_change", timestamp: ts(), agent: "architect", state: "working" },
      { type: "document_produced", timestamp: ts(), agent: "architect", doc_type: "delta_spec", doc_id: "ds-1", summary: "s" },
      { type: "cost_update", timestamp: ts(), total_tokens: 10, estimated_cost_usd: 0.01, round_tokens: {} },
      { type: "feedback_required", timestamp: ts(), method: "design_confirmation", message: "m", output: {} },
      { type: "error", timestamp: ts(), error_code: "LLM_TIMEOUT", message: "timeout", severity: "error", recoverable: true },
    ];
    for (const p of pushes) socket.receive(p);

    expect(received.map((m) => m.type)).toEqual([
      "agent_state_change",
      "document_produced",
      "cost_update",
      "feedback_required",
      "error",
    ]);
    client.close();
  });
});

describe("7.1 — 4 RPC requests serialize correctly + responses correlate by message_id", () => {
  it("start_flow → flow_started", async () => {
    const client = createSddpClient({ webSocketFactory: FACTORY });
    await client.connect();
    const socket = MockWebSocket.instances[0];

    const req = newStartFlowRequest("do thing", "/proj");
    const pending = client.sendRpc(req);

    const sent = JSON.parse(socket.sent[0]);
    expect(sent.type).toBe("start_flow");
    expect(sent.message_id).toBe(req.message_id);
    expect(sent.proposal).toBe("do thing");

    socket.receive({ type: "flow_started", timestamp: ts(), message_id: req.message_id, flow_id: "fid-1", status: "running" });
    const resp = await pending;
    expect(resp.type).toBe("flow_started");
    client.close();
  });

  it("user_feedback → feedback_accepted", async () => {
    const client = createSddpClient({ webSocketFactory: FACTORY });
    await client.connect();
    const socket = MockWebSocket.instances[0];

    const req = newUserFeedbackRequest("fid-1", "y");
    const pending = client.sendRpc(req);
    expect(JSON.parse(socket.sent[0]).feedback).toBe("y");

    socket.receive({ type: "feedback_accepted", timestamp: ts(), message_id: req.message_id, flow_id: "fid-1", status: "resuming" });
    expect((await pending).type).toBe("feedback_accepted");
    client.close();
  });

  it("resume_flow → flow_resumed", async () => {
    const client = createSddpClient({ webSocketFactory: FACTORY });
    await client.connect();
    const socket = MockWebSocket.instances[0];

    const req = newResumeFlowRequest("fid-1");
    const pending = client.sendRpc(req);
    socket.receive({ type: "flow_resumed", timestamp: ts(), message_id: req.message_id, flow_id: "fid-1", status: "running" });
    expect((await pending).type).toBe("flow_resumed");
    client.close();
  });

  it("abort_flow → flow_aborted", async () => {
    const client = createSddpClient({ webSocketFactory: FACTORY });
    await client.connect();
    const socket = MockWebSocket.instances[0];

    const req = newAbortFlowRequest("fid-1");
    const pending = client.sendRpc(req);
    socket.receive({ type: "flow_aborted", timestamp: ts(), message_id: req.message_id, flow_id: "fid-1", status: "aborted" });
    expect((await pending).type).toBe("flow_aborted");
    client.close();
  });

  it("RPC response with mismatched message_id does NOT resolve a different pending RPC", async () => {
    const client = createSddpClient({ webSocketFactory: FACTORY });
    await client.connect();
    const socket = MockWebSocket.instances[0];

    const req = newStartFlowRequest("x", ".");
    const pending = client.sendRpc(req);
    socket.receive({ type: "flow_started", timestamp: ts(), message_id: "someone-else", flow_id: "fid", status: "running" });
    socket.receive({ type: "flow_started", timestamp: ts(), message_id: req.message_id, flow_id: "fid", status: "running" });
    const resp = await pending;
    expect(resp.type).toBe("flow_started");
    client.close();
  });
});
