# 08: WebSocket IPC 契约（Python 引擎 ↔ Electron UI）

> 日期: 2026-07-21
> 状态: P0 — Dev-Phase 1 前置（D1-4/5/6/7/16 的实现依据）
> 关联: `analysis/00-sddp-pet-final.md` §7（协议设计）；`analysis/03-crewai-version-strategy.md`（锁定风格模板）；`analysis/04-llm-provider-strategy.md`（决策风格模板）；`openspec/specs/development-roadmap/dod.md` D1-4/5/6/7/16

---

## 一、问题陈述

`analysis/00` §7 已定下 WebSocket IPC 协议（5 Push + 4 RPC + 4 RPC-response + 错误格式 + 心跳 30s/10s/3-miss + `message_id` 关联），但**仅是协议草案**，未给出：

1. 服务端/客户端分别用哪个库、锁哪个版本（DP0 的 `requirements.lock.txt` 已含 `starlette/uvicorn/websockets` 传递依赖，但未显式纳入 FastAPI）
2. 9 类操作的**逐字段 TypeScript / Pydantic 契约**（前端开发与后端开发的硬接口）
3. 心跳"30s ping / 10s pong / 3 miss = 断开"的**可执行实现**（服务端与客户端各自如何写）
4. `message_id` 在 WS 边界上的**请求-响应关联**机制
5. 断线时**在途 RPC** 的命运，以及与 DP0 `@persist` 恢复（`flow_state.py` SQLite）的衔接
6. 远程模式 SSH 隧道在 2026-07 是否仍为最优选

本文件锁定上述 6 项，作为 D1-4（WS server↔Electron）、D1-5（5 Push 渲染）、D1-6（4 RPC）、D1-7（心跳）、D1-16（SSH 远程）的可执行实现依据。

**本文件不修改任何代码**；所有 `pyproject.toml`/`schemas.py` 片段均为提案，待 OpenSpec DP1 change 落地。

---

## 二、库版本锁定

### 2.1 关键事实：DP0 lockfile 已含 WS 服务端栈

`backend/requirements.lock.txt`（DP0 锁定产物，`crewai==1.15.4` 传递引入）已含：

| 包 | 锁定版本 | 来源 |
|----|---------|------|
| `starlette` | `1.3.1` | crewai 传递依赖 |
| `uvicorn` | `0.51.0` | crewai 传递依赖 |
| `websockets` | `16.1.1` | starlette 传递依赖 |
| `anyio` | `4.14.2` | starlette 传递依赖 |
| `websocket-client` | `1.9.0` | crewai-tools 传递依赖（仅 CLI 测试用，非生产） |

即：**WS 服务端运行时栈已经齐备且锁定**。Dev-Phase 1 唯一要做的是把 FastAPI 本身（starlette 的薄封装）从"传递依赖"提升为"直接依赖"，并锁到精确 patch。

### 2.2 锁定表（提案，写入 `backend/pyproject.toml` `[project.dependencies]`）

| 包 | 锁定版本（提案） | 选型准则（沿用 `analysis/03` 准则 1-4） | 验证方式 |
|----|-----------------|---------------------------------------|---------|
| `fastapi` | `==<TBD-patch>` ⚠️ | 准则 2（stable tag ≥ 2 周）+ **不抬升已锁 starlette==1.3.1** | 见 2.3 验证脚本 |
| `uvicorn[standard]` | `==0.51.0` | 已锁；显式提升为直接依赖（原为传递） | `pip show uvicorn` 与 lockfile 一致 |
| `websockets` | `==16.1.1` | 已锁；uvicorn WS 子协议实现 | 同上 |
| `python-socks` | **不引入** | SSH 隧道在 OS 层完成（见 §7），Python 侧无需 SOCKS 客户端 | N/A |

> **诚实声明（沿用 `analysis/03` §二）**：直接在分析阶段断言 `fastapi==0.118.X` 这类精确 patch 是不负责任的——FastAPI 在 2026-07 的具体 patch 号、其对 starlette 的下限要求是否覆盖 `1.3.1`，需在 DP1 第 0 步实查。准则 + 验证脚本如下，**不直接给魔法版本号**。

### 2.3 FastAPI 版本验证脚本（DP1 第 0 步，骨架）

