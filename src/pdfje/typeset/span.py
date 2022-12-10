from __future__ import annotations

import re
from dataclasses import dataclass, replace
from itertools import chain, tee
from operator import methodcaller
from typing import Iterable, Iterator, Sequence

from ..common import Char, Pt, add_slots, second, setattr_frozen
from ..fonts.common import TEXTSPACE_TO_GLYPHSPACE, GlyphPt
from ..ops import State, StateChange

Pos = int  # position within a string (index)
Kern = tuple[Pos, GlyphPt]
Text = str  # potentially large string

_BREAK_RE = re.compile(r" +")


@add_slots
@dataclass(frozen=True)
class Span:
    cmd: StateChange
    txt: Text


@add_slots
@dataclass(frozen=True)
class Line:
    segments: Sequence[StateChange | Kerned]
    space: Pt
    lead: Pt


@add_slots
@dataclass(frozen=True)
class FinishedLine:
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

    def segments(self) -> Iterable[StateChange | GaugedString]:
        yield self.head
        yield from self.tail

    def without_init_kern(self) -> MixedWord:
        new_head = self.head.without_init_kern()
        return MixedWord(
            new_head,
            self.tail,
            self.last,
            self.width + (new_head.width - self.head.width),
            self.lead,
            self.state,
        )


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
            trimmed, trim = item.trimmed()
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
    segments: Sequence[StateChange | GaugedString]
    space: Pt  # takes pending into account

    # Any remaining trailing content which hasn't been 'broken' yet.
    pending: MixedWord | None

    lead: Pt  # zero if there is no text (ignores pending)
    state_excl_pending: State
    last: Char | None  # if there is pending content, taken from there

    def state(self) -> State:
        return self.pending.state if self.pending else self.state_excl_pending

    def has_text(self) -> bool:
        return bool(self.pending or self.lead)

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
                segments=[*self.segments, cmd],
                state_excl_pending=state_new,
                last=last,
            )

    @staticmethod
    def empty(
        space: Pt, state: State, pending: MixedWord | None
    ) -> PartialLine:
        return (
            PartialLine(
                (),
                space - pending.width,
                pending,
                pending.lead,
                state,
                pending.last,
            )
            if pending
            else PartialLine((), space, None, 0, state, None)
        )

    def finish(self) -> Line:
        return Line(
            # Note we don't trim because this is the last line
            list(
                _finalize(
                    chain(
                        self.segments,
                        self.pending.segments() if self.pending else (),
                    )
                )
            ),
            self.space,
            max(self.lead, self.pending.lead) if self.pending else self.lead,
        )


@add_slots
@dataclass(frozen=True)
class Cursor:
    txt: Text
    pos: Pos

    def line(self, s: PartialLine, /) -> FinishedLine | PartialLine:
        state = s.state()
        match = break_at_width(
            self.txt, state, s.space, s.has_text(), self.pos, s.last
        )

        if match is None:
            # In this case there are breaks, but not enough room for content.
            # Thus, we can complete it. Any pending content cannot be included.
            strings, trim = _trim_and_finalize(s.segments)
            if s.pending:
                return FinishedLine(
                    Line(strings, s.space + s.pending.width + trim, s.lead),
                    self,
                    s.state_excl_pending,
                    s.pending.without_init_kern(),
                )
            else:
                return FinishedLine(
                    Line(strings, s.space + trim, s.lead),
                    self,
                    s.state_excl_pending,
                    None,
                )
        elif isinstance(match, Exhausted):
            pending = (
                MixedWord(
                    match.tail,
                    (),
                    match.tail.last,
                    match.tail.width,
                    state.leading(),
                    state,
                )
                if match.tail
                else None
            )
            if match.content:
                return PartialLine(
                    [
                        *s.segments,
                        *(s.pending.segments() if s.pending else ()),
                        match.content,
                    ],
                    s.space
                    - match.content.width
                    - (pending.width if pending else 0),
                    pending,
                    max(s.lead, state.leading()),
                    state,
                    pending.last if pending else match.content.last,
                )
            elif s.pending:
                return PartialLine(
                    s.segments,
                    s.space - (pending.width if pending else 0),
                    MixedWord(
                        s.pending.head,
                        [*s.pending.tail, *pending.segments()],
                        pending.last,
                        s.pending.width + pending.width,
                        max(pending.lead, s.pending.lead),
                        state,
                    )
                    if pending
                    else s.pending,
                    s.lead,
                    s.state_excl_pending,
                    pending.last if pending else s.pending.last,
                )
            else:
                return PartialLine(
                    s.segments,
                    s.space - (pending.width if pending else 0),
                    pending,
                    max(s.lead, state.leading()),
                    state,
                    pending.last if pending else s.last,
                )
        else:
            if s.pending:
                return FinishedLine(
                    Line(
                        [
                            *_finalize(
                                chain(s.segments, s.pending.segments())
                            ),
                            match.content.txt,
                        ],
                        s.space - match.content.width,
                        max(state.leading(), s.pending.lead),
                    ),
                    Cursor(self.txt, match.end),
                    state,
                    None,
                )
            else:
                return FinishedLine(
                    Line(
                        [*_finalize(s.segments), match.content.txt],
                        s.space - match.content.width,
                        max(s.lead, state.leading()),
                    ),
                    Cursor(self.txt, match.end),
                    state,
                    None,
                )


