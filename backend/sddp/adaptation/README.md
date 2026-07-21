# sddp/adaptation

CrewAI 解耦抽象层。提供 4 个 SDDP 原语 (`start` / `listen` / `router` / `persist`)
的统一接口，使 engine-core 不直接依赖 CrewAI Flows API。

## 模块

- `flow_definition.py` — 抽象基类 `FlowDefinition`，公开 API 不 import crewai
- `crewai_adapter.py` — `CrewAIFlowAdapter`，包装 CrewAI Flow 子类
- `mock_adapter.py` — `MockFlowAdapter`，单元测试用，无 CrewAI / 无 LLM

## 升级流程（analysis/03 §4.3）

CrewAI 升级是一次评审决策事件，依赖本适配层作为缓冲。

### 触发条件
- 官方修复 #6380（异步静默冻结）
- 出现阻塞性 bug
- 安全漏洞

### 验证流程

1. 在新分支运行：
   ```bash
   bash scripts/verify_crewai_version.sh <candidate-version>
   ```
2. 跑完整冒烟测试：
   ```bash
   pytest tests/ -m "not e2e"
   ```
3. 跑 Dev-Phase 0 契约测试 + Golden Demo 重放：
   ```bash
   pytest tests/kg/ tests/safe_agent/ tests/adaptation/ tests/engine/ tests/cli/
   bash openspec/regression/golden-demos/dev-phase-0.md  # 按 demo 文档执行
   ```

### 通过标准

- `verify_crewai_version.sh` 全部 5 项冒烟通过
- 所有单元测试 + 集成测试（非 E2E）PASS
- 历史 Golden Demo 重放无退化（成本 ≤ $5、合规率 ≥ 99% 等 D0-11~14 阈值全部满足）
- `CrewAIFlowAdapter.validate_crewai_flow_has_4_primitives()` 在 Engine Core 使用的 Flow 子类上仍返回 `[]`（无缺失原语）

任一不满足 → 升级失败，保留旧版本，触发 No-Go 评估。
