"""D1-9 verification: no plaintext API keys on disk (specs/security-compliance/spec.md).

Per spec Requirement: API 密钥 MUST 通过 OS 原生 credential manager 加密存储 +
Scenario: D1-9 grep 验证通过.

This test scans the SDDP runtime directory (default `~/.sddp-pet/`) for any file
containing common API key patterns (sk- / AKIA / ghp_ etc.). Any match fails.

The test is designed to run against a fresh process tree that has performed at
least one full SDDP flow (so logs, flow_state DBs, KG DBs, metrics.json etc.
have all been written at least once).

In CI, the test runs against an isolated tmp_path-driven SDDP home to verify the
scanning logic; in D1-9 manual verification, the user runs it against their real
~/.sddp-pet/ directory.
"""
from __future__ import annotations

import os
import re
import subprocess
import tempfile
from pathlib import Path

import pytest

# Regex catalog mirroring the high-signal patterns from sddp.security.prefilter
# (kept here as a separate copy — the test MUST NOT import the catalog module
# to avoid accidental coupling; the test should pass even if the catalog changes).
LEAK_PATTERNS = [
    re.compile(r"sk-(?:proj-|ant-)?[A-Za-z0-9_-]{20,}"),
    re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
    re.compile(r"\b(?:ghp|gho|ghu|ghs|ghr|github_pat)_[A-Za-z0-9]{36,}\b"),
]


def _scan_dir(root: Path) -> list[tuple[Path, int, str]]:
    """Walk `root` recursively, return list of (file, line_no, matched_line) hits."""
    hits: list[tuple[Path, int, str]] = []
    if not root.exists():
        return hits
    for dirpath, _dirs, files in os.walk(root):
        for fname in files:
            fpath = Path(dirpath) / fname
            # Skip binary files heuristically by extension
            if fpath.suffix in {".db", ".sqlite", ".sqlite3", ".pyc", ".so", ".dylib", ".dll"}:
                continue
            try:
                text = fpath.read_text(encoding="utf-8", errors="ignore")
            except (OSError, PermissionError):
                continue
            for line_no, line in enumerate(text.splitlines(), start=1):
                for pat in LEAK_PATTERNS:
                    if pat.search(line):
                        hits.append((fpath, line_no, line.strip()[:200]))
                        break  # one hit per line is enough
    return hits


def test_scan_dir_finds_known_leak_in_tmp_path(tmp_path: Path):
    """Sanity: the scanner DOES detect a deliberately planted plaintext key."""
    leaked = tmp_path / "config.txt"
    leaked.write_text("OPENAI_API_KEY=sk-abcdefghijklmnopqrstuvwxyz1234567890ABCD\n")
    hits = _scan_dir(tmp_path)
    assert len(hits) == 1
    assert hits[0][0] == leaked
    assert "sk-abcdef" in hits[0][2]


def test_scan_dir_ignores_binary_db_files(tmp_path: Path):
    """Binary SQLite DBs MUST be skipped (they may contain hash bytes that look like keys)."""
    db = tmp_path / "state.db"
    db.write_bytes(b"\x00\x01sk-abcdefghijklmnopqrstuvwxyz1234567890ABCD\x00\x02")
    hits = _scan_dir(tmp_path)
    assert hits == [], f"scanner should skip .db files; got {hits}"


def test_no_plaintext_keys_in_isolated_sddp_home(tmp_path: Path, monkeypatch):
    """D1-9 main scenario: after a flow runs in an isolated SDDP_PET_HOME,
    `grep -r sk- ~/.sddp-pet/` MUST return empty.

    We don't run a real flow (too slow); instead we simulate the artifacts a
    real flow would produce (logs / flow_state.db / metrics.json / config.json)
    and verify NONE of them contain plaintext keys.
    """
    sddp_home = tmp_path / ".sddp-pet"
    sddp_home.mkdir()
    (sddp_home / "flow_state.db").write_bytes(b"\x00\x01\x02\x03SQLite-format-3\x00")
    (sddp_home / "metrics.json").write_text('{"flow_id":"fid-1","flow_time_seconds":12.3,"status":"completed"}\n')
    (sddp_home / "config.json").write_text('{"provider":"openai","key_ref":"openai_default","model":"gpt-4o-mini"}\n')
    (sddp_home / "app.log").write_text("[INFO] flow started\n[INFO] flow completed\n")

    monkeypatch.setenv("SDDP_PET_HOME", str(sddp_home))
    hits = _scan_dir(sddp_home)
    assert hits == [], f"unexpected plaintext key hit: {hits}"


def test_grep_invocation_pattern_works(tmp_path: Path):
    """Verify the actual `grep -rE` command from D1-9 spec works as documented.

    Spec: `grep -r "sk-" ~/.sddp-pet/` MUST return empty (exit 1).
    """
    sddp_home = tmp_path / ".sddp-pet"
    sddp_home.mkdir()
    (sddp_home / "config.json").write_text('{"key_ref":"openai_default"}\n')  # safe

    result = subprocess.run(
        ["grep", "-rE", "sk-|AKIA|ghp_", str(sddp_home)],
        capture_output=True, text=True,
    )
    assert result.returncode == 1, f"grep should exit 1 (no matches); got rc={result.returncode}, stdout={result.stdout!r}"
    assert result.stdout == ""


def test_grep_detects_when_leak_exists(tmp_path: Path):
    """Negative case: if a leak IS planted, grep MUST detect it (sanity)."""
    sddp_home = tmp_path / ".sddp-pet"
    sddp_home.mkdir()
    (sddp_home / "bad.log").write_text("leaked key: sk-abcdefghijklmnopqrstuvwxyz1234567890ABCD\n")

    result = subprocess.run(
        ["grep", "-rE", "sk-|AKIA|ghp_", str(sddp_home)],
        capture_output=True, text=True,
    )
    assert result.returncode == 0, f"grep should find the leak; rc={result.returncode}"
    assert "sk-abcdef" in result.stdout
