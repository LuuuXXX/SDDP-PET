"""Tests: output_pydantic schema enforcement (D0-8)."""
from __future__ import annotations

import pytest
from pydantic import ValidationError

from sddp.schemas import (
    SCHEMA_REGISTRY,
    DeltaDesign,
    DeltaSpec,
    Proposal,
    to_json_schema,
)
from sddp.schemas.delta_spec import ImpactAnalysis


def test_proposal_validates_with_required_fields():
    """Valid proposal MUST validate."""
    p = Proposal(
        title="test",
        requirement_background="背景",
        core_objective="目标",
        expected_outputs=["a.md"],
        priority="P2",
        modules=["m1"],
        impact_scope="low",
        recommended_path="SDDP全流程",
        recommendation_reason="测试",
    )
    assert p.title == "test"


def test_proposal_rejects_missing_required_field():
    """Spec scenario: 不符合 schema 的输出被拒绝. Missing priority MUST raise ValidationError."""
    with pytest.raises(ValidationError):
        Proposal(  # type: ignore[call-arg]
            title="test",
            requirement_background="背景",
            core_objective="目标",
            expected_outputs=["a.md"],
            modules=["m1"],
            impact_scope="low",
            recommended_path="SDDP全流程",
            recommendation_reason="测试",
        )


def test_proposal_rejects_invalid_enum_value():
    """Invalid priority value MUST raise ValidationError."""
    with pytest.raises(ValidationError):
        Proposal(
            title="t",
            requirement_background="b",
            core_objective="o",
            expected_outputs=["x"],
            priority="INVALID",  # type: ignore[arg-type]
            modules=["m"],
            impact_scope="x",
            recommended_path="SDDP全流程",
            recommendation_reason="r",
        )


def test_delta_spec_requires_impact_with_kg_confidence():
    """Spec: delta_spec.impact MUST allow kg_confidence annotation."""
    ds = DeltaSpec(
        title="t",
        modules=["m"],
        files=["f"],
        impact=ImpactAnalysis(
            dependents=["d"],
            data_compatibility="no",
            kg_confidence="medium",
            kg_coverage_note="tree-sitter fallback",
        ),
    )
    assert ds.impact.kg_confidence == "medium"


def test_delta_design_validates_with_modules():
    """DeltaDesign MUST validate with modules list."""
    from sddp.schemas.delta_design import ModuleDivision
    dd = DeltaDesign(
        title="t",
        decisions=["d1"],
        data_flow="flow",
        modules=[ModuleDivision(module="m", responsibility="r")],
    )
    assert len(dd.modules) == 1


def test_schema_registry_has_3_main_documents():
    """Spec: 3 documents (proposal/delta_spec/delta_design) MUST be registered."""
    assert "proposal" in SCHEMA_REGISTRY
    assert "delta_spec" in SCHEMA_REGISTRY
    assert "delta_design" in SCHEMA_REGISTRY


def test_to_json_schema_exports_pydantic_schema():
    """Spec: schemas MUST export to JSON Schema."""
    schema = to_json_schema("proposal")
    assert isinstance(schema, dict)
    assert schema.get("type") == "object"
    assert "properties" in schema
    assert "title" in schema["properties"]
    assert "priority" in schema["properties"]


def test_unknown_schema_name_raises():
    with pytest.raises(KeyError):
        to_json_schema("nonexistent_schema")
