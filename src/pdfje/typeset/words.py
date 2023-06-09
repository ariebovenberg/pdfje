"Logic for breaking text into breakable units (words)."
# Note that a lot of the complexity here is due to the fact that we need to
# support changes to the text state (i.e. style), which can occur at any point
# in the text.
# Additionally, we try to keep performance reasonable by avoiding unnecessary
# copying, focussing on the most common cases, and using iterators.
# FUTURE: we could probablify this data model.
from __future__ import annotations

import re
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from itertools import chain
from typing import ClassVar, Generator, Iterable, Iterator, Sequence, TypeVar

from pdfje.typeset.hyphens import Hyphenator

from ..atoms import Array, LiteralStr, Real
from ..common import (
    Char,
    NonEmptySequence,
    Pt,
    Streamable,
    add_slots,
    fix_abstract_properties,
    second,
)
from ..compat import pairwise
from ..fonts.common import TEXTSPACE_TO_GLYPHSPACE, Font, GlyphPt, Kern
from .state import NO_OP, Command, State

_T = TypeVar("_T")
_find_wordchars = re.compile(r"\w+").finditer


@fix_abstract_properties
class WordLike(ABC):
    __slots__ = ()

    # FUTURE: rename to syllables?
    @property
    @abstractmethod
    def boxes(self) -> Sequence[Slug | MixedSlug]:
        ...

    # FUTURE: rename to end state?
    @property
    @abstractmethod
    def state(self) -> State:
        ...

    @property
    @abstractmethod
    def width(self) -> Pt:
        ...

    @property
    @abstractmethod
    def tail(self) -> TrailingSpace | None:
        ...

    @abstractmethod
    def pre_state(self) -> State:
        ...

    @abstractmethod
    def last(self) -> Char:
        ...

    @abstractmethod
    def has_init_kern(self) -> bool:
        ...

    @abstractmethod
    def without_init_kern(self: _T) -> _T:
        ...

    @abstractmethod
    def indent(self: _T, amount: Pt) -> _T:
        ...

    @abstractmethod
    def pruned_width(self) -> Pt:
        ...

    @abstractmethod
    def prunable_space(self) -> Pt:
        ...

    @abstractmethod
    def pruned(self) -> WordLike:
        ...

    @abstractmethod
    def extend_tail(self: _T, amount: Pt) -> _T:
        ...

    @abstractmethod
    def stretch_tail(self: _T, ratio: float) -> _T:
        ...

    @abstractmethod
    def hyphenate(self, w: Pt) -> tuple[WordLike | None, WordLike]:
        ...

    @abstractmethod
    def minimal_box(self) -> tuple[WordLike, WordLike | None]:
        ...

    @abstractmethod
    def encode_into_line(
        self, line: Iterable[LiteralStr | Real]
    ) -> Generator[bytes, None, Iterable[LiteralStr | Real]]:
        ...

    def with_cmd(self, cmd: Command) -> WordLike:
        return self if cmd is NO_OP else WithCmd(self, cmd)


