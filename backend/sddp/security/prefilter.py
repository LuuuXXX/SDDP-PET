"""Code pre-filter for LLM payload desensitization (Dev-Phase 1 D1-11).

Per `specs/security-compliance/spec.md` Requirement: 引擎 MUST 在调用 LLM 前对代码
payload 做正则脱敏. Per `analysis/09` §五: regex catalog approach (NOT cryptographic
redaction); mapping kept in memory only; reverse-substituted on LLM return.

Public API:
    scrub(text: str) -> ScrubResult
    restore(text: str, mapping: dict[str, str]) -> str

Where ScrubResult is a dataclass with:
    scrubbed_text: str — the redacted text (safe to send to LLM)
    mapping: dict[str, str] — placeholder → original (kept in memory; never written to disk)

Integration point: `SafeAgent.kickoff` MUST call `scrub` on its input payload
before calling `llm_client.chat.completions.create`, and `restore` on the
response content. See `sddp/safe_agent/wrapper.py`.

Design notes:
- Placeholders are deterministic per-original (hash-based) so that two
  occurrences of the same secret produce the same placeholder (helps the LLM
  reason about repetition) AND a fixed input produces byte-identical scrubbed
  output (D1-11 contract: "固定输入产生固定脱敏输出").
- Catalog is data-driven: list of (name, compiled_regex, placeholder_prefix).
- The catalog is intentionally NON-exhaustive; per `analysis/09` it is a
  pragmatic filter against accidental leaks, NOT a security boundary against
  adversarial inputs. Accepted risk AR-5 (see `design.md` Risks).
"""
from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field


# ---- regex catalog (analysis/09 §五) ----------------------------------------
# Each entry: (name, pattern, placeholder_prefix).
# Patterns use named-position captures; the whole match is replaced.
# Order matters: more specific patterns first (e.g., GitHub PAT before generic
# "api_key=" catch-all).

_CATALOG: list[tuple[str, str, str]] = [
    # ---- Provider-specific API keys (high-signal) ----
    # Order matters: more-specific provider prefixes (anthropic/deepseek) MUST
    # come BEFORE the generic openai `sk-...` pattern, otherwise the latter
    # would consume `sk-ant-...` and `sk-<32 hex>` first.
    (
        "anthropic_key",
        r"sk-ant-[A-Za-z0-9_-]{20,}",
        "REDACTED_ANTHROPIC_KEY",
    ),
    (
        "deepseek_key",
        r"sk-[a-f0-9]{32,}",
        "REDACTED_DEEPSEEK_KEY",
    ),
    (
        "openai_key",
        r"sk-(?:proj-)?[A-Za-z0-9_-]{20,}",
        "REDACTED_OPENAI_KEY",
    ),
    (
        "github_pat",
        r"\b(?:ghp|gho|ghu|ghs|ghr|github_pat)_[A-Za-z0-9]{36,}\b",
        "REDACTED_GITHUB_PAT",
    ),
    (
        "aws_access_key",
        r"\bAKIA[0-9A-Z]{16}\b",
        "REDACTED_AWS_ACCESS_KEY",
    ),
    (
        "aws_secret",
        r"\baws4_request.+?[A-Za-z0-9/+=]{40}\b",
        "REDACTED_AWS_SECRET",
    ),
    # ---- PEM-encoded private keys (full block) ----
    (
        "pem_private_key",
        r"-----BEGIN (?:RSA |EC |OPENSSH |DSA |PGP )?PRIVATE KEY-----.*?-----END (?:RSA |EC |OPENSSH |DSA |PGP )?PRIVATE KEY-----",
        "REDACTED_PEM_PRIVATE_KEY",
    ),
    # ---- Generic credential patterns (medium-signal) ----
    (
        # JWT: three base64-url segments separated by dots, starts with eyJ
        # Allow shorter segments (≥8 chars) to catch test/example JWTs.
        "jwt",
        r"\beyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\b",
        "REDACTED_JWT",
    ),
    (
        # Bearer token: "Bearer <token>" — token ≥10 alnum chars
        "bearer_token",
        r"(?:[Bb]earer)\s+([A-Za-z0-9_\.-]{10,})",
        "REDACTED_BEARER_TOKEN",
    ),
    (
        # Generic api_key=... / apikey=... / api-key=... / "api_key": "..."
        # Matches both assignment (k=v) and JSON ("k": "v") forms.
        "api_key_assignment",
        r"(?i)\b(?:api[_-]?key|apikey|access[_-]?token|secret[_-]?key)\b\s*[\"']?\s*[:=]\s*[\"']([A-Za-z0-9_/+=\.-]{12,})[\"']",
        "REDACTED_API_KEY",
    ),
    (
        # password=... (only when followed by non-trivial value)
        "password_assignment",
        r"(?i)\bpassword\s*[\"']?\s*[:=]\s*[\"']([^'\"]{8,})[\"']",
        "REDACTED_PASSWORD",
    ),
    # ---- PII: email addresses (lower-signal; only redact obvious PII) ----
    (
        "email",
        r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b",
        "REDACTED_EMAIL",
    ),
]

