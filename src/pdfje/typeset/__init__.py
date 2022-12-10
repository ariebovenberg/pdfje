"""Logic for positioning text into lines and pages.

What makes this so complex is the fact that the text state (font, size, etc.)
can change mid-line and even mid-word.
Most of the seemingly complicated code is to ensure style and word boundaries
are respected in all edge cases -- while keeping the performance of the common
case lean.

The typesetting process roughly goes through these stages:
0. We are given a text string with different styles spanning parts of it.
1. We convert text into boxes -- groups of characters (typically words)
   that need to stick together. It's possible for one box to contain
   several style changes.
2. We group these boxes into lines.
"""
from __future__ import annotations

import abc
import re
from dataclasses import dataclass, replace
from functools import partial, reduce
from itertools import chain
from operator import add
from typing import Generator, Iterable, Iterator, Sequence

from .. import ops
from ..atoms import Array, LiteralString, Real
from ..common import (
    XY,
    PeekableIterator,
    Pt,
    add_slots,
    prepend,
    skips_to_first_yield,
)
from ..fonts.common import GlyphPt
from ..ops import State, StateChange
from .common import CompoundWord, Span, Word

NonEmptyIterator = Iterator
NonEmptySequence = Sequence


@add_slots
@dataclass(frozen=True)
class Frame:
    bottomleft: XY
    width: Pt
    height: Pt

    def topleft(self) -> XY:
        return replace(self.bottomleft, y=self.bottomleft.y + self.height)


@add_slots
@dataclass(frozen=True)
class PositionedLines(ops.Object):
    location: XY
    init: State
    lines: Iterable[Linelike]

    def into_stream(self) -> Iterable[bytes]:
        leading = self.init.leading()
        yield b"BT\n%g %g Td\n/%b %g Tf\n%g TL\n%g %g %g rg\n" % (
            *self.location,
            self.init.font.id,
            self.init.size,
            leading,
            *self.init.color.astuple(),
        )
        for n in self.lines:
            # TODO: test
            if n.leading == leading:
                yield b"T*\n"
            else:
                yield b"0 %g TD\n" % -n.leading
            yield from n.into_stream()
        yield b"ET\n"


@skips_to_first_yield
def to_graphics(
    bs: SpanIterator,
    # TODO: also return end state?
    # TODO: control whether to take at least one or not.
) -> Generator[ops.Object, Frame, tuple[ops.Object, Frame]]:
    bounds = yield  # type: ignore[misc]

    state_init = bs.state
    if not (line := bs.take_line(bounds.width)):
        return (ops.NOTHING, bounds)

    height = bounds.height - line.leading
    width = bounds.width
    content = [line]

    while True:
        state_prev = bs.state
        if not (line := bs.take_line(bounds.width)):
            # There are no more lines, so we exit the generator,
            # returning the leftover space.
            return PositionedLines(
                bounds.topleft(), state_init, content
            ), replace(bounds, height=height)
        elif line.leading <= height:
            height -= line.leading
            content.append(line)
        else:
            bounds = yield PositionedLines(
                bounds.topleft(), state_init, content
            )
            # Margins are consistent in most documents. This check
            # saves us a lot of effort, because we don't need to rebuild
            # the line if the width is already what we need it to be.
            content = [
                line
                if width == bounds.width
                else bs.retake_line(line, state_prev, bounds.width)
            ]
            state_init = state_prev
            width = bounds.width
            height = bounds.height - line.leading


# For now we only consider ASCII space as word separator.
# This is reasonable for now since most unicode whitespace are not meant
# to break apart words.
_WORD = re.compile(r"[^ ]+")
_WORD_BETWEEN_SPACES = re.compile(r"(?<= )[^ ]+(?= )")
_WORD_WITH_TRAILING_SPACE = re.compile(r"[^ ]+(?= )")
_WORD_WITH_LEADING_SPACE = re.compile(r"(?<= )[^ ]+")


