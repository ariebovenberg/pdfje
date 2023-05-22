from __future__ import annotations

from typing import Iterable

from pdfje.common import BranchableIterator, Pt
from pdfje.typeset.common import Slug, State, Stretch
from pdfje.typeset.lines import Line, WrapDone, Wrapper
from pdfje.typeset.words import WithCmd, Word, parse
from pdfje.vendor.hyphenate import hyphenate_word

from ..common import (
    BIG,
    BLACK,
    BLUE,
    FONT,
    HUGE,
    NORMAL,
    RED,
    SMALL,
    approx,
    mkstate,
    multi,
)

STATE = mkstate(FONT, 10, hyphens=hyphenate_word)


def mkwrapper(
    words: Iterable[Word | WithCmd], s: State, lead: Pt | None = None
) -> Wrapper:
    return Wrapper(BranchableIterator(words), s, lead or s.lead)


def _assert_word_eq(a: Word, b: Word) -> None:
    assert len(a.boxes) == len(b.boxes)
    for box_a, box_b in zip(a.boxes, b.boxes):
        if type(box_a) is not type(box_b):
            assert box_a == box_b

        if isinstance(box_a, Slug) and isinstance(box_b, Slug):
            assert box_a.txt == box_b.txt
            assert box_a.kern == box_b.kern
            assert box_a.width == approx(box_b.width)
            assert box_a.state == box_b.state


def assert_word_eq(a: Word | WithCmd | None, b: Word | WithCmd | None) -> None:
    if isinstance(a, WithCmd) and isinstance(b, WithCmd):
        assert a.cmd == b.cmd
        _assert_word_eq(a.word, b.word)
    elif isinstance(a, Word) and isinstance(b, Word):
        _assert_word_eq(a, b)
    else:
        assert a == b


def assert_wrapper_eq(a: Wrapper | WrapDone, b: Wrapper | WrapDone) -> None:
    if type(a) is Wrapper and type(b) is Wrapper:
        words_a = list(a.queue.branch())
        words_b = list(b.queue.branch())
        assert len(words_a) == len(words_b)
        for word_a, word_b in zip(words_a, words_b):
            assert_word_eq(word_a, word_b)
        assert a.state == b.state
    else:
        assert a == b


class TestWrapLine:
    def test_empty(self):
        line, w = mkwrapper([], STATE).line(100)
        assert line == Line((), 0, 0)
        assert w == WrapDone(STATE)

    def test_one_word_and_enough_space(self):
        word = Word.simple("complex ", STATE, None)
        line, w = mkwrapper([word], STATE).line(10_000)
        assert line == Line((word,), approx(word.width()), 0)
        assert w == WrapDone(STATE)

    def test_one_word_and_barely_enough_space(self):
        word = Word.simple("complex ", STATE, None)
        line, w = mkwrapper([word], STATE).line(word.pruned().width() + 0.01)
        assert line == Line(
            (word,),
            approx(word.width()),
            0,
        )
        assert w == WrapDone(STATE)

    def test_one_word_and_just_too_little_space(self):
        word = Word.simple("complex ", STATE, None)
        cutoff = word.pruned().width() - 0.01
        line, w = mkwrapper([word], STATE).line(cutoff)
        assert line == Line(
            (partial := Word.simple("com-", STATE, None),),
            approx(partial.width()),
            cutoff - partial.width(),
        )
        assert_wrapper_eq(
            w,
            Wrapper(
                BranchableIterator([Word.simple("plex ", STATE, None)]),
                STATE,
                STATE.lead,
            ),
        )

    def test_one_word_and_very_little_space(self):
        word = Word.simple("complex ", STATE, None)
        line, w = mkwrapper([word], STATE).line(0.01)
        assert line == Line(
            (partial := Word.simple("com-", STATE, None),),
            approx(partial.width()),
            0.01 - partial.width(),
        )
        assert_wrapper_eq(
            w,
            Wrapper(
                BranchableIterator([Word.simple("plex ", STATE, None)]),
                STATE,
                STATE.lead,
            ),
        )

    def test_enough_space(self):
        words: tuple[Word | WithCmd, ...] = (
            Word.simple("complex ", STATE, None),
            Word.simple("is  ", STATE, " "),
            WithCmd(Word.simple("better ", STATE, " "), BLUE),
            Word.simple("than ", BLUE.apply(STATE), " "),
            Word.simple("complicated. ", BLUE.apply(STATE), " "),
        )
        line, w = mkwrapper(words, STATE).line(10_000)
        assert line == Line(
            words,
            approx(sum(w.width() for w in words)),
            0,
        )
        assert w == WrapDone(BLUE.apply(STATE))

    def test_barely_enough_space(self):
        words: tuple[Word | WithCmd, ...] = (
            Word.simple("complex ", STATE, None),
            Word.simple("is  ", STATE, " "),
            WithCmd(Word.simple("better ", STATE, " "), BLUE),
            Word.simple("than ", BLUE.apply(STATE), " "),
            Word.simple("complicated. ", BLUE.apply(STATE), " "),
        )
        min_width = (
            sum(w.width() for w in words[:-1]) + words[-1].pruned().width()
        )
        line, w = mkwrapper(words, STATE).line(min_width + 0.01)
        assert line == Line(
            words,
            approx(sum(w.width() for w in words)),
            0,
        )
        assert w == WrapDone(BLUE.apply(STATE))

    def test_just_too_little_space(self):
        words: tuple[Word | WithCmd, ...] = (
            Word.simple("complex ", STATE, None),
            Word.simple("is  ", STATE, " "),
            WithCmd(Word.simple("better ", STATE, " "), BLUE),
            Word.simple("than ", BLUE.apply(STATE), " "),
            Word.simple("complicated. ", BLUE.apply(STATE), " "),
        )
        min_width = (
            sum(w.width() for w in words[:-1]) + words[-1].pruned().width()
        )
        line, w = mkwrapper(words, STATE).line(min_width - 0.01)
        expect_words = (
            *words[:-1],
            Word.simple("complicat-", BLUE.apply(STATE), " "),
        )
        assert line == Line(
            expect_words,
            approx(expect_width := sum(w.width() for w in expect_words)),
            approx(min_width - 0.01 - expect_width),
        )
        assert_wrapper_eq(
            w,
            Wrapper(
                BranchableIterator(
                    [Word.simple("ed. ", BLUE.apply(STATE), None)]
                ),
                BLUE.apply(STATE),
                STATE.lead,
            ),
        )

    def test_partial_space(self):
        words: tuple[Word | WithCmd, ...] = (
            Word.simple("complex ", STATE, None),
            Word.simple("is  ", STATE, " "),
            WithCmd(Word.simple("better ", STATE, " "), BIG),
            WithCmd(Word.simple("than ", BIG.apply(STATE), " "), HUGE),
            Word.simple("complicated. ", HUGE.apply(STATE), " "),
        )
        expect_words = (
            *words[:3],
            WithCmd(Word.simple("than", BIG.apply(STATE), " "), HUGE),
        )
        expect_width = sum(w.width() for w in expect_words)
        line, w = mkwrapper(words, STATE, HUGE.apply(STATE).lead).line(
            expect_width + 1
        )
        assert line == Line(
            expect_words,
            approx(expect_width),
            approx(1),
        )
        assert_wrapper_eq(
            w,
            Wrapper(
                BranchableIterator([words[4].without_init_kern()]),
                HUGE.apply(STATE),
                HUGE.apply(STATE).lead,
            ),
        )


