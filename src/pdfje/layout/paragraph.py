from __future__ import annotations

from dataclasses import dataclass
from functools import partial
from itertools import tee
from typing import (
    ClassVar,
    Iterable,
    Iterator,
    Literal,
    Protocol,
    Sequence,
    cast,
    final,
)

from ..common import XY, Align, Pt, add_slots, advance, prepend, setattr_frozen
from ..resources import Resources
from ..style import Span, Style, StyledMixin, StyleFull, StyleLike
from ..typeset import firstfit, optimum
from ..typeset.layout import ShapedText
from ..typeset.parse import into_words
from ..typeset.state import Passage, State, max_lead, splitlines
from ..typeset.words import WordLike, indent_first
from .common import Block, ColumnFill


@add_slots
@dataclass(frozen=True)
class LinebreakParams:
    """Parameters for tweaking the optimum-fit algorithm.

    Parameters
    ----------
    tolerance
        The tolerance for the stretch of each line.
        If no feasible solution is found, the tolerance is increased until
        there is.
        Increase the tolerance if you want to avoid hyphenation
        at the cost of more stretching and longer runtime.
    hyphen_penalty
        The penalty for hyphenating a word. If increasing this value does
        not result in fewer hyphens, try increasing the tolerance.
    consecutive_hyphen_penalty
        The penalty for placing hyphens on consecutive lines. If increasing
        this value does not appear to work, try increasing the tolerance.
    fitness_diff_penalty
        The penalty for very tight and very loose lines following each other.
    """

    tolerance: float = 1
    hyphen_penalty: float = 1000
    consecutive_hyphen_penalty: float = 1000
    fitness_diff_penalty: float = 1000

    DEFAULT: ClassVar["LinebreakParams"]


LinebreakParams.DEFAULT = LinebreakParams()


@final
@add_slots
@dataclass(frozen=True, init=False)
class Paragraph(Block, StyledMixin):
    """A :class:`Block` that renders a paragraph of text.

    Parameters
    ----------
    content
        The text to render. Can be a string, or a nested :class:`~pdfje.Span`.
    style
        The style to render the text with.
        See :ref:`tutorial<style>` for more details.
    align: Align | ``"left"`` | ``"center"`` | ``"right"`` | ``"justify"``
        The horizontal alignment of the text.
    indent
        The amount of space to indent the first line of the paragraph.
    avoid_orphans
        Whether to avoid orphans (single lines before or after a page or
        column break).
    optimal
        Whether to use the optimal paragraph layout algorithm.
        If set to ``False`` or ``None``, a faster but less optimal algorithm
        is used. To customize the algorithm parameters, pass an
        :class:`~pdfje.layout.LinebreakParams` object.

    Examples
    --------

    .. code-block:: python

        from pdfje.layout import Paragraph
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
            style=times_roman,
            optimal=False,
        )

    """

    content: Sequence[str | Span]
    style: Style
    align: Align
    indent: Pt
    avoid_orphans: bool
    optimal: LinebreakParams | None

    def __init__(
        self,
        content: str | Span | Sequence[str | Span],
        style: StyleLike = Style.EMPTY,
        align: Align
        | Literal["left", "center", "right", "justify"] = Align.LEFT,
        indent: Pt = 0,
        avoid_orphans: bool = True,
        optimal: LinebreakParams | bool | None = True,
    ):
        if isinstance(content, (str, Span)):
            content = [content]
        setattr_frozen(self, "content", content)
        setattr_frozen(self, "style", Style.parse(style))
        setattr_frozen(self, "align", Align.parse(align))
        setattr_frozen(self, "indent", indent)
        setattr_frozen(self, "avoid_orphans", avoid_orphans)
        if isinstance(optimal, bool):
            optimal = LinebreakParams.DEFAULT if optimal else None
        setattr_frozen(self, "optimal", optimal)

    def into_columns(
        self, res: Resources, style: StyleFull, cs: Iterator[ColumnFill]
    ) -> Iterator[ColumnFill]:
        style |= self.style
        state = style.as_state(res)
        passages = list(self.flatten(res, style))
        lead = max_lead(passages, state)
        col = next(cs)
        for para in splitlines(passages):
            cs, _branch = tee(prepend(col, cs))
            [*filled, col], state = _fill_paragraph(
                iter(para),
                _branch,
                state,
                self.indent,
                lead,
                self.align,
                self.avoid_orphans,
                shape=cast(
                    Shaper,
                    (partial(optimum.shape, params=self.optimal))
                    if self.optimal
                    else firstfit.shape,
                ),
            )
            advance(cs, len(filled) + 1)
            yield from filled
        yield col


class Shaper(Protocol):
    def __call__(
        self,
        ws: Iterator[WordLike],
        columns: Iterator[XY],
        allow_empty: bool,
        lead: Pt,
        avoid_orphans: bool,
        align: Align,
    ) -> Iterator[ShapedText]:
        ...


def _fill_paragraph(
    txt: Iterator[Passage],
    cs: Iterator[ColumnFill],
    state: State,
    indent: Pt,
    lead: Pt,
    align: Align,
    avoid_orphans: bool,
    shape: Shaper,
) -> tuple[Iterable[ColumnFill], State]:
    done: list[ColumnFill] = []
    col = next(cs)
    allow_empty = bool(col.blocks)
    cmd, words = into_words(txt, state)
    state = cmd.apply(state)
    cs, _branch = tee(prepend(col, cs))
    for chunk, col in zip(  # pragma: no branch
        shape(
            indent_first(words, indent),
            (XY(c.box.width, c.height_free) for c in _branch),
            allow_empty=allow_empty,
            lead=lead,
            align=align,
            avoid_orphans=avoid_orphans,
        ),
        cs,
    ):
        done.append(col.add(chunk))
        state = chunk.end_state() or state
    return done, state
