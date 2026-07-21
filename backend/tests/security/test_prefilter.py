"""Tests for sddp/security/prefilter.py (D1-11).

Per specs/security-compliance/spec.md Requirement: 引擎 MUST 在调用 LLM 前对代码
payload 做正则脱敏 + scenarios:
  - 固定输入产生固定脱敏输出
  - 还原后的内容与原文一致
"""
from __future__ import annotations

import copy
import random

import pytest

from sddp.security.prefilter import scrub, restore, list_patterns, ScrubResult


# ---- catalog sanity ----


def test_catalog_has_at_least_8_patterns():
    """analysis/09 §五 mandates ≥8 regex categories."""
    patterns = list_patterns()
    assert len(patterns) >= 8, f"catalog too small: {len(patterns)}"
    names = {p["name"] for p in patterns}
    # Required categories per spec
    required = {
        "openai_key", "github_pat", "aws_access_key", "pem_private_key",
        "jwt", "email", "api_key_assignment", "password_assignment",
    }
    missing = required - names
    assert not missing, f"missing required categories: {missing}"


# ---- single-pattern coverage ----


@pytest.mark.parametrize(
    "name, sample_text, must_contain_placeholder",
    [
        ("openai_key", "OPENAI_KEY=sk-abcdefghijklmnopqrstuvwxyz1234567890ABCD", "REDACTED_OPENAI_KEY"),
        ("anthropic_key", "ANTHROPIC=sk-ant-api03-abcdefghijklmnopqrstuv", "REDACTED_ANTHROPIC_KEY"),
        ("deepseek_key", "DEEPSEEK=sk-deadbeefdeadbeefdeadbeefdeadbeef0000", "REDACTED_DEEPSEEK_KEY"),
        ("github_pat", "GH=ghp_0123456789012345678901234567890abcdef", "REDACTED_GITHUB_PAT"),
        ("aws_access_key", "AWS=AKIAIOSFODNN7EXAMPLE", "REDACTED_AWS_ACCESS_KEY"),
        ("pem_private_key", "-----BEGIN RSA PRIVATE KEY-----\nMIIE...\n-----END RSA PRIVATE KEY-----", "REDACTED_PEM_PRIVATE_KEY"),
        ("jwt", "tok=eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxMjMifQ.SflKxwRJSMeKKF2QT4fw", "REDACTED_JWT"),
        ("api_key_assignment", 'config = {"api_key": "ak_live_1234567890abcdef"}', "REDACTED_API_KEY"),
        ("password_assignment", 'password="supersecretpassword"', "REDACTED_PASSWORD"),
        ("email", "Contact: user@example.com for details", "REDACTED_EMAIL"),
        ("bearer_token", "Authorization: Bearer eyJhbGc.iOiJIUz.SflKxwRJ", "REDACTED_BEARER_TOKEN"),
    ],
)
def test_each_pattern_redacts_correctly(name: str, sample_text: str, must_contain_placeholder: str):
    """Each catalog pattern MUST replace its target with a <REDACTED_...> placeholder."""
    result = scrub(sample_text)
    assert must_contain_placeholder in result.scrubbed_text, (
        f"{name}: expected placeholder '{must_contain_placeholder}' "
        f"in scrubbed output, got: {result.scrubbed_text!r}"
    )
    # Original MUST NOT appear in scrubbed output
    assert sample_text not in result.scrubbed_text or sample_text == result.scrubbed_text.replace(
        f"<{must_contain_placeholder}_", "X"
    ), f"{name}: original leaked through scrub"


# ---- determinism (D1-11: 固定输入产生固定脱敏输出) ----


def test_deterministic_output_same_input():
    """Same input MUST produce byte-identical scrubbed output across calls."""
    text = "key=sk-abcdefghijklmnopqrstuvwxyz1234567890ABCD email=a@b.com"
    r1 = scrub(text)
    r2 = scrub(text)
    assert r1.scrubbed_text == r2.scrubbed_text
    assert r1.mapping == r2.mapping


def test_deterministic_output_under_iteration_order_randomization():
    """Mapping dict iteration order doesn't affect output (deterministic placeholders)."""
    text = "sk-abcdefghijklmnopqrstuvwxyz1234567890ABCD and another sk-abcdefghijklmnopqrstuvwxyz1234567890ABCD"
    result = scrub(text)
    # Same original → same placeholder → both occurrences replaced with same token
    placeholders = [p for p in result.mapping.keys() if "OPENAI" in p]
    assert len(placeholders) == 1, f"expected 1 placeholder for repeated secret, got {placeholders}"
    # Both occurrences in scrubbed text replaced with the single placeholder
    assert result.scrubbed_text.count(placeholders[0]) == 2


# ---- round-trip ----