```bash
# backend/scripts/verify_fastapi_version.sh
# 准则: 选 stable ≥ 2 周；不抬升 starlette/uvicorn/websockets 任一已锁版本
TARGET=$(pip index versions fastapi | head -3 | tail -1)   # 取 latest stable

python -m venv .verify-venv && source .verify-venv/bin/activate
pip install -r requirements.lock.txt                        # 先铺 DP0 锁定基线
pip install "fastapi==$TARGET"

# 准则 1 硬约束: 安装后 starlette/uvicorn/websockets 版本必须不变
python -c "
import importlib.metadata as m
assert m.version('starlette') == '1.3.1', f'starlette bumped to {m.version(\"starlette\")}'
assert m.version('uvicorn')    == '0.51.0', f'uvicorn bumped to {m.version(\"uvicorn\")}'
assert m.version('websockets') == '16.1.1', f'websockets bumped to {m.version(\"websockets\")}'
print('fastapi', m.version('fastapi'), ': compatible with locked WS stack')
"

# 准则 2: WS 端点冒烟
python -c "
from fastapi import FastAPI, WebSocket
app = FastAPI()
@app.websocket('/ws')
async def ws(w: WebSocket):
    await w.accept(); await w.send_text('ok'); await w.close()
print('FastAPI WS endpoint import OK')
"
```

通过后产出：`requirements.lock.txt` 重新 `pip-compile`，FastAPI 进入直接依赖列表，starlette/uvicorn/websockets pin **不移动**。若任一传递依赖被抬升 → 回退到上一个 FastAPI patch 重试（准则 1 优先于准则 2）。

### 2.4 客户端（Electron 渲染进程）

**不引入第三方 WS 库**。Electron 渲染进程使用浏览器原生 `WebSocket` API（Chromium 实现，支持 RFC 6455 全集）。理由：

1. 零依赖、零供应链风险（与 MIT/开源定位一致）
2. 浏览器原生 WS 已支持自动重连策略的可编程层（我们在应用层实现，见 §5）
3. 协议级 ping/pong 由 Chromium 自动处理（无法配置，故我们**额外**在应用层做 JSON 心跳，见 §5.1）

Node 主进程如需 WS（例如健康探针），用已锁的 `websocket-client==1.9.0`；MVP 不需要。

---

## 三、消息契约（TypeScript）

放在 `frontend/src/ipc/messages.ts`（提案）。**判别联合（discriminated union）on `type` 字段**，覆盖 §7 全部 13 个具名形状（5 Push + 4 RPC 请求 + 4 RPC 响应；RPC 请求与响应用 `message_id` 关联，故同属一个关联集）。

