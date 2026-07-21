/**
 * Global type declarations for the renderer-side `window.sddp` bridge.
 *
 * All renderer code (window1 + window2) shares this single declaration to
 * avoid duplicate `declare global` conflicts. The actual implementation is
 * in `electron/preload.ts`; this file only describes the shape.
 */

export interface SshTestResult {
  ok: boolean;
  /** "auth_failed" | "network_unreachable" | "port_in_use" | "unknown" */
  errorKind?: string;
  message: string;
}

export interface SddpWindowAPI {
  /** window1 pet renderer → main: toggle click-through */
  sendPetHitChange: (isHit: boolean) => void;
  /** main → renderer: persist window position to localStorage */
  onPersistPosition?: (cb: (p: { key: string; x: number; y: number }) => void) => void;
  /** renderer → main: push saved positions back for cross-session restore */
  restorePosition?: (key: string, x: number, y: number) => void;
  /** window2 SSH settings → main: test SSH tunnel (D1-16) */
  testSsh?: (cfg: import("./window2-panel/ssh-settings/ssh-settings").SshConfig) => Promise<SshTestResult>;
}

declare global {
  interface Window {
    sddp?: SddpWindowAPI;
  }
}
