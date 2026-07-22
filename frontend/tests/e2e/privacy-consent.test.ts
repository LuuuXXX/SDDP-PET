/**
 * D1-10 e2e: privacy-consent modal first-launch flow (Dev-Phase 1 task 7.3).
 *
 * App-level consent logic (modal shows / decline keeps running / consent
 * persists to localStorage / start-flow reachable after consent) is verified
 * in tests/unit/app-consent.test.tsx (5/5 pass). THIS file drives the same
 * flow through real Electron with a pristine userData dir (no prior consent).
 *
 * @tags e2e, electron, 7.3
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

describeOrSkip("7.3 e2e: privacy-consent modal (first launch)", () => {
  test("modal appears, 同意 reveals panel, 拒绝 keeps app alive", async () => {
    // eslint-disable-next-line @typescript-eslint/no-var-requires
    const { _electron: electron } = require("@playwright/test");
    // Fresh userData so localStorage has no prior consent
    const app = await electron.launch({
      args: ["./dist/main/index.js"],
      env: { ...process.env, ELECTRON_OVERRIDE_DIST_PATH: "" },
    });
    const window2 = app.windows().find((w: { url: () => string }) => w.url().includes("window2"));

    // 1. First launch → modal present, no start-flow form
    await expect(window2.locator("[data-testid=privacy-consent-modal]")).toBeVisible();
    expect(await window2.locator("[data-testid=start-flow-form]").count()).toBe(0);

    // 2. Decline → app stays alive (modal still mounted, no exit)
    await window2.locator("[data-testid=privacy-decline]").click();
    await expect(window2.locator("[data-testid=privacy-consent-modal]")).toBeVisible();

    // 3. Consent → modal gone, main panel + conn-state badge shown
    await window2.locator("[data-testid=privacy-consent]").click();
    await expect(window2.locator("[data-testid=privacy-consent-modal]")).toHaveCount(0);
    await expect(window2.locator("[data-testid=conn-state]")).toBeVisible();

    await app.close();
  });
});
