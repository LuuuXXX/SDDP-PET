## ADDED Requirements

### Requirement: cli-runner MUST 提供 sddp run 命令

cli-runner MUST 提供 `sddp run "<proposal>"` 命令作为 Dev-Phase 0 的唯一人机交互入口（依据 `dod.md` D0-9）。该命令 MUST 接受自然语言 proposal 字符串或文件路径作为输入，启动 engine-core Flow。

#### Scenario: sddp run 命令可用
- **WHEN** 运行 `sddp --help`
- **THEN** 帮助输出 MUST 含 `run` 子命令；`run` 子命令 MUST 接受 `<proposal>` 位置参数与 `--project <path>` 选项

#### Scenario: 文件路径作为 proposal 输入
- **WHEN** 运行 `sddp run tests/fixtures/proposals/config-hot-reload.txt --project tests/fixtures/sample-python-project/`
- **THEN** cli-runner MUST 读取文件内容作为 proposal 字符串；启动 engine-core Flow；产出文档写入 `--output` 指定目录（默认 `./out/`）

### Requirement: cli-runner MUST 实现 3 用户确认点的 stdin/stdout 阻塞

依据 SDDP 设计文档 Phase 0（需求确认）+ Phase 1（方案确认）+ Phase 2（任务确认）的用户确认点要求，与 `dod.md` D0-4，cli-runner MUST 通过 @human_feedback CLI adapter 在 3 个确认点阻塞等待 stdin 输入。

#### Scenario: 3 个确认点阻塞/恢复
- **WHEN** Flow 执行到确认点（需求确认/方案确认/任务确认）
- **THEN** cli-runner MUST 在 stdout 显示待确认内容摘要 + 提示"输入 y 继续 / n 中止 / e 编辑"；MUST 阻塞等待 stdin 输入；用户输入 `y` 后 Flow MUST 恢复执行

#### Scenario: @human_feedback 经 CLI adapter 适配
- **WHEN** CrewAI @human_feedback 触发
- **THEN** cli-runner 的 `CLIHumanFeedbackAdapter` MUST 接管该调用；MUST 将 @human_feedback 的请求转为 stdin/stdout 交互（而非 CrewAI 默认的 GUI/web 表单）

### Requirement: cli-runner MUST 支持中断后从 @persist 恢复

依据 `dod.md` D0-4 与 CrewAI @persist 机制，cli-runner MUST 支持流程中断（Ctrl+C / 进程崩溃）后从上次持久化状态恢复。

#### Scenario: 中断后恢复流程
- **WHEN** 用户在 Flow 执行中按 Ctrl+C 中断；重新运行相同命令（含 `--resume <flow_id>` 选项或自动检测 pending flow）
- **THEN** cli-runner MUST 从上次 @persist 状态恢复；MUST 不重做已完成的步骤；恢复后 Flow MUST 从中断点继续

#### Scenario: @persist 数据持久化到 SQLite
- **WHEN** Flow 执行中
- **THEN** Flow state MUST 通过 adaptation-layer 的 `persist` 原语写入本地 SQLite（路径默认 `~/.sddp-pet/flow_state.db`）；每个 Flow 实例 MUST 有唯一 `flow_id`

### Requirement: cli-runner MUST 输出可读的文档与 cost_report

cli-runner MUST 把 engine-core 产出的 3 种文档（proposal/delta-spec/delta-design）经 JSON ↔ Markdown 渲染（engine-core spec）写入 `--output` 目录；同时把 cost_report.json 写入该目录，含本次 Flow 的所有度量字段。

#### Scenario: 输出目录结构
- **WHEN** `sddp run` 完成后审查 `--output` 目录
- **THEN** 目录 MUST 含 `proposal.md` / `delta_spec.md` / `delta_design.md` / `architecture_research.md` / `cost_report.json` 5 个文件；任一缺失 MUST 在 stderr 报错

#### Scenario: cost_report 可在 CLI 显示摘要
- **WHEN** Flow 完成后
- **THEN** cli-runner MUST 在 stdout 显示 cost 摘要（成本、耗时、合规率）；用户可通过 `--verbose` 查看完整 report
