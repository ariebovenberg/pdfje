from __future__ import annotations

from dataclasses import replace
from functools import partial
from typing import Generator, TypeVar

import pytest

from pdfje.atoms import LiteralStr, Real
from pdfje.common import Char
from pdfje.typeset.common import NO_OP, Chain, Passage, Slug, State
from pdfje.typeset.words import (
    MixedBox,
    TrailingSpace,
    WithCmd,
    Word,
    parse,
    render_kerned,
)
from pdfje.vendor.hyphenate import hyphenate_word

from ..common import (
    BIG,
    BLUE,
    FONT,
    GREEN,
    HUGE,
    NORMAL,
    RED,
    SMALL,
    approx,
    eq_iter,
    mkstate,
    multi,
)

STATE = mkstate(FONT, 10, hyphens=hyphenate_word)


class TestHyphenateWord:
    def test_empty(self):
        word = Word((), TrailingSpace(20, 0), STATE)
        assert word.hyphenate(10) == (None, word)

    def test_word_with_one_syllable(self):
        word = Word.simple("Newt ", STATE, " ")
        assert word.hyphenate(word.width() - 0.01) == (
            None,
            word.without_init_kern(),
        )

    def test_word_with_two_syllables(self):
        word = Word.simple("complex", STATE, " ")
        a, b = word.hyphenate(word.width() - 0.01)
        assert a == Word((ga("com-", STATE, " "),), None, STATE)
        assert b == Word((ga("plex", STATE, None),), None, STATE)

    def test_split_too_short_for_first_syllable(self):
        word = Word.simple("complicated", STATE, " ")
        assert word.hyphenate(60) == (None, word.without_init_kern())

    def test_split_after_first_syllable(self):
        word = Word.simple("complicated ", STATE, " ")
        a, b = word.hyphenate(79.99)
        assert a == Word((ga("com-", STATE, " "),), None, STATE)
        assert b == Word(
            (
                ga("pli", STATE, None),
                ga("cat", STATE, "i"),
                ga("ed", STATE, "t"),
            ),
            TrailingSpace(20, 0),
            STATE,
        )

    def test_split_in_middle(self):
        word = Word.simple("complicated ", STATE, " ")
        a, b = word.hyphenate(150)
        assert a == Word(
            (ga("com", STATE, " "), ga("pli-", STATE, "m")), None, STATE
        )
        assert b == Word(
            (ga("cat", STATE, None), ga("ed", STATE, "t")),
            TrailingSpace(20, 0),
            STATE,
        )

    def test_split_before_last(self):
        word = Word.simple("complicated ", STATE, " ")
        a, b = word.hyphenate(word.width() - 30)
        assert a == Word(
            (
                ga("com", STATE, " "),
                ga("pli", STATE, "m"),
                ga("cat-", STATE, "i"),
            ),
            None,
            STATE,
        )
        assert b == Word((ga("ed", STATE, None),), TrailingSpace(20, 0), STATE)

    def test_hyphenation_not_needed(self):
        word = Word.simple("complicated ", STATE, " ")
        with pytest.raises(RuntimeError, match="necessary"):
            word.hyphenate(10_000)


