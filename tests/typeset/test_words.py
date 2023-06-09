from __future__ import annotations

from dataclasses import replace
from functools import partial
from typing import Generator, TypeVar

import pytest

from pdfje.atoms import LiteralStr, Real
from pdfje.common import Char
from pdfje.fonts.common import TEXTSPACE_TO_GLYPHSPACE
from pdfje.typeset.state import NO_OP, State
from pdfje.typeset.words import (
    MixedSlug,
    Slug,
    TrailingSpace,
    WithCmd,
    Word,
    into_syllables,
    render_kerned,
)
from pdfje.vendor.hyphenate import hyphenate_word

from ..common import BLUE, FONT, HUGE, RED, approx, mkstate

STATE = mkstate(FONT, 10, hyphens=hyphenate_word)


class TestIntoSyllables:
    def test_simple(self):
        assert list(into_syllables("complex", hyphenate_word)) == [
            "com",
            "plex",
        ]

    def test_ignores_punctuation(self):
        assert list(
            into_syllables("West.”...westerwest““you.", hyphenate_word)
        ) == [
            "West.”...west",
            "er",
            "west““you.",
        ]


class TestHyphenateWord:
    def test_empty(self):
        word = Word((), TrailingSpace(20, 0, STATE.size), STATE)
        assert word.hyphenate(10) == (None, word)

    def test_word_with_one_syllable(self):
        word = Word.new("Newt ", STATE, " ")
        assert word.hyphenate(word.width - 0.01) == (
            None,
            word.without_init_kern(),
        )

    def test_word_with_two_syllables(self):
        word = Word.new("complex", STATE, " ")
        a, b = word.hyphenate(word.width - 0.01)
        assert a == Word((ga("com-", STATE, " "),), None, STATE)
        assert b == Word((ga("plex", STATE, None),), None, STATE)

    def test_split_too_short_for_first_syllable(self):
        word = Word.new("complicated", STATE, " ")
        assert word.hyphenate(60) == (None, word.without_init_kern())

    def test_split_after_first_syllable(self):
        word = Word.new("complicated ", STATE, " ")
        a, b = word.hyphenate(79.99)
        assert a == Word((ga("com-", STATE, " "),), None, STATE)
        assert b == Word(
            (
                ga("pli", STATE, None),
                ga("cat", STATE, "i"),
                ga("ed", STATE, "t"),
            ),
            TrailingSpace(20, 0, STATE.size),
            STATE,
        )

    def test_split_in_middle(self):
        word = Word.new("complicated ", STATE, " ")
        a, b = word.hyphenate(150)
        assert a == Word(
            (ga("com", STATE, " "), ga("pli-", STATE, "m")), None, STATE
        )
        assert b == Word(
            (ga("cat", STATE, None), ga("ed", STATE, "t")),
            TrailingSpace(20, 0, STATE.size),
            STATE,
        )

    def test_split_before_last(self):
        word = Word.new("complicated ", STATE, " ")
        a, b = word.hyphenate(word.width - 30)
        assert a == Word(
            (
                ga("com", STATE, " "),
                ga("pli", STATE, "m"),
                ga("cat-", STATE, "i"),
            ),
            None,
            STATE,
        )
        assert b == Word(
            (ga("ed", STATE, None),), TrailingSpace(20, 0, STATE.size), STATE
        )

    def test_hyphenation_not_needed(self):
        word = Word.new("complicated ", STATE, " ")
        with pytest.raises(RuntimeError, match="necessary"):
            word.hyphenate(10_000)


