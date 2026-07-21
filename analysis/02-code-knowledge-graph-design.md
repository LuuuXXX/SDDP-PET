# G1: 代码知识图子系统设计

> 日期: 2026-07-20
> 状态: P0 缺口补齐
> 关联: 01-final-review.md G1; 00-sddp-pet-final.md 差距1
> 取代: 此前分析中"GitNexus/Graphify，自定义Python工具"的模糊表述（这两个名称不对应已知成熟项目，原表述等同于把核心子系统建立在虚构依赖上）

---

## 一、问题陈述

SDDP 全局约束原则要求"代码修改设计须先咨询代码资产管理员"，且"禁止假设—任何角色不得将未经代码库验证的假设作为决策依据"。这套原则的技术地基是：**一个能回答依赖方/影响面/隐藏依赖查询的代码知识图**。

此前分析把该子系统估为 2-3 天，且未定义 schema/查询接口/增量更新。本文件给出可落地的设计。

### 必须支撑的 4 类核心查询（来自 SDDP 设计文档）

| 查询 | SDDP 角色 | 用途 |
|------|----------|------|
| **Q1 影响面**: 符号 X 被哪些位置调用/引用？ | 架构师 | delta-spec 影响面分析 |
| **Q2 依赖方**: 修改文件 F 会影响哪些下游模块？ | 架构师/代码资产管理员 | 修改范围确认、隐藏依赖发现 |
| **Q3 隐藏依赖**: 符号 X 的实现依赖哪些其他符号/模块？ | 架构师 | 现状记录、约束提取 |
| **Q4 对外接口**: 模块 M 的对外 API 面？ | 架构师/验收师 | 接口契约定义/验证 |

---

## 二、工具选型（基于真实存在且成熟的项目）

放弃"自定义 Python 工具从零造轮子"路线。采用 **SCIP 为主 + tree-sitter 为辅** 的混合方案。

### 2.1 主干: SCIP (Sourcegraph Code Intelligence Protocol)

SCIP 是 LSIF 的继任者，是代码索引的业界事实标准：
- **定义**: protobuf 格式的代码 intelligence 数据交换协议
- **官方索引器覆盖 20+ 语言**: scip-python / scip-typescript / scip-rust / scip-java / scip-ruby / scip-cpp / scip-go / scip-php / scip-csharp / lsif-clang 等（多数由 Sourcegraph 官方或社区维护，活跃）
- **产出数据**: 定义(definition)、引用(reference)、悬停信息(hover/docstring)、符号层级关系、实现关系(implementation)
- **存储**: SCIP 索引文件本身是二进制 protobuf，可解析后导入图存储
- **许可证**: Apache-2.0（与 MIT 兼容）

**为何选 SCIP 而非从零解析**:
1. 多语言支持现成，不必为每门语言写解析器
2. 索引器经过生产验证（Sourcegraph 在用）
3. 解析层标准化，下游图存储与查询逻辑可复用
4. 增量索引有官方实践（按文件粒度 reindex）

### 2.2 辅助: tree-sitter

用于 SCIP 索引器不覆盖或质量不足的场景：
- 快速增量解析（文件保存触发局部重解析）
- SCIP 不提供的语法结构信息（如复杂控制流、宏展开后的结构）
- tree-sitter-stack-graphs（GitHub 名字解析）处理动态导入/重导出

### 2.3 否决的方案

| 方案 | 否决理由 |
|------|----------|
| Joern CPG | 面向安全分析(taint flow)，重型；语言覆盖偏 C/Java/JS/Python，对 Go/Rust 弱 |
| Semgrep | 模式匹配工具，非知识图；无法回答"被谁调用" |
| ctags/cscope | 经典但不精确（文本匹配，非语义）；无类型/无跨语言 |
| 从零自研 | 2-3 天估算是幻觉；多语言解析器单独就是数月工程 |
| LSP 运行时查询 | LSP 是编辑器实时协议，不适合批量/持久化查询；需长驻 language server 进程，资源重 |

---

## 三、知识图 Schema

存储于 SQLite（与 CrewAI @persist 一致，单文件可迁移）。采用属性图模型。

### 3.1 节点类型

