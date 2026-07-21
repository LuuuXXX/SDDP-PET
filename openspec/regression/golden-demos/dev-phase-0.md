# Golden Demo: Dev-Phase 0 — `config-hot-reload` 端到端

> **基线状态**：`frozen (Tier-B provisional)`
>
> 本 Golden Demo 当前以 **DeepSeek Tier-B**（`deepseek-chat` via OpenAI-compatible `OPENAI_BASE_URL`）为度量基线冻结。`analysis/04-llm-provider-strategy.md` MVP 决策 8 仍要求 **OpenAI Tier-S** 作为 Dev-Phase 0 官方 Go 基线；当 `OPENAI_API_KEY` 解锁后，MUST 用 Tier-S 重测本 demo 并把状态升级为 `frozen (Tier-S baseline)`，本文件追加"基线升级历史"小节保留 Tier-B 记录。

## 冻结元数据

- 冻结日期：2026-07-21
- 基线 provider：DeepSeek（`deepseek-chat`，底层模型 `deepseek-v4-flash`，Tier-B）
- git tag：**待定**（项目根未 `git init`，`dev-phase-0-v1` tag 推迟到 git 仓库初始化时创建）
- 关联变更：[`openspec/changes/dev-phase-0-engine-core/`](../../changes/dev-phase-0-engine-core/)
- 关联 DoD：[`openspec/specs/development-roadmap/dod.md`](../../specs/development-roadmap/dod.md) 第 D0-9 / D0-11 / D0-12 / D0-13 / D0-14 项
- 关联 E2E 测试：[`backend/tests/e2e/test_dev_phase_0_demo.py::test_dev_phase_0_demo_config_hot_reload_real`](../../../backend/tests/e2e/test_dev_phase_0_demo.py)

## 输入场景

**proposal 文件**：`backend/tests/fixtures/proposals/config-hot-reload.txt`

**自然语言需求摘要**：给 `backend/tests/fixtures/sample-python-project/`（10 个 Python 文件、43 个符号）新增配置热重载能力 —— 在 `config.py` 中新增 `ConfigWatcher` 类，监听 `config.json` 的 mtime 变化（asyncio 后台任务，1 秒轮询），变更时重新加载并通知订阅者；`logger.py` 订阅以动态调整日志级别；`main.py` 启停与信号处理；保持 `load_config(path)` 签名向后兼容。

**约束**：仅标准库（asyncio/os.path/signal）；不引入 watchdog；ConfigWatcher 是可选能力；异常时记 warning 不崩溃。

## 期望输出

`--output` 目录下 MUST 产出以下 5 个文件（顺序无关）：

| 文件 | 来源角色 | schema | 关键内容 |
|------|---------|--------|---------|
| `proposal.md` | requirement_officer | `Proposal` | 需求解析 + 变更范围 + 约束 + PCM + 流程建议 |
| `delta_spec.md` | architect (round 1) | `DeltaSpec` | 变更范围 + 接口契约 + 影响面分析（含 KG 置信度）+ 约束 |
| `delta_design.md` | architect (round 2) | `DeltaDesign` | 架构决策 + 数据流 + 关键算法 + 模块划分 + 异常处理 + 编码参照 |
| `architecture_research.md` | architect (round 3) | `ArchitectureResearch` | 方法论 + 现状基线 + 依赖链 + 约束提取 + **KG citations（每条含 confidence）** |
| `cost_report.json` | cost_meter | — | 见下方"度量阈值范围" |

**额外**：`--kg-db` 指向的 SQLite 中 `scan_meta.scan_version` MUST 较运行前递增。

**不要求**：4 markdown 的字面内容逐字相同；只要求字段齐全 + schema 合规。

## 度量阈值范围（实测）

> 实测环境：DeepSeek Tier-B（`deepseek-chat`），10 文件 sample project，单 proposal 端到端

