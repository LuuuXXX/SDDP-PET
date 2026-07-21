"""Tests for sddp CLI (D0-9)."""
from __future__ import annotations

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from sddp.cli import flow_state
from sddp.cli.feedback_adapter import CLIHumanFeedbackAdapter, FeedbackResult, prompt_user
from sddp.cli.main import app

runner = CliRunner()


def test_sddp_help_lists_run_command():
    """Spec scenario: sddp --help shows run subcommand."""
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "run" in result.stdout
    assert "scan" in result.stdout
    assert "flows" in result.stdout


def test_sddp_run_help_shows_options():
    """Spec scenario: sddp run accepts <proposal> positional + --project + --output + --resume."""
    result = runner.invoke(app, ["run", "--help"])
    assert result.exit_code == 0
    assert "--project" in result.stdout
    assert "--output" in result.stdout
    assert "--resume" in result.stdout
    assert "--mock" in result.stdout


def test_sddp_run_in_mock_mode_produces_outputs(tmp_path: Path):
    """Spec: end-to-end CLI in mock mode writes 4 markdown files + cost_report.json."""
    out = tmp_path / "out"
    kg_db = tmp_path / "kg.db"
    flow_db = tmp_path / "flow.db"
    project_fixture = tmp_path / "proj"
    project_fixture.mkdir()
    (project_fixture / "mod.py").write_text("def f():\n    pass\n", encoding="utf-8")

    result = runner.invoke(app, [
        "run",
        "给这个 Python 项目加一个配置热重载功能",
        "--project", str(project_fixture),
        "--output", str(out),
        "--kg-db", str(kg_db),
        "--flow-db", str(flow_db),
        "--mock",
        "--yes",  # auto-approve (mock mode also auto-approves)
    ])
    if result.exit_code != 0:
        print("STDOUT:", result.stdout)
        print("EXC:", result.exception)
        import traceback
        traceback.print_exception(type(result.exception), result.exception, result.exception.__traceback__)
    assert result.exit_code == 0, f"CLI failed: {result.stdout}\nexc={result.exception}"

    # cost_report.json MUST exist
    assert (out / "cost_report.json").is_file(), "cost_report.json missing"
    cr = json.loads((out / "cost_report.json").read_text())
    for field in ["measured_cost_usd", "wall_clock_minutes_excluding_human_wait",
                  "structured_output_first_try_rate", "total_tokens", "round_tokens"]:
        assert field in cr, f"missing field in cost_report: {field}"

    # proposal output MUST exist (either as .md or .raw.json)
    assert (out / "proposal.md").is_file() or (out / "proposal.raw.json").is_file()


def test_resume_records_flow_state(tmp_path: Path):
    """Spec: interrupted flows MUST be resumable via flow_state."""
    flow_db = tmp_path / "flow.db"
    flow_state.create_flow_meta("test-flow-id", {"requirement": "x"}, db_path=flow_db)
    flow_state.save_state("test-flow-id", "step-1", {"value": 1}, db_path=flow_db)
    flow_state.update_flow_status("test-flow-id", "paused", db_path=flow_db)

    pending = flow_state.list_pending_flows(db_path=flow_db)
    assert len(pending) >= 1
    assert pending[0]["flow_id"] == "test-flow-id"
    assert pending[0]["status"] == "paused"

    loaded = flow_state.load_state("test-flow-id", db_path=flow_db)
    assert loaded == {"value": 1}


def test_flow_state_idempotent_overwrite(tmp_path: Path):
    """Same (flow_id, step) write MUST overwrite (not duplicate)."""
    flow_db = tmp_path / "flow.db"
    flow_state.save_state("f1", "s1", {"v": 1}, db_path=flow_db)
    flow_state.save_state("f1", "s1", {"v": 2}, db_path=flow_db)
    loaded = flow_state.load_state("f1", "s1", db_path=flow_db)
    assert loaded == {"v": 2}
    steps = flow_state.list_steps("f1", db_path=flow_db)
    assert steps == ["s1"]


# ---- FeedbackAdapter tests ----


def test_feedback_adapter_auto_approve():
    """Spec: --yes (or mock mode) MUST auto-approve without prompting."""
    adapter = CLIHumanFeedbackAdapter(auto_approve=True)
    assert adapter("requirement_confirmation", {"x": 1}) is True
    assert adapter("design_confirmation", {"y": 2}) is True
    assert len(adapter.history) == 2
    assert all(r.approved for r in adapter.history)


def test_feedback_adapter_prompt_yes(monkeypatch):
    """User typing 'y' MUST approve."""
    inputs = iter(["y"])
    adapter = CLIHumanFeedbackAdapter(
        prompt_fn=lambda _: next(inputs),
        output_fn=lambda *_: None,
    )
    assert adapter("requirement_confirmation", {"x": 1}) is True


def test_feedback_adapter_prompt_no_aborts(monkeypatch):
    """User typing 'n' MUST reject (flow aborts)."""
    inputs = iter(["n"])
    adapter = CLIHumanFeedbackAdapter(
        prompt_fn=lambda _: next(inputs),
        output_fn=lambda *_: None,
    )
    assert adapter("requirement_confirmation", {"x": 1}) is False


def test_feedback_adapter_invalid_then_yes():
    """Invalid input MUST re-prompt."""
    inputs = iter(["invalid", "?", "y"])
    adapter = CLIHumanFeedbackAdapter(
        prompt_fn=lambda _: next(inputs),
        output_fn=lambda *_: None,
    )
    assert adapter("requirement_confirmation", {"x": 1}) is True


def test_feedback_adapter_edit_returns_comment():
    """User typing 'e' MUST return approved + comment."""
    inputs = iter(["e", "minor edit"])
    adapter = CLIHumanFeedbackAdapter(
        prompt_fn=lambda _: next(inputs),
        output_fn=lambda *_: None,
    )
    assert adapter("design_confirmation", {"y": 1}) is True
    assert adapter.history[-1].comment == "minor edit"