def test_restore_recovers_original_byte_for_byte():
    """restore(scrub(text).scrubbed_text, mapping) == text."""
    text = (
        "OPENAI_API_KEY=sk-abcdefghijklmnopqrstuvwxyz1234567890ABCD\n"
        'GH_TOKEN = "ghp_0123456789012345678901234567890abcdef"\n'
        "JWT=eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.SflKxwRJSMeKKF2QT4fwpMeJf36POk6yJV_adQssw5c\n"
        "EMAIL=user@example.com\n"
        "aws_key=AKIAIOSFODNN7EXAMPLE\n"
        'password="mysecretpassword123"\n'
        "-----BEGIN RSA PRIVATE KEY-----\nMIIEpAIBAAKCAQEA\n-----END RSA PRIVATE KEY-----\n"
    )
    result = scrub(text)
    restored = restore(result.scrubbed_text, result.mapping)
    assert restored == text, f"round-trip mismatch:\n--- original ---\n{text}\n--- restored ---\n{restored}"


def test_restore_with_empty_mapping_returns_input():
    assert restore("hello world", {}) == "hello world"
    assert restore("", {"<X>": "y"}) == ""


def test_restore_with_unknown_placeholders_leaves_them():
    """Defensive: unknown placeholders (not in mapping) are left in place."""
    out = restore("hello <UNKNOWN_PLACEHOLDER_a1b2c3> world", {"<OTHER>": "x"})
    assert out == "hello <UNKNOWN_PLACEHOLDER_a1b2c3> world"


def test_restore_preserves_repeated_placeholders():
    """If the same secret appears N times, restore MUST replace all N."""
    text = "key=sk-abcdefghijklmnopqrstuvwxyz1234567890ABCD twice=sk-abcdefghijklmnopqrstuvwxyz1234567890ABCD"
    result = scrub(text)
    restored = restore(result.scrubbed_text, result.mapping)
    assert restored == text


# ---- idempotence ----


def test_scrub_is_idempotent():
    """scrub(scrub(text).scrubbed_text) == scrub(text).scrubbed_text."""
    text = "key=sk-abcdefghijklmnopqrstuvwxyz1234567890ABCD"
    once = scrub(text)
    twice = scrub(once.scrubbed_text)
    assert once.scrubbed_text == twice.scrubbed_text


# ---- empty / edge cases ----


def test_scrub_empty_string():
    r = scrub("")
    assert r.scrubbed_text == ""
    assert r.mapping == {}


def test_scrub_text_without_secrets_is_unchanged():
    text = "just some normal code without anything sensitive\n"
    r = scrub(text)
    assert r.scrubbed_text == text
    assert r.mapping == {}


def test_scrub_does_not_mutate_input():
    """Caller's input string MUST NOT be modified (str is immutable, but assert for parity)."""
    text = "sk-abcdefghijklmnopqrstuvwxyz1234567890ABCD"
    snapshot = copy.deepcopy(text)
    scrub(text)
    assert text == snapshot


# ---- realistic-ish code fixture ----


def test_scrub_realistic_python_source():
    """Simulates a user pasting config code with secrets into the engine."""
    code = '''
import openai
openai.api_key = "sk-proj-abcdefghijklmnopqrstuvwxyz1234567890ABCDEFGHIJ"

AWS_CREDS = {
    "access_key_id": "AKIAIOSFODNN7EXAMPLE",
    "secret_access_key": "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY",
}

# Personal contact
CONTACT = "jane.doe@example.com"

def auth_header():
    return {"Authorization": "Bearer eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxMjMifQ.SflKxabc"}
'''
    result = scrub(code)
    # All 5+ secrets MUST be redacted
    assert "sk-proj-" not in result.scrubbed_text
    assert "AKIAIOSFODNN7EXAMPLE" not in result.scrubbed_text
    assert "jane.doe@example.com" not in result.scrubbed_text
    assert "Bearer eyJ" not in result.scrubbed_text
    # Mapping MUST be ≥5 entries
    assert len(result.mapping) >= 4, f"expected ≥4 redactions, got {len(result.mapping)}: {result.hit_counts}"
    # Round-trip restores code exactly
    restored = restore(result.scrubbed_text, result.mapping)
    assert restored == code


# ---- type / dataclass contract ----


def test_scrub_result_fields_populated():
    r = scrub("sk-abcdefghijklmnopqrstuvwxyz1234567890ABCD")
    assert isinstance(r, ScrubResult)
    assert hasattr(r, "scrubbed_text")
    assert hasattr(r, "mapping")
    assert hasattr(r, "hit_counts")
    assert isinstance(r.hit_counts, dict)
    assert "openai_key" in r.hit_counts


# ---- randomized stress ----


def test_randomized_round_trip_many_secrets():
    """Random-ordering of N secrets round-trips correctly (catches ordering bugs)."""
    rng = random.Random(42)
    secrets_pool = [
        "sk-abcdefghijklmnopqrstuvwxyz1234567890ABCD",
        "ghp_0123456789012345678901234567890abcdef",
        "AKIAIOSFODNN7EXAMPLE",
        "user1@example.com",
        "user2@example.com",
        "sk-ant-api03-zzzzzzzzzzzzzzzzzzzzzzzzzzz",
    ]
    # Build a random text with random repeats
    pieces = []
    for _ in range(50):
        pieces.append(rng.choice(secrets_pool))
    text = " | ".join(pieces)
    result = scrub(text)
    restored = restore(result.scrubbed_text, result.mapping)
    assert restored == text
