"""SDDP-Pet backend package.

Dev-Phase 1 D1-13 (OTEL hard-disable, per specs/security-compliance/spec.md
Requirement: 进程 MUST 硬编码 OTEL_SDK_DISABLED=true):
This MUST be the very first thing imported in any sddp entry point. Setting
the env var here ensures OpenTelemetry SDK (if pulled in transitively via
crewai/litellm/etc.) sees `OTEL_SDK_DISABLED=true` BEFORE it is initialized.

Users MUST NOT be able to override this via configuration — it is a hard
compliance requirement (design.md Decision 5; analysis/09 §七).
"""
from __future__ import annotations

import os

# Hard-disable OpenTelemetry BEFORE any `opentelemetry.*` import.
# `setdefault` is intentionally NOT used — we want to override any user-provided value.
os.environ["OTEL_SDK_DISABLED"] = "true"
# Also disable common exporter endpoints (defense-in-depth; if some library
# doesn't respect OTEL_SDK_DISABLED, these prevent active collection).
os.environ["OTEL_TRACES_EXPORTER"] = "none"
os.environ["OTEL_METRICS_EXPORTER"] = "none"
os.environ["OTEL_LOGS_EXPORTER"] = "none"
# Disable bibliothek auto-instrumentation that may run at import time
os.environ.setdefault("OTEL_PYTHON_DISABLED_INSTRUMENTATIONS", "*")
os.environ.setdefault("OTEL_PYTHON_DISABLE_AGENT", "true")
