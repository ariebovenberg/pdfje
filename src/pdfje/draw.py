from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Iterator, Literal, Sequence, final

from .atoms import LiteralStr, Real
from .common import (
    RGB,
    XY,
    Align,
    HexColor,
    Pt,
    Streamable,
    add_slots,
    pipe,
    setattr_frozen,
)
from .page import Drawing
from .resources import Resources
from .style import Span, Style, StyledMixin, StyleFull, StyleLike
from .typeset.layout import Line as _TextLineBase
from .typeset.layout import render_text
from .typeset.parse import into_words
from .typeset.state import Command, Passage, State, max_lead, splitlines
from .typeset.words import WordLike, render_kerned

__all__ = [
    "Circle",
    "Ellipse",
    "Line",
    "Polyline",
    "Rect",
    "Text",
    "Drawing",
]


@final
@add_slots
@dataclass(frozen=True, init=False)
class Line(Drawing):
    """A :class:`Drawing` of a straight line segment.

    Parameters
    ----------
    start
        The start point of the line. Can be parsed from a 2-tuple.
    end
        The end point of the line. Can be parsed from a 2-tuple.
    stroke: RGB | str | None
        The color -- can be parsed from a hex string (e.g. ``#ff0000``)

    """

    start: XY
    end: XY
    stroke: RGB | None

    def __init__(
        self,
        start: XY | tuple[float, float],
        end: XY | tuple[float, float],
        stroke: RGB | HexColor | None = RGB(0, 0, 0),
    ) -> None:
        setattr_frozen(self, "start", XY.parse(start))
        setattr_frozen(self, "end", XY.parse(end))
        setattr_frozen(self, "stroke", stroke and RGB.parse(stroke))

    def render(self, _: Resources, __: StyleFull, /) -> Streamable:
        yield b"%g %g m %g %g l " % (*self.start, *self.end)
        yield from _finish(None, self.stroke, False)


@final
@add_slots
@dataclass(frozen=True, init=False)
class Rect(Drawing):
    """A :class:`Drawing` of a rectangle.

    Parameters
    ----------
    origin
        The bottom left corner of the rectangle. Can be parsed from a 2-tuple.
    width
        The width of the rectangle.
    height
        The height of the rectangle.
    fill: RGB | str | None
        The fill color -- can be parsed from a hex string (e.g. ``#ff0000``)
    stroke: RGB | str | None
        The stroke color -- can be parsed from a hex string (e.g. ``#ff0000``)

    """

    origin: XY
    width: Pt
    height: Pt
    fill: RGB | None
    stroke: RGB | None

    def __init__(
        self,
        origin: XY | tuple[float, float],
        width: Pt,
        height: Pt,
        fill: RGB | HexColor | None = None,
        stroke: RGB | HexColor | None = RGB(0, 0, 0),
    ) -> None:
        setattr_frozen(self, "origin", XY.parse(origin))
        setattr_frozen(self, "width", width)
        setattr_frozen(self, "height", height)
        setattr_frozen(self, "fill", fill and RGB.parse(fill))
        setattr_frozen(self, "stroke", stroke and RGB.parse(stroke))

    def render(self, _: Resources, __: StyleFull, /) -> Streamable:
        yield b"%g %g %g %g re " % (*self.origin, self.width, self.height)
        yield from _finish(self.fill, self.stroke, False)


@final
@add_slots
@dataclass(frozen=True, init=False)
class Ellipse(Drawing):
    """A :class:`Drawing` of an ellipse.

    Parameters
    ----------
    center
        The center of the ellipse. Can be parsed from a 2-tuple.
    width
        The width of the ellipse.
    height
        The height of the ellipse.
    fill: RGB | str | None
        The fill color -- can be parsed from a hex string (e.g. ``#ff0000``)
    stroke: RGB | str | None
        The stroke color -- can be parsed from a hex string (e.g. ``#ff0000``)

    """

    center: XY
    width: Pt
    height: Pt
    fill: RGB | None
    stroke: RGB | None

    def __init__(
        self,
        center: XY | tuple[float, float],
        width: Pt,
        height: Pt,
        fill: RGB | HexColor | None = None,
        stroke: RGB | HexColor | None = RGB(0, 0, 0),
    ) -> None:
        setattr_frozen(self, "center", XY.parse(center))
        setattr_frozen(self, "width", width)
        setattr_frozen(self, "height", height)
        setattr_frozen(self, "fill", fill and RGB.parse(fill))
        setattr_frozen(self, "stroke", stroke and RGB.parse(stroke))

    def render(self, _: Resources, __: StyleFull, /) -> Streamable:
        return _ellipse(
            self.center, self.width, self.height, self.fill, self.stroke
        )


@final
@add_slots
@dataclass(frozen=True, init=False)
class Circle(Drawing):
    """A :class:`Drawing` of a circle.

    Parameters
    ----------
    center
        The center of the circle. Can be parsed from a 2-tuple.
    radius
        The radius of the circle.
    fill: RGB | str | None
        The fill color -- can be parsed from a hex string (e.g. ``#ff0000``)
    stroke: RGB | str | None
        The stroke color -- can be parsed from a hex string (e.g. ``#ff0000``)

    """

    center: XY
    radius: Pt
    fill: RGB | None
    stroke: RGB | None

    def __init__(
        self,
        center: XY | tuple[float, float],
        radius: Pt,
        fill: RGB | HexColor | None = None,
        stroke: RGB | HexColor | None = RGB(0, 0, 0),
    ) -> None:
        setattr_frozen(self, "center", XY.parse(center))
        setattr_frozen(self, "radius", radius)
        setattr_frozen(self, "fill", fill and RGB.parse(fill))
        setattr_frozen(self, "stroke", stroke and RGB.parse(stroke))

    def render(self, _: Resources, __: StyleFull, /) -> Streamable:
        width = self.radius * 2
        return _ellipse(self.center, width, width, self.fill, self.stroke)