# Pre-compile for performance
_COMPILED: list[tuple[str, "re.Pattern[str]", str, int]] = [
    (name, re.compile(pattern, re.DOTALL), placeholder, idx)
    for idx, (name, pattern, placeholder) in enumerate(_CATALOG)
]


@dataclass
class ScrubResult:
    """Result of scrub(): the redacted text + in-memory mapping.

    The mapping MUST NOT be persisted to disk. If the caller needs to log this
    object for debugging, log only `scrubbed_text` + `len(mapping)` (counts only).
    """

    scrubbed_text: str
    mapping: dict[str, str] = field(default_factory=dict)
    """placeholder → original (e.g., "<REDACTED_OPENAI_KEY_a1b2c3>" → "sk-...")"""

    hit_counts: dict[str, int] = field(default_factory=dict)
    """catalog name → number of matches replaced (for telemetry / debugging)"""


def _hash_suffix(original: str, salt: int = 0) -> str:
    """Deterministic short hash (6 hex chars) used to disambiguate placeholders.

    Same original → same hash → same placeholder. Two different originals get
    different placeholders. This satisfies D1-11 "固定输入产生固定脱敏输出"
    while helping the LLM see "the same token appears twice" as a single entity.
    """
    h = hashlib.sha1(f"{salt}|{original}".encode("utf-8")).hexdigest()
    return h[:6]


def scrub(text: str) -> ScrubResult:
    """Redact secret/PII patterns in `text` per the catalog.

    Returns a ScrubResult with:
      - scrubbed_text: safe to send to LLM
      - mapping: placeholder → original (reverse for `restore`)
      - hit_counts: per-pattern hit counts (debugging)

    Idempotent on already-scrubbed text: scrub(scrub(t).scrubbed_text) == scrub(t).
    """
    if not text:
        return ScrubResult(scrubbed_text="", mapping={}, hit_counts={})

    mapping: dict[str, str] = {}
    hit_counts: dict[str, int] = {}
    current = text

    for name, pattern, placeholder_prefix, _salt in _COMPILED:
        def _replace(match: "re.Match[str]") -> str:
            original = match.group(0)
            suffix = _hash_suffix(original, salt=0)
            placeholder = f"<{placeholder_prefix}_{suffix}>"
            # Preserve first-seen mapping (if collision produces same hash, fine)
            if placeholder not in mapping:
                mapping[placeholder] = original
            hit_counts[name] = hit_counts.get(name, 0) + 1
            return placeholder

        # For patterns with a capture group, we replace the WHOLE match (including
        # the keyword prefix like "Bearer ") — but only if group(1) exists. To keep
        # this simple, we always replace group(0); the catalog patterns are tuned
        # so that group(0) is the right unit.
        new_current = pattern.sub(_replace, current)
        current = new_current

    return ScrubResult(scrubbed_text=current, mapping=mapping, hit_counts=hit_counts)


def restore(text: str, mapping: dict[str, str]) -> str:
    """Reverse scrub(): substitute placeholders back to originals.

    If `text` contains placeholders not in `mapping`, they are left as-is
    (defensive — should not happen in normal operation).
    """
    if not text or not mapping:
        return text
    out = text
    # Replace longer placeholders first to avoid prefix collisions
    # (e.g., REDACTED_OPENAI_KEY_X vs REDACTED_OPENAI_KEY_XYZ — both are 6-hex
    # so collision is impossible, but defensive sort is cheap).
    for placeholder in sorted(mapping.keys(), key=len, reverse=True):
        out = out.replace(placeholder, mapping[placeholder])
    return out


# ---- catalog introspection (for tests / docs) ------------------------------


def list_patterns() -> list[dict[str, str]]:
    """Return the catalog as a list of dicts (for documentation / testing)."""
    return [
        {"name": name, "pattern": pattern, "placeholder_prefix": placeholder}
        for name, pattern, placeholder in _CATALOG
    ]


__all__ = ["ScrubResult", "scrub", "restore", "list_patterns"]