| 节点类型 | 主键 | 关键属性 | 来源 |
|---------|------|---------|------|
| **Repository** | repo_id | root_path, vcs, default_branch, scan_version | 预扫描器 |
| **File** | file_id (repo_id+path) | path, language, sha256, loc, last_scanned_at, scip_indexed | 预扫描器 |
| **Symbol** | symbol_id (SCIP id) | name, kind(function/class/method/module/variable/typedef), signature, docstring, defined_range, visibility(public/private/protected), is_exported | SCIP |
| **Module** | module_id | qualified_name(如 `pkg.sub.mod`), language, entry_file | SCIP/tree-sitter |
| **Package** | package_id | name, version, ecosystem(pypi/npm/cargo/...), manifest_file | 依赖清单解析 |

### 3.2 边类型

| 边类型 | 方向 | 语义 | 来源 |
|--------|------|------|------|
| **DEFINES** | File → Symbol | 文件定义了符号 | SCIP definition |
| **REFERENCES** | Site(文件位置) → Symbol | 某位置引用了某符号 | SCIP reference |
| **CALLS** | Symbol → Symbol | 函数 A 调用函数 B | 由 REFERENCES + 符号类型派生 |
| **IMPORTS** | File/Module → Module | 文件/模块导入了模块 | SCIP + import 语法解析 |
| **INHERITS** | Symbol(class) → Symbol(class) | 类继承/实现 | SCIP implementation |
| **CONTAINS** | Symbol → Symbol | 符号嵌套(类包含方法) | SCIP 符号层级 |
| **DEPENDS_ON** | Module → Module | 派生: 模块级传递依赖（IMPORTS+CALLS 的模块级投影，预计算） | 图遍历物化 |
| **DECLARED_IN_MANIFEST** | Package → Module/Package | 声明依赖 | manifest 解析 |

### 3.3 派生视图（预计算，加速查询）

- **`reverse_call_graph`**: 符号 → 直接+间接调用者（物化到固定深度 3）
- **`file_impact_set`**: 文件 → 受影响文件集合（传递 IMPORTS，深度 5）
- **`module_public_api`**: 模块 → exported 符号集合（缓存）

---

## 四、查询接口（代码资产管理员 Agent 的访问层）

Agent 不直接写图查询，通过结构化查询函数访问。每个查询返回**带置信度的结果**。

```python
# backend/knowledge_graph/query_api.py（伪代码骨架）

from dataclasses import dataclass
from typing import Literal
from enum import Enum

class Confidence(Enum):
    HIGH = "high"      # SCIP 索引覆盖 + 静态可解析
    MEDIUM = "medium"  # 部分依赖动态分析推断
    LOW = "low"        # 受扫描覆盖率限制，结果可能不全

@dataclass
class QueryResult:
    answer: dict
    confidence: Confidence
    coverage_note: str   # 如"未扫描 vendor/ 目录，结果可能遗漏第三方调用"
    sources: list[str]   # 数据来源标注(供 Agent 引用，满足"标注信息来源"约束)

class KnowledgeGraphQueryAPI:
    """代码资产管理员 Agent 唯一访问入口。
    所有方法返回结构化结果 + 置信度 + 来源标注。
    Agent 须把 confidence 与 coverage_note 转达给查询方角色。"""

    def find_callers(self, symbol_id: str, depth: int = 1) -> QueryResult:
        """Q1 影响面: 谁调用了 symbol？depth=1 直接调用者，>1 传递。"""

    def find_file_impact(self, file_path: str) -> QueryResult:
        """Q2 依赖方: 修改该文件会影响哪些文件/模块？"""

    def find_dependencies(self, symbol_id: str) -> QueryResult:
        """Q3 隐藏依赖: symbol 实现依赖哪些其他 symbol/module？"""

    def get_module_api(self, module_id: str) -> QueryResult:
        """Q4 对外接口: 模块的 exported 符号集合。"""

    def lookup_symbol(self, name: str, fuzzy: bool = False) -> QueryResult:
        """按名称查符号（Agent 自然语言提问的入口）。"""

    def get_scan_coverage(self) -> dict:
        """返回当前知识图覆盖率: 已扫描文件数/总文件数、按语言分布、
        未覆盖目录(vendor/build/dist 等)。供 confidence 评估。"""
```

