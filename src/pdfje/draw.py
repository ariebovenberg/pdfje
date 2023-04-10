from __future__ import annotations

import abc
from dataclasses import dataclass
from typing import Iterable

from .common import RGB, XY, HexColor, Pt, add_slots, pipe, setattr_frozen
from .fonts.registry import Registry
from .style import StyleFull


class Drawing(abc.ABC):
    """Base class for all drawing operations wich can be put on
    a :class:`~pdfje.Page`."""

    __slots__ = ()

    @abc.abstractmethod
    def render(self, f: Registry, s: StyleFull, /) -> Iterable[bytes]:
        ...


@add_slots
@dataclass(frozen=True, init=False)
class Line(Drawing):
    """A :class:`~pdfje.Drawing` of a straight line segment.

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

    def render(self, _: Registry, __: StyleFull, /) -> Iterable[bytes]:
        yield b"%g %g m %g %g l " % (*self.start, *self.end)
        yield from _finish(None, self.stroke, False)


@add_slots
@dataclass(frozen=True, init=False)
class Rect(Drawing):
    """A :class:`~pdfje.Drawing` of a rectangle.

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

    def render(self, _: Registry, __: StyleFull, /) -> Iterable[bytes]:
        yield b"%g %g %g %g re " % (*self.origin, self.width, self.height)
        yield from _finish(self.fill, self.stroke, False)


@add_slots
@dataclass(frozen=True, init=False)
class Ellipse(Drawing):
    """A :class:`~pdfje.Drawing` of an ellipse.

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

    def render(self, _: Registry, __: StyleFull, /) -> Iterable[bytes]:
        yield from _ellipse(
            self.center, self.width, self.height, self.fill, self.stroke
        )


@add_slots
@dataclass(frozen=True, init=False)
class Circle(Drawing):
    """A :class:`~pdfje.Drawing` of a circle.

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

    def render(self, _: Registry, __: StyleFull, /) -> Iterable[bytes]:
        width = self.radius * 2
        yield from _ellipse(self.center, width, width, self.fill, self.stroke)


def _finish(
    fill: RGB | None, stroke: RGB | None, close: bool
) -> Iterable[bytes]:
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
) -> Iterable[bytes]:
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


@add_slots
@dataclass(frozen=True, init=False)
class Polyline(Drawing):
    """A :class:`~pdfje.Drawing` of a polyline.

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

    def render(self, _: Registry, __: StyleFull, /) -> Iterable[bytes]:
        it = iter(self.points)
        try:
            yield b"%g %g m " % next(it)
        except StopIteration:
            return
        yield from map(pipe(tuple, b"%g %g l ".__mod__), it)
        yield from _finish(self.fill, self.stroke, self.close)
