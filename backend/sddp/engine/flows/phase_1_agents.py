"""Real-LLM agent builders for the Phase 1 confrontation flow (D2-1).

Per `analysis/crewai-technical-research.md` §8 Step 2 + the
`agents.py::_build_real_kickoff` pattern. Each builder returns an ``AgentFn``
(``dict -> dict``) that calls the LLM with a role-specific prompt and parses the
JSON output. This is the production wire-up for ``Phase1ConfrontationFlow``
(tests inject mock AgentFns; production injects these via
``build_real_confrontation_agents``).

Call pattern (validated by ``test_critic_llm_real.py`` for the critic):
  - DeepSeek (Tier-B): ``response_format={'type':'json_object'}`` + schema hint
    in the prompt; pydantic/direct-JSON parse client-side.
  - Every LLM call goes through ``sddp.security.prefilter.scrub`` on the way out
    and ``restore`` on the way back (D1-11 single-chokepoint rule).

Cost is metered per call when a ``cost_meter`` is supplied.
"""

from __future__ import annotations

import json
import logging
from typing import Any, Callable

from ...security.prefilter import scrub, restore
from .phase_1_state import CriticismPoint

logger = logging.getLogger(__name__)

AgentFn = Callable[[dict[str, Any]], dict[str, Any]]


def _llm_call(
    client: Any, model: str, system: str, user: str, schema_hint: str
) -> tuple[str, int, int]:
    """One LLM round: scrub → create(json_object) → restore → (content, ptoks, ctoks)."""
    s_sys = scrub(system)
    s_user = scrub(user)
    mapping: dict[str, str] = {}
    mapping.update(s_sys.mapping)
    mapping.update(s_user.mapping)
    messages = [
        {"role": "system", "content": s_sys.scrubbed_text},
        {
            "role": "system",
            "content": f"只输出单个 JSON 对象(no prose/markdown):\n{schema_hint}",
        },
        {"role": "user", "content": s_user.scrubbed_text},
    ]
    resp = client.chat.completions.create(
        model=model, messages=messages, response_format={"type": "json_object"}
    )
    content = resp.choices[0].message.content or ""
    if mapping:
        content = restore(content, mapping)
    usage = getattr(resp, "usage", None)
    pt = getattr(usage, "prompt_tokens", 0) if usage else 0
    ct = getattr(usage, "completion_tokens", 0) if usage else 0
    return content, pt, ct


def _record(cost_meter: Any, agent: str, model: str, pt: int, ct: int) -> None:
    if cost_meter is not None:
        try:
            cost_meter.record_call(
                agent=agent,
                model=model,
                prompt_tokens=pt,
                completion_tokens=ct,
                structured_output_first_try=True,
            )
        except Exception as e:  # metering is non-fatal
            logger.warning("cost_meter.record_call(%s) failed: %s", agent, e)


# ---- architect ----

_ARCH_SYS = (
    "你是经验丰富的架构师。基于需求 + 代码库研究 + 对抗反馈，产出经得起检验的 "
    "delta-spec 与 delta-design。每项决策标注理由和依据。只输出 JSON。"
)
_ARCH_HINT = (
    '{"architecture_research":"string","delta_spec":"string","delta_design":"string"}'
)


def build_real_architect(client: Any, model: str, cost_meter: Any = None) -> AgentFn:
    def architect(inputs: dict[str, Any]) -> dict[str, Any]:
        content, pt, ct = _llm_call(
            client,
            model,
            _ARCH_SYS,
            (
                f"需求：{inputs.get('proposal', '')}\n"
                f"研究：{str(inputs.get('research', ''))[:500]}\n"
                f"前轮质疑：{str(inputs.get('criticism_feedback', '首轮设计，无前轮质疑'))[:500]}\n"
                f"产出方案 JSON。"
            ),
            _ARCH_HINT,
        )
        _record(cost_meter, "architect", model, pt, ct)
        try:
            d = json.loads(content)
            return {
                "delta_spec": d.get("delta_spec", ""),
                "delta_design": d.get("delta_design", ""),
                "architecture_research": d.get("architecture_research", ""),
            }
        except json.JSONDecodeError:
            # unparseable → treat raw as the design (loop still proceeds)
            return {
                "delta_spec": content,
                "delta_design": content,
                "architecture_research": content,
            }

    return architect


# ---- critic ----

_CRITIC_SYS = (
    "你是严格的挑评师。从指定维度质疑架构师方案。每条质疑必须有据（引用方案文本或指出风险）。"
    "只质疑不提案。只输出 JSON。"
)
_CRITIC_HINT = '{"criticism_points":[{"id":"c1","dimension":"性能","content":"质疑内容","severity":"高|中|低"}]}'


