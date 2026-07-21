/**
 * Electron main process: dual-window creation + click-through + position
 * persistence (Dev-Phase 1 tasks 5.1, 5.2, 5.3).
 *
 * Per specs/desktop-pet-ui/spec.md:
 *   - window1 (transparent): PixiJS Canvas ONLY, 0 React DOM. DOM node count = 1.
 *   - window2 (opaque, transparent=false explicit): React panel root.
 *   - Click-through hit-testing drives `setIgnoreMouseEvents` (forward:true
 *     only forwards mousemove, never click — so hit-test MUST toggle).
 *   - Window positions persisted to localStorage on close, restored on open.
 */
import { app, BrowserWindow, screen, ipcMain } from "electron";
import * as path from "node:path";

// (D1-13 OTEL hard-disable lives in main.ts — set BEFORE any other import.)

const STORAGE_KEY_WINDOW1_POS = "sddp:window1:position";
const STORAGE_KEY_WINDOW2_POS = "sddp:window2:position";

let window1: BrowserWindow | null = null;
let window2: BrowserWindow | null = null;

function resolveAsset(subdir: "window1" | "window2"): string {
  // In production: dist/<subdir>/index.html; in dev: served by electron-vite
  const devRoot = path.join(__dirname, "..", "src");
  const prodRoot = path.join(__dirname, "..", "renderer", subdir);
  const isDev = !app.isPackaged && process.env.NODE_ENV !== "production";
  return isDev
    ? path.join(devRoot, subdir.replace("window", "window") + "-pet", "index.html")
    : path.join(prodRoot, "index.html");
}

/**
 * Create window1: transparent PixiJS pet window. Per D1-1, this window MUST
 * contain only a <canvas> (0 React DOM). The renderer is loaded from
 * `src/window1-pet/index.html` which imports `pet.ts` (no React).
 */
export function createWindow1(): BrowserWindow {
  const saved = loadPosition(STORAGE_KEY_WINDOW1_POS);
  const defaultPos = saved ?? defaultWindow1Position();

  window1 = new BrowserWindow({
    width: 280,
    height: 320,
    x: defaultPos.x,
    y: defaultPos.y,
    transparent: true,                // D1-1: window1 IS transparent
    frame: false,
    resizable: false,
    maximizable: false,
    minimizable: true,
    skipTaskbar: true,                // pet doesn't show in taskbar
    alwaysOnTop: true,
    hasShadow: false,
    webPreferences: {
      preload: path.join(__dirname, "preload.js"),
      contextIsolation: true,
      nodeIntegration: false,
    },
  });

  // D1-3 click-through: default ignores mouse events until pet area is hit.
  // The renderer (pet.ts) sends 'pet-hit-change' IPC events when the cursor
  // enters/leaves the pet sprite; we toggle setIgnoreMouseEvents here.
  // Initial state: ignoring (so user can interact with their desktop on launch).
  window1.setIgnoreMouseEvents(true, { forward: true });

  window1.on("move", () => savePosition(STORAGE_KEY_WINDOW1_POS, window1!.getPosition()));
  window1.on("closed", () => {
    if (window1) {
      savePosition(STORAGE_KEY_WINDOW1_POS, window1.getPosition());
    }
    window1 = null;
  });

  // Load the renderer
  if (process.env.ELECTRON_RENDERER_URL) {
    // dev mode: electron-vite dev serves renderer URLs
    window1.loadURL(`${process.env.ELECTRON_RENDERER_URL}/window1/`);
  } else {
    window1.loadFile(resolveAsset("window1"));
  }

  setupHitTestRelay(window1);
  return window1;
}

/**
 * Create window2: opaque React panel window. Per D1-2, transparent MUST be false
 * (Electron's default changed to true, so we set it explicitly).
 */
