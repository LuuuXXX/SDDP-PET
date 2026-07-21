"""5-role Agent factory (D0-7).

Per spec engine-core requirement 1: 5 roles MUST be constructible.
Per spec engine-core requirement 2: backstories MUST encode SDDP constraints.

This factory builds CrewAI Agent objects (or mock equivalents) using:
  - Backstories from sddp/engine/backstories/
  - SafeAgent wrapping (every kickoff MUST go through SafeAgent per spec/safe-agent-wrapper)
  - KG tools for code-asset-manager
  - Pydantic output models for proposal/delta-spec/delta-design

The factory supports a "mock" mode for unit tests (no real CrewAI Agent instantiation).
"""
from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from typing import Any, Callable, Literal

from ..safe_agent.wrapper import SafeAgent
from .backstories import BACKSTORIES
from .cost_meter import CostMeter
from .kg_tools import KGTools

logger = logging.getLogger(__name__)


RoleName = Literal["requirement_officer", "orchestrator", "architect", "executor", "code_asset_manager"]

# Per design.md decision 6: 5 roles use gpt-4o-mini by default.
# Per analysis/03 §五: all go through SafeAgent.
DEFAULT_ROLE_MODELS: dict[RoleName, str] = {
    "requirement_officer": "gpt-4o-mini",
    "orchestrator": "gpt-4o-mini",
    "architect": "gpt-4o-mini",
    "executor": "gpt-4o-mini",
    "code_asset_manager": "gpt-4o-mini",
}

# Provider override (plumbing verification only; not a Dev-Phase 0 Go baseline).
# Set SDDP_LLM_MODEL=deepseek-chat to uniformly override all 5 roles. Empty = honor
# DEFAULT_ROLE_MODELS as-is (i.e., the spec-compliant OpenAI gpt-4o-mini path).
_LLM_MODEL_OVERRIDE = os.environ.get("SDDP_LLM_MODEL", "").strip()
if _LLM_MODEL_OVERRIDE:
    DEFAULT_ROLE_MODELS = {role: _LLM_MODEL_OVERRIDE for role in DEFAULT_ROLE_MODELS}  # type: ignore[misc]
    logger.info("SDDP_LLM_MODEL override active: all roles use %s", _LLM_MODEL_OVERRIDE)


def _provider_supports_strict_json_schema(model: str) -> bool:
    """Return True if the model's provider supports response_format={'type':'json_schema', ...}.

    OpenAI gpt-4o-* models support strict json_schema (analysis/04 Tier-S).
    DeepSeek (deepseek-chat / deepseek-reasoner) only supports {'type':'json_object'}
    (no schema enforcement) — caller MUST fall back and rely on client-side pydantic
    validation, which may yield a lower structured_output_first_try_rate (D0-13).
    """
    return not model.lower().startswith("deepseek-")


@dataclass
class RoleAgent:
    """A constructed role: holds backstory + kickoff callable + metadata."""

    name: RoleName
    backstory: str
    model: str
    kickoff_fn: Callable[..., Any]  # wrapped through SafeAgent
    output_models: list[str]  # Pydantic schema names this role produces (empty list = free-form)
    safe_agent: SafeAgent
    tools: list[Callable[..., Any]] | None = None

    @property
    def output_model(self) -> str | None:
        """Primary output schema (first in output_models) or None for free-form roles.

        Kept for backward compatibility with callers/tests that read only the
        primary schema (D0-7 test path).
        """
        return self.output_models[0] if self.output_models else None


