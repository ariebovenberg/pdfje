from __future__ import annotations

import abc
from dataclasses import dataclass
from itertools import islice, tee
from operator import attrgetter
from typing import (
    Callable,
    Generator,
    Iterable,
    Iterator,
    Literal,
    Protocol,
    Sequence,
    TypeVar,
    final,
)

from .common import (
    RGB,
    XY,
    Align,
    HexColor,
    Sides,
    SidesLike,
    Streamable,
    add_slots,
    black,
    flatten,
    pipe,
    prepend,
    setattr_frozen,
)
from .page import Column, Page
from .resources import Resources
from .style import Span, Style, StyledMixin, StyleFull, StyleLike
from .typeset import firstfit
from .typeset.common import Passage, State, max_lead, splitlines
from .typeset.lines import Line
from .typeset.words import WordLike, indent_first, parse
from .units import Pt

__all__ = [
    "Paragraph",
    "Rule",
    "Block",
    "Align",
]


class Block(abc.ABC):
    """Base class for block elements that can be laid out in a column
    by :class:`~pdfje.AutoPage`.
    """

    __slots__ = ()

    @abc.abstractmethod
    def layout(
        self, res: Resources, col: ColumnFill, style: StyleFull
    ) -> Generator[ColumnFill, Column, ColumnFill]:
        ...

    # why not a generator? Because a block may need to consume multiple
    # columns to render itself, before starting to yield completed columns
    @abc.abstractmethod
    def fill(
        self, res: Resources, style: StyleFull, cs: Iterator[ColumnFill], /
    ) -> Iterator[ColumnFill]:
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
    typeset

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

    def fill(
        self,
        res: Resources,
        style: StyleFull,
        cs: Iterator[ColumnFill],
    ) -> Iterator[ColumnFill]:
        style |= self.style
        state = style.as_state(res)
        passages = list(self.flatten(res, style))
        lead = max_lead(passages, state)
        # TODO: use in optimum_fit
        # cs, branch = tee(cs)
        # line_length = _iter_index(
        #     flatten(
        #         repeat(c.box.width, int(c.height_free // lead)) for c in branch
        #     )
        # )
        breakpoint()
        yield next(cs)

    def layout(
        self, res: Resources, col: ColumnFill, style: StyleFull
    ) -> Generator[ColumnFill, Column, ColumnFill]:
        style |= self.style
        state = style.as_state(res)
        passages = list(self.flatten(res, style))
        lead = max_lead(passages, state)
        for para in splitlines(passages):
            col, state = yield from layout_paragraph(
                para, col, self.align, self.indent, lead, state
            )
        return col


_T = TypeVar("_T")


def _iter_index(it: Iterator[_T]) -> Callable[[int], _T]:
    cache: list[_T] = []

    def get(i: int) -> _T:
        try:
            return cache[i]
        except IndexError:
            cache.extend(islice(it, i - len(cache) + 1))
            return cache[i]

    return get


@add_slots
@dataclass(frozen=True)
class ColumnFill(Streamable):
    box: Column
    blocks: Sequence[Iterable[bytes]]
    height_free: Pt

    @staticmethod
    def new(col: Column) -> ColumnFill:
        return ColumnFill(col, [], col.height)

    def add(self, e: Iterable[bytes], height: Pt) -> ColumnFill:
        return ColumnFill(
            self.box, (*self.blocks, e), self.height_free - height
        )

    def cursor(self) -> XY:
        return self.box.origin.add_y(self.height_free)

    def __iter__(self) -> Iterator[bytes]:
        yield from flatten(self.blocks)


def layout_paragraph(
    content: Iterable[Passage],
    col: ColumnFill,
    align: Align,
    indent: Pt,
    lead: Pt,
    state: State,
) -> Generator[ColumnFill, Column, tuple[ColumnFill, State]]:
    words: Iterator[WordLike] | None
    cmd, words = parse(content, state)
    state = cmd.apply(state)
    words = indent_first(words, indent)

    # If the first line won't fit, start a new column and start over.
    if lead > col.height_free and col.blocks:
        box = yield col
        col = ColumnFill.new(box)

    words, stack = firstfit.box(
        words,
        col.box.width,
        col.height_free,
        allow_empty=bool(col.blocks),
        lead=lead,
    )

    while words:
        box = yield col.add(
            _render_text(
                col.cursor(), stack, state, align, col.box.width, lead
            ),
            len(stack) * lead,
        )
        if stack and stack[-1].words:
            state = stack[-1].words[-1].state
        words, stack = firstfit.box(
            words, box.width, box.height, allow_empty=False, lead=lead
        )
        col = ColumnFill.new(box)

    return (
        col.add(
            _render_text(
                col.cursor(), stack, state, align, col.box.width, lead
            ),
            len(stack) * lead,
        ),
        state,
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
    """A :class:`Block` that draws a horizontal line as a section break.

    i.e. if the rule would coincide with a page or column break,
    it is not drawn.
    """

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
        self, _: Resources, fill: ColumnFill, __: StyleFull
    ) -> Generator[ColumnFill, Column, ColumnFill]:
        top, right, bottom, left = self.margin
        if fill.height_free < top + bottom:
            fill = ColumnFill.new((yield fill))

        y = fill.box.origin.y + fill.height_free - top
        x = fill.box.origin.x + left
        return fill.add(
            _render_line(
                XY(x, y),
                XY(x + fill.box.width - left - right, y),
                self.color,
            ),
            top + bottom,
        )

    def fill(
        self, _: Resources, __: StyleFull, cs: Iterator[ColumnFill]
    ) -> Iterator[ColumnFill]:
        col = next(cs)
        top, right, bottom, left = self.margin
        if (height := top + bottom) > col.height_free:
            # There is not enough room for the rule in the current column.
            # Yield the column and start a new one.
            # Because the column already serves as a separator, we don't
            # need to draw the rule.
            yield col
        else:
            y = col.box.origin.y + col.height_free - top
            x = col.box.origin.x + left
            yield col.add(
                _render_line(
                    XY(x, y),
                    XY(col.box.origin.x + col.box.width - right, y),
                    self.color,
                ),
                height,
            )


def _render_line(start: XY, end: XY, color: RGB) -> Streamable:
    yield b"%g %g m %g %g l %g %g %g RG S\n" % (*start, *end, *color)


class Filler(Protocol):
    def __call__(
        self, nextcol: Iterator[ColumnFill], /
    ) -> Iterator[ColumnFill]:
        ...


@dataclass(frozen=True)
class PageFill:
    base: Page
    todo: Sequence[ColumnFill]
    done: Sequence[ColumnFill]


DocFill = Iterator[PageFill]


def fill_columns(
    doc: DocFill, f: Filler
) -> tuple[DocFill, Sequence[PageFill]]:
    trunk, branch = tee(doc)
    return _fill_into(f(flatten(p.todo for p in branch)), trunk)


def _fill_into(
    cs: Iterable[ColumnFill], doc: Iterator[PageFill]
) -> tuple[DocFill, Sequence[PageFill]]:
    completed: list[PageFill] = []
    for page in doc:
        cols = list(islice(cs, len(page.todo)))
        completed.append(
            PageFill(
                page.base, page.todo[len(cols) :], (*page.done, *cols)  # noqa
            )
        )
        if len(cols) < len(page.todo):
            break
    return prepend(completed.pop(), doc), completed
