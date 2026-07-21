# G7: Electron 双窗口桌宠架构 — 版本锁定与实现骨架

> 日期: 2026-07-21
> 状态: P0 DP1 前置（Dev-Phase 1 技术研究）
> 关联: 00-sddp-pet-final.md §6（架构细节·双窗口/穿透点击/位置持久化）；03-crewai-version-strategy.md（版本锁定方法论与诚实声明模板）；04-llm-provider-strategy.md（决策矩阵风格）；openspec/specs/development-roadmap/dod.md D1-1 / D1-2 / D1-3 / D1-8 / D1-12

---

## 一、问题陈述

Dev-Phase 1 把 SDDP 引擎从 CLI 前端切换为 Windows 桌宠前端。DP1 的 DoD 直接约束本文件必须先回答的五件事：

| DoD | 要求 | 本文件须回答 |
|-----|------|------------|
| D1-1 | 窗口1 透明，PixiJS 桌宠 + 气泡，**0 React DOM** | PixiJS 版本 + Application 骨架如何写出"0 React DOM"窗口 |
| D1-2 | 窗口2 不透明 React 面板（状态/诊断/确认/成本/SSH 5 子页） | React + Vite 工程结构与窗口不透明配置 |
| D1-3 | 鼠标进宠物区可交互；离开区 `setIgnoreMouseEvents(true, {forward:true})` 穿透+转发 | 该 API 在当前 Electron 是否仍工作、行为是否与 baseline 一致 |
| D1-8 | CLI 3 个确认点切换为桌宠气泡确认 | "气泡确认"承载于 window1（PixiJS）还是 window2（React）的决策 |
| D1-12 | 桌宠气泡旁标注"AI 驱动" | 标注渲染位置（PixiJS Text in window1） |

00-final §6 已给 baseline：双窗口（透明 PixiJS + 不透明 React）、穿透用 `setIgnoreMouseEvents`、位置用 `getPosition()` + localStorage。**本文件不推翻该设计，而是用当前库版本逐一验证 + 给出可粘贴的骨架代码**。验证结论：baseline 全部成立，但暴露两个 2026-07 才出现的新事实（§3.2 / §3.3）与一个工具链版本耦合陷阱（§二 R7）。

---

## 二、版本锁定矩阵

| 库 | 锁定版本 | 选型理由 | 已知问题 / 边界 |
|----|---------|---------|---------------|
| **electron** | `43.1.1` | 2026-07 最新 stable major；stable ≥2 个月（社区 bug 暴露窗口充分）；sandbox 自 v20 默认开启、IPC 硬化已稳定多版本；含 BaseWindow / WebContentsView 新视图模型，双窗口实现更干净 | `transparent` 默认值已改 `true`（§3.2）；`forward` 仅补发移动事件（§3.3） |
| **pixi.js** | `8.19.x` | v8 为面向 WebGPU/WebGL2 的重写，v8.x 进入性能稳定期；v7 已停主要修复；Sprite/Assets/Text API 满足桌宠渲染需求 | v8 为 breaking major：`Application.init()` 改异步、`Assets` 接口变更；DP1 从零实现，无迁移负担 |
| **react** | `19.2.x`（latest 19.2.7） | React 19 stable 已超 18 个月（2024-12 GA），`use`/Actions/Suspense 稳定；client API 成熟 | 无 |
| **react-dom** | `19.2.x` | 与 react 主版本对齐 | 无 |
| **vite** | `7.3.6`（**非 8**） | **被 electron-vite 5 的 peer dep 约束**：`electron-vite@5` 仅支持 `vite ^5‖^6‖^7`，不支持 vite 8；vite 7.3.6 是 7 系最新 stable | vite 8 的 esbuild/rollup 升级暂不可用；待 electron-vite 支持 vite 8 后作为升级事件评估 |
| **electron-vite** | `5.0.0` | Vite + Electron 集成事实标准；main / preload / renderer 三段构建；HMR 工作 | **peer 限制 vite 上界到 7**（见上行）；这是本矩阵的关键耦合点 |
| **@vitejs/plugin-react** | `5.2.0` | peer 同时支持 `vite ^4‖^5‖^6‖^7‖^8`，与上面的 vite 7.3.6 兼容 | 无 |
| **typescript** | `5.6.x` | main / preload / renderer 全 TS；与 electron 43 的 `@types/node ^24` 对齐 | 无 |
| **zod** | `^3.23` | WebSocket 消息（5 Push + 4 RPC + 4 响应）schema 校验；与后端 pydantic 对齐契约 | 无 |