def _fill_line(
    ws: PeekableIterator[Word],
    width: Pt,
    space: Pt,
    leading: Pt,
    spacechar: bytes,
) -> Line:
    """Fill a line of given width with words until it doesn't fit anymore"""
    buffer: list[Word] = []
    for word in iter(ws.peek, None):
        if word.width <= width:
            buffer.append(word)
            width -= word.width + space
            next(ws)
        else:
            break
    return Line(buffer, space, spacechar, width, leading)


def _fill_line_take_at_least_one(
    bs: PeekableIterator[Word],
    width: Pt,
    space: Pt,
    leading: Pt,
    spacechar: bytes,
) -> Line | None:
    """Fill a line, but try to take at least one word even if it doesn't fit"""
    line = _fill_line(bs, width, space, leading, spacechar)
    if not line.content:
        if bs.exhausted():
            return None
        else:
            return Line([next(bs)], space, spacechar, 0, leading)
    return line


@add_slots
@dataclass(frozen=True)
class CommandSpan:
    command: StateChange
    tail: Boxes

    def start_line(self, width: Pt) -> tuple[CommandAnd | None, Boxed | None]:
        ln, boxed = self.tail.start_line(width)
        return (
            (ln and CommandAnd(self.command, ln)),
            boxed,
        )  # type: ignore[return-value]

    def continue_line(
        self, previous: Linelike
    ) -> tuple[Linelike, Boxed | None]:
        line = _fill_line(
            self.tail.words,
            previous.width_left,
            self.tail.spacewidth,
            self.tail.leading,
            self.tail.spacechar,
        )
        # TODO: better test coverage
        if line.content:
            return (
                Linked(
                    previous,
                    CommandAnd(self.command, line),
                ),
                None if self.tail.words.exhausted() else self.tail,
            )
        else:
            return previous, None if self.tail.words.exhausted() else self


@add_slots
@dataclass(frozen=True)
class CompoundBoxSpan:
    head: CompoundWord
    tail: Boxes

    def start_line(self, width: Pt) -> tuple[Linelike | None, Boxed | None]:
        line = _fill_line(
            self.tail.words,
            width - self.head.width - self.tail.spacewidth,
            self.tail.spacewidth,
            self.tail.leading,
            self.tail.spacechar,
        )
        return (
            CompoundBoxAnd(self.head, line),
            (None if self.tail.words.exhausted() else self.tail),
        )

    def continue_line(
        self, previous: Linelike
    ) -> tuple[Linelike, Boxed | None]:
        if self.head.width <= previous.width_left:
            line = _fill_line(
                self.tail.words,
                previous.width_left - self.head.width - self.tail.spacewidth,
                self.tail.spacewidth,
                self.tail.leading,
                self.tail.spacechar,
            )
            return (
                Linked(
                    previous,
                    CompoundBoxAnd(self.head, line),
                ),
                None if self.tail.words.exhausted() else self.tail,
            )
        else:
            return previous, self


@add_slots
@dataclass(frozen=True)
class Boxes:
    words: PeekableIterator[Word]
    spacewidth: Pt
    leading: Pt
    spacechar: bytes

    def start_line(self, width: Pt) -> tuple[Line | None, Boxed | None]:
        line = _fill_line_take_at_least_one(
            self.words,
            width,
            self.spacewidth,
            self.leading,
            self.spacechar,
        )
        return (line, None if self.words.exhausted() else self)

    def continue_line(
        self, previous: Linelike
    ) -> tuple[Linelike, Boxed | None]:
        line = _fill_line(
            self.words,
            previous.width_left,
            self.spacewidth,
            self.leading,
            self.spacechar,
        )
        if line.content:
            return (
                Linked(previous, line),
                None if self.words.exhausted() else self,
            )
        else:
            return previous, None if self.words.exhausted() else self


Boxed = CommandSpan | CompoundBoxSpan | Boxes


