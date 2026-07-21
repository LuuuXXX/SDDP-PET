"""SCIP indexer invocation.

For Dev-Phase 0 KG-MVP, we attempt to invoke scip-python via subprocess. If unavailable,
the pre-scanner transparently falls back to tree-sitter-only mode (with lower confidence).

scip-python is typically installed via:
    pip install scip-python        # if available
    # or
    go install github.com/sourcegraph/scip-python/cmd/scip-python@latest
    # or download from https://github.com/sourcegraph/scip-python/releases

This module never raises on missing scip-python; it returns None and lets the caller
fall back. Per analysis/02 §5.1, tree-sitter is the documented fallback path.
"""
from __future__ import annotations

import dataclasses
import os
import shutil
import subprocess
import tempfile
from pathlib import Path


@dataclasses.dataclass
class SCIPIndexResult:
    """Result of a SCIP indexing run."""

    scip_index_path: Path
    via: str  # "scip-python" or "tree-sitter-fallback"
    success: bool
    error_message: str | None = None


def find_scip_python() -> str | None:
    """Locate scip-python executable on PATH (or via env var SCIP_PYTHON_PATH)."""
    env_path = os.environ.get("SCIP_PYTHON_PATH")
    if env_path and Path(env_path).is_file():
        return env_path
    return shutil.which("scip-python") or shutil.which("scip_python")


def index_python_project(project_root: str | Path, output_path: str | Path | None = None) -> SCIPIndexResult:
    """Run scip-python on a project, producing a .scip index file.

    Args:
        project_root: path to Python project
        output_path: where to write .scip file (default: temp file)

    Returns:
        SCIPIndexResult. If scip-python unavailable, returns success=False + via=fallback.
    """
    root = Path(project_root).resolve()
    if output_path is None:
        tmp = tempfile.NamedTemporaryFile(suffix=".scip", delete=False)
        output_path = Path(tmp.name)
        tmp.close()
    else:
        output_path = Path(output_path)

    scip_bin = find_scip_python()
    if scip_bin is None:
        return SCIPIndexResult(
            scip_index_path=output_path,
            via="tree-sitter-fallback",
            success=False,
            error_message="scip-python executable not found; fall back to tree-sitter",
        )

    try:
        cmd = [scip_bin, "index", str(root), "--output", str(output_path)]
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=300,  # 5 min cap
            check=False,
        )
        if result.returncode != 0:
            return SCIPIndexResult(
                scip_index_path=output_path,
                via="scip-python",
                success=False,
                error_message=f"scip-python exited {result.returncode}: {result.stderr[:500]}",
            )
        return SCIPIndexResult(
            scip_index_path=output_path,
            via="scip-python",
            success=True,
        )
    except (subprocess.TimeoutExpired, OSError) as e:
        return SCIPIndexResult(
            scip_index_path=output_path,
            via="scip-python",
            success=False,
            error_message=f"scip-python invocation failed: {e}",
        )
