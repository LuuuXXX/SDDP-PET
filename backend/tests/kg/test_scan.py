"""Smoke test for the pre-scanner (D0-4).

Validates: `python -m sddp.kg.scan <path>` produces non-empty graph on a
≥10-file Python project.
"""
from __future__ import annotations
import json
import sqlite3
import subprocess
import sys
from pathlib import Path

import pytest

from sddp.kg.scan import scan_project

FIXTURE_ROOT = Path(__file__).resolve().parents[1] / "fixtures" / "sample-python-project"


def test_fixture_has_at_least_ten_files():
    """D0-4 prerequisite: fixture MUST be a ≥10-file project (incl. tests/config)."""
    py_files = list(FIXTURE_ROOT.rglob("*.py"))
    assert len(py_files) >= 10, f"fixture has only {len(py_files)} .py files; need ≥10"


def test_scan_project_returns_non_empty_graph(tmp_path):
    """scan_project MUST produce scan_version > 0 + >0 symbols + >0 refs."""
    db = tmp_path / "scan_test.db"
    summary = scan_project(FIXTURE_ROOT, db_path=db, prefer_scip=False)

    assert "error" not in summary, f"scan failed: {summary}"
    assert summary["scan_version"] >= 1
    assert summary["total_files"] >= 10
    assert summary["parsed_files"] >= 9  # at least the 9 source files (test_sample.py may parse but counts)
    assert summary["total_symbols"] > 0, "no symbols found"
    assert summary["total_refs"] > 0, "no references found"
    assert summary["via"] in {"scip-python", "tree-sitter"}


def test_scan_writes_scan_version_to_sqlite(tmp_path):
    """SQLite MUST have scan_meta row with scan_version (D0-4 + D0-2 KG)."""
    db = tmp_path / "scan_meta_test.db"
    scan_project(FIXTURE_ROOT, db_path=db, prefer_scip=False)

    conn = sqlite3.connect(str(db))
    try:
        rows = list(conn.execute("SELECT scan_version, created_at, languages, coverage_stats FROM scan_meta"))
        assert len(rows) >= 1, "scan_meta table empty"
        version, created_at, languages, coverage_stats = rows[-1]
        assert version >= 1
        assert created_at
        assert "python" in languages
        stats = json.loads(coverage_stats)
        assert stats.get("total_files", 0) > 0
        assert stats.get("total_symbols", 0) > 0
        # Symbol nodes
        sym_count = conn.execute("SELECT COUNT(*) FROM nodes WHERE kind='Symbol'").fetchone()[0]
        assert sym_count > 0
        # Edge kinds present
        edge_kinds = {r[0] for r in conn.execute("SELECT DISTINCT kind FROM edges")}
        assert "DEFINES" in edge_kinds
        assert "CONTAINS" in edge_kinds
        # At least one of CALLS/REFERENCES/IMPORTS present (tree-sitter should produce some)
        assert edge_kinds & {"CALLS", "REFERENCES", "IMPORTS", "INHERITS"}
    finally:
        conn.close()


def test_scan_cli_invocable_via_subprocess(tmp_path):
    """`python -m sddp.kg.scan` MUST be invocable as subprocess (D0-4 verification path)."""
    db = tmp_path / "cli_test.db"
    result = subprocess.run(
        [sys.executable, "-m", "sddp.kg.scan", str(FIXTURE_ROOT), "--db", str(db), "--no-scip", "--json"],
        capture_output=True, text=True, cwd=Path(__file__).resolve().parents[2],  # backend/
    )
    assert result.returncode == 0, f"scan CLI failed: stderr={result.stderr}"
    payload = json.loads(result.stdout)
    assert payload["scan_version"] >= 1
    assert payload["total_symbols"] > 0


def test_default_excludes_apply(tmp_path):
    """Default excludes (vendor/node_modules/.git/.venv/etc.) MUST be filtered out."""
    # Create a project with a vendor/ dir that should be excluded
    proj = tmp_path / "proj"
    proj.mkdir()
    (proj / "main.py").write_text("def main():\n    pass\n", encoding="utf-8")
    (proj / "pyproject.toml").write_text("[project]\nname='proj'\n", encoding="utf-8")
    vendor = proj / "vendor"
    vendor.mkdir()
    (vendor / "lib.py").write_text("def lib_func():\n    pass\n", encoding="utf-8")

    db = tmp_path / "excl.db"
    summary = scan_project(proj, db_path=db, prefer_scip=False)
    assert summary["total_files"] == 1, f"vendor/ should be excluded; got {summary['total_files']} files"

    conn = sqlite3.connect(str(db))
    try:
        # No symbol named lib_func
        rows = conn.execute("SELECT name FROM nodes WHERE name='lib_func'").fetchall()
        assert rows == [], "vendor/lib_func leaked through exclude filter"
    finally:
        conn.close()
