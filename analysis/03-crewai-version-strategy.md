# G2: CrewAI 版本锁定策略

> 日期: 2026-07-20
> 状态: P0 缺口补齐
> 关联: 01-final-review.md G2; crewai-technical-research.md 第1节

---

## 一、问题陈述

此前分析 7 次提到"锁定 CrewAI 版本"，但从未给出具体版本号，也未定义"选哪个版本"的判定方法。Dev-Phase 0 模块清单中"锁定版本"是无法执行的空任务。本文件给出选型准则与可执行的锁定流程。

### 锁定的硬性前提（来自 crewai-technical-research.md 的证据）

| Issue/PR | 状态 | 对 SDDP 的影响 | 选型要求 |
|----------|------|---------------|---------|
| #5972 `or_()` 循环只触发一次 | ✅ 已修复(#5994/#5974) | 直接决定 Phase 1/3 循环能否工作 | **必须**选包含此 fix 的版本 |
| #6347/#6065 `human_input=True` 崩溃 | ✅ 已修复(#6372) | 影响 8 个用户确认点 | **必须**包含 #6372 |
| #6380 异步 LLM 失败静默冻结 | ❌ 未修复(#6407 开放) | async agent 卡死 | **不可依赖官方修复**，强制 SafeAgent wrapper |
| #6370 router hops 无上限 | 🟡 PR 开放 | 死循环风险 | 自实现 max_rounds，不依赖该 PR |
| #6219 LoopHalter | 🟡 开放 | 无原生循环检测 | 自实现收敛检测 |
| #6097 condition 评估改 stateless | ⚠️ breaking potential | 可能破坏现有 Flow | **必须避开**包含此 breaking change 的版本 |
| #6405 拒绝自监听 | ✅ 已合并 | SDDP 用 `or_()` 不受影响 | 兼容 |

---

## 二、诚实声明：本文件不直接给出"魔法版本号"

在分析阶段直接断言 `crewai==1.15.X` 的具体 patch 号是**不负责任的**，因为：
1. crewai 在 PyPI 上的具体发布节奏与 patch 内容，需在实现时用 `pip index versions crewai` 实查
2. 各 fix PR 合入的 release 标签需对照 GitHub release notes 确认
3. CrewAI 1.15.x 的子版本演进中可能有多个 patch，须挑具体那个

因此本文件给出**选型准则 + 可执行的锁定脚本**，而非一个可能已过时的数字。

---

## 三、选型准则（按优先级）

### 准则 1: 必含 fix，避开 breaking
```
必含修复: #5972(fix in #5994/#5974), #6347/#6065(fix in #6372)
避开 breaking: #6097(stateless condition) 若已合入主线则选其前一个 stable
```

### 准则 2: 选 stable tag 而非 main HEAD
- 不用 `crewai` 的开发分支/预发布
- 选 GitHub release 标记为 "Latest" 且距当前 ≥ 2 周的版本（给社区发现 bug 的时间）

### 准则 3: 锁定到精确 patch
- 不用 `crewai>=1.15,<2.0` 这类宽约束
- 用 `crewai==1.15.X`（精确 patch），连同传递依赖一起写入 lockfile

### 准则 4: Python 版本兼容
- CrewAI 1.15.x 要求 Python ≥ 3.10 且 < 3.13（典型）
- SDDP 锁定 Python 3.11.x（最稳定，与 chromadb/protobuf 生态兼容）

---

## 四、可执行的锁定流程（Dev-Phase 0 第一步）

### 4.1 选型验证脚本（在锁定前跑）

