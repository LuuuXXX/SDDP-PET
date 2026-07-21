"""Tests for sddp/observability/metrics_recorder.py (D1-14)."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from sddp.engine.cost_meter import CostMeter
from sddp.observability.metrics_recorder import (
    record_flow_metrics,
    _default_metrics_path,
)


def _meter_with_calls() -> CostMeter:
    """Build a CostMeter that has recorded 3 calls across 2 agents."""
    import time
    m = CostMeter()
    m._start_time = time.monotonic() - 5.0  # pretend flow took ~5s wall
    m.record_call(
        agent="requirement_officer", model="deepseek-chat",
        prompt_tokens=200, completion_tokens=50, structured_output_first_try=True,
    )
    m.record_call(
        agent="architect", model="deepseek-chat",
        prompt_tokens=300, completion_tokens=100, structured_output_first_try=True,
    )
    m.record_call(
        agent="architect", model="deepseek-chat",
        prompt_tokens=400, completion_tokens=200, structured_output_first_try=False,
    )
    return m


def test_record_appends_to_metrics_json(tmp_path: Path):
    """Spec D1-14 Scenario: 跑一个流程后 metrics.json 含 4 字段非空数值."""
    metrics_path = tmp_path / "metrics.json"
    m = _meter_with_calls()

    record = record_flow_metrics(
        flow_id="fid-1", status="completed", cost_meter=m, metrics_path=metrics_path,
    )

    # File created
    assert metrics_path.exists()
    lines = metrics_path.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 1

    parsed = json.loads(lines[0])
    assert parsed == record  # what we returned is what we wrote

    # All 4 metric fields present and non-empty
    assert parsed["flow_time_seconds"] > 0
    assert isinstance(parsed["agent_latency_seconds"], dict) and len(parsed["agent_latency_seconds"]) > 0
    assert parsed["token_consumption_rate"] >= 0
    assert 0.0 <= parsed["error_rate"] <= 1.0

    # Envelope fields
    assert parsed["flow_id"] == "fid-1"
    assert parsed["status"] == "completed"
    assert "timestamp" in parsed


def test_multiple_flows_append_not_overwrite(tmp_path: Path):
    """Spec: metrics.json is append-only JSON Lines."""
    metrics_path = tmp_path / "metrics.json"
    m = _meter_with_calls()

    for i in range(3):
        record_flow_metrics(
            flow_id=f"fid-{i}", status="completed", cost_meter=m, metrics_path=metrics_path,
        )

    lines = metrics_path.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 3
    flow_ids = [json.loads(line)["flow_id"] for line in lines]
    assert flow_ids == ["fid-0", "fid-1", "fid-2"]


def test_error_rate_reflects_window(tmp_path: Path):
    """Spec D1-14 Scenario: 失败流程也写入 metrics + error_rate reflects window."""
    metrics_path = tmp_path / "metrics.json"
    m = _meter_with_calls()

    # First: 1 success
    record_flow_metrics(flow_id="ok-1", status="completed", cost_meter=m, metrics_path=metrics_path)
    # Then: 1 failure
    fail_record = record_flow_metrics(
        flow_id="fail-1", status="failed", cost_meter=m, metrics_path=metrics_path,
    )
    # error_rate over 2-flow window: 1 failure / 2 total = 0.5
    assert fail_record["error_rate"] == 0.5

    # Add 8 more successes → window = 10 total, 1 failure → 0.1
    for i in range(8):
        record_flow_metrics(
            flow_id=f"ok-{i}", status="completed", cost_meter=m, metrics_path=metrics_path,
        )
    final_lines = metrics_path.read_text(encoding="utf-8").strip().splitlines()
    last = json.loads(final_lines[-1])
    assert last["error_rate"] == 0.1


def test_error_rate_uses_sliding_window_100(tmp_path: Path):
    """Window MUST cap at 100 most recent flows (per spec)."""
    metrics_path = tmp_path / "metrics.json"
    m = _meter_with_calls()

    # 100 failures + 1 success → window = last 100 = 99 fail + 1 success = 0.99
    for i in range(100):
        record_flow_metrics(
            flow_id=f"fail-{i}", status="failed", cost_meter=m, metrics_path=metrics_path,
        )
    last = record_flow_metrics(
        flow_id="ok-final", status="completed", cost_meter=m, metrics_path=metrics_path,
    )
    # window is the last 100 records (excluding this final ok), all failures → 1.0
    # Plus this success → window becomes 100 + 1 = 101 → we count last 100 incl. this one
    # = 99 failures / 100 = 0.99
    assert last["error_rate"] == 0.99


def test_failed_flow_writes_nonzero_flow_time(tmp_path: Path):
    """Spec: 失败流程也写入 metrics，flow_time_seconds reflects time-to-failure."""
    metrics_path = tmp_path / "metrics.json"
    m = CostMeter()  # empty meter (no calls — flow failed before first LLM)
    record = record_flow_metrics(
        flow_id="fid-fail", status="failed", cost_meter=m, metrics_path=metrics_path,
    )
    # Spec says "non-empty values"; we substitute a tiny epsilon to avoid div-by-zero
    assert record["flow_time_seconds"] > 0
    assert record["agent_latency_seconds"]  # not empty (has the (no_calls) stub)


def test_token_consumption_rate_calculation(tmp_path: Path):
    """token_consumption_rate = total_tokens / flow_time_seconds."""
    metrics_path = tmp_path / "metrics.json"
    m = _meter_with_calls()
    record = record_flow_metrics(
        flow_id="fid", status="completed", cost_meter=m, metrics_path=metrics_path,
    )
    expected_rate = m.total_tokens / record["flow_time_seconds"]
    assert abs(record["token_consumption_rate"] - round(expected_rate, 3)) < 0.001


def test_default_metrics_path_uses_sddp_pet_home(monkeypatch, tmp_path: Path):
    """Spec G-style: env var override for testing."""
    monkeypatch.setenv("SDDP_PET_HOME", str(tmp_path))
    assert _default_metrics_path() == tmp_path / "metrics.json"


def test_default_metrics_path_falls_back_to_home(monkeypatch):
    """Without SDDP_PET_HOME, default is ~/.sddp-pet/metrics.json."""
    monkeypatch.delenv("SDDP_PET_HOME", raising=False)
    p = _default_metrics_path()
    assert p.name == "metrics.json"
    assert p.parent.name == ".sddp-pet"


def test_record_creates_parent_dir_if_missing(tmp_path: Path):
    """Parent dir MUST be created (mkdir parents=True)."""
    nested = tmp_path / "a" / "b" / "c" / "metrics.json"
    m = _meter_with_calls()
    record_flow_metrics(
        flow_id="fid", status="completed", cost_meter=m, metrics_path=nested,
    )
    assert nested.exists()


def test_record_silently_skips_corrupt_existing_lines(tmp_path: Path):
    """Append-mode MUST be resilient to existing corrupt lines (don't crash)."""
    metrics_path = tmp_path / "metrics.json"
    metrics_path.write_text("{corrupt line\n{\"valid\": true}\n", encoding="utf-8")
    m = _meter_with_calls()
    record_flow_metrics(
        flow_id="fid", status="completed", cost_meter=m, metrics_path=metrics_path,
    )
    # New line appended
    lines = metrics_path.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 3
    assert "flow_id" in lines[-1]
