"""Phase 1 Confrontation Flow (Dev-Phase 2 D2-1).

Per `design.md` §1 + §4. This is the SDDP **self-built** adversarial loop — it
does NOT use CrewAI ``@router``/``or_()`` (that dependency is the No-Go-A risk;
architecture-level avoidance per design §2). The loop is a plain ``while`` plus
the deterministic convergence engine in ``sddp/engine/convergence.py``.

Agents are injected as callables (``AgentFn``) so the loop logic is independent
of the LLM backend:
    - tests inject synthetic mock functions (No-Go-A smoke — no LLM, no CrewAI)
    - production wires ``SafeAgent.kickoff`` (real LLM) at the adapter boundary

Loop topology (design §4):
    architecture_research → architect_produce_design
      ↘ (each round) critics_challenge → empiricist_verify
          → (if needs_arbitration) orchestrator_arbitrate → apply_arbitration
          → check_convergence → REVISE (architect_revise) | CONVERGED (user) | FORCE

``@persist`` resume semantics mirror DP0's ``LinearPhase02Flow._run_step``: a
step whose name is in ``prior_state`` is replayed from cache instead of
re-invoking the agent; ``persist_step`` is called after each step so an
interruption can resume.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from typing import Any, Callable

from ..convergence import (
    ConvergenceVerdict,
    apply_arbitration,
    check_convergence,
    needs_arbitration,
)
from .phase_1_state import CriticismPoint, Phase1ConfrontationState

logger = logging.getLogger(__name__)

# An agent function: takes a dict input, returns a dict output.
# Mock for tests, SafeAgent.kickoff (or adapter) for production.
AgentFn = Callable[[dict[str, Any]], dict[str, Any]]

_REQUIRED_AGENTS = ("architect", "critic", "empiricist", "orchestrator")


@dataclass
class ConfrontationResult:
    """End-to-end result of one confrontation flow run."""

    state: Phase1ConfrontationState
    converged: bool
    force_converged: bool
    rounds_run: int
    completed_steps: list[str] = field(default_factory=list)


class Phase1ConfrontationFlow:
    """Self-built adversarial flow (Dev-Phase 2 D2-1).

    Usage (mock smoke):
        flow = Phase1ConfrontationFlow(
            agents={"architect": mock_arch, "critic": mock_critic,
                    "empiricist": mock_emp, "orchestrator": mock_orch},
            critic_dimensions=["性能"],
            max_rounds=3,
        )
        result = flow.kickoff({"proposal": "..."})
    """

    def __init__(
        self,
        agents: dict[str, AgentFn],
        *,
        critic_dimensions: list[str] | None = None,
        max_rounds: int = 5,
        human_feedback_handler: Callable[[str, dict[str, Any]], bool] | None = None,
        flow_id: str | None = None,
        prior_state: dict[str, dict[str, Any]] | None = None,
        persist_step: Callable[[str, str, dict[str, Any]], None] | None = None,
    ) -> None:
        missing = set(_REQUIRED_AGENTS) - set(agents)
        if missing:
            raise ValueError(
                f"Phase1ConfrontationFlow missing agents: {sorted(missing)}"
            )
        self.agents = agents
        self.critic_dimensions = critic_dimensions or ["安全性", "性能", "可维护性"]
        self.max_rounds = max_rounds
        self.human_feedback_handler = human_feedback_handler or self._default_feedback
        self.flow_id = flow_id
        self.prior_state = prior_state or {}
        self.persist_step = persist_step

    # ---- public entry ----

    def kickoff(self, inputs: dict[str, Any]) -> ConfrontationResult:
        proposal = inputs.get("requirement") or inputs.get("proposal") or ""
        state = Phase1ConfrontationState(
            flow_id=self.flow_id or "",
            proposal=str(proposal),
            max_rounds=self.max_rounds,
        )
        completed: list[str] = []

        # 1. architecture research
        state.architecture_research = self._step(
            "architecture_research",
            lambda: _extract(
                self.agents["architect"](
                    {"proposal": state.proposal, "task": "research"}
                ),
                "architecture_research",
            ),
        )
        completed.append("architecture_research")

        # 2. initial design
        state.current_delta_spec, state.current_delta_design = self._architect_design(
            state, first=True
        )
        completed.append("architect_produce_design")

        # 3. adversarial loop
        while True:
            state.round_count += 1
            state.criticism_points = self._critics_challenge(state)
            completed.append(f"round_{state.round_count}_critics")

            self._empiricist_verify(state)
            completed.append(f"round_{state.round_count}_empiricist")

            if needs_arbitration(state.criticism_points):
                decisions = self._orchestrator_arbitrate(state)
                apply_arbitration(
                    state.criticism_points, decisions, errors=state.errors
                )
                completed.append(f"round_{state.round_count}_arbitration")

            verdict = check_convergence(
                state.criticism_points, state.round_count, state.max_rounds
            )
            completed.append(f"round_{state.round_count}_verdict_{verdict.value}")

            if verdict == ConvergenceVerdict.CONVERGED:
                approved = self.human_feedback_handler(
                    "design_confirmation",
                    {
                        "delta_spec": state.current_delta_spec,
                        "delta_design": state.current_delta_design,
                    },
                )
                if approved:
                    state.converged = True
                    break
                # user rejected → fall through to revise
            elif verdict == ConvergenceVerdict.FORCE_CONVERGED:
                approved = self.human_feedback_handler(
                    "force_convergence",
                    {
                        "round_count": state.round_count,
                        "delta_design": state.current_delta_design,
                    },
                )
                state.converged = approved
                break
            # REVISE (or user-rejected CONVERGED) → architect revises, loop continues
            state.current_delta_spec, state.current_delta_design = (
                self._architect_design(state, first=False)
            )
            completed.append(f"round_{state.round_count}_architect_revise")

        return ConfrontationResult(
            state=state,
            converged=state.converged,
            force_converged=(state.round_count >= state.max_rounds),
            rounds_run=state.round_count,
            completed_steps=completed,
        )

    # ---- step helpers (with @persist resume semantics) ----

    def _step(self, name: str, producer: Callable[[], Any]) -> Any:
        if name in self.prior_state:
            logger.info("step %s resumed from prior_state (agent skipped)", name)
            output = self.prior_state[name]
        else:
            output = producer()
        if self.persist_step is not None and self.flow_id is not None:
            try:
                self.persist_step(
                    self.flow_id,
                    name,
                    output
                    if isinstance(output, (dict, str))
                    else {"value": str(output)},
                )
            except Exception as e:  # persist failure is non-fatal
                logger.warning("persist_step(%s) failed: %s", name, e)
        return output

    def _architect_design(
        self, state: Phase1ConfrontationState, *, first: bool
    ) -> tuple[str, str]:
        step_name = (
            "architect_produce_design"
            if first
            else f"round_{state.round_count}_architect_revise"
        )
        inputs = {
            "proposal": state.proposal,
            "research": state.architecture_research or "",
            "existing_design": state.current_delta_design or "",
            "criticism_feedback": (
                str(state.criticism_points)
                if state.criticism_points
                else "首轮设计，无前轮质疑"
            ),
        }
        out = self._step(step_name, lambda: self.agents["architect"](inputs))
        delta_spec = _extract(out, "delta_spec") or _extract(out, "output") or str(out)
        delta_design = _extract(out, "delta_design") or delta_spec
        return str(delta_spec), str(delta_design)

    def _critics_challenge(
        self, state: Phase1ConfrontationState
    ) -> list[CriticismPoint]:
        points: list[CriticismPoint] = []
        for dim in self.critic_dimensions:
            out = self.agents["critic"](
                {
                    "dimension": dim,
                    "design": state.current_delta_design,
                    "proposal": state.proposal,
                }
            )
            points.extend(_parse_criticisms(out, dim))
        return points

    def _empiricist_verify(self, state: Phase1ConfrontationState) -> None:
        for point in state.criticism_points:
            if point.severity in ("高", "中") and point.status == "unresolved":
                out = self.agents["empiricist"](
                    {
                        "criticism_point": point.content,
                        "dimension": point.dimension,
                        "design": state.current_delta_design,
                    }
                )
                point.evidence_ref = _extract(out, "evidence") or (
                    str(out) if out else None
                )
                if point.evidence_ref:
                    state.evidence_reports.append(point.evidence_ref)

    def _orchestrator_arbitrate(
        self, state: Phase1ConfrontationState
    ) -> dict[str, dict]:
        targets = [
            p
            for p in state.criticism_points
            if p.severity in ("中", "低")
            and p.status == "unresolved"
            and p.arbitrator_decision is None
        ]
        if not targets:
            return {}
        out = self.agents["orchestrator"](
            {
                "criticism_points": str(targets),
                "evidence_reports": str(state.evidence_reports),
            }
        )
        return _parse_arbitration(out)

    @staticmethod
    def _default_feedback(kind: str, payload: dict[str, Any]) -> bool:
        logger.info("human_feedback(kind=%s) auto-approved (default handler)", kind)
        return True


# ---- output parsing helpers (LLM output is fragile → defensive fallbacks) ----


def _extract(out: Any, key: str) -> str | None:
    if isinstance(out, dict):
        v = out.get(key)
        if v is not None:
            return str(v)
    return None


def _parse_criticisms(out: Any, dimension: str) -> list[CriticismPoint]:
    """Parse critic output into CriticismPoints. Defensive: if nothing parses,
    synthesize a single medium-severity point so the loop always has something
    to converge on (matches §8 edge case "Critic produces no valid criticism")."""
    if isinstance(out, dict):
        raw = (
            out.get("criticism_points") or out.get("points") or out.get("output") or []
        )
    else:
        raw = out
    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except json.JSONDecodeError:
            raw = []

    points: list[CriticismPoint] = []

    # An explicit list (including EMPTY) means the critic rendered a verdict:
    # empty == "no criticism" → return [] so the loop can converge. We only
    # synthesize a fallback medium point when the output was NOT a list (None /
    # wrong type / JSON-decode failure), i.e. genuinely unparseable.
    if isinstance(raw, list):
        for i, item in enumerate(raw):
            if not isinstance(item, dict):
                continue
            points.append(
                CriticismPoint(
                    id=item.get("id", f"{dimension}-{i}"),
                    dimension=item.get("dimension", dimension),
                    content=item.get("content", ""),
                    severity=item.get("severity", "中"),
                    status=item.get("status", "unresolved"),
                )
            )
        return points  # may be empty — explicit "no criticism"

    # raw was not a parseable list → defensive fallback (one medium point)
    points.append(
        CriticismPoint(
            id=f"{dimension}-fallback",
            dimension=dimension,
            content=(str(out)[:200] if out else "无可解析质疑"),
            severity="中",
            status="unresolved",
        )
    )
    return points


def _parse_arbitration(out: Any) -> dict[str, dict]:
    raw = out.get("decisions") if isinstance(out, dict) else out
    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except json.JSONDecodeError:
            return {}
    if not isinstance(raw, list):
        return {}
    return {
        item["id"]: {
            "decision": item.get("decision", "采纳"),
            "basis": item.get("basis", ""),
        }
        for item in raw
        if isinstance(item, dict) and "id" in item
    }
