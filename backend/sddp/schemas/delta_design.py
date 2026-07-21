"""Pydantic model for SDDP delta-design documents (D0-8).

Per SDDP design document §Phase 1 delta-design format template.
"""
from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class ModuleDivision(BaseModel):
    """One row in 模块划分 table."""

    model_config = ConfigDict(populate_by_name=True)

    module: str = Field(description="模块名")
    responsibility: str = Field(description="职责")
    dependencies: list[str] = Field(default_factory=list, description="依赖")


class DeltaDesign(BaseModel):
    """SDDP delta-design document. MUST validate against this schema (D0-8)."""

    model_config = ConfigDict(populate_by_name=True)

    title: str = Field(description="变更标题")

    # 架构决策
    decisions: list[str] = Field(description="决策内容及理由列表")

    # 数据流
    data_flow: str = Field(description="关键数据流向描述或图表")

    # 关键算法
    algorithms: list[str] = Field(default_factory=list, description="核心逻辑伪代码或流程描述")

    # 模块划分
    modules: list[ModuleDivision] = Field(description="模块划分表")

    # 异常处理
    exception_handling: list[str] = Field(default_factory=list, description="边界情况及处理策略")

    # 编码参照（PCM 无编码规范域时，实施师遵循此节）
    naming_convention: str | None = Field(default=None, description="命名约定")
    directory_structure: str | None = Field(default=None, description="目录组织约定")
    code_style: str | None = Field(default=None, description="代码风格参照")
    ci_checks: str | None = Field(default=None, description="PCM CI required checks 或默认 lint 规则")