### 锁定原则（沿用 03-croewai §三 准则 1-4，UI 侧套用）

1. **stable tag 而非 main HEAD**：electron 43.1.1 是 GitHub release 标 "Latest" 且距 2026-07-21 ≥2 周的版本
2. **精确 patch**：`electron==43.1.1`，写入 `package-lock.json`；不用 `^` 宽约束
3. **Node 版本**：构建机 Node 版本随 electron 43 内嵌 Node 主版本（实施时从 electron 43 release notes 确认，预期 22.x LTS）
4. **避开 breaking**：PixiJS v8 是 breaking major，但 DP1 从零实现，无存量代码，无 breaking 风险；**vite 锁 7 而非 8 属"主动避开耦合陷阱"**，非 breaking

### 诚实声明（沿用 03 §二）

electron / pixijs 的 patch 演进在 DP1 实施时可能已前移。本表给的是 2026-07-21 当天的 stable 锚点（均经 `npm view` 核验）。实施第一步须重跑：

```bash
npm view electron version          # 期望 ≥ 43.1.1
npm view pixi.js version           # 期望 ≥ 8.19.0
npm view electron-vite peerDependencies   # 期望仍含 vite ^7（否则可解锁 vite 8）
```

- 若仅 patch 前移（43.1.1 → 43.1.2）：直接采用新 patch
- 若 minor 前移（43.1 → 43.2）：跑 §3 双窗口冒烟后再升
- 若 major 前移（43 → 44）：视为升级事件，需评审（同 03 §4.3）
- 若 electron-vite 支持 vite 8：可作为单独升级 PR，解锁 vite 8 生态

---

## 三、双窗口架构验证（对照 00-final §6 baseline）

### 3.1 baseline 复核结论：**全部成立，无需推翻**

| baseline 设计 | 2026-07 现状（核验来源） | 结论 |
|--------------|-------------------------|------|
| 窗口1 透明 + PixiJS，0 React DOM | Electron BrowserWindow `transparent` 选项仍存在；PixiJS v8 `Application` 可在无框架页面独立挂载到 `<canvas>` | ✅ 沿用 |
| 窗口2 不透明 + React | 同上；但须显式 `transparent: false`（§3.2） | ✅ 沿用 + 实现注意 |
| 不用混合（Canvas 与 React DOM 事件冲突） | 2026 仍无理由推翻；PixiJS v8 EventSystem 与 React 合成事件同时挂同一 document 会产生 hit-test 歧义 | ✅ 双窗口隔离仍是正解 |
| 穿透用 `setIgnoreMouseEvents(true, {forward:true})` | API 存在；官方文档明确 `forward` 在 macOS+Windows 生效（§3.3） | ✅ 沿用 |
| 位置持久化 `getPosition()` + localStorage | API 稳定；多显示器须配 `screen.getDisplayMatching()` 做边界校正（§4.3） | ✅ 沿用 + 增强 |

### 3.2 新事实 1：`transparent` 默认值已变为 `true`

Electron 当前 BrowserWindow 文档原文（已核验 https://www.electronjs.org/docs/latest/api/browser-window）：

> `transparent` boolean (optional) - Whether to enable background transparency for the guest page. **Default is `true`.** Note: The guest page's text and background colors are derived from the color scheme of its root element…

