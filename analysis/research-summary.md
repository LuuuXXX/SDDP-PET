# Desktop Pet Technology Research Summary

> **平台决策更新(2026-07-20)**: 目标平台调整为Windows桌面; Linux仅作远程任务服务器. Tauri在Windows透明窗口可用, 但Electron生态更成熟, 仍为首选.

## 1. Desktop Pet (桌宠/Shimeji) Implementations

### Top Projects by Stars

| Project | Stars | Language | Tech Stack | Key Features |
|---------|-------|----------|------------|--------------|
| **clawd-on-desk** (rullerzhou-afk) | 5,484 | JavaScript | Electron, SVG animation, pixel art | AI agent watcher for Claude Code/Codex/Cursor/Copilot/Gemini |
| **Mate-Engine** (shinyflvre) | 3,414 | ShaderLab | Unity, VRM support | Free Desktop Mate alternative with custom VRM, Steam distribution |
| **desktopPet** (Adrianotiger) | 1,123 | C# | .NET, WinForms | eSheep recreation, XML-based sprite config, web demo on GitHub Pages |
| **LingChat** (SlimeBoyOwO) | 1,096 | Rust | Tauri, Live2D | AI-driven galgame chat with desktop pet, scheduling, emotional expressions |
| **TokenTracker** (mm7894215) | 1,042 | JavaScript | Electron, native macOS/Windows | AI token tracker with desktop pet + 4 widgets + achievements |
| **Ark-Pets** (isHarryh/Ark-Pets) | 1,004 | Java | libGDX, Spine | Arknights (明日方舟) desktop pets, Spine animation, cross-platform |
| **openpets** (alvinunreal) | 929 | TypeScript | Electron, Plugin SDK v3 | Desktop companion platform with plugin SDK, coding-agent integrations |
| **DyberPet** (ChaozhongLiu/DyberPet) | 865 | Python | PySide6 | Desktop Cyber Pet Framework, modular plugin system |

### Shimeji-Specific Projects

| Project | Stars | Language | Description |
|---------|-------|----------|-------------|
| **Shijima-Qt** (pixelomer) | 195 | C++ | Cross-platform shimeji runner using Qt6, GPL-3.0, **archived** |
| **vibebud** (Shellishack) | 72 | TypeScript | Floating AI virtual pets for Codex/Claude Code on desktop & mobile |
| **shimeji-ee** (gil) | 54 | Java | Classic shimeji desktop pet fork, Mac compat fixes |
| **Shimeji-Desktop** (DalekCraft2) | 39 | Java | Modernized shimeji-ee ported to JDK 25, AWT/Swing |
| **NeurolingsCE** (qingchenyouforcc) | 31 | C++ | Deep modification of Shijima-Qt, Neuro-sama themed shimeji |
| **CoPet** (ChanceYu) | 21 | Rust | Tauri-based desktop pet reacting to AI agents (Claude Code, Codex, etc.) |

### Key Technical Components Across Implementations

