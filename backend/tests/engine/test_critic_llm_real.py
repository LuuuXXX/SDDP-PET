"""Real-LLM critic output-parsing validation (D2-1 / §8 highest risk).

Per `analysis/crewai-technical-research.md` §8, the **#1 Phase-2 risk** is
"LLM output parsing fragility" — the `_parse_criticisms` step. This test calls
the REAL DeepSeek API with a critic prompt and asserts the response parses into
valid ``CriticismPoint`` objects with valid severities. If this passes, real-LLM
adversarial confrontation is feasible (the loop logic is already verified by
the mock smoke tests in ``test_confrontation_smoke.py``).

Skipped without OPENAI_API_KEY (real-API e2e, NOT regular CI). Run manually:
    $env:OPENAI_API_KEY="sk-..."; $env:OPENAI_BASE_URL="https://api.deepseek.com/v1"
    $env:SDDP_LLM_MODEL="deepseek-chat"
    pytest tests/engine/test_critic_llm_real.py -v -s -m e2e
"""

from __future__ import annotations

import json
import os

import pytest
from openai import OpenAI

from sddp.engine.flows.phase_1_state import CriticismPoint

requires_llm = pytest.mark.skipif(
    not os.environ.get("OPENAI_API_KEY"),
    reason="real-LLM e2e requires OPENAI_API_KEY (design decision 8; not regular CI)",
)


CRITIC_SYSTEM = (
    "你是严格的挑评师，从【性能】维度质疑架构师的方案。每条质疑必须有据（引用方案文本或指出风险）。"
    "只质疑不提案。只输出 JSON，不要任何额外文字或 markdown：\n"
    '{"criticism_points":[{"id":"c1","dimension":"性能","content":"质疑内容","severity":"高|中|低"}]}'
)

SAMPLE_DESIGN = (
    "方案：配置变更时全量重载配置文件，后台线程每秒轮询。\n"
    "实现：while True:\\n  if config_changed(): reload_all()\\n  sleep(1)"
)


@requires_llm
@pytest.mark.e2e
def test_real_deepseek_critic_output_parses_to_criticism_points() -> None:
    """The §8 #1 risk: can a real DeepSeek critic output be parsed into CriticismPoint?"""
    model = os.environ.get("SDDP_LLM_MODEL", "deepseek-chat")
    client = OpenAI()

    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": CRITIC_SYSTEM},
            {"role": "user", "content": f"请质疑以下方案：\n{SAMPLE_DESIGN}"},
        ],
        response_format={"type": "json_object"},
    )
    content = response.choices[0].message.content or ""

    # Step 1: raw JSON must parse (the first fragile boundary)
    data = json.loads(content)
    raw_points = data.get("criticism_points", [])
    assert isinstance(raw_points, list), f"criticism_points not a list: {content[:200]}"

    # Step 2: each item must construct a valid CriticismPoint (the §8 _parse step)
    points = [
        CriticismPoint(
            id=p.get("id", f"c{i}"),
            dimension=p.get("dimension", "性能"),
            content=p.get("content", ""),
            severity=p.get("severity", "中"),
        )
        for i, p in enumerate(raw_points)
        if isinstance(p, dict)
    ]
    assert len(points) >= 1, f"critic produced no parseable points: {content[:200]}"

    # Step 3: severities are in the convergence engine's accepted vocabulary
    valid_severities = {"高", "中", "低"}
    for p in points:
        assert p.severity in valid_severities, (
            f"invalid severity {p.severity!r}: {p.content[:80]}"
        )

    # Diagnostics (visible with -s)
    usage = getattr(response, "usage", None)
    total_tokens = getattr(usage, "total_tokens", "?") if usage else "?"
    print(
        f"\n[critic e2e] model={model} points={len(points)} tokens={total_tokens} "
        f"first='{points[0].content[:80]}' severity={points[0].severity}"
    )