```typescript
// frontend/src/ipc/messages.ts （提案）

// ===== 公共类型 =====
export type AgentName =
  | "requirement_officer" | "orchestrator" | "architect"
  | "executor" | "code_asset_manager";
export type AgentState = "idle" | "working" | "thinking" | "waiting-feedback" | "error";
export type ErrorCode =
  | "LLM_TIMEOUT" | "LLM_AUTH_FAIL" | "LLM_RATE_LIMIT"
  | "PARSE_FAILURE" | "FLOW_STUCK"
  | "KNOWLEDGE_GRAPH_ERROR" | "SSH_CONNECTION_LOST";
export type Severity = "critical" | "error" | "warning";
export type FlowStatus = "running" | "resuming" | "aborted";

/** ISO-8601 UTC string, e.g. "2026-07-21T08:30:00.123Z" */
export type ISO8601 = string;
/** UUID v4 string */
export type MessageId = string;

// ===== 1. Push 消息（引擎 → 前端，5 种） =====
export interface AgentStateChangePush {
  type: "agent_state_change";
  agent: AgentName;
  state: AgentState;
  phase: 0 | 1 | 2;            // 当前所处 Phase
  round?: number;              // 对抗轮次（DP2 起；DP1 留空）
  detail?: string;
  timestamp: ISO8601;
}

export interface DocumentProducedPush {
  type: "document_produced";
  agent: AgentName;
  doc_type: "proposal" | "delta-spec" | "delta-design" | "architecture_research" | "confrontation_log";
  doc_id: string;              // flow_id + "/" + doc_type 作为稳定 ID
  summary: string;
  timestamp: ISO8601;
}

export interface CostUpdatePush {
  type: "cost_update";
  total_tokens: number;
  estimated_cost_usd: number;
  round_tokens: number;        // 本轮（自上次 cost_update 以来）增量
  timestamp: ISO8601;
}

export interface FeedbackRequiredPush {
  type: "feedback_required";
  flow_id: string;
  method: "requirement_confirmation" | "design_confirmation" | "task_confirmation";
  message: string;
  output: Record<string, unknown>;  // 待确认的内容（proposal / delta-spec / ...）
  timestamp: ISO8601;
}

export interface ErrorPush {
  type: "error";
  agent?: AgentName;
  error_type: string;
  error_code: ErrorCode;
  message: string;
  severity: Severity;
  recoverable: boolean;
  timestamp: ISO8601;
}

export type PushMessage =
  | AgentStateChangePush | DocumentProducedPush | CostUpdatePush
  | FeedbackRequiredPush | ErrorPush;

// ===== 2. RPC 请求（前端 → 引擎，4 种） =====
export interface StartFlowRequest {
  type: "start_flow";
  message_id: MessageId;      // UUID v4，前端生成
  proposal: string;           // 用户原始需求文本
  pcm: Record<string, unknown>;   // project context map（KG 摘要）
  project_path: string;
}

export interface UserFeedbackRequest {
  type: "user_feedback";
  message_id: MessageId;
  flow_id: string;
  feedback: "approve" | "reject" | "edit";
  outcome?: Record<string, unknown>;  // edit 时携带修改后的 payload
}

export interface ResumeFlowRequest {
  type: "resume_flow";
  message_id: MessageId;
  flow_id: string;
  feedback: "approve" | "reject" | "edit";
}

export interface AbortFlowRequest {
  type: "abort_flow";
  message_id: MessageId;
  flow_id: string;
}

export type RpcRequest =
  | StartFlowRequest | UserFeedbackRequest | ResumeFlowRequest | AbortFlowRequest;

// ===== 3. RPC 响应（引擎 → 前端，4 种；与 RPC 请求共享 message_id） =====
export interface FlowStartedResponse {
  type: "flow_started";
  message_id: MessageId;      // === 对应 start_flow 的 message_id
  flow_id: string;            // 引擎分配
  status: "running";
}

export interface FeedbackAcceptedResponse {
  type: "feedback_accepted";
  message_id: MessageId;      // === 对应 user_feedback 的 message_id
  flow_id: string;
  status: "resuming";
}

export interface FlowResumedResponse {
  type: "flow_resumed";
  message_id: MessageId;      // === 对应 resume_flow 的 message_id
  flow_id: string;
  status: "running";
}

export interface FlowAbortedResponse {
  type: "flow_aborted";
  message_id: MessageId;      // === 对应 abort_flow 的 message_id
  flow_id: string;
  status: "aborted";
}

export type RpcResponse =
  | FlowStartedResponse | FeedbackAcceptedResponse
  | FlowResumedResponse | FlowAbortedResponse;

// ===== 4. 心跳（应用层 JSON，见 §5） =====
export interface PingMessage  { type: "ping";  ts: ISO8601; seq: number; }
export interface PongMessage  { type: "pong";  ts: ISO8601; seq: number; }  // seq === ping.seq

// ===== 顶层联合：WS 上传输的任意帧 =====
export type WireMessage =
  | PushMessage | RpcRequest | RpcResponse | PingMessage | PongMessage;
```

**约束**：
- 所有消息顶层必有 `type` 字段（判别联合的 tag），值即 §7 定义的小写 snake_case 字符串。
- `timestamp` 一律 ISO-8601 UTC（`Z` 后缀），由发送方填；接收方不做时区转换，仅排序/展示。
- `message_id` 仅 RPC 请求/响应携带；Push 与心跳不带（无需关联）。
- 未知 `type` 的帧：**前端丢弃并记 console.warn；服务端 close 4001（协议错误）**。MVP 不做前向兼容。

---

## 四、消息契约（Python Pydantic v2）

提案路径：`backend/sddp/ipc/schemas.py`（DP1 新增模块）。Pydantic v2 模型与 §三 TS 接口**逐字段对齐**，作为服务端入站校验与出站序列化的单一来源。

