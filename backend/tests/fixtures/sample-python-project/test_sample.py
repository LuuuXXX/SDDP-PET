"""Tests for the sample project (placeholder)."""
from __future__ import annotations
import pytest

from utils import add, multiply
from calculator import square, cube
from animals import Dog, Cat


def test_add() -> None:
    assert add(2, 3) == 5


def test_square() -> None:
    assert square(4) == 16


def test_cube() -> None:
    assert cube(3) == 27


def test_dog_sound() -> None:
    assert Dog("Rex").sound() == "Woof"


def test_cat_sound() -> None:
    assert Cat("F").sound() == "Meow"
