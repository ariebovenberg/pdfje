from dataclasses import dataclass, field
from math import inf
from typing import Iterable
from unittest.mock import ANY

import pytest

from pdfje import RGB, helvetica, ops
from pdfje.atoms import LiteralString, Real
from pdfje.common import Char, Func, Pt, always, dictget, setattr_frozen
from pdfje.fonts.common import (
    TEXTSPACE_TO_GLYPHSPACE,
    Font,
    FontID,
    GlyphPt,
    Kern,
    KerningTable,
    kern,
)
from pdfje.ops import NO_OP, Chain, SetColor, SetFont, State, StateChange
from pdfje.typeset import (
    Cursor,
    Exhausted,
    GaugedString,
    Kerned,
    LimitReached,
    Line,
    MixedWord,
    Stretch,
    WrapDone,
    Wrapper,
    _encode_kerning,
    break_at_width,
    splitlines,
)

from .common import approx


class TestWrapperLine:
    def test_empty(self):
        w = Wrapper.start([], STATE)
        assert isinstance(w, WrapDone)
        assert w.state == STATE

    def test_one_empty_stretch(self):
        w = Wrapper.start([sp(RED, "")], STATE)
        assert isinstance(w, Wrapper)
        line, wnew = w.line(10_000)
        assert line == Line([], 10_000, STATE.lead)
        assert wnew == WrapDone(RED.apply(STATE))

    def test_one_word_stretch_fits(self):
        w = Wrapper.start([Stretch(BIG, "Complex")], STATE)
        assert isinstance(w, Wrapper)
        line, wnew = w.line(10_000)
        assert line == Line(
            [k("Complex", FONT_3)], approx(10_000 - 209.55), 18.75
        )
        assert wnew == WrapDone(BIG.apply(STATE))

    def test_one_word_stretch_doesnt_fit(self):
        w = Wrapper.start([Stretch(BLUE, "Complex")], STATE)
        assert isinstance(w, Wrapper)
        line, wnew = w.line(90)
        assert line == Line([k("Complex", FONT_3)], approx(90 - 139.7), 12.5)
        assert wnew == WrapDone(BLUE.apply(STATE))

    def test_one_stretch_fits(self):
        w = Wrapper.start([Stretch(SMALL, "Complex is better ")], STATE)
        assert isinstance(w, Wrapper)
        line, wnew = w.line(10_000)
        assert line == Line(
            [k("Complex is better", FONT_3)],
            approx(10_000 - 169.85),
            6.25,
        )
        assert wnew == WrapDone(SMALL.apply(STATE))

    def test_one_stretch_partial_fit(self):
        stretch = Stretch(BLUE, "Complex is better ")
        w = Wrapper.start([stretch], STATE)
        assert isinstance(w, Wrapper)
        line, wnew = w.line(200)
        assert line == Line([k("Complex is", FONT_3)], approx(0.3), 12.5)
        assert_wrapper_eq(
            wnew,
            Wrapper(EMPTY, Cursor(stretch.txt, 11), BLUE.apply(STATE), None),
        )

    def test_one_stretch_minimal_fit(self):
        stretch = Stretch(BLUE, "Complex is better ")
        w = Wrapper.start([stretch], STATE)
        assert isinstance(w, Wrapper)
        line, wnew = w.line(0.01)
        assert line == Line([k("Complex", FONT_3)], approx(-139.69), 12.5)
        assert_wrapper_eq(
            wnew,
            Wrapper(EMPTY, Cursor(stretch.txt, 8), BLUE.apply(STATE), None),
        )

    def test_one_stretch_with_trailing_that_fits(self):
        w = Wrapper.start(
            [Stretch(BLUE, "Complex  is better   than com")], STATE
        )
        assert isinstance(w, Wrapper)
        line, wnew = w.line(10_000)
        assert line == Line(
            [k("Complex  is better   than ", FONT_3), k("com", FONT_3, " ")],
            approx(10_000 - 579.55),
            12.5,
        )
        assert wnew == WrapDone(BLUE.apply(STATE))

    def test_one_stretch_with_trailing_that_doesnt_fit(self):
        stretch = Stretch(BLUE, "Complex  is better   than com")
        w = Wrapper.start([stretch], STATE)
        assert isinstance(w, Wrapper)
        line, wnew = w.line(540)
        assert line == Line(
            [k("Complex  is better   than", FONT_3)], approx(40.3), 12.5
        )
        assert_wrapper_eq(
            wnew,
            Wrapper(EMPTY, Cursor(stretch.txt, 26), BLUE.apply(STATE), None),
        )

    def test_one_stretch_with_trailing_partial_fit(self):
        stretch = Stretch(BLUE, "Complex  is better   than complicated")
        w = Wrapper.start([stretch], STATE)
        assert isinstance(w, Wrapper)
        line, wnew = w.line(450)
        assert line == Line(
            [k("Complex  is better  ", FONT_3)], approx(450 - 399.7), 12.5
        )
        assert_wrapper_eq(
            wnew,
            Wrapper(EMPTY, Cursor(stretch.txt, 21), BLUE.apply(STATE), None),
        )

    def test_multiple_stretches_exhausted_in_first_line(self):
        w = Wrapper.start(
            [
                Stretch(BLUE, "Complex  is "),
                Stretch(BIG, "better"),
                Stretch(GREEN, " than ...wait for it... com"),
                Stretch(RED, ""),
                Stretch(HUGE, ""),
                Stretch(SMALL, "plicated. Flat is be"),
                Stretch(GREEN, "tt"),
                Stretch(BLACK, ""),
                Stretch(RED, "er than  nested"),
                Stretch(BLUE, ""),
                Stretch(GREEN, ". "),
            ],
            STATE,
        )
        assert isinstance(w, Wrapper)
        expect_width = (
            width("Complex  is ", STATE, None)
            + width(
                "better than ...wait for it... com", BIG.apply(STATE), None
            )
            + width(
                "plicated. Flat is better than  nested.", SMALL.apply(STATE)
            )
        )
        # We can subtract a bit and the end due to trailing space
        line, wnew = w.line(expect_width + 0.01)
        assert line == Line(
            [
                k("Complex  is ", FONT_3),
                BIG,
                k("better", FONT_3, None),
                GREEN,
                k(" than ...wait for it... ", FONT_3, "r"),
                k("com", FONT_3, " "),
                RED,
                HUGE,
                SMALL,
                k("plicated. Flat is ", FONT_3, None),
                k("be", FONT_3, " "),
                GREEN,
                k("tt", FONT_3, "e"),
                BLACK,
                RED,
                k("er than  ", FONT_3, "t"),
                k("nested", FONT_3, " "),
                BLUE,
                GREEN,
                k(".", FONT_3, "d"),
            ],
            approx(0.01),
            BIG.apply(STATE).lead,
        )
        assert wnew == WrapDone(multi(SMALL, GREEN).apply(STATE))

    def test_multiple_stretches_exhausted_except_tail(self):
        w = Wrapper.start(
            [
                Stretch(BLUE, "Complex  is "),
                Stretch(BIG, "better"),
                Stretch(GREEN, " than ...wait for it... com"),
                Stretch(RED, ""),
                Stretch(SMALL, "plicated. Flat is be"),
                Stretch(GREEN, "tt"),
                Stretch(BLACK, ""),
                Stretch(RED, "er than  nested"),
                Stretch(BLUE, ""),
                Stretch(HUGE, ". "),
            ],
            STATE,
        )
        assert isinstance(w, Wrapper)
        width_expect = (
            width("Complex  is ", STATE, None)
            + width(
                "better than ...wait for it... com", BIG.apply(STATE), None
            )
            + width("plicated. Flat is better than ", SMALL.apply(STATE))
        )
        width_partial_tail = width_expect + width(
            " nested", SMALL.apply(STATE), " "
        )
        line, wnew = w.line(width_partial_tail + 0.01)
        assert line == Line(
            [
                k("Complex  is ", FONT_3),
                BIG,
                k("better", FONT_3, None),
                GREEN,
                k(" than ...wait for it... ", FONT_3, "r"),
                k("com", FONT_3, " "),
                RED,
                SMALL,
                k("plicated. Flat is ", FONT_3, None),
                k("be", FONT_3, " "),
                GREEN,
                k("tt", FONT_3, "e"),
                BLACK,
                RED,
                k("er than ", FONT_3, "t"),
            ],
            approx(width_partial_tail - width_expect + 0.01),
            BIG.apply(STATE).lead,
        )
        assert_wrapper_eq(
            wnew,
            Wrapper(
                EMPTY,
                Cursor(". ", 0),
                multi(RED, SMALL).apply(STATE),
                MixedWord(
                    GaugedString.build("nested", SMALL.apply(STATE), None),
                    [BLUE, HUGE],
                    None,
                    width("nested", SMALL.apply(STATE), None),
                    HUGE.apply(STATE).lead,
                    multi(HUGE, BLUE).apply(STATE),
                ),
            ),
        )

    def test_continue_pending_with_multiple_streches(self):
        w = Wrapper(
            iter(
                [Stretch(BIG, "better"), Stretch(RED, " than complicated. ")]
            ),
            Cursor("(ignored)  is ", 9),
            STATE,
            MixedWord(
                GaugedString.build("Com", STATE, None),
                [
                    HUGE,
                    GaugedString.build("pl", HUGE.apply(STATE), "m"),
                    NORMAL,
                    GaugedString.build(
                        "ex", multi(HUGE, GREEN).apply(STATE), "l"
                    ),
                    GREEN,
                ],
                "x",
                210,
                HUGE.apply(STATE).lead,
                GREEN.apply(STATE),
            ),
        )
        width_expect = (
            210
            + width("  is ", STATE, "x")
            + width("better than complicated.", BIG.apply(STATE), " ")
        )
        line, wnew = w.line(width_expect + 0.01)
        assert line == Line(
            [
                k("Com", FONT_3, None),
                HUGE,
                k("pl", FONT_3, "m"),
                NORMAL,
                k("ex", FONT_3, "l"),
                GREEN,
                k("  is ", FONT_3, "x"),
                BIG,
                k("better", FONT_3, "x"),
                RED,
                k(" than complicated.", FONT_3, "x"),
            ],
            approx(0.01),
            HUGE.apply(STATE).lead,
        )
        assert wnew == WrapDone(multi(BIG, RED).apply(STATE))

    def test_continue_pending_with_single_strech(self):
        w = Wrapper(
            EMPTY,
            Cursor(
                "  is better than complicated. " "Flat is better than nested.",
                0,
            ),
            STATE,
            MixedWord(
                GaugedString.build("Com", STATE, None),
                [
                    HUGE,
                    GaugedString.build("pl", HUGE.apply(STATE), "m"),
                    NORMAL,
                    GaugedString.build(
                        "ex", multi(HUGE, GREEN).apply(STATE), "l"
                    ),
                    GREEN,
                ],
                "x",
                210,
                HUGE.apply(STATE).lead,
                GREEN.apply(STATE),
            ),
        )
        width_expect = 210 + width(
            "  is better than complicated. Flat is better than",
            STATE,
            "x",
        )
        line, wnew = w.line(width_expect + 40)
        assert line == Line(
            [
                k("Com", FONT_3, None),
                HUGE,
                k("pl", FONT_3, "m"),
                NORMAL,
                k("ex", FONT_3, "l"),
                GREEN,
                k(
                    "  is better than complicated. " "Flat is better than",
                    FONT_3,
                    "x",
                ),
            ],
            approx(40),
            HUGE.apply(STATE).lead,
        )
        assert_wrapper_eq(
            wnew,
            Wrapper(
                EMPTY,
                Cursor(
                    "  is better than complicated. "
                    "Flat is better than nested.",
                    50,
                ),
                multi(NORMAL, GREEN).apply(STATE),
                None,
            ),
        )

    def test_continue_pending_with_single_stretch_no_space(self):
        w = Wrapper(
            EMPTY,
            Cursor("_is better than complicated. ", 0),
            STATE,
            MixedWord(
                GaugedString.build("Com", STATE, None),
                [
                    HUGE,
                    GaugedString.build("pl", HUGE.apply(STATE), "m"),
                    NORMAL,
                    GaugedString.build(
                        "ex", multi(HUGE, GREEN).apply(STATE), "l"
                    ),
                    GREEN,
                ],
                "x",
                210,
                HUGE.apply(STATE).lead,
                GREEN.apply(STATE),
            ),
        )
        line, wnew = w.line(0.01)
        assert line == Line(
            [
                k("Com", FONT_3, None),
                HUGE,
                k("pl", FONT_3, "m"),
                NORMAL,
                k("ex", FONT_3, "l"),
                GREEN,
                k("_is", FONT_3, "x"),
            ],
            ANY,
            HUGE.apply(STATE).lead,
        )
        assert_wrapper_eq(
            wnew,
            Wrapper(
                EMPTY,
                Cursor("_is better than complicated. ", 4),
                multi(NORMAL, GREEN).apply(STATE),
                None,
            ),
        )

    def test_continue_pending_with_single_space(self):
        w = Wrapper(
            EMPTY,
            Cursor(" is better than complicated. ", 0),
            STATE,
            MixedWord(
                GaugedString.build("Com", STATE, None),
                [
                    HUGE,
                    GaugedString.build("pl", HUGE.apply(STATE), "m"),
                    NORMAL,
                    GaugedString.build(
                        "ex", multi(HUGE, GREEN).apply(STATE), "l"
                    ),
                    GREEN,
                ],
                "x",
                210,
                HUGE.apply(STATE).lead,
                GREEN.apply(STATE),
            ),
        )
        line, wnew = w.line(0.01)
        assert line == Line(
            [
                k("Com", FONT_3, None),
                HUGE,
                k("pl", FONT_3, "m"),
                NORMAL,
                k("ex", FONT_3, "l"),
                GREEN,
            ],
            0.01 - 210,
            HUGE.apply(STATE).lead,
        )
        assert_wrapper_eq(
            wnew,
            Wrapper(
                EMPTY,
                Cursor(" is better than complicated. ", 1),
                multi(NORMAL, GREEN).apply(STATE),
                None,
            ),
        )


