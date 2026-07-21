# SDDP-PET Backend (Dev-Phase 0 + 1)

SDDP-PET (Spec-Driven Development Process desktop pet) 引擎核心。

本目录是后端 Python 代码与测试，覆盖 Dev-Phase 0 + Dev-Phase 1 的后端范围：
- **Dev-Phase 0**：5 角色线性 CrewAI Flow（需求官 → 调度官 → 架构师 → 实施师 → 代码资产管理员）+ SafeAgent / Adaptation Layer / KG-MVP / Engine Core + `sddp run` CLI + JSON↔Markdown 渲染 + 内置 token 计量 + `@persist` 中断恢复
- **Dev-Phase 1**：`sddp serve` WebSocket IPC server（端口 8765）+ `WebSocketHumanFeedbackAdapter` + 安全 prefilter（正则脱敏）+ OTEL 硬禁用 + 观测指标记录（`~/.sddp-pet/metrics.json`）

规格与设计依据：
- 路线图与 DoD：[`../openspec/specs/development-roadmap/`](../openspec/specs/development-roadmap/)（`phases.md` / `dod.md` / `no-go-rollback.md` / `modules.md`）
- Dev-Phase 0 变更（已 archive）：[`../openspec/changes/archive/2026-07-21-dev-phase-0-engine-core/`](../openspec/changes/archive/2026-07-21-dev-phase-0-engine-core/)
- Dev-Phase 1 变更：[`../openspec/changes/dev-phase-1-desktop-pet-mvp/`](../openspec/changes/dev-phase-1-desktop-pet-mvp/)
- 技术决策：[`../analysis/`](../analysis/)，特别是 [`03-crewai-version-strategy.md`](../analysis/03-crewai-version-strategy.md)、[`08-websocket-ipc-contract.md`](../analysis/08-websocket-ipc-contract.md)、[`09-secret-storage-cross-platform.md`](../analysis/09-secret-storage-cross-platform.md)

## 安装

依赖：Python `>=3.11,<3.13`（具体 patch 见 [`python-version`](python-version)，实测锁定 3.11.x 最稳定；详见 `analysis/03` 准则 4）。

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -e '.[dev]'
```

`pip install -e '.[dev]'` 会按 [`pyproject.toml`](pyproject.toml) 安装 `crewai==1.15.4`（精确 patch，选定理由见 [`CREWAI_VERSION_RATIONALE.md`](CREWAI_VERSION_RATIONALE.md)）+ 全部传递依赖。

如需锁定到具体传递依赖版本（推荐生产环境），用 [`requirements.lock.txt`](requirements.lock.txt)（任务 1.5 `pip-compile` 产出）：

```bash
pip install -r requirements.lock.txt
pip install -e '.[dev]' --no-deps
```

## 运行

### CLI 模式（Dev-Phase 0）

`OPENAI_API_KEY` 未设置时自动降级到 `--mock` 模式（不调用真实 LLM，适合开发调试）。

### 跑一个 proposal

```bash
# 字符串 proposal
sddp run "给这个 Python 项目加一个配置热重载功能" --project tests/fixtures/sample-python-project/

# 文件路径 proposal（Dev-Phase 0 Golden Demo 候选）
sddp run tests/fixtures/proposals/config-hot-reload.txt \
    --project tests/fixtures/sample-python-project/ \
    --output out/dev-phase-0-golden-demo/

# 显式 mock 模式（不调用 OpenAI API）
sddp run tests/fixtures/proposals/add-logging.txt --project tests/fixtures/sample-python-project/ --mock --yes
```

### IPC 服务器模式（Dev-Phase 1）

Dev-Phase 1 引入 `sddp serve` —— 启动 FastAPI WebSocket 服务器（端口 8765），
供 Electron 桌宠 UI 连接。

```bash
# 真实 LLM 模式（需 OPENAI_API_KEY 或 DeepSeek 经 scripts/deepseek-env.sh）
sddp serve --project tests/fixtures/sample-python-project/

# Mock 模式（前端开发 / CI 用，不需要 API key）
sddp serve --mock --port 8765

