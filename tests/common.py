from __future__ import annotations

from dataclasses import dataclass, field
from functools import partial, singledispatch
from typing import (
    TYPE_CHECKING,
    ClassVar,
    Collection,
    Iterable,
    List,
    Sequence,
    TypeVar,
)

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
from pdfje.typeset.hyphens import Hyphenator, never_hyphenate
from pdfje.typeset.layout import Line, ShapedText
from pdfje.typeset.state import (
    Chain,
    Command,
    Passage,
    SetColor,
    SetFont,
    State,
)
from pdfje.typeset.words import MixedSlug, Slug, WithCmd, Word

T = TypeVar("T")


class eq_iter(List[T]):
    """Test helper for comparing iterables."""

    def __eq__(self, other: object) -> bool:
        if isinstance(other, Sequence):
            return list(self) == list(other)
        elif isinstance(other, Collection):
            return set(self) == set(other)
        elif isinstance(other, Iterable):
            return list.__eq__(self, list(other))
        return NotImplemented


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

    encoding_width: ClassVar[int] = 1

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


FONT = DummyFont(
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
            ("x", "-"): -15,
        },
        0,
    ),
)

STATE = mkstate(font=FONT, size=12, color=(0, 0, 0))


RED = SetColor(RGB(1, 0, 0))
GREEN = SetColor(RGB(0, 1, 0))
BLUE = SetColor(RGB(0, 0, 1))
BLACK = SetColor(RGB(0, 0, 0))

HUGE = SetFont(FONT, 20)
BIG = SetFont(FONT, 15)
NORMAL = SetFont(FONT, 10)
SMALL = SetFont(FONT, 5)

LOREM_IPSUM = """\
Lorem ipsum dolor sit amet, consectetur adipiscing elit. \
Integer sed aliquet justo. Donec eu ultricies velit, porta pharetra massa. \
Ut non augue a urna iaculis vulputate ut sit amet sem. \
Nullam lectus felis, rhoncus sed convallis a, egestas semper risus. \
Fusce gravida metus non vulputate vestibulum. \
Vestibulum ante ipsum primis in faucibus orci luctus et ultrices posuere \
cubilia curae; Donec placerat suscipit velit. \
Mauris tincidunt lorem a eros eleifend tincidunt. \
Maecenas faucibus imperdiet massa quis pretium. Integer in lobortis nisi. \
Mauris at odio nec sem volutpat aliquam. Aliquam erat volutpat.\

Fusce at vehicula justo. Vestibulum eget viverra velit. \
Vivamus et nisi pulvinar, elementum lorem nec, volutpat leo. \
Aliquam erat volutpat. Sed tristique quis arcu vitae vehicula. \
Morbi egestas vel diam eget dapibus. Donec sit amet lorem turpis. \
Maecenas ultrices nunc vitae enim scelerisque tempus. \
Maecenas aliquet dui non hendrerit viverra. \
Aliquam fringilla, est sit amet gravida convallis, elit ipsum efficitur orci, \
eget convallis neque nunc nec lorem. Nam nisl sem, \
tristique a ultrices sed, finibus id enim.

Etiam vel dolor ultricies, gravida felis in, vestibulum magna. \
In diam ex, elementum ut massa a, facilisis sollicitudin lacus. \
Integer lacus ante, ullamcorper ac mauris eget, rutrum facilisis velit. \
Mauris eu enim efficitur, malesuada ipsum nec, sodales enim. \
Nam ac tortor velit. Suspendisse ut leo a felis aliquam dapibus ut a justo. \
Vestibulum sed commodo tortor. Sed vitae enim ipsum. \
Duis pellentesque dui et ipsum suscipit, in semper odio dictum.\

Sed in fermentum leo. Donec maximus suscipit metus. \
Nulla convallis tortor mollis urna maximus mattis. \
Sed aliquet leo ac sem aliquam, et ultricies mauris maximus. \
Cras orci ex, fermentum nec purus non, molestie venenatis odio. \
Etiam vitae sollicitudin nisl. Sed a ullamcorper velit.\

Aliquam congue aliquet eros scelerisque hendrerit. Vestibulum quis ante ex. \
Fusce venenatis mauris dolor, nec mattis libero pharetra feugiat. \
Pellentesque habitant morbi tristique senectus et netus et malesuada \
fames ac turpis egestas. Cras vitae nisl molestie augue finibus lobortis. \
In hac habitasse platea dictumst. Maecenas rutrum interdum urna, \
ut finibus tortor facilisis ac. Donec in fringilla mi. \
Sed molestie accumsan nisi at mattis. \
Integer eget orci nec urna finibus porta. \
Sed eu dui vel lacus pulvinar blandit sed a urna. \
Quisque lacus arcu, mattis vel rhoncus hendrerit, dapibus sed massa. \
Vivamus sed massa est. In hac habitasse platea dictumst. \
Nullam volutpat sapien quis tincidunt sagittis.\
"""
LOREM_SHORT = "\n".join(LOREM_IPSUM.split("\n")[:2])

ZEN_OF_PYTHON = """\
Beautiful is better than ugly.
Explicit is better than implicit.
Simple is better than complex.
Complex is better than complicated.
Flat is better than nested.
Sparse is better than dense.
Readability counts.
Special cases aren't special enough to break the rules.
Although practicality beats purity.
Errors should never pass silently.
Unless explicitly silenced.
In the face of ambiguity, refuse the temptation to guess.
There should be one — and preferably only one — obvious way to do it.
Although that way may not be obvious at first unless you're Dutch.
Now is better than never.
Although never is often better than *right* now.
If the implementation is hard to explain, it's a bad idea.
If the implementation is easy to explain, it may be a good idea.
Namespaces are one honking great idea — let's do more of those!"""


PASSAGES = [
    Passage(BLUE, "Simple is better than com"),
    Passage(RED, "plex. "),
    Passage(BLACK, "Complex is better than "),
    Passage(HUGE, "complicated. "),
    Passage(NORMAL, "Flat is better than nested. "),
    Passage(SMALL, "Sparse is better than d"),
    Passage(NORMAL, "ense. "),
    Passage(RED, "Readability counts. "),
    Passage(BIG, "Special cases aren't special enough to "),
    Passage(SMALL, "break the rules. "),
]


@singledispatch
def plaintext(ws: object) -> str:
    if hasattr(ws, "__iter__"):  # a bit hacky, but convenient for testing
        return "".join(map(plaintext, ws))
    raise NotImplementedError(f"plaintext not implemented for {type(ws)}")


@plaintext.register
def _(w: Word) -> str:
    body = "".join(map(plaintext, w.boxes))
    if w.tail:
        body += " "
    return body


@plaintext.register
def _(p: ShapedText) -> str:
    body = ""
    for line in p.lines:
        if body.endswith("-"):
            body = body[:-1]
        elif body:
            body += " "
        body += "".join(map(plaintext, line.words))
    if body.endswith("-"):
        body = body[:-1]
    else:
        body += " "
    return body


@plaintext.register
def _(ln: Line) -> str:
    return plaintext(ln.words)


@plaintext.register
def _(w: WithCmd) -> str:
    return plaintext(w.word)


@plaintext.register
def _(w: MixedSlug) -> str:
    return "".join(plaintext(p) for p, _ in w.segments)


@plaintext.register
def _(w: Slug) -> str:
    return w.txt


if TYPE_CHECKING:
    approx = float.__call__
else:
    from pytest import approx as _approx  # noqa

    approx = partial(_approx, abs=1e-3)