这与 00-final §6 隐含的"窗口2 默认不透明"假设相反。**后果**：窗口2（React 面板）若不在构造选项中显式写 `transparent: false` + `backgroundColor`，启动时会透出桌面，D1-2 面板会"漏底"。

窗口1（PixiJS）受益于默认值，但仍应**显式写 `transparent: true`** 以抗未来默认值回调。

### 3.3 新事实 2：`forward` 行为比 baseline 描述更精确

官方文档（`win.setIgnoreMouseEvents(ignore[, options])`，已核验）原文：

> `forward` boolean (optional) *macOS* *Windows* — If true, forwards **mouse move messages** to Chromium, enabling mouse related events such as `mouseleave`. Only used when `ignore` is true. If `ignore` is false, forwarding is always disabled regardless of this value.
>
> Makes the window ignore all mouse events. All mouse events happened in this window will be passed to the window below this window.

baseline 描述"穿透+转发"是对的，但精确化为两条硬约束：

1. `ignore=true` 时，**点击事件永远不进 renderer**（直接穿透给下层窗口）
2. `forward:true` 只**额外补发 mousemove / mouseleave 类移动事件**给 renderer，不补发 click

因此"穿透+转发"模式的完整工作流必须是：renderer 监听 forward 回来的 `mousemove` → 几何命中宠物精灵 → 调 `setIgnoreMouseEvents(false)` 切回可交互 → 才能收到后续 click。这与 00-final §6 的"进入宠物区域 setIgnoreMouseEvents(false)"一致，但明确了**切换触发源是 forward 回来的 mousemove，而非 click**（click 在 ignore=true 时永远收不到）。实现骨架见 §4 / §5.3。

### 3.4 Linux（DP5）前瞻

`forward` 文档标注为 macOS + Windows。Linux（仅 DP5 支持，D5-2）须另验；Electron 文档同时指出 Wayland 下编程性 resize/position/focus 受限。DP5 须单独做可行性验证，与本 DP1 文档无关，仅登记为 R8。

---

## 四、穿透点击实现（main process 骨架）

### 4.1 窗口1 创建

```ts
// electron/main/window1.ts —— 透明桌宠窗口
import { BrowserWindow } from 'electron'
import { restorePosition, persistPosition } from './position'

export function createPetWindow(): BrowserWindow {
  const [x, y] = restorePosition()
  const win = new BrowserWindow({
    width: 320, height: 320, x, y,
    frame: false,
    transparent: true,                 // §3.2 显式
    alwaysOnTop: true,
    skipTaskbar: true,
    resizable: false,
    hasShadow: false,                  // 透明窗口去阴影，避免 Windows 残影
    webPreferences: { preload: PET_PRELOAD_PATH, sandbox: true, contextIsolation: true },
  })
  win.setIgnoreMouseEvents(true, { forward: true })   // §3.3 启动即穿透
  win.on('moved', () => persistPosition(win.getPosition()))
  win.loadFile('dist/window1/index.html')
  return win
}
```

### 4.2 IPC 切换通道（preload + main）

```ts
// electron/preload/window1.ts
import { contextBridge, ipcRenderer } from 'electron'
contextBridge.exposeInMainWorld('pet', {
  // renderer 命中检测后调用：true 收 click / false 穿透
  setInteractive: (on: boolean) => ipcRenderer.send('pet:set-interactive', on),
})

// electron/main/window1-ipc.ts
import { BrowserWindow, ipcMain } from 'electron'
ipcMain.on('pet:set-interactive', (e, on: boolean) => {
  const win = BrowserWindow.fromWebContents(e.sender)!
  win.setIgnoreMouseEvents(!on, { forward: !on })   // §3.3 契约
})
```

### 4.3 位置持久化（增强 baseline）

baseline 用裸 `getPosition()` + localStorage。main process 无 `localStorage`，DP1 改用 `electron-store`；并增强**多显示器边界校正**（避免桌宠被持久化到已拔掉的显示器，Windows 常见"窗口消失"问题）：

