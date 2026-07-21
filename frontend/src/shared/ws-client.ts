/**
 * WebSocket client for SDDP-Pet IPC (Dev-Phase 1 D1-4).
 *
 * Per specs/websocket-ipc/spec.md:
 *   - Connect to ws://localhost:8765 (same URL in local & remote modes)
 *   - Validate every incoming message via zod (parse failures don't crash)
 *   - Reply to application-layer pings within 10 seconds (heartbeat client-side)
 *   - Auto-reconnect with exponential backoff on disconnect
 *   - RPC request/response correlation via message_id (UUID v4); 30s timeout
 *
 * Public API:
 *   const ws = createSddpClient({ url, onMessage, onConnectionStateChange })
 *   await ws.connect()
 *   const response = await ws.sendRpc({ type: "start_flow", ... })
 *   ws.close()
 */
import type {
  ClientMessage,
  ServerMessage,
  StartFlowRequest,
  UserFeedbackRequest,
  ResumeFlowRequest,
  AbortFlowRequest,
} from "./ws-schemas";
import { ServerMessageSchema } from "./ws-schemas";

const DEFAULT_URL = "ws://localhost:8765/ws";
const RPC_TIMEOUT_MS = 30_000;
const RECONNECT_BASE_MS = 500;
const RECONNECT_MAX_MS = 30_000;

export type ConnectionState =
  | "disconnected"
  | "connecting"
  | "connected"
  | "reconnecting"
  | "closed";

export interface SddpClientOptions {
  url?: string;
  onMessage?: (msg: ServerMessage) => void;
  onConnectionStateChange?: (state: ConnectionState) => void;
  onRawInvalidMessage?: (raw: unknown, error: Error) => void;
  /** Override the WebSocket factory (for testing). Defaults to browser WebSocket. */
  webSocketFactory?: (url: string) => WebSocket;
}

export interface SddpClient {
  connect(): Promise<void>;
  close(): void;
  sendRpc(req: RpcRequest): Promise<RpcResponse>;
  getState(): ConnectionState;
}

type RpcRequest =
  | StartFlowRequest
  | UserFeedbackRequest
  | ResumeFlowRequest
  | AbortFlowRequest;

type RpcResponse = ServerMessage; // FlowStarted | FeedbackAccepted | FlowResumed | FlowAborted

interface PendingRpc {
  message_id: string;
  resolve: (msg: RpcResponse) => void;
  reject: (err: Error) => void;
  timer: ReturnType<typeof setTimeout>;
}

/**
 * Cryptographically-random UUID v4 (browser crypto API; falls back to Math.random
 * for environments without crypto — Node test envs without DOM).
 */
function uuidv4(): string {
  try {
    if (typeof crypto !== "undefined" && typeof crypto.randomUUID === "function") {
      return crypto.randomUUID();
    }
  } catch {
    /* fall through */
  }
  // RFC 4122 v4 fallback
  const hex = "0123456789abcdef";
  let out = "";
  for (let i = 0; i < 36; i++) {
    if (i === 8 || i === 13 || i === 18 || i === 23) out += "-";
    else if (i === 14) out += "4";
    else if (i === 19) out += hex[(Math.random() * 4) | 0x8];
    else out += hex[(Math.random() * 16) | 0];
  }
  return out;
}

