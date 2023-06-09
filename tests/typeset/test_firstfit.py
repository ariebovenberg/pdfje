from __future__ import annotations

from itertools import repeat
from typing import Iterable, Sequence

import pytest

from pdfje.common import XY, Align, flatten
from pdfje.typeset import firstfit
from pdfje.typeset.firstfit import Line
from pdfje.typeset.parse import into_words
from pdfje.typeset.words import Slug, WithCmd, Word, WordLike
from pdfje.vendor.hyphenate import hyphenate_word

from ..common import (
    BIG,
    BLUE,
    FONT,
    HUGE,
    PASSAGES,
    RED,
    SMALL,
    approx,
    mkstate,
    multi,
    plaintext,
)

STATE = mkstate(FONT, 10, hyphens=hyphenate_word)


@pytest.fixture(scope="module")
def words() -> Sequence[WordLike]:
    return list(into_words(PASSAGES, STATE)[1])


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
        assert_word_eq(a.word, b.word)
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
        word = Word.new("complex ", STATE, None)
        ws, ln = firstfit.take_line(iter([word]), 10_000)
        assert ln == Line((word,), approx(word.width), 0)
        assert ws is None

    def test_one_word_and_barely_enough_space(self):
        word = Word.new("complex ", STATE, None)
        ws, ln = firstfit.take_line(iter([word]), word.pruned().width + 0.01)
        assert ln == Line((word,), approx(word.width), 0)
        assert ws is None

    def test_one_word_and_just_too_little_space(self):
        word = Word.new("complex ", STATE, None)
        cutoff = word.pruned().width - 0.01
        ws, ln = firstfit.take_line(iter([word]), cutoff)
        assert ln == Line(
            (partial := Word.new("com-", STATE, None),),
            approx(partial.width),
            cutoff - partial.width,
        )
        assert ws is not None
        [leftover] = ws
        assert_word_eq(leftover, Word.new("plex ", STATE, None))

    def test_one_word_and_very_little_space(self):
        word = Word.new("complex ", STATE, None)
        ws, ln = firstfit.take_line(iter([word]), 0.01)
        assert ln == Line(
            (partial := Word.new("com-", STATE, None),),
            approx(partial.width),
            0.01 - partial.width,
        )
        assert ws is not None
        [leftover] = ws
        assert_word_eq(leftover, Word.new("plex ", STATE, None))

    def test_enough_space(self):
        words: tuple[WordLike, ...] = (
            Word.new("complex ", STATE, None),
            Word.new("is  ", STATE, " "),
            WithCmd(Word.new("better ", STATE, " "), BLUE),
            Word.new("than ", BLUE.apply(STATE), " "),
            Word.new("complicated. ", BLUE.apply(STATE), " "),
        )
        ws, ln = firstfit.take_line(iter(words), 10_000)
        assert ln == Line(words, approx(sum(w.width for w in words)), 0)
        assert ws is None

    def test_barely_enough_space(self):
        words: tuple[WordLike, ...] = (
            Word.new("complex ", STATE, None),
            Word.new("is  ", STATE, " "),
            WithCmd(Word.new("better ", STATE, " "), BLUE),
            Word.new("than ", BLUE.apply(STATE), " "),
            Word.new("complicated. ", BLUE.apply(STATE), " "),
        )
        min_width = sum(w.width for w in words[:-1]) + words[-1].pruned().width
        ws, ln = firstfit.take_line(iter(words), min_width + 0.01)
        assert ln == Line(words, approx(sum(w.width for w in words)), 0)
        assert ws is None

    def test_just_too_little_space(self):
        words: tuple[WordLike, ...] = (
            Word.new("complex ", STATE, None),
            Word.new("is  ", STATE, " "),
            WithCmd(Word.new("better ", STATE, " "), BLUE),
            Word.new("than ", BLUE.apply(STATE), " "),
            Word.new("complicated. ", BLUE.apply(STATE), " "),
        )
        min_width = sum(w.width for w in words[:-1]) + words[-1].pruned().width
        ws, ln = firstfit.take_line(iter(words), min_width - 0.01)
        expect_words = (
            *words[:-1],
            Word.new("complicat-", BLUE.apply(STATE), " "),
        )
        assert ln == Line(
            expect_words,
            approx(expect_width := sum(w.width for w in expect_words)),
            approx(min_width - 0.01 - expect_width),
        )
        assert ws is not None
        assert_word_iter_eq(ws, [Word.new("ed. ", BLUE.apply(STATE), None)])

    def test_partial_space(self):
        words: tuple[WordLike, ...] = (
            Word.new("complex ", STATE, None),
            Word.new("is  ", STATE, " "),
            WithCmd(Word.new("better ", STATE, " "), BIG),
            WithCmd(Word.new("than ", BIG.apply(STATE), " "), HUGE),
            Word.new("complicated. ", HUGE.apply(STATE), " "),
        )
        expect_words = (
            *words[:3],
            WithCmd(Word.new("than", BIG.apply(STATE), " "), HUGE),
        )
        expect_width = sum(w.width for w in expect_words)
        ws, ln = firstfit.take_line(iter(words), expect_width + 1)
        assert ln == Line(expect_words, approx(expect_width), approx(1))
        assert ws is not None
        assert_word_iter_eq(ws, [words[4].without_init_kern()])

    def test_hard_hyphen(self):
        words: tuple[WordLike, ...] = (
            Word.new("complex ", STATE, None),
            Word.new("is  ", STATE, " "),
            WithCmd(Word.new("better ", STATE, " "), BIG),
            WithCmd(Word.new("than-", BIG.apply(STATE), " "), HUGE),
            Word.new("complicated. ", HUGE.apply(STATE), "-"),
        )
        expect_words = (
            *words[:3],
            WithCmd(Word.new("than-", BIG.apply(STATE), " "), HUGE),
        )
        expect_width = sum(w.width for w in expect_words)
        ws, ln = firstfit.take_line(iter(words), expect_width + 1)
        assert ln == Line(expect_words, approx(expect_width), approx(1))
        assert ws is not None
        assert_word_iter_eq(ws, [words[4].without_init_kern()])


