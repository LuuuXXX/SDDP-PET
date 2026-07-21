/**
 * Playwright e2e config (Dev-Phase 1 task 5.10-5.12).
 *
 * These tests require Electron to be installed (NOT included in this dev
 * environment; we used ELECTRON_SKIP_BINARY_DOWNLOAD=1). On a Windows / macOS
 * dev machine, run `npm install` without that env var to fetch the binary,
 * then `npm run test:e2e`.
 */
import { defineConfig } from "@playwright/test";

export default defineConfig({
  testDir: "./tests/e2e",
  timeout: 60_000,
  retries: 0,
  use: {
    trace: "retain-on-failure",
  },
  // No webServer config — Electron launches its own windows.
  // The test files use @playwright/test's electron support (see window1-dom.test.ts).
});
