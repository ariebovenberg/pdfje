from __future__ import annotations

import abc
import re
from dataclasses import dataclass, field, replace
from heapq import merge
from itertools import chain, groupby, tee
from operator import methodcaller
from typing import Collection, Iterable, Iterator, Sequence

from .atoms import Array, LiteralString, Real
from .common import (
    RGB,
    Char,
    NonEmptySequence,
    NonEmtpyIterator,
    Pos,
    Pt,
    Streamable,
    add_slots,
    first,
    flatten,
    prepend,
    second,
    setattr_frozen,
)
from .fonts.common import TEXTSPACE_TO_GLYPHSPACE, Font, GlyphPt, Kern

# FUTURE: expand to support more exotic unicode whitespace
_BREAK_RE = re.compile(r" +")
_WORDBREAK_RE = re.compile(r" ")
_NEWLINE_RE = re.compile(r"(?:\r\n|\n)")


class Command(Iterable[bytes]):
    __slots__ = ()

    @abc.abstractmethod
    def apply(self, s: State, /) -> State:
        ...


@add_slots
@dataclass(frozen=True)
class _NoOp(Command):
    def apply(self, s: State) -> State:
        return s

    def __iter__(self) -> Iterator[bytes]:
        return iter(())


NO_OP = _NoOp()


@add_slots
@dataclass(frozen=True)
class Chain(Command):
    items: Collection[Command]

    def apply(self, s: State) -> State:
        for c in self.items:
            s = c.apply(s)
        return s

    def __iter__(self) -> Iterator[bytes]:
        return flatten(self.items)

    @staticmethod
    def squash(it: Iterator[Command]) -> Command:
        by_type = {type(i): i for i in it}
        if len(by_type) == 1:
            return by_type.popitem()[1]
        elif len(by_type) == 0:
            return NO_OP
        else:
            return Chain(by_type.values())


@add_slots
@dataclass(frozen=True)
class SetFont(Command):
    font: Font
    size: Pt

    def apply(self, s: State) -> State:
        return replace(s, font=self.font, size=self.size)

    def __iter__(self) -> Iterator[bytes]:
        yield b"/%b %g Tf\n" % (self.font.id, self.size)


@add_slots
@dataclass(frozen=True)
class SetLineSpacing(Command):
    value: float

    def apply(self, s: State) -> State:
        return replace(s, line_spacing=self.value)

    def __iter__(self) -> Iterator[bytes]:
        # We don't actually emit anything here,
        # because its value is already used to calculate the leading space
        # on a per-line basis.
        return iter(())


@add_slots
@dataclass(frozen=True)
class SetColor(Command):
    value: RGB

    def apply(self, s: State) -> State:
        return replace(s, color=self.value)

    def __iter__(self) -> Iterator[bytes]:
        yield b"%g %g %g rg\n" % self.value.astuple()


@add_slots
@dataclass(frozen=True)
class State(Streamable):
    """Text state, see PDF 32000-1:2008, table 105"""

    font: Font
    size: Pt
    color: RGB
    line_spacing: float

    lead: Pt = field(init=False)  # cached calculation because it's used a lot

    def __iter__(self) -> Iterator[bytes]:
        yield from SetFont(self.font, self.size)
        yield from SetColor(self.color)

    def __post_init__(self) -> None:
        setattr_frozen(self, "lead", self.size * self.line_spacing)

    def kerns_with(self, other: State, /) -> bool:
        return self.font == other.font and self.size == other.size


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
    cmd: Command
    txt: str


@add_slots
@dataclass(frozen=True)
class Line(Streamable):
    segments: Sequence[Command | GaugedString]
    free_space: Pt  # space left on the line that can be filled when justifying
    width: Pt
    lead: Pt

    def __iter__(self) -> Iterator[bytes]:
        return flatten(self.segments)

    def indent(self, amount: Pt) -> Line:
        if not (amount and self.segments):
            return self
        # TODO: a better way to express in typing that the first item is
        # always a GaugedString.
        head = self.segments[0]
        assert isinstance(head, GaugedString)
        return Line(
            [head.indent(amount), *self.segments[1:]],
            self.free_space,
            self.width + amount,
            self.lead,
        )

    def justify(self) -> Line:
        breaks = [
            (
                [m.start() for m in _WORDBREAK_RE.finditer(g.txt)],
                g.state.size,
            )
            for g in self.segments
            if isinstance(g, GaugedString)
        ]
        try:
            # The additional width per word break, weighted by the font size,
            # which is needed to justify the text.
            width_per_break = self.free_space / sum(
                len(matches) * size for matches, size in breaks
            )
        except ZeroDivisionError:
            return self  # No word breaks, no justification.
        iterbreaks = map(first, breaks)
        return Line(
            [
                s
                if isinstance(s, Command)
                else _add_kerns(
                    s,
                    next(iterbreaks),
                    width_per_break * TEXTSPACE_TO_GLYPHSPACE,
                )
                for s in self.segments
            ],
            0,
            self.width + self.free_space,
            self.lead,
        )