1. **Sprite Animation**: XML/JSON config files defining animation states and frame sequences (shimeji-ee, desktopPet); Spine skeleton animation (Ark-Pets); SVG animation (clawd-on-desk)
2. **Window Transparency**: Platform-specific APIs - Win32 layered windows (C#), X11 SHAPE extension (C++/Qt), Electron's `transparent: true` BrowserWindow, Tauri's window transparency
3. **Drag Interaction**: Mouse event handlers with position delta tracking; click-through mode toggle (allow pet to walk behind windows)
4. **Edge Detection**: Screen boundary detection to prevent pets from walking off-screen; wall/floor walking behavior
5. **AI Agent Integration**: Recent trend - watching Claude Code/Codex terminal output via filesystem polling, reacting to agent states (idle, working, error)

---

## 2. Live2D / Spine2D Libraries

### Live2D

**Live2D Cubism SDK** (proprietary core, open framework):
- **Cubism Native SDK** (github.com/Live2D/CubismNativeSamples) - C++ with OpenGL/Metal/D3D11/Vulkan backends, GPL-3.0 compatible framework
- **Cubism Web SDK** (github.com/Live2D/CubismWebSamples) - TypeScript, supports Cubism 2/4/5, Node.js-based
- **live2d-widget** (stevenjoezhang) - 10,828 stars, JavaScript web widget for Live2D 看板娘 on web pages, GPL-3.0
- **l2d-widget** (hacxy) - 596 stars, TypeScript, zero-dependency drop-in Live2D for web, supports Cubism 2/4/5
- **easy-live2d** (Panzer-Jack) - 200 stars, TypeScript, PixiJS-based Live2D Web SDK
- **Live2dRender** (LSTM-Kirigaya) - 182 stars, TypeScript, web renderer for new Live2D versions
- **galnetwen/Live2D** - 1,054 stars, JavaScript web Live2D display
- **airi** (moeru-ai) - 42,863 stars, TypeScript, AI companion with Live2D + VRM + realtime voice chat, MIT license

**Key constraint**: Live2D Cubism **Core** is proprietary (closed-source). The framework layer is open, but you must download the core binary separately. Commercial use requires a license from Live2D Inc.

### Spine2D

- **Spine** is proprietary software by Esoteric Software. No open-source runtime implementations exist on GitHub.
- **Ark-Pets** (1,004 stars) uses Spine runtime (licensed) with libGDX to render Arknights characters - demonstrates Spine integration in desktop pets
- The Spine runtime itself is available under a specific license from Esoteric Software; it's not open-source but redistributable under their terms
- **No open-source Spine alternatives** were found that match Spine's capabilities (mesh deformation, IK constraints, etc.)

---

## 3. Interactive AI Agent Visualization

### Existing Projects

| Project | Stars | Language | Description |
|---------|-------|----------|-------------|
| **openclaw-office** (wickedapp) | 154 | JavaScript | Virtual AI Office Dashboard for OpenClaw - real-time multi-agent workflow visualization |
| **agent-monitor** (ruiqili2) | 54 | TypeScript | Real-time AI agent visualization dashboard for OpenClaw, pixel-art office, 18 behaviors |
| **openclaw-virtual-office** (thx0701) | 46 | HTML | Pixel-art virtual office dashboard for OpenClaw agent sessions |
| **Star-Office-UI-Node** (wangmiaozero) | 22 | JavaScript | Pixelated office dashboard for multi-agent collaboration |
| **agent-lens** (naimjeem) | 19 | HTML | Local dashboard for visualizing 7 AI coding agents - sessions, token costs, tool calls |
| **hermesdashboard** (mojomast) | 17 | Python | Web dashboard for Hermes AI agent runtime - chat, sessions, memory, graph visualization |

### Key Observation
The AI agent visualization space is dominated by the **OpenClaw** ecosystem (an open-source fork of OpenAI's Codex). Most dashboards use:
- Pixel-art character representations of agents in virtual "office" settings
- Real-time state updates (idle, coding, reviewing, debugging)
- Chat integration with agents
- Token/cost tracking overlays

No projects were found that combine **Live2D/Spine-quality character animation** with **AI agent workflow visualization** - this appears to be an open niche.

---

## 4. Electron vs Tauri for Desktop Pets

### Comparison for Transparent Overlay Use Case

| Aspect | Electron | Tauri |
|--------|----------|-------|
| **Runtime** | Chromium embedded (~100-150MB) | System WebView (~3-10MB) |
| **Language** | JavaScript/TypeScript | Rust backend + WebView frontend |
| **Transparent Windows** | `BrowserWindow({transparent: true})` well-documented | Supported via `WindowConfig.transparent` |
| **Click-through** | `setIgnoreMouseEvents(true)` API exists | Supported via `window.set_ignore_cursor_events(true)` |
| **Bundle Size** | ~100MB+ | ~3-10MB |
| **Memory Usage** | ~150-300MB typical | ~20-50MB typical |
| **Cross-platform** | Windows, macOS, Linux | Windows, macOS, Linux |
| **GPU Acceleration** | Chromium GPU process | System WebView GPU |
| **Maturity for overlay** | Battle-tested (clawd-on-desk, openpets, TokenTracker all use Electron) | Growing adoption (LingChat, CoPet use Tauri) |
| **IPC Performance** | IPC over named pipes | Rust FFI - much faster |
| **Always-on-top** | Well-supported | Supported |
| **Hot reload/dev** | Excellent tooling | Good but less mature |

### Evidence-Based Finding
- **3 major desktop pet projects use Electron** (clawd-on-desk, openpets, TokenTracker)
- **2 major desktop pet projects use Tauri** (LingChat, CoPet)
- Electron has more mature transparent overlay support and more community examples
- Tauri has significantly lower resource overhead, critical for an always-running overlay app
- **Recommendation**: Tauri is better suited for a lightweight desktop pet overlay due to its ~10x smaller footprint, but Electron offers more battle-tested transparency/overlay patterns. If the pet needs complex web rendering (Live2D, Spine), Electron's Chromium may render more consistently across platforms.

---

## 5. Python Desktop Pet Implementations

| Project | Stars | Tech Stack | Key Features |
|---------|-------|------------|--------------|
| **DyberPet** (ChaozhongLiu) | 865 | PySide6 (Qt for Python) | Framework with plugin system, custom animations, status bar, speech bubble |
| **Desktop-Cat** (1ilit) | 97 | tkinter | Simple sleeping/wandering cat, pixel art sprites |
| **Resona-Desktop-Pet** (JodieRuth) | 42 | PySide6 + LLM + SoVITS + STT | AI voice chat desktop pet, semi-realtime voice conversation |
| **wkostusiak/desktop-pet** | 40 | tkinter + PIL | GIF animation on desktop, taskbar pet |
| **pyCatAI-pet** (R37r0-Gh057) | 30 | tkinter + win32api + Gemini Vision | AI-powered Windows desktop pet with screen understanding |
| **MikuPet** (CharlesWiiFlowers) | 17 | tkinter + Python 3 | Hatsune Miku-inspired shimeji-like pet |
| **FloweyPet** (winwinking) | 12 | PyQt6 | Undertale Flowey desktop pet |
| **fatigue-monitoring-desktop-pet** (idealiu555) | 7 | Python + CNN + CV | Fatigue monitoring with desktop pet reminders |
| **PuppyPal** (scaxkl) | 8 | tkinter | Interactive puppy with feeding, petting, emotion system |

### Common Python Libraries Used
1. **tkinter** - Most common for simple pets; built-in, no deps. Creates transparent windows via `wm_attributes('-transparentcolor', color)`. Limitation: limited animation quality.
2. **PySide6/PyQt6** - Higher quality rendering, better transparency (`setAttribute(Qt.WA_TranslucentBackground)`), smoother animations. Used by DyberPet (865 stars - most popular Python pet).
3. **win32api (pywin32)** - Windows-specific: click-through (`SetWindowLong`), always-on-top, window manipulation
4. **PIL/Pillow** - Image loading and sprite sheet processing
5. **SoVITS/STT** - Voice synthesis/recognition for AI-interactive pets (Resona-Desktop-Pet)

---

## 6. Web-Based Desktop Pets

### Browser-Targeted Projects

| Project | Stars | Description |
|---------|-------|-------------|
| **shimeji-browser-extension** (shimejimascot) | new | Browser extension bringing shimeji mascots to web pages |
| **live2d-widget** (stevenjoezhang) | 10,828 | Web-based Live2D 看板娘 widget for any website |
| **l2d-widget** (hacxy) | 596 | Zero-dependency drop-in Live2D web component |
| **desktopPet web demo** (Adrianotiger) | 1,123 | Has a GitHub Pages web demo version |

### How Web-Based Pets Handle Animations & Interaction
1. **CSS/JS Animation**: DOM-based sprite animation using `requestAnimationFrame` or CSS animations. Sprites are positioned with `position: fixed` or `position: absolute`.
2. **Canvas/WebGL Rendering**: For higher-quality animations (Live2D uses WebGL canvas). PixiJS is commonly used as a rendering framework.
3. **Interaction**: Mouse events on the canvas/DOM element for drag, click; keyboard events for special actions
4. **Browser Extensions**: Chrome/Firefox extensions can inject pet elements into any webpage using content scripts. The shimeji-browser-extension does this.
5. **Limitation**: Web-based pets cannot overlay on the OS desktop - they're confined to browser windows. This is why desktop pet projects use Electron/Tauri to wrap web tech into native windows.

### Hybrid Approach (Web Tech + Native Window)
The dominant pattern in modern desktop pets is **web tech rendered in a native transparent window**:
- Electron/Tauri wraps a WebView with transparent background
- The pet is rendered using HTML/CSS/Canvas/WebGL inside the WebView
- Native APIs handle click-through, always-on-top, screen edge detection
- This gives web-quality animation with desktop overlay capability

---

## Summary of Key Trends

1. **AI Agent Integration** is the hottest new trend in desktop pets (2026) - projects like clawd-on-desk (5.4k stars), openpets, CoPet, TokenTracker all combine pet visualization with AI coding agent monitoring
2. **Tauri adoption** is growing for desktop pets due to its small footprint (CoPet, LingChat), though Electron remains more common
3. **Live2D** has extensive web ecosystem (10k+ stars on live2d-widget) but proprietary core limits fully open-source use
4. **Spine** has no open-source alternative; Ark-Pets demonstrates real-world Spine usage in desktop pets
5. **Python + PySide6** (DyberPet pattern) is the most capable Python approach, far superior to tkinter for animation quality
6. **No project** currently combines high-quality Live2D/Spine character animation with real-time AI agent workflow visualization - this is an open niche
7. The **shimeji XML format** remains the standard for defining pet behavior states (walk, idle, fall, climb, drag, etc.)
