"""Phase 2 Go-validation e2e: full 3-dimension × 5-round confrontation (D2-1 Go).

Per `design.md` §10 + `analysis/06` Go threshold: a complete 5-round
confrontation MUST complete at cost ≤ $15. This test runs it via the real
DeepSeek agents (no UI — the Electron UI is the deferred dev-machine part).
The capped-cost assertion IS the Go criterion.

Heavy: ~60-100 LLM calls, 3-5 min, ~$0.05-0.5 on DeepSeek Tier-B. Skipped w/o key.

Run manually:
    $env:OPENAI_API_KEY="sk-..."; $env:OPENAI_BASE_URL="https://api.deepseek.com/v1"
    $env:SDDP_LLM_MODEL="deepseek-chat"
    pytest tests/engine/test_confrontation_go.py -v -s -m e2e
"""

from __future__ import annotations

import os

import pytest
from openai import OpenAI

from sddp.engine.cost_meter import CostMeter
from sddp.engine.flows.phase_1_agents import build_real_confrontation_agents
from sddp.engine.flows.phase_1_confrontation import Phase1ConfrontationFlow

requires_llm = pytest.mark.skipif(
    not os.environ.get("OPENAI_API_KEY"),
    reason="real-LLM e2e requires OPENAI_API_KEY (not regular CI)",
)

# DP2 Go threshold (analysis/06 §四: 完整对抗 ≤ $15)
DP2_GO_MAX_COST_USD = 15.0

PROPOSAL = (
    "为 CLI 工具新增配置热重载：检测到配置文件变更后自动重新加载，无需重启进程。"
    "要求：低延迟、线程安全、不丢失运行中任务的状态。"
)


@requires_llm
@pytest.mark.e2e
def test_phase2_go_full_confrontation_cost_under_threshold() -> None:
    """The DP2 Go criterion: a full 3-dim × 5-round confrontation completes ≤ $15."""
    model = os.environ.get("SDDP_LLM_MODEL", "deepseek-chat")
    client = OpenAI()
    cost_meter = CostMeter()
    agents = build_real_confrontation_agents(client, model, cost_meter)

    flow = Phase1ConfrontationFlow(
        agents=agents,
        critic_dimensions=["安全性", "性能", "可维护性"],  # full 3 dimensions
        max_rounds=5,
        human_feedback_handler=lambda kind, payload: (
            True
        ),  # auto-approve converge/force
    )
    result = flow.kickoff({"proposal": PROPOSAL})

    report = cost_meter.to_report_dict()
    cost = float(report.get("measured_cost_usd", 0))

    # ---- Go criterion ----
    assert cost <= DP2_GO_MAX_COST_USD, (
        f"DP2 Go FAIL: cost ${cost:.4f} exceeds threshold ${DP2_GO_MAX_COST_USD}"
    )

    # ---- completion sanity ----
    assert 1 <= result.rounds_run <= 5
    assert result.converged or result.force_converged, (
        f"flow did not terminate cleanly: {result}"
    )
    assert result.state.current_delta_design, "no delta_design produced"
    assert len(result.state.errors) == 0, (
        f"flow recorded errors: {result.state.errors[:3]}"
    )

    print(
        f"\n[Phase2 Go] rounds={result.rounds_run} converged={result.converged} "
        f"force={result.force_converged} cost=${cost:.4f} tokens={report.get('total_tokens')} "
        f"dimensions=3 errors=0"
    )
