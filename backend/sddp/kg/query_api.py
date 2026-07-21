"""KnowledgeGraphQueryAPI: the sole entry point for code-asset-manager Agent.

Per analysis/02 §四, every query returns a QueryResult with answer + confidence +
coverage_note + sources. The 4 required queries:
  - find_callers(symbol_id, depth)   → Q1 影响面
  - find_file_impact(file_path)      → Q2 依赖方
  - find_dependencies(symbol_id)     → Q3 隐藏依赖
  - get_module_api(module_id)        → Q4 对外接口

Confidence is computed from scan coverage (analysis/02 §四 key design):
  - HIGH   when scanned coverage ≥ 90% of project files
  - MEDIUM when 70-90%
  - LOW    when <70% (or tree-sitter fallback used)
"""
from __future__ import annotations

import dataclasses
import json
import sqlite3
from enum import Enum
from pathlib import Path
from typing import Any


class Confidence(str, Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


@dataclasses.dataclass
class QueryResult:
    """Structured result for any KG query (analysis/02 §四)."""

    answer: dict[str, Any]
    confidence: Confidence
    coverage_note: str
    sources: list[str]

    def to_dict(self) -> dict[str, Any]:
        return {
            "answer": self.answer,
            "confidence": self.confidence.value,
            "coverage_note": self.coverage_note,
            "sources": self.sources,
        }


class KnowledgeGraphQueryAPI:
    """The sole entry point code-asset-manager Agent uses to query the knowledge graph.

    All methods return QueryResult with explicit confidence + coverage_note + sources
    so the calling agent can pass these through to downstream SDDP roles (architect
    MUST annotate confidence in delta-spec per analysis/02 §四).
    """

    def __init__(self, db_path: str | Path):
        self.db_path = str(db_path)
        self._conn: sqlite3.Connection | None = None

    # ---- connection management ----

    def _connect(self) -> sqlite3.Connection:
        if self._conn is None:
            self._conn = sqlite3.connect(self.db_path)
            self._conn.row_factory = sqlite3.Row
        return self._conn

    def close(self) -> None:
        if self._conn is not None:
            self._conn.close()
            self._conn = None

    # ---- coverage / confidence helpers ----

    def get_scan_coverage(self) -> dict[str, Any]:
        """Return coverage stats from the latest scan_version (analysis/02 §四 get_scan_coverage)."""
        conn = self._connect()
        cur = conn.cursor()
        cur.execute("SELECT * FROM scan_meta ORDER BY scan_version DESC LIMIT 1")
        row = cur.fetchone()
        if row is None:
            return {"scan_version": None, "coverage_stats": {}, "languages": []}
        return {
            "scan_version": row["scan_version"],
            "coverage_stats": json.loads(row["coverage_stats"]),
            "languages": row["languages"].split(",") if row["languages"] else [],
            "root_path": row["root_path"],
        }

    def _compute_confidence(self) -> tuple[Confidence, str]:
        """Compute confidence + coverage_note from latest scan meta."""
        cov = self.get_scan_coverage()
        stats = cov.get("coverage_stats", {})
        via = stats.get("via", "unknown")
        total = stats.get("total_files", 0)
        if total == 0:
            return Confidence.LOW, "Empty or missing scan; results may be empty."
        # Note: in Dev-Phase 0 MVP, parsed_files == total_files (tree-sitter parses all)
        # so coverage ratio is 1.0. The "via" determines confidence.
        if via == "scip-python":
            return Confidence.HIGH, f"SCIP indexed {total} files; static analysis covers explicit calls/imports."
        if via == "tree-sitter":
            return Confidence.MEDIUM, (
                f"tree-sitter fallback indexed {total} files; "
                "dynamic imports / reflection / eval NOT covered; results may miss hidden deps."
            )
        return Confidence.LOW, f"Unknown indexer (via={via}); coverage uncertain."

    # ---- Q1: 影响面 (callers of a symbol) ----

    def find_callers(self, symbol_id: str, depth: int = 1) -> QueryResult:
        """Q1: who calls this symbol? depth=1 direct callers; >1 transitive."""
        conn = self._connect()
        cur = conn.cursor()

        # Verify the symbol exists
        cur.execute("SELECT id, name, file_path FROM nodes WHERE id = ? AND kind = 'Symbol'", (symbol_id,))
        target = cur.fetchone()
        if target is None:
            confidence, note = self._compute_confidence()
            return QueryResult(
                answer={"symbol_id": symbol_id, "callers": [], "found": False},
                confidence=Confidence.LOW,
                coverage_note=f"Symbol {symbol_id} not in graph. {note}",
                sources=["sqlite:nodes"],
            )

        callers = self._collect_callers(symbol_id, depth)
        confidence, note = self._compute_confidence()
        return QueryResult(
            answer={
                "symbol_id": symbol_id,
                "symbol_name": target["name"],
                "file_path": target["file_path"],
                "callers": callers,
                "count": len(callers),
                "depth": depth,
                "found": True,
            },
            confidence=confidence,
            coverage_note=note,
            sources=["sqlite:edges:CALLS", "sqlite:edges:REFERENCES"],
        )

    def _collect_callers(self, symbol_id: str, depth: int) -> list[dict[str, Any]]:
        conn = self._connect()
        cur = conn.cursor()
        seen: set[str] = set()
        result: list[dict[str, Any]] = []
        frontier = [(symbol_id, 0)]
        while frontier:
            current, d = frontier.pop(0)
            if d >= depth:
                continue
            cur.execute(
                """
                SELECT n.id, n.name, n.file_path, n.line, e.kind, e.line AS edge_line
                FROM edges e
                JOIN nodes n ON n.id = e.src_id
                WHERE e.dst_id = ? AND e.kind IN ('CALLS', 'REFERENCES')
                """,
                (current,),
            )
            for row in cur.fetchall():
                if row["id"] in seen:
                    continue
                seen.add(row["id"])
                entry = {
                    "caller_symbol_id": row["id"],
                    "caller_name": row["name"],
                    "caller_file": row["file_path"],
                    "caller_line": row["line"],
                    "edge_kind": row["kind"],
                    "call_line": row["edge_line"],
                    "depth": d + 1,
                }
                result.append(entry)
                frontier.append((row["id"], d + 1))
        return result

    # ---- Q2: 依赖方 (files affected by modifying a file) ----

    def find_file_impact(self, file_path: str) -> QueryResult:
        """Q2: which files/modules would be impacted by modifying this file?"""
        conn = self._connect()
        cur = conn.cursor()
        # Normalize path
        target = str(Path(file_path))
        cur.execute("SELECT id FROM nodes WHERE kind = 'File' AND file_path = ?", (target,))
        file_row = cur.fetchone()
        if file_row is None:
            # Try suffix match
            cur.execute("SELECT id, file_path FROM nodes WHERE kind = 'File' AND file_path LIKE ?", (f"%{target}",))
            file_row = cur.fetchone()
            if file_row is None:
                confidence, note = self._compute_confidence()
                return QueryResult(
                    answer={"file_path": target, "impacted_files": [], "found": False},
                    confidence=Confidence.LOW,
                    coverage_note=f"File {target} not in graph. {note}",
                    sources=["sqlite:nodes"],
                )

        file_id = file_row["id"]
        # All symbols defined in this file (queried by file_path column, since the
        # File→Module→Symbol chain stores the symbol's file_path directly).
        cur.execute(
            "SELECT id AS sym_id, name AS sym_name FROM nodes WHERE kind = 'Symbol' AND file_path = ?",
            (target,),
        )
        symbols_in_file = [(r["sym_id"], r["sym_name"]) for r in cur.fetchall()]

        impacted: dict[str, dict[str, Any]] = {}
        for sym_id, sym_name in symbols_in_file:
            callers = self._collect_callers(sym_id, depth=1)
            for c in callers:
                cf = c["caller_file"]
                if cf is None or cf == target:
                    continue
                if cf not in impacted:
                    impacted[cf] = {"file_path": cf, "via_symbols": [], "count": 0}
                impacted[cf]["via_symbols"].append({"caller_symbol": c["caller_name"], "called_symbol": sym_name})
                impacted[cf]["count"] += 1

        confidence, note = self._compute_confidence()
        return QueryResult(
            answer={
                "file_path": target,
                "file_id": file_id,
                "symbols_defined": len(symbols_in_file),
                "impacted_files": list(impacted.values()),
                "impacted_count": len(impacted),
                "found": True,
            },
            confidence=confidence,
            coverage_note=note,
            sources=["sqlite:edges:CALLS", "sqlite:edges:REFERENCES", "sqlite:edges:CONTAINS"],
        )

    # ---- Q3: 隐藏依赖 (what this symbol depends on) ----

    def find_dependencies(self, symbol_id: str) -> QueryResult:
        """Q3: which symbols/modules does this symbol depend on (call/import)?"""
        conn = self._connect()
        cur = conn.cursor()

        cur.execute("SELECT id, name, file_path FROM nodes WHERE id = ? AND kind = 'Symbol'", (symbol_id,))
        target = cur.fetchone()
        if target is None:
            confidence, note = self._compute_confidence()
            return QueryResult(
                answer={"symbol_id": symbol_id, "dependencies": [], "found": False},
                confidence=Confidence.LOW,
                coverage_note=f"Symbol {symbol_id} not in graph. {note}",
                sources=["sqlite:nodes"],
            )

        cur.execute(
            """
            SELECT dst.id, dst.name, dst.kind, dst.file_path, e.kind AS edge_kind, e.line
            FROM edges e
            JOIN nodes dst ON dst.id = e.dst_id
            WHERE e.src_id = ? AND e.kind IN ('CALLS', 'REFERENCES', 'IMPORTS', 'INHERITS', 'DEPENDS_ON')
            """,
            (symbol_id,),
        )
        deps: list[dict[str, Any]] = []
        for row in cur.fetchall():
            deps.append(
                {
                    "dep_symbol_id": row["id"],
                    "dep_name": row["name"],
                    "dep_kind": row["kind"],
                    "dep_file": row["file_path"],
                    "edge_kind": row["edge_kind"],
                    "edge_line": row["line"],
                }
            )

        confidence, note = self._compute_confidence()
        return QueryResult(
            answer={
                "symbol_id": symbol_id,
                "symbol_name": target["name"],
                "file_path": target["file_path"],
                "dependencies": deps,
                "count": len(deps),
                "found": True,
            },
            confidence=confidence,
            coverage_note=note,
            sources=["sqlite:edges:CALLS", "sqlite:edges:IMPORTS", "sqlite:edges:INHERITS"],
        )

    # ---- Q4: 对外接口 (exported API of a module) ----

    def get_module_api(self, module_id: str) -> QueryResult:
        """Q4: what symbols does this module export (define)?"""
        conn = self._connect()
        cur = conn.cursor()

        cur.execute("SELECT id, name, file_path FROM nodes WHERE id = ? AND kind = 'Module'", (module_id,))
        target = cur.fetchone()
        if target is None:
            confidence, note = self._compute_confidence()
            return QueryResult(
                answer={"module_id": module_id, "exports": [], "found": False},
                confidence=Confidence.LOW,
                coverage_note=f"Module {module_id} not in graph. {note}",
                sources=["sqlite:nodes"],
            )

        cur.execute(
            """
            SELECT dst.id, dst.name, dst.file_path, dst.line
            FROM edges e
            JOIN nodes dst ON dst.id = e.dst_id
            WHERE e.src_id = ? AND e.kind = 'DEFINES' AND dst.kind = 'Symbol'
            """,
            (module_id,),
        )
        exports = [
            {"symbol_id": r["id"], "name": r["name"], "file_path": r["file_path"], "line": r["line"]}
            for r in cur.fetchall()
        ]
        confidence, note = self._compute_confidence()
        return QueryResult(
            answer={
                "module_id": module_id,
                "module_name": target["name"],
                "file_path": target["file_path"],
                "exports": exports,
                "count": len(exports),
                "found": True,
            },
            confidence=confidence,
            coverage_note=note,
            sources=["sqlite:edges:DEFINES"],
        )

    # ---- Q-extra: name lookup (Agent NL entry point) ----

    def lookup_symbol(self, name: str, fuzzy: bool = False) -> QueryResult:
        """Lookup symbols by name (analysis/02 §四 lookup_symbol). Used by Agent as NL→ID resolver."""
        conn = self._connect()
        cur = conn.cursor()
        if fuzzy:
            cur.execute(
                "SELECT id, name, file_path, line FROM nodes WHERE kind = 'Symbol' AND name LIKE ?",
                (f"%{name}%",),
            )
        else:
            cur.execute(
                "SELECT id, name, file_path, line FROM nodes WHERE kind = 'Symbol' AND name = ?",
                (name,),
            )
        matches = [
            {"symbol_id": r["id"], "name": r["name"], "file_path": r["file_path"], "line": r["line"]}
            for r in cur.fetchall()
        ]
        confidence, note = self._compute_confidence()
        return QueryResult(
            answer={"query_name": name, "fuzzy": fuzzy, "matches": matches, "count": len(matches)},
            confidence=confidence,
            coverage_note=note,
            sources=["sqlite:nodes:Symbol"],
        )
