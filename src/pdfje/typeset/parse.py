from __future__ import annotations

import re
from typing import Generator, Iterable, Iterator

from ..common import Char, Pos, prepend
from ..compat import pairwise
from ..fonts.common import TEXTSPACE_TO_GLYPHSPACE
from .state import Chain, Command, Passage, State
from .words import MixedSlug, Slug, TrailingSpace, Word, WordLike

# FUTURE: expand to support the full unicode spec,
# see https://unicode.org/reports/tr14/.
_WORD_RE = re.compile(
    r"(.*?( +|-|\N{ZERO WIDTH SPACE}|\N{EM DASH}|(?=\N{EM DASH}\w)))"
)


def into_words(
    it: Iterable[Passage], state: State
) -> tuple[Command, Iterator[WordLike]]:
    it = iter(it)
    cmd, txt, state = _fold_commands(it, state)
    return cmd, _parse(it, state, txt) if txt else iter(())


def _parse(
    it: Iterable[Passage], state: State, txt: str | None
) -> Iterator[WordLike]:
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
            cmd, txt = next(it)
        except StopIteration:
            yield last
            return
        yield last.with_cmd(cmd)
        state = cmd.apply(state)
        pos = 0


def _parse_simple_words(
    txt: str, pos: Pos, state: State, prev: Char | None
) -> Generator[WordLike, None, str | Word]:
    assert pos < len(txt)
    ms = _WORD_RE.finditer(txt, pos)
    try:
        next_match = next(ms)
    except StopIteration:
        return txt[pos:]

    for match, next_match in pairwise(prepend(next_match, ms)):
        word = match.group()
        match.groups()
        yield Word.new(word, state, prev)
        prev = word[-1]

    final_word = Word.new(next_match.group(), state, prev)
    pos = next_match.end()
    if pos < len(txt):
        yield final_word
        return txt[pos:]
    else:
        return final_word


def _complete_word(
    it: Iterator[Passage], head: str, state: State, prev: Char | None
) -> tuple[Word, str | None, Pos]:
    parts: list[tuple[Command, str]] = []
    has_trailing_space = False
    st: Passage | None
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
            return Word.new(head, state, prev), st, pos

    # SIMPLIFICATION: for now, we don't hyphenate words that are split across
    # multiple styles. This because it's a rare case, and it's non-trivial
    # to implement.

    seg = Slug.new(head, state, prev)
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
            seg = Slug.new(txt, state, prev)
            prev = txt[-1]

    segments.append((seg, Chain.squash(cmds)))

    trailing_space = None
    if has_trailing_space:
        trailing_space = TrailingSpace(
            state.font.spacewidth / TEXTSPACE_TO_GLYPHSPACE * state.size,
            state.font.charkern(prev, " ") if prev else 0,
            state.size,
        )

    return (
        Word((MixedSlug(tuple(segments), state),), trailing_space, state),
        st.txt if st else None,
        pos,
    )


def _fold_commands(
    it: Iterator[Passage], state: State
) -> tuple[Command, str | None, State]:
    buffer: list[Command] = []
    for s in it:
        buffer.append(s.cmd)
        state = s.cmd.apply(state)
        if s.txt:
            return Chain.squash(buffer), s.txt, state
    return Chain.squash(buffer), None, state
