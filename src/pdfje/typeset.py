from __future__ import annotations

import re
from dataclasses import dataclass, replace
from itertools import chain, tee
from operator import methodcaller
from typing import Iterable, Iterator, Sequence

from .atoms import Array, LiteralString, Real
from .common import (
    Char,
    NonEmptySequence,
    NonEmtpyIterator,
    Pos,
    Pt,
    add_slots,
    flatten,
    prepend,
    second,
    setattr_frozen,
)
from .fonts.common import TEXTSPACE_TO_GLYPHSPACE, Kern
from .ops import NO_OP, Command, State, StateChange

_BREAK_RE = re.compile(r" +")
_NEWLINE_RE = re.compile(r"(?:\r\n|\n)")


def splitlines(it: Iterable[Stretch]) -> Iterator[NonEmtpyIterator[Stretch]]:
    it = iter(it)
    try:
        transition = [next(it)]
    except StopIteration:
        return

    def _group() -> NonEmtpyIterator[Stretch]:
        for stretch in prepend(transition.pop(), it):
            if (newline := _NEWLINE_RE.search(stretch.txt)) is None:
                yield stretch
            else:
                yield Stretch(stretch.cmd, stretch.txt[: newline.start()])
                transition.append(
                    Stretch(NO_OP, stretch.txt[newline.end() :])  # noqa
                )
                return

    while transition:
        yield _group()


@add_slots
@dataclass(frozen=True)
class Stretch:
    cmd: StateChange
    txt: str


@add_slots
@dataclass(frozen=True)
class Line(Command):
    segments: Sequence[StateChange | Kerned]
    space: Pt
    lead: Pt

    def into_stream(self) -> Iterator[bytes]:
        return flatten(map(methodcaller("into_stream"), self.segments))


@add_slots
@dataclass(frozen=True)
class LineFinished:
    line: Line
    cursor: Cursor
    state: State
    pending: MixedWord | None


@add_slots
@dataclass(frozen=True)
class MixedWord:
    head: GaugedString
    tail: Sequence[StateChange | GaugedString]
    last: Char | None
    width: Pt
    lead: Pt
    state: State

    @staticmethod
    def start(head: GaugedString) -> MixedWord:
        return MixedWord(
            head, (), head.last, head.width, head.state.lead, head.state
        )

    def segments(self) -> Iterable[StateChange | GaugedString]:
        yield self.head
        yield from self.tail

    def without_init_kern(self) -> MixedWord:
        kern = self.head.txt.kerning
        if kern:
            firstkern_pos, firstkern = kern[0]
            if firstkern_pos == 0:
                delta = (
                    firstkern * self.head.state.size
                ) / TEXTSPACE_TO_GLYPHSPACE
                return replace(
                    self,
                    head=replace(
                        self.head, txt=Kerned(self.head.txt.content, kern[1:])
                    ),
                    width=self.width - delta,
                )
        return self


def _finalize(
    s: Iterable[StateChange | GaugedString],
) -> Iterable[StateChange | Kerned]:
    for item in s:
        if isinstance(item, GaugedString):
            yield item.txt
        else:
            yield item


def _trim_and_finalize(
    s: Sequence[StateChange | GaugedString],
) -> tuple[Sequence[StateChange | Kerned], Pt]:
    result: list[Kerned | StateChange] = []
    it = iter(reversed(s))
    trim = 0.0
    for item in it:
        if isinstance(item, GaugedString):
            trimmed, trim = item.without_trailing_space()
            result.append(trimmed)
            break
        else:
            result.append(item)

    result.extend(_finalize(it))
    result.reverse()
    return result, trim


