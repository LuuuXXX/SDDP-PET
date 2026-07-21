/**
 * SSH local port-forwarding tunnel for remote-mode IPC (Dev-Phase 1 D1-16).
 *
 * Per specs/remote-mode/spec.md: Windows runs the Electron UI; the SDDP engine
 * runs on a Linux server. We forward localhost:8765 (frontend's WS target) to
 * the remote engine's localhost:8765 via `ssh -L`. The frontend doesn't need
 * to know whether it's in local or remote mode.
 *
 * Lifecycle:
 *   const handle = await establishSshTunnel(cfg, { onStatus })
 *   // ... later
 *   await handle.close()
 *
 * Errors are classified into 4 kinds (D1-16 spec scenario: SSH 连接失败显示
 * 错误 + 重试按钮):
 *   - "auth_failed"     : key rejected / wrong user
 *   - "network_unreachable": DNS / routing / firewall
 *   - "port_in_use"     : local port 8765 already bound
 *   - "unknown"         : everything else (logs full stderr for diagnostics)
 */
import { spawn, type ChildProcess } from "node:child_process";
import * as fs from "node:fs";
import * as os from "node:os";
import * as path from "node:path";

export interface SshTunnelConfig {
  /** Remote host (e.g., "example.com" or "1.2.3.4"). */
  host: string;
  /** Remote SSH port (default 22). */
  port: number;
  /** Remote username. */
  username: string;
  /**
   * Reference to a key stored in OS credential manager (via secrets.ts).
   * The actual key material is fetched via the secrets API and written to a
   * temp file (0600) used by `ssh -i`.
   */
  keyRef: string;
  /** Local port to bind (default 8765, must match WS server expectation). */
  localPort?: number;
  /** Remote port to forward to (default same as localPort). */
  remotePort?: number;
}

export type SshErrorKind = "auth_failed" | "network_unreachable" | "port_in_use" | "unknown";

/**
 * Classify an ssh stderr line into one of the 4 error kinds (D1-16).
 *
 * Pure function — exported for direct unit testing without spinning up the
 * Promise/spawn flow. Returns null if the line doesn't match any known error.
 */
export function classifySshStderr(line: string): SshErrorKind | null {
  if (/Permission denied/i.test(line)) return "auth_failed";
  if (/Could not resolve hostname|Connection timed out|Network is unreachable|No route to host/i.test(line)) {
    return "network_unreachable";
  }
  if (/bind: Address already in use|local forward[\s\S]*?(fail|error)/i.test(line)) {
    return "port_in_use";
  }
  return null;
}

export class SshTunnelError extends Error {
  constructor(
    public kind: SshErrorKind,
    message: string,
    public stderr: string,
  ) {
    super(message);
    this.name = "SshTunnelError";
  }
}

export interface SshTunnelHandle {
  /** The underlying ssh ChildProcess; exposed for test inspection. */
  readonly process: ChildProcess;
  /** Resolve the key temp-file path (for cleanup logging). */
  readonly keyFilePath: string | null;
  /** Tear down: kill ssh + remove temp key file. */
  close(): Promise<void>;
}

export interface EstablishOptions {
  /**
   * Override the spawn function (for testing — inject a mock child_process).
   * Defaults to node:child_process.spawn.
   */
  spawnFn?: typeof spawn;
  /**
   * Override the key-fetch function (for testing — inject mock keyring).
   * Returns the PEM private key string, or undefined if not found.
   */
  fetchKey?: (keyRef: string) => Promise<string | undefined>;
  /**
   * Status callback for connection state changes.
   */
  onStatus?: (event: SshStatusEvent) => void;
  /**
   * How long to wait for the tunnel to come up before timing out.
   * Default 15s. ssh normally prints "Ready" within 1-2s on a healthy link.
   */
  readyTimeoutMs?: number;
}

export type SshStatusEvent =
  | { kind: "starting"; cmd: string }
  | { kind: "ready" }
  | { kind: "error"; error: SshTunnelError }
  | { kind: "closed" };

/**
 * Establish an SSH local-port-forward tunnel.
 *
 * Returns when ssh prints "Local forwarding listening" (or after first stderr
 * line that matches a known error pattern). Throws SshTunnelError on failure.
 */
