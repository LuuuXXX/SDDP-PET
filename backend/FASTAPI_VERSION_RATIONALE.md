# FastAPI 版本选定理由（Dev-Phase 1 day-0）

> 日期：2026-07-21
> 状态：P0 已选定
> 关联：`analysis/08-websocket-ipc-contract.md` §2.3、`backend/requirements.lock.txt`

## 一、选定结果

**`fastapi==0.139.2`**（当前 PyPI 最新稳定版，2026-07-21）。

## 二、选定准则（依据 `analysis/03` 准则延展）

| 准则 | 来源 | 实测 |
|------|------|------|
| 不 bump DP0 既有 deps | `analysis/08` §2.3 | ✅ `pip install --dry-run fastapi==0.139.2` 报告 "Would install fastapi-0.139.2"，其余 deps 全部 "already satisfied" |
| starlette pin 兼容 | PyPI metadata | ✅ FastAPI 0.134.0+ 全部要求 `starlette>=0.46.0`（无上限），DP0 lockfile 的 `starlette==1.3.1` 满足 |
| Python 3.11/3.12 兼容 | FastAPI release notes | ✅ FastAPI 0.139.x 显式支持 Python 3.9–3.13 |
| WebSocket 支持稳定 | FastAPI 文档 + Starlette changelog | ✅ Starlette 1.3.1 + uvicorn 0.51.0 + websockets 16.1.1 是当前稳定组合，`fastapi.testclient.TestClient` WS 握手通过 |

## 三、与 DP0 lockfile 的差异（最小化）

```diff
+ fastapi==0.139.2
```

其他 165 行 deps 完全不变。

## 四、备选方案与放弃理由

| 候选 | 放弃理由 |
|------|---------|
| `fastapi==0.116.x`（analysis/08 撰写时参考的版本） | 与 0.139.2 行为等价，但后者更新且零额外风险 |
| `fastapi[standard]==0.139.2` | `standard` extra 会主动拉 `uvicorn[standard]` / `python-multipart` / `fastapi-cloud-cli`，其中 `fastapi-cloud-cli` 是新依赖；DP1 不需要 cloud CLI，直接 pin 核心包 |
| `starlette` 直接（不经 FastAPI） | 失去 OpenAPI 文档 + auto-validation + Pydantic 集成；DP1 IPC server 用 FastAPI decorator 更简洁 |

## 五、未来重新选定的触发条件

- DP2 archive 时若 FastAPI 主版本号变化（0.x → 1.x）→ 重跑 `analysis/08` §2.3 验证脚本
- Starlette bump 2.0+ → 重新评估（Starlette 1.x → 2.x 可能有 breaking change）
- 任何对 websockets/uvicorn 的非兼容升级 → 阻断 archive（DP1-NG-G）
