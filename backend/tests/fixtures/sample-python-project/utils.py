"""Utility functions: small helpers used across the project."""
from __future__ import annotations


def add(a: int, b: int) -> int:
    return a + b


def multiply(a: int, b: int) -> int:
    return a * b


def format_pair(a: object, b: object) -> str:
    return f"({a!r}, {b!r})"
