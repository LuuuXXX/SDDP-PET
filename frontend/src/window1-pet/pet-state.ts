/**
 * Pet animation state machine (D1-1 + D2-3).
 *
 * DP1: 4 states (idle/working/waiting/error).
 * DP2 (D2-3): +4 confrontation states (debating/rebutted/converged/escalated)
 *   + role-aware rendering (architect/critic/empiricist/orchestrator).
 *
 * Per specs/desktop-pet-ui/spec.md + dev-phase-2/design.md §6:
 *   - architect working (round 1) → working
 *   - critic/empiricist/orchestrator speaking → debating
 *   - architect revising (round > 1) → rebutted
 *   - force_convergence escalate → escalated
 *
 * Pure logic — no PixiJS dependency — unit-testable without canvas.
 */

export type PetState =
  | "idle" | "working" | "waiting" | "error" // DP1
  | "debating" | "rebutted" | "converged" | "escalated"; // DP2 (D2-3)

export type PetRole = "architect" | "critic" | "empiricist" | "orchestrator" | null;

const ROLE_LABELS: Record<NonNullable<PetRole>, string> = {
  architect: "架构师",
  critic: "挑评师",
  empiricist: "实证师",
  orchestrator: "调度官",
};

export function roleLabel(role: PetRole): string {
  return role ? ROLE_LABELS[role] : "";
}

/**
 * Transitions driven by WS messages. DP1 states keep their DP1 transitions;
 * DP2 confrontation states are reachable from working/waiting and interleave
 * with the debate. Invalid transitions ignored (idempotent).
 */
const TRANSITIONS: Record<PetState, PetState[]> = {
  idle: ["working", "error", "debating"],
  working: ["waiting", "idle", "error", "debating", "rebutted", "converged"],
  waiting: ["working", "idle", "error", "escalated"],
  error: ["idle", "working"],
  // DP2 confrontation states
  debating: ["working", "rebutted", "converged", "escalated", "idle", "error"],
  rebutted: ["debating", "converged", "escalated", "working", "idle"],
  converged: ["idle", "working"],
  escalated: ["working", "idle", "waiting"],
};

export interface PetModel {
  state: PetState;
  /** Current speaking role (DP2); null in DP1 linear flow. */
  role: PetRole;
  /** Short prompt shown beside the pet. */
  bubbleText: string;
  history: Array<{ from: PetState; to: PetState; at: string; reason?: string }>;
}

export function createPetModel(initial: PetState = "idle"): PetModel {
  return { state: initial, role: null, bubbleText: "", history: [] };
}

export function transition(
  model: PetModel,
  next: PetState,
  opts?: { bubbleText?: string; reason?: string; role?: PetRole },
): PetModel {
  if (model.state === next) return model; // no-op
  const allowed = TRANSITIONS[model.state];
  if (!allowed.includes(next)) {
    return model; // invalid transition — idempotent
  }
  return {
    state: next,
    role: opts?.role ?? model.role,
    bubbleText: opts?.bubbleText ?? model.bubbleText,
    history: [
      ...model.history,
      { from: model.state, to: next, at: new Date().toISOString(), reason: opts?.reason },
    ],
  };
}

type ServerMessage = import("../shared/ws-schemas").ServerMessage;

/**
 * Map an incoming WS message to a pet state transition + bubble text + role.
 * Returns null if the message doesn't affect the pet.
 */
export function derivePetUpdate(
  msg: ServerMessage,
): { state: PetState; role?: PetRole; bubbleText?: string } | null {
  switch (msg.type) {
    case "agent_state_change": {
      // role is the DP2 additive field; absent (undefined) in DP1 linear flow
      const role = ((msg as { role?: string }).role ?? null) as PetRole;
      if (msg.state === "working") {
        // DP2: a challenger speaking → debating; architect revising → rebutted
        if (role === "critic" || role === "empiricist" || role === "orchestrator") {
          return { state: "debating", role, bubbleText: `${ROLE_LABELS[role]}发言中` };
        }
        const round = (msg as { round?: number }).round ?? 0;
        if (role === "architect" && round > 1) {
          return { state: "rebutted", role, bubbleText: "架构师修订中" };
        }
        return {
          state: "working",
          role,
          bubbleText: role ? `${ROLE_LABELS[role]}工作中` : `${msg.agent} 工作中`,
        };
      }
      if (msg.state === "idle") return { state: "idle", role, bubbleText: "" };
      if (msg.state === "waiting") return { state: "waiting", role, bubbleText: `${msg.agent} 等待` };
      if (msg.state === "error") return { state: "error", role, bubbleText: msg.detail ?? "出错" };
      return null;
    }
    case "feedback_required":
      // DP2: force_convergence method → escalated state
      if (msg.method === "force_convergence") {
        return { state: "escalated", bubbleText: msg.message };
      }
      return { state: "waiting", bubbleText: msg.message };
    case "error":
      return { state: "error", bubbleText: msg.message };
    case "document_produced":
    case "cost_update":
    case "ping":
    case "pong":
      return null;
    default:
      return null;
  }
}
