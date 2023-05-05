from __future__ import annotations

import abc
import re
from dataclasses import dataclass, field, replace
from itertools import chain
from typing import Collection, Generator, Iterable, Iterator, Sequence, TypeVar

from ..atoms import LiteralStr, Real
from ..common import (
    RGB,
    Char,
    NonEmtpyIterator,
    Pos,
    Pt,
    Streamable,
    add_slots,
    flatten,
    prepend,
    second,
    setattr_frozen,
)
from ..fonts.common import TEXTSPACE_TO_GLYPHSPACE, Font, Kern
from .hyphens import Hyphenator

_NEWLINE_RE = re.compile(r"(?:\r\n|\n)")

T = TypeVar("T")


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
def splitlines(it: Iterable[Stretch]) -> Iterator[NonEmtpyIterator[Stretch]]:
    it = iter(it)
    try:
        transition: list[tuple[Stretch, Pos]] = [(next(it), 0)]
    except StopIteration:
        return

    def _group() -> NonEmtpyIterator[Stretch]:
        stretch, pos = transition.pop()
        for stretch in prepend(stretch, it):
            if (newline := _NEWLINE_RE.search(stretch.txt, pos)) is None:
                yield Stretch(NO_OP, stretch.txt[pos:]) if pos else stretch
                pos = 0
            else:
                yield Stretch(
                    NO_OP if pos else stretch.cmd,
                    stretch.txt[pos : newline.start()],  # noqa
                )
                transition.append((stretch, newline.end()))
                return

    while transition:
        yield _group()


@add_slots
@dataclass(frozen=True)
class Stretch:
    cmd: Command
    txt: str


def _encode_kerning(
    txt: str,
    kerning: Sequence[Kern],
    f: Font,
) -> Iterable[LiteralStr | Real]:
    encoded = f.encode(txt)
    try:
        index_prev, space = kerning[0]
    except IndexError:
        yield LiteralStr(encoded)
        return

    if index_prev == 0:  # i.e. the case where we kern before any text
        yield Real(-space)
        kerning = kerning[1:]

    index_prev = index = 0
    for index, space in kerning:
        index *= f.encoding_width
        yield LiteralStr(encoded[index_prev:index])
        yield Real(-space)
        index_prev = index

    yield LiteralStr(encoded[index:])


@add_slots
@dataclass(frozen=True)
class Slug:
    "A fragment of text with its measured width and kerning information"
    txt: str  # non-empty
    kern: Sequence[Kern]
    width: Pt
    state: State

    @property
    def lead(self) -> Pt:
        return self.state.lead

    def last(self) -> Char:
        return self.txt[-1]

    def with_hyphen(self) -> Slug:
        kern = self.state.font.charkern(self.last(), "-")
        return Slug(
            self.txt + "-",
            [*self.kern, (len(self.txt), kern)] if kern else self.kern,
            self.width
            + (
                (self.state.font.charwidth("-") - kern)
                / TEXTSPACE_TO_GLYPHSPACE
            )
            * self.state.size,
            self.state,
        )

    def has_init_kern(self) -> bool:
        return bool(self.kern) and self.kern[0][0] == 0

    @staticmethod
    def nonempty(s: str, state: State, prev: Char | None) -> Slug:
        font = state.font
        kern = list(font.kern(s, prev))
        return Slug(
            s,
            kern,
            (font.width(s) + sum(map(second, kern)) / TEXTSPACE_TO_GLYPHSPACE)
            * state.size,
            state,
        )

    def without_init_kern(self) -> Slug:
        kern = self.kern
        if kern:
            firstkern_pos, firstkern = kern[0]
            if firstkern_pos == 0:
                delta = (firstkern * self.state.size) / TEXTSPACE_TO_GLYPHSPACE
                return Slug(
                    self.txt,
                    kern[1:],
                    self.width - delta,
                    self.state,
                )
        return self

    def indent(self, amount: Pt) -> Slug:
        # We only indent the first word of a line -- which never has Kerning
        # on the first letter.
        try:
            assert self.kern[0][0] != 0
        except IndexError:  # pragma: no cover
            pass
        return Slug(
            self.txt,
            [
                (0, amount / self.state.size * TEXTSPACE_TO_GLYPHSPACE),
                *self.kern,
            ],
            self.width + amount,
            self.state,
        )

    def to_atoms(self) -> Iterable[LiteralStr | Real]:
        return _encode_kerning(self.txt, self.kern, self.state.font)

    def encode_into_line(
        self, line: Iterable[LiteralStr | Real]
    ) -> Generator[bytes, None, Iterable[LiteralStr | Real]]:
        return chain(line, self.to_atoms())
        # We need have one yield to turn this into a generator,
        # even if it won't be reached.
        yield  # type: ignore[unreachable]