export async function establishSshTunnel(
  cfg: SshTunnelConfig,
  opts: EstablishOptions = {},
): Promise<SshTunnelHandle> {
  const spawnFn = opts.spawnFn ?? spawn;
  const fetchKey = opts.fetchKey ?? (() => Promise.resolve(undefined));
  const readyTimeoutMs = opts.readyTimeoutMs ?? 15_000;
  const localPort = cfg.localPort ?? 8765;
  const remotePort = cfg.remotePort ?? localPort;

  // Fetch + write key to temp file (0600). Skip -i if fetch returns nothing
  // (user may be using an SSH agent).
  let keyFilePath: string | null = null;
  const keyMaterial = await fetchKey(cfg.keyRef);
  if (keyMaterial) {
    keyFilePath = path.join(
      os.tmpdir(),
      `sddp-pet-ssh-key-${cfg.keyRef}-${process.pid}-${Date.now()}`,
    );
    fs.writeFileSync(keyFilePath, keyMaterial, { mode: 0o600 });
  }

  const sshArgs = [
    // -N: no remote command (just forward)
    "-N",
    // Strict host key checking off for first run; we'll surface "auth failed"
    // errors for clarity but tolerate unknown hosts (user UX)
    "-o", "StrictHostKeyChecking=accept-new",
    // Don't fall back to password prompt (we're a desktop app; fail fast)
    "-o", "BatchMode=yes",
    // Exit quickly if the server doesn't respond
    "-o", `ConnectTimeout=${Math.floor(readyTimeoutMs / 1000)}`,
    // Bind local interface only (don't expose to LAN)
    "-L", `127.0.0.1:${localPort}:localhost:${remotePort}`,
    "-p", String(cfg.port),
  ];
  if (keyFilePath) {
    sshArgs.push("-i", keyFilePath);
    // Protect against overly-open key file perms (ssh refuses otherwise)
    sshArgs.push("-o", "IdentitiesOnly=yes");
  }
  sshArgs.push(`${cfg.username}@${cfg.host}`);

  const cmd = `ssh ${sshArgs.join(" ")}`;
  opts.onStatus?.({ kind: "starting", cmd });

  const child = spawnFn("ssh", sshArgs, { stdio: ["ignore", "pipe", "pipe"] });

  return new Promise<SshTunnelHandle>((resolve, reject) => {
    const stderrChunks: string[] = [];
    let settled = false;

    const timeoutHandle = setTimeout(() => {
      if (settled) return;
      settled = true;
      // Treat unknown timeout as network_unreachable (most common cause)
      const err = new SshTunnelError(
        "network_unreachable",
        `SSH did not come up within ${readyTimeoutMs}ms`,
        stderrChunks.join(""),
      );
      opts.onStatus?.({ kind: "error", error: err });
      try {
        child.kill("SIGTERM");
      } catch {
        /* ignore */
      }
      cleanupKeyFile(keyFilePath);
      reject(err);
    }, readyTimeoutMs);

    child.stderr?.on("data", (chunk: Buffer) => {
      const text = chunk.toString("utf-8");
      stderrChunks.push(text);

      const kind = classifySshStderr(text);
      if (kind !== null) {
        if (settled) return;
        settled = true;
        clearTimeout(timeoutHandle);
        const message =
          kind === "auth_failed" ? "SSH 认证失败" :
          kind === "network_unreachable" ? "无法连接到远程主机" :
          kind === "port_in_use" ? `本地端口 ${localPort} 已被占用` :
          "SSH 错误";
        const err = new SshTunnelError(kind, message, stderrChunks.join(""));
        opts.onStatus?.({ kind: "error", error: err });
        try {
          child.kill("SIGTERM");
        } catch {
          /* ignore */
        }
        cleanupKeyFile(keyFilePath);
        reject(err);
        return;
      }
    });

    child.on("exit", (code, signal) => {
      if (settled) return;
      settled = true;
      clearTimeout(timeoutHandle);
      cleanupKeyFile(keyFilePath);
      const err = new SshTunnelError(
        "unknown",
        `SSH exited unexpectedly (code=${code}, signal=${signal})`,
        stderrChunks.join(""),
      );
      opts.onStatus?.({ kind: "error", error: err });
      reject(err);
    });

    // "Ready" heuristic: if ssh survives 1.5s without printing a known error,
    // assume the tunnel is up. This is conservative (ssh prints "Local forwarding
    // listening" on stderr in -v mode; without -v it just blocks silently).
    setTimeout(() => {
      if (settled) return;
      settled = true;
      clearTimeout(timeoutHandle);
      opts.onStatus?.({ kind: "ready" });
      resolve({
        process: child,
        keyFilePath,
        async close() {
          try {
            child.kill("SIGTERM");
          } catch {
            /* ignore */
          }
          cleanupKeyFile(keyFilePath);
          opts.onStatus?.({ kind: "closed" });
        },
      });
    }, 1500);
  });
}

function cleanupKeyFile(keyFilePath: string | null): void {
  if (!keyFilePath) return;
  try {
    fs.unlinkSync(keyFilePath);
  } catch {
    /* ignore (file may already be gone) */
  }
}

// ---- main-process wiring (used by ipcMain handler in windows.ts) ----

/**
 * Test a connection without keeping it alive. Returns ok=true on success or
 * ok=false + error kind/message on failure. Used by the SSH settings panel's
 * "Test Connection" button.
 */
export async function testSshConnection(
  cfg: SshTunnelConfig,
  opts: EstablishOptions = {},
): Promise<{ ok: true } | { ok: false; error: SshTunnelError }> {
  try {
    const handle = await establishSshTunnel(cfg, {
      ...opts,
      readyTimeoutMs: opts.readyTimeoutMs ?? 10_000,
    });
    await handle.close();
    return { ok: true };
  } catch (err) {
    if (err instanceof SshTunnelError) {
      return { ok: false, error: err };
    }
    return {
      ok: false,
      error: new SshTunnelError("unknown", (err as Error).message, ""),
    };
  }
}
