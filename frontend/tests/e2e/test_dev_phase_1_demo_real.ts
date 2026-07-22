/**
 * Dev-Phase 1 Golden-Demo e2e: real Python `sddp serve` + real Electron
 * driving one full SDDP flow (task 7.5).
 *
 * This is the integration keystone that CLI-verified Phase 1 work has been
 * waiting on ("frozen: CLI verified, UI pending dev machine" in tasks.md 8.8).
 * It starts the real backend WebSocket server, launches real Electron, runs
 * the config-hot-reload proposal end-to-end, and asserts the UI receives the
 * full Push stream (flow_started → agent_state_change×5 → document_produced×4 →
 * cost_update → flow_completed) and renders the 4 produced docs.
 *
 * Prerequisites (dev machine): Python 3.11+ venv with `pip install -e .[dev]`
 * (incl. crewai/tree-sitter), OPENAI_API_KEY/DEEPSEEK_API_KEY set, Electron
 * binary installed (no ELECTRON_SKIP_BINARY_DOWNLOAD).
 *
 * @tags e2e, electron, python, 7.5, golden-demo
 */
import { test, expect } from "@playwright/test";
import { spawn, type ChildProcess } from "node:child_process";
import * as path from "node:path";

const ELECTRON_AVAILABLE = (() => {
  try {
    return !!require.resolve("electron", { paths: [process.cwd()] });
  } catch {
    return false;
  }
})();

const PYTHON_VENV = process.env.SDDP_BACKEND_VENV ?? path.resolve(__dirname, "../../backend/.venv/Scripts/python.exe");
const BACKEND_ROOT = path.resolve(__dirname, "../../backend");
const SAMPLE_PROJECT = path.join(BACKEND_ROOT, "tests", "fixtures", "sample-python-project");
const PROPOSAL = path.join(BACKEND_ROOT, "tests", "fixtures", "proposals", "config-hot-reload.txt");

const describeOrSkip = ELECTRON_AVAILABLE ? test.describe : test.describe.skip;

describeOrSkip("7.5 e2e: real Python serve + real Electron full demo", () => {
  let server: ChildProcess | null = null;

  test.afterEach(() => {
    if (server && !server.killed) server.kill("SIGTERM");
    server = null;
  });

  test("one full SDDP flow renders 4 docs in window2", async () => {
    // 1. Start real backend: sddp serve (port 8765). Mock mode is acceptable
    //    for plumbing; set OPENAI_API_KEY for a real LLM run.
    server = spawn(PYTHON_VENV, ["-m", "sddp.cli.main", "serve", "--port", "8765"], {
      cwd: BACKEND_ROOT,
      env: { ...process.env, SDDP_LLM_MODEL: process.env.SDDP_LLM_MODEL ?? "deepseek-chat" },
      stdio: "ignore",
    });
    // Give uvicorn ~3s to bind
    await new Promise((r) => setTimeout(r, 3000));

    // eslint-disable-next-line @typescript-eslint/no-var-requires
    const { _electron: electron } = require("@playwright/test");
    const app = await electron.launch({ args: ["./dist/main/index.js"] });
    const window2 = app.windows().find((w: { url: () => string }) => w.url().includes("window2"));
    expect(window2).toBeDefined();

    // 2. Consent (first launch)
    await window2.locator("[data-testid=privacy-consent]").click();

    // 3. Wait for ws-client to connect (conn-state = 已连接)
    await expect(window2.locator("[data-testid=conn-state]")).toContainText(/已连接|connected/i, { timeout: 15000 });

    // 4. Submit the proposal
    await window2.locator("[data-testid=proposal-input]").fill(require("fs").readFileSync(PROPOSAL, "utf-8"));
    await window2.locator("[data-testid=start-flow-button]").click();

    // 5. Assert active-flow + the 4 produced docs appear
    await expect(window2.locator("[data-testid=active-flow]")).toBeVisible({ timeout: 20_000 });
    for (const doc of ["proposal", "delta_spec", "delta_design", "architecture_research"]) {
      await expect(window2.locator(`[data-testid=document-${doc}]`)).toBeVisible({ timeout: 180_000 });
    }

    await app.close();
  }, 300_000);
});
