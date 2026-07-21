"""Pydantic model for SDDP delta-spec documents (D0-8).

Per SDDP design document §Phase 1 delta-spec format template.
"""
from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class InterfaceContract(BaseModel):
    """One entry in 接口契约 (新增接口 / 变更接口 / 废弃接口)."""

    model_config = ConfigDict(populate_by_name=True)

    name: str = Field(description="接口名")
    signature: str = Field(description="入参 → 出参描述")
    change_type: str = Field(description="新增 / 变更 / 废弃")
    deprecation_reason: str | None = Field(default=None)


class ImpactAnalysis(BaseModel):
    """影响面分析 (MUST include code-asset-manager confidence)."""

    model_config = ConfigDict(populate_by_name=True)

    dependents: list[str] = Field(description="受影响的下游模块/调用方")
    data_compatibility: str = Field(description="是否涉及数据迁移/格式变更")
    # REQUIRED per analysis/02 §四: confidence MUST be annotated when results come from KG
    kg_confidence: str | None = Field(
        default=None,
        description="知识图查询置信度（high/medium/low）。MUST 标注当影响面基于 KG 查询。",
    )
    kg_coverage_note: str | None = Field(default=None, description="知识图覆盖率说明")


class DeltaSpec(BaseModel):
    """SDDP delta-spec document. MUST validate against this schema (D0-8)."""

    model_config = ConfigDict(populate_by_name=True)

    title: str = Field(description="变更标题")

    # 变更范围
    modules: list[str] = Field(description="涉及模块列表")
    files: list[str] = Field(description="涉及文件预估列表")

    # 接口契约
    new_interfaces: list[InterfaceContract] = Field(default_factory=list, description="新增接口")
    changed_interfaces: list[InterfaceContract] = Field(default_factory=list, description="变更接口")
    deprecated_interfaces: list[InterfaceContract] = Field(default_factory=list, description="废弃接口")

    # 影响面分析
    impact: ImpactAnalysis = Field(description="影响面分析（含 KG 置信度）")

    # 约束条件
    constraints: list[str] = Field(default_factory=list, description="性能 / 安全 / 兼容约束")
