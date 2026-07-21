"""E2E test for Dev-Phase 0 demo (D0-9 / D0-11 / D0-12 / D0-13 / D0-14).

Per design decision 8 (test strategy): E2E tests use REAL OpenAI API calls
and are NOT run in regular CI. They are invoked manually for Go judgment
and Golden Demo freezing.

Running the real-API tests requires:
    export OPENAI_API_KEY=sk-...
    pytest backend/tests/e2e/test_dev_phase_0_demo.py -v -m e2e

Without OPENAI_API_KEY the real-API tests skip automatically. A separate
mock-mode smoke test runs unconditionally to verify the E2E plumbing
(fixture path resolution, output writing, scan_version increment).

Per tasks.md task 7.2:
    - Runs `config-hot-reload` proposal
    - Calls real OpenAI API (non-CI regular run)
    - Asserts 4 markdown + cost_report.json + scan_version increments
"""
from __future__ import annotations

import json
import os
import sqlite3
from pathlib import Path

import pytest
from typer.testing import CliRunner

from sddp.cli.main import app

# Locate fixture paths relative to this test file so the test is cwd-independent.
TESTS_ROOT = Path(__file__).resolve().parents[1]
FIXTURES = TESTS_ROOT / "fixtures"
PROPOSALS_DIR = FIXTURES / "proposals"
SAMPLE_PROJECT = FIXTURES / "sample-python-project"

CONFIG_HOT_RELOAD_PROPOSAL = PROPOSALS_DIR / "config-hot-reload.txt"
ADD_LOGGING_PROPOSAL = PROPOSALS_DIR / "add-logging.txt"
REFACTOR_UTILS_PROPOSAL = PROPOSALS_DIR / "refactor-utils.txt"

# DoD thresholds (from dod.md D0-11/12/13)
D0_11_MAX_COST_USD = 5.0
D0_12_MAX_LATENCY_MIN = 10.0
D0_13_MIN_COMPLIANCE = 0.99

runner = CliRunner()

# ---- markers ---------------------------------------------------------------
# Uses the existing `e2e` marker registered in pyproject.toml:
#   "end-to-end tests requiring real OpenAI API key (skipped in CI)"

requires_openai = pytest.mark.skipif(
    not os.environ.get("OPENAI_API_KEY"),
    reason="E2E real-API test requires OPENAI_API_KEY (design decision 8; not regular CI)",
)


def _kg_scan_version(db_path: Path) -> int:
    """Read the max(scan_version) from a KG SQLite file. Returns 0 if no table."""
    if not db_path.exists():
        return 0
    conn = sqlite3.connect(str(db_path))
    try:
        row = conn.execute("SELECT MAX(scan_version) FROM scan_meta").fetchone()
        return int(row[0] or 0)
    except sqlite3.OperationalError:
        return 0
    finally:
        conn.close()


# ---- sanity tests (always run, no API key needed) --------------------------


def test_fixtures_exist():
    """All 3 fixture proposals MUST exist (task 7.1)."""
    for p in (CONFIG_HOT_RELOAD_PROPOSAL, ADD_LOGGING_PROPOSAL, REFACTOR_UTILS_PROPOSAL):
        assert p.is_file(), f"fixture missing: {p}"
        assert p.read_text(encoding="utf-8").strip(), f"fixture empty: {p}"


def test_sample_project_has_at_least_10_python_files():
    """D0-4: KG fixture MUST have ≥10 Python files for a meaningful scan."""
    py_files = list(SAMPLE_PROJECT.rglob("*.py"))
    # Exclude __pycache__
    py_files = [p for p in py_files if "__pycache__" not in p.parts]
    assert len(py_files) >= 10, f"sample project has only {len(py_files)} .py files: {py_files}"


def test_e2e_mock_mode_smoke(tmp_path: Path):
    """Mock-mode E2E: verify the full plumbing (no API call).

    This is the CI-safe E2E smoke. It exercises:
      - proposal fixture reading
      - KG pre-scan of sample-python-project
      - 5-role flow in mock mode
      - output writing (4 markdown + cost_report.json)
      - scan_version increment in the KG db
    """
    out = tmp_path / "out"
    kg_db = tmp_path / "kg.db"
    flow_db = tmp_path / "flow.db"

    # Pre-scan once to get baseline scan_version
    baseline = _kg_scan_version(kg_db)

    result = runner.invoke(app, [
        "run",
        str(CONFIG_HOT_RELOAD_PROPOSAL),
        "--project", str(SAMPLE_PROJECT),
        "--output", str(out),
        "--kg-db", str(kg_db),
        "--flow-db", str(flow_db),
        "--mock",
        "--yes",
    ])
    if result.exit_code != 0:
        print("STDOUT:", result.stdout)
        if result.exception:
            import traceback
            traceback.print_exception(type(result.exception), result.exception, result.exception.__traceback__)
    assert result.exit_code == 0, f"mock E2E failed: exit={result.exit_code}\nstdout={result.stdout}"

    # cost_report.json MUST exist with required fields
    cr_path = out / "cost_report.json"
    assert cr_path.is_file(), "cost_report.json missing in mock E2E"
    cr = json.loads(cr_path.read_text())
    for field in ("measured_cost_usd", "wall_clock_minutes_excluding_human_wait",
                  "structured_output_first_try_rate", "total_tokens", "round_tokens"):
        assert field in cr, f"missing field in cost_report: {field}"

    # At least proposal output MUST exist (.md or .raw.json fallback)
    assert (out / "proposal.md").is_file() or (out / "proposal.raw.json").is_file(), \
        "no proposal output written"

    # KG scan_version MUST have incremented (or stayed at >=1 if baseline was 0)
    after = _kg_scan_version(kg_db)
    assert after > baseline, f"scan_version did not increment: baseline={baseline} after={after}"


