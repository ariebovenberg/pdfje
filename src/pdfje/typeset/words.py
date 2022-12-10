from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass, replace
from functools import partial
from itertools import chain, repeat
from operator import methodcaller
from typing import (
    ClassVar,
    Generator,
    Iterable,
    Iterator,
    NamedTuple,
    Sequence,
    cast,
)

from ..common import (
    XY,
    Char,
    Pt,
    add_slots,
    flatten,
    prepend,
    second,
    skips_to_first_yield,
)
from ..fonts import TEXTSPACE_TO_GLYPHSPACE, Font, GlyphPt
from ..ops import MultiCommand, State, StateChange
from .common import Span

NonEmptyIterator = Iterator
StringIndex = int

_INIT_BODY_LAST_RE = re.compile("([^ ]* *)(.* |)([^ ]*)")
_BODY_AND_LAST_RE = re.compile("(.* )([^ ]+)")
_INIT_AND_BODY_RE = re.compile("([^ ]* *)(.+)")
_BREAK_RE = re.compile(r"(?: +|[^ ]\Z)")

Kern = tuple[StringIndex, GlyphPt]
Kerning = Sequence[Kern]


def split(spans: Iterable[Span], /) -> Iterator[Words]:
    """Split and merge spans at word boundaries"""
    return flatten(
        map(_adjacent_spans_into_words, _group_adjacent(_fold_commands(spans)))
    )


def _stack(
    it: Iterable[Line], height: Pt
) -> tuple[Sequence[Line], Pt, Line | None]:
    buffer: list[Line] = []
    for line in it:
        if line.lead > height:
            return buffer, height, line
        else:
            buffer.append(line)
            height -= line.lead

    return buffer, height, None


def _stack_atleast1(
    it: Iterator[Line], height: Pt
) -> tuple[Sequence[Line], Pt, Line | None]:
    lines, height, excess = _stack(it, height)
    if excess and not lines:
        lines = [excess]
        height -= excess.lead
        excess = next(it, None)
    return lines, height, excess


def typeset(
    ws: Iterable[Words], state: State, frame: Frame
) -> Generator[Frame, Box, Frame]:
    box = frame.capacity
    height = box.height
    width = box.width
    gen = wrap(ws, state)

    lines, height, excess = (_stack if frame.blocks else _stack_atleast1)(
        map(gen.send, repeat(width)), height
    )
    frame = (
        Frame(
            [*frame.blocks, Paragraph(lines, state)],
            replace(box, height=height),
        )
        if lines
        else frame
    )

    if excess is None:
        return frame
    else:
        box = yield frame

    if lines:
        state = lines[-1].state

    height = box.height - excess.lead
    assert box.width == width  # TODO

    while True:
        lines, height, next_excess = _stack(
            map(gen.send, repeat(width)), height
        )
        if next_excess is None:
            return Frame(
                [Paragraph([excess, *lines], state)],
                replace(box, height=height),
            )
        else:
            box = yield Frame(
                [Paragraph([excess, *lines], state)],
                replace(box, height=height),
            )
            height -= next_excess.lead
            excess = next_excess
            state = lines[-1].state
            height = box.height
        assert box.width == width  # TODO


@add_slots
@dataclass(frozen=True)
class Paragraph:
    lines: Sequence[Line]
    state: State


@add_slots
@dataclass(frozen=True)
class Box:
    loc: XY
    width: Pt
    height: Pt


@add_slots
@dataclass(frozen=True)
class Frame:
    blocks: Sequence[Paragraph]
    capacity: Box


# TODO: pos vs idx
@add_slots
@dataclass(frozen=True)
class Passage:
    txt: str  # non-empty
    pos: int = 0  # TODO explain

    def wrap(self, prev: PartialLine) -> Generator[Line, Pt, PartialLine]:
        pos, txt, width, state = self.pos, self.txt, prev.space, prev.state
        sub = slice_size(txt, state, prev.end, width, pos, prev.has_text())

        if sub.sized.content:
            line = prev.add(
                sub.sized,
                state.leading(),
                # The end character is never none if there is any content
                sub.end,  # type: ignore[arg-type]
                state,
            )
        else:
            assert isinstance(prev, Line)
            line = prev

        while sub.newpos != len(txt):
            try:
                width = yield line
            except Redo as r:
                diff = r.diff
                # If a width reduction fits within the whitespace surplus,
                # repeat the same line but with reduced available space
                if diff <= 0 and line.space + sub.trimmable_space + diff >= 0:
                    line = replace(line, space=line.space + diff)
                # If a width reduction doesn't fit in this passage,
                # tell the wrapper to rewind this and previous segments
                elif width + diff < 0:
                    raise _Rewind(Passage(txt, pos), diff)
                # If the width increases, or if a width reduction
                # fits within this passage, tell the word wrapper to
                # replay this passage from the start of the line.
                else:
                    raise _Replay(
                        replace(prev, space=width + diff), Passage(txt, pos)
                    )
            else:
                pos = sub.newpos
                sub = slice_size(txt, state, None, width, pos, False)
                prev = EmptyLine(width, state)
                line = prev.add(sub.sized, state.leading(), sub.end, state)
        return line


