from __future__ import annotations

import abc
from dataclasses import dataclass
from operator import attrgetter
from typing import (
    Callable,
    Generator,
    Iterable,
    Iterator,
    Literal,
    Sequence,
    final,
)

from .common import (
    RGB,
    XY,
    Align,
    HexColor,
    Pt,
    Sides,
    SidesLike,
    Streamable,
    add_slots,
    black,
    flatten,
    pipe,
    setattr_frozen,
)
from .fonts.registry import Registry
from .style import Span, Style, StyledMixin, StyleFull, StyleLike
from .typeset.common import State, splitlines
from .typeset.lines import Line, WrapDone, Wrapper

__all__ = [
    "Paragraph",
    "Rule",
    "Block",
    "Align",
]


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
        The width of the column.
    height
        The height of the column.

    """

    origin: XY
    width: Pt
    height: Pt

    def __init__(
        self, origin: XY | tuple[float, float], width: Pt, height: Pt
    ) -> None:
        setattr_frozen(self, "origin", XY.parse(origin))
        setattr_frozen(self, "width", width)
        setattr_frozen(self, "height", height)


class Block(abc.ABC):
    """Base class for block elements that can be laid out in a column
    by :class:`~pdfje.AutoPage`.
    """

    __slots__ = ()

    @abc.abstractmethod
    def layout(
        self, fr: Registry, col: ColumnFill, style: StyleFull
    ) -> Generator[ColumnFill, Column, ColumnFill]:
        ...


@final
@add_slots
@dataclass(frozen=True, init=False)
class Paragraph(Block, StyledMixin):
    """A :class:`Block` that renders a paragraph of text.

    Parameters
    ----------
    content: str | Span | ~typing.Iterable[str | Span]
        The text to render. Can be a string, or a nested :class:`~pdfje.Span`.
    style
        The style to render the text with.
        See :ref:`tutorial<style>` for more details.
    align: Align | ``"left"`` | ``"center"`` | ``"right"`` | ``"justify"``
        The horizontal alignment of the text.
    indent
        The amount of space to indent the first line of the paragraph.

    Examples
    --------

    .. code-block:: python

        from pdfje.blocks import Paragraph
        from pdfje.style import Style

        Paragraph(
            "This is a paragraph of text.",
            style="#003311",
            align="center",
        )
        Paragraph(
            [
                "It can also be ",
                Span("styled", "#00ff00"),
                " in multiple ",
                Span("ways", Style(size=14, italic=True)),
                ".",
            ],
            style=times_roman
        )

    """

    content: Sequence[str | Span]
    style: Style
    align: Align
    indent: Pt

    def __init__(
        self,
        content: str | Span | Sequence[str | Span],
        style: StyleLike = Style.EMPTY,
        align: Align
        | Literal["left", "center", "right", "justify"] = Align.LEFT,
        indent: Pt = 0,
    ):
        if isinstance(content, (str, Span)):
            content = [content]
        setattr_frozen(self, "content", content)
        setattr_frozen(self, "style", Style.parse(style))
        setattr_frozen(self, "align", Align.parse(align))
        setattr_frozen(self, "indent", indent)

    def layout(
        self, fr: Registry, col: ColumnFill, style: StyleFull
    ) -> Generator[ColumnFill, Column, ColumnFill]:
        style |= self.style
        state = style.as_state(fr)
        for strs in splitlines(self.flatten(fr, style)):
            wrap: Wrapper | WrapDone = Wrapper.start(strs, state, self.indent)
            assert isinstance(wrap, Wrapper)  # spans is non-empty
            col, state = yield from _layout_paragraph(wrap, col, self.align)
        return col


class Element(Streamable):
    @property
    @abc.abstractmethod
    def height(self) -> Pt:
        raise NotImplementedError()


@add_slots
@dataclass(frozen=True)
class ColumnFill(Iterable[bytes]):
    col: Column
    blocks: Sequence[Iterable[bytes]]
    height_free: Pt

    @staticmethod
    def new(col: Column) -> ColumnFill:
        return ColumnFill(col, [], col.height)

    def add(self, e: Iterable[bytes], height: Pt) -> ColumnFill:
        return ColumnFill(
            self.col, (*self.blocks, e), self.height_free - height
        )

    def cursor(self) -> XY:
        return self.col.origin.add_y(self.height_free)

    def __iter__(self) -> Iterator[bytes]:
        yield from flatten(self.blocks)


def _layout_paragraph(
    wrap: Wrapper,
    fill: ColumnFill,
    align: Align,
) -> Generator[ColumnFill, Column, tuple[ColumnFill, State]]:
    state = wrap.state

    # If the first line won't fit, start a new column and start over.
    if wrap.lead > fill.height_free and fill.blocks:
        col = yield fill
        fill = ColumnFill.new(col)

    stack, w = wrap.fill(
        fill.col.width, fill.height_free, allow_empty=bool(fill.blocks)
    )

    while isinstance(w, Wrapper):
        col = yield fill.add(
            _render_text(
                fill.cursor(), stack, state, align, fill.col.width, wrap.lead
            ),
            len(stack) * wrap.lead,
        )
        state = w.state
        stack, w = w.fill(col.width, col.height, allow_empty=False)
        fill = ColumnFill.new(col)

    return (
        fill.add(
            _render_text(
                fill.cursor(), stack, state, align, fill.col.width, wrap.lead
            ),
            len(stack) * wrap.lead,
        ),
        w.state,
    )


def _render_left(lines: Iterable[Line], lead: Pt, _: Pt) -> Iterator[bytes]:
    yield b"%g TL\n" % lead
    for ln in lines:
        yield b"T*\n"
        yield from ln


def _render_justified(
    lines: Iterable[Line], lead: Pt, width: Pt
) -> Iterator[bytes]:
    return _render_left(map(Line.justify, lines), lead, width)


def _render_centered(
    lines: Iterable[Line], lead: Pt, width: Pt
) -> Iterator[bytes]:
    for ln in lines:
        yield b"%g %g TD\n" % ((width - ln.width) / 2, -lead)
        yield from ln
        width = ln.width


def _render_right(
    lines: Iterable[Line], lead: Pt, width: Pt
) -> Iterator[bytes]:
    for ln in lines:
        yield b"%g %g TD\n" % ((width - ln.width), -lead)
        yield from ln
        width = ln.width


_pick_renderer: Callable[
    [Align], Callable[[Iterable[Line], Pt, Pt], Iterable[bytes]]
] = pipe(
    attrgetter("value"),
    [
        _render_left,
        _render_centered,
        _render_right,
        _render_justified,
    ].__getitem__,
)


def _render_text(
    origin: XY,
    lines: Iterable[Line],
    state: State,
    align: Align,
    width: Pt,
    lead: Pt,
) -> Iterator[bytes]:
    yield b"BT\n%g %g Td\n" % origin.astuple()
    yield from state
    yield from _pick_renderer(align)(lines, lead, width)
    yield b"ET\n"


@final
@add_slots
@dataclass(frozen=True, init=False)
class Rule(Block):
    """A :class:`Block` that draws a horizontal line."""

    color: RGB
    margin: Sides

    def __init__(
        self,
        color: RGB | HexColor = black,
        margin: SidesLike = Sides(6, 0, 6, 0),
    ) -> None:
        setattr_frozen(self, "color", RGB.parse(color))
        setattr_frozen(self, "margin", Sides.parse(margin))

    def layout(
        self, _: Registry, fill: ColumnFill, __: StyleFull
    ) -> Generator[ColumnFill, Column, ColumnFill]:
        top, right, bottom, left = self.margin
        if fill.height_free < top + bottom:
            fill = ColumnFill.new((yield fill))

        y = fill.col.origin.y + fill.height_free - top
        x = fill.col.origin.x + left
        return fill.add(
            _render_line(
                XY(x, y),
                XY(x + fill.col.width - left - right, y),
                self.color,
            ),
            top + bottom,
        )


def _render_line(start: XY, end: XY, color: RGB) -> Streamable:
    yield b"%g %g m %g %g l %g %g %g RG S\n" % (*start, *end, *color)
