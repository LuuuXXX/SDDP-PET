"""Contract tests for KnowledgeGraphQueryAPI (D0-5).

Validates:
  - 4 query methods return QueryResult with required 3 fields
  - Confidence enum has HIGH/MEDIUM/LOW
  - Schema CHECK constraints reject invalid kinds (D0-5 + graph_schema)
"""
from __future__ import annotations
import pytest
import sqlite3
from pathlib import Path

from sddp.kg.graph_schema import EDGE_KINDS, NODE_KINDS, init_db
from sddp.kg.query_api import Confidence, KnowledgeGraphQueryAPI, QueryResult


FIXTURE_ROOT = Path(__file__).resolve().parents[1] / "fixtures" / "sample-python-project"


@pytest.fixture(scope="module")
def kg_db(tmp_path_factory):
    """Build a KG from the fixture project; module-scoped for speed."""
    db = tmp_path_factory.mktemp("kg") / "test.db"
    from sddp.kg.scan import scan_project
    summary = scan_project(FIXTURE_ROOT, db_path=db, prefer_scip=False)
    assert summary.get("total_symbols", 0) > 0, "scan produced empty graph"
    return db


@pytest.fixture
def api(kg_db):
    a = KnowledgeGraphQueryAPI(kg_db)
    yield a
    a.close()


def test_confidence_enum_has_three_levels():
    """Confidence MUST expose HIGH/MEDIUM/LOW (analysis/02 §四)."""
    assert Confidence.HIGH.value == "high"
    assert Confidence.MEDIUM.value == "medium"
    assert Confidence.LOW.value == "low"


def test_node_kinds_count_is_five():
    """Schema MUST have exactly the 5 specified node kinds."""
    assert set(NODE_KINDS) == {"Repository", "File", "Symbol", "Module", "Package"}


def test_edge_kinds_count_is_eight():
    """Schema MUST have exactly the 8 specified edge kinds."""
    assert set(EDGE_KINDS) == {
        "DEFINES", "REFERENCES", "CALLS", "IMPORTS", "INHERITS",
        "CONTAINS", "DEPENDS_ON", "DECLARED_IN_MANIFEST",
    }


def test_schema_rejects_invalid_node_kind(tmp_path):
    """INSERT with invalid node kind MUST raise IntegrityError."""
    db = tmp_path / "x.db"
    conn = init_db(db)
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            "INSERT INTO nodes(id, kind, name, scan_version) VALUES (?, ?, ?, ?)",
            ("x", "InvalidKind", "x", 1),
        )
    conn.close()


def test_schema_rejects_invalid_edge_kind(tmp_path):
    """INSERT with invalid edge kind MUST raise IntegrityError."""
    db = tmp_path / "x.db"
    conn = init_db(db)
    conn.execute("INSERT INTO nodes(id, kind, name, scan_version) VALUES ('a','File','a',1)")
    conn.execute("INSERT INTO nodes(id, kind, name, scan_version) VALUES ('b','File','b',1)")
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            "INSERT INTO edges(src_id, dst_id, kind, scan_version) VALUES (?, ?, ?, ?)",
            ("a", "b", "INVALID_EDGE", 1),
        )
    conn.close()


def test_query_result_dataclass_has_required_fields():
    """QueryResult MUST expose answer, confidence, coverage_note, sources."""
    r = QueryResult(answer={"x": 1}, confidence=Confidence.HIGH, coverage_note="ok", sources=["t"])
    assert hasattr(r, "answer")
    assert hasattr(r, "confidence")
    assert hasattr(r, "coverage_note")
    assert hasattr(r, "sources")
    assert hasattr(r, "to_dict")


def test_find_callers_returns_three_field_structure(api: KnowledgeGraphQueryAPI):
    """Q1: find_callers MUST return QueryResult with confidence + coverage_note + sources (D0-5)."""
    # Lookup 'add' symbol first
    lookup = api.lookup_symbol("add")
    assert lookup.answer["count"] >= 1, "fixture should have 'add' symbol"
    sym_id = lookup.answer["matches"][0]["symbol_id"]

    result = api.find_callers(sym_id, depth=1)
    assert isinstance(result, QueryResult)
    assert isinstance(result.confidence, Confidence)
    assert isinstance(result.coverage_note, str) and result.coverage_note
    assert isinstance(result.sources, list) and len(result.sources) > 0
    # 'add' is called from sum_squares, main, test_add → at least 3
    assert result.answer["count"] >= 3, f"expected ≥3 callers, got {result.answer['count']}"
    caller_names = {c["caller_name"] for c in result.answer["callers"]}
    assert "sum_squares" in caller_names
    assert "main" in caller_names


def test_find_file_impact_returns_three_field_structure(api: KnowledgeGraphQueryAPI):
    """Q2: find_file_impact MUST return QueryResult with required fields."""
    utils_path = str(FIXTURE_ROOT / "utils.py")
    result = api.find_file_impact(utils_path)
    assert isinstance(result.confidence, Confidence)
    assert result.coverage_note
    assert result.sources
    # utils.py is imported by calculator, main, api, test_sample
    assert result.answer["impacted_count"] >= 4, f"expected ≥4 impacted files, got {result.answer['impacted_count']}"


def test_find_dependencies_returns_three_field_structure(api: KnowledgeGraphQueryAPI):
    """Q3: find_dependencies MUST return QueryResult with required fields."""
    # 'square' depends on 'multiply'
    lookup = api.lookup_symbol("square")
    assert lookup.answer["count"] >= 1
    sym_id = lookup.answer["matches"][0]["symbol_id"]

    result = api.find_dependencies(sym_id)
    assert isinstance(result.confidence, Confidence)
    assert result.coverage_note
    assert result.sources
    dep_names = {d["dep_name"] for d in result.answer["dependencies"]}
    assert "multiply" in dep_names, f"square should depend on multiply; got {dep_names}"


def test_get_module_api_returns_three_field_structure(api: KnowledgeGraphQueryAPI):
    """Q4: get_module_api MUST return QueryResult with required fields."""
    # Lookup utils module via DB
    import sqlite3
    conn = sqlite3.connect(str(api.db_path))
    try:
        row = conn.execute("SELECT id FROM nodes WHERE kind='Module' AND name='utils' LIMIT 1").fetchone()
    finally:
        conn.close()
    assert row is not None, "utils module not found in graph"
    mod_id = row[0]

    result = api.get_module_api(mod_id)
    assert isinstance(result.confidence, Confidence)
    assert result.coverage_note
    assert result.sources
    export_names = {e["name"] for e in result.answer["exports"]}
    assert {"add", "multiply", "format_pair"}.issubset(export_names), f"got {export_names}"


def test_find_callers_unknown_symbol_returns_low_confidence(api: KnowledgeGraphQueryAPI):
    """Lookup of nonexistent symbol MUST return LOW confidence + found=False."""
    result = api.find_callers("nonexistent-symbol-id-xyz", depth=1)
    assert result.confidence == Confidence.LOW
    assert result.answer["found"] is False


def test_get_scan_coverage_returns_metadata(api: KnowledgeGraphQueryAPI):
    """get_scan_coverage MUST return scan_version + coverage_stats + languages."""
    cov = api.get_scan_coverage()
    assert cov["scan_version"] is not None
    assert "coverage_stats" in cov
    assert "languages" in cov
    assert "python" in cov["languages"]