```python
# backend/sddp/ipc/schemas.py （提案，非实际文件）
from __future__ import annotations
from enum import Enum
from typing import Literal, Union
from datetime import datetime
from pydantic import BaseModel, Field


class AgentName(str, Enum):
    requirement_officer = "requirement_officer"
    orchestrator = "orchestrator"
    architect = "architect"
    executor = "executor"
    code_asset_manager = "code_asset_manager"


class AgentState(str, Enum):
    idle = "idle"; working = "working"; thinking = "thinking"
    waiting_feedback = "waiting-feedback"; error = "error"


class ErrorCode(str, Enum):
    LLM_TIMEOUT = "LLM_TIMEOUT"
    LLM_AUTH_FAIL = "LLM_AUTH_FAIL"
    LLM_RATE_LIMIT = "LLM_RATE_LIMIT"
    PARSE_FAILURE = "PARSE_FAILURE"
    FLOW_STUCK = "FLOW_STUCK"
    KNOWLEDGE_GRAPH_ERROR = "KNOWLEDGE_GRAPH_ERROR"
    SSH_CONNECTION_LOST = "SSH_CONNECTION_LOST"


class Severity(str, Enum):
    critical = "critical"; error = "error"; warning = "warning"


class _Base(BaseModel):
    model_config = {"extra": "forbid"}  # 未知字段拒绝（与 TS 丢弃策略对齐）


# --- 5 Push ---
class AgentStateChangePush(_Base):
    type: Literal["agent_state_change"]
    agent: AgentName
    state: AgentState
    phase: Literal[0, 1, 2]
    round: int | None = None
    detail: str | None = None
    timestamp: datetime


class DocumentProducedPush(_Base):
    type: Literal["document_produced"]
    agent: AgentName
    doc_type: Literal["proposal", "delta-spec", "delta-design",
                      "architecture_research", "confrontation_log"]
    doc_id: str
    summary: str
    timestamp: datetime


class CostUpdatePush(_Base):
    type: Literal["cost_update"]
    total_tokens: int
    estimated_cost_usd: float
    round_tokens: int
    timestamp: datetime


class FeedbackRequiredPush(_Base):
    type: Literal["feedback_required"]
    flow_id: str
    method: Literal["requirement_confirmation", "design_confirmation",
                    "task_confirmation"]
    message: str
    output: dict
    timestamp: datetime


class ErrorPush(_Base):
    type: Literal["error"]
    agent: AgentName | None = None
    error_type: str
    error_code: ErrorCode
    message: str
    severity: Severity
    recoverable: bool
    timestamp: datetime


# --- 4 RPC 请求 ---
class StartFlowRequest(_Base):
    type: Literal["start_flow"]
    message_id: str  # UUID v4
    proposal: str
    pcm: dict
    project_path: str


class UserFeedbackRequest(_Base):
    type: Literal["user_feedback"]
    message_id: str
    flow_id: str
    feedback: Literal["approve", "reject", "edit"]
    outcome: dict | None = None


class ResumeFlowRequest(_Base):
    type: Literal["resume_flow"]
    message_id: str
    flow_id: str
    feedback: Literal["approve", "reject", "edit"]


class AbortFlowRequest(_Base):
    type: Literal["abort_flow"]
    message_id: str
    flow_id: str


# --- 4 RPC 响应 ---
class FlowStartedResponse(_Base):
    type: Literal["flow_started"]
    message_id: str
    flow_id: str
    status: Literal["running"]


class FeedbackAcceptedResponse(_Base):
    type: Literal["feedback_accepted"]
    message_id: str
    flow_id: str
    status: Literal["resuming"]


class FlowResumedResponse(_Base):
    type: Literal["flow_resumed"]
    message_id: str
    flow_id: str
    status: Literal["running"]


class FlowAbortedResponse(_Base):
    type: Literal["flow_aborted"]
    message_id: str
    flow_id: str
    status: Literal["aborted"]


# --- 心跳 ---
class PingMessage(_Base):
    type: Literal["ping"]; ts: datetime; seq: int


class PongMessage(_Base):
    type: Literal["pong"]; ts: datetime; seq: int


# --- 判别联合（Pydantic v2 用 Union + Literal 自动判别） ---
WireMessage = Union[
    AgentStateChangePush, DocumentProducedPush, CostUpdatePush,
    FeedbackRequiredPush, ErrorPush,
    StartFlowRequest, UserFeedbackRequest, ResumeFlowRequest, AbortFlowRequest,
    FlowStartedResponse, FeedbackAcceptedResponse, FlowResumedResponse,
    FlowAbortedResponse,
    PingMessage, PongMessage,
]
```

**双向校验**：
- 服务端入站：`parsed = WireMessage.model_validate_json(raw)`，`ValidationError` → 回 `error` Push（`error_code=PARSE_FAILURE`, `recoverable=true`）并 close 4001。
- 服务端出站：发送前 `msg.model_dump_json()`，保证字段全集与 TS 镜像。
- **契约漂移检测**：DP1 测试套件加 `tests/ipc/test_schema_parity.py`，断言"TS 接口字段名集合 == Pydantic 模型字段名集合"（用正则扫 `messages.ts`，与 `WireMessage.__pydantic_fields__` 对照）。

---

## 五、心跳时序

