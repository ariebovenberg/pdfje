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
from typing import Generator, Iterable, Iterator

from . import fonts
from .common import BBox, Pt, add_slots, has_next
from .ops import Command, State

NonEmptyIterator = Iterator


@dataclass(frozen=True)
class Box:
    """a non-splittable unit of text"""

    content: fonts.Kerned
    width: Pt

    @staticmethod
    def build(t: State, s: str) -> Box:
        kerned = t.font.kern(s)
        return Box(kerned, (t.font.width(s) + kerned.space()) * t.size)


def to_boxes(
    items: Iterable[TextSpan], state: State
) -> Generator[BoxedSpan, None, State]:
    for group in _group_adjacent(_fold_commands(items)):
        state = yield from _group_to_boxes(state, group)
    return state


def take_line(
    s: Iterator[BoxedSpan], width: Pt
) -> tuple[Line | None, Iterator[BoxedSpan]]:
    try:
        span = next(s)
    except StopIteration:
        return None, s

    line, remainder = span.start_line(width)

    while line is None:
        try:
            span = next(s)
        except StopIteration:
            return None, s
        else:
            line, remainder = span.start_line(width)

    for span in s:
        if remainder:
            break
        line, remainder = span.continue_line(line)

    return line, (chain((remainder,), s) if remainder else s)


@add_slots
@dataclass(frozen=True)
class CompoundBox:
    """A box contaning one or more commands (e.g. style changes) within it"""

    prefix: Box
    segments: Iterable[tuple[Command, Box]]
    height: Pt

    @property
    def width(self) -> Pt:
        return self.prefix.width + sum(b.width for _, b in self.segments)


# For now we only consider ASCII space as word separator.
# This is reasonable for now since most unicode whitespace is not meant
# to break apart words.
_WORD = re.compile(r"[^ ]+")
_WORD_BETWEEN_SPACES = re.compile(r"(?<= )[^ ]+(?= )")
_WORD_WITH_TRAILING_SPACE = re.compile(r"[^ ]+(?= )")
_WORD_WITH_LEADING_SPACE = re.compile(r"(?<= )[^ ]+")
_TRAILING_RE = re.compile(r"[^ ]*\Z")  # always matches, at least empty string
_LEADING_RE = re.compile(r"\A[^ ]*")  # always matches, at least empty string


@add_slots
@dataclass(frozen=True)
class TextSpan:
    """A command and the following text it applies to"""

    command: Command
    content: str  # contains no linebreaks!

    def finditer(self, expr: re.Pattern) -> Iterator[str]:
        for m in expr.finditer(self.content):
            yield m.group()

    def trailing(self) -> str:
        # This re always matches, returning an empty string at the very least
        return _TRAILING_RE.search(self.content).group()  # type: ignore

    def leading(self) -> str:
        # This re always matches, returning an empty string at the very least
        return _LEADING_RE.search(self.content).group()  # type: ignore

    def has_space(self) -> bool:
        return " " in self.content

    def empty(self) -> bool:
        return not self.content

    def end_spaced(self) -> bool:
        return self.content.endswith(" ")

    def start_spaced(self) -> bool:
        return self.content.startswith(" ")


def _fill_line(
    bs: Iterator[Box], width: Pt, space: Pt, height: Pt
) -> tuple[SimpleLine, Iterator[Box]]:
    """Fill a line of given width with boxes until it doesn't fit anymore"""
    buffer: list[Box] = []
    for box in bs:
        if box.width <= width:
            buffer.append(box)
            width -= box.width + space
        else:
            bs = chain((box,), bs)
            break

    return SimpleLine(buffer, width, height), bs


def _fill_line_take_at_least_one(
    bs: Iterator[Box], width: Pt, space: Pt, height: Pt
) -> tuple[SimpleLine | None, Iterator[Box]]:
    """Fill a line, but try to take at least one box even if it doesn't fit"""
    line, bs = _fill_line(bs, width, space, height)
    if not line.content:
        try:
            line = SimpleLine([next(bs)], 0, height)
        except StopIteration:
            return None, bs
    return line, bs


@add_slots
@dataclass(frozen=True)
class CommandSpan:
    """A span divided into boxes"""

    command: Command
    boxes: Iterable[Box]
    spacewidth: Pt
    height: Pt

    def start_line(self, width: Pt) -> tuple[Line | None, BoxedSpan | None]:
        line, boxes = _fill_line_take_at_least_one(
            iter(self.boxes),
            width,
            self.spacewidth,
            self.height,
        )
        boxes, is_unfinished = has_next(boxes)
        return (
            None if line is None else CommandAnd(self.command, line),
            SimpleBoxSpan(boxes, self.spacewidth, self.height)
            if is_unfinished
            else None,
        )

    def continue_line(self, previous: Line) -> tuple[Line, BoxedSpan | None]:
        line, boxes = _fill_line(
            iter(self.boxes),
            previous.width_left,
            self.spacewidth,
            self.height,
        )
        if line.content:
            boxes, is_unfinished = has_next(boxes)
            return (
                Linked(previous, CommandAnd(self.command, line)),
                SimpleBoxSpan(boxes, self.spacewidth, self.height)
                if is_unfinished
                else None,
            )
        else:
            return previous, self


