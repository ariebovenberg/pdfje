"Logic for breaking text into breakable units (words)."
# Note that a lot of the complexity here is due to the fact that we need to
# support changes to the text state (i.e. style), which can occur at any point
# in the text.
# Additionally, we try to keep performance reasonable by avoiding unnecessary
# copying, focussing on the most common cases, and using iterators.
from __future__ import annotations

import re
from dataclasses import dataclass
from itertools import chain, pairwise
from typing import Generator, Iterable, Iterator, Sequence

from pdfje.atoms import Array, LiteralStr, Real

from ..common import (
    Char,
    NonEmptySequence,
    Pos,
    Pt,
    Streamable,
    add_slots,
    prepend,
)
from ..fonts.common import TEXTSPACE_TO_GLYPHSPACE, GlyphPt
from .common import NO_OP, Chain, Command, Slug, State, Stretch

# FUTURE: expand to support the full unicode spec,
# see https://unicode.org/reports/tr14/.
_WORD_RE = re.compile(
    r"(.*?( +|-|\N{ZERO WIDTH SPACE}|\N{EM DASH}|.(?=\N{EM DASH}\w)))"
)


@add_slots
@dataclass(frozen=True)
class MixedBox:
    segments: NonEmptySequence[tuple[Slug, Command]]
    state: State

    def with_hyphen(self) -> MixedBox:
        return MixedBox(
            (
                *self.segments,
                (
                    Slug.nonempty(
                        "-", self.state, self.segments[-1][0].last()
                    ),
                    NO_OP,
                ),
            ),
            self.state,
        )

    def without_init_kern(self) -> MixedBox:
        (first, cmd), *rest = self.segments
        return MixedBox(
            ((first.without_init_kern(), cmd), *rest),
            self.state,
        )

    def has_init_kern(self) -> bool:
        return self.segments[0][0].has_init_kern()

    def indent(self, amount: Pt) -> MixedBox:
        (first, cmd), *rest = self.segments
        return MixedBox(
            ((first.indent(amount), cmd), *rest),
            self.state,
        )

    @property
    def width(self) -> Pt:
        return sum(s.width for s, _ in self.segments)

    @property
    def lead(self) -> Pt:
        return max(s.lead for s, _ in self.segments)

    def encode_into_line(
        self, line: Iterable[LiteralStr | Real]
    ) -> Generator[bytes, None, Iterable[LiteralStr | Real]]:
        for txt, cmd in self.segments:
            yield from render_kerned(chain(line, txt.to_atoms()))
            yield from cmd
            line = ()
        return line


@add_slots
@dataclass(frozen=True)
class Word:
    boxes: Sequence[Slug | MixedBox]
    tail: TrailingSpace | None
    state: State

    @staticmethod
    def simple(s: str, state: State, prev: Char | None) -> Word:
        s, tail = TrailingSpace.parse(s, state, prev)
        segments = []
        for part in state.hyphens(s) if s else ():
            segments.append(Slug.nonempty(part, state, prev))
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
            return Word((), TrailingSpace(self.tail.width, 0), self.state)
        else:
            return self

    def indent(self, amount: Pt) -> Word:
        if self.boxes:
            return Word(
                (self.boxes[0].indent(amount), *self.boxes[1:]),
                self.tail,
                self.state,
            )
        assert self.tail  # Words with no boxes or tail shouldn't exist
        return Word((), self.tail.stretch(amount, self.state), self.state)

    def pruned_width(self) -> Pt:
        return sum(s.width for s in self.boxes)

    def width(self) -> Pt:
        return self.pruned_width() + (self.tail.width if self.tail else 0)

    def lead(self) -> Pt:
        return (
            max((s.lead for s in self.boxes))
            if self.boxes
            else self.state.lead
        )

    def with_cmd(self, c: Command) -> WithCmd | Word:
        if c is NO_OP:
            return self
        return WithCmd(self, c)

    def stretch_tail(self, amount: Pt) -> Word:
        return (
            Word(self.boxes, self.tail.stretch(amount, self.state), self.state)
            if self.tail
            else self
        )

    def prunable_space(self) -> Pt:
        return self.tail.width if self.tail else 0

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
class WithCmd:
    word: Word
    cmd: Command

    @property
    def state(self) -> State:
        return self.cmd.apply(self.word.state)

    @property
    def tail(self) -> TrailingSpace | None:
        return self.word.tail

    def lead(self) -> Pt:
        return self.word.lead()

    def without_init_kern(self) -> WithCmd:
        return WithCmd(self.word.without_init_kern(), self.cmd)

    def width(self) -> Pt:
        return self.word.width()

    def pruned_width(self) -> Pt:
        return self.word.pruned_width()

    def pruned(self) -> WithCmd:
        return WithCmd(self.word.pruned(), self.cmd)

    def stretch_tail(self, amount: Pt) -> WithCmd:
        return (
            WithCmd(self.word.stretch_tail(amount), self.cmd)
            if self.word.tail
            else self
        )

    def hyphenate(self, w: Pt, /) -> tuple[Word | None, Word | WithCmd]:
        a, b = self.word.hyphenate(w)
        return a, b.with_cmd(self.cmd)

    def minimal_box(self) -> tuple[Word | WithCmd, Word | WithCmd | None]:
        a, b = self.word.minimal_box()
        if b is None:
            return WithCmd(a, self.cmd), None
        return a, WithCmd(b, self.cmd)

    def prunable_space(self) -> Pt:
        return self.word.prunable_space()

    def indent(self, amount: Pt) -> WithCmd:
        return WithCmd(self.word.indent(amount), self.cmd)

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
    width: Pt  # including kerning adjustment
    kern: GlyphPt

    @staticmethod
    def parse(
        s: str, state: State, prev: Char | None
    ) -> tuple[str, TrailingSpace | None]:
        tail = None
        if s.endswith(" "):
            s = s[:-1]
            prev = s[-1] if s else prev
            kern = state.font.charkern(prev, " ") if prev else 0
            tail = TrailingSpace(
                (state.font.spacewidth + kern)
                * state.size
                / TEXTSPACE_TO_GLYPHSPACE,
                kern,
            )
        return s, tail

    def stretch(self, amount: Pt, state: State) -> TrailingSpace:
        return TrailingSpace(
            self.width + amount,
            self.kern + (amount / state.size * TEXTSPACE_TO_GLYPHSPACE),
        )

    def into_atoms(self, s: State) -> Iterable[Real | LiteralStr]:
        if self.kern:
            yield Real(-self.kern)
        yield LiteralStr(s.font.encode(" "))


