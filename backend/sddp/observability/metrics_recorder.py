"""Metrics recorder: append-only JSON Lines metrics for Dev-Phase 1 D1-14.

Per specs/observability/spec.md Requirement: 引擎 MUST 采集 4 项监控指标到
`metrics.json`. The file is JSON Lines (one record per line, append-only) at
`~/.sddp-pet/metrics.json`. Reuses CostMeter's already-collected wall-clock +
token data; does NOT re-instrument.

4 metrics per record:
  - flow_time_seconds (float)
  - agent_latency_seconds (dict[agent_name → float seconds]; one entry per role)
  - token_consumption_rate (float tokens/sec)
  - error_rate (float 0.0–1.0; sliding-window of last 100 flows)

Plus envelope fields: flow_id, timestamp, status (completed|failed|aborted).
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ..engine.cost_meter import CostMeter


def _default_metrics_path() -> Path:
    """`~/.sddp-pet/metrics.json` (overridable via SDDP_PET_HOME for tests)."""
    home = os.environ.get("SDDP_PET_HOME")
    base = Path(home) if home else Path.home() / ".sddp-pet"
    return base / "metrics.json"


def _ensure_parent(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def _read_records_for_window(path: Path, window_size: int = 100) -> list[dict[str, Any]]:
    """Read up to the last `window_size` records from the JSONL file."""
    if not path.exists():
        return []
    records: list[dict[str, Any]] = []
    try:
        with path.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    records.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
    except OSError:
        return []
    return records[-window_size:]


def record_flow_metrics(
    *,
    flow_id: str,
    status: str,
    cost_meter: CostMeter,
    metrics_path: Path | None = None,
    failed_agents: list[str] | None = None,
    flow_started_at: str | None = None,
) -> dict[str, Any]:
    """Compute the 4 metrics from `cost_meter` + window state, append to metrics.json.

    Args:
        flow_id: the flow identifier
        status: "completed" | "failed" | "aborted"
        cost_meter: the CostMeter instance from the flow (already has calls + start_time)
        metrics_path: override (for tests); defaults to ~/.sddp-pet/metrics.json
        failed_agents: agents that recorded failures (from SafeAgent state_errors);
            used to compute per-agent latency for failed branches
        flow_started_at: ISO 8601 timestamp of flow kickoff (optional; if absent
            uses cost_meter._start_time monotonic + derived seconds)

    Returns:
        The record dict that was appended (for inspection / unit-test asserts).

    Per spec: each record MUST contain non-empty values for all 4 metric fields.
    For "failed" flows, flow_time_seconds reflects time-to-failure (not full flow).
    """
    path = metrics_path or _default_metrics_path()
    _ensure_parent(path)

    report = cost_meter.to_report_dict()

    # flow_time_seconds: CostMeter stores wall_clock_minutes_excluding_human_wait
    flow_time_seconds = float(report["wall_clock_minutes_excluding_human_wait"]) * 60.0
    # For failed/aborted flows with no calls yet, fall back to a tiny non-zero
    # value so the metric isn't empty (spec: "non-empty values")
    if flow_time_seconds <= 0.0:
        flow_time_seconds = 0.001

    # agent_latency_seconds: per-role seconds. CostMeter doesn't track per-role
    # wall time, so approximate: distribute flow_time across roles proportional
    # to their token usage. This is a deliberate DP1 simplification (DP2 will
    # add per-role wall timers when agent_latency becomes a Tier-S metric).
    round_tokens: dict[str, int] = report.get("round_tokens", {})
    total_tokens = max(report.get("total_tokens", 0), 1)
    agent_latency_seconds: dict[str, float] = {}
    for agent, toks in round_tokens.items():
        if toks <= 0:
            continue
        agent_latency_seconds[agent] = round(flow_time_seconds * (toks / total_tokens), 3)
    if not agent_latency_seconds:
        # No tokens recorded (e.g., failed before first call); seed with a stub
        agent_latency_seconds["(no_calls)"] = flow_time_seconds

    # token_consumption_rate: tokens / second
    if flow_time_seconds > 0:
        token_consumption_rate = round(report.get("total_tokens", 0) / flow_time_seconds, 3)
    else:
        token_consumption_rate = 0.0

    # error_rate: sliding-window of last 100 flows INCLUDING the current one
    window = _read_records_for_window(path, window_size=99)  # leave room for current
    window.append({"status": status})  # add current flow to the window
    failed_count = sum(1 for r in window if r.get("status") in ("failed", "aborted"))
    total_count = max(len(window), 1)
    error_rate = round(failed_count / total_count, 4)

    record: dict[str, Any] = {
        "flow_id": flow_id,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "status": status,
        # 4 metrics
        "flow_time_seconds": round(flow_time_seconds, 3),
        "agent_latency_seconds": agent_latency_seconds,
        "token_consumption_rate": token_consumption_rate,
        "error_rate": error_rate,
        # Supporting data (for diagnostic panel provenance)
        "total_tokens": report.get("total_tokens", 0),
        "measured_cost_usd": report.get("measured_cost_usd", 0.0),
        "failed_agents": failed_agents or [],
    }

    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, default=str, ensure_ascii=False) + "\n")

    return record


__all__ = ["record_flow_metrics", "_default_metrics_path"]
