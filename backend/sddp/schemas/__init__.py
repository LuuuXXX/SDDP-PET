"""Schema registry + JSON Schema export (D0-8 + spec engine-core requirement 3)."""
from __future__ import annotations

from typing import Type

from pydantic import BaseModel

from .architecture_research import ArchitectureResearch, KGQueryCitation
from .delta_design import DeltaDesign, ModuleDivision
from .delta_spec import DeltaSpec, ImpactAnalysis, InterfaceContract
from .proposal import Proposal, ResourceItem

# Registry: model name → class
SCHEMA_REGISTRY: dict[str, Type[BaseModel]] = {
    "proposal": Proposal,
    "delta_spec": DeltaSpec,
    "delta_design": DeltaDesign,
    "architecture_research": ArchitectureResearch,
    # Supporting types
    "resource_item": ResourceItem,
    "interface_contract": InterfaceContract,
    "impact_analysis": ImpactAnalysis,
    "module_division": ModuleDivision,
    "kg_query_citation": KGQueryCitation,
}


def to_json_schema(model_name: str) -> dict:
    """Export a model's JSON Schema by name. Raises KeyError for unknown models."""
    if model_name not in SCHEMA_REGISTRY:
        raise KeyError(f"unknown model: {model_name!r}. Available: {list(SCHEMA_REGISTRY)}")
    return SCHEMA_REGISTRY[model_name].model_json_schema()


def to_all_json_schemas() -> dict[str, dict]:
    """Export all registered models' JSON Schemas."""
    return {name: cls.model_json_schema() for name, cls in SCHEMA_REGISTRY.items()}


__all__ = [
    "ArchitectureResearch",
    "DeltaDesign",
    "DeltaSpec",
    "KGQueryCitation",
    "ModuleDivision",
    "Proposal",
    "ResourceItem",
    "InterfaceContract",
    "ImpactAnalysis",
    "SCHEMA_REGISTRY",
    "to_all_json_schemas",
    "to_json_schema",
]