def _add_kerns(
    s: GaugedString, pos: Sequence[Pos], amount: GlyphPt
) -> GaugedString:
    kerns = [
        (i, sum(x for _, x in spaces))
        for i, spaces in groupby(
            merge(s.kern, ((p, amount) for p in pos)), key=first
        )
    ]
    return GaugedString(
        s.txt,
        kerns,
        s.width + len(pos) * amount * s.state.size / TEXTSPACE_TO_GLYPHSPACE,
        s.state,
    )


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
    tail: Sequence[Command | GaugedString]
    last: Char | None
    width: Pt
    lead: Pt
    state: State

    @staticmethod
    def start(head: GaugedString) -> MixedWord:
        return MixedWord(
            head, (), head.last(), head.width, head.state.lead, head.state
        )

    def segments(self) -> Iterable[Command | GaugedString]:
        yield self.head
        yield from self.tail

    def without_init_kern(self) -> MixedWord:
        kern = self.head.kern
        if kern:
            firstkern_pos, firstkern = kern[0]
            if firstkern_pos == 0:
                delta = (
                    firstkern * self.head.state.size
                ) / TEXTSPACE_TO_GLYPHSPACE
                return replace(
                    self,
                    head=replace(self.head, kern=kern[1:]),
                    width=self.width - delta,
                )
        return self


def _trim_last(
    s: Sequence[Command | GaugedString],
) -> tuple[Sequence[Command | GaugedString], Pt]:
    result: list[Command | GaugedString] = []
    it = iter(reversed(s))
    trim = 0.0
    for item in it:
        if isinstance(item, GaugedString):
            trimmed, trim = item.without_trailing_space()
            result.append(trimmed)
            break
        else:
            result.append(item)

    result.extend(it)
    result.reverse()
    return result, trim


