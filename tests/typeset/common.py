from dataclasses import dataclass
from typing import Generator, TypeVar

import pytest

from pdfje import RGB, Pt, fonts, helvetica, ops
from pdfje.common import Char, Func, always, dictget
from pdfje.fonts.common import (
    TEXTSPACE_TO_GLYPHSPACE,
    GlyphPt,
    Kerning,
    KerningTable,
)
from pdfje.typeset import Word

T1 = TypeVar("T1")
T2 = TypeVar("T2")


def genreturn(gen: Generator[object, T1, T2], s: T1 | None = None) -> T2:
    try:
        gen.send(s)  # type: ignore[arg-type]
    except StopIteration as e:
        return e.value
    else:
        pytest.fail("Expected generator to raise StopIteration")


@dataclass(frozen=True, repr=False)
class DummyFont(fonts.Font):
    """Helper to create dummy fonts with easily testable metrics"""

    id: fonts.FontID
    charwidth: Func[Char, GlyphPt]
    kerning: KerningTable | None = None

    encoding_width = 1

    def __repr__(self) -> str:
        return f"DummyFont({self.id.decode()})"

    def width(self, s: str, /) -> Pt:
        return sum(map(self.charwidth, s)) / TEXTSPACE_TO_GLYPHSPACE

    def kern(self, s: str, /, prev: Char | None, offset: int) -> Kerning:
        return (
            fonts.kern(self.kerning, s, 1, prev, offset)
            if self.kerning
            else ()
        )

    def encode(self, s: str, /) -> bytes:
        return s.encode("latin-1")

    def charkern(self, a: Char, b: Char, /) -> GlyphPt:
        return self.kerning((a, b)) if self.kerning else 0


FONT_1 = DummyFont(b"Dummy1", always(1000))
FONT_2 = DummyFont(b"Dummy2", always(2000))
FONT_3 = DummyFont(
    b"Dummy3",
    always(2000),
    dictget(
        {
            ("o", "w"): -25,
            ("e", "v"): -30,
            ("v", "e"): -30,
            (" ", "N"): -10,
            ("r", "."): -40,
            (" ", "n"): -5,
            ("w", " "): -10,
            ("m", "p"): -10,
            (" ", "C"): -15,
            ("e", "x"): -20,
            ("d", "."): -5,
            ("i", "c"): -10,
            (".", " "): -15,
            (" ", "c"): -15,
        },
        0,
    ),
)


def word(s: str, w: Pt) -> Word:
    "Helper to quickly create a word"
    return Word(s.encode(), [], w)


def mkstate(
    font: fonts.Font = helvetica.regular,
    size: int = 12,
    color: tuple[float, float, float] = (0, 0, 0),
    line_spacing: float = 1.25,
) -> ops.State:
    """factory to easily create a State"""
    return ops.State(font, size, RGB(*color), line_spacing)
