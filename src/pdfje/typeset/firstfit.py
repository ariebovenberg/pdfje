"A simple first-fit line wrapping algorithm."
from __future__ import annotations

from dataclasses import dataclass
from itertools import tee
from typing import Iterable, Iterator, NamedTuple, Sequence

from ..atoms import LiteralStr, Real
from ..common import XY, Align, NonEmptyIterator, Pt, add_slots, prepend
from .layout import Line as _Line
from .layout import ShapedText
from .words import WordLike, render_kerned


def shape(
    words: Iterator[WordLike],
    columns: Iterator[XY],
    allow_empty: bool,
    lead: Pt,
    avoid_orphans: bool,
    align: Align,
) -> Iterator[ShapedText]:
    _shape = _shape_avoid_orphans if avoid_orphans else _shape_simple
    return (
        (
            ShapedText(
                list(map(Line.justify, ls)), lead, align, len(ls) * lead
            )
            for ls in _shape(words, columns, allow_empty, lead)
        )
        if align is Align.JUSTIFY
        else (
            ShapedText(ls, lead, align, len(ls) * lead)
            for ls in _shape(words, columns, allow_empty, lead)
        )
    )


def _shape_avoid_orphans(
    ws: Iterator[WordLike] | None,
    columns: Iterator[XY],
    allow_empty: bool,
    lead: Pt,
) -> Iterator[Sequence[Line]]:
    col = next(columns)
    ws, lines, ws_undo = take_box(ws, col, allow_empty, lead)
    # In case of an avoidable orphan, start over
    if ws and len(lines) == 1 and allow_empty:
        ws = ws_undo
        lines = ()
    elif not ws:
        yield lines
        return

    col = next(columns)
    while True:
        lines_prev = lines
        ws_undo_prev = ws_undo
        ws, lines, ws_undo = take_box(ws, col, False, lead)
        # case: paragraph not done. Continue to next column.
        if ws:
            yield lines_prev
            col = next(columns)
        # case: a potentially fixable orphan
        elif len(lines) == 1 and len(lines_prev) > 2 and col.y >= lead * 2:
            # FUTURE: optimize the case where the column widths are the same,
            #         and we don't need to re-typeset the last line.
            assert ws_undo_prev is not None
            ws_undo_prev, _branch = tee(ws_undo_prev)
            _, _lines_new, ws_undo = take_box(_branch, col, False, lead)
            if len(_lines_new) == 1:
                break  # our attempt to fix the orphan failed. We're done.
            else:
                lines = lines_prev[:-1]
                ws = ws_undo_prev
        # case: we're done, but no (fixable) orphan.
        else:
            break

    yield lines_prev
    yield lines


# filling is a lot simpler if we don't avoid orphaned lines.
def _shape_simple(
    ws: Iterator[WordLike] | None,
    columns: Iterator[XY],
    allow_empty: bool,
    lead: Pt,
) -> Iterator[Sequence[Line]]:
    for col in columns:  # pragma: no branch
        ws, lines, _ = take_box(ws, col, allow_empty, lead)
        yield lines
        if not ws:
            return
        allow_empty = False


class _FilledBox(NamedTuple):
    rest: NonEmptyIterator[WordLike] | None
    lines: Sequence[Line]
    rest_incl_lastline: NonEmptyIterator[WordLike] | None


def take_box(
    queue: NonEmptyIterator[WordLike] | None,
    space: XY,
    allow_empty: bool,
    lead: Pt,
) -> _FilledBox:
    width, height = space
    max_line_count: float = height // lead or not allow_empty
    lines: list[Line] = []
    queue_prev = queue
    while queue and len(lines) < max_line_count:
        # OPTIMIZE: it'd be more efficient to only 'tee' on the last line
        queue, queue_prev = tee(queue)
        queue, ln = take_line(queue, width)
        lines.append(ln)
    return _FilledBox(queue, lines, queue_prev)


def take_line(
    ws: NonEmptyIterator[WordLike], width: Pt
) -> tuple[NonEmptyIterator[WordLike] | None, Line]:
    space = width
    content: list[WordLike] = []

    for word in ws:
        if word.pruned_width() > space:
            break

        space -= word.width
        content.append(word)
    else:
        # i.e. this is the last line of the paragraph
        return (None, Line(tuple(content), width - space, 0))

    last_word, dangling = word.hyphenate(space)
    ws = prepend(dangling, ws)
    if last_word:
        space -= last_word.width
        content.append(last_word)
    elif content and (extra_space := content[-1].prunable_space()):
        content[-1] = content[-1].pruned()
        space += extra_space
    elif not content:
        # We force placing at least a minimal word fragment to avoid
        # infinitely waiting for enough width.
        # This shouldn't occur in practice often, where the column
        # width is much larger than the longest word segment.
        word, leftover = next(ws).minimal_box()
        if leftover:
            ws = prepend(leftover, ws)
        else:
            # An extra check is needed to tell whether this is the last
            # word in the paragraph.
            try:
                ws = prepend(next(ws), ws)
            except StopIteration:
                return (None, Line((word,), word.width, 0))
        content = [word]
        space -= word.width

    return (ws, Line(tuple(content), width - space, space))


@add_slots
@dataclass(frozen=True)
class Line(_Line):
    words: tuple[WordLike, ...]
    width: Pt
    space: Pt

    def justify(self) -> Line:
        try:
            # The additional width per word break, weighted by the font size,
            # which is needed to justify the text.
            width_per_break = self.space / sum(
                w.state.size for w in self.words if w.tail
            )
        except ZeroDivisionError:
            return self  # No word breaks means no justification.
        return Line(
            tuple(
                w.extend_tail(width_per_break * w.state.size)
                for w in self.words
            ),
            self.width + self.space,
            0,
        )

    def __iter__(self) -> Iterator[bytes]:
        content: Iterable[Real | LiteralStr] = ()
        for w in self.words:
            content = yield from w.encode_into_line(content)
        yield from render_kerned(content)
