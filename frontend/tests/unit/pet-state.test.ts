/**
 * Pet state machine unit tests (task 5.10 partial).
 *
 * Pure-logic tests that don't require PixiJS / canvas. The full window1 DOM
 * assertion (D1-1 "node count = 1") is a Playwright e2e test — see
 * tests/e2e/window1-dom.test.ts.
 */
import { describe, expect, it } from "vitest";
import { createPetModel, transition, derivePetUpdate } from "../../src/window1-pet/pet-state";
import type { ServerMessage } from "../../src/shared/ws-schemas";

describe("pet-state", () => {
  it("starts in idle state", () => {
    const m = createPetModel();
    expect(m.state).toBe("idle");
    expect(m.bubbleText).toBe("");
    expect(m.history).toHaveLength(0);
  });

  it("allows idle → working transition", () => {
    const m = createPetModel();
    const m2 = transition(m, "working", { bubbleText: "architect 工作中" });
    expect(m2.state).toBe("working");
    expect(m2.bubbleText).toBe("architect 工作中");
    expect(m2.history).toHaveLength(1);
    expect(m2.history[0]).toMatchObject({ from: "idle", to: "working" });
  });

  it("records transition history", () => {
    let m = createPetModel();
    m = transition(m, "working");
    m = transition(m, "waiting");
    m = transition(m, "working");
    m = transition(m, "idle");
    expect(m.history).toHaveLength(4);
    expect(m.history.map((h) => `${h.from}→${h.to}`)).toEqual([
      "idle→working",
      "working→waiting",
      "waiting→working",
      "working→idle",
    ]);
  });

  it("ignores invalid transitions (idempotent)", () => {
    // idle → waiting is not in TRANSITIONS.idle = ["working", "error"]
    const m = createPetModel();
    const m2 = transition(m, "waiting");
    expect(m2).toBe(m); // same reference; no change
    expect(m2.state).toBe("idle");
  });

  it("no-op when transitioning to current state", () => {
    const m = createPetModel("idle");
    const m2 = transition(m, "idle");
    expect(m2).toBe(m);
  });

  it("preserves previous bubbleText if not provided", () => {
    let m = createPetModel();
    m = transition(m, "working", { bubbleText: "正在思考" });
    m = transition(m, "waiting"); // no bubbleText
    expect(m.bubbleText).toBe("正在思考");
  });

  describe("derivePetUpdate", () => {
    it("maps agent_state_change working → pet working", () => {
      const msg: ServerMessage = {
        type: "agent_state_change",
        timestamp: new Date().toISOString(),
        agent: "architect",
        state: "working",
      };
      const update = derivePetUpdate(msg);
      expect(update?.state).toBe("working");
      expect(update?.bubbleText).toContain("architect");
    });

    it("maps feedback_required → pet waiting", () => {
      const msg: ServerMessage = {
        type: "feedback_required",
        timestamp: new Date().toISOString(),
        method: "design_confirmation",
        message: "等待方案确认",
        output: {},
      };
      const update = derivePetUpdate(msg);
      expect(update?.state).toBe("waiting");
      expect(update?.bubbleText).toBe("等待方案确认");
    });

    it("maps error message → pet error", () => {
      const msg: ServerMessage = {
        type: "error",
        timestamp: new Date().toISOString(),
        error_code: "LLM_TIMEOUT",
        message: "Timeout",
        severity: "error",
        recoverable: true,
      };
      const update = derivePetUpdate(msg);
      expect(update?.state).toBe("error");
    });

    it("returns null for cost_update (no pet state change)", () => {
      const msg: ServerMessage = {
        type: "cost_update",
        timestamp: new Date().toISOString(),
        total_tokens: 100,
        estimated_cost_usd: 0.01,
        round_tokens: {},
      };
      expect(derivePetUpdate(msg)).toBeNull();
    });

    it("returns null for document_produced", () => {
      const msg: ServerMessage = {
        type: "document_produced",
        timestamp: new Date().toISOString(),
        agent: "architect",
        doc_type: "delta_spec",
        doc_id: "ds-1",
        summary: "spec",
      };
      expect(derivePetUpdate(msg)).toBeNull();
    });

    it("returns null for ping/pong", () => {
      const ts = new Date().toISOString();
      const ping: ServerMessage = { type: "ping", timestamp: ts };
      const pong: ServerMessage = { type: "pong", timestamp: ts, ping_timestamp: ts };
      expect(derivePetUpdate(ping)).toBeNull();
      expect(derivePetUpdate(pong)).toBeNull();
    });
  });
});