@add_slots
@dataclass(frozen=True)
class Slug(WordLike):
    "A fragment of text with its measured width and kerning information"
    txt: str  # non-empty
    kern: Sequence[Kern]
    width: Pt  # including kerning
    state: State = field(repr=False)

    tail: ClassVar[None] = None

    def pre_state(self) -> State:
        return self.state

    def last(self) -> Char:
        return self.txt[-1]

    def with_hyphen(self) -> Slug:
        kern = self.state.font.charkern(self.last(), "-")
        return Slug(
            self.txt + "-",
            [*self.kern, (len(self.txt), kern)] if kern else self.kern,
            self.width
            + (
                (self.state.font.charwidth("-") + kern)
                / TEXTSPACE_TO_GLYPHSPACE
            )
            * self.state.size,
            self.state,
        )

    def has_init_kern(self) -> bool:
        return bool(self.kern) and self.kern[0][0] == 0

    # FUTURE: rename?
    @staticmethod
    def new(s: str, state: State, prev: Char | None) -> Slug:
        font = state.font
        kern = list(font.kern(s, prev))
        return Slug(
            s,
            kern,
            (font.width(s) + sum(map(second, kern)) / TEXTSPACE_TO_GLYPHSPACE)
            * state.size,
            state,
        )

    def without_init_kern(self) -> Slug:
        kern = self.kern
        if kern:
            firstkern_pos, firstkern = kern[0]
            if firstkern_pos == 0:
                delta = (firstkern * self.state.size) / TEXTSPACE_TO_GLYPHSPACE
                return Slug(self.txt, kern[1:], self.width - delta, self.state)
        return self

    def indent(self, amount: Pt) -> Slug:
        # Shortcut for common case
        if not amount:
            return self

        # We only indent the first word of a line -- which never has Kerning
        # on the first letter.
        try:
            assert self.kern[0][0] != 0
        except IndexError:  # pragma: no cover
            pass
        return Slug(
            self.txt,
            [
                (0, amount / self.state.size * TEXTSPACE_TO_GLYPHSPACE),
                *self.kern,
            ],
            self.width + amount,
            self.state,
        )

    def pruned_width(self) -> Pt:
        return self.width

    def pruned(self) -> Slug:
        return self

    @property
    def boxes(self) -> Sequence[Slug | MixedSlug]:
        return (self,)

    def extend_tail(self, amount: Pt) -> Slug:
        return self

    def stretch_tail(self, ratio: float) -> Slug:
        return self

    def hyphenate(self, w: Pt, /) -> tuple[None, Slug]:
        return None, self

    # FUTURE: does this need to be in the interface?
    def minimal_box(self) -> tuple[Slug, None]:
        return self, None

    def prunable_space(self) -> Pt:
        return 0

    def to_atoms(self) -> Iterable[LiteralStr | Real]:
        return _encode_kerning(self.txt, self.kern, self.state.font)

    # FUTURE: we can be more efficient in writing multi-word strings.
    #         In the current situation they are always separated.
    def encode_into_line(
        self, line: Iterable[LiteralStr | Real]
    ) -> Generator[bytes, None, Iterable[LiteralStr | Real]]:
        return chain(line, self.to_atoms())
        # We need have one `yield` statement to turn this into a generator.
        # It doesn't matter that it will never be reached.
        yield  # type: ignore[unreachable]


@add_slots
@dataclass(frozen=True)
class MixedSlug(WordLike):
    """A fragment of text containing commands within it. For example a word
    which is partially italic."""

    segments: NonEmptySequence[tuple[Slug, Command]]
    state: State = field(repr=False)

    tail: ClassVar[None] = None

    def prunable_space(self) -> Pt:
        return 0

    def pruned(self) -> MixedSlug:
        return self

    def pruned_width(self) -> Pt:
        return self.width

    def minimal_box(self) -> tuple[WordLike, WordLike | None]:
        return self, None

    @property
    def boxes(self) -> Sequence[MixedSlug]:
        return (self,)

    def pre_state(self) -> State:
        return self.segments[0][0].state

    def last(self) -> Char:
        return self.segments[-1][0].last()

    def extend_tail(self, amount: Pt) -> MixedSlug:
        return self

    def stretch_tail(self, ratio: float) -> MixedSlug:
        return self

    def hyphenate(self, w: Pt, /) -> tuple[None, MixedSlug]:
        return None, self

    def with_hyphen(self) -> MixedSlug:
        return MixedSlug(
            (
                *self.segments,
                (
                    Slug.new("-", self.state, self.segments[-1][0].last()),
                    NO_OP,
                ),
            ),
            self.state,
        )

    def without_init_kern(self) -> MixedSlug:
        (first, cmd), *rest = self.segments
        return MixedSlug(
            ((first.without_init_kern(), cmd), *rest),
            self.state,
        )

    def has_init_kern(self) -> bool:
        return self.segments[0][0].has_init_kern()

    def indent(self, amount: Pt) -> MixedSlug:
        if amount:
            (first, cmd), *rest = self.segments
            return MixedSlug(
                ((first.indent(amount), cmd), *rest),
                self.state,
            )
        else:
            return self

    @property
    def width(self) -> Pt:
        return sum(s.width for s, _ in self.segments)

    def encode_into_line(
        self, line: Iterable[LiteralStr | Real]
    ) -> Generator[bytes, None, Iterable[LiteralStr | Real]]:
        for txt, cmd in self.segments:
            yield from render_kerned(chain(line, txt.to_atoms()))
            yield from cmd
            line = ()
        return line


def into_syllables(s: str, hyphens: Hyphenator) -> Iterable[str]:
    leftover = ""
    buffer: list[str] = []
    end = 0
    for match in _find_wordchars(s):
        leftover += s[end : match.start()]  # noqa: E203
        syllables = iter(hyphens(match.group()))
        buffer.append(leftover + next(syllables))
        buffer.extend(syllables)
        leftover = buffer.pop()
        yield from buffer
        buffer.clear()
        end = match.end()

    if leftover or end < len(s):
        yield leftover + s[end:]


