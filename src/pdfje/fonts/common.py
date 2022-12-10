from __future__ import annotations

import abc
from dataclasses import dataclass, field
from itertools import chain, count, pairwise
from pathlib import Path
from typing import TYPE_CHECKING, Iterable

from .. import atoms
from ..atoms import ASCII
from ..common import Char, Func, Pt, add_slots

__all__ = [
    "BuiltinTypeface",
    "Font",
    "FontID",
    "GlyphPt",
    "Kerning",
    "KerningTable",
    "TEXTSPACE_TO_GLYPHSPACE",
    "Typeface",
    "kern",
]

FontID = bytes  # unique, internal identifier assigned to a font within a PDF
GlyphPt = float  # length unit in glyph space
TEXTSPACE_TO_GLYPHSPACE = 1000  # See PDF32000-1:2008 (9.7.3)


class Font(abc.ABC):
    """A specific font within a typeface"""

    __slots__ = ()

    @property
    @abc.abstractmethod
    def id(self) -> FontID:
        ...

    @property
    @abc.abstractmethod
    def encoding_width(self) -> int:
        """The number of bytes assigned to each character when encoding"""

    @abc.abstractmethod
    def encode(self, s: str, /) -> bytes:
        ...

    @abc.abstractmethod
    def width(self, s: str, /) -> Pt:
        """The total width of the given string (excluding kerning)"""

    @staticmethod
    @abc.abstractmethod
    def charwidth(c: Char, /) -> GlyphPt:
        ...

    @abc.abstractmethod
    def kern(
        self, s: str, /, prev: Char | None, offset: int
    ) -> Iterable[tuple[int, GlyphPt]]:
        ...

    @abc.abstractmethod
    def charkern(self, a: Char, b: Char, /) -> GlyphPt:
        ...


# The `id` abstract property doesn't mix well with dataclass inheritance.
# Deleting properties at runtime fixes the issue. It has no runtime impact.
# We rely on the type checker to ensure subclasses define the needed methods.
if not TYPE_CHECKING:
    del Font.id
    del Font.encoding_width
    del Font.charwidth


@add_slots
@dataclass(frozen=True)
class TrueType:
    regular: Path
    bold: Path
    italic: Path
    bold_italic: Path

    def font(self, bold: bool, italic: bool) -> Path:
        if bold:
            return self.bold_italic if italic else self.bold
        else:
            return self.italic if italic else self.regular


@add_slots
@dataclass(frozen=True, repr=False)
class BuiltinTypeface:
    regular: BuiltinFont
    bold: BuiltinFont
    italic: BuiltinFont
    bold_italic: BuiltinFont

    def font(self, bold: bool, italic: bool) -> BuiltinFont:
        if bold:
            return self.bold_italic if italic else self.bold
        else:
            return self.italic if italic else self.regular


Typeface = BuiltinTypeface | TrueType


@add_slots
@dataclass(frozen=True)
class BuiltinFont(Font):
    name: ASCII
    id: FontID
    charwidth: Func[Char, GlyphPt] = field(repr=False)
    kerning: KerningTable | None = field(repr=False)

    encoding_width = 1

    def width(self, s: str) -> Pt:
        return sum(map(self.charwidth, s)) / TEXTSPACE_TO_GLYPHSPACE

    @staticmethod
    def encode(s: str) -> bytes:
        # FUTURE: normalize unicode to allow better unicode representation
        return s.encode("cp1252", errors="replace")

    def kern(
        self, s: str, /, prev: Char | None, offset: int
    ) -> Iterable[tuple[int, GlyphPt]]:
        return kern(self.kerning, s, 1, prev, offset) if self.kerning else ()

    def charkern(self, a: Char, b: Char, /) -> GlyphPt:
        return self.kerning((a, b)) if self.kerning else 0

    def to_resource(self) -> atoms.Dictionary:
        return atoms.Dictionary(
            (b"Type", atoms.Name(b"Font")),
            (b"Subtype", atoms.Name(b"Type1")),
            (b"BaseFont", atoms.Name(self.name)),
            (b"Encoding", atoms.Name(b"WinAnsiEncoding")),
        )


KerningTable = Func[tuple[Char, Char], GlyphPt]
Kern = tuple[int, GlyphPt]
Kerning = Iterable[Kern]


def kern(
    table: KerningTable,
    s: str,
    charsize: int,
    prev: Char | None,
    offset: int,
) -> Kerning:
    for i, pair in zip(
        count(offset + (not prev) * charsize, charsize),
        pairwise(chain(prev, s) if prev else s),
    ):
        if space := table(pair):
            yield (i, space)
