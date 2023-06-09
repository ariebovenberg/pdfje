from __future__ import annotations

import abc
from dataclasses import dataclass
from itertools import chain
from operator import methodcaller
from typing import Iterable, Iterator, Literal, Sequence, final

from . import atoms
from .atoms import OBJ_ID_PAGETREE, OBJ_ID_RESOURCES
from .common import (
    XY,
    Sides,
    SidesLike,
    Streamable,
    add_slots,
    flatten,
    setattr_frozen,
)
from .resources import Resources
from .style import StyleFull
from .units import A4, Pt, inch

Rotation = Literal[0, 90, 180, 270]


class Drawing(abc.ABC):
    """Base class for all drawing operations wich can be put on
    a :class:`~pdfje.Page`."""

    __slots__ = ()

    @abc.abstractmethod
    def render(self, r: Resources, s: StyleFull, /) -> Streamable:
        ...


@final
@add_slots
@dataclass(frozen=True, init=False)
class Column:
    """A column to lay out block elements in.

    Parameters
    ----------
    origin
        The bottom left corner of the column. Can be parsed from a 2-tuple.
    width
        The width of the column. Must be larger than 0.
    height
        The height of the column.

    """

    origin: XY
    width: Pt
    height: Pt

    def __init__(
        self, origin: XY | tuple[Pt, Pt], width: Pt, height: Pt
    ) -> None:
        setattr_frozen(self, "origin", XY.parse(origin))
        setattr_frozen(self, "width", width)
        setattr_frozen(self, "height", height)
        assert self.width > 0


@add_slots
@dataclass(frozen=True)
class RenderedPage:
    rotate: Rotation
    size: XY
    stream: Streamable

    def to_atoms(self, i: atoms.ObjectID) -> Iterable[atoms.Object]:
        yield i, atoms.Dictionary(
            (b"Type", atoms.Name(b"Page")),
            (b"Parent", atoms.Ref(OBJ_ID_PAGETREE)),
            (b"MediaBox", atoms.Array(map(atoms.Real, [0, 0, *self.size]))),
            (b"Contents", atoms.Ref(i + 1)),
            (b"Resources", atoms.Ref(OBJ_ID_RESOURCES)),
            (b"Rotate", atoms.Int(self.rotate)),
        )
        yield i + 1, atoms.Stream(self.stream)


@final
@add_slots
@dataclass(frozen=True, init=False)
class Page:
    """A single page within a document. Contains drawings at given positions.

    Example
    -------

    .. code-block:: python

       from pdfje import Page, Line, Rect, Text, A5
       title_page = Page([
           Text((100, 200), "My awesome story"),
           Line((100, 100), (200, 100)),
           Rect((50, 50), width=200, height=300),
       ], size=A5)

    Parameters
    ----------
    content
        The drawings to render on the page.
    size
        The size of the page in points. Common page sizes are available
        as constants:

        .. code-block:: python

            from pdfje.units import Page, A4, A5, A6, letter, legal, tabloid

    rotate
        The rotation of the page in degrees.
    margin
        The margin around the page in points, used for layout.
        Can be a single value, or a 2, 3 or 4-tuple following the CSS
        shorthand convention. see https://www.w3schools.com/css/css_margin.asp
    columns
        The columns to use for laying out the content.
        If not given, the content is laid out in a single column
        based on the page size and margin.

    """

    content: Iterable[Drawing]
    size: XY
    rotate: Rotation
    columns: Sequence[Column]

    def __init__(
        self,
        content: Iterable[Drawing] = (),
        size: XY | tuple[Pt, Pt] = A4,
        rotate: Rotation = 0,
        margin: SidesLike = Sides.parse(inch(1)),
        columns: Sequence[Column] = (),
    ) -> None:
        size = XY.parse(size)
        setattr_frozen(self, "content", content)
        setattr_frozen(self, "rotate", rotate)
        setattr_frozen(self, "columns", columns or [_column(size, margin)])
        setattr_frozen(self, "size", size)

    def add(self, d: Drawing, /) -> Page:
        """Create a new page with the given drawing added

        Parameters
        ----------
        d
            The drawing to add to the page
        """
        return Page(
            (*self.content, d), self.size, self.rotate, columns=self.columns
        )

    def render(
        self, r: Resources, s: StyleFull, pnum: int, /
    ) -> Iterator[RenderedPage]:
        yield RenderedPage(
            self.rotate,
            self.size,
            flatten(map(methodcaller("render", r, s), self.content)),
        )

    def fill(
        self, r: Resources, s: StyleFull, extra: Iterable[bytes]
    ) -> RenderedPage:
        return RenderedPage(
            self.rotate,
            self.size,
            chain(
                flatten(map(methodcaller("render", r, s), self.content)),
                extra,
            ),
        )


def _column(page: XY, margin: SidesLike) -> Column:
    top, right, bottom, left = Sides.parse(margin)
    return Column(
        XY(left, bottom), page.x - left - right, page.y - top - bottom
    )
