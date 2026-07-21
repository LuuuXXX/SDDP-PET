/**
 * ws-client unit tests (task 5.6 partial).
 *
 * Uses a mock WebSocket factory to avoid real network. Verifies:
 *   - zod schema validation rejects malformed messages
 *   - Application-layer ping is auto-replied with pong
 *   - RPC request/response correlation by message_id
 *   - RPC timeout rejects the promise
 *   - Connection state changes broadcast
 */
import { describe, expect, it, vi, beforeEach } from "vitest";
import {
  createSddpClient,
  newStartFlowRequest,
  newUserFeedbackRequest,
} from "../../src/shared/ws-client";
import type { ServerMessage } from "../../src/shared/ws-schemas";

// Minimal structural type — has the methods/properties ws-client actually uses


class MockWebSocket {
  static instances: MockWebSocket[] = [];

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

  // Test helper: simulate receiving a message from server
  receive(msg: ServerMessage) {
    this.onmessage?.({ data: JSON.stringify(msg) });
  }
}

function ts() {
  return new Date().toISOString();
}

describe("ws-client", () => {
  beforeEach(() => {
    MockWebSocket.instances = [];
  });

  it("connects and transitions through connection states", async () => {
    const states: string[] = [];
    const client = createSddpClient({
      webSocketFactory: ((url: string) => new MockWebSocket(url)) as unknown as (url: string) => WebSocket,
      onConnectionStateChange: (s) => states.push(s),
    });
    await client.connect();
    expect(states).toContain("connecting");
    expect(states).toContain("connected");
    expect(client.getState()).toBe("connected");
    client.close();
  });

  it("validates incoming messages via zod; invalid messages don't crash", async () => {
    const invalid: unknown[] = [
      { type: "bogus_type" },
      { type: "agent_state_change", timestamp: ts(), agent: "x" /* missing state */ },
      "not even an object",
    ];
    const errors: unknown[] = [];
    const client = createSddpClient({
      webSocketFactory: ((url: string) => new MockWebSocket(url)) as unknown as (url: string) => WebSocket,
      onRawInvalidMessage: (_raw, err) => errors.push(err.message),
    });
    await client.connect();
    const socket = MockWebSocket.instances[0];

    for (const bad of invalid) {
      socket.onmessage?.({ data: typeof bad === "string" ? bad : JSON.stringify(bad) });
    }
    expect(errors).toHaveLength(invalid.length);
    expect(client.getState()).toBe("connected"); // didn't crash
    client.close();
  });

  it("auto-replies pong to server ping (application-layer heartbeat)", () => {
    const client = createSddpClient({
      webSocketFactory: ((url: string) => new MockWebSocket(url)) as unknown as (url: string) => WebSocket,
    });
    client.connect();
    const socket = MockWebSocket.instances[0];
    const ping: ServerMessage = { type: "ping", timestamp: ts() };
    socket.receive(ping);

    const sent = socket.sent.map((s) => JSON.parse(s));
    const pong = sent.find((m) => m.type === "pong");
    expect(pong).toBeDefined();
    expect(pong.ping_timestamp).toBe(ping.timestamp);
    client.close();
  });

  it("correlates RPC response by message_id and resolves the promise", async () => {
    const client = createSddpClient({
      webSocketFactory: ((url: string) => new MockWebSocket(url)) as unknown as (url: string) => WebSocket,
    });
    await client.connect();
    const socket = MockWebSocket.instances[0];

    const req = newStartFlowRequest("do a thing", "/tmp");
    const respPromise = client.sendRpc(req);

    // Server responds
    socket.receive({
      type: "flow_started",
      timestamp: ts(),
      message_id: req.message_id,
      flow_id: "fid-123",
      status: "running",
    });

    const resp = await respPromise;
    expect(resp.type).toBe("flow_started");
    if (resp.type === "flow_started") {
      expect(resp.flow_id).toBe("fid-123");
    }
    client.close();
  });

  it("rejects RPC promise on timeout", async () => {
    // Use a very short RPC timeout by directly manipulating the timer via
    // vi.useFakeTimers. Note: connect() also uses setTimeout via MockWebSocket,
    // so we advance fake timers past that first.
    vi.useFakeTimers();
    try {
      const client = createSddpClient({
        webSocketFactory: ((url: string) => new MockWebSocket(url)) as unknown as (url: string) => WebSocket,
      });
      const connectPromise = client.connect();
      // Yield to allow MockWebSocket's constructor setTimeout to fire
      await vi.advanceTimersByTimeAsync(10);
      await connectPromise;

      const req = newStartFlowRequest("x", ".");
      const promise = client.sendRpc(req);
      // Advance past the 30s RPC timeout
      await vi.advanceTimersByTimeAsync(31_000);
      await expect(promise).rejects.toThrow(/RPC timeout/);
      client.close();
    } finally {
      vi.useRealTimers();
    }
  });

  it("rejects sendRpc when not connected", async () => {
    // Create a client whose factory throws — connect() rejects
    const client = createSddpClient({
      webSocketFactory: () => {
        throw new Error("factory fail");
      },
    });
    await expect(client.connect()).rejects.toThrow("factory fail");
    await expect(client.sendRpc(newStartFlowRequest("x", "."))).rejects.toThrow("not connected");
  });

  it("surfaces valid messages to onMessage callback", () => {
    const received: ServerMessage[] = [];
    const client = createSddpClient({
      webSocketFactory: ((url: string) => new MockWebSocket(url)) as unknown as (url: string) => WebSocket,
      onMessage: (m) => received.push(m),
    });
    client.connect();
    const socket = MockWebSocket.instances[0];

    socket.receive({
      type: "document_produced",
      timestamp: ts(),
      agent: "architect",
      doc_type: "delta_spec",
      doc_id: "ds-1",
      summary: "summary",
    });

    expect(received).toHaveLength(1);
    expect(received[0].type).toBe("document_produced");
    client.close();
  });

  it("helper constructors generate UUID-like message_ids", () => {
    const r1 = newStartFlowRequest("x", ".");
    const r2 = newStartFlowRequest("x", ".");
    expect(r1.message_id).not.toEqual(r2.message_id);
    // UUID v4 format: 8-4-4-4-12
    expect(r1.message_id).toMatch(/^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[0-9a-f]{4}-[0-9a-f]{12}$/i);

    const f = newUserFeedbackRequest("fid-1", "y");
    expect(f.feedback).toBe("y");
    expect(f.flow_id).toBe("fid-1");
  });
});