class TestSlug:
    def test_build(self):
        s = Slug.new("Complex", STATE, " ")
        assert s.kern == [(0, -15), (3, -10), (6, -20)]
        assert s.width == approx(
            (
                STATE.font.width("Complex")
                + sum(x for _, x in s.kern) / TEXTSPACE_TO_GLYPHSPACE
            )
            * STATE.size
        )

    def test_basic_properties(self):
        s = Slug.new("Complex", STATE, " ")
        assert s.pre_state() == STATE
        assert s.last() == "x"
        assert s.pruned_width() == s.width
        assert s.pruned() is s
        assert s.boxes == (s,)
        assert s.extend_tail(8) is s
        assert s.stretch_tail(1.2) is s
        assert s.hyphenate(10) == (None, s)
        assert s.minimal_box() == (s, None)
        assert s.prunable_space() == 0
        assert s.tail is None
        assert s.kern == [(0, -15), (3, -10), (6, -20)]

    def test_with_hyphen(self):
        s = Slug.new("Complex", STATE, " ")
        assert s.with_hyphen() == Slug.new("Complex-", STATE, " ")

    def test_init_kern(self):
        s = Slug.new("Complex", STATE, " ")
        assert s.has_init_kern()
        assert s.without_init_kern() == Slug.new("Complex", STATE, None)

    def test_indent(self):
        s = Slug.new("Complex", STATE, None)
        assert s.indent(0) == s
        indented = s.indent(10)
        assert indented.kern[0] == (
            0,
            10 * TEXTSPACE_TO_GLYPHSPACE / STATE.size,
        )


class TestMixedSlug:
    def test_basic_properties(self):
        s = MixedSlug(
            (
                (Slug.new("Fl", BLUE.apply(STATE), " "), RED),
                (Slug.new("at", RED.apply(STATE), "t"), NO_OP),
            ),
            RED.apply(STATE),
        )
        assert s.pre_state() == BLUE.apply(STATE)
        assert s.last() == "t"
        assert s.pruned_width() == s.width
        assert s.pruned() is s
        assert s.boxes == (s,)
        assert s.extend_tail(8) is s
        assert s.stretch_tail(1.2) is s
        assert s.hyphenate(10) == (None, s)
        assert s.minimal_box() == (s, None)
        assert s.prunable_space() == 0
        assert s.tail is None

    def test_init_kern(self):
        s = MixedSlug(
            (
                (Slug.new("Com", BLUE.apply(STATE), " "), RED),
                (Slug.new("plex", RED.apply(STATE), "m"), NO_OP),
            ),
            RED.apply(STATE),
        )
        assert s.has_init_kern()
        assert s.without_init_kern() == MixedSlug(
            (
                (Slug.new("Com", BLUE.apply(STATE), None), RED),
                (Slug.new("plex", RED.apply(STATE), "m"), NO_OP),
            ),
            RED.apply(STATE),
        )

    def test_indent(self):
        s = MixedSlug(
            (
                (Slug.new("Com", BLUE.apply(STATE), None), RED),
                (Slug.new("plex", RED.apply(STATE), "m"), NO_OP),
            ),
            RED.apply(STATE),
        )
        assert s.indent(0) == s
        indented = s.indent(13)
        assert indented.segments[0][0].kern[0] == (
            0,
            13 * TEXTSPACE_TO_GLYPHSPACE / STATE.size,
        )

    def test_with_hyphen(self):
        s = MixedSlug(
            (
                (Slug.new("Com", BLUE.apply(STATE), None), RED),
                (Slug.new("plex", RED.apply(STATE), "m"), NO_OP),
            ),
            RED.apply(STATE),
        )
        assert s.with_hyphen() == MixedSlug(
            (
                (Slug.new("Com", BLUE.apply(STATE), None), RED),
                (Slug.new("plex", RED.apply(STATE), "m"), NO_OP),
                (Slug.new("-", RED.apply(STATE), "x"), NO_OP),
            ),
            RED.apply(STATE),
        )


class TestWord:
    def test_basic_properties(self):
        word = Word.new("complex. ", STATE, " ")
        assert word.tail is not None
        assert word.pre_state() == STATE
        assert word.last() == " "
        assert word.pruned_width() == approx(
            Word.new("complex.", STATE, " ").width
        )
        assert word.pruned().width == approx(word.pruned_width())
        assert len(word.boxes) == 2
        assert word.extend_tail(8).width == approx(word.width + 8)
        assert word.stretch_tail(1.2).width == approx(
            word.width + word.tail.width_excl_kern * 1.2
        )
        assert word.minimal_box() == word.hyphenate(100)
        assert word.prunable_space() == word.tail.width()
        assert word.tail is not None

    def test_init_kern(self):
        word = Word.new("complex. ", STATE, " ")
        assert word.has_init_kern()
        assert word.without_init_kern() == Word.new("complex. ", STATE, None)
        word2 = Word.new(" ", STATE, "w")
        assert word2.has_init_kern()
        assert word2.without_init_kern() == Word.new(" ", STATE, None)

    def test_indent(self):
        word = Word.new("complex. ", STATE, None)
        assert word.indent(0) == word
        indented = word.indent(13)
        assert isinstance(indented.boxes[0], Slug)
        assert indented.boxes[0].kern[0] == (
            0,
            13 * TEXTSPACE_TO_GLYPHSPACE / STATE.size,
        )
        empty = Word.new(" ", STATE, None)
        indented_empty = empty.indent(13)
        assert indented_empty.tail is not None
        assert indented_empty.tail.kern == (
            13 * TEXTSPACE_TO_GLYPHSPACE / STATE.size
        )


