# 回归门控报告：Dev-Phase 0（`dev-phase-0-engine-core`）

- **报告日期**：2026-07-21
- **关联变更**：[`openspec/changes/dev-phase-0-engine-core/`](../../changes/dev-phase-0-engine-core/)
- **关联 DoD**：[`openspec/specs/development-roadmap/dod.md`](../../specs/development-roadmap/dod.md) 第 X-5 项（回归无退化）
- **关联规格**：[`openspec/specs/regression-strategy/spec.md`](../../specs/regression-strategy/spec.md)

## 一、Golden Demo 重放

依据 `regression-strategy/spec.md` 的回归门控规则：Dev-Phase N 验收前 MUST 重放所有状态为 `frozen` 的 Golden Demo（N=1 时重放 DP0；N=2 时重放 DP0+DP1；以此类推）。

**Dev-Phase 0 是首个 Dev-Phase（N=0）**：

- 重放集合大小：**0**（`openspec/regression/golden-demos/` 下除 `README.md` 外无任何 `dev-phase-*.md` 文件）
- 重放结果：**N/A — 无历史 Golden Demo 可重放**（符合 `golden-demos-index.md` 第二节的 Dev-Phase 0 槽位说明："本阶段为 Dev-Phase 0，无历史 Golden Demo 需重放（前置阶段数为 0）"）

**本阶段 archive 时**：本阶段冻结的 Golden Demo（任务 7.5，`openspec/regression/golden-demos/dev-phase-0.md` + git tag `dev-phase-0-v1`）将成为 **Dev-Phase 1** 验收时的回归基线。

## 二、契约测试运行

依据 `contracts-index.md` 第三节"契约 → 测试代码映射"，本阶段引入的 17 条 Dev-Phase 0 契约（KG 7 + SafeAgent 3 + Adaptation Layer 2 + JSON Schema 3 + 渲染管道 1 + CLI 1）的测试代码落在 `backend/tests/<module>/`。

**实际执行**（任务 9.3）：

```bash
pytest backend/tests/ -m "not e2e"
```

- 结果：**110 passed / 4 deselected**（4 个为需 `OPENAI_API_KEY` 的真实 API E2E，按设计决策 8 不在常规回归运行）
- 退出码：**0**
- 契约覆盖率：17/17 条 Dev-Phase 0 契约均有对应测试代码路径（见 `contracts-index.md` 第三节表）

## 三、结论

| 门控项 | 结果 | 备注 |
|--------|------|------|
| 历史 Golden Demo 重放 | N/A | Dev-Phase 0 是首个阶段，无历史 demo |
| 契约测试运行 | PASS | 110/114 测试通过（4 个 e2e-real 按设计跳过） |
| 已接受风险状态 | 不变 | `accepted-risks.md` 4 项维持；AR-2/AR-3 在本阶段首次实际暴露但不阻断 |

**门控判定**：Dev-Phase 0 的回归门控通过（无历史回归失败；契约测试全部 PASS）。剩余阻塞项为 D0-9/D0-11/D0-12/D0-13/D0-14 的真实 API 运行（任务 7.3/7.4），需 `OPENAI_API_KEY` 才能解锁，不属回归门控范畴。

## 二·补、DeepSeek Tier-B provisional 重测（2026-07-21 当日追加）

任务 7.3/7.4 解锁：使用 DeepSeek `deepseek-chat`（OpenAI-compatible via `OPENAI_BASE_URL`）作为 Tier-B plumbing 基线，跑通 3 个 fixture proposal。

| 项 | 结果 | 证据 |
|----|------|------|
| 契约测试（含 DeepSeek env） | **110 passed / 4 deselected** | `pytest tests/ -m "not e2e"` |
| E2E 真实 API（含 D0-9 + D0-14） | **7 passed** | `pytest tests/e2e/test_dev_phase_0_demo.py`（耗时 183s） |
| D0-11 成本 ≤ $5 | **PASS**（最差 $0.0111） | 3 proposal `cost_report.json` |
| D0-12 延迟 ≤ 10 min | **PASS**（最差 0.90 min） | 同上 |
| D0-13 合规率 ≥ 99% | **PASS**（18/18 = 100%） | 同上 |
| D0-14 三 proposal 不崩溃 | **PASS** | `test_d0_14_three_proposals_no_crash_real` |
| D0-10 @persist 中断恢复 | **PASS** | `tests/cli/test_resume.py` 6 测试 + 真实 DeepSeek resume 端到端（2.0s / 0 token） |
| Golden Demo 冻结 | **frozen (Tier-B provisional)** | `openspec/regression/golden-demos/dev-phase-0.md` |

**Tier-B caveat**：`analysis/04-llm-provider-strategy.md` MVP 决策 8 仍要求 **OpenAI Tier-S** 作为官方 Go 基线（D0-13 在复杂 schema / 对抗场景下 Tier-B 可能掉到 90-95%）。本次结果作为"plumbing 验证 + Tier-B provisional baseline"，OpenAI Tier-S 重测待 `OPENAI_API_KEY` 解锁。**门控判定维持 PASS**（Tier-B 已超过所有量化阈值；Tier-S 重测是基线升级，不阻断当前回归门控）。

## 四、为 Dev-Phase 1 留下的基线

Dev-Phase 1 验收时 MUST：

1. 重放本阶段冻结的 `openspec/regression/golden-demos/dev-phase-0.md`（任务 7.5 完成后）
2. 重跑本阶段契约测试集（17 条，对应 `backend/tests/{kg,safe_agent,adaptation,engine,cli}/`）
3. 任一失败 → 阻断 Dev-Phase 1 的 Go 判定 → 按失败定位的责任模块回退