```bash
# backend/scripts/verify_crewai_version.sh（骨架）
TARGET_VERSION="<待填，按准则1-4筛出候选>"

# 1. 安装候选版本到隔离 venv
python -m venv .verify-venv && source .verify-venv/bin/activate
pip install crewai==$TARGET_VERSION

# 2. 验证必含的 fix 是否在该版本中
python -c "
import crewai
from crewai.flow.flow import Flow, listen, router, start, or_
import inspect
# 检查 or_ 是否支持循环重触发(#5972 fix 标志: or_ 不再标记 fire-once)
src = inspect.getsource(listen)
assert 'fire_once' not in src or '_already_fired' not in src, '#5972 fix 缺失'
print('crewai', crewai.__version__, ': #5972 fix present')
"

# 3. 跑最小对抗循环冒烟测试(1维度3轮)
python -m tests.smoke.adversarial_loop_smoke
# 期望: 循环能进入第2轮(#5972未修复则卡在第1轮)

# 4. 跑 @human_feedback 冒烟测试
python -m tests.smoke.human_feedback_smoke
# 期望: 不抛 AttributeError(#6347 fix 标志)

# 5. 跑 #6380 复现测试(确认 SafeAgent wrapper 确实兜住静默冻结)
python -m tests.smoke.async_freeze_mitigation
# 期望: SafeAgent 触发 timeout+retry，不卡死
```

### 4.2 锁定产物

通过验证后产出:
- `requirements.txt`: `crewai==1.15.X`（精确）
- `requirements.lock.txt`: `pip-compile` 产出的完整传递依赖锁定（含 chromadb/langchain 等易冲突包）
- `python-version`: `3.11.X`
- `CREWAI_VERSION_RATIONALE.md`: 记录为何选此版本（含准则1-4的逐条对照）

### 4.3 升级策略

- **不自动升级** CrewAI。升级是一次有评审的决策事件。
- 升级触发条件: 官方修复 #6380 / 出现阻塞性 bug / 安全漏洞。
- 升级流程: 在新分支跑完整验证脚本 + 全套冒烟测试 + Phase 0/1 集成测试 → 通过才合并。
- 适配层（见 00-final 第十节"适配层抽象"）是升级能低成本进行的前提，Phase 0 必须先建。

---

## 五、SafeAgent wrapper 是硬性前提（无论选哪个版本）

由于 #6380 未修复，**任何 CrewAI 版本都需要 SafeAgent wrapper**。这不是版本选择能回避的。在 Dev-Phase 0 模块3（SafeAgent wrapper）落地前，所有 agent 调用都视为不可靠。

SafeAgent 的最小契约（crewai-technical-research.md 已给骨架，此处强调约束）:
- 包裹 `kickoff` 与 `kickoff_async`
- 强制 `asyncio.wait_for` timeout（默认 120s，可配）
- tenacity retry：仅对 `TimeoutError/ConnectionError/RateLimitError` 重试，**不对** `ValueError/ParseError` 重试（避免无意义重试）
- 每次失败记录到 state.errors 供 UI 显示
- 区分"可恢复"(网络/限流)与"不可恢复"(解析/逻辑)错误，前者重试后者上报

---

## 六、对 Dev-Phase 0 模块清单的修订

原 00-final 第十节"Dev-Phase 0 模块"中:
- 模块3 "SafeAgent wrapper 1天" → **保留**，但标注为"阻塞性前置，所有 agent 调用前必须就绪"
- 新增 **模块0: "CrewAI 版本选定 + 验证脚本 + lockfile"**，工期 **1-2 天**，作为所有 Python 工作的第 0 步

修订后的关键路径: **0(版本)→3(SafeAgent)→4(角色)→6(Flow)→9(CLI验证)**

---

## 七、风险残留（明确标注为已接受）

即便按本策略锁定，仍存在不可消除的风险:
1. **升级窗口风险**: 项目周期 23-33 周，期间 CrewAI 必然发布多个版本；适配层是唯一缓冲
2. **未知 bug**: 选定版本可能含未被社区发现的 bug；冒烟测试只能覆盖已知模式
3. **#6380 长期未修复**: 若官方迟迟不修，SafeAgent wrapper 成为永久性技术债

这些在 `00-sddp-pet-final.md` 第十一节风险矩阵中保留为"已接受风险"。