@add_slots
@dataclass(frozen=True)
class CompoundBoxSpan:
    """a box consisting of different parts with different text states"""

    head: CompoundBox
    tail: Iterable[Box]
    spacewidth: Pt
    tail_height: Pt

    def start_line(self, width: Pt) -> tuple[Line | None, BoxedSpan | None]:
        line, boxes = _fill_line(
            iter(self.tail),
            width - self.head.width - self.spacewidth,
            self.spacewidth,
            self.tail_height,
        )
        boxes, is_unfinished = has_next(boxes)
        return (
            CompoundBoxAnd(self.head, line),
            (
                SimpleBoxSpan(boxes, self.spacewidth, self.tail_height)
                if is_unfinished
                else None
            ),
        )

    def continue_line(self, previous: Line) -> tuple[Line, BoxedSpan | None]:
        if self.head.width <= previous.width_left:
            line, boxes = _fill_line(
                iter(self.tail),
                previous.width_left - self.head.width - self.spacewidth,
                self.spacewidth,
                self.tail_height,
            )
            boxes, is_unfinished = has_next(boxes)
            return (
                Linked(previous, CompoundBoxAnd(self.head, line)),
                SimpleBoxSpan(boxes, self.spacewidth, self.tail_height)
                if is_unfinished
                else None,
            )
        else:
            return previous, self


@add_slots
@dataclass(frozen=True)
class SimpleBoxSpan:
    """a box consisting of different parts with different text states"""

    boxes: Iterable[Box]
    spacewidth: Pt
    height: Pt

    def start_line(self, width: Pt) -> tuple[Line | None, BoxedSpan | None]:
        line, boxes = _fill_line_take_at_least_one(
            iter(self.boxes),
            width,
            self.spacewidth,
            self.height,
        )
        boxes, is_unfinished = has_next(boxes)
        return (
            line,
            SimpleBoxSpan(boxes, self.spacewidth, self.height)
            if is_unfinished
            else None,
        )

    def continue_line(self, previous: Line) -> tuple[Line, BoxedSpan | None]:
        line, boxes = _fill_line(
            iter(self.boxes),
            previous.width_left,
            self.spacewidth,
            self.height,
        )
        if line.content:
            boxes, is_unfinished = has_next(boxes)
            return (
                Linked(previous, line),
                SimpleBoxSpan(boxes, self.spacewidth, self.height)
                if is_unfinished
                else None,
            )
        else:
            return previous, self


BoxedSpan = CommandSpan | CompoundBoxSpan | SimpleBoxSpan


def _group_to_boxes(
    state: State,
    group: NonEmptyIterator[TextSpan],
) -> Generator[BoxedSpan, None, State]:
    """Reorganize adjoining spans into boxes"""

    first = next(group)
    state <<= first.command

    try:
        s = next(group)
    except StopIteration:
        yield CommandSpan(
            first.command,
            map(partial(Box.build, state), first.finditer(_WORD)),
            state.spacewidth(),
            state.size,
        )
        return state

    yield CommandSpan(
        first.command,
        map(
            partial(Box.build, state),
            first.finditer(_WORD_WITH_TRAILING_SPACE),
        ),
        state.spacewidth(),
        state.size,
    )

    head = Box.build(state, first.trailing())
    body: list[tuple[Command, Box]] = []
    height = state.size

    for following in group:
        state <<= s.command
        height = max(height, state.size)
        if s.has_space():
            body.append((s.command, Box.build(state, s.leading())))
            yield CompoundBoxSpan(
                CompoundBox(head, body, height),
                map(
                    partial(Box.build, state), s.finditer(_WORD_BETWEEN_SPACES)
                ),
                state.spacewidth(),
                state.size,
            )
            body = []
            head = Box.build(state, s.trailing())
            height = state.size
        else:
            body.append((s.command, Box.build(state, s.trailing())))
        s = following

    state <<= s.command
    body.append((s.command, Box.build(state, s.leading())))
    yield CompoundBoxSpan(
        CompoundBox(head, body, max(state.size, height)),
        map(partial(Box.build, state), s.finditer(_WORD_WITH_LEADING_SPACE)),
        state.spacewidth(),
        state.size,
    )
    return state


# TODO: make fully lazy as well
def _group_adjacent(
    it: Iterator[TextSpan],
) -> Iterator[NonEmptyIterator[TextSpan]]:
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


def _fold_commands(s: Iterable[TextSpan]) -> Iterator[TextSpan]:
    """Combine commands when encountering empty spans"""
    buffer: list[Command] = []
    for span in s:
        if span.empty():
            buffer.append(span.command)
        elif buffer:
            buffer.append(span.command)
            yield replace(span, command=reduce(add, buffer))
            buffer.clear()
        else:
            yield span

    if buffer:
        yield TextSpan(reduce(add, buffer), "")


class Line(abc.ABC):
    @property
    @abc.abstractmethod
    def width_left(self) -> Pt:
        ...

    @property
    @abc.abstractmethod
    def height(self) -> Pt:
        ...


@add_slots
@dataclass(frozen=True)
class CommandAnd(Line):
    command: Command
    line: SimpleLine  # TODO rename

    @property
    def width_left(self) -> Pt:
        return self.line.width_left

    @property
    def height(self) -> Pt:
        return self.line.height


@add_slots
@dataclass(frozen=True)
class CompoundBoxAnd(Line):
    head: CompoundBox
    line: SimpleLine

    @property
    def width_left(self) -> Pt:
        return self.line.width_left

    @property
    def height(self) -> Pt:
        return max(self.line.height, self.head.height)


@add_slots
@dataclass(frozen=True)
class SimpleLine(Line):
    content: Iterable[Box]
    width_left: Pt  # including trailing space
    height: Pt


@add_slots
@dataclass(frozen=True)
class Linked(Line):
    prev: Line
    next: Line

    @property
    def width_left(self) -> Pt:
        return self.next.width_left

    @property
    def height(self) -> Pt:
        return max(self.next.height, self.prev.height)
