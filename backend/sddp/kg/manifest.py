"""Project manifest detector for the pre-scanner.

Identifies project languages by looking for known manifest files. For Dev-Phase 0
(KG-MVP), only Python is supported; other manifests are recorded for future phases.

Per analysis/02 §5.1: ManifestDetector → SCIP Indexer (per-lang) → Graph Loader.
"""
from __future__ import annotations

import dataclasses
from pathlib import Path

# Map of manifest file → language. Dev-Phase 0 only acts on Python.
LANGUAGE_MANIFESTS: dict[str, str] = {
    "pyproject.toml": "python",
    "setup.py": "python",
    "requirements.txt": "python",
    "package.json": "typescript",  # Dev-Phase 1+ (KG-v1)
    "Cargo.toml": "rust",           # future
    "go.mod": "go",                 # future
    "pom.xml": "java",              # future
}

# Default exclude patterns (analysis/02 §5.2)
DEFAULT_EXCLUDES: tuple[str, ...] = (
    "vendor",
    "node_modules",
    "dist",
    "build",
    ".git",
    ".venv",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".tox",
    "site-packages",
)


@dataclasses.dataclass(frozen=True)
class ProjectManifest:
    """Detected project manifest."""

    root: Path
    languages: tuple[str, ...]
    manifests: dict[str, Path]  # language → manifest file path
    excludes: tuple[str, ...]


def detect_manifest(
    root: str | Path,
    excludes: tuple[str, ...] | None = None,
    languages_whitelist: tuple[str, ...] | None = None,
) -> ProjectManifest:
    """Detect the project manifest at root.

    Args:
        root: project root path
        excludes: directories to exclude (None → DEFAULT_EXCLUDES)
        languages_whitelist: if set, only these languages are recorded
            (Dev-Phase 0 default: ("python",))

    Returns:
        ProjectManifest with languages found.
    """
    root_path = Path(root).resolve()
    if not root_path.is_dir():
        raise FileNotFoundError(f"Project root not found or not a directory: {root_path}")

    if excludes is None:
        excludes = DEFAULT_EXCLUDES
    if languages_whitelist is None:
        # Dev-Phase 0: Python only
        languages_whitelist = ("python",)

    found_manifests: dict[str, Path] = {}
    for filename, lang in LANGUAGE_MANIFESTS.items():
        if languages_whitelist and lang not in languages_whitelist:
            continue
        manifest_path = root_path / filename
        if manifest_path.is_file():
            # Don't overwrite the first detected manifest for a language
            if lang not in found_manifests:
                found_manifests[lang] = manifest_path

    # If no manifest but .py files exist, infer python
    if not found_manifests:
        py_files = list(root_path.rglob("*.py"))
        if py_files and "python" in languages_whitelist:
            found_manifests["python"] = root_path  # root acts as implicit manifest

    languages = tuple(sorted(found_manifests.keys()))
    return ProjectManifest(
        root=root_path,
        languages=languages,
        manifests=found_manifests,
        excludes=excludes,
    )


def iter_source_files(manifest: ProjectManifest, language: str) -> list[Path]:
    """Yield source files for the given language, respecting excludes.

    Args:
        manifest: detected project manifest
        language: e.g. "python"

    Returns:
        Sorted list of Path objects.
    """
    extensions = {
        "python": (".py",),
        "typescript": (".ts", ".tsx"),
        "rust": (".rs",),
        "go": (".go",),
        "java": (".java",),
    }.get(language, ())
    if not extensions:
        return []

    exclude_set = set(manifest.excludes)
    out: list[Path] = []
    for path in manifest.root.rglob("*"):
        if not path.is_file():
            continue
        if path.suffix not in extensions:
            continue
        # check excludes
        try:
            rel_parts = path.relative_to(manifest.root).parts
        except ValueError:
            continue
        if any(part in exclude_set for part in rel_parts):
            continue
        out.append(path)
    out.sort()
    return out