```ts
// electron/main/position.ts
import Store from 'electron-store'
import { screen } from 'electron'
const store = new Store<{ x: number; y: number }>({ name: 'pet-pos' })

export function restorePosition(): [number, number] {
  const saved = store.get('pet-pos')
  if (!saved) return [200, 200]
  const visible = screen.getAllDisplays().some(d =>
    saved.x >= d.bounds.x && saved.x < d.bounds.x + d.bounds.width &&
    saved.y >= d.bounds.y && saved.y < d.bounds.y + d.bounds.height)
  return visible ? [saved.x, saved.y] : [200, 200]   // 越界回默认
}

export function persistPosition(pos: readonly [number, number]) {
  store.set('pet-pos', { x: pos[0], y: pos[1] })
}
```

> 位置数据非敏感，明文 electron-store 可接受；密钥类数据走 D1-9 的 Windows Credential Manager，不走 electron-store。

### 4.4 行为契约（对应 D1-3 验证）

| 场景 | main 调用 | renderer 收到 |
|------|----------|-------------|
| 鼠标在窗口1 透明区 | `setIgnoreMouseEvents(true, {forward:true})` | 仅 mousemove（持续命中检测），**不收 click**（穿透给下层） |
| mousemove 命中桌宠精灵 hit-box | renderer 调 `pet.setInteractive(true)` → main 调 `setIgnoreMouseEvents(false)` | 收 mousemove + click（拖拽/点气泡） |
| 鼠标移出 hit-box | renderer 调 `pet.setInteractive(false)` → main 调 `setIgnoreMouseEvents(true, {forward:true})` | 回到穿透 |

### 4.5 已知边界（DP1 接受）

- **forward 只补发移动事件**：click 永远不进 ignore=true 的窗口（§3.3）。命中检测必须用 mousemove + 几何 hit-test
- **多显示器 / DPI 缩放**：mousemove 坐标在 DPI≠100% 时须除以 `devicePixelRatio` 再与 PixiJS 坐标比较
- **alwaysOnTop + 透明** 在 Windows 偶有重绘残影；`setHasShadow(false)` + `transparent:true` 组合缓解（已写入骨架）

---

## 五、PixiJS 桌宠骨架（window1，0 React DOM）

### 5.1 PixiJS vs Live2D 结论（验证 00-final §8 的推迟决策）

| 维度 | PixiJS 8（DP1 选） | Live2D Cubism Web SDK（DP4 可选） |
|------|-------------------|--------------------------------|
| 许可 | MIT，与项目 MIT 兼容，**可捆绑** | Live2D 专有许可；旧 `live2d-widget` 是 GPL（与 MIT 冲突，**不可捆绑**）；Cubism 4 Web SDK 商用需签约 |
| 美术资产 | 精灵图（sprite sheet），8 角色可同模板批量产 | 每角色需独立 .moc3 + 物理 rigs，单角色美术成本 10-50× 于精灵图 |
| 性能（2026-07） | WebGL2/WebGPU，单角色 <1% CPU | Cubism 4 已优化，但 8 角色 + 复杂物理在低端机仍吃力 |
| 状态机对接 | 自由实现，与 SDDP 6 状态机天然对齐 | 需映射到 Cubism 参数（ParamMouthOpenY 等），状态机被 SDK 绑架 |
| DP2 8 角色 | 加 8 个 sprite + 状态机配置即可 | 需 8 套 Live2D 模型，工期与美术成本不可控 |

**结论：00-final §8 把 Live2D 推迟到 DP4（D4-1）的判断在 2026-07 仍正确，甚至更牢固**——Cubism 商用许可门槛未降，GPL 旧实现仍不可捆绑。DP1 锁 PixiJS 8。

### 5.2 状态机设计（为 DP2 8 角色预留）

SDDP 角色状态（DoD D2-7）：`idle / working / thinking / waiting-feedback / error / converged`。DP1 实现 `idle / working / waiting-feedback / error` 4 个（DP2/3 补全）。要点：**状态机与角色解耦**，DP2 加角色只注册 sprite + 配置，不改状态机代码。