@add_slots
@dataclass
class SpanIterator(Iterator[Boxed]):
    items: Iterator[tuple[Boxed, State]]
    state: State = State.DEFAULT

    def __next__(self) -> Boxed:
        span, self.state = next(self.items)
        return span

    def _undo(self, ln: Linelike, state: State) -> None:
        self.state = state
        self.items = chain(self._add_states(ln.explode(), state), self.items)

    def retake_line(
        self, ln: Linelike, prev_state: State, width: Pt
    ) -> Linelike:
        self._undo(ln, prev_state)
        # we can assume the outcome of the next line is never None,
        # since we just 'undid' a line
        return self.take_line(width)  # type: ignore[return-value]

    def take_line(self, width: Pt) -> Linelike | None:
        line: Linelike | None = None
        while line is None:
            try:
                span = next(self)
            except StopIteration:
                # case: there is no content, so there is no line to output
                return None
            line, leftovers = span.start_line(width)

        while not leftovers:
            try:
                span = next(self)
            except StopIteration:
                # case: we've run out of content,
                # so we output what we have so far
                return line
            line, leftovers = span.continue_line(line)
        # case: we've run out of space, since there is content left over
        self.items = prepend((leftovers, self.state), self.items)
        return line

    @staticmethod
    def _add_states(
        it: Iterable[Boxed], state: State
    ) -> Iterator[tuple[Boxed, State]]:
        for b in it:
            if isinstance(b, CommandSpan):
                yield b, (state := b.command.apply(state))
            elif isinstance(b, CompoundBoxSpan):
                for command, _ in b.head.segments:
                    state = command.apply(state)
                yield b, state
            else:
                yield b, state


def to_words(
    items: Iterable[Span], state: State
) -> Iterator[tuple[Boxed, State]]:
    for group in _group_adjacent(_fold_commands(items)):
        state = yield from _group_to_boxes(state, group)


def _group_to_boxes(
    state: State,
    group: NonEmptyIterator[Span],
) -> Generator[tuple[Boxed, State], None, State]:
    """Reorganize adjoining spans into boxes"""

    first = next(group)
    state = first.command.apply(state)

    try:
        span = next(group)
    except StopIteration:
        yield CommandSpan(
            first.command,
            Boxes(
                PeekableIterator(
                    map(partial(Word.build, state), first.finditer(_WORD))
                ),
                state.spacewidth(),
                state.leading(),
                state.spacechar(),
            ),
        ), state
        return state

    yield CommandSpan(
        first.command,
        Boxes(
            PeekableIterator(
                map(
                    partial(Word.build, state),
                    first.finditer(_WORD_WITH_TRAILING_SPACE),
                )
            ),
            state.spacewidth(),
            state.leading(),
            state.spacechar(),
        ),
    ), state

    head = Word.build(state, first.trailing())
    body: list[tuple[StateChange, Word]] = []
    leading = state.leading()

    for following in group:
        state = span.command.apply(state)
        leading = max(leading, state.leading())
        if span.has_space():
            body.append((span.command, Word.build(state, span.head())))
            yield CompoundBoxSpan(
                CompoundWord(head, body, leading),
                Boxes(
                    PeekableIterator(
                        map(
                            partial(Word.build, state),
                            span.finditer(_WORD_BETWEEN_SPACES),
                        )
                    ),
                    state.spacewidth(),
                    state.leading(),
                    state.spacechar(),
                ),
            ), state
            body = []
            head = Word.build(state, span.trailing())
            leading = state.leading()
        else:
            body.append((span.command, Word.build(state, span.trailing())))
        span = following

    state = span.command.apply(state)
    body.append((span.command, Word.build(state, span.head())))
    yield CompoundBoxSpan(
        CompoundWord(head, body, max(state.leading(), leading)),
        Boxes(
            PeekableIterator(
                map(
                    partial(Word.build, state),
                    span.finditer(_WORD_WITH_LEADING_SPACE),
                )
            ),
            state.spacewidth(),
            state.leading(),
            state.spacechar(),
        ),
    ), state
    return state


# TODO: make fully lazy as well
def _group_adjacent(
    it: Iterator[Span],
) -> Iterator[NonEmptyIterator[Span]]:
    """Group spans together when they aren't separated by space"""
    try:
        a = next(it)
    except StopIteration:
        return

    buffer = [a]
    for b in it:
        if a.end_spaced() or b.start_spaced():
            yield iter(buffer)
            buffer = [b]
        else:
            buffer.append(b)
        a = b

    yield iter(buffer)