export function createSddpClient(options: SddpClientOptions = {}): SddpClient {
  const url = options.url ?? DEFAULT_URL;
  const wsFactory = options.webSocketFactory ?? ((u: string) => new WebSocket(u));

  let socket: WebSocket | null = null;
  let state: ConnectionState = "disconnected";
  let reconnectAttempts = 0;
  let reconnectTimer: ReturnType<typeof setTimeout> | null = null;
  let manuallyClosed = false;
  const pendingRpcs = new Map<string, PendingRpc>();

  function setState(next: ConnectionState) {
    if (state === next) return;
    state = next;
    options.onConnectionStateChange?.(next);
  }

  function handleIncoming(raw: string) {
    let parsed: unknown;
    try {
      parsed = JSON.parse(raw);
    } catch (err) {
      options.onRawInvalidMessage?.(raw, new Error(`invalid JSON: ${(err as Error).message}`));
      return;
    }
    const result = ServerMessageSchema.safeParse(parsed);
    if (!result.success) {
      options.onRawInvalidMessage?.(parsed, new Error(result.error.message));
      return;
    }
    const msg = result.data;

    // Heartbeat: reply with pong (within 10s per spec)
    if (msg.type === "ping") {
      const pong = {
        type: "pong" as const,
        timestamp: new Date().toISOString(),
        ping_timestamp: msg.timestamp,
        flow_id: msg.flow_id ?? null,
      };
      sendRaw(pong);
      return; // ping/pong aren't user-visible
    }

    // RPC response correlation
    const messageId = (msg as { message_id?: string }).message_id;
    if (messageId && pendingRpcs.has(messageId)) {
      const pending = pendingRpcs.get(messageId)!;
      clearTimeout(pending.timer);
      pendingRpcs.delete(messageId);
      pending.resolve(msg);
      // Also surface to onMessage (so UI can update)
    }

    options.onMessage?.(msg);
  }

  function sendRaw(msg: ClientMessage) {
    if (!socket || socket.readyState !== WebSocket.OPEN) {
      // Silently drop; the caller for RPCs will time out
      return;
    }
    socket.send(JSON.stringify(msg));
  }

  function attachSocket(s: WebSocket) {
    s.onopen = () => {
      reconnectAttempts = 0;
      setState("connected");
    };
    s.onmessage = (event) => {
      if (typeof event.data === "string") handleIncoming(event.data);
    };
    s.onerror = () => {
      // Don't setState here; onclose will handle reconnect
    };
    s.onclose = () => {
      if (manuallyClosed) {
        setState("closed");
        return;
      }
      // Auto-reconnect with exponential backoff
      setState("reconnecting");
      reconnectAttempts += 1;
      const delay = Math.min(
        RECONNECT_BASE_MS * 2 ** (reconnectAttempts - 1),
        RECONNECT_MAX_MS,
      );
      reconnectTimer = setTimeout(() => {
        if (manuallyClosed) return;
        try {
          socket = wsFactory(url);
          attachSocket(socket);
        } catch (err) {
          // Factory failed; try again after another delay
          options.onRawInvalidMessage?.(null, new Error(`reconnect factory failed: ${(err as Error).message}`));
        }
      }, delay);
    };
  }

  return {
    connect() {
      return new Promise<void>((resolve, reject) => {
        if (socket && socket.readyState === WebSocket.OPEN) {
          resolve();
          return;
        }
        setState("connecting");
        try {
          socket = wsFactory(url);
        } catch (err) {
          setState("disconnected");
          reject(err);
          return;
        }
        // Resolve on first open; reject on first error before open
        const onOpen = () => {
          socket?.removeEventListener("open", onOpen);
          socket?.removeEventListener("error", onErr);
          resolve();
        };
        const onErr = () => {
          socket?.removeEventListener("open", onOpen);
          socket?.removeEventListener("error", onErr);
          setState("disconnected");
          reject(new Error(`failed to connect to ${url}`));
        };
        socket.addEventListener("open", onOpen);
        socket.addEventListener("error", onErr);
        attachSocket(socket);
      });
    },

    close() {
      manuallyClosed = true;
      if (reconnectTimer) {
        clearTimeout(reconnectTimer);
        reconnectTimer = null;
      }
      // Reject all pending RPCs
      for (const [, pending] of pendingRpcs) {
        clearTimeout(pending.timer);
        pending.reject(new Error("client closed"));
      }
      pendingRpcs.clear();
      if (socket) {
        socket.close();
        socket = null;
      }
      setState("closed");
    },

    sendRpc(req) {
      return new Promise<RpcResponse>((resolve, reject) => {
        if (!socket || socket.readyState !== WebSocket.OPEN) {
          reject(new Error("not connected"));
          return;
        }
        const timer = setTimeout(() => {
          if (pendingRpcs.has(req.message_id)) {
            pendingRpcs.delete(req.message_id);
            reject(new Error(`RPC timeout after ${RPC_TIMEOUT_MS}ms: ${req.type}`));
          }
        }, RPC_TIMEOUT_MS);
        pendingRpcs.set(req.message_id, { message_id: req.message_id, resolve, reject, timer });
        sendRaw(req);
      });
    },

    getState() {
      return state;
    },
  };
}

/**
 * Convenience helpers for the 4 RPC types — generate message_id + timestamp
 * automatically so the React panels don't repeat boilerplate.
 */
export function newStartFlowRequest(
  proposal: string,
  projectPath: string,
  partial?: Partial<StartFlowRequest>,
): StartFlowRequest {
  return {
    type: "start_flow",
    message_id: uuidv4(),
    timestamp: new Date().toISOString(),
    proposal,
    project_path: projectPath,
    ...partial,
  };
}

export function newUserFeedbackRequest(
  flowId: string,
  feedback: UserFeedbackRequest["feedback"],
  partial?: Partial<UserFeedbackRequest>,
): UserFeedbackRequest {
  return {
    type: "user_feedback",
    message_id: uuidv4(),
    flow_id: flowId,
    timestamp: new Date().toISOString(),
    feedback,
    ...partial,
  };
}

export function newResumeFlowRequest(flowId: string): ResumeFlowRequest {
  return {
    type: "resume_flow",
    message_id: uuidv4(),
    flow_id: flowId,
    timestamp: new Date().toISOString(),
  };
}

export function newAbortFlowRequest(flowId: string): AbortFlowRequest {
  return {
    type: "abort_flow",
    message_id: uuidv4(),
    flow_id: flowId,
    timestamp: new Date().toISOString(),
  };
}
