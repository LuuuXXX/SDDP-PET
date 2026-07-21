# Contracts

本目录存放 SDDP-PET 的关键接口契约测试代码。契约清单（不含代码）维护在上级目录的 `../contracts-index.md`。

## 子目录组织

按契约类型分组：

```
contracts/
├── websocket/            # WebSocket Push/RPC 消息契约（Dev-Phase 1 引入）
├── knowledge-graph/      # KnowledgeGraphQueryAPI 契约（Dev-Phase 0 KG-MVP 引入）
├── safe-agent/           # SafeAgent wrapper 接口契约（Dev-Phase 0 引入）
├── adaptation-layer/     # CrewAI 适配层 Flow 抽象契约（Dev-Phase 0 引入）
└── json-schema/          # proposal / delta-spec / delta-design 等输出 schema（Dev-Phase 0 引入）
```

## 命名约定

测试文件命名：`<contract-name>.<test-ext>`，例如：
- `websocket/push-agent-state-change.test.ts`
- `knowledge-graph/find-callers.test.py`
- `safe-agent/timeout-retry.test.py`

## 单调增长规则

契约测试集 MUST 单调增长（只允许新增，不允许删除）。如需删除/变更某契约，MUST：
1. 在所属 Dev-Phase 变更的 `proposal.md` 的"跨阶段接口变更登记"小节登记
2. 标注 BREAKING（如适用）
3. 提供迁移路径
4. 升级引用该契约的所有历史 Golden Demo

详见 `openspec/specs/regression-strategy/spec.md` 的"关键接口契约 MUST 捕获为契约测试"与"跨阶段接口变更 MUST 登记并向后兼容评估"需求。

## 引入时机

| 子目录 | 引入 Dev-Phase | 来源规格 |
|--------|---------------|----------|
| `knowledge-graph/` | Dev-Phase 0（KG-MVP） | `analysis/02-code-knowledge-graph-design.md` |
| `safe-agent/` | Dev-Phase 0（模块 3） | `analysis/00-sddp-pet-final.md` 第五节 |
| `adaptation-layer/` | Dev-Phase 0（模块 8） | `analysis/00-sddp-pet-final.md` 第十节 |
| `json-schema/` | Dev-Phase 0（模块 5） | `analysis/00-sddp-pet-final.md` 第十节 |
| `websocket/` | Dev-Phase 1（D1-2） | `analysis/00-sddp-pet-final.md` 第七节 |
| `execution-subsystem/` | Dev-Phase 3a | `analysis/05-quality-gate-flow-design.md` |
