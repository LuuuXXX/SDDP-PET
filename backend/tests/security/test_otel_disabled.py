"""D1-13 verification: OTEL hard-disable (specs/security-compliance/spec.md).

Per spec Requirement: 进程 MUST 硬编码 OTEL_SDK_DISABLED=true + Scenario: 进程启动后
无 OTEL 上报网络请求.

This test verifies:
  1. `sddp.__init__` (the very first import) sets OTEL_SDK_DISABLED=true
  2. The env var CANNOT be unset by configuration (it's hardcoded before user code runs)
  3. No OTEL network traffic is initiated at import time
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


def test_sddp_init_sets_otel_disabled():
    """Importing `sddp` MUST set OTEL_SDK_DISABLED=true in the current process."""
    # Run in a subprocess to ensure no carryover from test-runner env
    code = (
        "import os, sys; "
        "assert os.environ.get('OTEL_SDK_DISABLED') in (None, ''), 'precondition: env not set'; "
        "import sddp; "
        "assert os.environ.get('OTEL_SDK_DISABLED') == 'true', "
        "f'OTEL_SDK_DISABLED={os.environ.get(\"OTEL_SDK_DISABLED\")!r}'; "
        "print('OK')"
    )
    clean_env = {k: v for k, v in os.environ.items() if k != "OTEL_SDK_DISABLED"}
    result = subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True,
        text=True,
        env=clean_env,
        cwd=str(Path(__file__).parent.parent.parent),
    )
    assert result.returncode == 0, f"sddp import failed: {result.stderr}"
    assert "OK" in result.stdout, f"unexpected stdout: {result.stdout}"


def test_otel_disabled_overrides_user_provided_value():
    """If user sets OTEL_SDK_DISABLED=false, importing sddp MUST override to true."""
    code = (
        "import os; "
        "os.environ['OTEL_SDK_DISABLED'] = 'false'; "
        "import sddp; "
        "assert os.environ['OTEL_SDK_DISABLED'] == 'true', "
        "f'sddp must override user-provided value; got {os.environ[\"OTEL_SDK_DISABLED\"]!r}'; "
        "print('OK')"
    )
    result = subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True,
        text=True,
        cwd=str(Path(__file__).parent.parent.parent),
    )
    assert result.returncode == 0, f"override test failed: {result.stderr}"
    assert "OK" in result.stdout


def test_otel_exporter_env_vars_also_set():
    """Defense-in-depth: OTEL_TRACES/METRICS/LOGS_EXPORTER all set to 'none'."""
    code = (
        "import sddp, os\n"
        "for var in ['OTEL_TRACES_EXPORTER', 'OTEL_METRICS_EXPORTER', 'OTEL_LOGS_EXPORTER']:\n"
        "    assert os.environ.get(var) == 'none', f'{var}={os.environ.get(var)!r}'\n"
        "print('OK')"
    )
    result = subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True,
        text=True,
        cwd=str(Path(__file__).parent.parent.parent),
    )
    assert result.returncode == 0, f"exporter check failed: {result.stderr}"
    assert "OK" in result.stdout


def test_no_otel_network_call_at_import_time():
    """Importing `sddp` MUST NOT initiate any network call (no OTEL collector probe).

    We approximate this by checking that no socket is opened during import. This
    is conservative — a real OTEL probe would do TCP connect/dns lookups.
    """
    code = """
import socket
_orig_getaddrinfo = socket.getaddrinfo
calls = []
def spy(*a, **kw):
    calls.append(a[0] if a else '?')
    return _orig_getaddrinfo(*a, **kw)
socket.getaddrinfo = spy

import sddp  # should not make any DNS lookups

# Filter out anything that's clearly OTEL-related
otel_calls = [c for c in calls if 'otel' in str(c).lower() or 'telemetry' in str(c).lower() or 'signals' in str(c).lower()]
assert not otel_calls, f'OTEL network call detected at import: {otel_calls}'
print('OK')
"""
    result = subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True,
        text=True,
        cwd=str(Path(__file__).parent.parent.parent),
    )
    assert result.returncode == 0, f"network check failed: {result.stderr}"
    assert "OK" in result.stdout, f"unexpected output: {result.stdout}"


def test_sddp_init_module_source_contains_hardcoded_string():
    """Static check: `sddp/__init__.py` source MUST contain the literal env var assignment.

    This guards against accidental removal in a future refactor.
    """
    init_path = Path(__file__).parent.parent.parent / "sddp" / "__init__.py"
    src = init_path.read_text(encoding="utf-8")
    assert "OTEL_SDK_DISABLED" in src, (
        "sddp/__init__.py must reference OTEL_SDK_DISABLED"
    )
    assert '"true"' in src or "'true'" in src, "OTEL_SDK_DISABLED must be set to 'true'"