class TestMixedWord:
    def test_without_init_kern(self):
        m = MixedWord(
            GaugedString.build("Comp", STATE, " "),
            [HUGE, GaugedString.build("lex", HUGE.apply(STATE), "p")],
            "x",
            210,
            HUGE.apply(STATE).lead,
            HUGE.apply(STATE),
        )
        assert m.head.txt.kerning[0] == (0, -15)
        m_without = m.without_init_kern()
        assert m_without.head.txt.kerning == m.head.txt.kerning[1:]
        assert m_without.width == approx(m.width + 0.15)
        assert m_without.without_init_kern() == m_without

        m_no_kern = MixedWord(
            GaugedString.build("Fo", STATE, " "),
            [HUGE, GaugedString.build("o", HUGE.apply(STATE), "o")],
            "o",
            210,
            HUGE.apply(STATE).lead,
            HUGE.apply(STATE),
        )
        assert m_no_kern.without_init_kern() == m_no_kern


class TestWrapperFill:
    def test_long_low_frame(self):
        w = Wrapper.start(STRETCHES, STATE)
        assert isinstance(w, Wrapper)
        assert w.state == RED.apply(STATE)

        section, w_new = w.fill(10_000, 0.1, allow_empty=True)
        assert section.lines == []
        assert section.height_left == approx(0.1)
        assert_wrapper_eq(w, w_new)

        section, w_new = w.fill(10_000, 0.1, allow_empty=False)
        assert section.lines == [
            Line(
                [
                    k(STRETCHES[0].txt, FONT_3),
                    BIG,
                    k(STRETCHES[1].txt, FONT_3, " "),
                    NORMAL,
                    k(STRETCHES[2].txt[:-1], FONT_3, "e"),
                ],
                ANY,
                BIG.apply(STATE).lead,
            )
        ]
        assert section.height_left == approx(0.1 - BIG.apply(STATE).lead)
        assert w_new == WrapDone(w.state)

    def test_narrow_tall_frame(self):
        w = Wrapper.start(STRETCHES, STATE)
        assert isinstance(w, Wrapper)
        assert w.state == RED.apply(STATE)
        section, w_new = w.fill(0.1, 10_000, allow_empty=False)
        assert w.fill(0.1, 10_000, allow_empty=True) == (section, w_new)
        assert len(section.lines) == 15
        assert section.height_left == approx(
            10_000 - (14 * STATE.lead + BIG.apply(STATE).lead)
        )
        assert w_new == WrapDone(w.state)

    def test_narrow_low_frame(self):
        w = Wrapper.start(STRETCHES, STATE)
        assert isinstance(w, Wrapper)
        assert w.state == RED.apply(STATE)
        section, w_new = w.fill(0.1, 0.1, allow_empty=False)
        assert section.lines == [
            Line([k("Beautiful", FONT_3)], ANY, STATE.lead)
        ]
        assert section.height_left == approx(0.1 - STATE.lead)
        assert_wrapper_eq(
            w_new,
            Wrapper(
                iter(STRETCHES[1:]),
                Cursor(STRETCHES[0].txt, 10),
                RED.apply(STATE),
                None,
            ),
        )

    def test_tall_frame(self):
        w = Wrapper.start(STRETCHES, STATE)
        assert isinstance(w, Wrapper)
        assert w.state == RED.apply(STATE)
        section, w_new = w.fill(500, 10_000, allow_empty=True)
        assert len(section.lines) == 4
        assert section.height_left == approx(
            10_000 - (3 * STATE.lead + BIG.apply(STATE).lead)
        )
        assert w_new == WrapDone(multi(NORMAL, RED).apply(STATE))

    def test_medium_frame(self):
        w = Wrapper.start(STRETCHES, STATE)
        assert isinstance(w, Wrapper)
        assert w.state == RED.apply(STATE)
        section, w_new = w.fill(500, 50, allow_empty=True)
        assert len(section.lines) == 3
        assert section.height_left == approx(
            50 - (2 * STATE.lead + BIG.apply(STATE).lead)
        )
        assert isinstance(w_new, Wrapper)
        assert_wrapper_eq(
            w_new,
            Wrapper(
                EMPTY, Cursor(STRETCHES[2].txt, 1), RED.apply(STATE), None
            ),
        )
        section, w_new = w_new.fill(300, 100, allow_empty=True)
        assert len(section.lines) == 2
        assert section.height_left == approx(100 - 2 * STATE.lead)

    def test_infinite_frame(self):
        w = Wrapper.start(STRETCHES, STATE)
        assert isinstance(w, Wrapper)
        assert w.state == RED.apply(STATE)
        section, done = w.fill(inf, inf, allow_empty=True)
        [line] = section.lines
        assert line.lead == 18.75
        assert len(line.segments) == 5
        assert section.height_left == inf
        assert isinstance(done, WrapDone)
        assert done.state == RED.apply(STATE)


