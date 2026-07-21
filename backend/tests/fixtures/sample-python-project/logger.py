"""Logger module: Logger class + helpers."""
from __future__ import annotations
from typing import Any


class Logger:
    """Simple logger."""

    def __init__(self, name: str = "default") -> None:
        self.name = name
        self.entries: list[str] = []

    def info(self, msg: str) -> None:
        self.entries.append(f"[INFO] {msg}")

    def error(self, msg: str) -> None:
        self.entries.append(f"[ERROR] {msg}")

    def clear(self) -> None:
        self.entries.clear()


def log_call(logger: Logger, fn_name: str, *args: Any) -> None:
    """Log a function call."""
    logger.info(f"call {fn_name}({args})")
