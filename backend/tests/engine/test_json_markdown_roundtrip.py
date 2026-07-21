"""Tests: JSON ↔ Markdown renderer (analysis/00 §10 模块 7)."""
from __future__ import annotations

import pytest
from pydantic import BaseModel

from sddp.schemas import (
    ArchitectureResearch,
    DeltaDesign,
    DeltaSpec,
    Proposal,
)
from sddp.schemas.delta_design import ModuleDivision
from sddp.schemas.delta_spec import ImpactAnalysis
from sddp.schemas.renderer import (
    _parse_proposal_markdown,
    from_markdown,
    to_markdown,
)


def _make_proposal() -> Proposal:
    return Proposal(
        title="测试 Proposal",
        requirement_background="需求背景描述",
        core_objective="核心目标 X",
        expected_outputs=["out.md", "code.py"],
        priority="P1",
        modules=["m1", "m2"],
        impact_scope="中等",
        technical_constraints=["tc1"],
        business_constraints=["bc1"],
        risk_assessment=["r1"],
        recommended_path="SDDP全流程",
        recommendation_reason="因为复杂",
    )


def _make_delta_spec() -> DeltaSpec:
    return DeltaSpec(
        title="测试 Spec",
        modules=["m1"],
        files=["a.py"],
        new_interfaces=[],
        impact=ImpactAnalysis(
            dependents=["d1"],
            data_compatibility="无",
            kg_confidence="high",
            kg_coverage_note="SCIP indexed 10 files",
        ),
    )


def _make_delta_design() -> DeltaDesign:
    return DeltaDesign(
        title="测试 Design",
        decisions=["d1"],
        data_flow="A → B",
        modules=[ModuleDivision(module="m", responsibility="r", dependencies=["d"])],
    )


def test_to_markdown_proposal_has_required_sections():
    """Spec scenario: Markdown 输出符合 SDDP 模板."""
    md = to_markdown(_make_proposal())
    assert "# Proposal:" in md
    for section in ["## 需求背景", "## 需求解析", "## 变更范围预估", "## 约束与风险",
                    "## 资源需求清单", "## 资源就绪汇总", "## 流程建议", "## 项目配置清单(PCM)"]:
        assert section in md, f"missing section {section!r}"


def test_to_markdown_delta_spec_has_kg_confidence():
    """Spec: delta_spec Markdown MUST surface kg_confidence."""
    md = to_markdown(_make_delta_spec())
    assert "# Delta-Spec:" in md
    assert "## 影响面分析" in md
    assert "high" in md  # kg_confidence value
    assert "SCIP indexed" in md  # coverage note


def test_to_markdown_delta_design_has_module_table():
    """Spec: delta_design Markdown MUST include module table."""
    md = to_markdown(_make_delta_design())
    assert "# Delta-Design:" in md
    assert "## 模块划分" in md
    assert "| 模块 | 职责 | 依赖 |" in md
    assert "m" in md


def test_to_markdown_unknown_model_raises():
    class Foo(BaseModel):
        x: int

    with pytest.raises(TypeError):
        to_markdown(Foo(x=1))


def test_from_markdown_proposal_returns_model():
    """Spec scenario: 双向转换. Markdown → Proposal."""
    md = to_markdown(_make_proposal())
    parsed = from_markdown(md, Proposal)
    assert isinstance(parsed, Proposal)
    assert parsed.title == "测试 Proposal"
    assert parsed.priority in {"P0", "P1", "P2", "P3"}


def test_from_markdown_delta_spec_returns_model():
    md = to_markdown(_make_delta_spec())
    parsed = from_markdown(md, DeltaSpec)
    assert isinstance(parsed, DeltaSpec)
    assert parsed.impact.kg_confidence in {"high", "medium", "low", None}


def test_from_markdown_unknown_model_raises():
    class Foo(BaseModel):
        x: int

    with pytest.raises(TypeError):
        from_markdown("anything", Foo)


def test_architecture_research_to_markdown_includes_citations():
    from sddp.schemas.architecture_research import KGQueryCitation
    ar = ArchitectureResearch(
        title="t",
        methodology="m",
        current_state="cs",
        kg_citations=[
            KGQueryCitation(
                query_method="find_callers",
                query_args={"symbol_name": "foo"},
                answer_summary="3 callers",
                confidence="high",
                coverage_note="ok",
            )
        ],
    )
    md = to_markdown(ar)
    assert "find_callers" in md
    assert "**high**" in md