`analysis/00` §7 line 227 规定：**引擎每 30s 发 ping；前端 10s 内回 pong；连续 3 次未回触发"连接丢失"事件**。

### 5.1 应用层 vs 协议层 ping/pong

- **协议层**（RFC 6455 控制帧 0x9/0xA）：`websockets` 库默认开启（`ping_interval=20s`, `ping_timeout=20s`），但 **Starlette 的 WebSocket 封装不暴露配置**，且 Chromium 客户端无法干预其策略。**不依赖**。
- **应用层**（JSON `{"type":"ping"}`）：两端完全可控、可测、可观测（诊断面板能显示 seq）。**采用此方案**。

> 这是对 §7 "发送 ping"的**明确化**——指应用层 JSON 消息，不是协议控制帧。与 §7 不矛盾，是落地澄清。

### 5.2 时序图

```
Engine (FastAPI)                       Electron (renderer, 原生 WebSocket)
     |                                            |
     |<--------------- WS connect ws://localhost:8765 ----------|
     |                  accept()                  |
     |<-------------------------------------------|
     |                                            |
T=0s |================ ping seq=1 {ts} ==========>|  客户端 onmessage → 即刻回 pong
T=0.2|<============== pong  seq=1 {ts} ===========|  miss_count = 0
     |                                            |
T=30s|================ ping seq=2 {ts} ==========>|  正常回 pong
T=30.|<============== pong  seq=2 ===============>|  miss_count = 0
     |                                            |
     |          *** 用户合上笔记本盖 / 网络中断 *** |
     |                                            X
T=60s|================ ping seq=3 ===============>|  (永远不到)
T=70s| 10s 内无 pong → miss_count = 1              |
T=90s|================ ping seq=4 ===============>|  (不到)
T=100| miss_count = 2                             |
T=120|================ ping seq=5 ===============>|  (不到)
T=130| miss_count = 3 → 触发 on_connection_lost   |
     |                                            |
     | 引擎侧动作:                                  |
     |  1. flow_state.update_flow_status(          |
     |       flow_id, "paused")                    |
     |  2. 中断 WebSocketHumanFeedbackHandler 的   |
     |     asyncio.Future 等待（见 §6）             |
     |  3. flow 协程阻塞在 await feedback_future   |
     |     （不退出，状态在 SQLite）                |
     |                                            |
     |     *** 用户点击 UI "重连"按钮 ***           |
     |<--------------- WS reconnect --------------|
     |                  accept()                  |
     |<-------------------------------------------|
     |                                            |
     | 引擎侧 on_connect 逻辑:                      |
     |  pending = flow_state.list_pending_flows() |
     |  for f in pending:                          |
     |      push feedback_required(f.flow_id, ...) |
     |      让前端知道还有未完成 flow                |
     |                                            |
     |<==== resume_flow {message_id, flow_id} =====|
     |  引擎: 唤醒 feedback_future.set_result(...) |
     |  flow 从 @persist prior_state 续跑          |
     |======= flow_resumed {message_id} =========>|
     |                                            |
```

### 5.3 服务端实现要点

```python
# backend/sddp/ipc/server.py （提案骨架）
import asyncio
PING_INTERVAL = 30.0
PONG_TIMEOUT  = 10.0
MISS_THRESHOLD = 3

async def _heartbeat_loop(ws: WebSocket) -> None:
    seq, miss = 0, 0
    while True:
        await asyncio.sleep(PING_INTERVAL)
        seq += 1
        await ws.send_json({"type": "ping", "ts": _now_iso(), "seq": seq})
        try:
            # 等 pong：用一次性 future，由主接收循环在收到 pong 时 set
            await asyncio.wait_for(_await_pong(seq), timeout=PONG_TIMEOUT)
            miss = 0
        except asyncio.TimeoutError:
            miss += 1
            if miss >= MISS_THRESHOLD:
                await ws.close(code=4002, reason="heartbeat-timeout")
                return
```

### 5.4 客户端实现要点

```typescript
// frontend/src/ipc/heartbeat.ts （提案骨架）
const PING_INTERVAL = 30;  // 仅作客户端 backoff 参考；以服务端到达为准
ws.onmessage = (e) => {
  const msg = JSON.parse(e.data);
  if (msg.type === "ping") {
    ws.send(JSON.stringify({ type: "pong", ts: new Date().toISOString(), seq: msg.seq }));
  }
};
// 浏览器原生 WebSocket 断开会触发 onclose / onerror；
// "连接中断" UI 在 onclose 触发时显示（无需客户端自行计时 3 miss）
```