```ts
// window1/src/state.ts
export type PetState = 'idle' | 'working' | 'waiting-feedback' | 'error'
export interface PetRole {
  id: string
  sprites: Record<PetState, string>   // 每 state 对应一张精灵图
}
export const PET_ROLES: PetRole[] = [
  { id: 'requirement-officer', sprites: { idle: '...', working: '...', 'waiting-feedback': '...', error: '...' } },
  // DP2 补到 8 角色
]
```

### 5.3 Application + 精灵 + 命中检测骨架（v8 异步 init）

PixiJS v8 的 `Application.init()` 是异步，是与 v7 最大差异，骨架必须正确处理：

```ts
// window1/src/main.ts —— window1 entry（Vite 入口）
import { Application, Sprite, Assets, Text, FederatedPointerEvent } from 'pixi.js'
import type { PetState } from './state'

const HIT_W = 120, HIT_H = 160     // 精灵命中盒

async function boot() {
  const app = new Application()
  await app.init({ width: 320, height: 320, backgroundAlpha: 0, antialias: true })
  document.body.appendChild(app.canvas)

  const tex = await Assets.load('assets/pet-idle.png')
  const sprite = new Sprite(tex)
  sprite.anchor.set(0.5); sprite.x = 160; sprite.y = 160
  sprite.eventMode = 'static'       // v8 事件模式
  app.stage.addChild(sprite)

  // D1-12 AI 驱动标注
  const label = new Text({ text: 'AI 驱动', style: { fontSize: 12, fill: '#888' } })
  label.anchor.set(0.5); label.x = 160; label.y = 250
  app.stage.addChild(label)

  // §4 契约：透明区穿透 / 精灵区可交互
  let interactive = false
  const hit = (cx: number, cy: number) =>
    Math.abs(cx - 160) < HIT_W / 2 && Math.abs(cy - 160) < HIT_H / 2
  app.stage.eventMode = 'static'
  app.stage.on('pointermove', (e: FederatedPointerEvent) => {
    const over = hit(e.global.x, e.global.y)
    if (over !== interactive) {
      interactive = over
      ;(window as any).pet.setInteractive(over)   // → preload IPC → main
    }
  })

  // 状态切换入口（window2 WebSocketProvider 经 IPC 转发调用）
  ;(window as any).__setPetState = (s: PetState) => {
    Assets.load(spriteTextures[s]).then(t => sprite.texture = t)
  }
}
boot()
```

### 5.4 气泡（D1-1 的"气泡文本" + D1-8 的承载候选）

气泡用 PixiJS `Container` + `Graphics`（圆角矩形）+ `Text` 实现，**0 React DOM**：

```ts
// window1/src/bubble.ts
import { Container, Graphics, Text } from 'pixi.js'
export function makeBubble(msg: string): Container {
  const c = new Container()
  const bg = new Graphics().roundRect(0, 0, 200, 48, 8).fill({ color: 0xffffff, alpha: 0.95 })
  const t = new Text({ text: msg, style: { fontSize: 13, fill: '#222', wordWrap: true, wordWrapWidth: 190 } })
  c.addChild(bg, t)
  return c
}
```

气泡内**是否放交互按钮（确认/拒绝）**见 §8 对 D1-8 的影响——这是 DP1 须先决策的点。

---

## 六、React 面板骨架（window2，不透明）

### 6.1 工程结构（electron-vite 多入口）