def build_real_critic(client: Any, model: str, cost_meter: Any = None) -> AgentFn:
    def critic(inputs: dict[str, Any]) -> dict[str, Any]:
        dim = inputs.get("dimension", "性能")
        content, pt, ct = _llm_call(
            client,
            model,
            _CRITIC_SYS,
            (
                f"维度：{dim}\n需求：{str(inputs.get('proposal', ''))[:300]}\n"
                f"方案：\n{str(inputs.get('design', ''))[:1000]}\n"
                f"从【{dim}】维度质疑，输出 JSON。"
            ),
            _CRITIC_HINT,
        )
        _record(cost_meter, "critic", model, pt, ct)
        try:
            pts = json.loads(content).get("criticism_points", [])
        except json.JSONDecodeError:
            pts = []
        out = [
            {
                "id": p.get("id", f"c{i}"),
                "dimension": p.get("dimension", dim),
                "content": p.get("content", ""),
                "severity": p.get("severity", "中"),
            }
            for i, p in enumerate(pts)
            if isinstance(p, dict)
        ]
        if not out:
            out = [
                {
                    "id": "c-fallback",
                    "dimension": dim,
                    "content": "critic 无有效输出",
                    "severity": "中",
                }
            ]
        return {"criticism_points": out}

    return critic


# ---- empiricist ----

_EMP_SYS = (
    "你是实证师。为挑评师的质疑提供证据支撑（快速原型验证 / 边界分析 / 依赖检查）。"
    "只输出 JSON。"
)
_EMP_HINT = '{"evidence":"string","verdict":"成立|不成立|部分成立"}'


def build_real_empiricist(client: Any, model: str, cost_meter: Any = None) -> AgentFn:
    def empiricist(inputs: dict[str, Any]) -> dict[str, Any]:
        content, pt, ct = _llm_call(
            client,
            model,
            _EMP_SYS,
            (
                f"质疑：{str(inputs.get('criticism_point', ''))[:400]}\n"
                f"维度：{inputs.get('dimension', '')}\n"
                f"方案：\n{str(inputs.get('design', ''))[:800]}\n"
                f"提供实证，输出 JSON。"
            ),
            _EMP_HINT,
        )
        _record(cost_meter, "empiricist", model, pt, ct)
        try:
            d = json.loads(content)
            return {"evidence": d.get("evidence", ""), "verdict": d.get("verdict", "")}
        except json.JSONDecodeError:
            return {"evidence": content, "verdict": ""}

    return empiricist


# ---- orchestrator (arbitrator) ----

_ORCH_SYS = (
    "你是调度官，裁决对抗中未收敛的中/低质疑点。裁决必须引用实证报告或方案证据。"
    "高严重度质疑不得无据驳回。只输出 JSON。"
)
_ORCH_HINT = '{"decisions":[{"id":"c1","decision":"采纳|驳回","basis":"裁决依据"}]}'


def build_real_orchestrator(client: Any, model: str, cost_meter: Any = None) -> AgentFn:
    def orchestrator(inputs: dict[str, Any]) -> dict[str, Any]:
        content, pt, ct = _llm_call(
            client,
            model,
            _ORCH_SYS,
            (
                f"未收敛质疑：\n{str(inputs.get('criticism_points', ''))[:800]}\n"
                f"实证报告：\n{str(inputs.get('evidence_reports', ''))[:600]}\n"
                f"逐条裁决，输出 JSON。"
            ),
            _ORCH_HINT,
        )
        _record(cost_meter, "orchestrator", model, pt, ct)
        try:
            decs = json.loads(content).get("decisions", [])
        except json.JSONDecodeError:
            decs = []
        return {
            "decisions": [
                {
                    "id": d.get("id"),
                    "decision": d.get("decision", "采纳"),
                    "basis": d.get("basis", ""),
                }
                for d in decs
                if isinstance(d, dict) and d.get("id")
            ]
        }

    return orchestrator


def build_real_confrontation_agents(
    client: Any, model: str, cost_meter: Any = None
) -> dict[str, AgentFn]:
    """Build all 4 real agents for ``Phase1ConfrontationFlow``."""
    return {
        "architect": build_real_architect(client, model, cost_meter),
        "critic": build_real_critic(client, model, cost_meter),
        "empiricist": build_real_empiricist(client, model, cost_meter),
        "orchestrator": build_real_orchestrator(client, model, cost_meter),
    }


__all__ = [
    "AgentFn",
    "build_real_architect",
    "build_real_critic",
    "build_real_empiricist",
    "build_real_orchestrator",
    "build_real_confrontation_agents",
]
