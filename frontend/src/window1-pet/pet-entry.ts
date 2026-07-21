/**
 * window1 entry point. Loads the canvas + mounts the pet renderer.
 *
 * Per D1-1: this file MUST NOT import React (0 React DOM in window1).
 */
import { mountPetRenderer, startPetController } from "./pet";

const canvas = document.getElementById("pet-canvas") as HTMLCanvasElement | null;
if (!canvas) {
  throw new Error("#pet-canvas not found in window1 DOM");
}
const renderer = mountPetRenderer(canvas);
startPetController(renderer);
