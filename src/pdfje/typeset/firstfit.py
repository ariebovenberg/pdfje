"A simple first-fit line wrapping algorithm."
from __future__ import annotations

from typing import Sequence

from ..common import NonEmptyIterator, Pt, prepend
from .lines import Line
from .words import WordLike


def box(
    ws: NonEmptyIterator[WordLike] | None,
    width: Pt,
    height: Pt,
    allow_empty: bool,
    lead: Pt,
) -> tuple[NonEmptyIterator[WordLike] | None, Sequence[Line]]:
    max_lines = max(int(height // lead), not allow_empty)
    lines: list[Line] = []
    while ws and len(lines) < max_lines:
        ws, ln = take_line(ws, width)
        lines.append(ln)
    return ws, lines


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
        # TODO: catch no content case
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