def test_with_cmd():
    w = WithCmd(
        Word.new("complex. ", STATE, " "),
        RED,
    )
    assert w.pre_state() == STATE
    assert w.state == RED.apply(STATE)
    assert w.last() == " "
    assert w.pruned_width() == approx(Word.new("complex.", STATE, " ").width)
    assert w.pruned().width == approx(w.pruned_width())
    assert len(w.boxes) == 2
    assert w.extend_tail(8).width == approx(w.width + 8)
    assert w.tail is not None
    assert w.stretch_tail(1.2).width == approx(
        w.width + w.tail.width_excl_kern * 1.2
    )
    assert w.minimal_box() == w.hyphenate(100)
    assert w.prunable_space() == w.tail.width()
    assert w.tail is not None
    assert w.has_init_kern()
    assert w.without_init_kern() == WithCmd(
        Word.new("complex. ", STATE, None),
        RED,
    )
    assert w.indent(0) == w
    assert w.without_init_kern().indent(14) == WithCmd(
        Word.new("complex. ", STATE, None).indent(14),
        RED,
    )


T = TypeVar("T")
U = TypeVar("U")


def consume_gen(g: Generator[T, None, U]) -> tuple[list[T], U]:
    buffer = []
    try:
        while True:
            buffer.append(next(g))
    except StopIteration as e:
        return buffer, e.value


class TestEncodeIntoLine:
    def test_word(self):
        word = Word.new("complex. ", STATE, " ")
        gen = word.encode_into_line([Real(15), LiteralStr(b"better than")])
        content, rest = consume_gen(gen)
        assert content == []
        assert list(rest) == [
            Real(15),
            LiteralStr(b"better than"),
            Real(15),
            LiteralStr(b"com"),
            Real(10),
            LiteralStr(b"ple"),
            Real(20),
            LiteralStr(b"x."),
            Real(15),
            LiteralStr(b" "),
        ]

    def test_mixed_word(self):
        word = Word(
            (
                MixedSlug(
                    (
                        (ga("Fl", BLUE.apply(STATE), " "), RED),
                        (ga("at", RED.apply(STATE), "t"), NO_OP),
                    ),
                    RED.apply(STATE),
                ),
            ),
            None,
            RED.apply(STATE),
        )
        gen = word.encode_into_line([Real(5), LiteralStr(b"complicated. ")])
        content, rest = consume_gen(gen)
        assert list(rest) == []
        assert content == [
            *render_kerned(
                [
                    Real(5),
                    LiteralStr(b"complicated. "),
                    LiteralStr(b"Fl"),
                ]
            ),
            *RED,
            *render_kerned([LiteralStr(b"at")]),
        ]

    def test_word_with_cmd(self):
        word = WithCmd(Word.new("complex. ", STATE, " "), HUGE)
        gen = word.encode_into_line([Real(15), LiteralStr(b"better than ")])
        content, rest = consume_gen(gen)
        assert list(rest) == []
        assert content == [
            *render_kerned(
                [
                    Real(15),
                    LiteralStr(b"better than "),
                    Real(15),
                    LiteralStr(b"com"),
                    Real(10),
                    LiteralStr(b"ple"),
                    Real(20),
                    LiteralStr(b"x."),
                    Real(15),
                    LiteralStr(b" "),
                ]
            ),
            *HUGE,
        ]


def g(
    s: str, st: State, prev: Char | None = None, approx_: bool = False
) -> Slug:
    """Helper to create a kerned string"""
    string = Slug.new(s, st, prev)
    assert isinstance(string, Slug)
    return replace(string, width=approx(string.width)) if approx_ else string


ga = partial(g, approx_=True)
