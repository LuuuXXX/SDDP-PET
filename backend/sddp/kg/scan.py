"""Pre-scanner CLI entry: `python -m sddp.kg.scan <path>`.

Per analysis/02 §5.2: Manifest探测 → SCIP索引 → tree-sitter fallback → Graph Loading →
Derived Views (materialized by graph_loader on demand via SQL views; this module exposes
convenience functions for the 3 derived view names).

Also per Dev-Phase 0 spec: emits scan_version + non-empty graph on success.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .graph_loader import load_project, parse_project_with_tree_sitter
from .manifest import DEFAULT_EXCLUDES, detect_manifest, iter_source_files
from .query_api import KnowledgeGraphQueryAPI
from .scip_indexer import index_python_project


def scan_project(
    project_root: str | Path,
    db_path: str | Path = "knowledge_graph.db",
    excludes: tuple[str, ...] | None = None,
    prefer_scip: bool = True,
) -> dict:
    """Scan a project, build the KG, return summary dict.

    Args:
        project_root: path to project
        db_path: SQLite output path
        excludes: directories to exclude (None → defaults)
        prefer_scip: try scip-python first, fall back to tree-sitter

    Returns:
        Summary dict with scan_version, total_files, total_symbols, via.
    """
    project_root = Path(project_root).resolve()
    if excludes is None:
        excludes = DEFAULT_EXCLUDES

    # 1. Manifest
    manifest = detect_manifest(project_root, excludes=excludes)
    if "python" not in manifest.languages:
        return {
            "error": f"No Python detected at {project_root}; Dev-Phase 0 supports Python only",
            "languages_found": manifest.languages,
        }

    # 2. Index (try SCIP, fall back to tree-sitter)
    via = "tree-sitter"
    scip_result = None
    if prefer_scip:
        scip_result = index_python_project(project_root)
        if scip_result.success:
            via = "scip-python"
            # Note: For Dev-Phase 0 MVP, we still primarily use tree-sitter-parsed symbols because
            # implementing the full SCIP protobuf parser is out-of-scope (analysis/02 §5.2 step 4
            # is the planned but heavier path). SCIP success is recorded in coverage_stats.
            # The tree-sitter path below produces the actual graph.

    # 3. Parse with tree-sitter (always, even when SCIP succeeds, for Dev-Phase 0 MVP)
    symbols_by_file, refs_by_file, total_files, parsed_files = parse_project_with_tree_sitter(manifest)

    # 4. Load into SQLite
    scan_version = load_project(
        manifest=manifest,
        db_path=db_path,
        symbols_by_file=symbols_by_file,
        refs_by_file=refs_by_file,
        via=via,
    )

    total_symbols = sum(len(s) for s in symbols_by_file.values())
    total_refs = sum(len(r) for r in refs_by_file.values())

    return {
        "scan_version": scan_version,
        "via": via,
        "scip_attempted": scip_result is not None,
        "scip_success": scip_result.success if scip_result else False,
        "scip_error": scip_result.error_message if scip_result else None,
        "project_root": str(project_root),
        "languages": list(manifest.languages),
        "total_files": total_files,
        "parsed_files": parsed_files,
        "total_symbols": total_symbols,
        "total_refs": total_refs,
        "db_path": str(db_path),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m sddp.kg.scan",
        description="Pre-scan a Python project into the SDDP knowledge graph (Dev-Phase 0 KG-MVP).",
    )
    parser.add_argument("path", help="Project root path to scan")
    parser.add_argument(
        "--db",
        default="knowledge_graph.db",
        help="SQLite KG output path (default: knowledge_graph.db)",
    )
    parser.add_argument(
        "--exclude",
        action="append",
        default=None,
        help="Directory to exclude (repeatable). Default: vendor/node_modules/dist/build/.git/.venv/__pycache__",
    )
    parser.add_argument(
        "--no-scip",
        action="store_true",
        help="Skip scip-python attempt; go straight to tree-sitter fallback.",
    )
    parser.add_argument(
        "--query",
        action="append",
        nargs=2,
        metavar=("METHOD", "ARG"),
        help="After scan, run a query: e.g. --query lookup_symbol my_func",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Emit machine-readable JSON to stdout",
    )
    args = parser.parse_args(argv)

    excludes = tuple(args.exclude) if args.exclude else None
    summary = scan_project(args.path, db_path=args.db, excludes=excludes, prefer_scip=not args.no_scip)

    if "error" in summary:
        print(f"[error] {summary['error']}", file=sys.stderr)
        return 2

    if args.json:
        print(json.dumps(summary, indent=2, default=str))
    else:
        print(f"[ok] scan_version={summary['scan_version']} via={summary['via']}")
        print(f"     files: {summary['parsed_files']}/{summary['total_files']} parsed")
        print(f"     symbols: {summary['total_symbols']}, refs: {summary['total_refs']}")
        print(f"     db: {summary['db_path']}")

    if args.query:
        api = KnowledgeGraphQueryAPI(args.db)
        for method, arg in args.query:
            if method == "lookup_symbol":
                result = api.lookup_symbol(arg)
            elif method == "find_file_impact":
                result = api.find_file_impact(arg)
            else:
                print(f"[warn] unknown query method: {method}", file=sys.stderr)
                continue
            print(json.dumps(result.to_dict(), indent=2, default=str))
        api.close()

    return 0 if summary["total_symbols"] > 0 else 3


if __name__ == "__main__":
    sys.exit(main())