class AgentFactory:
    """Builds 5 role Agent objects with SafeAgent wrapping + KG tool injection."""

    def __init__(
        self,
        llm_client: Any | None = None,
        cost_meter: CostMeter | None = None,
        kg_tools: KGTools | None = None,
        safe_agent_timeout_seconds: int | None = None,
        safe_agent_max_retries: int | None = None,
        mock_mode: bool = False,
    ) -> None:
        """
        Args:
            llm_client: object with `.chat.completions.create(model=, messages=, response_format=)` (OpenAI-style)
                        If None and mock_mode=True, uses a deterministic mock.
            cost_meter: shared CostMeter instance for the Flow
            kg_tools: KGTools instance for code_asset_manager; required for that role
            mock_mode: if True, return mock kickoff_fn that doesn't call real LLM
        """
        self.llm_client = llm_client
        self.cost_meter = cost_meter or CostMeter()
        self.kg_tools = kg_tools
        self.safe_agent_timeout_seconds = safe_agent_timeout_seconds
        self.safe_agent_max_retries = safe_agent_max_retries
        self.mock_mode = mock_mode

    # ---- public ----

    def build_all(self) -> dict[RoleName, RoleAgent]:
        """Build all 5 role Agents."""
        return {role: self.build_role(role) for role in BACKSTORIES.keys()}  # type: ignore[misc]

    def build_role(self, role: RoleName) -> RoleAgent:
        """Build one RoleAgent."""
        if role not in BACKSTORIES:
            raise KeyError(f"unknown role: {role!r}. Available: {list(BACKSTORIES)}")
        backstory = BACKSTORIES[role]
        model = DEFAULT_ROLE_MODELS[role]

        # Pick output schema(s) per role (D0-8 schema enforcement).
        # Architect produces 3 schemas sequentially (delta_spec → delta_design →
        # architecture_research); other roles produce 0 or 1.
        output_models: list[str]
        if role == "requirement_officer":
            output_models = ["proposal"]
        elif role == "architect":
            output_models = ["delta_spec", "delta_design", "architecture_research"]
        else:
            output_models = []

        # Tools
        tools: list[Callable[..., Any]] | None
        if role == "code_asset_manager":
            if self.kg_tools is None:
                raise ValueError("code_asset_manager requires kg_tools")
            tools = self.kg_tools.as_tool_list()
        else:
            tools = None

        # Build kickoff_fn (mock or real)
        kickoff_fn = self._build_kickoff_fn(role, model, output_models, tools)

        # Wrap in SafeAgent
        safe = SafeAgent(
            name=role,
            kickoff_fn=kickoff_fn,
            timeout_seconds=self.safe_agent_timeout_seconds,
            max_retries=self.safe_agent_max_retries,
            state_errors_sink=lambda r: logger.info("role %s error: %s", role, r),
        )

        return RoleAgent(
            name=role,
            backstory=backstory,
            model=model,
            kickoff_fn=safe.kickoff,  # caller invokes SafeAgent.kickoff
            output_models=output_models,
            safe_agent=safe,
            tools=tools,
        )

    # ---- internals ----

    def _build_kickoff_fn(
        self,
        role: RoleName,
        model: str,
        output_models: list[str],
        tools: list[Callable[..., Any]] | None,
    ) -> Callable[..., Any]:
        """Return a callable(inputs) -> dict that performs one or more LLM rounds.

        - If mock_mode: returns deterministic mock output matching each schema in output_models
        - If real: calls self.llm_client once per schema, merges results into one dict.
          The first schema's parsed result is stored under the "output" key (back-compat);
          every schema including the first is also stored under its own name.
        """
        if self.mock_mode:
            return self._build_mock_kickoff(role, output_models)
        if self.llm_client is None:
            raise ValueError("real kickoff requires llm_client; pass mock_mode=True for tests")
        return self._build_real_kickoff(role, model, output_models, tools)

    def _build_mock_kickoff(self, role: RoleName, output_models: list[str]) -> Callable[..., Any]:
        """Deterministic mock kickoff for tests (D0-7 5-role kickoff test path)."""

        def mock_kickoff(inputs: Any) -> dict[str, Any]:
            base: dict[str, Any] = {"role": role, "inputs_echo": inputs, "mock": True}
            for schema_name in output_models:
                base[schema_name] = self._mock_output_for_schema(schema_name)
            # Back-compat: also expose the first schema under "output"
            if output_models:
                base["output"] = base[output_models[0]]
            return base

        return mock_kickoff

    def _mock_output_for_schema(self, schema_name: str) -> dict[str, Any]:
        """Deterministic mock payload for one schema. Used by mock kickoff + tests."""
        if schema_name == "proposal":
            return {
                "title": "Mock Proposal",
                "requirement_background": "mock",
                "core_objective": "mock",
                "expected_outputs": ["mock.md"],
                "priority": "P2",
                "modules": ["mock-module"],
                "impact_scope": "mock",
                "recommended_path": "SDDP全流程",
                "recommendation_reason": "mock",
                "impact": {
                    "dependents": [], "data_compatibility": "mock",
                    "kg_confidence": "medium", "kg_coverage_note": "mock",
                },
            }
        if schema_name == "delta_spec":
            return {
                "title": "Mock DeltaSpec",
                "scope": {"modules": ["mock-module"], "files": ["mock.py"]},
                "interfaces": {"new": ["mock"], "changed": [], "deprecated": []},
                "impact": {
                    "dependents": [], "data_compatibility": "mock",
                    "kg_confidence": "medium", "kg_coverage_note": "mock",
                },
                "constraints": ["mock constraint"],
            }
        if schema_name == "delta_design":
            return {
                "title": "Mock DeltaDesign",
                "decisions": ["mock decision"],
                "data_flow": "mock data flow",
                "algorithms": ["mock algorithm"],
                "modules": [{"module": "mock", "responsibility": "mock", "dependencies": []}],
                "exception_handling": ["mock exception handling"],
                "naming_convention": "mock", "directory_structure": "mock",
                "code_style": "mock", "ci_checks": "mock",
            }
        if schema_name == "architecture_research":
            return {
                "title": "Mock ArchitectureResearch",
                "methodology": "mock methodology",
                "current_state": "mock current state",
                "dependency_chain": ["mock dep"],
                "extracted_constraints": ["mock constraint"],
                "kg_citations": [{
                    "query_method": "find_callers",
                    "query_args": {"symbol_id": "mock"},
                    "answer_summary": "mock answer",
                    "confidence": "high",
                    "coverage_note": "mock coverage",
                }],
                "pcm_adr_references": [],
            }
        return {"mock": True, "schema": schema_name}

    def _build_real_kickoff(
        self,
        role: RoleName,
        model: str,
        output_models: list[str],
        tools: list[Callable[..., Any]] | None,
    ) -> Callable[..., Any]:
        """Real kickoff: call LLM once per output schema, merge results into one dict.

        For multi-schema roles (e.g. architect producing delta_spec + delta_design
        + architecture_research), each schema is a separate LLM round so that
        response_format enforcement + cost metering stay per-schema. The merged
        result is `{"output": <first schema>, <schema_name>: <parsed>, ...}`.
        """
        from ..schemas import SCHEMA_REGISTRY

        def _one_llm_round(schema_name: str | None, inputs: dict[str, Any]) -> tuple[dict[str, Any], bool, int, int]:
            """Run one LLM round for an optional schema; return (result_dict, first_try_ok, prompt_tokens, completion_tokens).

            D1-11 integration: messages are passed through `sddp.security.prefilter.scrub`
            before sending to the LLM; the response content is passed through `restore`
            before parsing. This is the SINGLE chokepoint — no other code path may
            call `self.llm_client.chat.completions.create` (per security-compliance spec
            Requirement: 不允许绕过 prefilter).
            """
            from ..security.prefilter import scrub, restore

            backstory = BACKSTORIES[role]
            user_input = self._format_user_input(role, inputs, schema_name)

            # Scrub all message parts (system, user, schema-hint) before LLM send.
            # Backstory is project-controlled (low risk) but scrubbed anyway for
            # defense-in-depth (cheap; regex over ~1KB text).
            scrubbed_backstory = scrub(backstory)
            scrubbed_user = scrub(user_input)
            messages: list[dict[str, Any]] = [
                {"role": "system", "content": scrubbed_backstory.scrubbed_text},
                {"role": "user", "content": scrubbed_user.scrubbed_text},
            ]
            # Combined mapping for restore on the way back
            restore_mapping: dict[str, str] = {}
            restore_mapping.update(scrubbed_backstory.mapping)
            restore_mapping.update(scrubbed_user.mapping)

            kwargs: dict[str, Any] = {"model": model, "messages": messages}
            if schema_name:
                if _provider_supports_strict_json_schema(model):
                    # OpenAI gpt-4o-* strict schema (Tier-S per analysis/04)
                    kwargs["response_format"] = {"type": "json_schema", "json_schema": {"name": schema_name, "schema": SCHEMA_REGISTRY[schema_name].model_json_schema()}}
                else:
                    # DeepSeek-style providers: only JSON mode, no schema enforcement.
                    # Prompt MUST request the schema explicitly; pydantic validates client-side.
                    schema_hint = SCHEMA_REGISTRY[schema_name].model_json_schema()
                    schema_hint_str = __import__('json').dumps(schema_hint, ensure_ascii=False)
                    scrubbed_hint = scrub(schema_hint_str)
                    restore_mapping.update(scrubbed_hint.mapping)
                    messages.append({
                        "role": "system",
                        "content": (
                            f"Reply with a SINGLE JSON object conforming to this JSON Schema (no prose, no markdown):\n"
                            f"{scrubbed_hint.scrubbed_text}"
                        ),
                    })
                    kwargs["response_format"] = {"type": "json_object"}

            response = self.llm_client.chat.completions.create(**kwargs)
            usage = getattr(response, "usage", None)
            prompt_tokens = getattr(usage, "prompt_tokens", 0) if usage else 0
            completion_tokens = getattr(usage, "completion_tokens", 0) if usage else 0

            content = response.choices[0].message.content
            # Restore placeholders BEFORE pydantic parsing — the LLM should have
            # produced JSON with placeholders; we substitute originals back so
            # downstream schema validation sees real content.
            if restore_mapping:
                content = restore(content, restore_mapping)
            structured_first_try = True
            try:
                if schema_name:
                    parsed = SCHEMA_REGISTRY[schema_name].model_validate_json(content)
                    result = parsed.model_dump()
                else:
                    result = {"raw": content}
            except Exception as e:
                structured_first_try = False
                logger.warning("role %s schema %s validation failed: %s", role, schema_name, e)
                result = {"_parse_error": str(e), "raw": content}
            return result, structured_first_try, prompt_tokens, completion_tokens

        def real_kickoff(inputs: Any) -> dict[str, Any]:
            inputs_dict = inputs if isinstance(inputs, dict) else {"input": str(inputs)}
            merged: dict[str, Any] = {"role": role}
            schemas_to_run: list[str | None] = list(output_models) or [None]
            for schema_name in schemas_to_run:
                result, first_try, ptoks, ctoks = _one_llm_round(schema_name, inputs_dict)
                # Cost-meter under the role name (each LLM round tracked separately)
                self.cost_meter.record_call(
                    agent=role,
                    model=model,
                    prompt_tokens=ptoks,
                    completion_tokens=ctoks,
                    structured_output_first_try=first_try,
                )
                if schema_name:
                    merged[schema_name] = result
                else:
                    merged["output"] = result
            # Back-compat: expose the first schema under "output" key
            if output_models:
                merged["output"] = merged[output_models[0]]
            return merged

        return real_kickoff

    def _format_user_input(self, role: RoleName, inputs: dict[str, Any], schema_name: str | None = None) -> str:
        """Format the user input message for the LLM based on role + inputs + target schema."""
        # Simple formatter for MVP; richer templates in Dev-Phase 2
        if role == "requirement_officer":
            return f"解析以下用户需求并产出结构化 proposal：\n\n{inputs.get('requirement', '')}"
        if role == "architect":
            # Schema-aware prompt: each architect output gets its own framing.
            proposal_text = inputs.get('proposal', '')
            if isinstance(proposal_text, dict):
                proposal_text = __import__('json').dumps(proposal_text, ensure_ascii=False, indent=2)
            if schema_name == "delta_design":
                return (
                    "基于以下 delta-spec / proposal 产出 delta-design（含模块划分、关键决策、数据流、异常处理）：\n\n"
                    f"{proposal_text}"
                )
            if schema_name == "architecture_research":
                return (
                    "基于以下 proposal 产出 architecture-research（含知识图查询引用 kg_citations，"
                    "每条 MUST 含 confidence 字段 high/medium/low；含覆盖率说明 coverage_note）：\n\n"
                    f"{proposal_text}"
                )
            # delta_spec (default for architect)
            return f"基于以下 proposal 产出 delta-spec（含影响面分析 + KG 置信度）：\n\n{proposal_text}"
        if role == "orchestrator":
            return f"对以下方案做可行性判定：\n\n{inputs.get('plan', '')}"
        if role == "executor":
            return f"基于以下 delta-design 产出代码建议（不写文件）：\n\n{inputs.get('design', '')}"
        if role == "code_asset_manager":
            return f"处理以下查询：\n\n{inputs}"
        return str(inputs)
