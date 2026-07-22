# Desktop Pet UI

## Purpose

Dev-Phase 1 的桌宠人机交互入口。`desktop-pet-ui` 由两个独立的 Electron `BrowserWindow` 构成：window1（透明）纯 PixiJS Canvas 渲染桌宠精灵 / 气泡文本 / "AI 驱动" 标注，window2（不透明）承载 React 状态面板 / 诊断面板 / 确认按钮 / 成本显示 / SSH 设置页 / 隐私同意 modal。穿透点击通过 hit-testing 驱动 `setIgnoreMouseEvents`；窗口位置持久化到 localStorage 并在启动时恢复；首次启动弹出隐私同意 modal，用户拒绝则 `start_flow` RPC 被引擎拒绝（应用本身继续运行）；人类反馈确认点由 window2 ConfirmPanel 承载（window1 仅显示提示）。对应 `dod.md` D1-1、D1-2、D1-3、D1-8、D1-10、D1-12。权威来源：`analysis/00` §六、`analysis/07`。

## Requirements

### Requirement: 双窗口 Electron shell MUST 严格分离 PixiJS（window1）与 React（window2）

依据 `analysis/07` 第三节与 `dod.md` D1-1、D1-2、D1-12，桌宠 UI MUST 由两个独立的 Electron `BrowserWindow` 构成：
- **window1（透明）**：纯 PixiJS Canvas 渲染桌宠精灵 + 气泡文本 + "AI 驱动" 标注；DevTools 检查 window1 的 DOM 节点数 MUST = 1（仅 canvas 节点，0 React DOM）
- **window2（不透明）**：React 面板，含状态面板 / 诊断面板 / 确认按钮 / 成本显示 / SSH 设置页 / 隐私同意 modal
- window2 MUST 显式设置 `transparent: false`（Electron 当前版本 `transparent` 默认为 `true`）

PixiJS Canvas 与 React DOM 的事件系统冲突，混窗口不可行（`analysis/00` §六 baseline）。

#### Scenario: window1 仅含 canvas
- **WHEN** 启动应用后用 DevTools 检查 window1
- **THEN** DOM 节点数 MUST = 1（仅 canvas）；MUST 无任何 React DOM 节点；MUST 显示桌宠精灵与 "AI 驱动" 标注

#### Scenario: window2 渲染 6 类面板
- **WHEN** 启动应用后用 DevTools 检查 window2
- **THEN** MUST 渲染：状态面板、诊断面板、确认按钮、成本显示、SSH 设置页、隐私同意 modal；window2 MUST 不透明（`transparent: false`）

#### Scenario: "AI 驱动" 标注可见
- **WHEN** 用户查看 window1 桌宠气泡区域
- **THEN** 气泡旁 MUST 持续显示 "AI 驱动" 文本标注（对应 `dod.md` D1-12）

### Requirement: 穿透点击 MUST 通过 hit-testing 驱动 `setIgnoreMouseEvents`

依据 `analysis/07` 第四节与 `dod.md` D1-3，桌宠外的空白区域 MUST 让鼠标事件穿透到桌面；进入桌宠区域 MUST 可交互。Electron `setIgnoreMouseEvents(true, {forward: true})` **只转发 `mousemove`、永不转发 click**，因此 toggle MUST 由 hit-testing 驱动：
- 鼠标进入桌宠 sprite 命中区：`setIgnoreMouseEvents(false)` → 可交互
- 鼠标离开命中区：`setIgnoreMouseEvents(true, {forward: true})` → 穿透 + 转发 mousemove

#### Scenario: 点击桌宠与点击空白行为不同
- **WHEN** 用户在 window1 上点击桌宠 sprite 区域，再点击桌宠旁的空白区域
- **THEN** 点击桌宠 MUST 触发交互（如打开 window2 状态面板）；点击空白 MUST 穿透到下层桌面（不触发任何本应用行为）

