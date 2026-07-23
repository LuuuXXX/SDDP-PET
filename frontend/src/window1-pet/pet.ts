/**
 * window1 PixiJS renderer: transparent pet sprite + bubble + AI label.
 *
 * Per specs/desktop-pet-ui/spec.md Requirement: 双窗口 MUST 严格分离:
 *   - This file runs in window1 (transparent BrowserWindow)
 *   - 0 React DOM (D1-1) — DevTools MUST report DOM node count = 1 (only <canvas>)
 *   - PixiJS Application renders pet sprite + bubble text + "AI 驱动" label
 *
 * Pet sprite: for DP1 we render a simple colored circle (no Live2D; deferred to
 * DP4 per Decision 1). DP2 will swap in role-specific sprites.
 *
 * Click-through hit-testing: PixiJS knows which pixels are pet vs. blank; we
 * relay the boolean to the main process via `sddp.sendPetHitChange(isHit)`.
 */
import { Application, Graphics, Text, TextStyle, Container } from "pixi.js";
import type { PetModel, PetState } from "./pet-state";
import { createPetModel, transition, roleLabel } from "./pet-state";

// Global `window.sddp` type comes from src/shared/global.d.ts (loaded via tsconfig).

// Color per state (simple visual cue; DP2 adds 4 confrontation states)
const STATE_COLORS: Record<PetState, number> = {
  idle: 0x4ade80,      // green
  working: 0x60a5fa,   // blue
  waiting: 0xfacc15,   // yellow
  error: 0xef4444,     // red
  // DP2 confrontation states (D2-3) — placeholder colors (no sprite art yet)
  debating: 0xf97316,   // orange — critic/empiricist/orchestrator speaking
  rebutted: 0x8b5cf6,   // purple — architect revising
  converged: 0x10b981,  // emerald — converged
  escalated: 0xdc2626,  // strong red — force-converged escalate
};

const STATE_LABELS: Record<PetState, string> = {
  idle: "休息中",
  working: "工作中",
  waiting: "等待确认",
  error: "出错",
  debating: "对抗辩论中",
  rebutted: "修订中",
  converged: "已收敛",
  escalated: "已升级裁决",
};

// DP2 role prefix (D2-3): shown in bubble when a confrontation role is active.
// Placeholder for sprite art — distinct color + label per role for now.

const PET_RADIUS = 60;
const BUBBLE_OFFSET_X = 80;
const BUBBLE_OFFSET_Y = -40;
const AI_LABEL_OFFSET_Y = 70;
const AI_LABEL_TEXT = "AI 驱动";

/**
 * Mount the PixiJS app into the given <canvas> element. Returns a controller
 * with `update(partial)` to apply state changes from outside (e.g., when a
 * WS message arrives via the main process or via postMessage).
 */
export interface PetRenderer {
  update(model: PetModel): void;
  destroy(): void;
}

export function mountPetRenderer(canvas: HTMLCanvasElement): PetRenderer {
  const app = new Application({
    view: canvas,
    width: 280,
    height: 320,
    background: "transparent" as unknown as import("pixi.js").ColorSource,
    antialias: true,
    resolution: window.devicePixelRatio || 1,
    autoDensity: true,
  });

  const root = new Container();
  app.stage.addChild(root);

  // Pet sprite (colored circle with subtle border)
  const pet = new Graphics();
  pet.interactive = true;
  pet.hitArea = { contains: (x: number, y: number) => isInsidePet(x, y) } as unknown as import("pixi.js").IHitArea;
  root.addChild(pet);

  // Bubble text (short prompt beside the pet)
  const bubbleStyle = new TextStyle({
    fontFamily: "system-ui, sans-serif",
    fontSize: 14,
    fill: 0x111827,
    wordWrap: true,
    wordWrapWidth: 180,
  });
  const bubble = new Text({ text: "", style: bubbleStyle });
  bubble.anchor.set(0, 0.5);
  root.addChild(bubble);

  // AI label (D1-12: "AI 驱动" persistent badge)
  const aiLabelStyle = new TextStyle({
    fontFamily: "system-ui, sans-serif",
    fontSize: 11,
    fill: 0x6b7280,
  });
  const aiLabel = new Text({ text: AI_LABEL_TEXT, style: aiLabelStyle });
  aiLabel.anchor.set(0.5, 0);
  root.addChild(aiLabel);

  // Track mouse position for click-through hit-testing
  let lastHitState = false;
  function updateHitState(event: { x: number; y: number }) {
    const isHit = isInsidePet(event.x, event.y);
    if (isHit !== lastHitState) {
      lastHitState = isHit;
      window.sddp?.sendPetHitChange?.(isHit);
    }
  }
  canvas.addEventListener("mousemove", (e) => {
    const rect = canvas.getBoundingClientRect();
    updateHitState({ x: e.clientX - rect.left, y: e.clientY - rect.top });
  });

  let currentModel = createPetModel();
  redraw(currentModel);

  function redraw(model: PetModel) {
    pet.clear();
    pet.circle(140, 160, PET_RADIUS);
    pet.fill({ color: STATE_COLORS[model.state] });
    pet.stroke({ color: 0xffffff, width: 3 });

    const rolePrefix = model.role ? roleLabel(model.role) + "·" : "";
    bubble.text = rolePrefix + (model.bubbleText || STATE_LABELS[model.state]);
    bubble.position.set(140 + BUBBLE_OFFSET_X, 160 + BUBBLE_OFFSET_Y);

    aiLabel.position.set(140, 160 + AI_LABEL_OFFSET_Y);
  }

  return {
    update(model: PetModel) {
      currentModel = model;
      redraw(model);
    },
    destroy() {
      app.destroy(true);
    },
  };
}

/** Hit-test the pet circle: distance from center ≤ PET_RADIUS. */
export function isInsidePet(x: number, y: number): boolean {
  const dx = x - 140;
  const dy = y - 160;
  return dx * dx + dy * dy <= PET_RADIUS * PET_RADIUS;
}

/**
 * Wire the renderer to a global event bus. In DP1 we receive WS messages via
 * postMessage from window2 (which holds the WS client). This keeps window1
 * free of WS / Node deps (D1-1 0 React DOM spirit extended to 0 network).
 */
export function startPetController(renderer: PetRenderer): void {
  let model = createPetModel();
  renderer.update(model);

  window.addEventListener("message", (event) => {
    if (event.source !== window && event.origin !== window.location.origin) return;
    const data = event.data as { type?: string; petState?: PetState; bubbleText?: string };
    if (data?.type === "sddp:pet-update" && data.petState) {
      model = transition(model, data.petState, { bubbleText: data.bubbleText });
      renderer.update(model);
    }
  });
}