export function createWindow2(): BrowserWindow {
  const saved = loadPosition(STORAGE_KEY_WINDOW2_POS);
  const defaultPos = saved ?? defaultWindow2Position();

  window2 = new BrowserWindow({
    width: 640,
    height: 720,
    x: defaultPos.x,
    y: defaultPos.y,
    transparent: false,               // D1-2: window2 MUST be opaque (explicit)
    frame: true,
    resizable: true,
    maximizable: true,
    title: "SDDP-Pet Control Panel",
    webPreferences: {
      preload: path.join(__dirname, "preload.js"),
      contextIsolation: true,
      nodeIntegration: false,
    },
  });

  window2.on("move", () => savePosition(STORAGE_KEY_WINDOW2_POS, window2!.getPosition()));
  window2.on("close", (event: Electron.Event) => {
    // Persist position before window goes away
    if (window2) {
      savePosition(STORAGE_KEY_WINDOW2_POS, window2.getPosition());
    }
    // Closing window2 quits the app (D1-2 design choice: panel is the primary surface)
    // unless we're already in the middle of an app-wide quit (before-quit set the flag).
    const quitting = (app as unknown as { isQuitting?: boolean }).isQuitting;
    if (!quitting) {
      event.preventDefault();
      app.quit();
    }
  });

  if (process.env.ELECTRON_RENDERER_URL) {
    window2.loadURL(`${process.env.ELECTRON_RENDERER_URL}/window2/`);
  } else {
    window2.loadFile(resolveAsset("window2"));
  }

  return window2;
}

/**
 * D1-3 hit-testing relay: the PixiJS renderer in window1 knows which pixels
 * are pet vs. blank. It sends IPC messages to toggle window1's mouse-event
 * ignoring behavior.
 *
 * Why IPC: setIgnoreMouseEvents is a main-process API; renderer can't call it
 * directly. Renderer does mousemove hit-testing on its canvas + sends
 * 'pet-hit-change' events with the new "in pet?" boolean.
 */
function setupHitTestRelay(win: BrowserWindow): void {
  ipcMain.on("pet-hit-change", (_event, isHit: boolean) => {
    if (win.isDestroyed()) return;
    if (isHit) {
      win.setIgnoreMouseEvents(false);
    } else {
      win.setIgnoreMouseEvents(true, { forward: true });
    }
  });
}

// ---- position persistence (D1 spec: localStorage via renderer) ----
//
// We can't directly touch localStorage from the main process. The preload
// bridge exposes read/write APIs; for simplicity we use the in-memory cache +
// ask the renderer to persist via IPC. A real implementation would use
// electron-store or app.getPath("userData") + JSON file. For DP1 we lean on
// the renderer to call back.

const _positionCache: Record<string, { x: number; y: number }> = {};

function loadPosition(key: string): { x: number; y: number } | null {
  return _positionCache[key] ?? null;
}

function savePosition(key: string, pos: number[]): void {
  if (pos.length < 2) return;
  _positionCache[key] = { x: pos[0], y: pos[1] };
  // Also persist via renderer (best-effort; window1/window2 may be null at quit)
  const target = key === STORAGE_KEY_WINDOW1_POS ? window1 : window2;
  if (target && !target.isDestroyed()) {
    target.webContents.send("persist-window-position", { key, x: pos[0], y: pos[1] });
  }
}

function defaultWindow1Position(): { x: number; y: number } {
  const display = screen.getPrimaryDisplay();
  const { width, height } = display.workAreaSize;
  // Pet sits in the bottom-right corner by default
  return { x: width - 320, y: height - 360 };
}

function defaultWindow2Position(): { x: number; y: number } {
  const display = screen.getPrimaryDisplay();
  const { width } = display.workAreaSize;
  // Panel on the right side, vertically centered-ish (Electron centers automatically if x/y omitted)
  return { x: width - 700, y: 100 };
}

// Allow renderer to push saved positions back (cross-session persistence)
ipcMain.on("restore-window-position", (_event, payload: { key: string; x: number; y: number }) => {
  _positionCache[payload.key] = { x: payload.x, y: payload.y };
});

// ---- single-instance + lifecycle ----

// Quit when all windows are closed (except on macOS)
app.on("window-all-closed", () => {
  if (process.platform !== "darwin") app.quit();
});

app.on("activate", () => {
  if (BrowserWindow.getAllWindows().length === 0) {
    createWindow1();
    createWindow2();
  }
});
