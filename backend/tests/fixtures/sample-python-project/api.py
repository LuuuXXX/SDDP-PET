"""API layer: calls datastore + utils."""
from __future__ import annotations
from datastore import DataStore
from utils import format_pair
from calculator import square, cube


class Api:
    """Tiny API facade."""

    def __init__(self) -> None:
        self.store = DataStore()

    def put_value(self, k: str, v: str) -> None:
        self.store.put(k, v)

    def get_pair(self, k1: str, k2: str) -> str:
        v1 = self.store.get(k1)
        v2 = self.store.get(k2)
        return format_pair(v1, v2)

    def square_then_cube(self, n: int) -> tuple[int, int]:
        return square(n), cube(n)
