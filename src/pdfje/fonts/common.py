from __future__ import annotations

import abc
from dataclasses import dataclass, field
from itertools import chain, count, pairwise
from pathlib import Path
from typing import TYPE_CHECKING, Iterable, final

from .. import atoms
from ..atoms import ASCII
from ..common import Char, Func, Pos, Pt, add_slots, setattr_frozen

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

    # It's worth caching this value, as it is used often
    @property
    @abc.abstractmethod
    def spacewidth(self) -> GlyphPt:
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
    def kern(self, s: str, /, prev: Char | None) -> Iterable[Kern]:
        ...

    @abc.abstractmethod
    def charkern(self, a: Char, b: Char, /) -> GlyphPt:
        ...


# The abstract properties don't mix well with dataclass inheritance.
# Deleting properties at runtime fixes the issue. It has no runtime impact.
# We rely on the type checker to ensure subclasses define the needed methods.
if not TYPE_CHECKING:  # pragma: no cover
    del Font.id
    del Font.encoding_width
    del Font.charwidth
    del Font.spacewidth


@final
@add_slots
@dataclass(frozen=True, init=False)
class TrueType:
    """A TrueType font to be embedded in a PDF

    Parameters
    ----------
    regular
        The regular (i.e. non-bold, non-italic) .ttf file
    bold
        The bold .ttf file
    italic
        The italic .ttf file
    bold_italic
        The bold italic .ttf file

    """

    regular: Path
    bold: Path
    italic: Path
    bold_italic: Path

    def __init__(
        self,
        regular: Path | str,
        bold: Path | str,
        italic: Path | str,
        bold_italic: Path | str,
    ) -> None:
        setattr_frozen(self, "regular", Path(regular))
        setattr_frozen(self, "bold", Path(bold))
        setattr_frozen(self, "italic", Path(italic))
        setattr_frozen(self, "bold_italic", Path(bold_italic))

    # This method cannot be defined in the class body, as it would cause a
    # circular import. The implementation is patched into the class
    # in the `style` module.
    if TYPE_CHECKING:  # pragma: no cover
        from ..common import HexColor
        from ..style import Style, StyleLike

        def __or__(self, _: StyleLike, /) -> Style:
            ...

        def __ror__(self, _: HexColor, /) -> Style:
            ...

    def font(self, bold: bool, italic: bool) -> Path:
        if bold:
            return self.bold_italic if italic else self.bold
        else:
            return self.italic if italic else self.regular


@final
@add_slots
@dataclass(frozen=True, repr=False)
class BuiltinTypeface:
    """A typeface that is built into the PDF renderer."""

    regular: BuiltinFont
    bold: BuiltinFont
    italic: BuiltinFont
    bold_italic: BuiltinFont

    # This method cannot be defined in the class body, as it would cause a
    # circular import. The implementation is patched into the class
    # in the `style` module.
    if TYPE_CHECKING:  # pragma: no cover
        from ..common import HexColor
        from ..style import Style, StyleLike

        def __or__(self, _: StyleLike, /) -> Style:
            ...

        def __ror__(self, _: HexColor, /) -> Style:
            ...

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}({self.regular.name.decode()})"

    def font(self, bold: bool, italic: bool) -> BuiltinFont:
        if bold:
            return self.bold_italic if italic else self.bold
        else:
            return self.italic if italic else self.regular


Typeface = BuiltinTypeface | TrueType


@final
@add_slots
@dataclass(frozen=True, eq=False)
class BuiltinFont(Font):
    name: ASCII
    id: FontID
    charwidth: Func[Char, GlyphPt] = field(repr=False)
    kerning: KerningTable | None = field(repr=False)
    spacewidth: Pt = field(init=False, repr=False)

    encoding_width = 1

    def __post_init__(self) -> None:
        setattr_frozen(self, "spacewidth", self.charwidth(" "))

    def width(self, s: str) -> Pt:
        return sum(map(self.charwidth, s)) / TEXTSPACE_TO_GLYPHSPACE

    @staticmethod
    def encode(s: str) -> bytes:
        # FUTURE: normalize unicode to allow better unicode representation
        return s.encode("cp1252", errors="replace")

    def kern(self, s: str, /, prev: Char | None) -> Iterable[Kern]:
        return kern(self.kerning, s, prev) if self.kerning else ()

    def charkern(self, a: Char, b: Char) -> GlyphPt:
        return self.kerning((a, b)) if self.kerning else 0

    def to_resource(self) -> atoms.Dictionary:
        return atoms.Dictionary(
            (b"Type", atoms.Name(b"Font")),
            (b"Subtype", atoms.Name(b"Type1")),
            (b"BaseFont", atoms.Name(self.name)),
            (b"Encoding", atoms.Name(b"WinAnsiEncoding")),
        )


KerningTable = Func[tuple[Char, Char], GlyphPt]
Kern = tuple[Pos, GlyphPt]


def kern(
    table: KerningTable,
    s: str,
    prev: Char | None,
) -> Iterable[Kern]:
    for i, pair in zip(
        count(not prev),
        pairwise(chain(prev, s) if prev else s),
    ):
        if space := table(pair):
            yield (i, space)
