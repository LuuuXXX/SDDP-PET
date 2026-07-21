/**
 * Preload bridge: secure context-isolation-safe API exposed to renderers.
 *
 * Per Electron security best practices: renderers run with contextIsolation
 * enabled, so they CANNOT touch `require` or Node APIs directly. This preload
 * exposes only the explicitly-allowed IPC channels.
 *
 * Window1 (PixiJS pet) needs:
 *   - sendPetHitChange(isHit: boolean) → IPC 'pet-hit-change' to main for click-through toggle
 *   - onPersistPosition(callback) → receive position-save requests from main
 *
 * Window2 (React panel) needs:
 *   - onPersistPosition(callback)
 *   - restorePosition(key, x, y) → push saved positions back to main
 *
 * Both windows MAY also need access to secrets (window2 only) — but we expose
 * it via a separate `secrets` channel so window1 (transparent, less trusted)
 * cannot read API keys.
 */
import { contextBridge, ipcRenderer } from "electron";

const windowAPI = {
  /** Used by window1 pet renderer to signal hit-test changes for click-through. */
  sendPetHitChange: (isHit: boolean) => ipcRenderer.send("pet-hit-change", isHit),

  /** Receive position-save requests from main (renderer stores in localStorage). */
  onPersistPosition: (callback: (payload: { key: string; x: number; y: number }) => void) => {
    const handler = (_event: Electron.IpcRendererEvent, payload: { key: string; x: number; y: number }) => callback(payload);
    ipcRenderer.on("persist-window-position", handler);
    return () => ipcRenderer.off("persist-window-position", handler);
  },

  /** Push saved positions back to main (cross-session restore). */
  restorePosition: (key: string, x: number, y: number) =>
    ipcRenderer.send("restore-window-position", { key, x, y }),
};

try {
  contextBridge.exposeInMainWorld("sddp", windowAPI);
} catch (err) {
  // Preload scripts run in isolated world; failure here is fatal for renderer.
  // eslint-disable-next-line no-console
  console.error("[preload] failed to expose contextBridge:", err);
}

// Type declaration for renderer (imported via `declare global` in shared types)
export type SddpWindowAPI = typeof windowAPI;