# FUTURE: benchmark to ensure can handle huge strings
# TODO: rename stack_horiz?
# TODO: return None if empty?
def slice_size(
    txt: str,
    state: State,
    prev: Char | None,
    space: Pt,
    start: StringIndex,
    allow_empty: bool,
) -> SubPassage:
    font = state.font
    size = state.size
    prev_index = pos = start
    width = prev_trimmable_space = 0.0
    kerning: list[Kern] = []
    for pos in map(methodcaller("end"), _BREAK_RE.finditer(txt, start)):
        offset = prev_index - start
        word = _size_string(txt[prev_index:pos], state, prev, offset)
        trimmable_space = word.trimmable_space(font, size, offset)
        if width + word.width - trimmable_space > space:
            break

        kerning.extend(word.kerning)
        width += word.width
        prev_index = pos
        prev = txt[pos - 1]
        prev_trimmable_space = trimmable_space

    if width or allow_empty:
        return SubPassage(
            SizedString(txt[start:prev_index], kerning, width),
            prev_trimmable_space,
            prev,
            prev_index,
        )
    else:
        return SubPassage(word, trimmable_space, txt[pos - 1], pos)


@add_slots
@dataclass(frozen=True)
class SubPassage:
    sized: SizedString
    trimmable_space: Pt
    end: Char | None
    newpos: StringIndex


@add_slots
@dataclass(frozen=True)
class MixedWord:
    head: str  # non-empty
    segments: Sequence[tuple[StateChange, str]]  # non-empty

    def wrap(self, line: PartialLine) -> Generator[Line, Pt, PartialLine]:
        sized = self.size(line.state, line.end)
        return (yield from sized.wrap(line))

    def size(self, state: State, prev: Char | None) -> SizedMixedWord:
        head = _size_string(self.head, state, prev, 0)
        lead = state.leading()
        width = head.width

        prev = self.head[-1]
        segments = []
        for change, substring in self.segments:
            new_state = change.apply(state)
            sized = _size_string(
                substring,
                new_state,
                prev if state.font is new_state.font else None,
                0,
            )
            segments.append((change, sized))
            lead = max(lead, new_state.leading())
            width += sized.width
            state = new_state

        return SizedMixedWord(
            head,
            segments,
            width,
            lead,
            state,
            sized.trimmable_space(state.font, state.size, 0),
        )


@add_slots
@dataclass(frozen=True)
class SizedMixedWord:
    head: SizedString
    segments: Sequence[tuple[StateChange, SizedString]]
    width: Pt
    lead: Pt
    new_state: State
    trimmable_space: Pt

    def without_init_kern(self, head_size: Pt) -> SizedMixedWord:
        if self.head.kerning:
            first_kern_index, first_kern_space = self.head.kerning[0]
            if first_kern_index == 0:
                kern_diff = (
                    first_kern_space * head_size
                ) / TEXTSPACE_TO_GLYPHSPACE
                return replace(
                    self,
                    head=replace(
                        self.head,
                        kerning=self.head.kerning[1:],
                        width=self.head.width - kern_diff,
                    ),
                    width=self.width - kern_diff,
                )
        return self

    def wrap(self, line: PartialLine) -> Generator[Line, Pt, PartialLine]:
        sized = self
        if (
            sized.width - sized.trimmable_space > line.space
            and isinstance(line, Line)
            and line.has_text()
        ):
            sized = sized.without_init_kern(line.state.size)
            try:
                width = (yield line) - sized.width
            except Redo as r:
                # If width adjustment fits in this word, tell
                # the wrapper to replay this.
                if line.space + r.diff >= 0:
                    raise _Replay(
                        replace(line, space=line.space + r.diff), self
                    )
                # Otherwise, we need to rewind the rest of the line as well.
                raise _Rewind(self, r.diff)
            return Line(
                [sized],
                width,
                sized.lead,
                self.segments[-1][1].content[-1],
                sized.new_state,
            )
        else:
            return line.add(
                sized,
                sized.lead,
                self.segments[-1][1].content[-1],
                sized.new_state,
            )