@add_slots
@dataclass(frozen=True)
class PartialLine:
    body: Sequence[StateChange | GaugedString]

    # The widths include any pending content.
    # Note we need to track both the width of the line and the space
    # remaining on the line. This is because space can be infinite.
    width: Pt
    space: Pt

    # Any remaining trailing content which hasn't been 'broken' yet.
    pending: MixedWord | None

    lead: Pt  # zero if there is no text (ignores anything pending)
    body_state: State
    last: Char | None  # for kerning purposes, includes pending content

    def state(self) -> State:
        return self.pending.state if self.pending else self.body_state

    def has_text(self) -> bool:
        return bool(self.lead)

    def free_space(self) -> Pt:
        return self.space - self.width

    def add(
        self, content: GaugedString | None, pending: GaugedString | None
    ) -> PartialLine:
        if content:
            return PartialLine(
                [
                    *self.body,
                    *(self.pending.segments() if self.pending else ()),
                    content,
                ],
                self.width + content.width + (pending.width if pending else 0),
                self.space,
                MixedWord.start(pending) if pending else None,
                max(
                    self.lead,
                    content.state.lead,
                    self.pending.lead if self.pending else 0,
                ),
                content.state,
                pending.last if pending else content.last,
            )

        elif self.pending:
            return PartialLine(
                self.body,
                self.width + (pending.width if pending else 0),
                self.space,
                MixedWord(
                    self.pending.head,
                    [*self.pending.tail, pending],
                    pending.last,
                    self.pending.width + pending.width,
                    max(pending.state.lead, self.pending.lead),
                    pending.state,
                )
                if pending
                else self.pending,
                self.lead,
                self.body_state,
                pending.last if pending else self.pending.last,
            )
        else:
            return PartialLine(
                self.body,
                self.width + (pending.width if pending else 0),
                self.space,
                MixedWord.start(pending) if pending else None,
                self.lead,
                self.body_state,
                pending.last if pending else self.last,
            )

    def finish_excl_pending(self) -> Line:
        strings, trim = _trim_and_finalize(self.body)
        return Line(
            strings,
            self.free_space()
            + (self.pending.width if self.pending else 0)
            + trim,
            self.lead,
        )

    def finish(self, content: GaugedString) -> Line:
        # FUTURE: unify with self.add?
        # Currently test fails for `return self.add(content, None).close()`
        if self.pending:
            return Line(
                [
                    *_finalize(chain(self.body, self.pending.segments())),
                    content.txt,
                ],
                self.free_space() - content.width,
                max(self.lead, content.state.lead, self.pending.lead),
            )
        else:
            return Line(
                [*_finalize(self.body), content.txt],
                self.free_space() - content.width,
                max(self.lead, content.state.lead),
            )

    def close(self) -> Line:
        if self.pending:
            strings, trim = _trim_and_finalize(
                [*self.body, *self.pending.segments()]
            )
            return Line(
                strings,
                self.free_space() + trim,
                max(self.lead, self.pending.lead),
            )
        else:
            strings, trim = _trim_and_finalize(self.body)
            return Line(
                strings,
                self.free_space() + trim,
                self.lead or self.body_state.lead,
            )

    def add_cmd(self, cmd: StateChange) -> PartialLine:
        state_new = cmd.apply(state_old := self.state())
        last = self.last if state_new.kerns_with(state_old) else None
        if self.pending:
            return replace(
                self,
                pending=replace(
                    self.pending,
                    tail=[*self.pending.tail, cmd],
                    state=state_new,
                    last=last,
                ),
                last=last,
            )
        else:
            return replace(
                self,
                body=[*self.body, cmd],
                body_state=state_new,
                last=last,
            )

    @staticmethod
    def new(space: Pt, state: State, pending: MixedWord | None) -> PartialLine:
        return (
            PartialLine(
                (), pending.width, space, pending, 0, state, pending.last
            )
            if pending
            else PartialLine((), 0, space, None, 0, state, None)
        )