class TestBreakAtWidth:
    def test_empty(self):
        assert break_at_width("", STATE, 0.01, False, 0, None) == Exhausted(
            None, None
        )
        assert break_at_width("", STATE, 0.01, True, 0, None) == Exhausted(
            None, None
        )

    def test_word(self):
        gauged = GaugedString.build("complex", STATE, None)
        assert break_at_width(
            "complex", STATE, gauged.width + 0.01, False, 0, None
        ) == Exhausted(None, gauged)
        assert break_at_width(
            "complex", STATE, gauged.width + 0.01, True, 0, None
        ) == Exhausted(None, gauged)
        assert break_at_width(
            "complex", STATE, gauged.width - 0.01, False, 0, None
        ) == Exhausted(None, gauged)
        assert break_at_width(
            "complex", STATE, gauged.width - 0.01, True, 0, None
        ) == LimitReached(None, 0)

    def test_word_with_initial_kern(self):
        gauged = GaugedString.build("complex", STATE, " ")
        assert break_at_width(
            "complex", STATE, gauged.width + 0.01, False, 0, " "
        ) == Exhausted(None, gauged)
        assert break_at_width(
            "complex", STATE, gauged.width + 0.01, True, 0, " "
        ) == Exhausted(None, gauged)
        assert break_at_width(
            "complex", STATE, gauged.width - 0.01, False, 0, " "
        ) == Exhausted(None, gauged)
        assert break_at_width(
            "complex", STATE, gauged.width - 0.01, True, 0, " "
        ) == LimitReached(None, 0)

    def test_word_with_break(self):
        gauged = GaugedString.build("complex.  ", STATE, None)
        w = width("complex. ", STATE, None)
        assert break_at_width(
            "complex.  ", STATE, w + 0.01, False, 0, None
        ) == Exhausted(gauged, None)
        assert break_at_width(
            "complex.  ", STATE, w + 0.01, True, 0, None
        ) == Exhausted(gauged, None)
        assert break_at_width(
            "complex.  ", STATE, w - 0.01, False, 0, None
        ) == Exhausted(gauged, None)
        assert break_at_width(
            "complex.  ", STATE, w - 0.01, True, 0, None
        ) == LimitReached(None, 0)

    def test_word_with_break_and_kerning_around_edges(self):
        gauged = GaugedString.build("complex. ", STATE, " ")
        w = width("complex.", STATE, " ")
        assert break_at_width(
            "complex. ", STATE, w + 0.01, False, 0, " "
        ) == Exhausted(gauged, None)
        assert break_at_width(
            "complex. ", STATE, w + 0.01, True, 0, " "
        ) == Exhausted(gauged, None)
        assert break_at_width(
            "complex. ", STATE, w - 0.01, False, 0, " "
        ) == Exhausted(gauged, None)
        assert break_at_width(
            "complex. ", STATE, w - 0.01, True, 0, " "
        ) == LimitReached(None, 0)

    @pytest.mark.parametrize("allow_empty", [True, False])
    def test_sentence_fits(self, allow_empty):
        gauged = GaugedString.build("better  than complex. ", STATE, None)
        w = width("better  than complex.", STATE, None)
        assert break_at_width(
            "better  than complex. ", STATE, w + 0.01, allow_empty, 0, None
        ) == Exhausted(gauged, None)

    def test_sentence_first_word_too_wide(self):
        assert break_at_width(
            "better  than complex.  ", STATE, 139, False, 0, None
        ) == LimitReached(GaugedString.build("better ", STATE, None), 8)
        assert break_at_width(
            "better  than complex.  ", STATE, 139, True, 0, None
        ) == LimitReached(None, 0)

    @pytest.mark.parametrize("allow_empty", [True, False])
    def test_sentence_partial_fit(self, allow_empty):
        assert break_at_width(
            "better  than complex.  ", STATE, 300, allow_empty, 0, None
        ) == LimitReached(GaugedString.build("better  than", STATE, None), 13)

    @pytest.mark.parametrize("allow_empty", [True, False])
    def test_sentence_with_tail_fits(self, allow_empty):
        assert break_at_width(
            "better  than complex. Compl", STATE, 10_000, allow_empty, 0, None
        ) == Exhausted(
            GaugedString.build("better  than complex. ", STATE, None),
            GaugedString.build("Compl", STATE, " "),
        )

    @pytest.mark.parametrize("allow_empty", [True, False])
    def test_sentence_tail_doesnt_fit(self, allow_empty):
        assert break_at_width(
            "better  than complex.  Compl", STATE, 500, allow_empty, 0, None
        ) == LimitReached(
            GaugedString.build("better  than complex. ", STATE, None), 23
        )

    def test_start_from(self):
        assert break_at_width(
            "Simple is better than complex", STATE, 10_000, False, 22, None
        ) == Exhausted(None, GaugedString.build("complex", STATE, None))

        assert break_at_width(
            "Simple is  better  than complex.  Compl",
            STATE,
            500,
            False,
            11,
            None,
        ) == LimitReached(
            GaugedString.build("better  than complex. ", STATE, None), 34
        )


