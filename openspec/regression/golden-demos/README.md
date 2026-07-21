# Golden Demos

本目录存放每个 Dev-Phase 完成时（Go 判定通过时）冻结的 Golden Demo。每个 Dev-Phase 一个文件：

- `dev-phase-0.md`
- `dev-phase-1.md`
- `dev-phase-2.md`
- `dev-phase-3a.md`
- `dev-phase-3b.md`
- `dev-phase-4.md`（按选定特性子项分别冻结）
- `dev-phase-5.md`（可选）

## 命名约定

`dev-phase-<n>.md`，其中 `<n>` 与 `openspec/specs/development-roadmap/phases.md` 的 Dev-Phase 标识完全一致（含 `3a` / `3b` 这类带后缀的形式）。

## 文件格式

每个 Golden Demo 文件 MUST 包含以下章节：

```markdown
# Golden Demo: Dev-Phase <n> — <短标题>

## 冻结元数据
- 冻结日期: YYYY-MM-DD
- git tag: dev-phase-<n>-v1
- 关联变更: openspec/changes/dev-phase-<n>-<scope>/
- 关联 DoD: openspec/specs/development-roadmap/dod.md#dev-phase-<n>

## 输入场景
<自然语言需求或命令，描述具体且可复现>

## 期望输出
<端到端输出的关键字段或可观察行为；不要求逐字相同>

## 度量阈值范围
| 指标 | 下限 | 上限 | 来源 |
|------|------|------|------|
| 单流程成本 (USD) |  |  | dod.md |
| 端到端延迟 (min) |  |  | dod.md |
| ... |  |  |  |

## 运行命令
<执行该 demo 的具体命令，含环境准备步骤>

## 重放结果历史
| 重放日期 | 重放基线 (git tag) | 重放目标 (HEAD) | 结果 | 报告路径 |
|----------|-------------------|-----------------|------|----------|
```

## 不可变性规则

Golden Demo 一经冻结，在该 Dev-Phase 内 MUST 不修改。修改需作为新一阶段变更的"基线升级"，且 MUST 走接口变更登记流程（见 `openspec/specs/regression-strategy/spec.md` 的"跨阶段接口变更"需求）。

BREAKING 接口变更导致的 Golden Demo 升级 MUST 在文件末尾追加"基线升级历史"小节，保留旧版本引用。