| 指标 | DoD 下限 | DoD 上限 | config-hot-reload 实测 | 来源 |
|------|---------:|---------:|----------------------:|------|
| 单流程成本 (USD) [D0-11] | — | 5.0 | **0.0078** | `dod.md` D0-11 |
| 端到端延迟 (min, 不含人工等待) [D0-12] | — | 10.0 | **0.67** | `dod.md` D0-12 |
| Structured Outputs 合规率 [D0-13] | 0.99 | — | **1.0000** (18/18 调用) | `dod.md` D0-13 |
| 5 角色 kickoff 全部完成 [D0-7] | — | — | ✅ 5/5 | `dod.md` D0-7 |
| scan_version 递增 [D0-4] | ≥1 | — | ✅ +1 | `dod.md` D0-4 |

**D0-14 横向对照**（3 个 fixture proposal 均通过同一基线）：

| proposal | cost_usd | wall_min | compliance | tokens | calls | 退出码 |
|----------|---------:|---------:|-----------:|-------:|------:|:------:|
| config-hot-reload | $0.0078 | 0.67 | 100.0% | 14,344 | 6 | 0 |
| add-logging       | $0.0095 | 0.80 | 100.0% | 15,713 | 6 | 0 |
| refactor-utils    | $0.0111 | 0.90 | 100.0% | 18,372 | 6 | 0 |

**Tier-B vs Tier-S 差异说明**：
- 成本/延迟：DeepSeek Tier-B 实测约比 OpenAI gpt-4o-mini 估价低 5-10x（更便宜的 input/output 单价）
- 合规率：本 3 proposal 18 次调用 100% 合规（远超 Tier-B 预期 90-95%）。**样本量不足以外推**：复杂 schema 或对抗场景下 Tier-B 可能掉到 90-95%，触发 pydantic 重试，从而抬高成本/延迟。OpenAI Tier-S 在生成期保证 100% schema 合规，是 D0-13 的官方基线。

## 运行命令

### 环境准备（DeepSeek Tier-B 基线）

```bash
cd backend
source scripts/deepseek-env.sh   # 设置 OPENAI_API_KEY/OPENAI_BASE_URL/SDDP_LLM_MODEL
.venv/bin/python -c "from openai import OpenAI; OpenAI().chat.completions.create(model='deepseek-chat', messages=[{'role':'user','content':'JSON {\"ping\":true}'}], response_format={'type':'json_object'}, max_tokens=20)"  # 烟雾测试
```

### 端到端运行（默认 config-hot-reload）

```bash
cd backend
source scripts/deepseek-env.sh
.venv/bin/python -m sddp.cli.main run \
  tests/fixtures/proposals/config-hot-reload.txt \
  --project tests/fixtures/sample-python-project \
  --output out/config-hot-reload \
  --kg-db /tmp/sddp-golden-kg.db \
  --flow-db /tmp/sddp-golden-flow.db \
  --yes
```

**期望退出码**：0；**期望产出**：`out/config-hot-reload/` 下 5 个文件（见"期望输出"）。

### E2E 测试驱动（推荐用于回归）

```bash
cd backend
source scripts/deepseek-env.sh
.venv/bin/python -m pytest tests/e2e/test_dev_phase_0_demo.py -v
# 期望：7 passed（含 D0-9 真实 API + D0-14 三 proposal 参数化）
```

## 重放结果历史

| 重放日期 | 重放基线 (provider/tag) | 重放目标 (HEAD) | 结果 | 报告路径 |
|----------|-------------------------|-----------------|------|----------|
| 2026-07-21 | DeepSeek Tier-B / (git tag 待定) | dev-phase-0-engine-core 工作树 | PASS（7/7 E2E） | 本文 + `openspec/regression/reports/2026-07-21-dev-phase-0-gate.md` |

## 基线升级历史

- **2026-07-21 Tier-B provisional baseline 冻结** —— 首次冻结；待 OpenAI Tier-S 重测后追加 Tier-S 行
