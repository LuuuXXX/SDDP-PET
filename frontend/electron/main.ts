/**
 * Electron main process entry (Dev-Phase 1 D1-1/D1-2/D1-13).
 *
 * Wires up OTEL hard-disable (D1-13) and creates both windows on app ready.
 */

// D1-13: hard-disable OpenTelemetry. MUST come before any other import.
process.env.OTEL_SDK_DISABLED = "true";
process.env.OTEL_TRACES_EXPORTER = "none";
process.env.OTEL_METRICS_EXPORTER = "none";
process.env.OTEL_LOGS_EXPORTER = "none";
process.env.OTEL_PYTHON_DISABLE_AGENT = "true";

import { app, BrowserWindow } from "electron";
import { createWindow1, createWindow2 } from "./windows";

// Increase main-process GC friendliness for long-running WS connections
app.commandLine.appendSwitch("js-flags", "--max-old-space-size=512");

// Quitting flag (used by window2 close handler to differentiate user-quit
// from app.shutdown). Set to true in before-quit so windows' close handlers
// can short-circuit the "quit app" path.
let isQuitting = false;
Object.defineProperty(app, "isQuitting", {
  get: () => isQuitting,
  configurable: true,
});

app.whenReady().then(() => {
  // eslint-disable-next-line no-console
  console.log(
    "[sddp-pet main] ready — OTEL_SDK_DISABLED=" +
      process.env.OTEL_SDK_DISABLED +
      " (D1-13 enforced)",
  );
  createWindow1();
  createWindow2();
});

app.on("window-all-closed", () => {
  if (process.platform !== "darwin") app.quit();
});

// Surface certificate: prevent silent failures when WS endpoint has cert issues
// (defensive for SSH-tunnel scenarios in remote mode, task 4.x)
app.on("certificate-error", (event, _webContents, _url, _error, _certificate, callback) => {
  // For DP1 we reject all certificates with errors (fail-closed)
  event.preventDefault();
  callback(false);
});

app.on("before-quit", () => {
  isQuitting = true;
});

export { BrowserWindow };
