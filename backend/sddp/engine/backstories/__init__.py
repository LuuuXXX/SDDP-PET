"""Backstory registry."""
from __future__ import annotations

from .architect import ARCHITECT_BACKSTORY
from .code_asset_manager import CODE_ASSET_MANAGER_BACKSTORY
from .executor import EXECUTOR_BACKSTORY
from .orchestrator import ORCHESTRATOR_BACKSTORY
from .requirement_officer import REQUIREMENT_OFFICER_BACKSTORY

BACKSTORIES: dict[str, str] = {
    "requirement_officer": REQUIREMENT_OFFICER_BACKSTORY,
    "orchestrator": ORCHESTRATOR_BACKSTORY,
    "architect": ARCHITECT_BACKSTORY,
    "executor": EXECUTOR_BACKSTORY,
    "code_asset_manager": CODE_ASSET_MANAGER_BACKSTORY,
}

__all__ = ["BACKSTORIES"]
