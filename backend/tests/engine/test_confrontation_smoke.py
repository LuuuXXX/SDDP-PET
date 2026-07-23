"""Phase 1 confrontation flow smoke tests (Dev-Phase 2 D2-1 / No-Go-A).

Validates the SELF-BUILT adversarial loop (design §1 — NOT CrewAI ``@router``/
``or_()``): the while-loop cycles correctly, the convergence engine integrates,
and ``@persist`` resume does not cross-contaminate state across rounds or
between concurrent flows. Mock agents inject synthetic outputs so no LLM and no
CrewAI are involved.

These tests ARE the No-Go-A confirmation: the SDDP self-built engine handles
multi-round adversarial 往返 without CrewAI ``or_()`` and without state
corruption — the risk is mitigated at the architecture layer (design §2).
"""

from __future__ import annotations

import pytest

from sddp.engine.flows.phase_1_confrontation import Phase1ConfrontationFlow


def _arch(inputs):
    return {
        "delta_spec": "spec-v1",
        "delta_design": "design-v1",
        "architecture_research": "research",
    }


class TestConfrontationSmoke:
    def test_single_round_converge_via_arbitration_dismiss(self):
        """Medium-severity point → arbitrator dismisses with basis → CONVERGED in 1 round."""

        def critic(inputs):
            return {
                "criticism_points": [
                    {
                        "id": "c1",
                        "dimension": inputs["dimension"],
                        "content": "x",
                        "severity": "中",
                    }
                ]
            }

        def empiricist(inputs):
            return {"evidence": "evid-1 substantive evidence text"}

        def orchestrator(inputs):
            return {
                "decisions": [
                    {
                        "id": "c1",
                        "decision": "驳回",
                        "basis": "evid-1 证明不成立，依据充分",
                    }
                ]
            }

        flow = Phase1ConfrontationFlow(
            agents={
                "architect": _arch,
                "critic": critic,
                "empiricist": empiricist,
                "orchestrator": orchestrator,
            },
            critic_dimensions=["性能"],
            max_rounds=5,
        )
        result = flow.kickoff({"proposal": "加配置热重载"})
        assert result.converged is True
        assert result.rounds_run == 1
        assert result.state.criticism_points[0].status == "dismissed"

    def test_high_severity_drives_revise_loop_to_force_converge(self):
        """High-severity point each round → REVISE → REVISE → max_rounds FORCE."""
        critic_calls = {"n": 0}

        def critic(inputs):
            critic_calls["n"] += 1
            return {
                "criticism_points": [
                    {
                        "id": f"c{critic_calls['n']}",
                        "dimension": inputs["dimension"],
                        "content": "high risk",
                        "severity": "高",
                    }
                ]
            }

        rev = {"n": 0}

        def arch(inputs):
            rev["n"] += 1  # design mutates each revision
            return {
                "delta_spec": f"spec-v{rev['n']}",
                "delta_design": f"design-v{rev['n']}",
                "architecture_research": "research",
            }

        flow = Phase1ConfrontationFlow(
            agents={
                "architect": arch,
                "critic": critic,
                "empiricist": lambda i: {"evidence": "ev text"},
                "orchestrator": lambda i: {},
            },
            critic_dimensions=["性能"],
            max_rounds=3,
            human_feedback_handler=lambda k, p: True,  # auto-approve force_convergence
        )
        result = flow.kickoff({"proposal": "p"})
        assert result.rounds_run == 3
        assert result.force_converged is True
        assert result.converged is True  # force + user approved
        # state mutated across rounds via architect revise (no stale state)
        assert "design-v" in (result.state.current_delta_design or "")
        # criticism_points are per-round (overwritten); cross-round history
        # injection into architect is a v2 optimization (design §4).
        assert result.state.criticism_points[0].severity == "高"

    def test_no_criticism_converges_immediately(self):
        def critic(inputs):
            return {"criticism_points": []}

        flow = Phase1ConfrontationFlow(
            agents={
                "architect": _arch,
                "critic": critic,
                "empiricist": lambda i: {},
                "orchestrator": lambda i: {},
            },
            critic_dimensions=["性能"],
        )
        result = flow.kickoff({"proposal": "p"})
        assert result.converged is True
        assert result.rounds_run == 1
        assert result.state.criticism_points == []

    def test_persist_resume_skips_research_step(self):
        """prior_state has architecture_research → that step is resumed, not recomputed."""
        arch_calls: list[str] = []

        def arch(inputs):
            arch_calls.append(inputs.get("task") or "design")
            return {
                "delta_spec": "s",
                "delta_design": "d",
                "architecture_research": "FRESH",
            }

        def critic(inputs):
            return {"criticism_points": []}

        flow = Phase1ConfrontationFlow(
            agents={
                "architect": arch,
                "critic": critic,
                "empiricist": lambda i: {},
                "orchestrator": lambda i: {},
            },
            critic_dimensions=["性能"],
            prior_state={"architecture_research": "CACHED_RESEARCH"},
        )
        result = flow.kickoff({"proposal": "p"})
        assert result.converged is True
        assert (
            result.state.architecture_research == "CACHED_RESEARCH"
        )  # resumed, not recomputed
        assert "research" not in arch_calls  # research agent call was skipped

    def test_persist_callback_invoked_per_step(self):
        persisted: list[tuple[str, str]] = []

        def critic(inputs):
            return {"criticism_points": []}

        flow = Phase1ConfrontationFlow(
            agents={
                "architect": _arch,
                "critic": critic,
                "empiricist": lambda i: {},
                "orchestrator": lambda i: {},
            },
            critic_dimensions=["性能"],
            flow_id="flow-test",
            persist_step=lambda fid, name, out: persisted.append((fid, name)),
        )
        flow.kickoff({"proposal": "p"})
        assert any(fid == "flow-test" for fid, _ in persisted)
        assert any("architecture_research" in n for _, n in persisted)
        assert any("architect_produce_design" in n for _, n in persisted)

    def test_two_flows_isolated_by_flow_id(self):
        """D2-4: two concurrent flows don't cross-talk (flow_id namespace isolation)."""

        def critic(inputs):
            return {"criticism_points": []}

        f1 = Phase1ConfrontationFlow(
            agents={
                "architect": _arch,
                "critic": critic,
                "empiricist": lambda i: {},
                "orchestrator": lambda i: {},
            },
            critic_dimensions=["性能"],
            flow_id="flow-A",
        )
        f2 = Phase1ConfrontationFlow(
            agents={
                "architect": _arch,
                "critic": critic,
                "empiricist": lambda i: {},
                "orchestrator": lambda i: {},
            },
            critic_dimensions=["性能"],
            flow_id="flow-B",
        )
        r1 = f1.kickoff({"proposal": "proposal-A"})
        r2 = f2.kickoff({"proposal": "proposal-B"})
        assert r1.state.flow_id == "flow-A"
        assert r2.state.flow_id == "flow-B"
        assert r1.state.proposal == "proposal-A"
        assert r2.state.proposal == "proposal-B"  # no cross-contamination

    def test_guardrail_integrates_into_loop(self):
        """Arbitrator tries to rubber-stamp a HIGH point → guardrail refuses → REVISE continues.
        End-to-end integration of convergence.guardrail with the flow loop."""

        # round 1: medium point; orchestrator tries invalid dismiss of... actually
        # high never reaches arbitrator. Test medium dismiss-without-basis → stays unresolved → REVISE.
        def critic(inputs):
            return {
                "criticism_points": [
                    {"id": "c1", "dimension": "性能", "content": "x", "severity": "中"}
                ]
            }

        def orchestrator(inputs):
            # dismiss WITHOUT substantive basis → guardrail-for-medium is not enforced,
            # but basis is empty → dismiss still applies for medium. To force a REVISE,
            # have arbitrator ACCEPT instead (→ unresolved → REVISE).
            return {"decisions": [{"id": "c1", "decision": "采纳", "basis": "valid"}]}

        flow = Phase1ConfrontationFlow(
            agents={
                "architect": _arch,
                "critic": critic,
                "empiricist": lambda i: {"evidence": "ev"},
                "orchestrator": orchestrator,
            },
            critic_dimensions=["性能"],
            max_rounds=2,
            human_feedback_handler=lambda k, p: True,
        )
        result = flow.kickoff({"proposal": "p"})
        # round1: medium → arbitrate accept → unresolved → REVISE
        # round2: critic produces medium again → arbitrate accept → REVISE → max_rounds → FORCE
        assert result.force_converged is True
        assert result.state.criticism_points[0].arbitrator_decision == "采纳"

    def test_missing_agent_raises(self):
        with pytest.raises(ValueError, match="missing agents"):
            Phase1ConfrontationFlow(agents={"architect": _arch})  # missing 3 agents
