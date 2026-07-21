"""Graph loader: writes symbols/refs into the SQLite knowledge graph.

Accepts SymbolInfo/ReferenceInfo from tree_sitter_fallback (and, when available,
augments with SCIP data — Dev-Phase 0 MVP runs primarily on tree-sitter due to
environment; the API is identical so swapping in real SCIP later needs no caller changes).

Per analysis/02 §5.2 steps 4 (Graph Loading) + 6 (Derived Views - triggered separately).
"""
from __future__ import annotations

import hashlib
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from .graph_schema import init_db
from .manifest import ProjectManifest
from .tree_sitter_fallback import ReferenceInfo, SymbolInfo, parse_python_file


def _stable_id(*parts: str) -> str:
    """Stable hash ID for a node (deterministic across runs)."""
    raw = "|".join(str(p) for p in parts)
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()[:32]


def load_project(
    manifest: ProjectManifest,
    db_path: str | Path,
    symbols_by_file: dict[Path, list[SymbolInfo]],
    refs_by_file: dict[Path, list[ReferenceInfo]],
    via: str = "tree-sitter",
) -> int:
    """Load symbols and refs into SQLite. Returns the new scan_version.

    Idempotent within a scan_version; each load creates a new scan_version row.
    """
    conn = init_db(db_path)
    cur = conn.cursor()

    # Determine next scan_version
    cur.execute("SELECT COALESCE(MAX(scan_version), 0) FROM scan_meta")
    next_version = (cur.fetchone()[0] or 0) + 1

    # Insert Repository + root-level Package
    repo_id = _stable_id("repo", str(manifest.root))
    cur.execute(
        "INSERT OR IGNORE INTO nodes(id, kind, name, file_path, scan_version) VALUES (?, 'Repository', ?, ?, ?)",
        (repo_id, manifest.root.name, str(manifest.root), next_version),
    )

    # Per language, insert Package
    pkg_ids: dict[str, str] = {}
    for lang in manifest.languages:
        pkg_id = _stable_id("pkg", str(manifest.root), lang)
        pkg_ids[lang] = pkg_id
        cur.execute(
            "INSERT OR IGNORE INTO nodes(id, kind, name, file_path, scan_version) VALUES (?, 'Package', ?, ?, ?)",
            (pkg_id, f"{manifest.root.name}:{lang}", str(manifest.root), next_version),
        )
        cur.execute(
            "INSERT OR IGNORE INTO edges(src_id, dst_id, kind, scan_version) VALUES (?, ?, 'CONTAINS', ?)",
            (repo_id, pkg_id, next_version),
        )

    # Build file → module path mapping (best-effort: file path relative to root, without .py)
    def _module_id(file_path: Path) -> str:
        try:
            rel = file_path.relative_to(manifest.root)
        except ValueError:
            rel = file_path
        module_dotted = ".".join(rel.with_suffix("").parts)
        return _stable_id("module", str(manifest.root), module_dotted)

    # Insert files, modules, symbols
    for file_path, symbols in symbols_by_file.items():
        file_id = _stable_id("file", str(file_path))
        cur.execute(
            "INSERT OR IGNORE INTO nodes(id, kind, name, file_path, scan_version) VALUES (?, 'File', ?, ?, ?)",
            (file_id, file_path.name, str(file_path), next_version),
        )
        # File belongs to the python package
        if "python" in pkg_ids:
            cur.execute(
                "INSERT OR IGNORE INTO edges(src_id, dst_id, kind, scan_version) VALUES (?, ?, 'CONTAINS', ?)",
                (pkg_ids["python"], file_id, next_version),
            )
        # Module node (one per .py file)
        mod_id = _module_id(file_path)
        cur.execute(
            "INSERT OR IGNORE INTO nodes(id, kind, name, file_path, scan_version) VALUES (?, 'Module', ?, ?, ?)",
            (mod_id, file_path.stem, str(file_path), next_version),
        )
        cur.execute(
            "INSERT OR IGNORE INTO edges(src_id, dst_id, kind, scan_version) VALUES (?, ?, 'CONTAINS', ?)",
            (file_id, mod_id, next_version),
        )

        # Symbols in this file
        for sym in symbols:
            sym_id = _stable_id("symbol", str(file_path), sym.name, str(sym.line))
            kind_label = {"function": "Symbol", "method": "Symbol", "class": "Symbol"}.get(sym.kind, "Symbol")
            cur.execute(
                "INSERT OR IGNORE INTO nodes(id, kind, name, file_path, line, scan_version) VALUES (?, ?, ?, ?, ?, ?)",
                (sym_id, kind_label, sym.name, str(file_path), sym.line, next_version),
            )
            # Module DEFINES Symbol
            cur.execute(
                "INSERT OR IGNORE INTO edges(src_id, dst_id, kind, scan_version) VALUES (?, ?, 'DEFINES', ?)",
                (mod_id, sym_id, next_version),
            )
            # Class inheritance: parent → child CONTAINS
            if sym.parent:
                parent_id = _stable_id("symbol", str(file_path), sym.parent, "class")
                cur.execute(
                    "INSERT OR IGNORE INTO edges(src_id, dst_id, kind, scan_version) VALUES (?, ?, 'CONTAINS', ?)",
                    (parent_id, sym_id, next_version),
                )

    # Insert references (call/import/inherit)
    # Build name → symbol_id index for this scan to resolve REFERENCES/CALLS edges.
    name_to_symbol_ids: dict[str, list[str]] = {}
    for file_path, symbols in symbols_by_file.items():
        for sym in symbols:
            sym_id = _stable_id("symbol", str(file_path), sym.name, str(sym.line))
            name_to_symbol_ids.setdefault(sym.name, []).append(sym_id)

    for file_path, refs in refs_by_file.items():
        for ref in refs:
            # Resolve ref.name to a target symbol id (if defined in this scan)
            target_ids = name_to_symbol_ids.get(ref.name, [])
            if not target_ids:
                # External reference (e.g. stdlib import); skip edge insertion but could record as Package
                continue
            # Resolve enclosing symbol (the caller)
            enclosing_id = None
            if ref.enclosing_symbol:
                # Find the enclosing symbol in this same file
                for sym in symbols_by_file.get(file_path, []):
                    if sym.name == ref.enclosing_symbol:
                        enclosing_id = _stable_id("symbol", str(file_path), sym.name, str(sym.line))
                        break

            edge_kind = {
                "call": "CALLS",
                "import": "IMPORTS",
                "inherit": "INHERITS",
            }.get(ref.kind, "REFERENCES")

            for target_id in target_ids:
                if enclosing_id and edge_kind in {"CALLS", "REFERENCES"}:
                    cur.execute(
                        "INSERT OR IGNORE INTO edges(src_id, dst_id, kind, scan_version, line) VALUES (?, ?, ?, ?, ?)",
                        (enclosing_id, target_id, edge_kind, next_version, ref.line),
                    )
                elif edge_kind == "IMPORTS":
                    # Module imports symbol
                    mod_id = _module_id(file_path)
                    cur.execute(
                        "INSERT OR IGNORE INTO edges(src_id, dst_id, kind, scan_version, line) VALUES (?, ?, ?, ?, ?)",
                        (mod_id, target_id, edge_kind, next_version, ref.line),
                    )
                elif edge_kind == "INHERITS":
                    # Child class inherits from parent
                    if enclosing_id is None:
                        # ref produced by class_definition; use first symbol in this file with name ref.name? No, the
                        # enclosing class is set during parse only for methods. For inheritance, find the class in file
                        # closest to ref.line. Simplify: find class in this file
                        for sym in symbols_by_file.get(file_path, []):
                            if sym.kind == "class" and abs(sym.line - ref.line) < 50:
                                enclosing_id = _stable_id("symbol", str(file_path), sym.name, str(sym.line))
                                break
                    if enclosing_id:
                        cur.execute(
                            "INSERT OR IGNORE INTO edges(src_id, dst_id, kind, scan_version, line) VALUES (?, ?, ?, ?, ?)",
                            (enclosing_id, target_id, edge_kind, next_version, ref.line),
                        )

    # Coverage stats
    total_files = len(symbols_by_file)
    total_symbols = sum(len(syms) for syms in symbols_by_file.values())
    coverage = {
        "via": via,
        "total_files": total_files,
        "total_symbols": total_symbols,
    }
    import json as _json
    cur.execute(
        "INSERT INTO scan_meta(scan_version, created_at, root_path, languages, coverage_stats) VALUES (?, ?, ?, ?, ?)",
        (
            next_version,
            datetime.now(timezone.utc).isoformat(),
            str(manifest.root),
            ",".join(manifest.languages),
            _json.dumps(coverage),
        ),
    )
    conn.commit()
    conn.close()
    return next_version


def parse_project_with_tree_sitter(manifest: ProjectManifest) -> tuple[dict[Path, list[SymbolInfo]], dict[Path, list[ReferenceInfo]], int, int]:
    """Parse all Python files in the manifest using tree-sitter.

    Returns (symbols_by_file, refs_by_file, total_files, parsed_files).
    """
    from .manifest import iter_source_files

    symbols_by_file: dict[Path, list[SymbolInfo]] = {}
    refs_by_file: dict[Path, list[ReferenceInfo]] = {}
    total_files = 0
    parsed_files = 0

    for lang in manifest.languages:
        if lang != "python":
            continue
        for file_path in iter_source_files(manifest, lang):
            total_files += 1
            try:
                syms, refs = parse_python_file(file_path)
                symbols_by_file[file_path] = syms
                refs_by_file[file_path] = refs
                parsed_files += 1
            except Exception:
                # Skip un-parseable file
                continue

    return symbols_by_file, refs_by_file, total_files, parsed_files