```
sddp-pet/
├─ electron/
│  ├─ main/                 # main process（双窗口创建、IPC、SSH 隧道、引擎子进程）
│  │  ├─ index.ts
│  │  ├─ window1.ts         # §4.1
│  │  ├─ window2.ts
│  │  └─ position.ts        # §4.3
│  └─ preload/
│     ├─ window1.ts         # contextBridge pet.*
│     └─ window2.ts         # contextBridge api.*
├─ window1/                 # PixiJS renderer，独立 entry
│  ├─ index.html            # <canvas id="pet"></canvas>，无 #root
│  └─ src/main.ts           # §5.3
└─ window2/                 # React renderer，独立 entry
   ├─ index.html            # <div id="root"></div>
   └─ src/
      ├─ main.tsx           # createRoot
      ├─ App.tsx
      ├─ panels/
      │  ├─ StatusPanel.tsx        # D1-2 状态面板
      │  ├─ DiagnosticsPanel.tsx   # D1-2 / D1-15 诊断面板
      │  ├─ ConfirmPanel.tsx       # D1-8 确认按钮（候选承载，见 §8）
      │  ├─ CostPanel.tsx          # D1-2 成本显示
      │  └─ SshSettingsPanel.tsx   # D1-2 / D1-16 SSH 设置
      └─ ws/
         ├─ WebSocketProvider.tsx  # D1-4 / D1-8 5 Push + 4 RPC
         └─ schema.ts              # zod schema（§二 zod）
```

window2 的 BrowserWindow 构造（**注意 §3.2 显式 `transparent:false`**）：

```ts
// electron/main/window2.ts
import { BrowserWindow } from 'electron'
export function createPanelWindow(): BrowserWindow {
  const win = new BrowserWindow({
    width: 420, height: 640,
    transparent: false,              // §3.2 关键：覆盖新默认值 true
    backgroundColor: '#1e1e2e',      // 不透明底色
    frame: true,
    webPreferences: { preload: PANEL_PRELOAD_PATH, sandbox: true, contextIsolation: true },
  })
  win.loadFile('dist/window2/index.html')
  return win
}
```

### 6.2 WebSocketProvider（D1-4 / D1-8 共用）

window2 的 React renderer 是**唯一**持有 WebSocket 连接的窗口（window1 不直连引擎）。window1 的状态切换经 IPC 从 window2 转发：

```tsx
// window2/src/ws/WebSocketProvider.tsx（骨架）
import { useEffect, useRef } from 'react'
import { WSMessageSchema } from './schema'

export function WebSocketProvider({ children }: { children: React.ReactNode }) {
  const ws = useRef<WebSocket | null>(null)
  useEffect(() => {
    const url = localStorage.getItem('sddp.ws.url') ?? 'ws://localhost:8765'
    ws.current = new WebSocket(url)
    ws.current.onmessage = (ev) => {
      const msg = WSMessageSchema.parse(JSON.parse(ev.data))   // zod 校验
      switch (msg.type) {
        case 'agent_state_change':
          window.api.setPetState(msg.state)                    // → main → window1
          break
        case 'feedback_required':
          // 触发 ConfirmPanel（见 §8 决策）
          break
        // …document_produced / cost_update / error
      }
    }
    return () => ws.current?.close()
  }, [])
  return <Ctx.Provider value={ws.current}>{children}</Ctx.Provider>
}
```

---

## 七、已接受风险

| # | 风险 | 接受理由 | 缓解 / 触发条件 |
|---|------|---------|---------------|
| R1 | **Live2D 推迟到 DP4** | 00-final §8 已定；2026-07 验证结论更牢固（§5.1） | DP4 若选 Live2D 须独立模块不捆绑（D4-1） |
| R2 | **`forward:true` 只补发移动事件，不补发 click** | 官方文档明确（§3.3），属设计契约非 bug | 实现用 mousemove 命中检测，骨架已正确（§5.3） |
| R3 | **`transparent` 默认值改 true** | Electron 演进事实 | window2 显式 `transparent:false`（§6.1）；已写入骨架 |
| R4 | **electron / pixijs 锁定时 patch 可能前移** | 同 03 §二 诚实声明 | 实施首日跑 `npm view`；patch 前移直接采用，minor 前移跑 §3 冒烟 |
| R5 | **多显示器 / DPI 命中检测偏差** | Windows 多显示器生态固有 | mousemove 坐标除以 `devicePixelRatio`；位置持久化做边界校正（§4.3） |
| R6 | **window1 0 React DOM = 气泡内做富交互成本高** | D1-1 硬约束 | 若 D1-8 把确认按钮放 window1，须 PixiJS 手写按钮（hit area + 键盘 a11y 局限）。推荐放 window2（§8） |
| R7 | **electron-vite 5 不支持 vite 8** | peer dep 实测（§二） | 锁 vite 7.3.6；electron-vite 支持 vite 8 后作单独升级 PR |
| R8 | **Linux / Wayland click-through 未验** | DP1 仅 Windows；forward 文档标注 macOS+Windows | DP5 单独验证（D5-2），不影响 DP1 |