### 关键设计: 置信度贯穿

SDDP 要求"禁止假设"。但**任何静态分析都无法 100% 覆盖真实代码库**（动态导入、反射、eval、生成代码、宏）。因此知识图不承诺"权威"，而承诺"**带置信度的权威**"：
- 每个查询结果携带 `confidence` 与 `coverage_note`
- 代码资产管理员 Agent 须把置信度转达给架构师等查询方
- 架构师在 delta-spec 中须标注"影响面分析基于知识图查询，置信度=中"
- 这把 G1 从"伪权威风险"转化为"可管理的已知不确定性"（对应 01-review G12）

---

## 五、预扫描器架构

### 5.1 组件

```
┌─────────────────────────────────────────────────────────┐
│                   PreScanner (系统组件)                   │
│                                                          │
│  ┌──────────┐   ┌──────────────┐   ┌─────────────────┐  │
│  │ Manifest │──▶│ SCIP Indexer │──▶│ Graph Loader    │  │
│  │ Detector │   │ (per-lang)   │   │ (SCIP→SQLite)   │  │
│  │          │   │              │   │                 │  │
│  │ 识别项目 │   │ 调用 scip-*  │   │ 解析 protobuf  │  │
│  │ 语言/依赖│   │ 索引器       │   │ 写入节点/边     │  │
│  └──────────┘   └──────────────┘   └─────────────────┘  │
│                        │                                 │
│                        ▼                                 │
│  ┌──────────────────────────────────────────────────┐   │
│  │  tree-sitter Fallback (SCIP 未覆盖/增量)         │   │
│  └──────────────────────────────────────────────────┘   │
│                        │                                 │
│                        ▼                                 │
│  ┌──────────────────────────────────────────────────┐   │
│  │  Derived View Materializer (reverse graph 等)    │   │
│  └──────────────────────────────────────────────────┘   │
│                        │                                 │
│                        ▼                                 │
│                 SQLite Knowledge Graph                   │
└─────────────────────────────────────────────────────────┘
```

### 5.2 扫描流程

1. **Manifest 探测**: 识别项目语言（pyproject.toml/package.json/Cargo.toml/go.mod/pom.xml...），确定用哪些 SCIP 索引器
2. **排除规则**: 默认排除 `vendor/ node_modules/ dist/ build/ .git/`，可由 PCM 配置覆盖
3. **SCIP 索引**: 调用对应语言索引器，产出 `.scip` 文件
4. **Graph 加载**: 解析 SCIP protobuf → 写入 SQLite 节点/边
5. **tree-sitter 补充**: 对 SCIP 不覆盖的语法结构补充解析
6. **派生物化**: 计算 reverse_call_graph / file_impact_set / module_public_api
7. **覆盖率统计**: 写入 scan_version 元数据

### 5.3 增量更新（实施师改代码后）

触发: 实施师产出"变更文件清单"（SDDP Phase 2 输出）。
流程:
1. 对变更文件重新跑 SCIP 索引（文件粒度）
2. diff 新旧索引，得到: 新增/删除/变更的符号与引用
3. 更新 SQLite: 删除旧定义/引用 → 插入新定义/引用
4. 局部重算受影响派生视图（仅涉及变更符号的 reverse graph）
5. 更新 scan_version，代码资产管理员可向架构师报告"本轮变更影响面"

---

## 六、本地模式 vs 远程模式

| 维度 | 本地模式 | 远程模式 |
|------|---------|---------|
| 预扫描器运行位置 | Windows 本机 | Linux 服务器 |
| SCIP 索引器安装 | 本机需各语言工具链 | 服务器预装 |
| 知识图存储 | 本机 SQLite | 远程 SQLite |
| Agent 查询 | 直连 SQLite | 通过 SSH RPC `query_kg` 指令 |
| 回传前端的内容 | 全量可查 | 查询结果摘要回传(供 UI 显示)，全量留在服务器 |
| 大型仓库性能 | 受本机算力限制 | 服务器更强 |

远程模式查询接口（扩展现有 WebSocket RPC）:
```
RPC: query_kg { message_id, query_type, params }
响应: kg_result { message_id, answer, confidence, coverage_note, sources }
```

---

## 七、准确性验证（解决 01-review G15 中的"无 ground-truth"问题）

