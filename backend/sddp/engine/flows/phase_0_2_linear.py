"""Linear Flow for Dev-Phase 0: 5-role sequential pipeline (Phase 0 → Phase 2).

Per spec engine-core requirement 1 + analysis/00 §10 MVP linear flow:
  需求官 → 调度官 → 架构师 → 实施师 → 代码资产管理员

3 user confirmation points (Phase 0/1/2) integrate via cli-runner's
CLIHumanFeedbackAdapter (Dev-Phase 0). This flow uses MockFlowAdapter as the
execution substrate; production wire-up with CrewAI Flows is via CrewAIFlowAdapter.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Callable

from ...adaptation.mock_adapter import MockFlowAdapter
from ...kg.query_api import KnowledgeGraphQueryAPI
from ...safe_agent.wrapper import SafeAgent
from ..agents import AgentFactory, RoleAgent
from ..cost_meter import CostMeter

logger = logging.getLogger(__name__)


@dataclass
class FlowResult:
    """End-to-end result of the linear flow."""

    proposal: dict[str, Any] | None = None
    feasibility: dict[str, Any] | None = None
    architecture_research: dict[str, Any] | None = None
    delta_spec: dict[str, Any] | None = None
    delta_design: dict[str, Any] | None = None
    code_suggestions: dict[str, Any] | None = None
    kg_update: dict[str, Any] | None = None
    completed_steps: list[str] = field(default_factory=list)
    cost_report: dict[str, Any] | None = None


class LinearPhase02Flow:
    """5-role linear flow (Dev-Phase 0 MVP).

    Usage:
        flow = LinearPhase02Flow(agent_factory=factory, kg_db_path="...")
        result = flow.kickoff({"requirement": "..."})
    """

    def __init__(
        self,
        agent_factory: AgentFactory,
        kg_db_path: str | None = None,
        human_feedback_handler: Callable[[str, dict[str, Any]], bool] | None = None,
        *,
        flow_id: str | None = None,
        prior_state: dict[str, dict[str, Any]] | None = None,
        persist_step: Callable[[str, str, dict[str, Any]], None] | None = None,
    ) -> None:
        """
        Args:
            agent_factory: produces the 5 role Agents
            kg_db_path: path for the post-step KG rescan
            human_feedback_handler: confirmation callback (default auto-approves)
            flow_id: optional flow identifier for @persist bookkeeping (D0-10)
            prior_state: optional {step_name: step_output} to skip already-completed
                steps on resume (D0-10). When a step is present here, its LLM call
                is bypassed and the cached output is reused.
            persist_step: optional callback (flow_id, step_name, step_output) invoked
                after each successful step (D0-10). Wired by CLI to flow_state.save_state.
        """
        self.factory = agent_factory
        self.kg_db_path = kg_db_path
        self.human_feedback_handler = human_feedback_handler or self._default_human_feedback
        self.cost_meter = agent_factory.cost_meter
        self.flow_id = flow_id
        self.prior_state = prior_state or {}
        self.persist_step = persist_step

    def _run_step(
        self,
        name: str,
        producer: Callable[[], dict[str, Any]],
        result_setter: Callable[[dict[str, Any]], None],
    ) -> dict[str, Any]:
        """Run one step, honoring @persist resume semantics (D0-10).

        - If `name` is in `self.prior_state`, reuse cached output (skip LLM).
        - Otherwise call `producer()` to compute fresh output.
        - Either way, call `self.persist_step` (if wired) so the next interruption
          can resume from this point.
        """
        if name in self.prior_state:
            logger.info("step %s resumed from prior_state (LLM skipped)", name)
            output = self.prior_state[name]
        else:
            output = producer()
        result_setter(output)
        if self.persist_step is not None and self.flow_id is not None:
            try:
                self.persist_step(self.flow_id, name, output)
            except Exception as e:
                logger.warning("persist_step(%s) failed (non-fatal): %s", name, e)
        return output

    def kickoff(self, inputs: dict[str, Any]) -> FlowResult:
        """Run the linear flow. inputs MUST contain 'requirement' (string).

        If `prior_state` was supplied at construction, any step whose name is a
        key in prior_state is replayed from cache instead of re-invoking the LLM.
        """
        result = FlowResult()
        self.cost_meter._start_time = __import__("time").monotonic()  # reset clock

        # 1. 需求官
        def _produce_proposal() -> dict[str, Any]:
            requirement_officer = self.factory.build_role("requirement_officer")
            proposal_output = requirement_officer.kickoff_fn({"requirement": inputs["requirement"]})
            return proposal_output.get("output", proposal_output)

        proposal = self._run_step("requirement_officer", _produce_proposal, lambda v: setattr(result, "proposal", v))
        result.completed_steps.append("requirement_officer")

        # CONFIRMATION POINT 1: 需求确认 (Phase 0)
        approved = self.human_feedback_handler("requirement_confirmation", {"proposal": result.proposal})
        if not approved:
            logger.info("flow aborted at requirement_confirmation")
            result.cost_report = self.cost_meter.to_report_dict()
            return result

        # 2. 调度官 (feasibility gate)
        def _produce_feasibility() -> dict[str, Any]:
            orchestrator = self.factory.build_role("orchestrator")
            return orchestrator.kickoff_fn({"proposal": result.proposal})

        feasibility = self._run_step("orchestrator", _produce_feasibility, lambda v: setattr(result, "feasibility", v))
        result.completed_steps.append("orchestrator")

        # 3. 架构师 (produces delta_spec + delta_design + architecture_research)
        def _produce_arch() -> dict[str, Any]:
            architect = self.factory.build_role("architect")
            return architect.kickoff_fn({"proposal": result.proposal})

        arch_output = self._run_step("architect", _produce_arch, lambda v: None)  # output parsed below
        # Architect may produce multiple outputs
        if isinstance(arch_output, dict):
            result.delta_spec = arch_output.get("output") or arch_output
            result.architecture_research = arch_output.get("architecture_research")
            result.delta_design = arch_output.get("delta_design")
        else:
            result.delta_spec = arch_output
        result.completed_steps.append("architect")

        # CONFIRMATION POINT 2: 方案确认 (Phase 1)
        approved = self.human_feedback_handler("design_confirmation", {
            "delta_spec": result.delta_spec,
            "delta_design": result.delta_design,
        })
        if not approved:
            logger.info("flow aborted at design_confirmation")
            result.cost_report = self.cost_meter.to_report_dict()
            return result

        # 4. 实施师 (code suggestions; NO file writes per spec)
        def _produce_executor() -> dict[str, Any]:
            executor = self.factory.build_role("executor")
            return executor.kickoff_fn({"design": result.delta_design or result.delta_spec})

        code_output = self._run_step("executor", _produce_executor, lambda v: setattr(result, "code_suggestions", v))
        result.completed_steps.append("executor")

        # 5. 代码资产管理员 (KG update — Dev-Phase 0 MVP: just records the scan_version delta)
        def _produce_kg_update() -> dict[str, Any]:
            if not self.kg_db_path:
                return {"skipped": "no kg_db_path"}
            from ...kg.scan import scan_project
            try:
                kg_summary = scan_project(inputs.get("project_path", "."), db_path=self.kg_db_path, prefer_scip=False)
                return kg_summary
            except Exception as e:
                logger.warning("KG update failed: %s", e)
                return {"error": str(e)}

        kg_out = self._run_step("code_asset_manager", _produce_kg_update, lambda v: setattr(result, "kg_update", v))
        result.completed_steps.append("code_asset_manager")

        result.cost_report = self.cost_meter.to_report_dict()
        return result

    def _default_human_feedback(self, kind: str, payload: dict[str, Any]) -> bool:
        """Default handler: always approve (used in unit tests). Production wires CLI adapter."""
        logger.info("human_feedback(kind=%s) auto-approved (default handler)", kind)
        return True


def enforce_no_file_write(code_suggestions: dict[str, Any]) -> list[str]:
    """Guardrail: scan code_suggestions for any path-write API calls.

    Per spec engine-core requirement 6: 实施师 MUST NOT 调用 open() write 模式、
    pathlib.Path.write_text 等。Returns list of violations (empty = OK).
    """
    violations: list[str] = []
    forbidden_patterns = [
        "open(", "Path.write_text", "Path.write_bytes", ".write(", "os.write(",
        "shutil.copy", "shutil.move", "os.rename", "os.replace",
    ]
    suggestions = code_suggestions.get("output", code_suggestions) if isinstance(code_suggestions, dict) else code_suggestions
    if not isinstance(suggestions, dict):
        return violations
    # Inspect each suggestion's diff content
    items = suggestions.get("suggestions") or suggestions.get("code_suggestions") or []
    for item in items:
        if not isinstance(item, dict):
            continue
        diff = item.get("diff", "") or ""
        for pat in forbidden_patterns:
            if pat in diff:
                violations.append(f"suggestion for {item.get('target_file', '?')}: pattern {pat!r} in diff")
    return violations