---

## 八、对 D1-DoD 的影响

| DoD | 本文档决策 | 是否需 scope 调整 |
|-----|-----------|----------------|
| D1-1 窗口1 0 React DOM | PixiJS 8 `Application` + 独立 entry（§5.3），`index.html` 仅 `<canvas>`，DOM 节点数=1 满足验证 | ✅ 无调整 |
| D1-2 窗口2 5 子页 | React 19 + Vite 7（electron-vite 5）多入口（§6.1）；**注意显式 `transparent:false`**（§3.2） | ✅ 无调整（实现注意） |
| D1-3 穿透点击 | `setIgnoreMouseEvents(true, {forward:true})` 在 electron 43 文档确认 macOS+Windows 生效（§3.3 / §4） | ✅ 无调整 |
| **D1-8 气泡确认** | **⚠️ 需 DP1 change 先决策**：确认按钮承载于 window1 PixiJS 气泡（富交互成本高，与 D1-1 0-React 张力）还是 window2 React ConfirmPanel（推荐，复用 React 表单）。DoD 文本"桌宠气泡确认"对承载窗口含糊；验证标准（"同一 proposal 在 CLI 与桌宠 UI 下产出相同文档集"）与承载位置无关 | **⚠️ 建议澄清**（见下方） |
| D1-12 AI 身份标注 | PixiJS `Text` 渲染在 window1 气泡旁（§5.3 `label.x=160; label.y=250`） | ✅ 无调整 |

### 单一需 scope 调整项：D1-8

研究暴露 D1-8 的"桌宠气泡确认"措辞与 D1-1 的"0 React DOM"约束存在张力。若严格按字面把"确认"放进气泡（window1），则须用 PixiJS 手写交互按钮 + 自实现键盘可访问性，工期显著高于复用 React，且 0-React 窗口的 a11y 远不如 DOM。

**推荐**：DP1 change 把 D1-8 拆为两条子验证——
- (a) **window1 气泡**显示提示文本（PixiJS `makeBubble`）+ 桌宠切 `waiting-feedback` 动画
- (b) **window2 ConfirmPanel**（React）承载确认/拒绝按钮，经 WebSocket 发 `user_feedback`

DoD 验证标准（"产出相同文档集"）不受影响，仅明确承载分工。本文件骨架已按此推荐布局（ConfirmPanel.tsx 在 window2/panels/，气泡在 window1/src/bubble.ts）。

---

## 九、DP1 落地清单（给 opsx-apply 的可执行项）

1. 锁定 `package.json`：electron 43.1.1 / pixi.js 8.19.x / react 19.2.x / **vite 7.3.6** / electron-vite 5.0.0 / @vitejs/plugin-react 5.2.0 / typescript 5.6 / zod 3.23（§二）
2. 起 electron-vite 多入口工程（§6.1 目录）
3. 实现 window1 透明窗口 + `setIgnoreMouseEvents` + IPC 切换（§4）
4. 实现 window1 PixiJS Application + 状态机骨架 + AI 标注（§5）
5. 实现 window2 React 面板 5 子页 + WebSocketProvider（§6）
6. 冒烟：D1-3 穿透（透明区 click 穿透 / 精灵区 click 命中）、D1-1 DOM 节点数=1
7. 决策 D1-8 承载分工并写入 DP1 change 的 spec（§8）