@add_slots
@dataclass(frozen=True)
class Cursor:
    txt: str
    pos: Pos

    def line(self, s: PartialLine, /) -> LineFinished | PartialLine:
        match = break_at_width(
            self.txt,
            s.state(),
            s.space - s.width,
            s.has_text(),
            self.pos,
            s.last,
        )
        if isinstance(match, Exhausted):
            return s.add(match.content, match.tail)
        else:
            if match.end == self.pos:
                return LineFinished(
                    s.finish_excl_pending(),
                    self,
                    s.body_state,
                    s.pending.without_init_kern() if s.pending else None,
                )
            else:
                return LineFinished(
                    s.finish(match.content) if match.content else s.close(),
                    Cursor(self.txt, match.end),
                    s.state(),
                    None,
                )


@add_slots
@dataclass(frozen=True)
class LimitReached:
    content: GaugedString | None
    end: Pos


@add_slots
@dataclass(frozen=True)
class Exhausted:
    content: GaugedString | None
    tail: GaugedString | None


_end = methodcaller("end")


def break_at_width(
    txt: str,
    state: State,
    space: Pt,
    allow_empty: bool,
    start: Pos,
    prev: Char | None,
) -> Exhausted | LimitReached:
    pos = pos_next = start
    width = trim = 0.0
    kerning: list[Kern] = []
    for pos_next in map(_end, _BREAK_RE.finditer(txt, start)):
        word_width, word_kern, word_trim = _size_string(
            txt[pos:pos_next], state, prev, pos - start
        )
        if width + word_width - word_trim > space:
            break

        kerning.extend(word_kern)
        width += word_width
        pos = pos_next
        prev = txt[pos - 1]
        trim = word_trim

    else:  # i.e. we've consumed all breaks in the text
        content = (
            None
            if start == pos
            else GaugedString(
                Kerned(state.font.encode(txt[start:pos]), kerning),
                width,
                state,
                # Here, prev is always set by the loop (so is not None)
                prev,  # type: ignore[arg-type]
            )
        )
        if pos == len(txt):
            return Exhausted(content, None)
        # i.e. there is still trailing content. We still need to determine
        # if that would fit.
        else:
            tail = GaugedString.build(txt[pos:], state, prev)
            if start == pos:
                if allow_empty and width + tail.width > space:
                    return LimitReached(None, start)
                else:
                    return Exhausted(None, tail)

            if width + tail.width > space:
                return LimitReached(
                    GaugedString.sliced(
                        txt, start, pos, kerning, width, word_trim, state
                    ),
                    pos,
                )
            else:
                return Exhausted(content, tail)

    if width:
        return LimitReached(
            GaugedString.sliced(txt, start, pos, kerning, width, trim, state),
            pos,
        )
    elif allow_empty:
        return LimitReached(None, start)
    else:
        if pos_next == len(txt):
            return Exhausted(
                GaugedString.sliced(
                    txt, start, pos_next, word_kern, word_width, 0, state
                ),
                None,
            )
        return LimitReached(
            GaugedString.sliced(
                txt, start, pos_next, word_kern, word_width, word_trim, state
            ),
            pos_next,
        )


@add_slots
@dataclass
class LineSet:
    lines: Sequence[Line]
    height_left: Pt