@add_slots
@dataclass(frozen=True)
class EmptyLine:
    space: Pt
    state: State

    segments: ClassVar[Sequence[Sized]] = ()
    lead: ClassVar[None] = None
    end: ClassVar[None] = None

    def add(self, s: Sized, lead: Pt, last: Char, state: State) -> Line:
        return Line([s], self.space - s.width, lead, last, state)

    def has_text(self) -> bool:
        return False

    def width(self) -> Pt:
        return self.space


@add_slots
@dataclass(frozen=True)
class Line:
    segments: Sequence[Sized]  # NOTE: may contain only commands until finished
    space: Pt  # NOTE: can be negative if there is trimmable trailing space
    lead: Pt
    end: Char | None
    state: State

    def add(self, s: Sized, lead: Pt, last: Char, state: State) -> Line:
        return Line(
            [*self.segments, s],
            self.space - s.width,
            max(lead, self.lead),
            last,
            state,
        )

    def has_text(self) -> bool:
        return self.end is not None

    def width(self) -> Pt:
        return sum(s.width for s in self.segments) + self.space


PartialLine = EmptyLine | Line


@dataclass(frozen=True)
class Redo(Exception):
    diff: Pt


@dataclass(frozen=True)
class _Replay(Exception):
    "Tells the text wrapper to re-wrap one line segment"
    line: PartialLine
    words: Words


@dataclass(frozen=True)
class _Rewind(Exception):
    "Tells the text wrapper to re-wrap an entire line"
    head: Words
    diff: Pt


@skips_to_first_yield
def wrap(ws: Iterable[Words], state: State) -> Generator[Line, Pt, None]:
    ws = iter(ws)
    width = yield  # type: ignore[misc]
    line: PartialLine = EmptyLine(width, state)
    while True:
        if (words := next(ws, None)) is None:
            break

        try:
            line = yield from words.wrap(line)
        except _Replay as r:
            ws = prepend(r.words, ws)
            line = r.line
        except _Rewind as w:
            ws = chain(line.segments, [w.head], ws)
            line = EmptyLine(line.width() + w.diff, state)

    if isinstance(line, Line):
        yield line


@add_slots
@dataclass(frozen=True)
class SizedString:
    content: str
    kerning: Kerning
    width: Pt

    def trimmable_space(self, f: Font, size: Pt, offset: int) -> Pt:
        # TODO: cache font properties for performance
        if self.content.endswith(" "):
            trimmable_space = f.charwidth(" ")
            if self.kerning:
                last_kern_index, last_kern_size = self.kerning[-1]
                if (
                    last_kern_index - offset * f.encoding_width
                ) + f.encoding_width == len(self.content):
                    trimmable_space += last_kern_size
            return trimmable_space * size / TEXTSPACE_TO_GLYPHSPACE
        else:
            return 0

    def wrap(self, line: PartialLine) -> Generator[Line, Pt, PartialLine]:
        return (yield from Passage(self.content).wrap(line))


Words = Passage | MixedWord | StateChange | SizedMixedWord | SizedString
Sized = SizedString | SizedMixedWord | StateChange


def _size_string(
    s: str, state: State, prev: Char | None, offset: int
) -> SizedString:
    # TODO: prev can be None
    font = state.font
    kerning = list(font.kern(s, prev or "M", offset))
    return SizedString(
        s,
        kerning,
        (font.width(s) + sum(map(second, kerning)) / TEXTSPACE_TO_GLYPHSPACE)
        * state.size,
    )


def _adjacent_spans_into_words(
    group: NonEmptyIterator[Span],
) -> Iterator[Words]:
    first = next(group)
    yield first.command

    try:
        span = next(group)
    except StopIteration:
        yield Passage(first.content)
        return

    body, head = (
        _BODY_AND_LAST_RE.fullmatch(first.content)
    ).groups()  # type: ignore[union-attr]
    yield Passage(body)

    segments = []
    for following in group:
        init, body, last = (
            _INIT_BODY_LAST_RE.fullmatch(span.content)
        ).groups()  # type: ignore[union-attr]
        segments.append((span.command, init))
        if last:
            yield MixedWord(head, segments)
            yield Passage(body)
            segments = []
            head = last
        span = following

    init, body = cast(
        re.Match, _INIT_AND_BODY_RE.fullmatch(span.content)
    ).groups()

    segments.append((span.command, init))
    yield MixedWord(head, segments)
    yield Passage(body)


# FUTURE: make fully lazy as well
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
        if not span.content:
            buffer.append(span.command)
        elif buffer:
            buffer.append(span.command)
            yield Span(MultiCommand(buffer), span.content)
            buffer = []
        else:
            yield span
    if len(buffer) == 1:
        yield Span(buffer[0], "")
    elif buffer:
        yield Span(MultiCommand(buffer), "")