@add_slots
@dataclass(frozen=True)
class PartialLine:
    body: Sequence[Command | GaugedString]

    # The widths include any pending content.
    # FUTURE: tracking either one of these should be enough.
    #         one can be directly derived from the other at completion time.
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
                pending.last() if pending else content.last(),
            )

        elif self.pending:
            return PartialLine(
                self.body,
                self.width + (pending.width if pending else 0),
                self.space,
                MixedWord(
                    self.pending.head,
                    [*self.pending.tail, pending],
                    pending.last(),
                    self.pending.width + pending.width,
                    max(pending.state.lead, self.pending.lead),
                    pending.state,
                )
                if pending
                else self.pending,
                self.lead,
                self.body_state,
                pending.last() if pending else self.pending.last,
            )
        else:
            return PartialLine(
                self.body,
                self.width + (pending.width if pending else 0),
                self.space,
                MixedWord.start(pending) if pending else None,
                self.lead,
                self.body_state,
                pending.last() if pending else self.last,
            )

    def finish_excl_pending(self) -> Line:
        strings, trim = _trim_last(self.body)
        diff = (self.pending.width if self.pending else 0) + trim
        return Line(
            strings,
            self.free_space() + diff,
            self.width - diff,
            self.lead,
        )

    def finish(self, content: GaugedString) -> Line:
        if self.pending:
            return Line(
                [
                    *chain(self.body, self.pending.segments()),
                    content,
                ],
                self.free_space() - content.width,
                self.width + content.width,
                max(self.lead, content.state.lead, self.pending.lead),
            )
        else:
            return Line(
                [*self.body, content],
                self.free_space() - content.width,
                self.width + content.width,
                max(self.lead, content.state.lead),
            )

    def close(self, last_in_paragraph: bool) -> Line:
        if self.pending:
            segments, trim = _trim_last([*self.body, *self.pending.segments()])
            return Line(
                segments,
                0 if last_in_paragraph else self.free_space() + trim,
                self.width - trim,
                max(self.lead, self.pending.lead),
            )
        else:
            segments, trim = _trim_last(self.body)
            return Line(
                segments,
                0 if last_in_paragraph else self.free_space() + trim,
                self.width - trim,
                self.lead or self.body_state.lead,
            )

    def add_cmd(self, cmd: Command) -> PartialLine:
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
        match = break_(
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
            if match.end == self.pos:  # i.e. no room for any content
                return LineFinished(
                    s.finish_excl_pending(),
                    self,
                    s.body_state,
                    s.pending.without_init_kern() if s.pending else None,
                )
            else:
                return LineFinished(
                    s.finish(match.content)
                    if match.content
                    else s.close(last_in_paragraph=False),
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


def break_(
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
            else GaugedString(txt[start:pos], kerning, width, state)
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
                return result.close(last_in_paragraph=True), WrapDone(
                    result.state()
                )
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


def _encode_kerning(
    txt: str,
    kerning: NonEmptySequence[Kern],
    f: Font,
) -> Iterable[LiteralString | Real]:
    encoded = f.encode(txt)
    index_prev, space = kerning[0]

    if index_prev == 0:  # i.e. the case where we kern before any text
        yield Real(-space)
        kerning = kerning[1:]

    index_prev = index = 0
    for index, space in kerning:
        index *= f.encoding_width
        yield LiteralString(encoded[index_prev:index])
        yield Real(-space)
        index_prev = index

    yield LiteralString(encoded[index:])


@add_slots
@dataclass(frozen=True)
class GaugedString(Streamable):
    txt: str
    kern: Sequence[Kern]
    width: Pt
    state: State

    def last(self) -> Char | None:
        try:
            return self.txt[-1]
        except IndexError:
            return None

    @staticmethod
    def build(s: str, state: State, prev: Char | None) -> GaugedString:
        font = state.font
        kern = list(font.kern(s, prev, 0))
        return GaugedString(
            s,
            kern,
            # TODO: should we also take into account the font's size?
            (font.width(s) + sum(map(second, kern)) / TEXTSPACE_TO_GLYPHSPACE)
            * state.size,
            state,
        )

    def indent(self, amount: Pt) -> GaugedString:
        # We only indent the first word of a line -- which never has Kerning
        # on the first letter.
        try:
            assert self.kern[0][0] != 0
        except IndexError:  # pragma: no cover
            pass
        return GaugedString(
            self.txt,
            [
                (0, amount / self.state.size * TEXTSPACE_TO_GLYPHSPACE),
                *self.kern,
            ],
            self.width + amount,
            self.state,
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
                txt[start:trimpos],
                kern,
                width - trim,
                state,
            )
        )

    def without_trailing_space(self) -> tuple[GaugedString, Pt]:
        trim, kern = _trim(self.txt, self.kern, self.state, 0)
        if trim:
            return (
                GaugedString(
                    self.txt[:-1], kern, self.width - trim, self.state
                ),
                trim,
            )
        else:
            return self, 0

    def __iter__(self) -> Iterator[bytes]:
        if self.kern:
            yield from Array(
                _encode_kerning(self.txt, self.kern, self.state.font)
            ).write()
            yield b" TJ\n"
        else:
            yield from LiteralString(self.state.font.encode(self.txt)).write()
            yield b" Tj\n"


def _size_string(
    s: str, state: State, prev: Char | None, offset: Pos
) -> tuple[Pt, Sequence[Kern], Pt]:
    font = state.font
    kerning = list(font.kern(s, prev, offset))
    return (
        (font.width(s) + sum(map(second, kerning)) / TEXTSPACE_TO_GLYPHSPACE)
        * state.size,
        kerning,
        _trim(s, kerning, state, offset)[0],
    )


def _trim(
    txt: str, kern: Sequence[Kern], s: State, offset: Pos
) -> tuple[Pt, Sequence[Kern]]:
    if txt and txt[-1] == " ":
        trimmable_space = s.font.spacewidth
        if kern:
            lastkern_pos, lastkern = kern[-1]
            if (lastkern_pos - offset) + 1 == len(txt):
                trimmable_space += lastkern
                kern = kern[:-1]
        return trimmable_space * s.size / TEXTSPACE_TO_GLYPHSPACE, kern
    else:
        return 0, kern
