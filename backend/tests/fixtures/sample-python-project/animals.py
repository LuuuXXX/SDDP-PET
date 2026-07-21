"""Animal hierarchy: demonstrates inheritance (Cat/Dog inherit Animal)."""
from __future__ import annotations
from abc import ABC, abstractmethod


class Animal(ABC):
    """Abstract base."""

    def __init__(self, name: str) -> None:
        self.name = name

    @abstractmethod
    def sound(self) -> str:
        ...

    def describe(self) -> str:
        return f"{self.__class__.__name__}({self.name}) says {self.sound()}"


class Dog(Animal):
    """Concrete dog."""

    def sound(self) -> str:
        return "Woof"


class Cat(Animal):
    """Concrete cat."""

    def sound(self) -> str:
        return "Meow"


def make_animals() -> list[Animal]:
    """Factory function."""
    return [Dog("Rex"), Cat("Felix")]
