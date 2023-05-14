from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Iterator, Sequence

from ..atoms import LiteralStr, Real
from ..common import BranchableIterator, Pt, Streamable, add_slots
from .common import SetFont, SetLineSpacing, State, Stretch
from .words import WithCmd, Word
from .words import parse as parse_words
from .words import render_kerned


@add_slots
@dataclass(frozen=True)
class Line(Streamable):
    words: tuple[Word | WithCmd, ...]
    width: Pt
    space: Pt

    # TODO: remove special case?
    def state(self) -> State | None:
        if self.words:
            return self.words[-1].state
        return None

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
            self.width + self.space,
            0,
        )

    def __iter__(self) -> Iterator[bytes]:
        content: Iterable[Real | LiteralStr] = ()
        for w in self.words:
            content = yield from w.encode_into_line(content)
        yield from render_kerned(content)


def _indent_first(
    ws: Iterable[Word | WithCmd], amount: Pt
) -> Iterator[Word | WithCmd]:
    it = iter(ws)
    try:
        first = next(it)
    except StopIteration:
        return
    yield first.indent(amount)
    yield from it


def _max_lead(s: Iterable[Stretch], state: State) -> Pt:
    # TODO: we apply commands elsewhere, so doing it also here
    # is perhaps a bit wasteful
    lead = state.lead
    for cmd, _ in s:
        state = cmd.apply(state)
        lead = max(lead, state.lead)
    return lead


@add_slots
@dataclass(frozen=True)
class Wrapper:
    """Wraps text into lines.

    Taking content results in a new wrapper instance, so that the original
    can be used do undo/redo/rewind lines."""

    queue: BranchableIterator[Word | WithCmd]
    state: State
    lead: Pt

    @staticmethod
    def start(
        it: Iterable[Stretch],
        state: State,
        indent: Pt,
    ) -> Wrapper:
        it = list(it)
        cmd, words = parse_words(it, state)
        return Wrapper(
            BranchableIterator(_indent_first(words, indent)),
            cmd.apply(state),
            _max_lead(it, state),
        )

    def line(self, width: Pt) -> tuple[Line, Wrapper | WrapDone]:
        queue = self.queue.branch()
        space = width
        content: list[Word | WithCmd] = []

        for word in queue:
            if word.pruned_width() > space:
                break

            space -= word.width()
            content.append(word)
        else:
            # i.e. this is the last line of the paragraph
            return (
                (
                    Line(tuple(content), width - space, 0),
                    WrapDone(word.state),
                )
                if content
                else (Line((), 0, 0), WrapDone(self.state))
            )

        last_word, dangling = word.hyphenate(space)
        queue.prepend(dangling)
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
            word, leftover = next(queue).minimal_box()
            if leftover:
                queue.prepend(leftover)
            content = [word]
            space -= word.width()

        return Line(tuple(content), width - space, space), Wrapper(
            queue, content[-1].state, self.lead
        )

    # TODO: make this a simple function?
    def iterlines(self, width: Pt) -> Iterator[tuple[Wrapper, Line]]:
        w: Wrapper | WrapDone = self
        while isinstance(w, Wrapper):
            ln, w_next = w.line(width)
            yield w, ln
            w = w_next

    def fill(
        self, width: Pt, height: Pt, allow_empty: bool
    ) -> tuple[LineStack, Wrapper | WrapDone]:
        w: Wrapper | WrapDone
        if allow_empty:
            w = self
            lines = []
        else:
            ln, w = self.line(width)
            lines = [ln]
            height -= self.lead
        while isinstance(w, Wrapper):
            ln, w_new = w.line(width)
            height -= self.lead
            if height < 0:
                return LineStack(lines, height + self.lead, self.lead), w
            lines.append(ln)
            w = w_new
        return LineStack(lines, height, self.lead), w


@add_slots
@dataclass
class LineStack:
    lines: Sequence[Line]
    height_left: Pt
    lead: Pt

    def height(self) -> Pt:
        return len(self.lines) * self.lead


@add_slots
@dataclass(frozen=True)
class WrapDone:
    state: State
