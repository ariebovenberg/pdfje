from __future__ import annotations

import abc
import re
from dataclasses import dataclass, field, replace
from typing import Collection, Iterable, Iterator, NamedTuple

from ..common import (
    RGB,
    NonEmptyIterator,
    Pos,
    Pt,
    Streamable,
    add_slots,
    flatten,
    prepend,
    setattr_frozen,
)
from ..fonts.common import Font
from .hyphens import Hyphenator

_next_newline = re.compile(r"(?:\r\n|\n)").search


class Command(Streamable):
    __slots__ = ()

    @abc.abstractmethod
    def apply(self, s: State, /) -> State:
        ...


@add_slots
@dataclass(frozen=True)
class _NoOp(Command):
    def apply(self, s: State) -> State:
        return s

    def __iter__(self) -> Iterator[bytes]:
        return iter(())


NO_OP = _NoOp()


@add_slots
@dataclass(frozen=True)
class Chain(Command):
    items: Collection[Command]

    def apply(self, s: State) -> State:
        for c in self.items:
            s = c.apply(s)
        return s

    def __iter__(self) -> Iterator[bytes]:
        return flatten(self.items)

    @staticmethod
    def squash(it: Iterable[Command]) -> Command:
        by_type = {type(i): i for i in it}
        if len(by_type) == 1:
            return by_type.popitem()[1]
        elif len(by_type) == 0:
            return NO_OP
        else:
            return Chain(by_type.values())


@add_slots
@dataclass(frozen=True)
class SetFont(Command):
    font: Font
    size: Pt

    def apply(self, s: State) -> State:
        return replace(s, font=self.font, size=self.size)

    def __iter__(self) -> Iterator[bytes]:
        yield b"/%b %g Tf\n" % (self.font.id, self.size)


@add_slots
@dataclass(frozen=True)
class SetLineSpacing(Command):
    value: float

    def apply(self, s: State) -> State:
        return replace(s, line_spacing=self.value)

    def __iter__(self) -> Iterator[bytes]:
        # We don't actually emit anything here,
        # because its value is already used to calculate the leading space
        # on a per-line basis.
        return iter(())


@add_slots
@dataclass(frozen=True)
class SetColor(Command):
    value: RGB

    def apply(self, s: State) -> State:
        return replace(s, color=self.value)

    def __iter__(self) -> Iterator[bytes]:
        yield b"%g %g %g rg\n" % self.value.astuple()


@add_slots
@dataclass(frozen=True)
class SetHyphens(Command):
    value: Hyphenator

    def apply(self, s: State) -> State:
        return replace(s, hyphens=self.value)

    def __iter__(self) -> Iterator[bytes]:
        # hyphenation behavior is not written to the PDF stream itself,
        # but rather used in the text layout algorithm.
        return iter(())


@add_slots
@dataclass(frozen=True)
class State(Streamable):
    """Text state, see PDF 32000-1:2008, table 105"""

    font: Font
    size: Pt
    color: RGB
    line_spacing: float
    hyphens: Hyphenator

    lead: Pt = field(init=False, compare=False)  # cached calculation

    def __iter__(self) -> Iterator[bytes]:
        yield from SetFont(self.font, self.size)
        yield from SetColor(self.color)

    def __post_init__(self) -> None:
        setattr_frozen(self, "lead", self.size * self.line_spacing)

    def kerns_with(self, other: State, /) -> bool:
        return self.font == other.font and self.size == other.size


# NOTE: the result must be consumed in order, similar to itertools.groupby
def splitlines(it: Iterable[Passage]) -> Iterator[NonEmptyIterator[Passage]]:
    it = iter(it)
    try:
        transition: list[tuple[Passage, Pos]] = [(next(it), 0)]
    except StopIteration:
        return

    def _group() -> NonEmptyIterator[Passage]:
        psg, pos = transition.pop()
        for psg in prepend(psg, it):
            if (newline := _next_newline(psg.txt, pos)) is None:
                yield Passage(NO_OP, psg.txt[pos:]) if pos else psg
                pos = 0
            else:
                yield Passage(
                    NO_OP if pos else psg.cmd,
                    psg.txt[pos : newline.start()],  # noqa
                )
                transition.append((psg, newline.end()))
                return

    while transition:
        yield _group()


class Passage(NamedTuple):
    cmd: Command
    txt: str


def max_lead(s: Iterable[Passage], state: State) -> Pt:
    # FUTURE: we apply commands elsewhere, so doing it also here
    #         is perhaps a bit wasteful
    lead = 0.0
    for cmd, txt in s:
        state = cmd.apply(state)
        # Only count leading if there is actually text with this value
        if txt:
            lead = max(lead, state.lead)
    # If there's no text to go on, use the state's default
    return lead or state.lead