**关键不对称**：服务端**主动**跑 3-miss 计数器（权威方）；客户端**被动**靠 `ws.onclose`（浏览器在 TCP RST/keepalive 失败时触发）。两者都能感知断线，但服务端判定优先（MVP 不让客户端做 3-miss，避免双计时器漂移）。

---

## 六、DP0 集成点：`WebSocketHumanFeedbackAdapter`

### 6.1 现状

`backend/sddp/cli/feedback_adapter.py:88` 的 `CLIHumanFeedbackAdapter` 是**同步阻塞**：`__call__(kind, payload) -> bool`（line 106）内部走 `input()` 阻塞 stdin。`LinearPhase02Flow` 通过 `human_feedback_handler` 注入点（`phase_0_2_linear.py:72`、line 123/153）调用它。

DP0 的 3 个确认点（`requirement_confirmation` / `design_confirmation` / 预留 `task_confirmation`）因此**仅在 CLI 下可用**。DP1 必须在不改 Flow 逻辑的前提下，把 `human_feedback_handler` 换成 WS 版。

### 6.2 DP0 @persist 复用点

`flow_state.py` 已提供（DP0 已落地）：
- `save_state(flow_id, step, data)` (line 47) — 每步成功后落 SQLite
- `load_state(flow_id, step)` (line 61) — 读单步缓存
- `list_pending_flows()` (line 118) — 列出 `running`/`paused` 的 flow，**重连后用它告诉前端有何未完**

`phase_0_2_linear.py:55` 的 `prior_state` 参数 + `:78-102` 的 `_run_step`：当步骤名出现在 `prior_state` 时**跳过 LLM 调用，直接用缓存输出**。这是断线重连能"续跑"而不是"重跑"的关键。`flow_id` 由 WS server 在 `start_flow` 时分配（`create_flow_meta`，`flow_state.py:91`），并随 `flow_started` Push 回前端。

### 6.3 WebSocketHumanFeedbackAdapter 草案

核心难点：`LinearPhase02Flow.kickoff()` 是**同步**方法（在 worker 线程跑），但 WS 通信是**异步**的。用 `asyncio.run_coroutine_threadsafe` 桥接：

```python
# backend/sddp/ipc/feedback_adapter_ws.py （提案骨架）
import asyncio, uuid
from concurrent.futures import Future
from typing import Any

from ..cli.flow_state import update_flow_status


class WebSocketHumanFeedbackAdapter:
    """替换 CLIHumanFeedbackAdapter；同签名 (kind, payload) -> bool。

    流程: 发 feedback_required Push → 在 asyncio loop 上等 user_feedback/resume_flow
          RPC（用 message_id 关联）→ 收到后唤醒 future → 返回 bool。
    断线: flow 协程阻塞在 future 上，状态已落 SQLite；重连后由 on_connect 重新推
          feedback_required，前端再发 resume_flow 唤醒。
    """

    def __init__(self, ipc_hub: "IpcHub", flow_id: str, loop: asyncio.AbstractEventLoop):
        self._hub = ipc_hub     # 持有 active WS 与广播能力
        self._flow_id = flow_id
        self._loop = loop
        self._pending: dict[str, Future] = {}  # message_id -> concurrent.futures.Future

    def __call__(self, kind: str, payload: dict[str, Any]) -> bool:
        # 在 worker 线程被 Flow 调用（同步入口）
        message_id = str(uuid.uuid4())
        fut: Future = Future()
        self._pending[message_id] = fut

        # 发 feedback_required Push（线程安全地 schedule 到 loop）
        asyncio.run_coroutine_threadsafe(
            self._hub.push({
                "type": "feedback_required",
                "flow_id": self._flow_id,
                "method": kind,
                "message": f"请确认 {kind}",
                "output": payload,
                "timestamp": _now_iso(),
            }),
            self._loop,
        )

        # 阻塞等结果；断线时此 future 不会被 resolve（Flow 协程停在 await 上，
        # process 不退出；SQLite 已存进度）
        try:
            req = fut.result(timeout=None)  # 由 deliver_user_feedback() 唤醒
        finally:
            self._pending.pop(message_id, None)

        update_flow_status(self._flow_id, "running")  # 标记恢复运行
        return req["feedback"] in ("approve", "edit")

    def deliver_user_feedback(self, message_id: str, req: dict[str, Any]) -> None:
        """主 WS 接收循环收到 user_feedback/resume_flow 时调用（loop 线程）。"""
        fut = self._pending.get(message_id)
        if fut is not None:
            fut.set_result(req)
```