@add_slots
@dataclass(frozen=True)
class Word(WordLike):
    # FUTURE: defer hyphenation until it is absolutely necessary.
    #         this would improve performance
    boxes: Sequence[Slug | MixedSlug]
    tail: TrailingSpace | None
    state: State = field(repr=False)

    def pre_state(self) -> State:
        try:
            first = self.boxes[0]
        except IndexError:
            return self.state
        return first.pre_state()

    def last(self) -> Char:
        return " " if self.tail else self.boxes[-1].last()

    def has_init_kern(self) -> bool:
        return (
            self.boxes[0].has_init_kern()
            if self.boxes
            else bool(self.tail and self.tail.kern)
        )

    @staticmethod
    def new(s: str, state: State, prev: Char | None) -> Word:
        s, tail = TrailingSpace.parse(s, state, prev)
        segments = []
        for part in into_syllables(s, state.hyphens):
            segments.append(Slug.new(part, state, prev))
            prev = part[-1]
        return Word(tuple(segments), tail, state)

    def hyphenate(self, space: Pt, /) -> tuple[Word | None, Word]:
        if len(self.boxes) < 1 or self.boxes[0].with_hyphen().width > space:
            return (None, self.without_init_kern())
        fitting = []
        it = iter(self.boxes)
        for box, next_box in pairwise(it):
            space -= box.width
            if next_box.with_hyphen().width > space:
                fitting.append(box.with_hyphen())
                break
            fitting.append(box)
        else:
            # We shouldn't reach this point because hypenation is only
            # called if it's necessary.
            raise RuntimeError("Hyphenation not necessary")

        return (
            Word(tuple(fitting), None, box.state) if fitting else None,
            Word((next_box.without_init_kern(), *it), self.tail, self.state),
        )

    def minimal_box(self) -> tuple[Word, Word | None]:
        "Split off a minimal part of the word, leaving the rest."
        if len(self.boxes) < 2:
            return (self, None)
        else:
            return (
                Word(
                    (self.boxes[0].with_hyphen(),), None, self.boxes[0].state
                ),
                Word(
                    (self.boxes[1].without_init_kern(), *self.boxes[2:]),
                    self.tail,
                    self.state,
                ),
            )

    def without_init_kern(self) -> Word:
        if self.boxes:
            return (
                Word(
                    (self.boxes[0].without_init_kern(), *self.boxes[1:]),
                    self.tail,
                    self.state,
                )
                if self.boxes[0].has_init_kern()
                else self
            )
        elif self.tail and self.tail.kern:
            return Word(
                (),
                TrailingSpace(self.tail.width_excl_kern, 0, self.tail.size),
                self.state,
            )
        else:
            return self

    def indent(self, amount: Pt) -> Word:
        if amount:
            if self.boxes:
                return Word(
                    (self.boxes[0].indent(amount), *self.boxes[1:]),
                    self.tail,
                    self.state,
                )
            assert self.tail  # Words with no boxes or tail shouldn't exist
            return Word((), self.tail.stretch(amount, self.state), self.state)
        else:
            return self

    def pruned_width(self) -> Pt:
        return sum(s.width for s in self.boxes)

    @property
    def width(self) -> Pt:
        return self.pruned_width() + (self.tail.width() if self.tail else 0)

    def extend_tail(self, amount: Pt) -> Word:
        return (
            Word(self.boxes, self.tail.stretch(amount, self.state), self.state)
            if self.tail and amount
            else self
        )

    def stretch_tail(self, ratio: float) -> Word:
        return (
            Word(
                self.boxes,
                self.tail.stretch(
                    ratio * self.tail.width_excl_kern, self.state
                ),
                self.state,
            )
            if self.tail and ratio != 1
            else self
        )

    def prunable_space(self) -> Pt:
        return self.tail.width() if self.tail else 0

    def pruned(self) -> Word:
        return Word(self.boxes, None, self.state) if self.tail else self

    def encode_into_line(
        self, line: Iterable[LiteralStr | Real]
    ) -> Generator[bytes, None, Iterable[LiteralStr | Real]]:
        for b in self.boxes:
            line = yield from b.encode_into_line(line)
        return (
            chain(line, self.tail.into_atoms(self.state))
            if self.tail
            else line
        )


