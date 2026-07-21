"""Renderer module: formats data for display."""
from __future__ import annotations
from typing import Any, Iterable

from logger import Logger
from utils import format_pair


def render_kv(logger: Logger, key: str, value: Any) -> str:
    """Render a key-value pair via format_pair + log it."""
    s = format_pair(key, value)
    logger.info(s)
    return s


def render_list(items: Iterable[Any]) -> str:
    """Render a list of items."""
    return ", ".join(str(i) for i in items)


def render_table(rows: Iterable[tuple[Any, ...]]) -> str:
    """Render rows as a simple table."""
    return "\n".join(" | ".join(str(c) for c in r) for r in rows)
