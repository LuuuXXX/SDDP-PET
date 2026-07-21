/**
 * D1-1 verification: window1 MUST contain ONLY a canvas (0 React DOM).
 *
 * Per specs/desktop-pet-ui/spec.md Requirement: 双窗口 MUST 严格分离 — DevTools
 * 检查 window1 的 DOM 节点数 MUST = 1（仅 canvas）.
 *
 * This test runs against real Electron — SKIPPED automatically in environments
 * without Electron binary. Run with `npm run test:e2e` on a dev machine.
 *
 * @tags e2e, electron, D1-1
 */
import { test, expect } from "@playwright/test";

const ELECTRON_AVAILABLE = (() => {
  try {
    // Resolve would throw if electron binary isn't installed
    return !!require.resolve("electron", { paths: [process.cwd()] });
  } catch {
    return false;
  }
})();

const describeOrSkip = ELECTRON_AVAILABLE ? test.describe : test.describe.skip;

describeOrSkip("D1-1: window1 has 0 React DOM (only canvas)", () => {
  test("DevTools reports exactly 1 DOM node in window1", async () => {
    // eslint-disable-next-line @typescript-eslint/no-var-requires
    const { _electron: electron } = require("@playwright/test");
    const app = await electron.launch({ args: ["./dist/main/index.js"] });

    // Find the transparent window (window1)
    const windows = app.windows();
    const window1 = windows.find((w: { url: () => string }) => {
      // window1 is transparent + frame:false + alwaysOnTop
      // We rely on title or URL pattern; the renderer is window1-pet
      return w.url().includes("window1") || w.url().includes("pet");
    });
    expect(window1).toBeDefined();

    // Count DOM nodes inside window1's body
    const bodyChildCount = await window1.evaluate(() => {
      return document.body.querySelectorAll("*").length;
    });
    // body should have only 1 descendant element (the canvas)
    expect(bodyChildCount).toBe(1);

    // And that element MUST be a canvas
    const childTag = await window1.evaluate(() => {
      const el = document.body.querySelector("*");
      return el?.tagName.toLowerCase();
    });
    expect(childTag).toBe("canvas");

    await app.close();
  });
});
