from dataclasses import dataclass
from itertools import tee
from operator import attrgetter
from typing import Callable, Iterable, Iterator, Literal, Sequence, final

from pdfje.typeset import firstfit
from pdfje.typeset.lines import Line
from pdfje.typeset.words import indent_first, parse

from ..common import (
    XY,
    Align,
    NonEmptyIterator,
    Pt,
    Streamable,
    add_slots,
    pipe,
    prepend,
    setattr_frozen,
)
from ..resources import Resources
from ..style import Span, Style, StyledMixin, StyleFull, StyleLike
from ..typeset.common import Passage, State, max_lead, splitlines
from .common import Block, ColumnFill


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
        self, res: Resources, style: StyleFull, cs: Iterator[ColumnFill]
    ) -> Iterator[ColumnFill]:
        style |= self.style
        state = style.as_state(res)
        passages = list(self.flatten(res, style))
        lead = max_lead(passages, state)
        col = next(cs)
        for para in splitlines(passages):
            [*filled, col], state = _fill_subparagraph(
                para, prepend(col, cs), state, self.indent, lead, self.align
            )
            yield from filled
        yield col


def _fill_subparagraph(
    txt: NonEmptyIterator[Passage],
    cs: Iterator[ColumnFill],
    state: State,
    indent: Pt,
    lead: Pt,
    align: Align,
) -> tuple[Iterable[ColumnFill], State]:
    done: list[ColumnFill] = []
    col = next(cs)
    allow_empty = bool(col.blocks)
    cmd, words = parse(txt, state)
    state = cmd.apply(state)
    cs, _branch = tee(prepend(col, cs))
    for lines, col in zip(  # pragma: no branch
        firstfit.fill(
            indent_first(words, indent),
            (XY(c.box.width, c.height_free) for c in _branch),
            allow_empty=allow_empty,
            lead=lead,
        ),
        cs,
    ):
        done.append(
            col.add(
                TypesetText(
                    col.cursor(), lines, state, align, col.box.width, lead
                ),
                len(lines) * lead,
            )
        )
        try:
            state = lines[-1].words[-1].state
        except IndexError:
            # its OK -- just an empty subparagraph. The state doesn't change.
            pass

    return done, state


@add_slots
@dataclass(frozen=True)
class TypesetText(Streamable):
    origin: XY
    lines: Sequence[Line]
    state: State
    align: Align
    width: Pt
    lead: Pt

    def __iter__(self) -> Iterator[bytes]:
        yield b"BT\n%g %g Td\n" % self.origin.astuple()
        yield from self.state
        yield from _pick_renderer(self.align)(
            self.lines, self.lead, self.width
        )
        yield b"ET\n"


# _T = TypeVar("_T")


# def _iter_index(it: Iterator[_T]) -> Callable[[int], _T]:
#     cache: list[_T] = []

#     def get(i: int) -> _T:
#         try:
#             return cache[i]
#         except IndexError:
#             cache.extend(islice(it, i - len(cache) + 1))
#             return cache[i]

#     return get


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
