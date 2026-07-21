# Adaptation Layer

## Purpose

封装 CrewAI（流程编排引擎）的具体实现，对外提供与 CrewAI 无关的 `FlowDefinition` 抽象（4 个原语：start / listen / router / persist），并提供 `MockFlowAdapter` 用于无 LLM、无 CrewAI 依赖的解耦测试。同时为 CrewAI 版本升级建立评审决策与验证流程，使升级成为可控事件而非隐式依赖漂移。本 capability 为 Dev-Phase 0 交付范围（`dod.md` D0-3、D0-7）。

## Requirements

### Requirement: FlowDefinition 抽象 MUST 与 CrewAI Flows API 解耦

`adaptation-layer` MUST 提供 `FlowDefinition` 抽象基类，封装 SDDP 所需的 4 个原语：`start`（流程入口）、`listen`（监听上游事件）、`router`（条件路由）、`persist`（状态持久化）。CrewAI 的具体实现 MUST 通过 `CrewAIFlowAdapter` 适配，不在 `FlowDefinition` 接口中暴露 CrewAI 类型。

#### Scenario: FlowDefinition 接口不含 CrewAI 类型
- **WHEN** 审查 `sddp/adaptation/flow_definition.py` 的公开 API（类签名、方法参数、返回类型）
- **THEN** 接口 MUST 不 import `crewai` 包；类型注解 MUST 使用 Python 标准库或本项目内部类型

#### Scenario: CrewAIFlowAdapter 实现 FlowDefinition
- **WHEN** 审查 `sddp/adaptation/crewai_adapter.py`
- **THEN** 该文件 MUST 定义 `CrewAIFlowAdapter` 类，继承 `FlowDefinition`，并实现 4 个原语的方法

### Requirement: Adaptation Layer MUST 提供 Mock Adapter 用于解耦测试

为满足 `dod.md` D0-3（适配层抽象就位）与 D0-7（5 角色 kickoff 可在 LLM mock 下通过），adaptation-layer MUST 提供至少一个 `MockFlowAdapter`，在不依赖真实 CrewAI 与 LLM API 的情况下驱动 Flow 原语。

#### Scenario: Mock adapter 冒烟测试通过
- **WHEN** 运行 `pytest tests/adaptation/test_mock_adapter.py`
- **THEN** 测试 MUST 通过（退出码 0）；测试 MUST 覆盖 4 个原语（start/listen/router/persist）的最小行为

#### Scenario: Mock adapter 用于 5 角色 kickoff 测试
- **WHEN** 运行 `pytest tests/engine/test_5_roles_kickoff.py`（D0-7）
- **THEN** 该测试 MUST 使用 `MockFlowAdapter` 而非真实 CrewAI；测试 MUST 在不调用真实 LLM API 的情况下通过

### Requirement: 适配层升级路径 MUST 文档化

依据 `analysis/03` 第 4.3 节，CrewAI 升级是一次评审决策事件，依赖适配层作为缓冲。adaptation-layer MUST 在 `sddp/adaptation/README.md` 中文档化升级流程：(1) 触发条件（#6380 修复 / 阻塞性 bug / 安全漏洞）；(2) 验证流程（新分支跑 `verify_crewai_version.sh` + 全套冒烟测试）；(3) 通过标准。

#### Scenario: 升级流程文档可被引用
- **WHEN** 后续 Dev-Phase 出现 CrewAI 升级需求
- **THEN** `sddp/adaptation/README.md` MUST 包含升级流程章节，含明确的"通过标准"（如所有 Dev-Phase 0 的契约测试 + Golden DEMO 重放全部通过）
