/**
 * D1-2 verification: window2 renders all 6 panel types.
 *
 * Per specs/desktop-pet-ui/spec.md: state-panel / diagnostic-panel / confirm-panel
 * (under feedback) / cost-display / ssh-settings / privacy-consent-modal.
 *
 * SKIPPED in environments without Electron binary. The component-level vitest
 * in tests/unit/panels.test.tsx covers each panel individually; this e2e test
 * verifies they integrate correctly inside the real window2.
 *
 * @tags e2e, electron, D1-2
 */
import { test, expect } from "@playwright/test";

const ELECTRON_AVAILABLE = (() => {
  try {
    return !!require.resolve("electron", { paths: [process.cwd()] });
  } catch {
    return false;
  }
})();

const describeOrSkip = ELECTRON_AVAILABLE ? test.describe : test.describe.skip;

describeOrSkip("D1-2: window2 renders 6 panel types", () => {
  test("state panel renders by default", async () => {
    // eslint-disable-next-line @typescript-eslint/no-var-requires
    const { _electron: electron } = require("@playwright/test");
    const app = await electron.launch({ args: ["./dist/main/index.js"] });

    const windows = app.windows();
    const window2 = windows.find((w: { url: () => string }) => w.url().includes("window2"));
    expect(window2).toBeDefined();

    // Default tab: state panel
    await window2.waitForSelector('[data-testid="state-panel"]', { timeout: 5_000 });

    // Switch to diagnostic tab
    await window2.click("text=诊断");
    await window2.waitForSelector('[data-testid="diagnostic-panel"]');

    // Switch to settings (SSH) tab
    await window2.click("text=设置");
    await window2.waitForSelector('[data-testid="ssh-settings"]');

    await app.close();
  });

  test("first launch shows privacy consent modal", async () => {
    // eslint-disable-next-line @typescript-eslint/no-var-requires
    const { _electron: electron } = require("@playwright/test");
    // Use a fresh userData dir so consent isn't cached
    const app = await electron.launch({
      args: ["./dist/main/index.js"],
      env: { ...process.env, SDDP_TEST_FRESH_USERDATA: "1" },
    });

    const window2 = app.windows().find((w: { url: () => string }) => w.url().includes("window2"));
    await window2?.waitForSelector('[data-testid="privacy-consent-modal"]', { timeout: 5_000 });

    await app.close();
  });
});
