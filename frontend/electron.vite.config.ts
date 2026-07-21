import { defineConfig } from "electron-vite";
import react from "@vitejs/plugin-react";
import { resolve } from "node:path";

// Dev-Phase 1 dual-window Electron config:
//   - main: Node-side main process (window creation, click-through, secrets, SSH tunnel)
//   - preload: privileged bridge between main and renderer (context-isolation safe)
//   - renderer-window1: PixiJS pet (transparent window, 0 React DOM)
//   - renderer-window2: React panel (opaque window)
export default defineConfig({
  main: {
    build: {
      outDir: "dist/main",
      lib: { entry: "electron/main.ts" },
    },
  },
  preload: {
    build: {
      outDir: "dist/preload",
      lib: { entry: "electron/preload.ts" },
    },
  },
  renderer: [
    {
      name: "window1",
      root: "src/window1-pet",
      build: {
        outDir: "dist/window1",
        rollupOptions: { input: resolve(__dirname, "src/window1-pet/index.html") },
      },
      plugins: [react()],
    },
    {
      name: "window2",
      root: "src/window2-panel",
      build: {
        outDir: "dist/window2",
        rollupOptions: { input: resolve(__dirname, "src/window2-panel/index.html") },
      },
      plugins: [react()],
    },
  ],
});
