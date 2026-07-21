"""tree-sitter fallback parser.

Used when scip-python indexer is unavailable, or to supplement SCIP with constructs
SCIP doesn't cover (analysis/02 §5.1, §5.2 step 5).

For Dev-Phase 0 KG-MVP, tree-sitter may be the *primary* code analysis path when
scip-python is not installed. In that case, confidence is automatically MEDIUM/LOW
(see query_api.py confidence mapping).
"""
from __future__ import annotations

import dataclasses
from pathlib import Path

import tree_sitter_python as tspython
from tree_sitter import Language, Node, Parser

# Cached language+parser (Python only for Dev-Phase 0)
_PY_LANGUAGE: Language | None = None
_PY_PARSER: Parser | None = None


def _get_python_parser() -> tuple[Language, Parser]:
    global _PY_LANGUAGE, _PY_PARSER
    if _PY_LANGUAGE is None:
        _PY_LANGUAGE = Language(tspython.language())
    if _PY_PARSER is None:
        _PY_PARSER = Parser(_PY_LANGUAGE)
    return _PY_LANGUAGE, _PY_PARSER


@dataclasses.dataclass
class SymbolInfo:
    """A symbol extracted by tree-sitter."""

    name: str
    kind: str  # "function", "class", "method"
    file_path: str
    line: int  # 1-indexed
    end_line: int
    parent: str | None  # enclosing class for methods, else None


@dataclasses.dataclass
class ReferenceInfo:
    """A reference (call/import) extracted by tree-sitter."""

    name: str
    kind: str  # "call", "import", "inherit"
    file_path: str
    line: int  # 1-indexed
    enclosing_symbol: str | None  # which symbol contains this ref


def parse_python_file(file_path: str | Path, source: bytes | None = None) -> tuple[list[SymbolInfo], list[ReferenceInfo]]:
    """Parse a Python file with tree-sitter; return defined symbols + references.

    Extracts:
      - function definitions (def) → SymbolInfo(kind="function" or "method")
      - class definitions (class) → SymbolInfo(kind="class")
      - import statements → ReferenceInfo(kind="import")
      - function calls → ReferenceInfo(kind="call")
      - class bases (inheritance) → ReferenceInfo(kind="inherit")
    """
    _, parser = _get_python_parser()
    path = Path(file_path)
    if source is None:
        source = path.read_bytes()
    tree = parser.parse(source)
    root = tree.root_node

    symbols: list[SymbolInfo] = []
    references: list[ReferenceInfo] = []
    file_path_str = str(path)

    def _walk(node: Node, enclosing_class: str | None, enclosing_func: str | None) -> None:
        if node.type == "function_definition":
            name_node = node.child_by_field_name("name")
            if name_node is None:
                _recurse_children(node, enclosing_class, enclosing_func)
                return
            name = _node_text(name_node, source)
            kind = "method" if enclosing_class else "function"
            sym = SymbolInfo(
                name=name,
                kind=kind,
                file_path=file_path_str,
                line=node.start_point[0] + 1,
                end_line=node.end_point[0] + 1,
                parent=enclosing_class,
            )
            symbols.append(sym)
            _recurse_children(node, enclosing_class, name)
        elif node.type == "class_definition":
            name_node = node.child_by_field_name("name")
            if name_node is None:
                _recurse_children(node, enclosing_class, enclosing_func)
                return
            name = _node_text(name_node, source)
            sym = SymbolInfo(
                name=name,
                kind="class",
                file_path=file_path_str,
                line=node.start_point[0] + 1,
                end_line=node.end_point[0] + 1,
                parent=None,
            )
            symbols.append(sym)
            # Inheritance: superclasses are in "superclasses" field
            supers = node.child_by_field_name("superclasses")
            if supers is not None:
                for child in supers.children:
                    if child.type == "argument_list" or child.type == "(":
                        continue
                    base_name = _node_text(child, source)
                    if base_name and base_name not in {",", "(", ")"}:
                        references.append(
                            ReferenceInfo(
                                name=base_name,
                                kind="inherit",
                                file_path=file_path_str,
                                line=child.start_point[0] + 1,
                                enclosing_symbol=enclosing_func,
                            )
                        )
            _recurse_children(node, name, enclosing_func)
        elif node.type == "import_statement" or node.type == "import_from_statement":
            # Capture imported module names
            for child in node.children:
                if child.type in {"dotted_name", "aliased_import"}:
                    mod = _node_text(child, source)
                    if mod:
                        references.append(
                            ReferenceInfo(
                                name=mod,
                                kind="import",
                                file_path=file_path_str,
                                line=node.start_point[0] + 1,
                                enclosing_symbol=enclosing_func,
                            )
                        )
                elif child.type == "dotted_name":
                    pass  # handled above
            _recurse_children(node, enclosing_class, enclosing_func)
        elif node.type == "call":
            func_node = node.child_by_field_name("function")
            if func_node is not None:
                call_name = _node_text(func_node, source)
                if call_name and not call_name.startswith("("):
                    references.append(
                        ReferenceInfo(
                            name=call_name,
                            kind="call",
                            file_path=file_path_str,
                            line=node.start_point[0] + 1,
                            enclosing_symbol=enclosing_func,
                        )
                    )
            _recurse_children(node, enclosing_class, enclosing_func)
        else:
            _recurse_children(node, enclosing_class, enclosing_func)

    def _recurse_children(node: Node, enclosing_class: str | None, enclosing_func: str | None) -> None:
        for child in node.children:
            _walk(child, enclosing_class, enclosing_func)

    _walk(root, None, None)
    return symbols, references


def _node_text(node: Node, source: bytes) -> str:
    """Return the source text spanned by node, decoded."""
    return source[node.start_byte : node.end_byte].decode("utf-8", errors="replace")
