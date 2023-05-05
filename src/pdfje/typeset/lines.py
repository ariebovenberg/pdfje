from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Iterator, Sequence

from ..atoms import LiteralStr, Real
from ..common import BranchableIterator, Pt, Streamable, add_slots
from .common import State, Stretch
from .words import WithCmd, Word
from .words import parse as parse_words
from .words import render_kerned


@add_slots
@dataclass(frozen=True)
class Line(Streamable):
    words: tuple[Word | WithCmd, ...]
    lead: Pt
    width: Pt
    space: Pt

    def indent(self, amount: Pt) -> Line:
        if amount and self.words:
            return Line(
                (self.words[0].indent(amount), *self.words[1:]),
                self.lead,
                self.width + amount,
                self.space,
            )
        return self

    def justify(self) -> Line:
        try:
            # The additional width per word break, weighted by the font size,
            # which is needed to justify the text.
            width_per_break = self.space / sum(
                w.state.size for w in self.words if w.tail
            )
        except ZeroDivisionError:
            return self  # No word breaks, no justification.
        return Line(
            tuple(
                w.stretch_tail(width_per_break * w.state.size)
                for w in self.words
            ),
            self.lead,
            self.width + self.space,
            0,
        )

    def __iter__(self) -> Iterator[bytes]:
        content: Iterable[Real | LiteralStr] = ()
        for w in self.words:
            content = yield from w.encode_into_line(content)
        yield from render_kerned(content)


@add_slots
@dataclass(frozen=True)
class Wrapper:
    """Wraps text into lines.

    Taking content results in a new wrapper instance, so that the original
    can be used do undo/redo/rewind lines."""

    queue: BranchableIterator[Word | WithCmd]
    state: State

    @staticmethod
    def start(it: Iterable[Stretch], state: State) -> Wrapper:
        cmd, words = parse_words(it, state)
        return Wrapper(BranchableIterator(words), cmd.apply(state))

    def line(self, width: Pt) -> tuple[Line, Wrapper | WrapDone]:
        queue = self.queue.branch()
        space = width
        content: list[Word | WithCmd] = []
        lead: Pt = 0

        for word in queue:
            if word.pruned_width() > space:
                break

            space -= word.width()
            content.append(word)
            lead = max(lead, word.lead())
        else:
            # i.e. this is the last line of the paragraph
            return (
                (
                    Line(tuple(content), lead, width - space, 0),
                    WrapDone(word.state),
                )
                if content
                else (Line((), self.state.lead, 0, 0), WrapDone(self.state))
            )

        last_word, dangling = word.hyphenate(space)
        queue.prepend(dangling)
        if last_word:
            space -= last_word.width()
            lead = max(lead, last_word.lead())
            content.append(last_word)
        elif content and (extra_space := content[-1].prunable_space()):
            content[-1] = content[-1].pruned()
            space += extra_space
        elif not content:
            # We force placing at least a minimal word fragment to avoid
            # infinitely waiting for enough width.
            # This shouldn't occur in practice often, where the column
            # width is much larger than the longest word segment.
            word, leftover = next(queue).minimal_box()
            if leftover:
                queue.prepend(leftover)
            content = [word]
            lead = word.lead()
            space -= word.width()

        return Line(tuple(content), lead, width - space, space), Wrapper(
            queue, content[-1].state
        )

    def fill(
        self, width: Pt, height: Pt, allow_empty: bool
    ) -> tuple[LineSet, Wrapper | WrapDone]:
        w: Wrapper | WrapDone
        if allow_empty:
            w = self
            lines = []
        else:
            ln, w = self.line(width)
            lines = [ln]
            height -= ln.lead
        while isinstance(w, Wrapper):
            ln, w_new = w.line(width)
            height -= ln.lead
            if height < 0:
                return LineSet(lines, height + ln.lead), w
            lines.append(ln)
            w = w_new
        return LineSet(lines, height), w


@add_slots
@dataclass
class LineSet:
    lines: Sequence[Line]
    height_left: Pt


@add_slots
@dataclass(frozen=True)
class WrapDone:
    state: State