def _finish(fill: RGB | None, stroke: RGB | None, close: bool) -> Streamable:
    if fill and stroke:
        yield b"%g %g %g rg %g %g %g RG " % (*fill, *stroke)
        yield b"b\n" if close else b"B\n"
    elif fill:
        yield b"%g %g %g rg f\n" % fill.astuple()
    elif stroke:
        yield b"%g %g %g RG " % stroke.astuple()
        yield b"s\n" if close else b"S\n"
    else:
        yield b"n\n"


# based on https://stackoverflow.com/questions/2172798
def _ellipse(
    center: XY, w: Pt, h: Pt, fill: RGB | None, stroke: RGB | None
) -> Streamable:
    x, y = center - (w / 2, h / 2)
    kappa = 0.5522848
    ox = (w / 2) * kappa
    oy = (h / 2) * kappa
    xe = x + w
    ye = y + h
    xm = x + w / 2
    ym = y + h / 2
    yield b"%g %g m " % (x, ym)
    yield b"%g %g %g %g %g %g c " % (
        x,
        ym - oy,
        xm - ox,
        y,
        xm,
        y,
    )
    yield b"%g %g %g %g %g %g c " % (
        xm + ox,
        y,
        xe,
        ym - oy,
        xe,
        ym,
    )
    yield b"%g %g %g %g %g %g c " % (
        xe,
        ym + oy,
        xm + ox,
        ye,
        xm,
        ye,
    )
    yield b"%g %g %g %g %g %g c " % (
        xm - ox,
        ye,
        x,
        ym + oy,
        x,
        ym,
    )
    yield from _finish(fill, stroke, False)


@final
@add_slots
@dataclass(frozen=True, init=False)
class Polyline(Drawing):
    """A :class:`Drawing` of a polyline.

    Parameters
    ----------
    points
        The points of the polyline. Can be parsed from a 2-tuple.
    close
        Whether to close the polyline.
    fill: RGB | str | None
        The fill color -- can be parsed from a hex string (e.g. ``#ff0000``)
    stroke: RGB | str | None
        The stroke color -- can be parsed from a hex string (e.g. ``#ff0000``)

    """

    points: Iterable[XY | tuple[float, float]]
    close: bool = False
    fill: RGB | None = None
    stroke: RGB | None = RGB(0, 0, 0)

    def __init__(
        self,
        points: Iterable[XY | tuple[float, float]],
        close: bool = False,
        fill: RGB | HexColor | None = None,
        stroke: RGB | HexColor | None = RGB(0, 0, 0),
    ) -> None:
        setattr_frozen(self, "points", points)
        setattr_frozen(self, "close", close)
        setattr_frozen(self, "fill", fill and RGB.parse(fill))
        setattr_frozen(self, "stroke", stroke and RGB.parse(stroke))

    def render(self, _: Resources, __: StyleFull, /) -> Streamable:
        it = iter(self.points)
        try:
            yield b"%g %g m " % next(it)
        except StopIteration:
            return
        yield from map(pipe(tuple, b"%g %g l ".__mod__), it)
        yield from _finish(self.fill, self.stroke, self.close)


@final
@add_slots
@dataclass(frozen=True, init=False)
class Text(Drawing, StyledMixin):
    """A :class:`Drawing` of text at the given location (not wrapped)

    Parameters
    ----------
    loc
        The location of the text. Can be parsed from a 2-tuple.
    content: str | Span | ~typing.Sequence[str | Span]
        The text to render. Can be a string, or a nested :class:`~pdfje.Span`.
    style
        The style to apply to the text.
    align
        The horizontal alignment of the text.
    """

    loc: XY
    content: Sequence[str | Span]
    style: Style
    align: Align

    def __init__(
        self,
        loc: XY | tuple[float, float],
        content: str | Span | Sequence[str | Span],
        style: StyleLike = Style.EMPTY,
        align: Align | Literal["left", "center", "right"] = Align.LEFT,
    ) -> None:
        if isinstance(content, (str, Span)):
            content = [content]
        setattr_frozen(self, "loc", XY.parse(loc))
        setattr_frozen(self, "content", content)
        setattr_frozen(self, "style", Style.parse(style))
        setattr_frozen(self, "align", Align.parse(align))
        # FUTURE: a more elegant way to do this
        if self.align is Align.JUSTIFY:
            raise NotImplementedError(
                "Justified alignment not implemented for explicitly "
                "positioned text."
            )

    def render(self, r: Resources, s: StyleFull, /) -> Streamable:
        state = s.as_state(r)
        passages = list(self.flatten(r, s))
        return render_text(
            self.loc,
            state,
            0,
            list(into_lines(splitlines(passages), state)),
            max_lead(passages, state),
            self.align,
        )


@add_slots
@dataclass(frozen=True)
class _TextLine(_TextLineBase):
    cmd: Command
    words: tuple[WordLike, ...]
    width: Pt

    def __iter__(self) -> Iterator[bytes]:
        yield from self.cmd
        content: Iterable[Real | LiteralStr] = ()
        for w in self.words:
            content = yield from w.encode_into_line(content)
        yield from render_kerned(content)


def into_lines(
    split: Iterable[Iterable[Passage]], state: State
) -> Iterator[_TextLine]:
    for s in split:
        cmd, [*words] = into_words(s, state)
        yield _TextLine(cmd, tuple(words), sum(w.width for w in words))
        try:
            state = words[-1].state
        except IndexError:
            pass  # empty line -- no change to state
