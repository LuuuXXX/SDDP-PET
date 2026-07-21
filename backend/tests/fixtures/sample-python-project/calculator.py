"""Calculator: more functions to call from other modules."""
from __future__ import annotations
from utils import add, multiply


def square(n: int) -> int:
    return multiply(n, n)


def cube(n: int) -> int:
    return multiply(square(n), n)


def sum_squares(lo: int, hi: int) -> int:
    total = 0
    for i in range(lo, hi):
        total = add(total, square(i))
    return total
