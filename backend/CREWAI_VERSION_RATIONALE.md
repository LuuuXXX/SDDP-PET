# CrewAI 版本选定理由（CREWAI_VERSION_RATIONALE.md）

> 本文件依据 `analysis/03-crewai-version-strategy.md` 第 4.2 节产出。
> Dev-Phase 0 实现：2026-07-20

## 选定版本

```
crewai==1.15.4
```

`requirements.lock.txt`（任务 1.5 pip-compile 产出）含完整传递依赖锁定。

## 4 准则逐条对照（analysis/03 §三）

### 准则 1: 必含 fix，避开 breaking

| Issue/PR | 要求 | 1.15.4 状态 | 验证 |
|----------|------|------------|------|
| #5972 `or_()` 循环只触发一次（fix in #5994/#5974） | 必含 | ✅ 含 | `inspect.getsource(listen)` 不再含 `_already_fired` 标志（实测 2026-07-20）；4 类原语 `start/listen/router/or_` 全部可导入 |
| #6347/#6065 `human_input=True` 崩溃（fix in #6372） | 必含 | ✅ 含（推断） | `from crewai.agent import Agent` 可导入；完整验证依赖 `tests/engine/test_human_feedback.py`（Dev-Phase 0 模块 6 集成测试中） |
| #6380 异步 LLM 失败静默冻结 | 不可依赖官方修复 | N/A | SafeAgent wrapper（`sddp/safe_agent/`）作为硬性前提，不依赖 CrewAI 上游修复 |
| #6097 condition 评估改 stateless（breaking） | 必须避开 | ✅ 避开 | 1.15.4 早于该 PR 的合入主线；选定版本不含此 breaking change |
| #6370 router hops 无上限 | 自实现 max_rounds | N/A | 不依赖该 PR，由 `sddp/engine/flows/phase_0_2_linear.py` 显式控制流程步数 |

### 准则 2: 选 stable tag 而非 main HEAD

- 1.15.4 是 PyPI 当前"Latest"发布版本（PyPI `info.version` 字段）
- 上传时间：2026-07-17T14:34:17Z（距选定日 2026-07-20 为 3 天）
- **偏差说明**：`analysis/03` 准则 2 建议"距当前 ≥ 2 周"，但 1.15.x 系列仅有此 patch 可选；2 周观察窗口在 Dev-Phase 0 实施期（3-4 周）内会自然满足。如期间暴露重大 bug，按 No-Go 条件 B（`openspec/specs/development-roadmap/no-go-rollback.md` DP0-NG-B）回退到上一 stable。

### 准则 3: 锁定到精确 patch

- 锁定 `crewai==1.15.4`（精确 patch，非 `>=1.15,<2.0` 宽约束）
- `pyproject.toml` 的 `dependencies` 含精确等号约束
- `requirements.lock.txt`（pip-compile 产出）含完整传递依赖（chromadb / langchain / protobuf / grpcio / onnxruntime / litellm 等）

### 准则 4: Python 版本兼容

- **CrewAI 1.15.4 声明**：`Requires-Python: <3.14,>=3.10`（PyPI 元数据）
- **本环境实际**：Python 3.12.3（apt 仓库中无 python3.11；apt-cache 查询返回空）
- **偏差登记**：`analysis/03` 准则 4 推荐 Python 3.11.x（与 chromadb/protobuf 生态最稳定），但本环境仅有 3.12.3 可用。3.12 在 CrewAI 1.15.4 的允许范围内（<3.14），冒烟导入测试通过（`crewai.flow.flow` / `crewai.agent.Agent` 全部可导入）。若实施中遇到 3.12 特有兼容性问题，触发 No-Go 并安装 Python 3.11（deadnsakes PPA 或源码编译）。

## 验证脚本

`backend/scripts/verify_crewai_version.sh` 已实现（依据 `analysis/03` §4.1 骨架），含 5 个冒烟检查：
1. `crewai.flow.flow` 导入（#5972 fix 路径存在）
2. `crewai.agent.Agent` 导入（#6347 fix 假定存在）
3. Smoke Flow with router + listen wiring（无运行时 kickoff）
4. `crewai.utilities.internal_instructor` 导入（human_feedback 内部）
5. #6380 由本项目 SafeAgent 提供（非 CrewAI 上游职责）

实测命令（在 `backend/` 下）：
```bash
bash scripts/verify_crewai_version.sh 1.15.4
```

## 升级策略（依据 analysis/03 §4.3）

- **不自动升级** CrewAI。升级是一次有评审的决策事件。
- 升级触发条件：官方修复 #6380 / 出现阻塞性 bug / 安全漏洞。
- 升级流程：在新分支跑 `verify_crewai_version.sh` + 全套冒烟测试 + Dev-Phase 0 契约测试 + Golden Demo 重放 → 通过才合并。
- 适配层（`sddp/adaptation/`）是升级能低成本进行的前提。

## 已接受风险（依据 analysis/03 §七）

1. **升级窗口风险**：项目周期 21-35 周，期间 CrewAI 必然发布多个版本；适配层是唯一缓冲。
2. **未知 bug**：选定版本可能含未被社区发现的 bug；冒烟测试只能覆盖已知模式。
3. **#6380 长期未修复**：若官方迟迟不修，SafeAgent wrapper 成为永久性技术债。

以上 3 项保留在 `analysis/00-sddp-pet-final.md` 风险矩阵中，并已在 `openspec/regression/accepted-risks.md` 中作为 AR-1~AR-4 的关联上下文登记。
