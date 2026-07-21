"""Pydantic model for architecture research reports.

Produced by the Architect role after consulting the code-asset-manager (analysis/02
mandates confidence + coverage_note be propagated through).
"""
from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class KGQueryCitation(BaseModel):
    """One knowledge-graph query cited in the research report."""

    model_config = ConfigDict(populate_by_name=True)

    query_method: str = Field(description="find_callers / find_file_impact / find_dependencies / get_module_api")
    query_args: dict = Field(description="查询参数")
    answer_summary: str = Field(description="查询结果摘要")
    confidence: str = Field(description="high / medium / low")
    coverage_note: str = Field(description="覆盖率说明（来自 QueryResult）")


class ArchitectureResearch(BaseModel):
    """Architecture research report. Per analysis/02 §四, MUST cite KG queries with confidence."""

    model_config = ConfigDict(populate_by_name=True)

    title: str = Field(description="研究主题")
    methodology: str = Field(description="研究方法论摘要")

    # 现状记录
    current_state: str = Field(description="代码库现状基线摘要")

    # 依赖追踪 / 约束提取
    dependency_chain: list[str] = Field(default_factory=list, description="依赖链路")
    extracted_constraints: list[str] = Field(default_factory=list, description="约束条件")

    # 知识图查询引用（REQUIRED）
    kg_citations: list[KGQueryCitation] = Field(
        default_factory=list,
        description="本报告所基于的知识图查询列表；每条 MUST 含 confidence。",
    )

    # PCM 架构决策引用
    pcm_adr_references: list[str] = Field(default_factory=list, description="引用的 PCM ADR 路径")
