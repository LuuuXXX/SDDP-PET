## ADDED Requirements

### Requirement: KG-MVP 预扫描器 MUST 支持 Python 单语言索引

依据 `analysis/02-code-knowledge-graph-design.md` 第五节，KG-MVP（最小可行版）MUST 集成 SCIP 索引器（Python 起步）+ tree-sitter fallback，扫描本地代码库产出 SQLite 知识图。**范围限定**：Dev-Phase 0 仅交付 Python 单语言、不含增量更新、不含多语言、不含远程模式（推迟到 KG-v1）。

#### Scenario: Python 项目预扫描产出非空图
- **WHEN** 运行 `python -m sddp.kg.scan <path>` 其中 `<path>` 是一个 ≥10 文件的 Python 项目（含函数定义、调用、import、class 继承）
- **THEN** 命令 MUST 退出码 0；SQLite 知识图中 `Symbol` 节点数 MUST > 0；`scan_version` 元数据 MUST 写入

#### Scenario: 排除规则默认生效
- **WHEN** 扫描的项目含 `vendor/` / `node_modules/` / `dist/` / `build/` / `.git/` 目录
- **THEN** 这些目录 MUST 被默认排除；用户可通过 PCM 配置覆盖排除规则（Dev-Phase 0 通过 CLI 参数 `--exclude` 覆盖）

### Requirement: 知识图 schema MUST 含 5 类节点与 8 类边

依据 `analysis/02` 第四节，知识图 schema MUST 实现 5 类节点（`Repository` / `File` / `Symbol` / `Module` / `Package`）与 8 类边（`DEFINES` / `REFERENCES` / `CALLS` / `IMPORTS` / `INHERITS` / `CONTAINS` / `DEPENDS_ON` / `DECLARED_IN_MANIFEST`）。

#### Scenario: Schema 在 SQLite 中可验证
- **WHEN** 检查 SQLite 知识图的表/视图结构
- **THEN** 节点表的 `kind` 列 MUST 仅允许上述 5 类值；边表的 `kind` 列 MUST 仅允许上述 8 类值；插入非法 `kind` MUST 抛出 `IntegrityError`

#### Scenario: SCIP→SQLite 加载器处理 protobuf
- **WHEN** SCIP 索引器产出 `.scip` 文件
- **THEN** Graph Loader MUST 解析 SCIP protobuf；定义（`SymbolInformation`）转为 `DEFINES` 边；引用（`SymbolOccurrence` with role=1）转为 `REFERENCES` 边；调用关系转为 `CALLS` 边

### Requirement: KnowledgeGraphQueryAPI MUST 提供 4 类查询且返回带置信度

依据 `analysis/02` 第四节，`KnowledgeGraphQueryAPI` MUST 提供 4 个查询方法：`find_callers(symbol_id, depth)` / `find_file_impact(file_path)` / `find_dependencies(symbol_id)` / `get_module_api(module_id)`。每个方法 MUST 返回 `QueryResult` 结构（含 `answer` / `confidence` / `coverage_note` / `sources` 字段）。

#### Scenario: 4 类查询返回三字段结构
- **WHEN** 运行 `pytest tests/kg/test_queries.py`
- **THEN** 4 个查询方法的返回值 MUST 全部含 `answer`、`confidence`、`coverage_note` 三字段；`confidence` MUST 是 `Confidence` 枚举值（`HIGH` / `MEDIUM` / `LOW`）

#### Scenario: 置信度基于扫描覆盖率映射
- **WHEN** 知识图扫描覆盖率高（默认排除目录外的文件 100% 被索引）
- **THEN** `find_callers` 等查询返回 `confidence=HIGH`；当扫描覆盖率低（如 tree-sitter fallback 路径多）时 `confidence=MEDIUM` 或 `LOW`；映射规则 MUST 在代码中显式定义

#### Scenario: 来源标注满足"标注信息来源"约束
- **WHEN** 审查 `QueryResult.sources` 字段
- **THEN** 该字段 MUST 列出该查询结果的数据来源（如 `scip_index` / `tree_sitter_fallback` / `derived_view`），供代码资产管理员 Agent 引用

### Requirement: KG-MVP MUST 含准确性验证套件

KG-MVP MUST 含准确性验证套件。依据 `analysis/02` 第七节与 `dod.md` D0-6，准确性验证套件是 Dev-Phase 0 的硬性产出（非可选）。验证方法：构造 ground-truth（已知真实调用图）+ 计算召回率与精确率 + 把召回率映射到 `Confidence` 枚举。

#### Scenario: 验证套件可执行且产出量化指标
- **WHEN** 运行 `python -m sddp.kg.evaluate --gold tests/kg/golden.json`
- **THEN** 命令 MUST 产出 JSON 输出，含 `recall` 与 `precision` 数值字段；JSON MUST 含 `confidence_calibration` 子对象，记录召回率到 `Confidence` 的映射

#### Scenario: 召回率达 70% 阈值（D0-6 通过）
- **WHEN** 运行验证套件（Go 判定时）
- **THEN** 输出 JSON 的 `recall` 字段 MUST ≥ 0.70；低于此阈值触发 Dev-Phase 0 No-Go 条件 A（见 `no-go-rollback.md`），回归 KG 设计

#### Scenario: 验证套件作为回归基线
- **WHEN** 后续 KG 代码变更（KG-v1 等）
- **THEN** 验证套件 MUST 重新运行；recall/precision MUST 不退化（允许持平或提升）