@add_slots
@dataclass(frozen=True)
class Wrapper:
    """Wraps text into lines.

    Taking content results in a new wrapper instance, so that the original
    can be used do undo/redo/rewind lines."""

    queue: Iterator[Stretch]
    cursor: Cursor
    state: State
    pending: MixedWord | None

    @staticmethod
    def start(it: Iterable[Stretch], s: State) -> Wrapper | WrapDone:
        it = iter(it)
        try:
            first = next(it)
        except StopIteration:
            return WrapDone(s)
        return Wrapper(it, Cursor(first.txt, 0), first.cmd.apply(s), None)

    def line(self, width: Pt) -> tuple[Line, Wrapper | WrapDone]:
        result = self.cursor.line(
            PartialLine.new(width, self.state, self.pending)
        )
        queue = self._branch_queue()
        while isinstance(result, PartialLine):
            try:
                stretch = next(queue)
            except StopIteration:
                return result.close(), WrapDone(result.state())
            result = Cursor(stretch.txt, 0).line(result.add_cmd(stretch.cmd))
        return result.line, Wrapper(
            queue, result.cursor, result.state, result.pending
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

    def _branch_queue(self) -> Iterator[Stretch]:
        # Performance note: when old Wrapper instances are garbage collected,
        # these tee objects shrink in size again as they 'know' they can
        # forget intermediate values.
        a, b = tee(self.queue)
        setattr_frozen(self, "queue", a)
        return b


@add_slots
@dataclass(frozen=True)
class WrapDone:
    state: State


@add_slots
@dataclass(frozen=True)
class Kerned:
    content: bytes
    kerning: Sequence[Kern]

    def into_stream(self) -> Iterable[bytes]:
        if self.kerning:
            yield from Array(
                _encode_kerning(self.content, self.kerning)
            ).write()
            yield b" TJ\n"
        else:
            yield from LiteralString(self.content).write()
            yield b" Tj\n"


def _encode_kerning(
    s: bytes, kerning: NonEmptySequence[Kern]
) -> Iterable[LiteralString | Real]:
    index_prev, space = kerning[0]

    if index_prev == 0:  # i.e. the case where we kern before any text
        yield Real(-space)
        kerning = kerning[1:]

    index_prev = index = 0
    for index, space in kerning:
        yield LiteralString(s[index_prev:index])
        yield Real(-space)
        index_prev = index

    yield LiteralString(s[index:])


@add_slots
@dataclass(frozen=True)
class GaugedString:
    txt: Kerned
    width: Pt
    state: State
    last: Char

    @staticmethod
    def build(s: str, state: State, prev: Char | None) -> GaugedString:
        assert s
        font = state.font
        kerning = list(font.kern(s, prev, 0))
        return GaugedString(
            Kerned(font.encode(s), kerning),
            (
                font.width(s)
                + sum(map(second, kerning)) / TEXTSPACE_TO_GLYPHSPACE
            )
            * state.size,
            state,
            s[-1],
        )

    @staticmethod
    def sliced(
        txt: str,
        start: Pos,
        end: Pos,
        kern: Sequence[Kern],
        width: Pt,
        trim: Pt,
        state: State,
    ) -> GaugedString | None:
        """Create an instance from a string slice, already sized"""
        trimpos = end - bool(trim)
        return (
            None
            if start == trimpos
            else GaugedString(
                Kerned(state.font.encode(txt[start:trimpos]), kern),
                width - trim,
                state,
                txt[trimpos - 1],
            )
        )

    def without_trailing_space(self) -> tuple[Kerned, Pt]:
        trim, kerning = _trim(
            self.last, len(self.txt.content), self.txt.kerning, self.state, 0
        )
        if trim:
            return (
                Kerned(
                    self.txt.content[: -self.state.font.encoding_width],
                    kerning,
                ),
                trim,
            )
        else:
            return self.txt, 0


def _size_string(
    s: str, state: State, prev: Char | None, offset: Pos
) -> tuple[Pt, Sequence[Kern], Pt]:
    font = state.font
    kerning = list(font.kern(s, prev, offset * font.encoding_width))
    return (
        (font.width(s) + sum(map(second, kerning)) / TEXTSPACE_TO_GLYPHSPACE)
        * state.size,
        kerning,
        _trim(s[-1], len(s) * font.encoding_width, kerning, state, offset)[0],
    )


def _trim(
    last: Char, maxpos: int, kern: Sequence[Kern], s: State, offset: Pos
) -> tuple[Pt, Sequence[Kern]]:
    if last == " ":
        trimmable_space = s.font.spacewidth
        if kern:
            lastkern_pos, lastkern = kern[-1]
            if (
                lastkern_pos - offset * s.font.encoding_width
            ) + s.font.encoding_width == maxpos:
                trimmable_space += lastkern
                kern = kern[:-1]
        return trimmable_space * s.size / TEXTSPACE_TO_GLYPHSPACE, kern
    else:
        return 0, kern
