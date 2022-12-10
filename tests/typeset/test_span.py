from typing import TYPE_CHECKING

import pytest

from pdfje import RGB
from pdfje.common import Char, Pt
from pdfje.fonts.common import Font
from pdfje.ops import SetColor, SetFont, State
from pdfje.typeset.span import (
    Cursor,
    Exhausted,
    GaugedString,
    Kerned,
    LimitReached,
    Line,
    MixedWord,
    Span,
    WrapDone,
    Wrapper,
    break_at_width,
)

from .common import FONT_3, mkstate

if TYPE_CHECKING:
    approx = float.__call__
else:
    from pytest import approx

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


def assert_wrapper_eq(a: Wrapper | WrapDone, b: Wrapper | WrapDone):
    if type(a) is Wrapper and type(b) is Wrapper:
        assert list(a._branched_span_iterator()) == list(
            b._branched_span_iterator()
        )
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
    return Kerned(f.encode(s), list(f.kern(s, prev, 0)))


def width(s: str, state: State, prev: Char | None = None) -> Pt:
    return GaugedString.build(s, state, prev).width


class TestWrapper:
    def test_one_empty_span(self):
        w = Wrapper.start([Span(RED, "")], STATE)
        assert isinstance(w, Wrapper)
        line, wnew = w.line(10_000)
        assert line == Line([], 10_000, 12.5)
        assert wnew == WrapDone(RED.apply(STATE))

    def test_one_word_span_fits(self):
        w = Wrapper.start([Span(BIG, "Complex")], STATE)
        assert isinstance(w, Wrapper)
        line, wnew = w.line(10_000)
        assert line == Line(
            [k("Complex", FONT_3)], approx(10_000 - 209.55), 18.75
        )
        assert wnew == WrapDone(BIG.apply(STATE))

    def test_one_word_span_doesnt_fit(self):
        w = Wrapper.start([Span(BLUE, "Complex")], STATE)
        assert isinstance(w, Wrapper)
        line, wnew = w.line(90)
        assert line == Line([k("Complex", FONT_3)], approx(90 - 139.7), 12.5)
        assert wnew == WrapDone(BLUE.apply(STATE))

    def test_one_span_fits(self):
        w = Wrapper.start([Span(SMALL, "Complex is better ")], STATE)
        assert isinstance(w, Wrapper)
        line, wnew = w.line(10_000)
        assert line == Line(
            [k("Complex is better ", FONT_3)],
            approx(10_000 - 179.85),
            6.25,
        )
        assert wnew == WrapDone(SMALL.apply(STATE))

    def test_one_span_partial_fit(self):
        span = Span(BLUE, "Complex is better ")
        w = Wrapper.start([span], STATE)
        assert isinstance(w, Wrapper)
        line, wnew = w.line(200)
        assert line == Line([k("Complex is", FONT_3)], approx(0.3), 12.5)
        assert_wrapper_eq(
            wnew,
            Wrapper(EMPTY, Cursor(span.txt, 11), BLUE.apply(STATE), None),
        )

    def test_one_span_minimal_fit(self):
        span = Span(BLUE, "Complex is better ")
        w = Wrapper.start([span], STATE)
        assert isinstance(w, Wrapper)
        line, wnew = w.line(0.01)
        assert line == Line([k("Complex", FONT_3)], approx(-139.69), 12.5)
        assert_wrapper_eq(
            wnew,
            Wrapper(EMPTY, Cursor(span.txt, 8), BLUE.apply(STATE), None),
        )

    def test_one_span_with_trailing_that_fits(self):
        w = Wrapper.start([Span(BLUE, "Complex  is better   than com")], STATE)
        assert isinstance(w, Wrapper)
        line, wnew = w.line(10_000)
        assert line == Line(
            [k("Complex  is better   than ", FONT_3), k("com", FONT_3, " ")],
            approx(10_000 - 579.55),
            12.5,
        )
        assert wnew == WrapDone(BLUE.apply(STATE))

    def test_one_span_with_trailing_that_doesnt_fit(self):
        span = Span(BLUE, "Complex  is better   than com")
        w = Wrapper.start([span], STATE)
        assert isinstance(w, Wrapper)
        line, wnew = w.line(540)
        assert line == Line(
            [k("Complex  is better   than", FONT_3)], approx(40.3), 12.5
        )
        assert_wrapper_eq(
            wnew,
            Wrapper(EMPTY, Cursor(span.txt, 26), BLUE.apply(STATE), None),
        )

    def test_one_span_with_trailing_partial_fit(self):
        span = Span(BLUE, "Complex  is better   than complicated")
        w = Wrapper.start([span], STATE)
        assert isinstance(w, Wrapper)
        line, wnew = w.line(450)
        assert line == Line(
            [k("Complex  is better  ", FONT_3)], approx(450 - 399.7), 12.5
        )
        assert_wrapper_eq(
            wnew,
            Wrapper(EMPTY, Cursor(span.txt, 21), BLUE.apply(STATE), None),
        )

    def test_multiple_spans_exhausted_in_first_line(self):
        w = Wrapper.start(
            [
                Span(BLUE, "Complex  is "),
                Span(BIG, "better"),
                Span(GREEN, " than ...wait for it... com"),
                Span(RED, ""),
                Span(HUGE, ""),
                Span(SMALL, "plicated. Flat is be"),
                Span(GREEN, "tt"),
                Span(BLACK, ""),
                Span(RED, "er than  nested"),
                Span(BLUE, ""),
                Span(GREEN, ". "),
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
                "plicated. Flat is better than  nested. ", SMALL.apply(STATE)
            )
        )
        # We can subtract a bit and the end due to trailing space
        line, wnew = w.line(expect_width + 0.01 - 5)
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
                k(". ", FONT_3, "d"),
            ],
            approx(0.01 - 5),
            BIG.apply(STATE).leading(),
        )
        assert wnew == WrapDone((SMALL + GREEN).apply(STATE))

    def test_multiple_spans_exhausted_except_tail(self):
        w = Wrapper.start(
            [
                Span(BLUE, "Complex  is "),
                Span(BIG, "better"),
                Span(GREEN, " than ...wait for it... com"),
                Span(RED, ""),
                Span(SMALL, "plicated. Flat is be"),
                Span(GREEN, "tt"),
                Span(BLACK, ""),
                Span(RED, "er than  nested"),
                Span(BLUE, ""),
                Span(HUGE, ". "),
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
            BIG.apply(STATE).leading(),
        )
        assert_wrapper_eq(
            wnew,
            Wrapper(
                EMPTY,
                Cursor(". ", 0),
                (RED + SMALL).apply(STATE),
                MixedWord(
                    GaugedString.build("nested", SMALL.apply(STATE), None),
                    [BLUE, HUGE],
                    None,
                    width("nested", SMALL.apply(STATE), None),
                    HUGE.apply(STATE).leading(),
                    (HUGE + BLUE).apply(STATE),
                ),
            ),
        )

    def test_continue_pending_with_multiple_spans(self):
        w = Wrapper(
            iter([Span(BIG, "better"), Span(RED, " than complicated. ")]),
            Cursor("(ignored)  is ", 9),
            STATE,
            MixedWord(
                GaugedString.build("Com", STATE, None),
                [
                    HUGE,
                    GaugedString.build("pl", HUGE.apply(STATE), "m"),
                    NORMAL,
                    GaugedString.build("ex", (HUGE + GREEN).apply(STATE), "l"),
                    GREEN,
                ],
                "x",
                210,
                HUGE.apply(STATE).leading(),
                GREEN.apply(STATE),
            ),
        )
        width_expect = (
            210
            + width("  is ", STATE, "x")
            + width("better than complicated. ", BIG.apply(STATE), " ")
        )
        line, wnew = w.line(width_expect + 0.01 - 5)
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
                k(" than complicated. ", FONT_3, "x"),
            ],
            approx(0.01 - 5),
            HUGE.apply(STATE).leading(),
        )
        assert wnew == WrapDone((BIG + RED).apply(STATE))

    def test_continue_pending_with_single_span(self):
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
                    GaugedString.build("ex", (HUGE + GREEN).apply(STATE), "l"),
                    GREEN,
                ],
                "x",
                210,
                HUGE.apply(STATE).leading(),
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
            HUGE.apply(STATE).leading(),
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
                (NORMAL + GREEN).apply(STATE),
                None,
            ),
        )


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
        assert (
            break_at_width(
                "complex", STATE, gauged.width - 0.01, True, 0, None
            )
            is None
        )

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
        assert (
            break_at_width("complex", STATE, gauged.width - 0.01, True, 0, " ")
            is None
        )

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
        assert (
            break_at_width("complex.  ", STATE, w - 0.01, True, 0, None)
            is None
        )

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
        assert (
            break_at_width("complex. ", STATE, w - 0.01, True, 0, " ") is None
        )

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
        assert (
            break_at_width(
                "better  than complex.  ", STATE, 139, True, 0, None
            )
            is None
        )

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