def _fold_commands(s: Iterable[Span]) -> Iterator[Span]:
    """Combine commands when encountering empty spans"""
    buffer: list[StateChange] = []
    for span in s:
        buffer.append(span.command)
        if not span.empty():
            yield replace(span, command=reduce(add, buffer))
            buffer.clear()

    if buffer:
        yield Span(reduce(add, buffer), "")


class Linelike(abc.ABC):
    __slots__ = ()

    @property
    @abc.abstractmethod
    def width_left(self) -> Pt:  # including trailing space
        ...

    @property
    @abc.abstractmethod
    def leading(self) -> Pt:
        ...

    @abc.abstractmethod
    def explode(self) -> Iterable[Boxed]:
        ...

    @abc.abstractmethod
    def into_stream(self) -> Iterator[bytes]:
        ...


# @dataclass
# class MultiLine(Linelike):
#     content:


@add_slots
@dataclass(frozen=True)
class Line(Linelike):
    content: Sequence[Word]
    spacewidth: Pt
    spacechar: bytes
    width_left: Pt
    leading: Pt

    def explode(self) -> Iterator[Boxes]:
        yield Boxes(
            PeekableIterator(self.content),
            self.spacewidth,
            self.leading,
            self.spacechar,
        )

    def into_stream(self) -> Iterator[bytes]:
        yield from _write_boxes(self.content, self.spacechar)


@add_slots
@dataclass(frozen=True)
class CommandAnd(Linelike):
    command: StateChange
    tail: Line

    @property
    def width_left(self) -> Pt:
        return self.tail.width_left

    @property
    def leading(self) -> Pt:
        return self.tail.leading

    def explode(self) -> Iterable[Boxed]:
        yield CommandSpan(self.command, next(self.tail.explode()))

    def into_stream(self) -> Iterator[bytes]:
        yield from self.command.into_stream()
        yield from self.tail.into_stream()


@add_slots
@dataclass(frozen=True)
class CompoundBoxAnd(Linelike):
    head: CompoundWord
    tail: Line

    @property
    def leading(self) -> Pt:
        return max(self.head.leading, self.tail.leading)

    @property
    def width_left(self) -> Pt:
        return self.tail.width_left

    def explode(self) -> Iterable[Boxed]:
        yield CompoundBoxSpan(self.head, next(self.tail.explode()))

    def into_stream(self) -> Iterator[bytes]:
        # TODO implement
        raise NotImplementedError()


@add_slots
@dataclass(frozen=True)
class Linked(Linelike):
    prev: Linelike
    next: Linelike

    @property
    def width_left(self) -> Pt:
        return self.next.width_left

    @property
    def leading(self) -> Pt:
        return max(self.next.leading, self.prev.leading)

    def explode(self) -> Iterable[Boxed]:
        yield from self.prev.explode()
        yield from self.next.explode()

    def into_stream(self) -> Iterator[bytes]:
        yield from self.prev.into_stream()
        yield from self.next.into_stream()


def _write_boxes(boxes: Sequence[Word], space: bytes) -> Iterator[bytes]:
    if not boxes:
        return
    txt = space.join(b.content for b in boxes)
    kerning = list(Word.chain_kerning(boxes, len(space)))
    if kerning:
        yield from Array(_text_and_spaces(txt, kerning)).write()
        yield b" TJ\n"
    else:
        yield from LiteralString(txt).write()
        yield b" Tj\n"


def _text_and_spaces(
    s: bytes, kerning: NonEmptySequence[tuple[int, GlyphPt]]
) -> Iterable[LiteralString | Real]:
    index_prev, space = kerning[0]

    if index_prev == 0:  # i.e. we kern before any text
        yield Real(-space)
        kerning = kerning[1:]

    index_prev = index = 0
    for index, space in kerning:
        yield LiteralString(s[index_prev:index])
        yield Real(-space)
        index_prev = index

    if index != len(s):
        yield LiteralString(s[index:])
