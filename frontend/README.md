# SDDP-Pet Frontend (Dev-Phase 1)

Electron dual-window desktop pet UI for SDDP-Pet. Dev-Phase 1 implements:

- **window1** (transparent): PixiJS pet + bubble + "AI 驱动" label (0 React DOM, D1-1)
- **window2** (opaque): React panel with 6 subpanels (state / diagnostic / SSH settings / privacy consent / cost / confirm)
- **WebSocket IPC client**: connects to backend `sddp serve` on `ws://localhost:8765`
- **Click-through hit-testing**: `setIgnoreMouseEvents` toggled by PixiJS mousemove (D1-3)
- **Encrypted API key storage**: `@napi-rs/keyring` + Electron `safeStorage` fallback (D1-9)

See `../openspec/changes/dev-phase-1-desktop-pet-mvp/` for the full spec.

## Quick start

### Prerequisites

- Node.js ≥ 20 (verified on 22.x)
- Backend running: `cd ../backend && pip install -e . && sddp serve --mock` (or with DeepSeek per `backend/scripts/deepseek-env.sh.example`)

### Install + dev

```bash
npm install                # may take ~1 min; Electron binary ~100MB
npm run dev                # electron-vite dev — launches both windows
```

### Production build

```bash
npm run build              # outputs to dist/main, dist/preload, dist/window1, dist/window2
npm run preview            # launch built version
```

### Test

```bash
npm run typecheck          # tsc --noEmit
npm test                   # vitest unit tests (35+ tests, jsdom environment)
npm run test:e2e           # Playwright e2e (requires Electron binary + dev machine)
```

### Key entry points

| Path | Purpose |
|------|---------|
| `electron/main.ts` | Electron main process entry; OTEL hard-disable; creates both windows |
| `electron/windows.ts` | `createWindow1/2` + click-through IPC relay + position persistence |
| `electron/preload.ts` | contextBridge — exposes `window.sddp.*` to renderers |
| `electron/secrets.ts` | `@napi-rs/keyring` wrapper + safeStorage fallback (D1-9) |
| `electron/ssh-tunnel.ts` | `ssh -L 8765:localhost:8765` child process management (D1-16) |
| `src/window1-pet/pet.ts` | PixiJS renderer (transparent window, 0 React DOM) |
| `src/window1-pet/pet-state.ts` | Pure 4-state state machine (idle/working/waiting/error) |
| `src/window2-panel/app.tsx` | React root with 6-panel tab state + WS client |
| `src/shared/ws-client.ts` | `SddpClient` — zod validation, RPC correlation, auto-reconnect |
| `src/shared/ws-schemas.ts` | zod schemas mirroring `backend/sddp/ipc/schemas.py` |

## Versions locked (per `analysis/07`)

| Library | Version | Source |
|---------|---------|--------|
| electron | 43.1.1 | npm latest stable |
| pixi.js | 8.19.0 | `analysis/07` §二 |
| react / react-dom | 19.2.0 | `analysis/07` §二 |
| vite | 7.3.6 | constrained by electron-vite 5 |
| electron-vite | 5.0.0 | latest stable |
| typescript | 5.7.3 | `analysis/07` says 5.6.x but 5.6.0 doesn't exist on npm |
| `@napi-rs/keyring` | 1.3.0 | `analysis/09` §二 (keytar EXCLUDED — Atom archived) |
| zod | ^3.23 | latest stable 3.x |

## Test environments

| Type | Where | Notes |
|------|-------|-------|
| vitest unit | any OS with Node 20+ | jsdom env; 46 tests; fast (~3s) |
| Playwright e2e | Windows / macOS dev machine | requires Electron binary; ~60s/run |
| Manual UX | Windows 11 (primary target per `analysis/00`) | D1-1/D1-3/D1-12/D1-16 hand-verify |

Linux headless environments (CI without X11) cannot run Electron — use
`ELECTRON_SKIP_BINARY_DOWNLOAD=1` during `npm install` and rely on vitest.

## IPC contract

All WebSocket messages conform to zod schemas in `src/shared/ws-schemas.ts`,
which mirror `backend/sddp/ipc/schemas.py` (Pydantic v2). Any protocol change
MUST update both files in lockstep; the next cross-language contract test
(D1-17, optional per `analysis/08` §九) will pin this with a parity test.