知识图的"正确性"必须有可度量验证，否则"权威性"是空话。

### 验证方法

1. **Ground-truth 构造**: 选 N 个开源项目（已有完整测试套件的），用其测试调用关系作为"已知真实调用图"的代理
2. **指标**:
   - 召回率: 知识图找到的真实调用占全部真实调用的比例
   - 精确率: 知识图报告的调用中真实存在的比例
   - 影响面准确率: find_file_impact 报告的受影响文件 vs 实际改该文件后测试失败涉及的文件
3. **置信度校准**: 把实测召回率映射到 Confidence 枚举（如召回率>90%=HIGH，70-90%=MEDIUM，<70%=LOW）
4. **回归测试**: 每次知识图代码变更，跑验证套件确保指标不退化

### 验证套件纳入 Dev-Phase 0

这是 Phase 0 的硬性产出（不是可选）。无验证套件的知识图不可用于对抗/质量关卡，因为架构师会基于不可靠数据做决策。

---

## 八、工期重估（取代"2-3 天"）

| 模块 | 工期 | 说明 |
|------|------|------|
| Manifest 探测 + 语言识别 | 1-2 天 | 多语言项目探测 |
| SCIP 索引器集成（3 种主语言起步: Python/TS/Go） | 3-4 天 | 每语言 1 天调通 |
| SQLite 图存储 + SCIP 加载器 | 3-4 天 | schema + protobuf 解析 + 批量写入 |
| tree-sitter fallback | 2-3 天 | 按需补充 |
| 派生视图物化(reverse/impact/api) | 2-3 天 | 图遍历 + 缓存 |
| 查询 API（4 类查询 + 置信度） | 3-4 天 | 含文档 |
| Agent 查询集成（代码资产管理员调用层） | 2-3 天 | backstory + 工具封装 |
| 增量更新 | 2-3 天 | diff + 局部重算 |
| 准确性验证套件 | 3-4 天 | ground-truth + 指标 + 校准 |
| 多语言扩展测试 + 边界场景 | 2-3 天 | |
| **合计** | **23-33 天 ≈ 3-4.5 周** | |

**与原"2-3 天"的差异**: 原估算只覆盖了"扫一下文件树生成 JSON"，未包含图存储、查询引擎、置信度、增量更新、验证。这些才是 SDDP 真正需要的部分。

### 分阶段交付（避免成为 Phase 0 的长阻塞）

| 子阶段 | 范围 | 可用性 |
|--------|------|--------|
| KG-MVP | 单语言(Python) + 4 类查询 + 静态置信度 + 无增量 | 够 Phase 0 CLI 验证用 |
| KG-v1 | + 增量更新 + 2 种语言 + 验证套件 | 够 Dev-Phase 1 桌宠联调 |
| KG-v2 | + 多语言 + 远程模式 + 动态置信度校准 | 生产级 |

KG-MVP 约 12-15 天（2-2.5 周），可作为 Phase 0 内部的并行子项目，不阻塞其他模块的关键路径。

---

## 九、风险与缓解

| 风险 | 缓解 |
|------|------|
| SCIP 索引器对某些语言/框架质量不足 | tree-sitter fallback + 置信度暴露给上层 |
| 大型仓库索引耗时（10万+文件） | 远程模式 + 增量索引 + 排除规则 |
| 动态语言(Python/JS)的隐式依赖查不全 | 置信度标注 LOW + 覆盖率提示 + 不假装权威 |
| 增量更新遗漏导致知识图陈旧 | scan_version 比对 + 实施师变更清单强制触发 |
| SCIP 索引器版本变动破坏兼容 | 锁定索引器版本 + protobuf schema 兼容性测试 |

---

## 十、对 SDDP 设计文档的建议修订

建议在 SDDP 设计文档"代码资产管理员"角色章节补充:
1. 明确知识图技术栈为 SCIP + tree-sitter（取代"GitNexus/Graphify"）
2. 明确"权威性"是带置信度的（取代"唯一权威代码知识来源"的绝对表述）
3. 增加全局约束: "架构师引用知识图查询结果时，须在 delta-spec/delta-design 中标注查询置信度"

这些修订在后续 `00-sddp-pet-final.md` 更新中体现。
