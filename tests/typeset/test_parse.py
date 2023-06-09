from __future__ import annotations

from dataclasses import replace

from pdfje.common import Char
from pdfje.typeset.parse import into_words
from pdfje.typeset.state import NO_OP, Chain, Passage, State
from pdfje.typeset.words import MixedSlug, Slug, TrailingSpace, WithCmd, Word
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


class TestIntoWords:
    def test_empty(self):
        cmd, words = into_words([], STATE)
        assert cmd is NO_OP
        assert list(words) == []

    def test_only_commands(self):
        cmd, words = into_words([Passage(BLUE, ""), Passage(BIG, "")], STATE)
        assert cmd == Chain(eq_iter([BLUE, BIG]))
        assert list(words) == []

    def test_one_word(self):
        cmd, words = into_words([Passage(BLUE, "complex ")], STATE)
        assert cmd == BLUE
        assert list(words) == [
            Word(
                (
                    ga("com", BLUE.apply(STATE), None),
                    ga("plex", BLUE.apply(STATE), "m"),
                ),
                TrailingSpace(20, 0, STATE.size),
                BLUE.apply(STATE),
            )
        ]

    def test_words_separated_by_nonspace(self):
        cmd, words = into_words(
            [Passage(RED, "com"), Passage(BLUE, "plex-")], STATE
        )
        assert cmd == RED
        assert list(words) == [
            Word(
                (
                    MixedSlug(
                        (
                            (ga("com", RED.apply(STATE), None), BLUE),
                            (ga("plex-", BLUE.apply(STATE), "m"), NO_OP),
                        ),
                        BLUE.apply(STATE),
                    ),
                ),
                None,
                BLUE.apply(STATE),
            ),
        ]

    def test_one_space(self):
        cmd, words = into_words([Passage(BLUE, " ")], STATE)
        assert cmd == BLUE
        assert list(words) == [
            Word((), TrailingSpace(20, 0, STATE.size), BLUE.apply(STATE))
        ]

    def test_two_compound_words(self):
        cmd, words = into_words(
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
                    MixedSlug(
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
                TrailingSpace(30, 0, BIG.size),
                multi(BLUE, BIG).apply(STATE),
            ),
            WithCmd(
                Word(
                    (
                        MixedSlug(
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
                    TrailingSpace(30, 0, BIG.size),
                    multi(GREEN, BIG).apply(STATE),
                ),
                HUGE,
            ),
        ]

    def test_one_word_then_command(self):
        cmd, words = into_words(
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
                    TrailingSpace(20, 0, STATE.size),
                    BLUE.apply(STATE),
                ),
                RED,
            )
        ]

    def test_separated_words(self):
        cmd, words = into_words(
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
                TrailingSpace(20, -15, STATE.size),
                BLUE.apply(STATE),
            ),
            Word(
                (ga("Flat", BLUE.apply(STATE), " "),),
                TrailingSpace(20, 0, STATE.size),
                BLUE.apply(STATE),
            ),
            Word(
                (ga("is ", BLUE.apply(STATE), " "),),
                TrailingSpace(20, 0, STATE.size),
                BLUE.apply(STATE),
            ),
            Word(
                (
                    ga("bet", BLUE.apply(STATE), " "),
                    ga("ter", BLUE.apply(STATE), "t"),
                ),
                TrailingSpace(20, 0, STATE.size),
                BLUE.apply(STATE),
            ),
        ]

    def test_last_word_has_no_break(self):
        cmd, words = into_words([Passage(BLUE, "complicated.  Flat")], STATE)
        assert cmd == BLUE
        assert list(words) == [
            Word(
                (
                    ga("com", BLUE.apply(STATE), None),
                    ga("pli", BLUE.apply(STATE), "m"),
                    ga("cat", BLUE.apply(STATE), "i"),
                    ga("ed. ", BLUE.apply(STATE), "t"),
                ),
                TrailingSpace(20, 0, STATE.size),
                BLUE.apply(STATE),
            ),
            Word(
                (ga("Flat", BLUE.apply(STATE), " "),), None, BLUE.apply(STATE)
            ),
        ]

    def test_last_word_has_segments_but_no_break(self):
        cmd, words = into_words(
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
                TrailingSpace(20, 0, STATE.size),
                BLUE.apply(STATE),
            ),
            Word(
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
            ),
        ]

    def test_final_passage_is_just_a_space(self):
        cmd, words = into_words(
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
                    TrailingSpace(20, -15, STATE.size),
                    BLUE.apply(STATE),
                ),
                HUGE,
            ),
            Word(
                (),
                TrailingSpace(40, 0, HUGE.size),
                multi(HUGE, BLUE).apply(STATE),
            ),
        ]

    def test_words_traversing_passages(self):
        cmd, words = into_words(
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
                    MixedSlug(
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
                TrailingSpace(approx(20), 0, STATE.size),
                BLUE.apply(STATE),
            ),
            Word(
                (ga("Flat", BLUE.apply(STATE), " "),),
                TrailingSpace(20, 0, STATE.size),
                BLUE.apply(STATE),
            ),
        ]


def ga(
    s: str, st: State, prev: Char | None = None, approx_: bool = True
) -> Slug:
    """Helper to create a kerned string"""
    string = Slug.new(s, st, prev)
    assert isinstance(string, Slug)
    return replace(string, width=approx(string.width)) if approx_ else string
