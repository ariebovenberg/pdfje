from __future__ import annotations

from typing import Iterable, Sequence

from pdfje.common import XY, flatten
from pdfje.typeset import firstfit
from pdfje.typeset.common import Passage, Slug
from pdfje.typeset.lines import Line
from pdfje.typeset.words import WithCmd, Word, WordLike, parse
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
    plaintext,
)

STATE = mkstate(FONT, 10, hyphens=hyphenate_word)


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


def assert_word_eq(a: WordLike | None, b: WordLike | None) -> None:
    if isinstance(a, WithCmd) and isinstance(b, WithCmd):
        assert a.cmd == b.cmd
        _assert_word_eq(a.word, b.word)
    elif isinstance(a, Word) and isinstance(b, Word):
        _assert_word_eq(a, b)
    else:
        assert a == b


def assert_word_iter_eq(a: Iterable[WordLike], b: Iterable[WordLike]) -> None:
    words_a = list(a)
    words_b = list(b)
    assert len(words_a) == len(words_b)
    for word_a, word_b in zip(words_a, words_b):
        assert_word_eq(word_a, word_b)


class TestTakeLine:
    def test_empty(self):
        ws, ln = firstfit.take_line(iter(()), 100)
        assert ws is None
        assert ln == Line((), 0, 0)

    def test_one_word_and_enough_space(self):
        word = Word.simple("complex ", STATE, None)
        ws, ln = firstfit.take_line(iter([word]), 10_000)
        assert ln == Line((word,), approx(word.width()), 0)
        assert ws is None

    def test_one_word_and_barely_enough_space(self):
        word = Word.simple("complex ", STATE, None)
        ws, ln = firstfit.take_line(iter([word]), word.pruned().width() + 0.01)
        assert ln == Line(
            (word,),
            approx(word.width()),
            0,
        )
        assert ws is None

    def test_one_word_and_just_too_little_space(self):
        word = Word.simple("complex ", STATE, None)
        cutoff = word.pruned().width() - 0.01
        ws, ln = firstfit.take_line(iter([word]), cutoff)
        assert ln == Line(
            (partial := Word.simple("com-", STATE, None),),
            approx(partial.width()),
            cutoff - partial.width(),
        )
        assert ws is not None
        [leftover] = ws
        assert_word_eq(leftover, Word.simple("plex ", STATE, None))

    def test_one_word_and_very_little_space(self):
        word = Word.simple("complex ", STATE, None)
        ws, ln = firstfit.take_line(iter([word]), 0.01)
        assert ln == Line(
            (partial := Word.simple("com-", STATE, None),),
            approx(partial.width()),
            0.01 - partial.width(),
        )
        assert ws is not None
        [leftover] = ws
        assert_word_eq(leftover, Word.simple("plex ", STATE, None))

    def test_enough_space(self):
        words: tuple[WordLike, ...] = (
            Word.simple("complex ", STATE, None),
            Word.simple("is  ", STATE, " "),
            WithCmd(Word.simple("better ", STATE, " "), BLUE),
            Word.simple("than ", BLUE.apply(STATE), " "),
            Word.simple("complicated. ", BLUE.apply(STATE), " "),
        )
        ws, ln = firstfit.take_line(iter(words), 10_000)
        assert ln == Line(words, approx(sum(w.width() for w in words)), 0)
        assert ws is None

    def test_barely_enough_space(self):
        words: tuple[WordLike, ...] = (
            Word.simple("complex ", STATE, None),
            Word.simple("is  ", STATE, " "),
            WithCmd(Word.simple("better ", STATE, " "), BLUE),
            Word.simple("than ", BLUE.apply(STATE), " "),
            Word.simple("complicated. ", BLUE.apply(STATE), " "),
        )
        min_width = (
            sum(w.width() for w in words[:-1]) + words[-1].pruned().width()
        )
        ws, ln = firstfit.take_line(iter(words), min_width + 0.01)
        assert ln == Line(
            words,
            approx(sum(w.width() for w in words)),
            0,
        )
        assert ws is None

    def test_just_too_little_space(self):
        words: tuple[WordLike, ...] = (
            Word.simple("complex ", STATE, None),
            Word.simple("is  ", STATE, " "),
            WithCmd(Word.simple("better ", STATE, " "), BLUE),
            Word.simple("than ", BLUE.apply(STATE), " "),
            Word.simple("complicated. ", BLUE.apply(STATE), " "),
        )
        min_width = (
            sum(w.width() for w in words[:-1]) + words[-1].pruned().width()
        )
        ws, ln = firstfit.take_line(iter(words), min_width - 0.01)
        expect_words = (
            *words[:-1],
            Word.simple("complicat-", BLUE.apply(STATE), " "),
        )
        assert ln == Line(
            expect_words,
            approx(expect_width := sum(w.width() for w in expect_words)),
            approx(min_width - 0.01 - expect_width),
        )
        assert ws is not None
        assert_word_iter_eq(ws, [Word.simple("ed. ", BLUE.apply(STATE), None)])

    def test_partial_space(self):
        words: tuple[WordLike, ...] = (
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
        ws, ln = firstfit.take_line(iter(words), expect_width + 1)
        assert ln == Line(expect_words, approx(expect_width), approx(1))
        assert ws is not None
        assert_word_iter_eq(ws, [words[4].without_init_kern()])

    def test_hard_hyphen(self):
        words: tuple[WordLike, ...] = (
            Word.simple("complex ", STATE, None),
            Word.simple("is  ", STATE, " "),
            WithCmd(Word.simple("better ", STATE, " "), BIG),
            WithCmd(Word.simple("than-", BIG.apply(STATE), " "), HUGE),
            Word.simple("complicated. ", HUGE.apply(STATE), "-"),
        )
        expect_words = (
            *words[:3],
            WithCmd(Word.simple("than-", BIG.apply(STATE), " "), HUGE),
        )
        expect_width = sum(w.width() for w in expect_words)
        ws, ln = firstfit.take_line(iter(words), expect_width + 1)
        assert ln == Line(expect_words, approx(expect_width), approx(1))
        assert ws is not None
        assert_word_iter_eq(ws, [words[4].without_init_kern()])


PASSAGES = [
    Passage(BLUE, "Simple is better than com"),
    Passage(RED, "plex. "),
    Passage(BLACK, "Complex is better than "),
    Passage(HUGE, "complicated. "),
    Passage(NORMAL, "Flat is better than nested. "),
    Passage(SMALL, "Sparse is better than d"),
    Passage(NORMAL, "ense. "),
    Passage(RED, "Readability counts. "),
    Passage(BIG, "Special cases aren't special enough to "),
    Passage(SMALL, "break the rules. "),
]


class TestTakeBox:
    def test_long_low_frame(self):
        _, [*words] = parse(PASSAGES, STATE)
        w_new, stack, _ = firstfit.take_box(
            iter(words), XY(10_000, 0.1), allow_empty=True, lead=20
        )
        assert stack == []
        assert words == list(w_new or ())
        w_new, stack, _ = firstfit.take_box(
            iter(words), XY(10_000, 0.1), allow_empty=False, lead=20
        )
        [line] = stack
        assert len(line.words) == 31
        assert w_new is None
        assert line.words[-1].state == multi(SMALL, RED).apply(STATE)

    def test_narrow_tall_frame(self):
        _, words = parse(PASSAGES, STATE)
        w_new, stack, _ = firstfit.take_box(
            words, XY(0.1, 10_000), allow_empty=False, lead=20
        )
        assert len(stack) == 47
        assert w_new is None
        assert stack[-1].words[-1].state == multi(RED, SMALL).apply(STATE)

    def test_narrow_low_frame(self):
        _, [*words] = parse(PASSAGES, STATE)
        w_new, stack, _ = firstfit.take_box(
            iter(words), XY(0.1, 0.1), allow_empty=False, lead=20
        )
        [line] = stack
        assert len(line.words) == 1
        # The result has the same amount of 'words' because the first word
        # is split into two, and the second part is re-added to the queue.
        assert len(list(w_new or ())) == len(words)

    def test_tall_frame(self):
        _, words = parse(PASSAGES, STATE)
        w_new, stack, _ = firstfit.take_box(
            words, XY(500, 10_000), allow_empty=True, lead=20
        )
        assert len(stack) == 10
        assert w_new is None
        assert stack[-1].words[-1].state == multi(RED, SMALL).apply(STATE)

    def test_medium_frame(self):
        _, words = parse(PASSAGES, STATE)
        w_new, stack, _ = firstfit.take_box(
            words, XY(500, 76), allow_empty=True, lead=25
        )
        assert len(stack) == 3
        assert stack[-1].words[-1].state == HUGE.apply(STATE)
        w_new, stack, _ = firstfit.take_box(
            w_new, XY(800, 90), allow_empty=True, lead=25
        )
        assert len(stack) == 3


def _plain(ls: Iterable[Sequence[Line]]) -> str:
    return "".join(map(plaintext, flatten(ls))).strip()


class TestFill:
    def test_empty(self):
        [lines] = list(
            firstfit.fill(
                iter([]),
                iter([XY(500, 70), XY(800, 90), XY(400, 120)]),
                True,
                25,
            )
        )
        assert lines == [Line((), 0, 0)]

    def test_one_line(self):
        _, [*words] = parse(PASSAGES, STATE)
        filled = list(
            firstfit.fill(
                iter(words),
                iter([XY(10_000, 900), XY(800, 90)]),
                True,
                25,
            )
        )
        linecounts = list(map(len, filled))
        assert linecounts == [1]
        assert plaintext(words).strip() == _plain(filled)

    def test_one_box(self):
        _, [*words] = parse(PASSAGES, STATE)
        filled = list(
            firstfit.fill(
                iter(words),
                iter([XY(800, 900), XY(800, 90)]),
                True,
                25,
            )
        )
        linecounts = list(map(len, filled))
        assert linecounts == [6]
        assert (
            plaintext(words).strip()
            == "".join(map(plaintext, flatten(filled))).strip()
        )

    def test_no_orphans(self):
        _, [*words] = parse(PASSAGES, STATE)
        filled = list(
            firstfit.fill(
                iter(words),
                iter([XY(500, 70), XY(800, 90), XY(400, 120), XY(500, 70)]),
                True,
                25,
            )
        )
        linecounts = list(map(len, filled))
        assert linecounts == [2, 3, 3]
        assert plaintext(words).strip() == _plain(filled)

    def test_forced_orphan(self):
        _, [*words] = parse(PASSAGES, STATE)
        filled = list(
            firstfit.fill(
                iter(words),
                iter([XY(500, 30), XY(800, 90), XY(400, 20), XY(500, 300)]),
                False,
                25,
            )
        )
        linecounts = list(map(len, filled))
        assert linecounts == [1, 3, 1, 3]
        assert (
            plaintext(words).strip()
            == "".join(map(plaintext, flatten(filled))).strip()
        )

    def test_prevent_orphaned_first_line(self):
        _, [*words] = parse(PASSAGES, STATE)
        filled = list(
            firstfit.fill(
                iter(words),
                iter([XY(500, 30), XY(800, 90), XY(400, 300)]),
                True,
                25,
            )
        )
        assert list(map(len, filled)) == [0, 3, 6]
        assert plaintext(words).strip() == _plain(filled)

    def test_prevent_orphaned_last_line(self):
        _, [*words] = parse(PASSAGES, STATE)
        filled = list(
            firstfit.fill(
                iter(words),
                iter([XY(500, 51), XY(800, 30), XY(400, 153), XY(500, 300)]),
                True,
                25,
            )
        )
        linecounts = list(map(len, filled))
        assert linecounts == [2, 1, 5, 2]
        assert plaintext(words).strip() == _plain(filled)

    def test_last_orphan_not_fixable(self):
        _, [*words] = parse(PASSAGES, STATE)
        filled = list(
            firstfit.fill(
                iter(words),
                iter(
                    [
                        XY(500, 51),
                        XY(800, 30),
                        XY(400, 153),
                        # orphan occurs here, but there is not enough space
                        # to add an extra line to this column
                        XY(500, 43),
                        XY(400, 400),
                    ]
                ),
                True,
                25,
            )
        )
        linecounts = list(map(len, filled))
        assert linecounts == [2, 1, 6, 1]
        assert plaintext(words).strip() == _plain(filled)

    def test_begin_and_end_orphan_fixable(self):
        _, [*words] = parse(PASSAGES, STATE)
        filled = list(
            firstfit.fill(
                iter(words),
                iter([XY(3_000, 30), XY(3_000, 500), XY(400, 153)]),
                True,
                25,
            )
        )
        linecounts = list(map(len, filled))
        assert linecounts == [0, 2]
        assert plaintext(words).strip() == _plain(filled)

    def test_orphan_not_fixable_because_not_allow_empty(self):
        _, [*words] = parse(PASSAGES, STATE)
        filled = list(
            firstfit.fill(
                iter(words),
                iter([XY(3_000, 30), XY(3_000, 500), XY(400, 153)]),
                False,
                25,
            )
        )
        linecounts = list(map(len, filled))
        assert linecounts == [1, 1]
        assert plaintext(words).strip() == _plain(filled)

    def test_orphan_not_fixable_because_would_create_empty_column(self):
        _, [*words] = parse(PASSAGES, STATE)
        filled = list(
            firstfit.fill(
                iter(words),
                iter(
                    [
                        XY(400, 53),
                        XY(600, 21),
                        XY(10_000, 500),
                        XY(1_000, 1_000),
                    ]
                ),
                False,
                25,
            )
        )
        linecounts = list(map(len, filled))
        assert linecounts == [2, 1, 1]
        assert plaintext(words).strip() == _plain(filled)

    def test_orphan_not_fixable_because_would_create_one_line_column(self):
        _, [*words] = parse(PASSAGES, STATE)
        filled = list(
            firstfit.fill(
                iter(words),
                iter(
                    [
                        XY(400, 53),
                        XY(600, 52),
                        XY(10_000, 500),
                        XY(1_000, 1_000),
                    ]
                ),
                False,
                25,
            )
        )
        linecounts = list(map(len, filled))
        assert linecounts == [2, 2, 1]
        assert plaintext(words).strip() == _plain(filled)

    def test_fixing_orphan_not_possible_because_last_column_is_very_wide(self):
        _, [*words] = parse(PASSAGES, STATE)
        filled = list(
            firstfit.fill(
                iter(words),
                iter([XY(500, 51), XY(600, 76), XY(10_000, 153)]),
                False,
                25,
            )
        )
        linecounts = list(map(len, filled))
        assert linecounts == [2, 3, 1]
        assert plaintext(words).strip() == _plain(filled)

    def test_fixing_orphan_leads_to_many_more_columns(self):
        _, [*words] = parse(PASSAGES, STATE)
        filled = list(
            firstfit.fill(
                iter(words),
                iter(
                    [
                        XY(500, 51),
                        XY(1_110, 76),
                        # solving an orphan here leads to many more columns
                        # because the previous column is relatively wide
                        XY(210, 76),
                        XY(210, 76),
                        # this in turn creates another fixable orphan here
                        XY(210, 76),
                    ]
                ),
                False,
                25,
            )
        )
        linecounts = list(map(len, filled))
        assert linecounts == [2, 2, 3, 2, 2]
        assert plaintext(words).strip() == _plain(filled)


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
        words = tuple(parse(PASSAGES, STATE)[1])
        line = Line(tuple(words), sum(w.width() for w in words), 10)
        justified = line.justify()
        assert justified.width == approx(line.width + 10)
        assert sum(w.width() for w in justified.words) == approx(
            justified.width
        )
