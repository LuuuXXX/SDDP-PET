# Observability

## Purpose

Dev-Phase 1 的可观测性能力。`observability` 采集 4 项监控指标到 `~/.sddp-pet/metrics.json`（JSON Lines 格式，append-only）：流程执行时间（`flow_time_seconds`）、单角色延迟（`agent_latency_seconds`）、token 消耗率（`token_consumption_rate`）、错误率（`error_rate`，滑动窗口 100 个）；window2 诊断面板实时展示这 4 项指标（当前值经 `cost_update` Push 每 5 秒刷新，历史值启动时从 metrics.json 读取最近 100 条计算平均 / 中位数 / P95），错误率卡片在 `error_rate > 0.1` 时变红。集成点复用 DP0 `CostMeter` 已采集的 `wall_clock_minutes_excluding_human_wait` 与 `total_tokens`，不重新计时。对应 `dod.md` D1-14、D1-15。权威来源：`analysis/00` §六。

## Requirements

### Requirement: 引擎 MUST 采集 4 项监控指标到 `metrics.json`

依据 `dod.md` D1-14，引擎 MUST 在每个 flow 完成时（含成功 / 失败 / 中止）将以下 4 项指标写入 `~/.sddp-pet/metrics.json`（append-only，每行一个 JSON 对象，JSON Lines 格式）：

| 指标 | 字段名 | 单位 / 类型 | 计算来源 |
|------|--------|-----------|----------|
| 流程执行时间 | `flow_time_seconds` | 秒（float） | flow.kickoff 入口到出口的 wall clock（不含 human_feedback 等待） |
| 单角色延迟 | `agent_latency_seconds` | 秒（float，每角色一条） | 单个 `SafeAgent.kickoff` 入口到出口 |
| token 消耗率 | `token_consumption_rate` | tokens/秒（float） | `total_tokens / flow_time_seconds` |
| 错误率 | `error_rate` | 0.0–1.0（float） | 失败 flow 数 / 总 flow 数（滑动窗口 100 个） |

每条记录 MUST 含 `flow_id`、`timestamp`、`status`(completed\|failed\|aborted) 字段。`token_consumption_rate` 与 `error_rate` 由 `metrics.json` 派生计算时 MUST 与原始 `flow_time_seconds` / `total_tokens` / `status` 一致（可重算）。

**集成点**：复用 DP0 `CostMeter`（`backend/sddp/engine/cost_meter.py`）已采集的 `wall_clock_minutes_excluding_human_wait` 与 `total_tokens`，不重新计时。

#### Scenario: 跑一个流程后 metrics.json 含 4 项指标
- **WHENT** 跑一个完整 SDDP 流程（任意 proposal）
- **THEN** `~/.sddp-pet/metrics.json` MUST 追加一条新行；该行 MUST 含 `flow_time_seconds` / `agent_latency_seconds`(每角色一条) / `token_consumption_rate` / `error_rate` 四个字段的非空数值；MUST 含 `flow_id` / `timestamp` / `status`

#### Scenario: 失败流程也写入 metrics
- **WHENT** 跑一个流程并在中途触发 `LLM_TIMEOUT` 错误
- **THEN** `metrics.json` MUST 追加一条新行，`status`="failed"；`flow_time_seconds` MUST 反映失败前的实际耗时；`error_rate` 字段 MUST 反映该次失败（滑动窗口更新）

### Requirement: 诊断面板 MUST 实时展示 4 项指标

依据 `dod.md` D1-15，window2 诊断面板 MUST 实时展示上述 4 项指标。展示规则：
- 实时值（当前 flow 进行中）：通过 `cost_update` Push 消息（DP0 既有）每 5 秒更新一次
- 历史值（已完成 flow 的统计）：启动时从 `~/.sddp-pet/metrics.json` 读取最近 100 条，计算平均 / 中位数 / P95
- UI 元素：每项指标一个独立卡片，含当前值 + 历史平均值；错误率卡片 MUST 在 `error_rate > 0.1` 时变红

#### Scenario: 诊断面板显示 4 项指标
- **WHENT** 启动应用并跑一个流程
- **THEN** window2 诊断面板 MUST 显示 4 个独立指标卡片；每张卡片 MUST 含当前值 + 历史平均值；MUST 实时刷新（≤ 5 秒延迟）

#### Scenario: 错误率高时视觉告警
- **WHENT** 滑动窗口 100 个 flow 中失败数 > 10（`error_rate > 0.1`）
- **THEN** 诊断面板的错误率卡片 MUST 变红；MUST 不影响其他指标卡片的展示
