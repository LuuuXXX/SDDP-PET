"""Pydantic model for SDDP proposal documents (D0-8).

Per SDDP design document §Phase 0 proposal format template + Dev-Phase 0 spec
engine-core requirement 3: Proposal MUST have these sections.
"""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class ResourceItem(BaseModel):
    """One row in 资源需求清单."""

    model_config = ConfigDict(populate_by_name=True)

    name: str = Field(description="资源名称")
    description: str = Field(description="资源描述")
    provider: str | None = Field(default=None, description="需谁提供（人工输入项）/ 来源（技术/数据依赖）")
    acquisition_method: str | None = Field(default=None, description="预期获取方式")
    ready_status: Literal["已就绪", "需人工提供", "待获取"] = Field(description="就绪状态")
    notes: str | None = Field(default=None)


class Proposal(BaseModel):
    """SDDP proposal document. MUST validate against this schema (D0-8)."""

    model_config = ConfigDict(populate_by_name=True)

    title: str = Field(description="需求标题")

    # 需求背景
    requirement_background: str = Field(description="用户原始需求描述")

    # 需求解析
    core_objective: str = Field(description="提炼后的核心目标")
    expected_outputs: list[str] = Field(description="期望的交付物列表")
    priority: Literal["P0", "P1", "P2", "P3"] = Field(description="优先级")

    # 变更范围预估
    modules: list[str] = Field(description="初步预估涉及模块")
    impact_scope: str = Field(description="初步预估影响范围")

    # 约束与风险
    technical_constraints: list[str] = Field(default_factory=list, description="已知技术限制")
    business_constraints: list[str] = Field(default_factory=list, description="业务规则/时间约束")
    risk_assessment: list[str] = Field(default_factory=list, description="初步风险识别")

    # 资源需求清单
    human_input_items: list[ResourceItem] = Field(default_factory=list, description="人工输入项")
    technical_dependency_items: list[ResourceItem] = Field(default_factory=list, description="技术依赖项")
    data_dependency_items: list[ResourceItem] = Field(default_factory=list, description="数据依赖项")

    # 资源就绪汇总
    ready_count: int = Field(default=0, description="已就绪数量")
    need_human_count: int = Field(default=0, description="需人工提供数量")
    pending_count: int = Field(default=0, description="待获取数量")

    # 流程建议
    recommended_path: Literal["SDDP全流程", "快速通道", "拒绝"] = Field(description="建议路径")
    recommendation_reason: str = Field(description="判定依据")

    # PCM（项目配置清单）
    pcm: str | None = Field(default=None, description="项目配置清单内容；无 PCM 时为 None")

    # Code-asset-manager context (added by 需求官)
    context_overview: dict | None = Field(
        default=None, description="代码资产管理员提供的上下文概览（含查询覆盖范围、依赖链路、现状基线摘要）"
    )
