/**
 * Heartbeat / connection-loss behavior (Dev-Phase 1 task 7.2 logic layer).
 *
 * D1-7 contract (specs/websocket-ipc/spec.md): the client MUST
 *   - auto-reply pong to server pings (keeps the link alive)
 *   - transition to "reconnecting" when the server side drops (simulating the
 *     server's 3-miss threshold firing + closing the socket)
 *   - surface the connection-state change so the UI can show a "连接中断 /
 *     重连" affordance
 *
 * The 3-miss detection itself is server-side (see backend HeartbeatMonitor +
 * tests/ipc/test_heartbeat.py). Here we verify the client's reaction to the
 * resulting socket close. The real-Electron UI assertion is in
 * tests/e2e/heartbeat-miss.test.ts.
 */
import { describe, expect, it, vi, beforeEach, afterEach } from "vitest";
import { createSddpClient, type ConnectionState } from "../../src/shared/ws-client";
import type { ServerMessage } from "../../src/shared/ws-schemas";

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
afterEach(() => {
  vi.useRealTimers();
});

describe("7.2 — client keeps the link alive", () => {
  it("auto-replies pong to every server ping", async () => {
    const client = createSddpClient({ webSocketFactory: FACTORY });
    await client.connect();
    const socket = MockWebSocket.instances[0];

    for (let i = 0; i < 3; i++) {
      socket.receive({ type: "ping", timestamp: ts() });
    }
    const pongs = socket.sent.map((s) => JSON.parse(s)).filter((m) => m.type === "pong");
    expect(pongs).toHaveLength(3);
    expect(pongs.every((p) => typeof p.ping_timestamp === "string")).toBe(true);
    client.close();
  });
});

describe("7.2 — connection loss after server-side 3-miss threshold", () => {
  it("transitions through reconnecting and attempts a new socket", async () => {
    vi.useFakeTimers();
    const states: ConnectionState[] = [];
    const client = createSddpClient({
      webSocketFactory: FACTORY,
      onConnectionStateChange: (s) => states.push(s),
    });
    const connectPromise = client.connect();
    await vi.advanceTimersByTimeAsync(10);
    await connectPromise;

    const firstSocket = MockWebSocket.instances[0];
    expect(client.getState()).toBe("connected");

    firstSocket.close();

    expect(states).toContain("reconnecting");
    expect(client.getState()).toBe("reconnecting");

    await vi.advanceTimersByTimeAsync(600);
    expect(MockWebSocket.instances.length).toBe(2);
    client.close();
  });

  it("does NOT auto-reconnect after an explicit client.close()", async () => {
    vi.useFakeTimers();
    const states: ConnectionState[] = [];
    const client = createSddpClient({
      webSocketFactory: FACTORY,
      onConnectionStateChange: (s) => states.push(s),
    });
    const connectPromise = client.connect();
    await vi.advanceTimersByTimeAsync(10);
    await connectPromise;

    client.close();
    const countAfterClose = MockWebSocket.instances.length;

    await vi.advanceTimersByTimeAsync(60_000);
    expect(MockWebSocket.instances.length).toBe(countAfterClose);
    expect(states).toContain("closed");
  });
});
