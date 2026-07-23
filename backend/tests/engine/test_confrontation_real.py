"""Full real-LLM confrontation e2e (D2-1 — the "Go validation" in miniature).

Wires ``Phase1ConfrontationFlow`` to the 4 REAL DeepSeek agents
(``build_real_confrontation_agents``) and runs one complete adversarial cycle
on a small proposal. This is the integration keystone: it proves the whole
loop (architect → critic → empiricist → convergence → possibly revise/force)
runs end-to-end on a real LLM, not just mocks.

Capped at 1 dimension × 2 rounds to keep cost/time modest (~8-16 LLM calls).
The full 3-dimension × 5-round run (Go threshold ≤ $15) is a separate,
heavier validation.

Skipped without OPENAI_API_KEY. Run manually:
    $env:OPENAI_API_KEY="sk-..."; $env:OPENAI_BASE_URL="https://api.deepseek.com/v1"
    $env:SDDP_LLM_MODEL="deepseek-chat"
    pytest tests/engine/test_confrontation_real.py -v -s -m e2e
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

PROPOSAL = (
    "为 CLI 工具新增配置热重载：检测到配置文件变更后自动重新加载，无需重启进程。"
    "要求：低延迟、不丢失运行中任务的状态。"
)


@requires_llm
@pytest.mark.e2e
def test_real_deepseek_confrontation_completes() -> None:
    """One full adversarial cycle on real DeepSeek must complete (converge or force).

    Asserts:
      - flow terminates (no infinite loop — max_rounds + convergence engine work)
      - rounds_run stays within the cap
      - cost_meter recorded calls for architect + critic (proving real LLM ran)
      - final delta_design is non-empty
    """
    model = os.environ.get("SDDP_LLM_MODEL", "deepseek-chat")
    client = OpenAI()
    cost_meter = CostMeter()
    agents = build_real_confrontation_agents(client, model, cost_meter)

    flow = Phase1ConfrontationFlow(
        agents=agents,
        critic_dimensions=["性能"],  # 1 dimension to cap cost
        max_rounds=2,  # cap rounds
        human_feedback_handler=lambda kind, payload: (
            True
        ),  # auto-approve converge/force
    )
    result = flow.kickoff({"proposal": PROPOSAL})

    # 1. terminated within cap
    assert result.rounds_run <= 2, f"flow overran max_rounds: {result.rounds_run}"
    assert result.rounds_run >= 1

    # 2. real LLM calls were made (architect + critic at minimum)
    report = cost_meter.to_report_dict()
    assert report.get("total_tokens", 0) > 0, (
        "no LLM tokens recorded — agents not wired"
    )
    round_tokens = report.get("round_tokens", {})
    assert "architect" in round_tokens or "critic" in round_tokens, (
        f"expected architect/critic tokens, got: {round_tokens}"
    )

    # 3. produced a design
    assert result.state.current_delta_design, "no delta_design produced"
    assert len(result.state.current_delta_design) > 20

    # 4. convergence outcome is sane
    assert result.converged is True or result.force_converged is True, (
        f"flow neither converged nor force-converged: {result}"
    )

    print(
        f"\n[confrontation e2e] rounds={result.rounds_run} "
        f"converged={result.converged} force={result.force_converged} "
        f"tokens={report.get('total_tokens')} cost=${report.get('measured_cost_usd', 0):.4f} "
        f"errors={len(result.state.errors)}"
    )
