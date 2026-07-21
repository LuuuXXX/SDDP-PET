"""Cost meter: intercepts LLM API calls and measures tokens + structured output compliance.

Per Dev-Phase 0 spec engine-core requirement 5: cost_report.json MUST contain:
  - measured_cost_usd (based on actual usage, not estimates)
  - wall_clock_minutes_excluding_human_wait
  - structured_output_first_try_rate (based on pydantic validation retries)
  - total_tokens / round_tokens

Per analysis/06 X-3: 成本 MUST be measured not estimated.
"""
from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# OpenAI pricing (USD per 1M tokens). Update from openai.com/pricing.
# These are documented constants — measured_cost = (tokens/1M) * price.
# Per design decision 6: Dev-Phase 0 uses gpt-4o-mini for 5 roles by default.
OPENAI_PRICING_USD_PER_1M: dict[str, dict[str, float]] = {
    "gpt-4o-mini": {"input": 0.15, "output": 0.60},
    "gpt-4o": {"input": 2.50, "output": 10.00},
    "gpt-4-turbo": {"input": 10.00, "output": 30.00},
    # DeepSeek (OpenAI-compatible provider; used only for plumbing verification,
    # NOT a Dev-Phase 0 Go-judgment baseline — see design.md decision 6).
    # Prices per https://api-docs.deepseek.com/quick_start/pricing (cache-miss tier).
    "deepseek-chat": {"input": 0.27, "output": 1.10},
    "deepseek-reasoner": {"input": 0.55, "output": 2.19},
    # Fallback for unknown models
    "_default": {"input": 1.00, "output": 3.00},
}


@dataclass
class LLMCallRecord:
    """One LLM call record."""

    agent: str
    model: str
    prompt_tokens: int
    completion_tokens: int
    cost_usd: float
    structured_output_first_try: bool  # True if pydantic validation passed on first try
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


@dataclass
class CostMeter:
    """Accumulates LLM call records + computes cost_report.json fields.

    Usage:
        meter = CostMeter(default_model="gpt-4o-mini")
        meter.record_call(agent="architect", model="gpt-4o-mini",
                          prompt_tokens=1200, completion_tokens=800,
                          structured_output_first_try=True)
        meter.write_report(Path("cost_report.json"))
    """

    default_model: str = "gpt-4o-mini"
    calls: list[LLMCallRecord] = field(default_factory=list)
    _start_time: float = field(default_factory=time.monotonic)
    _human_wait_seconds: float = 0.0  # accumulated time spent waiting for human input

    def record_call(
        self,
        *,
        agent: str,
        model: str | None = None,
        prompt_tokens: int,
        completion_tokens: int,
        structured_output_first_try: bool,
    ) -> LLMCallRecord:
        """Record one LLM call. Returns the record."""
        m = model or self.default_model
        pricing = OPENAI_PRICING_USD_PER_1M.get(m, OPENAI_PRICING_USD_PER_1M["_default"])
        cost = (prompt_tokens / 1_000_000) * pricing["input"] + (completion_tokens / 1_000_000) * pricing["output"]
        record = LLMCallRecord(
            agent=agent,
            model=m,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            cost_usd=cost,
            structured_output_first_try=structured_output_first_try,
        )
        self.calls.append(record)
        return record

    def record_human_wait(self, seconds: float) -> None:
        """Accumulate time spent waiting for human input (excluded from latency)."""
        self._human_wait_seconds += seconds

    @property
    def total_tokens(self) -> int:
        return sum(c.prompt_tokens + c.completion_tokens for c in self.calls)

    @property
    def total_cost_usd(self) -> float:
        return round(sum(c.cost_usd for c in self.calls), 6)

    @property
    def structured_output_first_try_rate(self) -> float:
        """Rate of calls where pydantic validation passed on first try (0.0-1.0)."""
        if not self.calls:
            return 1.0
        return sum(1 for c in self.calls if c.structured_output_first_try) / len(self.calls)

    @property
    def wall_clock_minutes_excluding_human_wait(self) -> float:
        elapsed = time.monotonic() - self._start_time - self._human_wait_seconds
        # Clamp to ≥0 (in case _human_wait_seconds exceeds elapsed due to test/edge timing)
        return round(max(0.0, elapsed) / 60.0, 4)

    def round_tokens(self, agent: str | None = None) -> dict[str, int]:
        """Per-agent token breakdown."""
        out: dict[str, int] = {}
        for c in self.calls:
            key = agent or c.agent
            out.setdefault(key, 0)
            out[key] += c.prompt_tokens + c.completion_tokens
        return out

    def to_report_dict(self) -> dict[str, Any]:
        """Build the cost_report.json dict."""
        return {
            "measured_cost_usd": self.total_cost_usd,
            "wall_clock_minutes_excluding_human_wait": self.wall_clock_minutes_excluding_human_wait,
            "structured_output_first_try_rate": round(self.structured_output_first_try_rate, 4),
            "total_tokens": self.total_tokens,
            "round_tokens": self.round_tokens(),
            "call_count": len(self.calls),
            "default_model": self.default_model,
            "calls": [
                {
                    "agent": c.agent,
                    "model": c.model,
                    "prompt_tokens": c.prompt_tokens,
                    "completion_tokens": c.completion_tokens,
                    "cost_usd": round(c.cost_usd, 6),
                    "structured_output_first_try": c.structured_output_first_try,
                    "timestamp": c.timestamp,
                }
                for c in self.calls
            ],
            # DoD threshold checks (D0-11/12/13)
            "dod_checks": {
                "D0-11_cost_le_5_usd": self.total_cost_usd <= 5.0,
                "D0-12_latency_le_10_min": self.wall_clock_minutes_excluding_human_wait <= 10.0,
                "D0-13_compliance_ge_99_pct": self.structured_output_first_try_rate >= 0.99,
            },
        }

    def write_report(self, path: str | Path) -> dict[str, Any]:
        """Write cost_report.json; return the dict."""
        report = self.to_report_dict()
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(report, indent=2, ensure_ascii=False))
        return report