class TestTakeBox:
    def test_long_low_frame(self):
        _, [*words] = into_words(PASSAGES, STATE)
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
        _, words = into_words(PASSAGES, STATE)
        w_new, stack, _ = firstfit.take_box(
            words, XY(0.1, 10_000), allow_empty=False, lead=20
        )
        assert len(stack) == 47
        assert w_new is None
        assert stack[-1].words[-1].state == multi(RED, SMALL).apply(STATE)

    def test_narrow_low_frame(self):
        _, [*words] = into_words(PASSAGES, STATE)
        w_new, stack, _ = firstfit.take_box(
            iter(words), XY(0.1, 0.1), allow_empty=False, lead=20
        )
        [line] = stack
        assert len(line.words) == 1
        # The result has the same amount of 'words' because the first word
        # is split into two, and the second part is re-added to the queue.
        assert len(list(w_new or ())) == len(words)

    def test_tall_frame(self):
        _, words = into_words(PASSAGES, STATE)
        w_new, stack, _ = firstfit.take_box(
            words, XY(500, 10_000), allow_empty=True, lead=20
        )
        assert len(stack) == 10
        assert w_new is None
        assert stack[-1].words[-1].state == multi(RED, SMALL).apply(STATE)

    def test_medium_frame(self):
        _, words = into_words(PASSAGES, STATE)
        w_new, stack, _ = firstfit.take_box(
            words, XY(500, 76), allow_empty=True, lead=25
        )
        assert len(stack) == 3
        assert stack[-1].words[-1].state == HUGE.apply(STATE)
        w_new, stack, _ = firstfit.take_box(
            w_new, XY(800, 90), allow_empty=True, lead=25
        )
        assert len(stack) == 3


class TestShapeSimple:
    def test_empty(self):
        [lines] = list(
            firstfit._shape_simple(
                iter([]),
                iter([XY(500, 70), XY(800, 90), XY(400, 120)]),
                True,
                25,
            )
        )
        assert lines == [Line((), 0, 0)]

    def test_one_line(self):
        _, [*words] = into_words(PASSAGES, STATE)
        shaped = list(
            firstfit._shape_simple(
                iter(words),
                iter([XY(10_000, 900), XY(800, 90)]),
                True,
                25,
            )
        )
        linecounts = list(map(len, shaped))
        assert linecounts == [1]
        assert plaintext(words).strip() == plaintext(shaped).strip()

    def test_one_box(self):
        _, [*words] = into_words(PASSAGES, STATE)
        shaped = list(
            firstfit._shape_simple(
                iter(words),
                iter([XY(800, 900), XY(800, 90)]),
                True,
                25,
            )
        )
        linecounts = list(map(len, shaped))
        assert linecounts == [6]
        assert (
            plaintext(words).strip()
            == "".join(map(plaintext, flatten(shaped))).strip()
        )

    def test_no_orphans(self):
        _, [*words] = into_words(PASSAGES, STATE)
        shaped = list(
            firstfit._shape_simple(
                iter(words),
                iter([XY(500, 70), XY(800, 90), XY(400, 120), XY(500, 70)]),
                True,
                25,
            )
        )
        linecounts = list(map(len, shaped))
        assert linecounts == [2, 3, 3]
        assert plaintext(words).strip() == plaintext(shaped).strip()