class TestSplitlines:
    def test_empty(self):
        result = splitlines(iter([]))
        assert next(result, None) is None

    def test_no_breaks(self):
        result = splitlines(
            iter(
                [
                    Stretch(RED, "Beautiful "),
                    Stretch(BLUE, "is better "),
                    Stretch(GREEN, "than ugly."),
                ]
            )
        )
        assert list(next(result)) == [
            Stretch(RED, "Beautiful "),
            Stretch(BLUE, "is better "),
            Stretch(GREEN, "than ugly."),
        ]

    def test_breaks(self):
        result = splitlines(
            iter(
                [
                    Stretch(RED, "Beautiful "),
                    Stretch(BLUE, "is better "),
                    Stretch(GREEN, "than\nugly.\r\n\n"),
                    Stretch(RED, "Explicit is "),
                    Stretch(BIG, "better than \nimplicit. \n"),
                ]
            )
        )
        assert list(next(result)) == [
            Stretch(RED, "Beautiful "),
            Stretch(BLUE, "is better "),
            Stretch(GREEN, "than"),
        ]
        assert list(next(result)) == [Stretch(NO_OP, "ugly.")]
        assert list(next(result)) == [Stretch(NO_OP, "")]
        assert list(next(result)) == [
            Stretch(NO_OP, ""),
            Stretch(RED, "Explicit is "),
            Stretch(BIG, "better than "),
        ]
        assert list(next(result)) == [Stretch(NO_OP, "implicit. ")]
        assert list(next(result)) == [Stretch(NO_OP, "")]


