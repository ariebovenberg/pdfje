"""Low-level graphics operators, see PDF32000-1:2008 (8.2)"""
from __future__ import annotations

import abc
from dataclasses import dataclass, replace
from typing import ClassVar, Collection

from . import fonts
from .common import RGB, Pt, add_slots


class Command(abc.ABC):
    @abc.abstractmethod
    def apply(self, s: State) -> State:
        ...

    def __add__(self, other: Command) -> Command:
        return MultiCommand([self, other])

    # TODO: to PDF raw commands


@add_slots
@dataclass(frozen=True)
class MultiCommand(Command):
    items: Collection[Command]

    def apply(self, s: State) -> State:
        for c in self.items:
            s = c.apply(s)
        return s

    def __add__(self, other: Command) -> Command:
        return MultiCommand([*self.items, other])


@add_slots
@dataclass(frozen=True)
class SetFont(Command):
    font: fonts.Font
    size: Pt

    def apply(self, s: State) -> State:
        return replace(s, font=self.font, size=self.size)


@add_slots
@dataclass(frozen=True)
class SetColor(Command):
    value: RGB

    def apply(self, s: State) -> State:
        return replace(s, color=self.value)


@dataclass(frozen=True)
class State:
    """Text state, see PDF 32000-1:2008, table 105"""

    font: fonts.Font = fonts.helvetica
    size: Pt = 12
    color: RGB | None = None  # TODO: implement

    def spacewidth(self) -> Pt:
        return self.font.width(" ") * self.size

    def __lshift__(self, c: Command) -> State:
        return c.apply(self)

    DEFAULT: ClassVar[State]


State.DEFAULT = State()
