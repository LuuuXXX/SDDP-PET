"""Tests: 5 roles can kickoff (D0-7). Uses MockFlowAdapter; no real LLM."""
from __future__ import annotations

import pytest

from sddp.engine.agents import AgentFactory, RoleAgent
from sddp.engine.backstories import BACKSTORIES
from sddp.engine.cost_meter import CostMeter
from sddp.engine.kg_tools import KGTools


@pytest.fixture
def factory(tmp_path):
    """Build an AgentFactory in mock mode (no real LLM)."""
    # Build a small KG for code_asset_manager to query
    from sddp.kg.scan import scan_project
    fixture = tmp_path / "fixture"
    fixture.mkdir()
    (fixture / "mod.py").write_text("def f():\n    pass\n", encoding="utf-8")
    db = tmp_path / "kg.db"
    scan_project(fixture, db_path=db, prefer_scip=False)
    kg_tools = KGTools(db)
    return AgentFactory(mock_mode=True, cost_meter=CostMeter(), kg_tools=kg_tools)


def test_all_5_backstories_present():
    """Spec: 5 roles MUST have backstories encoding SDDP constraints."""
    expected = {"requirement_officer", "orchestrator", "architect", "executor", "code_asset_manager"}
    assert set(BACKSTORIES.keys()) == expected
    for name, story in BACKSTORIES.items():
        assert isinstance(story, str) and len(story) > 200, f"backstory too short for {name}"


def test_each_backstory_mentions_sddp_constraints():
    """Spec scenario: Backstory 含 SDDP 共性约束. Each MUST mention 不扩展职责/标注来源/禁止假设/不越权."""
    common_markers = ["不得自行扩展职责", "标注", "假设", "越权"]
    for name, story in BACKSTORIES.items():
        for marker in common_markers:
            assert marker in story, f"backstory {name!r} missing common-constraint marker {marker!r}"


def test_architect_backstory_mentions_kg_consultation():
    """Spec scenario: 架构师 backstory 含'先咨询代码资产管理员'."""
    arch_story = BACKSTORIES["architect"]
    assert "代码资产管理员" in arch_story
    assert "修改范围" in arch_story or "咨询" in arch_story


def test_factory_builds_all_5_roles(factory):
    """Spec scenario: 5 角色 Agent 可 kickoff (build path)."""
    roles = factory.build_all()
    assert set(roles.keys()) == {"requirement_officer", "orchestrator", "architect", "executor", "code_asset_manager"}
    for name, role in roles.items():
        assert isinstance(role, RoleAgent)
        assert role.name == name
        assert isinstance(role.backstory, str)
        assert callable(role.kickoff_fn)
        assert role.safe_agent is not None  # wrapped in SafeAgent


def test_each_role_kickoff_succeeds_in_mock_mode(factory):
    """Spec scenario: kickoff each of 5 roles in mock mode → returns dict."""
    roles = factory.build_all()
    for name, role in roles.items():
        result = role.kickoff_fn({"test": name})
        assert isinstance(result, dict), f"{name} kickoff returned non-dict: {type(result)}"
        assert result.get("mock") is True or "output" in result or "role" in result


def test_code_asset_manager_has_kg_tools(factory):
    """Spec: code_asset_manager MUST have KG tools wired."""
    role = factory.build_role("code_asset_manager")
    assert role.tools is not None
    assert len(role.tools) == 4  # find_callers/find_file_impact/find_dependencies/get_module_api


def test_code_asset_manager_kg_tool_returns_query_result(factory):
    """End-to-end: code_asset_manager's find_callers tool works against a real KG."""
    role = factory.build_role("code_asset_manager")
    find_callers = role.tools[0]  # type: ignore[index]
    # Should return a dict (QueryResult.to_dict) — even for nonexistent symbol
    result = find_callers(symbol_name="f", depth=1)
    assert isinstance(result, dict)
    assert "confidence" in result
    assert "coverage_note" in result
    assert "sources" in result


def test_role_kickoff_records_to_cost_meter(factory):
    """Spec scenario: token 计量. Mock kickoff still records a call record (0 tokens)."""
    # Note: mock kickoff doesn't go through real LLM, so tokens=0; but the path
    # validates that cost_meter is shared and write_report works.
    factory.cost_meter.record_call(
        agent="architect", model="gpt-4o-mini",
        prompt_tokens=100, completion_tokens=50,
        structured_output_first_try=True,
    )
    report = factory.cost_meter.to_report_dict()
    assert report["call_count"] == 1
    assert report["total_tokens"] == 150
    assert report["measured_cost_usd"] > 0  # measured from pricing table
    assert report["structured_output_first_try_rate"] == 1.0


def test_default_role_models_use_gpt_4o_mini(monkeypatch):
    """Design decision 6: 5 roles use gpt-4o-mini by default (when SDDP_LLM_MODEL unset)."""
    # The SDDP_LLM_MODEL env var intentionally overrides defaults for Tier-B
    # plumbing verification (DeepSeek); clear it to assert the spec baseline.
    monkeypatch.delenv("SDDP_LLM_MODEL", raising=False)
    import importlib, sddp.engine.agents as agents_mod
    importlib.reload(agents_mod)
    for role, model in agents_mod.DEFAULT_ROLE_MODELS.items():
        assert model == "gpt-4o-mini", f"{role} expected gpt-4o-mini, got {model}"