class TestEncodeKerning:
    def test_typical(self):
        assert list(
            _encode_kerning(b"abcdefg", [(1, -20), (2, -30), (6, -40)])
        ) == [
            LiteralString(b"a"),
            Real(20),
            LiteralString(b"b"),
            Real(30),
            LiteralString(b"cdef"),
            Real(40),
            LiteralString(b"g"),
        ]

    def test_kern_first_char(self):
        assert list(_encode_kerning(b"abcdefg", [(0, -20), (2, -30)])) == [
            Real(20),
            LiteralString(b"ab"),
            Real(30),
            LiteralString(b"cdefg"),
        ]


@dataclass(frozen=True, repr=False)
class DummyFont(Font):
    """Helper to create dummy fonts with easily testable metrics"""

    id: FontID
    charwidth: Func[Char, GlyphPt]
    kerning: KerningTable | None = None
    spacewidth: GlyphPt = field(init=False)

    encoding_width = 1

    def __post_init__(self) -> None:
        setattr_frozen(self, "spacewidth", self.charwidth(" "))

    def __repr__(self) -> str:
        return f"DummyFont({self.id.decode()})"

    def width(self, s: str, /) -> Pt:
        return sum(map(self.charwidth, s)) / TEXTSPACE_TO_GLYPHSPACE

    def kern(
        self, s: str, /, prev: Char | None, offset: int
    ) -> Iterable[Kern]:
        return kern(self.kerning, s, 1, prev, offset) if self.kerning else ()

    def encode(self, s: str, /) -> bytes:
        return s.encode("latin-1")


