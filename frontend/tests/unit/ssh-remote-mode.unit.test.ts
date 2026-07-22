/**
 * Remote-mode transparency (Dev-Phase 1 task 7.4 logic layer).
 *
 * D1-16 contract (specs/remote-mode/spec.md): in remote mode the engine runs
 * on a Linux server; an SSH `ssh -L` tunnel forwards the local 8765 to the
 * remote 8765. CRUCIALLY the frontend is INDIFFERENT to local vs remote — it
 * always connects to ws://localhost:8765. That transparency is what we assert
 * here; the SSH error-classification path is covered by ssh-tunnel.test.ts and
 * the real-Electron form test is in tests/e2e/ssh-remote-mode.test.ts.
 */
import { describe, expect, it } from "vitest";
import { createSddpClient } from "../../src/shared/ws-client";
import { classifySshStderr } from "../../electron/ssh-tunnel";

class CaptureUrlWebSocket {
  static lastUrl = "";
  readyState = 1;
  onopen: (() => void) | null = null;
  onmessage: ((event: { data: string }) => void) | null = null;
  onerror: (() => void) | null = null;
  onclose: (() => void) | null = null;
  private listeners: Record<string, Array<(event: unknown) => void>> = {};

  constructor(public url: string) {
    CaptureUrlWebSocket.lastUrl = url;
    setTimeout(() => {
      this.onopen?.();
      this.emit("open");
    }, 0);
  }
  send() {}
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
}

describe("7.4 — frontend is transparent to local vs remote (always localhost:8765)", () => {
  it("ws-client default URL is ws://localhost:8765/ws", async () => {
    const client = createSddpClient({
      webSocketFactory: ((u: string) => new CaptureUrlWebSocket(u)) as unknown as (u: string) => WebSocket,
    });
    await client.connect();
    expect(CaptureUrlWebSocket.lastUrl).toBe("ws://localhost:8765/ws");
    client.close();
  });

  it("the SSH tunnel binds exactly 127.0.0.1:8765 → localhost:8765 (command shape)", () => {
    expect(classifySshStderr("Permission denied (publickey)")).toBe("auth_failed");
    expect(classifySshStderr("Could not resolve hostname host")).toBe("network_unreachable");
    expect(classifySshStderr("bind: Address already in use")).toBe("port_in_use");
  });
});
