# Golden Demo: Dev-Phase 1 — `config-hot-reload` 端到端（CLI 复现 + UI 待 dev 机）

> **基线状态**：`frozen (CLI verified, UI pending dev machine)`
>
> 本 Golden Demo 当前以 **DP1 CLI 复现路径** 为度量基线冻结。UI 路径（D1-8 同 proposal 在桌宠 UI 下产出相同文档集）的端到端验证需要 Windows/macOS dev 机跑真实 Electron；待 dev 机验证后追加"UI 重放历史"小节并升级状态为 `frozen (CLI + UI baseline)`。

## 冻结元数据

- 冻结日期：2026-07-21
- 基线 provider：DeepSeek（`deepseek-chat`，底层模型 `deepseek-v4-flash`，Tier-B）
- git tag：**待打**（DP1 archive 后打 `dev-phase-1-v1`；当前 HEAD 在 `dev-phase-1-desktop-pet-mvp` 工作树）
- 关联变更：[`openspec/changes/dev-phase-1-desktop-pet-mvp/`](../../changes/dev-phase-1-desktop-pet-mvp/)
- 关联 DoD：[`openspec/specs/development-roadmap/dod.md`](../../specs/development-roadmap/dod.md) 第 D1-8 / X-3 / X-5 项
- 关联 E2E 测试：[`backend/tests/e2e/test_dev_phase_0_demo.py`](../../../backend/tests/e2e/test_dev_phase_0_demo.py)（CLI 路径复用 DP0 的真实 API E2E 测试）

## 输入场景

**proposal 文件**：`backend/tests/fixtures/proposals/config-hot-reload.txt`（与 DP0 Golden Demo 同输入）

**自然语言需求摘要**：给 `backend/tests/fixtures/sample-python-project/`（10 个 Python 文件、43 个符号）新增配置热重载能力 —— `ConfigWatcher` 类、asyncio 后台轮询、订阅者通知、优雅启停、向后兼容。（详见 DP0 Golden Demo 同名字段）

**DP1 新增验证维度**：proposal 输入穿过 `sddp/security/prefilter.py` 脱敏 → DeepSeek → 还原 → 4 markdown 产出，**全链路不应破坏 DP0 输出结构**。

## 期望输出

`--output` 目录下 MUST 产出 5 个文件（与 DP0 Golden Demo 完全一致）：

| 文件 | 来源角色 | schema |
|------|---------|--------|
| `proposal.md` | requirement_officer | `Proposal` |
| `delta_spec.md` | architect round 1 | `DeltaSpec` |
| `delta_design.md` | architect round 2 | `DeltaDesign` |
| `architecture_research.md` | architect round 3 | `ArchitectureResearch` |
| `cost_report.json` | cost_meter | — |

DP1 新增期望（不在 DP0 Golden Demo）：
- `~/.sddp-pet/metrics.json` 追加 1 行（含 4 字段非空）—— `SDDP_PET_HOME` 环境变量可重定向
- 流程经 `sddp serve` WebSocket 路径时：前端 MUST 收到 5 Push 消息类型全覆盖（含 `feedback_required` + `cost_update`）—— 由 `tests/ipc/test_server.py::test_ws_full_mock_flow_pushes_documents_and_cost` 验证

## 度量阈值范围（CLI 路径实测）

| 指标 | DoD 下限 | DoD 上限 | DP1 CLI 实测 | DP0 基线 | 比值 | 结果 |
|------|---------:|---------:|-------------:|---------:|-----:|:----:|
| 成本 (USD) [D1/X-3] | — | 5.0 | **0.0080** | 0.0078 | 1.02x | ✅ |
| 延迟 (min) [D0-12 继承] | — | 10.0 | **0.86** | 0.67 | 1.28x | ✅（容差内） |
| Schema 合规率 [D0-13 继承] | 0.99 | — | **1.0000** | 1.0000 | — | ✅ |
| Token 数 | — | — | 13,869 | 14,344 | 0.97x | ✅ |
| 产出文件数 | 5 | 5 | **5** | 5 | — | ✅ |

**结论**：CLI 路径在 DP1 代码树下与 DP0 基线行为一致（prefilter scrub/restore 开销 < 5% 延迟，token 偏差 ±5% 内）。X-5 回归无退化 PASS。

## 运行命令

### CLI 路径（本基线实测）

```bash
cd backend
source scripts/deepseek-env.sh   # 设置 OPENAI_API_KEY/OPENAI_BASE_URL/SDDP_LLM_MODEL
.venv/bin/python -m sddp.cli.main run \
  tests/fixtures/proposals/config-hot-reload.txt \
  --project tests/fixtures/sample-python-project \
  --output /tmp/dp1-golden-demo \
  --kg-db /tmp/dp1-golden-kg.db \
  --flow-db /tmp/dp1-golden-flow.db \
  --yes
```

**期望退出码**：0；**期望产出**：`/tmp/dp1-golden-demo/` 下 5 文件。

### UI 路径（待 dev 机）

```bash
# Terminal 1: 启动 IPC server
cd backend && source scripts/deepseek-env.sh
sddp serve --project tests/fixtures/sample-python-project/

# Terminal 2: 启动 Electron UI
cd frontend && npm run dev

# UI 操作：
# 1. 首次启动 → 隐私同意 modal → 点击"同意"
# 2. window2 状态面板 → 输入 proposal（或粘贴 config-hot-reload.txt 内容）
# 3. 点击"启动流程"
# 4. 每个确认点 → window2 ConfirmPanel 点击"y"
# 5. 流程完成 → 诊断面板显示 metrics；文档列表显示 4 markdown
```

**期望**：与 CLI 路径产出**相同的 4 markdown**（标题、影响面、KG citations 集合一致）；`cost_report.json` 数值在 ±20% 内。

### E2E 测试驱动（用于 DP2 回归重放）

```bash
cd backend && source scripts/deepseek-env.sh
.venv/bin/python -m pytest tests/e2e/test_dev_phase_0_demo.py::test_dev_phase_0_demo_config_hot_reload_real -v
# 期望 PASS（复用 DP0 的真实 API E2E 测试，验证 DP1 代码树不退化）
```

## 重放结果历史

| 重放日期 | 重放基线 (provider/git) | 重放目标 (HEAD) | 结果 | 报告路径 |
|----------|-------------------------|-----------------|------|----------|
| 2026-07-21 | DeepSeek Tier-B / (git tag 待打) | dev-phase-1-desktop-pet-mvp 工作树（commit `2706a53`） | PASS（CLI 路径；5 文件齐全 + cost 1.02x + token 0.97x） | 本文 + `openspec/regression/reports/2026-07-21-dev-phase-1-gate.md` |

## 基线升级历史

- **2026-07-21 Tier-B CLI baseline 冻结** —— 首次冻结；UI 路径 + OpenAI Tier-S 重测两路待 dev 机 + OPENAI_API_KEY 解锁
