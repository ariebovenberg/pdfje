from dataclasses import dataclass, field
from typing import Iterable

from pdfje import RGB
from pdfje.common import Char, Func, Pt, always, dictget, setattr_frozen
from pdfje.fonts import helvetica
from pdfje.fonts.common import (
    TEXTSPACE_TO_GLYPHSPACE,
    Font,
    FontID,
    GlyphPt,
    Kern,
    KerningTable,
    kern,
)
from pdfje.typeset.common import Chain, Command, SetColor, SetFont, State
from pdfje.typeset.hyphens import Hyphenator, never_hyphenate


def mkstate(
    font: Font = helvetica.regular,
    size: int = 12,
    color: tuple[float, float, float] = (0, 0, 0),
    line_spacing: float = 1.25,
    hyphens: Hyphenator = never_hyphenate,
) -> State:
    """factory to easily create a State"""
    return State(font, size, RGB(*color), line_spacing, hyphens)


@dataclass(frozen=True, repr=False, eq=False)
class DummyFont(Font):
    """Helper to create dummy fonts with easily testable metrics"""

    id: FontID
    charwidth: Func[Char, GlyphPt]
    kerning: KerningTable | None = None
    spacewidth: GlyphPt = field(init=False)

    encoding_width = 1

    def __post_init__(self) -> None:
        setattr_frozen(self, "spacewidth", self.charwidth(" "))

    def __repr__(self) -> str:
        return f"DummyFont({self.id.decode()})"

    def width(self, s: str, /) -> Pt:
        return sum(map(self.charwidth, s)) / TEXTSPACE_TO_GLYPHSPACE

    def kern(self, s: str, /, prev: Char | None) -> Iterable[Kern]:
        return kern(self.kerning, s, prev) if self.kerning else ()

    def charkern(self, a: Char, b: Char, /) -> GlyphPt:
        return self.kerning((a, b)) if self.kerning else 0

    def encode(self, s: str, /) -> bytes:
        return s.encode("latin-1")


def multi(*args: Command) -> Command:
    return Chain(args)


FONT = FONT_3 = DummyFont(
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

STATE = mkstate(font=FONT, size=12, color=(0, 0, 0))


RED = SetColor(RGB(1, 0, 0))
GREEN = SetColor(RGB(0, 1, 0))
BLUE = SetColor(RGB(0, 0, 1))
BLACK = SetColor(RGB(0, 0, 0))

HUGE = SetFont(FONT_3, 20)
BIG = SetFont(FONT_3, 15)
NORMAL = SetFont(FONT_3, 10)
SMALL = SetFont(FONT_3, 5)
