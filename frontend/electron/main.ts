/**
 * Electron main process entry (Dev-Phase 1 D1-1/D1-2/D1-13).
 *
 * Stub for Section 3.5 (OTEL hard-disable) — full window creation logic lands
 * in Section 5 (task 5.1). Committed now so D1-13 env var is enforced from
 * day-1 of any frontend dev work.
 *
 * Per specs/security-compliance/spec.md Requirement: 进程 MUST 硬编码
 * `OTEL_SDK_DISABLED=true` 禁用遥测 — env var MUST be set before any module
 * import that could initialize an OTEL tracer (i.e., before electron app ready).
 */

// D1-13: hard-disable OpenTelemetry. MUST come before any other import.
process.env.OTEL_SDK_DISABLED = "true";
process.env.OTEL_TRACES_EXPORTER = "none";
process.env.OTEL_METRICS_EXPORTER = "none";
process.env.OTEL_LOGS_EXPORTER = "none";
process.env.OTEL_PYTHON_DISABLE_AGENT = "true";

// Now safe to import the rest
import { app } from "electron";

// Stub handler — full dual-window logic lands in task 5.1
app.whenReady().then(() => {
  // eslint-disable-next-line no-console
  console.log(
    "[sddp-pet main] ready — OTEL_SDK_DISABLED=" +
      process.env.OTEL_SDK_DISABLED +
      " (D1-13 enforced)",
  );
  // TODO(task 5.1): createWindow1() + createWindow2() with click-through hit-testing
});

app.on("window-all-closed", () => {
  if (process.platform !== "darwin") app.quit();
});