### Requirement: 窗口位置 MUST 持久化到 localStorage 并在启动时恢复

依据 `analysis/00` §六与 `analysis/07` 第二节，window1 与 window2 的位置 MUST 在 `window.close` 时通过 `win.getPosition()` 保存到 localStorage，在应用下次启动时通过 `win.setPosition()` 恢复。

#### Scenario: 关闭重启后位置保持
- **WHEN** 用户拖动 window1 到屏幕坐标 (100, 200)，关闭应用，重新启动
- **THEN** window1 MUST 恢复到 (100, 200)；首次启动（无 localStorage 记录）MUST 使用默认位置（如屏幕右下角）

### Requirement: 首次启动 MUST 弹出隐私同意 modal；用户拒绝则 start_flow 被拒（应用继续运行）

依据 `analysis/09` §六与 `dod.md` D1-10（澄清后语义），首次启动应用 MUST 弹出隐私同意 modal，明示"代码与 proposal 将发送到远程 LLM provider"。用户操作：
- **同意**：modal 关闭，consent 持久化到 localStorage；后续 `start_flow` RPC 正常处理
- **拒绝**：modal 关闭，consent 持久化为 `false`；后续 `start_flow` RPC MUST 被引擎拒绝（返回 `error` 消息，`error_code=PRIVACY_CONSENT_REQUIRED`）；**应用本身 MUST 继续运行**以允许用户查看历史 / 修改设置 / 重新同意

#### Scenario: 首次启动显示同意 modal
- **WHEN** 用户首次启动应用（localStorage 无 consent 记录）
- **THEN** window2 MUST 显示隐私同意 modal；modal 文本 MUST 包含"数据将发送到远程 LLM" 提示；MUST 提供"同意"与"拒绝"按钮

#### Scenario: 拒绝后应用不退出
- **WHENT** 用户在隐私同意 modal 点击"拒绝"，然后尝试通过 `start_flow` RPC 启动流程
- **THEN** 引擎 MUST 返回 `error_code=PRIVACY_CONSENT_REQUIRED`；应用 MUST 继续运行（不退出）；用户 MUST 能打开设置页重新同意

#### Scenario: 同意后不再弹窗
- **WHENT** 用户点击"同意"，关闭应用，重新启动
- **THEN** modal MUST 不再出现；`start_flow` RPC MUST 正常处理

### Requirement: 人类反馈确认点 MUST 由 window2 ConfirmPanel 承载（window1 仅显示提示）

依据 `analysis/07` 第八节对 `dod.md` D1-8 的澄清，DP1 的人类反馈确认点（需求确认 / 方案确认 / 任务确认）MUST 按以下分工：
- **window1**：桌宠气泡显示当前待确认内容的摘要 + 桌宠动画状态（如"思考" → "等待"），**不含交互按钮**（与 D1-1 0-DOM 规则一致）
- **window2 ConfirmPanel（React）**：显示完整待确认内容 + y/n/e（同意 / 拒绝 / 编辑）三按钮；用户点击后通过 `user_feedback` RPC 发到引擎

#### Scenario: 同一 proposal 在 CLI 与 UI 下产出相同文档集
- **WHENT** 同一份 proposal 文本先用 `sddp run` CLI 跑通，再用桌宠 UI 跑通（两次都接受所有确认点）
- **THEN** 两次产出 MUST 是 4 markdown + cost_report.json 同结构；proposal.md 标题 MUST 相同；delta_spec.md 影响面分析 MUST 引用相同的 KG citations

#### Scenario: 确认点阻塞桌宠气泡更新
- **WHENT** 流程到达需求确认点（feedback_required Push 消息到达）
- **THEN** window1 桌宠气泡 MUST 显示"等待需求确认"提示文本 + 桌宠切换到"等待"动画；window2 ConfirmPanel MUST 显示 proposal 摘要 + y/n/e 按钮；用户 MUST 能在 window2 完成确认
