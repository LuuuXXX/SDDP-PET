# G3: LLM Provider 策略与降级矩阵

> 日期: 2026-07-20
> 状态: P0 缺口补齐
> 关联: 01-final-review.md G3; 00-sddp-pet-final.md 第二节(三层保障)、第十三节(缺失考虑)

---

## 一、问题陈述

00-sddp-pet-final.md 的核心可靠性策略是"三层 LLM 保障: Structured Outputs(99.9%) + pydantic(85-95%) + guardrails"。但 Structured Outputs API 是 **OpenAI 专有能力**。这意味着:
- SDDP-Pet 的可靠性**强依赖 OpenAI**
- 与项目定位(MIT/开源/可离线)存在张力
- 此前分析把"多 provider 密钥管理"列为缺失项，但**没点明: provider 切换 = 可靠性降级**，这是产品级取舍

本文件明确各 provider 的能力等级、MVP 决策、以及降级路径。

---

## 二、Provider 能力矩阵

结构化输出强制能力的业界现状（2026-07）:

| Provider | Schema 强制能力 | 强制等级 | 一次性合规率 | 备注 |
|----------|----------------|---------|------------|------|
| **OpenAI** | Structured Outputs API(JSON Schema via function calling) | **Tier-S 强制生成期** | ~99.9% | 唯一在生成期保证 100% schema 合规的 |
| **Anthropic(Claude)** | tool_use 强制 JSON + prompt 引导 | **Tier-A 后校验强** | ~95-98% | tool_use 强制 JSON 但 schema 约束弱于 OpenAI；需 pydantic 兜底 |
| **Google(Gemini)** | JSON mode + responseSchema | **Tier-A 后校验强** | ~95-97% | responseSchema 支持但嵌套/枚举约束不完整 |
| **Mistral** | JSON format + function calling | **Tier-B** | ~90-95% | JSON mode 可用但 schema 强制有限 |
| **本地 Ollama(开源模型)** | 依赖具体模型; 多数仅 JSON mode 无 schema 强制 | **Tier-C** | ~75-90% | 取决于模型; qwen/deepseek 等较好但仍远低于 OpenAI |
| **纯 prompt 引导(任意模型)** | 模板注入 + 重试 | **Tier-D** | ~80-85% | 00-final 第三节"纯 Markdown 模板"对应此档 |

### 三层保障在不同 provider 下的实际表现

| Provider | 第一层(生成期强制) | 第二层(pydantic 后校验) | 第三层(guardrails) | 综合可靠性 |
|----------|-------------------|----------------------|-------------------|----------|
| OpenAI | ✅ 99.9% | ✅ 兜底剩余 0.1% | ✅ 域校验 | **~99.95%** |
| Claude/Gemini | ⚠️ 95-98% | ✅ 兜底+重试(每次重试=1次完整 LLM 调用成本) | ✅ 域校验 | ~98-99%(成本↑) |
| Mistral | ⚠️ 90-95% | ✅ 重试更多 | ✅ | ~95-97%(成本↑↑) |
| Ollama 本地 | ❌ 75-90% | ✅ 重试频繁 | ✅ | ~90-95%(成本↑↑↑，延迟↑) |

**关键洞察**: 第二层(pydantic)在非 OpenAI provider 上会**频繁触发重试**，每次重试都是一次完整 LLM 调用。这直接冲击 00-final 第九节成本模型——切到非 OpenAI provider，**成本可能翻 2-4 倍**且延迟显著增加。

---

## 三、MVP 决策: OpenAI-only（明确取舍）

### 决策
**Dev-Phase 0-2 (MVP + 对抗验证) 锁定 OpenAI 作为唯一 provider。**

### 理由
1. **可靠性是 SDDP 引擎的核心价值**。SDDP 卖点是"对抗+裁决+质量关卡"，每一步都依赖结构化输出可靠。Tier-A/B/C 的重试成本与延迟会让对抗循环(5轮×多角色)变得不经济
2. **MVP 阶段验证的是引擎机制是否成立**，不是验证多 provider 兼容。多 provider 是 Dev-Phase 4/5 的优化项
3. **成本可控**: OpenAI Structured Outputs 几乎无重试，单流程成本可预测($1-12.5，见 00-final 第九节)

### 取舍的明确代价（标注为已接受）
- ❌ 用户必须自备 OpenAI API key（增加采用摩擦）
- ❌ 数据发送到 OpenAI（隐私敏感用户排斥；00-final 第八节隐私同意界面必须明确告知）
- ❌ 与"可离线"目标冲突（离线推迟到 Dev-Phase 5，且离线=可靠性降级到 Tier-C）

### 这个决策对产品定位的影响
SDDP-Pet 实际定位分两段:
- **Dev-Phase 0-4**: "OpenAI 驱动的高可靠性 SDDP 引擎 + 桌宠"（非完全离线开源）
- **Dev-Phase 5(可选)**: "可离线但可靠性降级的 SDDP 引擎"