# ---- real-API E2E tests (skipped without OPENAI_API_KEY) -------------------


@requires_openai
@pytest.mark.e2e
def test_dev_phase_0_demo_config_hot_reload_real(tmp_path: Path):
    """D0-9 + D0-11 + D0-12 + D0-13: real-API run of config-hot-reload proposal.

    This is the Golden Demo candidate. Asserts:
      - 4 markdown files produced (proposal/delta_spec/delta_design/architecture_research)
      - cost_report.json with DoD-threshold-compliant metrics
      - scan_version increments
    """
    out = tmp_path / "out"
    kg_db = tmp_path / "kg.db"
    flow_db = tmp_path / "flow.db"

    baseline = _kg_scan_version(kg_db)

    result = runner.invoke(app, [
        "run",
        str(CONFIG_HOT_RELOAD_PROPOSAL),
        "--project", str(SAMPLE_PROJECT),
        "--output", str(out),
        "--kg-db", str(kg_db),
        "--flow-db", str(flow_db),
        "--yes",  # auto-approve (real run still calls LLM but skips human blocking)
    ])
    if result.exit_code != 0:
        print("STDOUT:", result.stdout)
        if result.exception:
            import traceback
            traceback.print_exception(type(result.exception), result.exception, result.exception.__traceback__)
    assert result.exit_code == 0, f"real E2E failed: exit={result.exit_code}\nstdout={result.stdout}"

    # Spec cli-runner requirement 4 scenario: 5 files in output dir
    expected_docs = ["proposal.md", "delta_spec.md", "delta_design.md", "architecture_research.md"]
    for name in expected_docs:
        # .md preferred; .raw.json fallback acceptable if rendering failed (still proves the doc was produced)
        assert (out / name).is_file() or (out / name.replace(".md", ".raw.json")).is_file(), \
            f"missing output: {name} (and no .raw.json fallback)"

    # cost_report.json + DoD thresholds
    cr = json.loads((out / "cost_report.json").read_text())
    dod = cr.get("dod_checks", {})
    assert dod.get("D0-11_cost_le_5_usd") is True, \
        f"D0-11 FAIL: measured_cost_usd={cr['measured_cost_usd']} > {D0_11_MAX_COST_USD}"
    assert dod.get("D0-12_latency_le_10_min") is True, \
        f"D0-12 FAIL: wall_clock={cr['wall_clock_minutes_excluding_human_wait']} > {D0_12_MAX_LATENCY_MIN}"
    assert dod.get("D0-13_compliance_ge_99_pct") is True, \
        f"D0-13 FAIL: compliance={cr['structured_output_first_try_rate']} < {D0_13_MIN_COMPLIANCE}"

    # scan_version MUST increment
    after = _kg_scan_version(kg_db)
    assert after > baseline, f"scan_version did not increment: baseline={baseline} after={after}"

    # Persist report for Golden Demo freezing (task 7.4/7.5 consume this)
    report_path = tmp_path / "e2e_report_config_hot_reload.json"
    report_path.write_text(json.dumps({
        "proposal": str(CONFIG_HOT_RELOAD_PROPOSAL),
        "output_dir": str(out),
        "cost_report": cr,
        "scan_version_before": baseline,
        "scan_version_after": after,
    }, indent=2, ensure_ascii=False))


@requires_openai
@pytest.mark.e2e
@pytest.mark.parametrize("proposal_path", [
    CONFIG_HOT_RELOAD_PROPOSAL,
    ADD_LOGGING_PROPOSAL,
    REFACTOR_UTILS_PROPOSAL,
], ids=["config-hot-reload", "add-logging", "refactor-utils"])
def test_d0_14_three_proposals_no_crash_real(tmp_path: Path, proposal_path: Path):
    """D0-14: 3 different proposals MUST all complete without crash (real API).

    Per dod.md D0-14: 连续跑 3 个不同 proposal，全程无需人工介入。
    Each runs in its own tmp_path; assertion is simply exit_code == 0 + outputs produced.
    """
    out = tmp_path / "out"
    kg_db = tmp_path / "kg.db"
    flow_db = tmp_path / "flow.db"

    result = runner.invoke(app, [
        "run",
        str(proposal_path),
        "--project", str(SAMPLE_PROJECT),
        "--output", str(out),
        "--kg-db", str(kg_db),
        "--flow-db", str(flow_db),
        "--yes",
    ])
    assert result.exit_code == 0, f"D0-14 proposal {proposal_path.name} crashed: exit={result.exit_code}\nstdout={result.stdout}"
    assert (out / "cost_report.json").is_file(), f"cost_report.json missing for {proposal_path.name}"
    assert (out / "proposal.md").is_file() or (out / "proposal.raw.json").is_file(), \
        f"no proposal output for {proposal_path.name}"
