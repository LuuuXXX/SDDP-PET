"""Datastore module: simple key-value store."""
from __future__ import annotations
from logger import Logger


class DataStore:
    """In-memory KV store."""

    def __init__(self) -> None:
        self._data: dict[str, str] = {}
        self._log = Logger("datastore")

    def put(self, key: str, value: str) -> None:
        self._data[key] = value
        self._log.info(f"put {key!r}")

    def get(self, key: str) -> str | None:
        return self._data.get(key)

    def keys(self) -> list[str]:
        return list(self._data.keys())