STRETCHES = [
    Stretch(BLUE, "Simple is better than com"),
    Stretch(RED, "plex. "),
    Stretch(BLACK, "Complex is better than "),
    Stretch(HUGE, "complicated. "),
    Stretch(NORMAL, "Flat is better than nested. "),
    Stretch(SMALL, "Sparse is better than d"),
    Stretch(NORMAL, "ense. "),
    Stretch(RED, "Readability counts. "),
    Stretch(BIG, "Special cases aren't special enough to "),
    Stretch(SMALL, "break the rules. "),
]


class TestWrapFill:
    def test_long_low_frame(self):
        w = Wrapper.start(STRETCHES, BLUE.apply(STATE), 0)
        assert w.state == BLUE.apply(STATE)
        stack, w_new = w.fill(10_000, 0.1, allow_empty=True)
        assert stack == []
        assert_wrapper_eq(w, w_new)
        stack, w_new = w.fill(10_000, 0.1, allow_empty=False)
        assert w_new == WrapDone(multi(SMALL, RED).apply(STATE))
        [line] = stack
        assert len(line.words) == 31

    def test_narrow_tall_frame(self):
        w = Wrapper.start(STRETCHES, STATE, 0)
        assert w.state == BLUE.apply(STATE)
        stack, w_new = w.fill(0.1, 10_000, allow_empty=False)
        assert w.fill(0.1, 10_000, allow_empty=True) == (stack, w_new)
        assert len(stack) == 48
        assert w_new == WrapDone(multi(RED, SMALL).apply(STATE))

    def test_narrow_low_frame(self):
        w = Wrapper.start(STRETCHES, STATE, 0)
        assert w.state == BLUE.apply(STATE)
        stack, w_new = w.fill(0.1, 0.1, allow_empty=False)
        [line] = stack
        assert len(line.words) == 1
        assert isinstance(w_new, Wrapper)
        assert_wrapper_eq(
            w_new,
            Wrapper(w_new.queue, BLUE.apply(STATE), w.lead),
        )

    def test_tall_frame(self):
        w = Wrapper.start(STRETCHES, STATE, 0)
        assert w.state == BLUE.apply(STATE)
        stack, w_new = w.fill(500, 10_000, allow_empty=True)
        assert len(stack) == 10
        assert w_new == WrapDone(multi(RED, SMALL).apply(STATE))

    def test_medium_frame(self):
        w = Wrapper.start(STRETCHES, STATE, 0)
        assert w.state == BLUE.apply(STATE)
        stack, w_new = w.fill(500, 76, allow_empty=True)
        assert len(stack) == 3
        assert isinstance(w_new, Wrapper)
        assert_wrapper_eq(
            w_new,
            Wrapper(
                w_new.queue,
                HUGE.apply(STATE),
                w.lead,
            ),
        )
        stack, w_new = w_new.fill(800, 90, allow_empty=True)
        assert len(stack) == 3


class TestJustify:
    def test_empty(self):
        line = Line((), 0, 0)
        assert line.justify() == line

    def test_no_word_breaks(self):
        line = Line((Word.simple("complex", STATE, None),), 200, 10)
        assert line.justify() == line

    def test_one_word_break(self):
        content = (
            Word.simple("Beautiful ", STATE, None),
            Word.simple("is", STATE, " "),
        )
        line = Line(
            content,
            width=sum(w.width() for w in content),
            space=8,
        )
        justified = line.justify()
        assert justified.width == approx(line.width + 8)
        assert sum(w.width() for w in justified.words) == approx(
            justified.width
        )

    def test_multiple_breaks_different_sizes(self):
        words = tuple(parse(STRETCHES, STATE)[1])
        line = Line(tuple(words), sum(w.width() for w in words), 10)
        justified = line.justify()
        assert justified.width == approx(line.width + 10)
        assert sum(w.width() for w in justified.words) == approx(
            justified.width
        )