def multi(*args: StateChange) -> StateChange:
    return Chain(args)


FONT_3 = DummyFont(
    b"Dummy3",
    always(2000),
    dictget(
        {
            ("o", "w"): -25,
            ("e", "v"): -30,
            ("v", "e"): -30,
            (" ", "N"): -10,
            ("r", "."): -40,
            (" ", "n"): -5,
            ("w", " "): -10,
            ("m", "p"): -10,
            (" ", "C"): -15,
            ("e", "x"): -20,
            ("d", "."): -5,
            ("i", "c"): -10,
            (".", " "): -15,
            (" ", "c"): -15,
        },
        0,
    ),
)


def mkstate(
    font: Font = helvetica.regular,
    size: int = 12,
    color: tuple[float, float, float] = (0, 0, 0),
    line_spacing: float = 1.25,
) -> ops.State:
    """factory to easily create a State"""
    return ops.State(font, size, RGB(*color), line_spacing)


STATE = mkstate(FONT_3, 10)

RED = SetColor(RGB(1, 0, 0))
GREEN = SetColor(RGB(0, 1, 0))
BLUE = SetColor(RGB(0, 0, 1))
BLACK = SetColor(RGB(0, 0, 0))

HUGE = SetFont(FONT_3, 20)
BIG = SetFont(FONT_3, 15)
NORMAL = SetFont(FONT_3, 10)
SMALL = SetFont(FONT_3, 5)