**关键性质**：
- `LinearPhase02Flow` **零改动**——仍调 `self.human_feedback_handler(kind, payload)`（`phase_0_2_linear.py:123`），只是注入的 handler 从 CLI 版换成 WS 版。
- 断线时 `fut.result(timeout=None)` **永不返回**，但 `flow_state` 已存 `running`/`paused`，flow 进程不退出。重连后引擎 `on_connect` 重推 `feedback_required`，前端再发 `resume_flow`，**用新的 `message_id` 唤醒**（旧 future 丢弃；这要求 `_pending` 在断线时被清理——见 §6.4）。

### 6.4 断线清理（避免 future 泄漏）

服务端 `on_connection_lost` 时：遍历 `WebSocketHumanFeedbackAdapter._pending`，**不 resolve**（保留 Flow 阻塞），但记录到 `flow_state.update_flow_status(flow_id, "paused")`。重连时 `on_connect` 用 `list_pending_flows()` 重建新的 `_pending` 项并重推 `feedback_required`。这是"future 跨连接不复活，靠 flow_state 续跑"的简化模型，与 §7 "引擎暂停 flow 等待重连"一致。

---

## 七、远程模式（SSH 隧道）

### 7.1 决策：v1 用 `ssh -L`，其他方案 defer

| 方案 | v1 评估 | 结论 |
|------|---------|------|
| **`ssh -L 8765:localhost:8765`** | 0 额外依赖；所有 OS 自带 `ssh` 客户端（Win10+ OpenSSH、macOS、Linux）；前端代码完全无感（仍连 `localhost:8765`）；故障模式清晰（见 7.3） | **采用** |
| Tailscale Funnel | 需账号、需安装客户端、需暴露到公网（Funnel 是公网入口）；与"桌宠本地优先"定位冲突 | defer 到 D4+ |
| cloudflared | 同上，且增加 Cloudflare 供应商依赖；隧道健康状态难排障 | defer |
| 现代 SOCKS5 + `ssh -D` | 前端要懂 SOCKS，Electron 原生 WS 不支持 SOCKS 代理（需 HTTP_PROXY hack，不稳） | 不采用 |
| WireGuard | OS 级网络配置，超出桌宠 MVP 范围 | defer |

**判定**：Tailscale/cloudflared 在 v1 **没有明确收益**（增加依赖、增加公网暴露面、增加排障复杂度），而 `ssh -L` 已满足 §7 line 238 "前端仍连 localhost:8765"且零依赖。**按 §任务说明"无明显优势则 defer"准则 defer**。

### 7.2 具体命令

```bash
# 1. 远程主机上启动引擎（监听 localhost:8765，绝不绑 0.0.0.0）
sddp serve --host 127.0.0.1 --port 8765

# 2. 本地建立隧道（本地 8765 → 远程 localhost:8765）
ssh -N -L 8765:localhost:8765 user@remote-host

# 3. Electron 启动时 WebSocket URL 仍为 ws://localhost:8765
#    （配置项 "remote_mode" 仅切换提示文案与隐私同意页，不改 URL）
```

`-N` = 不开远程 shell；`-L` = 本地端口转发；隧道进程独立于引擎进程，便于用户独立 kill/重启。

### 7.3 故障模式

| 现象 | 根因 | 检测/处理 |
|------|------|-----------|
| Electron `ws.onerror` 即时触发 | ssh 进程退出 / 远程主机宕机 | 浏览器原生 WS 在 TCP RST 时触发 onclose → 显示"连接中断" + 重连按钮（D1-16） |
| 隧道活但引擎崩 | 远程 `sddp serve` 退出 | WS 握手失败（连接拒绝）→ UI 显示"引擎未启动"，与"网络中断"区分 |
| 隧道 idle 被中间设备杀 | NAT 超时（典型 30-60 min） | 应用层心跳 30s 持续打流量；`ssh -o ServerAliveInterval=25` 双保险 |
| 隧道与本地服务抢端口 | 本地 8765 已被占 | `ssh -L` 启动即报 `bind: Address already in use` → 用户改端口 |

`SSH_CONNECTION_LOST` 已在 `ErrorCode` 枚举（§三、§四）预留——但**注意**：SSH 隧道断 ≠ Python 进程能感知。Python 侧只看到 WS 连接 close（`WebSocketDisconnect`），与本地模式断线无法区分。`SSH_CONNECTION_LOST` 仅在引擎**主动检测到远程 SSH 调用失败**（如 KG scan via SSH）时使用，**不**用于 IPC 层。本条作为已澄清事项记入 §九。