class TestParse:
    def test_empty(self):
        cmd, words = parse([], STATE)
        assert cmd is NO_OP
        assert list(words) == []

    def test_only_commands(self):
        cmd, words = parse([Passage(BLUE, ""), Passage(BIG, "")], STATE)
        assert cmd == Chain(eq_iter([BLUE, BIG]))
        assert list(words) == []

    def test_one_word(self):
        cmd, words = parse([Passage(BLUE, "complex ")], STATE)
        assert cmd == BLUE
        assert list(words) == [
            Word(
                (
                    ga("com", BLUE.apply(STATE), None),
                    ga("plex", BLUE.apply(STATE), "m"),
                ),
                TrailingSpace(20, 0),
                BLUE.apply(STATE),
            )
        ]

    def test_one_space(self):
        cmd, words = parse([Passage(BLUE, " ")], STATE)
        assert cmd == BLUE
        assert list(words) == [
            Word((), TrailingSpace(20, 0), BLUE.apply(STATE))
        ]

    def test_two_compound_words(self):
        cmd, words = parse(
            [
                Passage(BLUE, "bet"),
                Passage(BIG, "ter th"),
                Passage(GREEN, "an "),
                Passage(HUGE, ""),
            ],
            STATE,
        )
        assert cmd == BLUE
        assert list(words) == [
            Word(
                (
                    MixedBox(
                        (
                            (ga("bet", BLUE.apply(STATE), None), BIG),
                            (
                                ga("ter", multi(BIG, BLUE).apply(STATE), "b"),
                                NO_OP,
                            ),
                        ),
                        multi(BLUE, BIG).apply(STATE),
                    ),
                ),
                TrailingSpace(30, 0),
                multi(BLUE, BIG).apply(STATE),
            ),
            WithCmd(
                Word(
                    (
                        MixedBox(
                            (
                                (
                                    ga(
                                        "th",
                                        multi(BLUE, BIG).apply(STATE),
                                        " ",
                                    ),
                                    GREEN,
                                ),
                                (
                                    ga(
                                        "an",
                                        multi(GREEN, BIG).apply(STATE),
                                        "h",
                                    ),
                                    NO_OP,
                                ),
                            ),
                            multi(GREEN, BIG).apply(STATE),
                        ),
                    ),
                    TrailingSpace(30, 0),
                    multi(GREEN, BIG).apply(STATE),
                ),
                HUGE,
            ),
        ]

    def test_one_word_then_command(self):
        cmd, words = parse(
            [Passage(BLUE, "complex "), Passage(RED, "")], STATE
        )
        assert cmd == BLUE
        assert list(words) == [
            WithCmd(
                Word(
                    (
                        ga("com", BLUE.apply(STATE), None),
                        ga("plex", BLUE.apply(STATE), "m"),
                    ),
                    TrailingSpace(20, 0),
                    BLUE.apply(STATE),
                ),
                RED,
            )
        ]

    def test_separated_words(self):
        cmd, words = parse(
            [Passage(BLUE, "complicated. Flat is  better ")], STATE
        )
        assert cmd == BLUE
        assert list(words) == [
            Word(
                (
                    ga("com", BLUE.apply(STATE), None),
                    ga("pli", BLUE.apply(STATE), "m"),
                    ga("cat", BLUE.apply(STATE), "i"),
                    ga("ed.", BLUE.apply(STATE), "t"),
                ),
                TrailingSpace(approx(19.85), -15),
                BLUE.apply(STATE),
            ),
            Word(
                (ga("Flat", BLUE.apply(STATE), " "),),
                TrailingSpace(20, 0),
                BLUE.apply(STATE),
            ),
            Word(
                (ga("is ", BLUE.apply(STATE), " "),),
                TrailingSpace(20, 0),
                BLUE.apply(STATE),
            ),
            Word(
                (
                    ga("bet", BLUE.apply(STATE), " "),
                    ga("ter", BLUE.apply(STATE), "t"),
                ),
                TrailingSpace(20, 0),
                BLUE.apply(STATE),
            ),
        ]

    def test_last_word_has_no_break(self):
        cmd, words = parse([Passage(BLUE, "complicated.  Flat")], STATE)
        assert cmd == BLUE
        assert list(words) == [
            Word(
                (
                    ga("com", BLUE.apply(STATE), None),
                    ga("pli", BLUE.apply(STATE), "m"),
                    ga("cat", BLUE.apply(STATE), "i"),
                    ga("ed. ", BLUE.apply(STATE), "t"),
                ),
                TrailingSpace(20, 0),
                BLUE.apply(STATE),
            ),
            Word(
                (ga("Flat", BLUE.apply(STATE), " "),), None, BLUE.apply(STATE)
            ),
        ]

    def test_last_word_has_segments_but_no_break(self):
        cmd, words = parse(
            [Passage(BLUE, "complicated.  Fl"), Passage(RED, "at")], STATE
        )
        assert cmd == BLUE
        assert list(words) == [
            Word(
                (
                    ga("com", BLUE.apply(STATE), None),
                    ga("pli", BLUE.apply(STATE), "m"),
                    ga("cat", BLUE.apply(STATE), "i"),
                    ga("ed. ", BLUE.apply(STATE), "t"),
                ),
                TrailingSpace(20, 0),
                BLUE.apply(STATE),
            ),
            Word(
                (
                    MixedBox(
                        (
                            (ga("Fl", BLUE.apply(STATE), " "), RED),
                            (ga("at", RED.apply(STATE), "t"), NO_OP),
                        ),
                        RED.apply(STATE),
                    ),
                ),
                None,
                RED.apply(STATE),
            ),
        ]

    def test_final_passage_is_just_a_space(self):
        cmd, words = parse(
            [Passage(BLUE, "complicated. "), Passage(HUGE, " ")], STATE
        )
        assert cmd == BLUE
        assert list(words) == [
            WithCmd(
                Word(
                    (
                        ga("com", BLUE.apply(STATE), None),
                        ga("pli", BLUE.apply(STATE), "m"),
                        ga("cat", BLUE.apply(STATE), "i"),
                        ga("ed.", BLUE.apply(STATE), "t"),
                    ),
                    TrailingSpace(approx(19.85), -15),
                    BLUE.apply(STATE),
                ),
                HUGE,
            ),
            Word((), TrailingSpace(40, 0), multi(HUGE, BLUE).apply(STATE)),
        ]

    def test_words_traversing_passages(self):
        cmd, words = parse(
            [
                Passage(BLUE, "comp"),
                Passage(HUGE, "li"),
                Passage(RED, ""),
                Passage(GREEN, "ca"),
                Passage(BLUE, ""),
                Passage(BIG, "t"),
                Passage(SMALL, "ed."),
                Passage(NORMAL, " Flat "),
            ],
            STATE,
        )
        assert cmd == BLUE
        assert list(words) == [
            Word(
                (
                    MixedBox(
                        (
                            (ga("comp", BLUE.apply(STATE), None), HUGE),
                            (
                                ga("li", multi(HUGE, BLUE).apply(STATE), "m"),
                                GREEN,
                            ),
                            (
                                ga("ca", multi(GREEN, HUGE).apply(STATE), "i"),
                                Chain(eq_iter([BLUE, BIG])),
                            ),
                            (
                                ga("t", multi(BIG, BLUE).apply(STATE), None),
                                SMALL,
                            ),
                            (
                                ga(
                                    "ed.",
                                    multi(SMALL, BLUE).apply(STATE),
                                    None,
                                ),
                                NORMAL,
                            ),
                        ),
                        BLUE.apply(STATE),
                    ),
                ),
                TrailingSpace(approx(20), 0),
                BLUE.apply(STATE),
            ),
            Word(
                (ga("Flat", BLUE.apply(STATE), " "),),
                TrailingSpace(20, 0),
                BLUE.apply(STATE),
            ),
        ]


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
        word = Word.simple("complex. ", STATE, " ")
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
                MixedBox(
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
        # TODO: Atoms themselves streamable?
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
        word = WithCmd(Word.simple("complex. ", STATE, " "), HUGE)
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
    string = Slug.nonempty(s, st, prev)
    assert isinstance(string, Slug)
    return replace(string, width=approx(string.width)) if approx_ else string


ga = partial(g, approx_=True)