# 健康检查
curl http://127.0.0.1:8765/health
# → {"status":"ok","mock_mode":true}
```

完整 WS 消息契约见 [`analysis/08-websocket-ipc-contract.md`](../analysis/08-websocket-ipc-contract.md)。

### 输出目录

`sddp run` 完成后，`--output` 目录（默认 `./out/`）含：
- `proposal.md` / `delta_spec.md` / `delta_design.md` / `architecture_research.md`（4 个 markdown 文档）
- `cost_report.json`（含 `measured_cost_usd` / `wall_clock_minutes_excluding_human_wait` / `structured_output_first_try_rate` 等度量字段）

### 其他子命令

```bash
sddp --help                # 主命令帮助
sddp run --help            # run 子命令详细参数
sddp scan <path>           # 仅扫描项目到 KG（不跑 Flow）
sddp flows                 # 列出 pending/resumable flows
```

### 中断恢复

`Ctrl+C` 中断后，Flow state 持久化到 `~/.sddp-pet/flow_state.db`（SQLite）。重启用 `--resume <flow_id>`：

```bash
sddp run ... --resume <flow_id_from_previous_run>
```

## 测试

```bash
# 单元 + 集成测试（LLM 全 mock，CI 安全）—— 对应 dod.md D0-1 ~ D0-10
pytest tests/

# 排除 E2E（更快的反馈循环）
pytest tests/ -m "not e2e"

# 仅 E2E（需 OPENAI_API_KEY；非 CI 常规运行，仅用于 Go 判定 + Golden Demo 冻结）
pytest tests/ -m e2e -v

# KG 准确性评估（dod.md D0-6，召回率 ≥ 70%）
python -m sddp.kg.evaluate --gold tests/kg/golden.json
```

测试组织（见 [`../openspec/regression/contracts-index.md`](../openspec/regression/contracts-index.md) 的"契约 → 测试代码映射"）：

| 模块 | 测试目录 | 对应 DoD |
|------|----------|----------|
| SafeAgent | `tests/safe_agent/` | D0-2 |
| Adaptation Layer | `tests/adaptation/` | D0-3 |
| KG-MVP | `tests/kg/` | D0-4 / D0-5 / D0-6 |
| Engine Core | `tests/engine/` | D0-7 / D0-8 |
| CLI Runner | `tests/cli/` | D0-9 / D0-10 |
| E2E | `tests/e2e/` | D0-9 / D0-11 / D0-12 / D0-13 / D0-14 |

## CrewAI 版本选定

- **选定版本**：`crewai==1.15.4`（精确 patch）
- **选定理由**：详见 [`CREWAI_VERSION_RATIONALE.md`](CREWAI_VERSION_RATIONALE.md)，按 [`analysis/03-crewai-version-strategy.md`](../analysis/03-crewai-version-strategy.md) 第 4.2 节的 4 准则（必含 fix / 避 breaking / 选 stable / Python 兼容）逐条对照
- **重新验证**：升级 CrewAI 时重跑 `bash scripts/verify_crewai_version.sh`（5 个冒烟检查：#5972 / #6347 / #6380 复现 / 1 维度 3 轮对抗 / @human_feedback）

## 模块结构

```
sddp/
├── safe_agent/     # CrewAI #6380 防护（SafeAgent wrapper + retry policy）
├── adaptation/     # FlowDefinition 抽象 + CrewAI/Mock adapter
├── kg/             # KG-MVP（manifest→SCIP/tree-sitter→SQLite→4 类查询带置信度）
├── engine/         # 5 角色 backstory + agents + 线性 Flow + token 计量
├── cli/            # sddp run 命令 + feedback adapter + flow_state 持久化
└── schemas/        # Pydantic v2 模型（proposal/delta_spec/delta_design）+ JSON↔Markdown 渲染
```

## 更多信息

- Dev-Phase 0 完整规格：[`../openspec/changes/dev-phase-0-engine-core/`](../openspec/changes/dev-phase-0-engine-core/)
- 项目设计文档：[`../SDDP/SDDP智能小队设计文档.md`](../SDDP/SDDP智能小队设计文档.md)
- 回归基础设施：[`../openspec/regression/`](../openspec/regression/)