---

## 八、已接受风险

1. **MVP 无 RPC 重试/幂等** — DP1 用 simple ack（4 RPC-response）。若 `start_flow` 的 RPC 响应丢失，客户端 N 秒超时后由用户手动重试；服务端用 `message_id` 去重（同一 `message_id` 二次到达时返回已存在的 `flow_id` 而非新建 flow）。**不做**更复杂的 exactly-once。
2. **消息顺序保证仅限单 WS 连接内** — 单连接上 WS 协议保证帧顺序；但**跨重连不保序**（旧连接上的 trailing Push 可能在新连接的 RPC 之后到达）。MVP 客户端按 `timestamp` 字段排序展示；不接受乱序导致的状态机错误（用 `flow_id` + `phase` 做幂等过滤）。
3. **不压缩、不分片** — `proposal` + `pcm` 单帧可能 >16KB；浏览器原生 WS 无帧大小上限，但若超过 ~256KB（含 KG 摘要）应在服务端裁剪。MVP 上限 1MB，超过返回 `PARSE_FAILURE`。
4. **无消息级加密** — 本地模式走 `localhost`（不出内核）；远程模式走 SSH 隧道（加密由 SSH 提供）。WS 层不做 TLS（`wss://`），避免证书管理复杂度。若未来移除 SSH 隧道则必须加 `wss://`。
5. **单连接单 flow（MVP）** — `IpcHub` 同时只允许一个 active WS；D2 的并发 flow（D2-9）需要扩展为多连接/多 flow 路由，**当前契约支持但实现不就绪**。
6. **客户端不做 3-miss 计数** — 完全依赖服务端心跳权威 + 浏览器 `onclose`。若服务端心跳 bug 导致 ping 不发，客户端可能挂死在"看似已连"状态——通过诊断面板显示 `last_ping_received_at`（D1-15 监控指标）让用户自检。

---

## 九、对 D1-DoD 的影响

| DoD 项 | 本文件决策 | 是否需调整 DoD 文本 |
|--------|-----------|-------------------|
| **D1-4** FastAPI WebSocket server 对接 Electron | §二锁定 FastAPI（待 patch）+ starlette/uvicorn/websockets 已锁；§三/四定义契约；§六定义集成 | 否；DoD 文本"双向消息可发收；连接失败有错误提示"已覆盖 |
| **D1-5** 5 种 Push 消息渲染 | §三 5 个 Push 接口为硬契约；`extra: "forbid"` 保证字段不漂移 | 否；建议验证方式追加 `tests/ipc/test_schema_parity.py` |
| **D1-6** 4 种 RPC 请求 | §三 4 个 RPC 请求 + §六 `message_id` 关联 | 否 |
| **D1-7** 心跳 30s/10s/3-miss | §五明确为**应用层 JSON ping/pong**（非协议控制帧）；服务端权威计时，客户端被动 onclose | **建议补充**：DoD 文本"30s ping"后加"（应用层 JSON `{"type":"ping"}`）"，避免实现方误用协议层控制帧 |
| **D1-16** SSH 隧道 | §七锁定 `ssh -L`；defer Tailscale/cloudflared | 否；DoD 文本"`ssh -L 8765:localhost:8765` 转发"已精确 |

**唯一建议调整**：D1-7 的 DoD 文本应在"30s ping"后明确"应用层 JSON 帧"，否则实现方可能尝试配置 Starlette/websockets 的协议级 ping（不可达，见 §5.1），延误工期。此调整不改变 DoD 的判定阈值，仅澄清实现路径。

**新增建议 DoD（非强制）**：D1 增加 `D1-17 消息契约前后端字段对齐`：`pytest tests/ipc/test_schema_parity.py` 退出码 0（TS 接口字段集 == Pydantic 模型字段集）。防止前后端独立开发导致的字段漂移。是否纳入由 OpenSpec DP1 change 决定。

---

> **后续动作**（不在本文件范围）：
> 1. 创建 OpenSpec change `add-websocket-ipc-layer`（DP1），把 §二/三/四/六/七 落为 delta spec
> 2. DP1 第 0 步跑 §2.3 验证脚本，回填 `fastapi==<exact-patch>` 到本文件 §2.2 与 `pyproject.toml`
> 3. §6.3 的 `WebSocketHumanFeedbackAdapter` 实现并接入 `LinearPhase02Flow` 的依赖注入点（不改 Flow 代码）
