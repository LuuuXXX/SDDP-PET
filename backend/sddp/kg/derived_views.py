"""Derived views (analysis/02 §5.2 step 6).

For Dev-Phase 0 KG-MVP, derived views are computed *lazily* inside query_api.py methods
(find_callers walks reverse_call_graph; find_file_impact walks file_impact_set;
get_module_api walks module_public_api). This module provides:
  1. Explicit materialization helpers (used by tests + future optimization)
  2. The SQL CREATE VIEW statements for future materialization (KG-v1+)

Materializing at insert-time is a KG-v1 optimization (analysis/02 §八 分阶段交付).
"""
from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any

# SQL for future materialization (KG-v1). For Dev-Phase 0 MVP, these are not created
# by default; tests can opt-in via materialize_all_views().
DERIVED_VIEWS_SQL = {
    "reverse_call_graph": """
        CREATE VIEW IF NOT EXISTS reverse_call_graph AS
        SELECT
            e.dst_id AS target_symbol_id,
            e.src_id AS caller_symbol_id,
            n.name   AS caller_name,
            n.file_path AS caller_file,
            e.kind   AS edge_kind,
            e.line   AS call_line,
            e.scan_version
        FROM edges e
        JOIN nodes n ON n.id = e.src_id
        WHERE e.kind IN ('CALLS', 'REFERENCES')
          AND n.kind = 'Symbol'
    """,
    "file_impact_set": """
        CREATE VIEW IF NOT EXISTS file_impact_set AS
        SELECT
            target_file.file_path AS source_file,
            caller_file.file_path AS impacted_file,
            target_sym.name       AS via_symbol,
            caller_sym.name       AS caller_symbol,
            e.line                AS call_line,
            e.scan_version
        FROM edges e
        JOIN nodes target_sym ON target_sym.id = e.dst_id
        JOIN nodes target_file ON target_file.file_path = target_sym.file_path AND target_file.kind = 'File'
        JOIN nodes caller_sym ON caller_sym.id = e.src_id
        JOIN nodes caller_file ON caller_file.file_path = caller_sym.file_path AND caller_file.kind = 'File'
        WHERE e.kind IN ('CALLS', 'REFERENCES')
    """,
    "module_public_api": """
        CREATE VIEW IF NOT EXISTS module_public_api AS
        SELECT
            m.id     AS module_id,
            m.name   AS module_name,
            m.file_path,
            sym.id   AS symbol_id,
            sym.name AS symbol_name,
            sym.line,
            e.scan_version
        FROM edges e
        JOIN nodes m ON m.id = e.src_id AND m.kind = 'Module'
        JOIN nodes sym ON sym.id = e.dst_id AND sym.kind = 'Symbol'
        WHERE e.kind = 'DEFINES'
    """,
}


def materialize_all_views(db_path: str | Path) -> list[str]:
    """Create all 3 derived SQL views. Returns the list of created view names.

    Idempotent. For Dev-Phase 0 MVP, optional (lazy query path is the default).
    """
    conn = sqlite3.connect(str(db_path))
    try:
        created = []
        for name, sql in DERIVED_VIEWS_SQL.items():
            conn.execute(sql)
            created.append(name)
        conn.commit()
        return created
    finally:
        conn.close()


def query_reverse_call_graph(db_path: str | Path, target_symbol_id: str) -> list[dict[str, Any]]:
    """Explicit materialized-query form of reverse_call_graph (used by tests + future API)."""
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    try:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT n.id AS caller_symbol_id, n.name AS caller_name, n.file_path AS caller_file,
                   e.kind AS edge_kind, e.line AS call_line
            FROM edges e
            JOIN nodes n ON n.id = e.src_id AND n.kind = 'Symbol'
            WHERE e.dst_id = ? AND e.kind IN ('CALLS', 'REFERENCES')
            """,
            (target_symbol_id,),
        )
        return [dict(r) for r in cur.fetchall()]
    finally:
        conn.close()


def query_file_impact_set(db_path: str | Path, source_file_path: str) -> list[dict[str, Any]]:
    """Explicit materialized-query form of file_impact_set."""
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    try:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT DISTINCT caller_file.file_path AS impacted_file,
                            target_sym.name       AS via_symbol,
                            caller_sym.name       AS caller_symbol
            FROM edges e
            JOIN nodes target_sym ON target_sym.id = e.dst_id AND target_sym.kind = 'Symbol'
            JOIN nodes caller_sym ON caller_sym.id = e.src_id AND caller_sym.kind = 'Symbol'
            JOIN nodes caller_file ON caller_file.file_path = caller_sym.file_path AND caller_file.kind = 'File'
            WHERE e.kind IN ('CALLS', 'REFERENCES')
              AND target_sym.file_path = ?
            """,
            (source_file_path,),
        )
        return [dict(r) for r in cur.fetchall()]
    finally:
        conn.close()


def query_module_public_api(db_path: str | Path, module_id: str) -> list[dict[str, Any]]:
    """Explicit materialized-query form of module_public_api."""
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    try:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT sym.id AS symbol_id, sym.name AS symbol_name, sym.line, sym.file_path
            FROM edges e
            JOIN nodes sym ON sym.id = e.dst_id AND sym.kind = 'Symbol'
            WHERE e.src_id = ? AND e.kind = 'DEFINES'
            """,
            (module_id,),
        )
        return [dict(r) for r in cur.fetchall()]
    finally:
        conn.close()