EMPTY = iter(())

STRETCHES = [
    Stretch(
        RED,
        "Beautiful is better than ugly. Explicit is better than implicit. ",
    ),
    Stretch(BIG, "Simple"),
    Stretch(NORMAL, " is better than complex. "),
]


def assert_wrapper_eq(a: Wrapper | WrapDone, b: Wrapper | WrapDone):
    if type(a) is Wrapper and type(b) is Wrapper:
        assert list(a._branch_queue()) == list(b._branch_queue())
        assert a.cursor == b.cursor
        assert a.state == b.state
        if a.pending and b.pending:
            assert a.pending.head.txt == b.pending.head.txt
            assert list(a.pending.tail) == list(b.pending.tail)
            assert a.pending.last == b.pending.last
            assert approx(a.pending.width) == approx(b.pending.width)
            assert a.pending.state == b.pending.state
        else:
            assert a.pending == b.pending
    else:
        assert a == b


def k(s: str, f: Font, prev: Char | None = None) -> Kerned:
    """Helper to create a kerned string"""
    return Kerned(f.encode(s), list(f.kern(s, prev, 0)))


def sp(cmd: StateChange, s: str) -> Stretch:
    return Stretch(cmd, s)


def width(s: str, state: State, prev: Char | None = None) -> Pt:
    return GaugedString.build(s, state, prev).width