00-final 第十二节"竞争定位"需据此调整：护城河是 SDDP 引擎+可靠性，而非"开源离线"。这点在更新 00-final 时体现。

---

## 四、Provider 抽象层设计（为未来降级铺路）

即便 MVP 锁 OpenAI，代码必须从 Day1 通过抽象层访问 LLM，避免硬编码 OpenAI 调用。

### 4.1 抽象接口

```python
# backend/llm/provider.py（骨架）
from typing import Protocol
from pydantic import BaseModel

class StructuredOutputCapability(Enum):
    SCHEMA_ENFORCED = "schema_enforced"   # OpenAI Structured Outputs
    JSON_WITH_SCHEMA_HINT = "json_hint"   # Claude/Gemini
    JSON_MODE_ONLY = "json_only"          # Mistral
    PROMPT_ONLY = "prompt_only"           # Ollama/通用

class LLMProvider(Protocol):
    name: str
    capability: StructuredOutputCapability

    def structured_complete(
        self,
        prompt: str,
        output_schema: type[BaseModel],
        max_retries: int = 3,
    ) -> "StructuredResult": ...
```

### 4.2 可靠性适配器（核心）

不同 capability 等级的 provider 走不同的保障路径，业务层无感知:

```
SCHEMA_ENFORCED (OpenAI):
  调用 → 直接返回（几乎无需重试）

JSON_WITH_SCHEMA_HINT (Claude/Gemini):
  调用 → pydantic 校验 → 失败则带错误反馈重试(max_retries) → 仍失败则降级处理

JSON_MODE_ONLY (Mistral):
  调用 → pydantic 校验 → 重试 → 降级 → 最终失败上报

PROMPT_ONLY (Ollama):
  调用 → 模板注入 → pydantic 校验 → 多轮重试 → 高失败率预期 → 流程可能卡住
```

### 4.3 降级策略（每角色可配）

关键场景(如调度官裁决)用 OpenAI 保证可靠；次要场景(如挑评师初步质疑)可降级到更便宜 provider 以省成本。配置:
```yaml
# config/llm_routing.yaml
role_routing:
  调度官: { provider: openai, model: gpt-4o }       # 裁决必须可靠
  架构师: { provider: openai, model: gpt-4o }       # 设计必须可靠
  挑评师: { provider: openai, model: gpt-4o-mini }  # 可降级模型省成本
  代码资产管理员: { provider: openai, model: gpt-4o-mini }  # 查询总结
  实证师: { provider: openai, model: gpt-4o }       # 验证必须可靠
```

---

## 五、对成本模型的影响（修订 00-final 第九节）

00-final 第九节成本模型基于 OpenAI 假设。补充 provider 维度:

| 场景 | OpenAI(Tier-S) | Claude(Tier-A) | 本地 Ollama(Tier-C) |
|------|---------------|----------------|---------------------|
| 快速通道 | $1 | $2-3(重试) | $0(电费)但延迟3-5x |
| 中等(3对抗+2修复) | $6 | $12-18 | $0 但单流程可能 30-60min |
| 复杂(5对抗+3修复) | $12.5 | $25-40 | $0 但可能因解析失败卡死 |

**结论**: 非 OpenAI provider 不是"免费替代"，而是"用延迟/失败率换金钱"。MVP 选 OpenAI 是经济性+可靠性双重最优。

---

## 六、离线路径(Dev-Phase 5)的可行性再评估

00-final 把"离线(Ollama)"列为 Dev-Phase 5 可选。基于本分析修正:
- 离线 SDDP 的可靠性将降到 Tier-C(~90-95%)，对抗循环失败率显著上升
- 离线模式下应**简化流程**: 减少对抗轮数(5→2)、减少质量关卡(3角色→1角色)、用规则映射替代部分 LLM 裁决
- 离线不是"完整 SDDP 的离线版"，而是"降级版 SDDP"
- Dev-Phase 5 启动前需先做"Tier-C 下对抗循环可行性验证"，可能结论是"离线只支持快速通道，不支持全流程"

这点在更新 00-final 时写入 Dev-Phase 5 说明。

---

## 七、对 00-final 的修订项

更新 00-sddp-pet-final.md 时:
1. 第二节技术选型表: "三层 LLM 保障"行增加备注"MVP 锁定 OpenAI；多 provider 经抽象层支持"
2. 第十二节竞争定位: 护城河表述从"开源"调整为"引擎可靠性"
3. 第十三节缺失考虑: "LLM 密钥管理生命周期"补充"provider 切换=可靠性降级"维度
4. 第九节成本模型: 增加 provider 对比表（本文件第五节）

---

## 八、已接受风险

1. **MVP 强依赖 OpenAI** — 为可靠性付出 vendor lock-in 代价，Dev-Phase 4+ 通过抽象层缓解
2. **离线模式可靠性降级** — 离线 ≠ 完整 SDDP，是降级版
3. **非 OpenAI 用户被排除在 MVP 外** — 明确的目标用户取舍
