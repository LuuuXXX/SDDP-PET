"""Configuration module: defines Config dataclass + load_config()."""
from __future__ import annotations
from dataclasses import dataclass


@dataclass
class Config:
    """Runtime config."""
    name: str = "sample"
    debug: bool = False


def load_config(path: str) -> Config:
    """Load config from a path (placeholder)."""
    return Config(name=path)


def default_config() -> Config:
    """Return default config."""
    return Config()
