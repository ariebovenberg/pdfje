from __future__ import annotations

from bisect import bisect
from dataclasses import dataclass
from math import inf
from typing import Callable, ClassVar, Iterable, Iterator, Protocol, Sequence

from pdfje.fonts.common import TEXTSPACE_TO_GLYPHSPACE

from ..atoms import LiteralStr, Real
from ..common import XY, Align, Pt, add_slots, peek
from ..compat import cache
from .knuth_plass import Box, Break, NoFeasibleBreaks, optimum_fit
from .layout import Line as _Line
from .layout import ShapedText
from .state import NO_OP, Command
from .words import WithCmd, Word, WordLike, render_kerned

_STRETCH_RATIO = 0.5
_SHRINK_RATIO = 1 / 3


class Parameters(Protocol):
    tolerance: float
    hyphen_penalty: float
    consecutive_hyphen_penalty: float
    fitness_diff_penalty: float


class ColumnQueue:
    lead: Pt
    _queue: Iterator[XY]  # (infinite) queue of columns
    columns: list[XY]  # columns which have already been read from the queue
    line_counts: list[int]  # number of lines in each column, cumulative.

    __slots__ = ("lead", "_queue", "columns", "line_counts")

    def __init__(
        self, queue: Iterable[XY], lead: Pt, allow_empty: bool
    ) -> None:
        self.lead = lead
        self._queue = queue = iter(queue)
        self.columns = [nextcol := next(queue)]
        self.line_counts = [int(nextcol.y // self.lead or not allow_empty)]

    def _next_column(self) -> XY:
        col = next(self._queue)
        self.columns.append(col)
        self.line_counts.append(
            self.line_counts[-1] + (int(col.y // self.lead) or 1)
        )
        return col

    def line_length(self, i: int) -> Pt:
        try:
            return self.columns[bisect(self.line_counts, i)].x
        except IndexError:
            while self.line_counts[-1] <= i:  # always true on first iteration
                col = self._next_column()
            return col.x

    def remove_first_column(self) -> None:
        self.columns.pop(0)
        firstcount = self.line_counts.pop(0)
        self.line_counts[:] = map(firstcount.__rsub__, self.line_counts)

    def shorten_column(self, i: int) -> None:
        self.line_counts[i:] = map((1).__rsub__, self.line_counts[i:])


@add_slots
@dataclass(frozen=True)
class Fragment:
    txt: WordLike
    on_break: WordLike | None
    cmd: Command


def _to_boxes(
    ws: Iterable[WordLike], justify: bool
) -> Iterator[tuple[Fragment, Box]]:
    width = 0.0
    shrink = 0.0
    if justify:
        stretch = 0.0
    else:
        try:
            word_first, ws = peek(iter(ws))
        except StopIteration:
            return
        # For ragged text, we need to specify a constant stretch.
        # good value is 3 times the width of a space (see knuth_plass.py)
        stretch = (
            word_first.state.size
            * (word_first.state.font.spacewidth / TEXTSPACE_TO_GLYPHSPACE)
            * 3
        )

    for word in ws:
        if isinstance(word, WithCmd):
            cmd = word.cmd
            word = word.word
        else:
            cmd = NO_OP
        for chunk in word.boxes[:-1]:
            with_hyphen = chunk.with_hyphen()
            width_new = width + chunk.width
            yield Fragment(
                chunk,
                with_hyphen,
                NO_OP,
            ), Box(
                width_new,
                stretch,
                shrink,
                width_new,
                width + with_hyphen.width,
                hyphenated=True,
                no_break=False,
            )
            width = width_new

        if word.tail:
            syllables = word.boxes[-1:]
            width += syllables[0].width if syllables else 0
            yield Fragment(
                Word(syllables, word.tail, word.state),
                syllables[0] if syllables else None,
                cmd,
            ), Box(
                width,
                stretch,
                shrink,
                # FUTURE: account for initial kern of the next word
                width_new := width + word.tail.width(),
                width,
                hyphenated=False,
                no_break=False,
            )
            # FUTURE: prevent running this every loop
            if justify:
                stretch += word.tail.width_excl_kern * _STRETCH_RATIO
                shrink += word.tail.width_excl_kern * _SHRINK_RATIO
            width = width_new
        else:  # a break made possible by non-space (e.g. a hyphen, or a dash)
            ending = word.boxes[-1]
            width += ending.width
            yield Fragment(ending, ending, cmd), Box(
                width,
                stretch,
                shrink,
                width,
                width,
                hyphenated=ending.last() in "-\N{EM DASH}",
                no_break=False,
            )


def into_boxes(
    ws: Iterable[WordLike], justify: bool
) -> tuple[Sequence[Fragment], Sequence[Box]]:
    [*result] = zip(*_to_boxes(ws, justify))
    if not result:  # i.e. there were no words
        return [], []
    return tuple(result)  # type: ignore[return-value]


@add_slots
@dataclass(frozen=True)
class Line(_Line):
    words: Sequence[WordLike]
    width: Pt

    def __iter__(self) -> Iterator[bytes]:
        content: Iterable[Real | LiteralStr] = ()
        for w in self.words:
            content = yield from w.encode_into_line(content)
        yield from render_kerned(content)

    def stretch(self, adjust: float) -> Line:
        return Line(
            [
                f.stretch_tail(
                    adjust * (_STRETCH_RATIO if adjust > 0 else _SHRINK_RATIO)
                )
                for f in self.words
            ],
            # FUTURE: we don't adjust the width here,
            # because we don't use it if the line is stretched.
            # Of course, this should be adressed in a nicer way.
            self.width,
        )

    EMPTY: ClassVar[Line]


Line.EMPTY = Line((), 0)


def _into_lines_justified(
    breaks: Sequence[Break], frags: Sequence[Fragment]
) -> Iterable[Line]:
    for br, line in zip(breaks, _into_lines_ragged(breaks, frags)):
        yield line.stretch(br.adjust)


def _into_lines_ragged(
    breaks: Sequence[Break], frags: Sequence[Fragment]
) -> Iterable[Line]:
    pos_prev = 0
    for br in breaks:
        *init, last = frags[pos_prev : br.pos]  # noqa: E203
        body = [f.txt.with_cmd(f.cmd) for f in init]
        if tail := last.on_break:
            body.append(tail.with_cmd(last.cmd))
        elif body:
            body[-1] = body[-1].with_cmd(last.cmd)
        else:
            # FUTURE: strictly speaking, we should do something here
            #         with last.cmd. However, in practice, it's always
            #         the last line, and it's almost always NO_OP.
            pass
        yield Line(body, br.width)
        pos_prev = br.pos


def find_breaks(
    boxes: Sequence[Box],
    line_length: Callable[[int], float],
    ragged: bool,
    params: Parameters,
) -> Sequence[Break]:
    assert boxes
    # OPTIMIZE: a smarter way of adjusting the tolerance
    for scale in 1, 2, 3, 5, 8, inf:
        try:
            return optimum_fit(
                boxes,
                line_length,
                params.tolerance * scale,
                params.hyphen_penalty,
                params.consecutive_hyphen_penalty,
                params.fitness_diff_penalty,
                ragged=ragged,
            )
        except NoFeasibleBreaks:
            pass
    else:  # pragma: no cover
        raise RuntimeError(
            "Error in optimal line breaking algorithm. "
            "Is the line length too small to fit single words? "
            "If not, please report this as a bug."
        )


def _lines_per_column(
    ls: Sequence[Line], counts: Iterable[int]
) -> Iterator[Sequence[Line]]:
    prev_index = 0
    for linecount in counts:
        lines_in_subpara = ls[prev_index:linecount]
        if not lines_in_subpara:
            break
        yield lines_in_subpara
        prev_index = linecount


def shape(
    ws: Iterator[WordLike],
    columns: Iterator[XY],
    allow_empty: bool,
    lead: Pt,
    avoid_orphans: bool,
    align: Align,
    params: Parameters,
) -> Iterator[ShapedText]:
    ragged = align is not Align.JUSTIFY
    into_lines = _into_lines_ragged if ragged else _into_lines_justified
    fragments, boxes = into_boxes(ws, justify=not ragged)

    col_queue = ColumnQueue(columns, lead, allow_empty)

    # if the first column has no lines, fast-forward to the next one
    if col_queue.line_counts[0] == 0:
        yield ShapedText((), lead, align, 0)
        col_queue = ColumnQueue(columns, lead, allow_empty=False)

    if not boxes:
        yield ShapedText((Line.EMPTY,), lead, align, lead)
        return

    breaks = find_breaks(boxes, cache(col_queue.line_length), ragged, params)
    lines = list(into_lines(breaks, fragments))

    # redo everything if there's an orphaned first line
    # OPTIMIZE: to prevent running the optimization twice, we could
    #           do an initial check if the first line will very *likely*
    #           be orphaned. This check can't be 100% accurate, but it
    #           would save time for obvious cases.
    if (
        avoid_orphans
        and allow_empty
        and col_queue.line_counts[0] == 1
        and len(lines) > 1
        and col_queue.line_counts[1] >= 2
    ):
        yield ShapedText((), lead, align, 0)
        col_queue.remove_first_column()
        breaks = find_breaks(
            boxes, cache(col_queue.line_length), ragged, params
        )
        lines = list(into_lines(breaks, fragments))

    grouped_lines = list(_lines_per_column(lines, col_queue.line_counts))

    # redo everything if there's an orphaned last line -- this may
    # need to happen multiple times if column widths are very different.
    if avoid_orphans:
        while (
            # we've found an orphaned last line
            len(grouped_lines[-1]) == 1
            # ...and there's enough room for another line
            and col_queue.line_counts[len(grouped_lines) - 1]
            - col_queue.line_counts[len(grouped_lines) - 2]
            > 1
            # ...and moving the previous line won't leave an orphan there
            and len(grouped_lines) > 1
            and len(grouped_lines[-2]) > 2
        ):
            col_queue.shorten_column(len(grouped_lines) - 2)
            breaks = find_breaks(
                boxes, cache(col_queue.line_length), ragged, params
            )
            lines = list(into_lines(breaks, fragments))
            grouped_lines_new = list(
                _lines_per_column(lines, col_queue.line_counts)
            )
            if (
                len(grouped_lines) == len(grouped_lines_new)
                and len(grouped_lines_new[-1]) == 1
            ):
                # Our attempt to fix the orphan failed. This can happen if
                # the last line is very long and the previous line is very
                # short. In this case, we'll just have to live with the
                # original orphan.
                break
            grouped_lines = grouped_lines_new  # FUTURE: test the need for this

    for ls in grouped_lines:
        yield ShapedText(ls, lead, align, len(ls) * lead)