@add_slots
@dataclass(frozen=True)
class LimitReached:
    content: GaugedString
    end: Pos


@add_slots
@dataclass(frozen=True)
class Exhausted:
    content: GaugedString | None
    tail: GaugedString | None


_end = methodcaller("end")


def break_at_width(
    txt: Text,
    state: State,
    space: Pt,
    allow_empty: bool,
    start: Pos,
    prev: Char | None,
) -> Exhausted | LimitReached | None:
    if not txt:
        return Exhausted(None, None)
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
        content = GaugedString(
            Kerned(state.font.encode(txt[start:pos]), kerning),
            width,
            state,
            prev,
        )
        if pos == len(txt):
            return Exhausted(content, None)
        else:
            tail = GaugedString.build(txt[pos:], state, prev)
            if start == pos:
                if allow_empty and width + tail.width > space:
                    return None
                else:
                    return Exhausted(None, tail)

            if width + tail.width > space:
                return LimitReached(
                    GaugedString(
                        Kerned(
                            state.font.encode(
                                txt[start : pos - bool(word_trim)]
                            ),
                            kerning,
                        ),
                        width - word_trim,
                        state,
                        txt[pos - bool(word_trim) - 1],
                    ),
                    pos,
                )
            else:
                return Exhausted(content, tail)

    if width:
        return LimitReached(
            GaugedString(
                Kerned(
                    state.font.encode(txt[start : pos - bool(trim)]), kerning
                ),
                width - trim,
                state,
                txt[pos - bool(trim) - 1],
            ),
            pos,
        )
    elif allow_empty:
        return None
    else:
        if pos_next == len(txt):
            return Exhausted(
                GaugedString(
                    Kerned(state.font.encode(txt[start:]), word_kern),
                    word_width,
                    state,
                    txt[-1],
                ),
                None,
            )
        return LimitReached(
            GaugedString(
                Kerned(
                    state.font.encode(txt[start : pos_next - bool(word_trim)]),
                    word_kern,
                ),
                word_width - word_trim,
                state,
                txt[pos_next - bool(word_trim) - 1],
            ),
            pos_next,
        )


@add_slots
@dataclass(frozen=True)
class Wrapper:
    """Wraps text into lines.

    Taking a line results in a new wrapper instance, so that the original
    can be used do undo/redo/rewind lines."""

    spans: Iterator[Span]
    cursor: Cursor
    state: State
    pending: MixedWord | None

    @staticmethod
    def start(it: Iterable[Span], s: State) -> Wrapper | WrapDone:
        it = iter(it)
        try:
            first = next(it)
        except StopIteration:
            return WrapDone(s)
        return Wrapper(it, Cursor(first.txt, 0), first.cmd.apply(s), None)

    def line(self, width: Pt) -> tuple[Line, Wrapper | WrapDone]:
        result = self.cursor.line(
            PartialLine.empty(width, self.state, self.pending)
        )
        iterspans = self._branched_span_iterator()
        while isinstance(result, PartialLine):
            try:
                span = next(iterspans)
            except StopIteration:
                return result.finish(), WrapDone(result.state())
            result = Cursor(span.txt, 0).line(result.add_cmd(span.cmd))

        return result.line, Wrapper(
            iterspans, result.cursor, result.state, result.pending
        )

    def _branched_span_iterator(self) -> Iterator[Span]:
        # Performance note: we 'tee' the iterator every time we wrap a line.
        # However, when old Wrapper instances are garbage collected,
        # these tee objects shrink in size again as they 'know'
        # they can forget intermediate values.
        a, b = tee(self.spans)
        setattr_frozen(self, "spans", a)
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

    def trimmed(self) -> tuple[Kerned, Pt]:
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

    def without_init_kern(self) -> GaugedString:
        if self.txt.kerning:
            firstkern_pos, firstkern = self.txt.kerning[0]
            if firstkern_pos == 0:
                delta = (firstkern * self.state.size) / TEXTSPACE_TO_GLYPHSPACE
                return replace(
                    self,
                    txt=Kerned(self.txt.content, self.txt.kerning[1:]),
                    width=self.width - delta,
                )
        return self


def _size_string(
    s: str, state: State, prev: Char | None, offset: Pos
) -> tuple[Pt, Sequence[Kern], Pt]:
    font = state.font
    kerning = list(font.kern(s, prev, offset))
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
        # TODO: cache font properties for performance
        trimmable_space = s.font.charwidth(" ")
        if kern:
            last_kern_index, last_kern_size = kern[-1]
            if (
                last_kern_index - offset * s.font.encoding_width
            ) + s.font.encoding_width == maxpos:
                trimmable_space += last_kern_size
                kern = kern[:-1]
        return trimmable_space * s.size / TEXTSPACE_TO_GLYPHSPACE, kern
    else:
        return 0, kern
