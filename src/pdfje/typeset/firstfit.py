"A simple first-fit line wrapping algorithm."
from __future__ import annotations

from itertools import tee
from typing import Iterator, NamedTuple, Sequence

from ..common import XY, NonEmptyIterator, Pt, prepend
from .lines import Line
from .words import WordLike


def fill(
    ws: Iterator[WordLike] | None,
    columns: Iterator[XY],
    allow_empty: bool,
    lead: Pt,
) -> Iterator[Sequence[Line]]:
    "Fill the given columns with text, avoiding orphans where possible."
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


class _FilledBox(NamedTuple):
    rest: NonEmptyIterator[WordLike] | None
    lines: Sequence[Line]
    rest_incl_lastline: NonEmptyIterator[WordLike] | None


def take_box(
    ws: NonEmptyIterator[WordLike] | None,
    space: XY,
    allow_empty: bool,
    lead: Pt,
) -> _FilledBox:
    width, height = space
    max_lines = max(int(height // lead), not allow_empty)
    lines: list[Line] = []
    ws_undo = ws
    while ws and len(lines) < max_lines:
        # FUTURE: it'd be more optimal to only 'tee' on the last line
        ws, ws_undo = tee(ws)
        ws, ln = take_line(ws, width)
        lines.append(ln)
    return _FilledBox(ws, lines, ws_undo)


def take_line(
    ws: NonEmptyIterator[WordLike], width: Pt
) -> tuple[NonEmptyIterator[WordLike] | None, Line]:
    space = width
    content: list[WordLike] = []

    for word in ws:
        if word.pruned_width() > space:
            break

        space -= word.width()
        content.append(word)
    else:
        # i.e. this is the last line of the paragraph
        # TODO: catch case where there is no content
        return (None, Line(tuple(content), width - space, 0))

    last_word, dangling = word.hyphenate(space)
    ws = prepend(dangling, ws)
    if last_word:
        space -= last_word.width()
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
                return (None, Line((word,), word.width(), 0))
        content = [word]
        space -= word.width()

    return (ws, Line(tuple(content), width - space, space))
