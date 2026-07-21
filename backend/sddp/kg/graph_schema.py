"""SQLite schema for the SDDP-PET knowledge graph.

Defines 5 node kinds and 8 edge kinds per analysis/02-code-knowledge-graph-design.md §四.
"""
from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Iterable

# 5 node kinds (analysis/02 §四)
NODE_KINDS = (
    "Repository",
    "File",
    "Symbol",
    "Module",
    "Package",
)

# 8 edge kinds (analysis/02 §四)
EDGE_KINDS = (
    "DEFINES",
    "REFERENCES",
    "CALLS",
    "IMPORTS",
    "INHERITS",
    "CONTAINS",
    "DEPENDS_ON",
    "DECLARED_IN_MANIFEST",
)

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS nodes (
    id           TEXT PRIMARY KEY,
    kind         TEXT NOT NULL CHECK (kind IN ({node_kinds})) ,
    name         TEXT NOT NULL,
    file_path    TEXT,
    line         INTEGER,
    scan_version INTEGER NOT NULL,
    extra        TEXT
);

CREATE TABLE IF NOT EXISTS edges (
    src_id       TEXT NOT NULL,
    dst_id       TEXT NOT NULL,
    kind         TEXT NOT NULL CHECK (kind IN ({edge_kinds})) ,
    scan_version INTEGER NOT NULL,
    line         INTEGER,
    PRIMARY KEY (src_id, dst_id, kind, scan_version)
);

CREATE TABLE IF NOT EXISTS scan_meta (
    scan_version   INTEGER PRIMARY KEY,
    created_at     TEXT NOT NULL,
    root_path      TEXT NOT NULL,
    languages      TEXT NOT NULL,
    coverage_stats TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_nodes_kind       ON nodes(kind);
CREATE INDEX IF NOT EXISTS idx_nodes_file_path  ON nodes(file_path);
CREATE INDEX IF NOT EXISTS idx_nodes_name       ON nodes(name);
CREATE INDEX IF NOT EXISTS idx_edges_src        ON edges(src_id);
CREATE INDEX IF NOT EXISTS idx_edges_dst        ON edges(dst_id);
CREATE INDEX IF NOT EXISTS idx_edges_kind       ON edges(kind);
CREATE INDEX IF NOT EXISTS idx_edges_src_kind   ON edges(src_id, kind);
CREATE INDEX IF NOT EXISTS idx_edges_dst_kind   ON edges(dst_id, kind);
""".format(
    node_kinds=", ".join("'%s'" % k for k in NODE_KINDS),
    edge_kinds=", ".join("'%s'" % k for k in EDGE_KINDS),
)


def init_db(db_path: str | Path) -> sqlite3.Connection:
    """Initialize the SQLite knowledge graph at db_path. Idempotent."""
    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA foreign_keys = ON;")
    conn.executescript(SCHEMA_SQL)
    conn.commit()
    return conn


def drop_all(conn: sqlite3.Connection) -> None:
    """Drop all KG tables (used by full re-scan)."""
    conn.executescript(
        "DROP TABLE IF EXISTS edges; DROP TABLE IF EXISTS nodes; DROP TABLE IF EXISTS scan_meta;"
    )
    conn.commit()


def validate_kinds(node_kinds: Iterable[str], edge_kinds: Iterable[str]) -> None:
    """Validate that all kinds are in the allowed sets. Raises ValueError on violation."""
    for k in node_kinds:
        if k not in NODE_KINDS:
            raise ValueError(f"Invalid node kind: {k!r}. Allowed: {NODE_KINDS}")
    for k in edge_kinds:
        if k not in EDGE_KINDS:
            raise ValueError(f"Invalid edge kind: {k!r}. Allowed: {EDGE_KINDS}")
