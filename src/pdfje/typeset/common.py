from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Iterable, Iterator, Sequence

from ..common import Pt, add_slots, second
from ..fonts import TEXTSPACE_TO_GLYPHSPACE, GlyphPt, Kerning
from ..ops import State, StateChange

_TRAILING_RE = re.compile(r"[^ ]*\Z")  # always matches, at least empty string
_LEADING_RE = re.compile(r"\A[^ ]*")  # always matches, at least empty string


@add_slots
@dataclass(frozen=True)
class Span:
    """A command and the following text it applies to"""

    command: StateChange
    content: str  # contains no linebreaks!

    def finditer(self, expr: re.Pattern) -> Iterator[str]:
        for m in expr.finditer(self.content):
            yield m.group()

    def trailing(self) -> str:
        # This re always matches, returning an empty string at the very least
        return _TRAILING_RE.search(self.content).group()  # type: ignore

    # TODO: rename?
    def head(self) -> str:
        # This re always matches, returning an empty string at the very least
        return _LEADING_RE.search(self.content).group()  # type: ignore

    def has_space(self) -> bool:
        return " " in self.content

    def empty(self) -> bool:
        return not self.content

    def end_spaced(self) -> bool:
        return self.content.endswith(" ")

    def start_spaced(self) -> bool:
        return self.content.startswith(" ")


@add_slots
@dataclass(frozen=True)
class Word:
    """a unit of text with measurements"""

    content: bytes
    kerning: Sequence[tuple[int, GlyphPt]]
    width: Pt

    @staticmethod
    def build(t: State, s: str) -> Word:
        kerning = list(t.font.kern(s, " ", 0))
        return Word(
            t.font.encode(s),
            kerning,
            (
                t.font.width(s)
                + sum(map(second, kerning)) / TEXTSPACE_TO_GLYPHSPACE
            )
            * t.size,
        )

    @staticmethod
    def chain_kerning(bs: Iterable[Word], space_length: int) -> Kerning:
        offset = 0
        for box in bs:
            for index, space in box.kerning:
                yield (index + offset, space)
            # Remember we also need to add a space!
            offset += len(box.content) + space_length


@add_slots
@dataclass(frozen=True)
class CompoundWord:
    """A box contaning one or more commands (e.g. style changes) within it"""

    # FUTURE: implement kerning between boxes if fonts are the same (e.g.
    # only the color is different
    prefix: Word
    segments: Iterable[tuple[StateChange, Word]]
    leading: Pt

    @property
    def width(self) -> Pt:
        return self.prefix.width + sum(b.width for _, b in self.segments)