def parse(
    it: Iterable[Stretch], state: State
) -> tuple[Command, Iterator[Word | WithCmd]]:
    it = iter(it)
    cmd, txt, state = _fold_commands(it, state)
    return cmd, _parse_rest(it, state, txt) if txt else iter(())


def _parse_simple_words(
    txt: str, pos: Pos, state: State, prev: Char | None
) -> Generator[Word | WithCmd, None, str | Word]:
    assert pos < len(txt)
    ms = _WORD_RE.finditer(txt, pos)
    try:
        next_match = next(ms)
    except StopIteration:
        return txt[pos:]

    for match, next_match in pairwise(prepend(next_match, ms)):
        word = match.group()
        yield Word.simple(word, state, prev)
        prev = word[-1]

    final_word = Word.simple(next_match.group(), state, prev)
    pos = next_match.end()
    if pos < len(txt):
        yield final_word
        return txt[pos:]
    else:
        return final_word


def _parse_rest(
    it: Iterable[Stretch], state: State, txt: str | None
) -> Iterator[Word | WithCmd]:
    it = iter(it)
    prev: Char | None = None
    pos = 0

    while txt:
        last = yield from _parse_simple_words(txt, pos, state, prev)
        if isinstance(last, str):
            last, txt, pos = _complete_word(it, last, state, prev)
            state = last.state
            if txt is None:
                yield last
                return
            elif pos < len(txt):
                yield last
                continue
        try:
            __s = next(it)
            cmd = __s.cmd
            txt = __s.txt
        except StopIteration:
            yield last
            return
        yield last.with_cmd(cmd)
        state = cmd.apply(state)
        pos = 0


def _complete_word(
    it: Iterator[Stretch], head: str, state: State, prev: Char | None
) -> tuple[Word, str | None, Pos]:
    parts: list[tuple[Command, str]] = []
    has_trailing_space = False
    st: Stretch | None
    for st in it:
        if match := _WORD_RE.search(st.txt):
            word = match.group()
            if word.endswith(" "):
                has_trailing_space = True
                word = word[:-1]
            parts.append((st.cmd, word))
            pos = match.end()
            break
        parts.append((st.cmd, st.txt))
    else:
        pos = 0
        st = None
        if not parts:
            # A common case -- i.e. no space after the last word of a paragraph
            return Word.simple(head, state, prev), st, pos

    # SIMPLIFICATION: for now, we don't hyphenate words that are split across
    # multiple styles. This because it's a rare case, and it's non-trivial
    # to implement.

    seg = Slug.nonempty(head, state, prev)
    prev = seg.last()
    segments: list[tuple[Slug, Command]] = []
    cmds = []
    for cmd, txt in parts:
        new_state = cmd.apply(state)
        prev = prev if state.kerns_with(new_state) else None
        state = new_state
        cmds.append(cmd)
        if txt:
            segments.append((seg, Chain.squash(cmds)))
            cmds.clear()
            seg = Slug.nonempty(txt, state, prev)
            prev = txt[-1]

    segments.append((seg, Chain.squash(cmds)))

    trailing_space = None
    if has_trailing_space:
        kern = state.font.charkern(prev, " ") if prev else 0
        trailing_space = TrailingSpace(
            (state.font.spacewidth + kern)
            * state.size
            / TEXTSPACE_TO_GLYPHSPACE,
            kern,
        )

    return (
        Word((MixedBox(tuple(segments), state),), trailing_space, state),
        st.txt if st else None,
        pos,
    )


def _fold_commands(
    it: Iterator[Stretch], state: State
) -> tuple[Command, str | None, State]:
    buffer: list[Command] = []
    for s in it:
        buffer.append(s.cmd)
        state = s.cmd.apply(state)
        if s.txt:
            return Chain.squash(buffer), s.txt, state
    return Chain.squash(buffer), None, state


def render_kerned(content: Iterable[LiteralStr | Real]) -> Streamable:
    return chain(Array(content).write(), (b" TJ\n",))
