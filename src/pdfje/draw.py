from __future__ import annotations

import abc
from dataclasses import dataclass
from operator import attrgetter
from typing import Callable, Iterable, Iterator, Literal, final

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
from .fonts.registry import Registry
from .style import Span, Style, StyledMixin, StyleFull, StyleLike
from .typeset.common import Command, State, Stretch, splitlines
from .typeset.lines import Line as TextLine
from .typeset.words import parse as parse_words

__all__ = [
    "Circle",
    "Ellipse",
    "Line",
    "Polyline",
    "Rect",
    "Text",
    "Drawing",
]


class Drawing(abc.ABC):
    """Base class for all drawing operations wich can be put on
    a :class:`~pdfje.Page`."""

    __slots__ = ()

    @abc.abstractmethod
    def render(self, f: Registry, s: StyleFull, /) -> Streamable:
        ...


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

    def render(self, _: Registry, __: StyleFull, /) -> Streamable:
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

    def render(self, _: Registry, __: StyleFull, /) -> Streamable:
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

    def render(self, _: Registry, __: StyleFull, /) -> Streamable:
        yield from _ellipse(
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

    def render(self, _: Registry, __: StyleFull, /) -> Streamable:
        width = self.radius * 2
        yield from _ellipse(self.center, width, width, self.fill, self.stroke)


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

    def render(self, _: Registry, __: StyleFull, /) -> Streamable:
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
    content: str | Span | ~typing.Iterable[str | Span]
        The text to render. Can be a string, or a nested :class:`~pdfje.Span`.
    style
        The style to apply to the text.
    align
        The horizontal alignment of the text.
    """

    loc: XY
    content: Iterable[str | Span]
    style: Style
    align: Align

    def __init__(
        self,
        loc: XY | tuple[float, float],
        content: str | Span | Iterable[str | Span],
        style: StyleLike = Style.EMPTY,
        align: Align | Literal["left", "center", "right"] = Align.LEFT,
    ) -> None:
        if isinstance(content, (str, Span)):
            content = [content]
        setattr_frozen(self, "loc", XY.parse(loc))
        setattr_frozen(self, "content", content)
        setattr_frozen(self, "style", Style.parse(style))
        setattr_frozen(self, "align", Align.parse(align))
        if self.align is Align.JUSTIFY:
            raise NotImplementedError(
                "Justified alignment not implemented for explicitly "
                "positioned text."
            )

    def render(self, r: Registry, s: StyleFull, /) -> Streamable:
        state = s.as_state(r)
        yield b"BT\n%g %g Td\n" % self.loc.astuple()
        yield from state
        yield from _pick_renderer(self.align)(
            into_words(splitlines(self.flatten(r, s)), state), state.lead, 0
        )
        yield b"ET\n"


def into_words(
    split: Iterable[Iterable[Stretch]], state: State
) -> Iterator[tuple[Command, TextLine]]:
    for s in split:
        cmd, [*words] = parse_words(s, state)
        yield (
            cmd,
            TextLine(
                tuple(words),
                max(w.lead() for w in words),
                sum(w.width() for w in words),
                0,
            ),
        )
        state = words[-1].state


def _render_left(
    lines: Iterable[tuple[Command, TextLine]], lead: Pt, _: Pt
) -> Iterator[bytes]:
    yield b"%g TL\n" % lead
    for cmd, ln in lines:
        yield from cmd
        if ln.lead == lead:
            yield b"T*\n"
        else:
            yield b"0 %g TD\n" % -ln.lead
            lead = ln.lead
        yield from ln


def _render_centered(
    lines: Iterable[tuple[Command, TextLine]], _: Pt, width: Pt
) -> Iterator[bytes]:
    for cmd, ln in lines:
        yield from cmd
        yield b"%g %g TD\n" % ((width - ln.width) / 2, -ln.lead)
        yield from ln
        width = ln.width


def _render_right(
    lines: Iterable[tuple[Command, TextLine]], _: Pt, width: Pt
) -> Iterator[bytes]:
    for cmd, ln in lines:
        yield from cmd
        yield b"%g %g TD\n" % ((width - ln.width), -ln.lead)
        yield from ln
        width = ln.width


_pick_renderer: Callable[
    [Align],
    Callable[[Iterable[tuple[Command, TextLine]], Pt, Pt], Iterable[bytes]],
] = pipe(
    attrgetter("value"),
    [
        _render_left,
        _render_centered,
        _render_right,
        _render_left,
    ].__getitem__,
)