class TestShapeAvoidingOrphans:
    def test_empty(self):
        [lines] = list(
            firstfit._shape_avoid_orphans(
                iter([]),
                iter([XY(500, 70), XY(800, 90), XY(400, 120)]),
                True,
                25,
            )
        )
        assert lines == [Line((), 0, 0)]

    def test_one_line(self):
        _, [*words] = into_words(PASSAGES, STATE)
        shaped = list(
            firstfit._shape_avoid_orphans(
                iter(words),
                iter([XY(10_000, 900), XY(800, 90)]),
                True,
                25,
            )
        )
        linecounts = list(map(len, shaped))
        assert linecounts == [1]
        assert plaintext(words).strip() == plaintext(shaped).strip()

    def test_one_box(self):
        _, [*words] = into_words(PASSAGES, STATE)
        shaped = list(
            firstfit._shape_avoid_orphans(
                iter(words),
                iter([XY(800, 900), XY(800, 90)]),
                True,
                25,
            )
        )
        linecounts = list(map(len, shaped))
        assert linecounts == [6]
        assert plaintext(words).strip() == plaintext(shaped).strip()

    def test_no_orphans(self):
        _, [*words] = into_words(PASSAGES, STATE)
        shaped = list(
            firstfit._shape_avoid_orphans(
                iter(words),
                iter([XY(500, 70), XY(800, 90), XY(400, 120), XY(500, 70)]),
                True,
                25,
            )
        )
        linecounts = list(map(len, shaped))
        assert linecounts == [2, 3, 3]
        assert plaintext(words).strip() == plaintext(shaped).strip()

    def test_forced_orphan_due_to_short_columns(self):
        _, [*words] = into_words(PASSAGES, STATE)
        shaped = list(
            firstfit._shape_avoid_orphans(
                iter(words),
                iter([XY(500, 30), XY(800, 90), XY(400, 20), XY(500, 300)]),
                False,
                25,
            )
        )
        linecounts = list(map(len, shaped))
        assert linecounts == [1, 3, 1, 3]
        assert plaintext(words).strip() == plaintext(shaped).strip()

    def test_prevent_orphaned_first_line(self):
        _, [*words] = into_words(PASSAGES, STATE)
        shaped = list(
            firstfit._shape_avoid_orphans(
                iter(words),
                iter([XY(500, 30), XY(800, 90), XY(400, 300)]),
                True,
                25,
            )
        )
        assert list(map(len, shaped)) == [0, 3, 6]
        assert plaintext(words).strip() == plaintext(shaped).strip()

    def test_prevent_orphaned_last_line(self):
        _, [*words] = into_words(PASSAGES, STATE)
        shaped = list(
            firstfit._shape_avoid_orphans(
                iter(words),
                iter([XY(500, 51), XY(800, 30), XY(400, 153), XY(500, 300)]),
                True,
                25,
            )
        )
        linecounts = list(map(len, shaped))
        assert linecounts == [2, 1, 5, 2]
        assert plaintext(words).strip() == plaintext(shaped).strip()

    def test_last_orphan_not_fixable(self):
        _, [*words] = into_words(PASSAGES, STATE)
        shaped = list(
            firstfit._shape_avoid_orphans(
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
        linecounts = list(map(len, shaped))
        assert linecounts == [2, 1, 6, 1]
        assert plaintext(words).strip() == plaintext(shaped).strip()

    def test_begin_and_end_orphan_fixable(self):
        _, [*words] = into_words(PASSAGES, STATE)
        shaped = list(
            firstfit._shape_avoid_orphans(
                iter(words),
                iter([XY(3_000, 30), XY(3_000, 500), XY(400, 153)]),
                True,
                25,
            )
        )
        linecounts = list(map(len, shaped))
        assert linecounts == [0, 2]
        assert plaintext(words).strip() == plaintext(shaped).strip()

    def test_orphan_not_fixable_because_not_allow_empty(self):
        _, [*words] = into_words(PASSAGES, STATE)
        shaped = list(
            firstfit._shape_avoid_orphans(
                iter(words),
                iter([XY(3_000, 30), XY(3_000, 500), XY(400, 153)]),
                False,
                25,
            )
        )
        linecounts = list(map(len, shaped))
        assert linecounts == [1, 1]
        assert plaintext(words).strip() == plaintext(shaped).strip()

    def test_orphan_not_fixable_because_would_create_empty_column(self):
        _, [*words] = into_words(PASSAGES, STATE)
        shaped = list(
            firstfit._shape_avoid_orphans(
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
        linecounts = list(map(len, shaped))
        assert linecounts == [2, 1, 1]
        assert plaintext(words).strip() == plaintext(shaped).strip()

    def test_orphan_not_fixable_because_would_create_one_line_column(self):
        _, [*words] = into_words(PASSAGES, STATE)
        shaped = list(
            firstfit._shape_avoid_orphans(
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
        linecounts = list(map(len, shaped))
        assert linecounts == [2, 2, 1]
        assert plaintext(words).strip() == plaintext(shaped).strip()

    def test_fixing_orphan_not_possible_because_last_column_is_very_wide(self):
        _, [*words] = into_words(PASSAGES, STATE)
        shaped = list(
            firstfit._shape_avoid_orphans(
                iter(words),
                iter([XY(500, 51), XY(600, 76), XY(10_000, 153)]),
                False,
                25,
            )
        )
        linecounts = list(map(len, shaped))
        assert linecounts == [2, 3, 1]
        assert plaintext(words).strip() == plaintext(shaped).strip()

    def test_fixing_orphan_leads_to_many_more_columns(self):
        _, [*words] = into_words(PASSAGES, STATE)
        shaped = list(
            firstfit._shape_avoid_orphans(
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
        linecounts = list(map(len, shaped))
        assert linecounts == [2, 2, 3, 2, 2]
        assert plaintext(words).strip() == plaintext(shaped).strip()


class TestShape:
    @pytest.mark.parametrize("allow_empty", [True, False])
    @pytest.mark.parametrize("avoid_orphans", [True, False])
    @pytest.mark.parametrize(
        "align", [Align.LEFT, Align.RIGHT, Align.CENTER, Align.JUSTIFY]
    )
    def test_justified(self, allow_empty, avoid_orphans, align, words):
        width = 500
        shaped = list(
            firstfit.shape(
                iter(words),
                repeat(XY(width, 51)),
                allow_empty=allow_empty,
                lead=15,
                avoid_orphans=avoid_orphans,
                align=align,
            )
        )
        assert plaintext(words).strip() == plaintext(shaped).strip()
        assert len(shaped) == 4
        if align is Align.JUSTIFY:
            for block in shaped:
                for ln in block.lines[:-1]:
                    assert ln.width == approx(width)
                assert block.lines[-1].width <= width
        else:
            for block in shaped:
                for ln in block.lines:
                    assert ln.width < width


class TestJustify:
    def test_empty(self):
        line = Line((), 0, 0)
        assert line.justify() == line

    def test_no_word_breaks(self):
        line = Line((Word.new("complex", STATE, None),), 200, 10)
        assert line.justify() == line

    def test_one_word_break(self):
        content = (
            Word.new("Beautiful ", STATE, None),
            Word.new("is", STATE, " "),
        )
        line = Line(
            content,
            width=sum(w.width for w in content),
            space=8,
        )
        justified = line.justify()
        assert justified.width == approx(line.width + 8)
        assert sum(w.width for w in justified.words) == approx(justified.width)

    def test_multiple_breaks_different_sizes(self):
        words = tuple(into_words(PASSAGES, STATE)[1])
        line = Line(tuple(words), sum(w.width for w in words), 10)
        justified = line.justify()
        assert justified.width == approx(line.width + 10)
        assert sum(w.width for w in justified.words) == approx(justified.width)


@plaintext.register
def _(ws: Line) -> str:
    body = "".join(map(plaintext, ws.words))
    # FUTURE: this assumption that we can strip any trailing hyphen is
    # not true in *all* cases -- but good enough for our tests.
    return body.rstrip("-") if body.endswith("-") else (body + " ")
