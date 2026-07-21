"""Tools exposing KnowledgeGraphQueryAPI to the code-asset-manager Agent.

Per analysis/02 §四: code-asset-manager Agent accesses KG ONLY through these tools.
Each tool wraps a KnowledgeGraphQueryAPI method and returns a structured result with
confidence + coverage_note.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from ..kg.query_api import KnowledgeGraphQueryAPI, QueryResult


class KGTools:
    """CrewAI tool wrapper around KnowledgeGraphQueryAPI.

    Usage:
        tools = KGTools(db_path="knowledge_graph.db")
        agent = Agent(tools=[tools.find_callers_tool, tools.find_file_impact_tool, ...])
    """

    def __init__(self, db_path: str | Path):
        self.api = KnowledgeGraphQueryAPI(db_path)
        self.db_path = str(db_path)

    def close(self) -> None:
        self.api.close()

    # ---- Tool 1: find_callers (Q1 影响面) ----

    def find_callers(self, symbol_name: str, depth: int = 1) -> dict[str, Any]:
        """Q1 影响面: find callers of a named symbol (depth=1 direct, >1 transitive)."""
        lookup = self.api.lookup_symbol(symbol_name)
        if not lookup.answer["matches"]:
            return lookup.to_dict()
        sym_id = lookup.answer["matches"][0]["symbol_id"]
        result = self.api.find_callers(sym_id, depth=depth)
        return result.to_dict()

    # ---- Tool 2: find_file_impact (Q2 依赖方) ----

    def find_file_impact(self, file_path: str) -> dict[str, Any]:
        """Q2 依赖方: which files would be impacted by modifying this file."""
        result = self.api.find_file_impact(file_path)
        return result.to_dict()

    # ---- Tool 3: find_dependencies (Q3 隐藏依赖) ----

    def find_dependencies(self, symbol_name: str) -> dict[str, Any]:
        """Q3 隐藏依赖: what does this symbol depend on."""
        lookup = self.api.lookup_symbol(symbol_name)
        if not lookup.answer["matches"]:
            return lookup.to_dict()
        sym_id = lookup.answer["matches"][0]["symbol_id"]
        result = self.api.find_dependencies(sym_id)
        return result.to_dict()

    # ---- Tool 4: get_module_api (Q4 对外接口) ----

    def get_module_api(self, module_name: str) -> dict[str, Any]:
        """Q4 对外接口: what symbols does this module export."""
        import sqlite3
        conn = sqlite3.connect(self.db_path)
        try:
            row = conn.execute(
                "SELECT id FROM nodes WHERE kind='Module' AND name=? ORDER BY scan_version DESC LIMIT 1",
                (module_name,),
            ).fetchone()
        finally:
            conn.close()
        if row is None:
            return {
                "answer": {"module_name": module_name, "exports": [], "found": False},
                "confidence": "low",
                "coverage_note": f"Module {module_name} not in graph",
                "sources": ["sqlite:nodes"],
            }
        result = self.api.get_module_api(row[0])
        return result.to_dict()

    def as_tool_list(self) -> list:
        """Return CrewAI-compatible tool wrappers.

        For Dev-Phase 0 MVP we expose the bound methods directly; CrewAI can wrap them
        via crewai.Tool(func=...) or use StructuredTool.from_function in Dev-Phase 1.
        """
        return [
            self.find_callers,
            self.find_file_impact,
            self.find_dependencies,
            self.get_module_api,
        ]
