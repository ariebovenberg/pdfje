from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Iterator

from ..atoms import LiteralStr, Real
from ..common import Pt, Streamable, add_slots
from .words import WordLike, render_kerned


@add_slots
@dataclass(frozen=True)
class Line(Streamable):
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
                w.stretch_tail(width_per_break * w.state.size)
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
