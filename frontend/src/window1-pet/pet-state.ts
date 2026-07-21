/**
 * Pet animation state machine (Dev-Phase 1 D1-1).
 *
 * Per specs/desktop-pet-ui/spec.md: the PixiJS renderer in window1 holds a small
 * state machine for the pet's emotional state. DP1 supports 4 states
 * (idle/working/waiting/error); DP2 will extend to 8 (per role).
 *
 * Pure logic — no PixiJS dependency — so it's unit-testable without canvas.
 */

export type PetState = "idle" | "working" | "waiting" | "error";

/**
 * Transitions are driven by incoming WS messages (or local events like
 * "connection lost"). Invalid transitions are ignored (idempotent).
 */
const TRANSITIONS: Record<PetState, PetState[]> = {
  idle: ["working", "error"],
  working: ["waiting", "idle", "error"],
  waiting: ["working", "idle", "error"],
  error: ["idle", "working"],
};

export interface PetModel {
  state: PetState;
  /** Current bubble text shown next to the pet (short prompt). */
  bubbleText: string;
  /** History of state transitions for debugging. */
  history: Array<{ from: PetState; to: PetState; at: string; reason?: string }>;
}

export function createPetModel(initial: PetState = "idle"): PetModel {
  return {
    state: initial,
    bubbleText: "",
    history: [],
  };
}

export function transition(
  model: PetModel,
  next: PetState,
  opts?: { bubbleText?: string; reason?: string },
): PetModel {
  if (model.state === next) return model; // no-op
  const allowed = TRANSITIONS[model.state];
  if (!allowed.includes(next)) {
    // Invalid transition — ignore (idempotent)
    return model;
  }
  return {
    state: next,
    bubbleText: opts?.bubbleText ?? model.bubbleText,
    history: [
      ...model.history,
      {
        from: model.state,
        to: next,
        at: new Date().toISOString(),
        reason: opts?.reason,
      },
    ],
  };
}

/**
 * Map an incoming WS server message to a pet state transition + bubble text.
 * Returns null if the message doesn't affect the pet (e.g., cost_update).
 */
export function derivePetUpdate(
  msg: import("../shared/ws-schemas").ServerMessage,
): { state: PetState; bubbleText?: string } | null {
  switch (msg.type) {
    case "agent_state_change":
      if (msg.state === "working") return { state: "working", bubbleText: `${msg.agent} 工作中` };
      if (msg.state === "idle") return { state: "idle", bubbleText: "" };
      if (msg.state === "waiting") return { state: "waiting", bubbleText: `${msg.agent} 等待` };
      if (msg.state === "error") return { state: "error", bubbleText: msg.detail ?? "出错" };
      return null;
    case "feedback_required":
      return { state: "waiting", bubbleText: msg.message };
    case "error":
      return { state: "error", bubbleText: msg.message };
    case "document_produced":
      return null; // doesn't change pet state
    case "cost_update":
      return null;
    case "ping":
    case "pong":
      return null;
    default:
      return null;
  }
}
