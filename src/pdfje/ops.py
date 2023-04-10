"""Low-level graphics operators, see PDF32000-1:2008 (8.2)"""
# TODO: rename this graphics?
from __future__ import annotations

import abc
from dataclasses import dataclass, field, replace
from operator import methodcaller
from typing import Callable, Collection, Iterable, Iterator

from .common import RGB, XY, Pt, add_slots, setattr_frozen
from .fonts.common import Font


class Command(abc.ABC):
    __slots__ = ()

    @abc.abstractmethod
    def into_stream(self) -> Iterable[bytes]:
        ...


@add_slots
@dataclass(frozen=True)
class DrawLine(Command):
    start: XY
    end: XY
    stroke: RGB

    def into_stream(self) -> Iterable[bytes]:
        yield b"%g %g m %g %g l %g %g %g RG S\n" % (
            *self.start,
            *self.end,
            *self.stroke,
        )


class StateChange(Command):
    __slots__ = ()

    @abc.abstractmethod
    def apply(self, s: State, /) -> State:
        ...


@add_slots
@dataclass(frozen=True)
class _NoOp(StateChange):
    def apply(self, s: State) -> State:
        return s

    def into_stream(self) -> Iterable[bytes]:
        return ()


NO_OP = _NoOp()


@add_slots
@dataclass(frozen=True)
class Chain(StateChange):
    items: Collection[StateChange]

    def apply(self, s: State) -> State:
        for c in self.items:
            s = c.apply(s)
        return s

    def into_stream(self) -> Iterable[bytes]:
        for i in self.items:
            yield from i.into_stream()

    @staticmethod
    def squash(it: Iterator[StateChange]) -> StateChange:
        by_type = {type(i): i for i in it}
        if len(by_type) == 1:
            return by_type.popitem()[1]
        elif len(by_type) == 0:
            return NO_OP
        else:
            return Chain(by_type.values())


@add_slots
@dataclass(frozen=True)
class SetFont(StateChange):
    font: Font
    size: Pt

    def apply(self, s: State) -> State:
        return replace(s, font=self.font, size=self.size)

    def into_stream(self) -> Iterable[bytes]:
        yield b"/%b %g Tf\n" % (self.font.id, self.size)


@add_slots
@dataclass(frozen=True)
class SetLineSpacing(StateChange):
    value: float

    def apply(self, s: State) -> State:
        return replace(s, line_spacing=self.value)

    def into_stream(self) -> Iterable[bytes]:
        # We don't actually emit anything here,
        # because its value is already used to calculate the leading space
        # on a per-line basis.
        return ()


@add_slots
@dataclass(frozen=True)
class SetColor(StateChange):
    value: RGB

    def apply(self, s: State) -> State:
        return replace(s, color=self.value)

    def into_stream(self) -> Iterable[bytes]:
        yield b"%g %g %g rg\n" % self.value.astuple()


@add_slots
@dataclass(frozen=True)
class State:
    """Text state, see PDF 32000-1:2008, table 105"""

    font: Font
    size: Pt
    color: RGB
    line_spacing: float

    lead: Pt = field(init=False)  # cached calculation because it's used a lot

    def __post_init__(self) -> None:
        setattr_frozen(self, "lead", self.size * self.line_spacing)

    def kerns_with(self, other: State, /) -> bool:
        return self.font == other.font and self.size == other.size


into_stream: Callable[[Command], Iterable[bytes]] = methodcaller("into_stream")
