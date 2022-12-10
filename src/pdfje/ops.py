"""Low-level graphics operators, see PDF32000-1:2008 (8.2)"""
# TODO: rename this graphics?
from __future__ import annotations

import abc
from dataclasses import dataclass, replace
from typing import TYPE_CHECKING, ClassVar, Collection, Generator, Iterable

from . import fonts
from .common import RGB, XY, Pt, add_slots


# TODO: rename to Command
class Object(abc.ABC):
    __slots__ = ()

    @abc.abstractmethod
    def into_stream(self) -> Iterable[bytes]:
        ...


# TODO: rename to DrawLine or something
@add_slots
@dataclass(frozen=True)
class Line(Object):
    start: XY
    end: XY

    def into_stream(self) -> Iterable[bytes]:
        yield b"%g %g m %g %g l S\n" % (
            *self.start.astuple(),
            *self.end.astuple(),
        )


# TODO fix
if TYPE_CHECKING:
    from .typeset.words import Line as TLine
    from .typeset.words import PartialLine


class StateChange(Object):
    __slots__ = ()

    width = 0

    @abc.abstractmethod
    def apply(self, s: State, /) -> State:
        ...

    # TODO: remove
    def __add__(self, other: StateChange) -> StateChange:
        return MultiCommand([self, other])

    def wrap(self, line: PartialLine) -> Generator[TLine, Pt, PartialLine]:
        from .typeset.words import Line as TLine

        return TLine(
            [*line.segments, self],
            line.space,
            line.lead or 0,
            line.end,
            self.apply(line.state),
        )
        # We need at least one yield to make this a generator function.
        # It doesn't matter that it cannot be reached
        yield  # type: ignore[unreachable]


@add_slots
@dataclass(frozen=True)
class _Nothing(StateChange):
    def apply(self, s: State) -> State:
        return s

    def into_stream(self) -> Iterable[bytes]:
        return iter(())


NOTHING = _Nothing()


@add_slots
@dataclass(frozen=True)
class MultiCommand(StateChange):
    items: Collection[StateChange]

    def apply(self, s: State) -> State:
        for c in self.items:
            s = c.apply(s)
        return s

    def __add__(self, other: StateChange) -> StateChange:
        return MultiCommand([*self.items, other])

    def into_stream(self) -> Iterable[bytes]:
        for i in self.items:
            yield from i.into_stream()


@add_slots
@dataclass(frozen=True)
class SetFont(StateChange):
    font: fonts.Font
    size: Pt

    def apply(self, s: State) -> State:
        return replace(s, font=self.font, size=self.size)

    def into_stream(self) -> Iterable[bytes]:
        yield b"%b %g Tf\n" % (self.font.id, self.size)


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

    font: fonts.Font
    size: Pt
    color: RGB
    line_spacing: float

    # TODO: cache some of these?
    def spacewidth(self) -> Pt:
        return self.font.width(" ") * self.size

    def spacechar(self) -> bytes:
        return self.font.encode(" ")

    def leading(self) -> Pt:
        return self.size * self.line_spacing

    def kerns_with(self, other: State) -> bool:
        return self.font == other.font and self.size == other.size

    DEFAULT: ClassVar[State]


State.DEFAULT = State(fonts.helvetica.regular, 12, RGB(0, 0, 0), 1.25)