@add_slots
@dataclass(frozen=True)
class WithCmd(WordLike):
    word: WordLike
    cmd: Command

    def last(self) -> Char:
        return self.word.last()

    def has_init_kern(self) -> bool:
        return self.word.has_init_kern()

    @property
    def state(self) -> State:
        return self.cmd.apply(self.word.state)

    def pre_state(self) -> State:
        return self.word.pre_state()

    @property
    def tail(self) -> TrailingSpace | None:
        return self.word.tail

    @property
    def boxes(self) -> Sequence[Slug | MixedSlug]:
        return self.word.boxes

    def without_init_kern(self) -> WithCmd:
        return WithCmd(self.word.without_init_kern(), self.cmd)

    @property
    def width(self) -> Pt:
        return self.word.width

    def pruned_width(self) -> Pt:
        return self.word.pruned_width()

    def pruned(self) -> WithCmd:
        return WithCmd(self.word.pruned(), self.cmd)

    def extend_tail(self, amount: Pt) -> WithCmd:
        return (
            WithCmd(self.word.extend_tail(amount), self.cmd)
            if self.word.tail and amount
            else self
        )

    def stretch_tail(self, ratio: float) -> WithCmd:
        return (
            WithCmd(self.word.stretch_tail(ratio), self.cmd)
            if self.word.tail
            else self
        )

    def hyphenate(self, w: Pt, /) -> tuple[WordLike | None, WordLike]:
        a, b = self.word.hyphenate(w)
        return a, b.with_cmd(self.cmd)

    def minimal_box(self) -> tuple[WordLike, WordLike | None]:
        a, b = self.word.minimal_box()
        if b is None:
            return a.with_cmd(self.cmd), None
        return a, b.with_cmd(self.cmd)

    def prunable_space(self) -> Pt:
        return self.word.prunable_space()

    def indent(self, amount: Pt) -> WithCmd:
        return WithCmd(self.word.indent(amount), self.cmd) if amount else self

    def encode_into_line(
        self, line: Iterable[LiteralStr | Real]
    ) -> Generator[bytes, None, Iterable[LiteralStr | Real]]:
        line = yield from self.word.encode_into_line(line)
        yield from render_kerned(line)
        yield from self.cmd
        return ()


@add_slots
@dataclass(frozen=True)
class TrailingSpace:
    width_excl_kern: Pt  # including kerning adjustment
    kern: GlyphPt
    size: Pt

    @staticmethod
    def parse(
        s: str, state: State, prev: Char | None
    ) -> tuple[str, TrailingSpace | None]:
        tail = None
        if s.endswith(" "):
            s = s[:-1]
            prev = s[-1] if s else prev
            tail = TrailingSpace(
                state.font.spacewidth / TEXTSPACE_TO_GLYPHSPACE * state.size,
                state.font.charkern(prev, " ") if prev else 0,
                state.size,
            )
        return s, tail

    # FUTURE: cache?
    def width(self) -> Pt:
        return (
            self.width_excl_kern
            + (self.kern * self.size) / TEXTSPACE_TO_GLYPHSPACE
        )

    def stretch(self, amount: Pt, state: State) -> TrailingSpace:
        return TrailingSpace(
            self.width_excl_kern,
            self.kern + (amount / state.size * TEXTSPACE_TO_GLYPHSPACE),
            self.size,
        )

    def into_atoms(self, s: State) -> Iterable[Real | LiteralStr]:
        if self.kern:
            yield Real(-self.kern)
        yield LiteralStr(s.font.encode(" "))


def render_kerned(content: Iterable[LiteralStr | Real]) -> Streamable:
    return chain(Array(content).write(), (b" TJ\n",))


def indent_first(ws: Iterable[WordLike], amount: Pt) -> Iterator[WordLike]:
    it = iter(ws)
    try:
        first = next(it)
    except StopIteration:
        return
    yield first.indent(amount)
    yield from it


# FUTURE: handle generic iterable
def _encode_kerning(
    txt: str, kerning: Sequence[Kern], f: Font
) -> Iterable[LiteralStr | Real]:
    encoded = f.encode(txt)
    try:
        index_prev, space = kerning[0]
    except IndexError:
        yield LiteralStr(encoded)
        return

    if index_prev == 0:  # i.e. the case where we kern before any text
        yield Real(-space)
        kerning = kerning[1:]

    index_prev = index = 0
    for index, space in kerning:
        index *= f.encoding_width
        yield LiteralStr(encoded[index_prev:index])
        yield Real(-space)
        index_prev = index

    yield LiteralStr(encoded[index:])
