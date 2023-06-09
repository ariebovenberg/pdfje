from __future__ import annotations

from types import SimpleNamespace
from typing import Sequence, cast

import pytest

from pdfje import XY
from pdfje.common import Align
from pdfje.typeset.layout import Line
from pdfje.typeset.optimum import ColumnQueue, Fragment, Parameters, shape
from pdfje.typeset.parse import into_words
from pdfje.typeset.words import Word, WordLike
from pdfje.vendor.hyphenate import hyphenate_word

from ..common import FONT, PASSAGES, approx, mkstate, plaintext

STATE = mkstate(font=FONT, size=12, color=(0, 0, 0), hyphens=hyphenate_word)
PARAMS = cast(
    Parameters,
    SimpleNamespace(
        tolerance=1,
        hyphen_penalty=1000,
        consecutive_hyphen_penalty=1000,
        fitness_diff_penalty=1000,
    ),
)


@pytest.fixture(scope="module")
def words() -> Sequence[WordLike]:
    return list(into_words(PASSAGES, STATE)[1])


class TestShape:
    @pytest.mark.parametrize("allow_empty", [True, False])
    @pytest.mark.parametrize("avoid_orphans", [True, False])
    @pytest.mark.parametrize("align", [Align.LEFT, Align.JUSTIFY])
    def test_no_orphans(self, avoid_orphans, allow_empty, align, words):
        shaped = list(
            shape(
                iter(words),
                iter(
                    [
                        XY(500, 70),
                        XY(700, 90),
                        XY(400, 80),
                        XY(500, 70),
                        XY(500, 400),
                    ]
                ),
                allow_empty,
                25,
                avoid_orphans,
                align,
                PARAMS,
            )
        )
        shaped = list(shaped)
        linecounts = [len(c.lines) for c in shaped]
        assert linecounts == [2, 3, 3, 2]
        assert plaintext(words).strip() == plaintext(shaped).strip()

    @pytest.mark.parametrize("allow_empty", [True])
    @pytest.mark.parametrize("avoid_orphans", [True])
    @pytest.mark.parametrize("align", [Align.LEFT])
    def test_one_line(self, allow_empty, avoid_orphans, align, words):
        width = sum(w.width for w in words)
        shaped = list(
            shape(
                iter(words),
                iter([XY(width, 70), XY(800, 90)]),
                allow_empty,
                25,
                avoid_orphans,
                align,
                PARAMS,
            )
        )
        linecounts = [len(c.lines) for c in shaped]
        assert linecounts == [1]
        assert plaintext(words).strip() == plaintext(shaped).strip()

    @pytest.mark.parametrize("allow_empty", [True, False])
    @pytest.mark.parametrize("avoid_orphans", [True, False])
    @pytest.mark.parametrize("align", [Align.LEFT, Align.JUSTIFY, Align.LEFT])
    def test_fits_in_one_column(
        self, allow_empty, avoid_orphans, align, words
    ):
        colwidth = 1000
        [shaped] = list(
            shape(
                iter(words),
                iter([XY(colwidth, 900), XY(800, 90)]),
                allow_empty,
                25,
                avoid_orphans,
                align,
                PARAMS,
            )
        )
        assert len(shaped.lines) == 5
        assert plaintext(words).strip() == plaintext(shaped).strip()

        if align is Align.JUSTIFY:
            for ln in shaped.lines[:-1]:
                assert _linewidth(ln) == approx(colwidth, abs=0.4)
            assert _linewidth(shaped.lines[-1]) <= colwidth
        else:
            for ln in shaped.lines:
                assert _linewidth(ln) < colwidth

    @pytest.mark.parametrize("avoid_orphans", [True, False])
    @pytest.mark.parametrize("align", [Align.LEFT, Align.JUSTIFY])
    def test_first_column_skipped_because_too_low(
        self, avoid_orphans, align, words
    ):
        [nothing, shaped] = list(
            shape(
                iter(words),
                iter([XY(800, 9), XY(1000, 900), XY(800, 90)]),
                True,
                25,
                avoid_orphans,
                align,
                PARAMS,
            )
        )
        assert len(nothing.lines) == 0
        assert len(shaped.lines) == 5
        assert plaintext(words).strip() == plaintext(shaped).strip()

    @pytest.mark.parametrize("avoid_orphans", [True, False])
    @pytest.mark.parametrize("align", [Align.LEFT, Align.JUSTIFY])
    def test_first_column_doesnt_allow_empty(
        self, avoid_orphans, align, words
    ):
        [first, second] = list(
            shape(
                iter(words),
                iter([XY(800, 9), XY(1000, 900), XY(800, 90)]),
                False,
                25,
                avoid_orphans,
                align,
                PARAMS,
            )
        )
        assert len(first.lines) == 1
        assert len(second.lines) > 2
        assert plaintext(words).strip() == plaintext([first, second]).strip()

    @pytest.mark.parametrize("allow_empty", [True, False])
    @pytest.mark.parametrize("avoid_orphans", [True, False])
    @pytest.mark.parametrize("align", [Align.LEFT, Align.JUSTIFY])
    def test_empty(self, allow_empty, avoid_orphans, align, words):
        shaped = list(
            shape(
                iter([]),
                iter([XY(500, 70), XY(800, 90)]),
                allow_empty,
                25,
                avoid_orphans,
                align,
                PARAMS,
            )
        )
        linecounts = [len(c.lines) for c in shaped]
        assert linecounts == [1]
        assert plaintext(shaped).strip() == ""

    @pytest.mark.parametrize("allow_empty", [True, False])
    @pytest.mark.parametrize("avoid_orphans", [True, False])
    @pytest.mark.parametrize("align", [Align.LEFT, Align.JUSTIFY])
    def test_one_space(self, allow_empty, avoid_orphans, align):
        shaped = list(
            shape(
                iter([Word.new(" ", STATE, None)]),
                iter([XY(500, 70), XY(800, 90)]),
                allow_empty,
                25,
                avoid_orphans,
                align,
                PARAMS,
            )
        )
        linecounts = [len(c.lines) for c in shaped]
        assert linecounts == [1]
        assert plaintext(shaped).strip() == ""

    @pytest.mark.parametrize("avoid_orphans", [True, False])
    @pytest.mark.parametrize("align", [Align.LEFT, Align.JUSTIFY])
    def test_empty_doesnt_fit(self, avoid_orphans, align):
        shaped = list(
            shape(
                iter([]),
                iter([XY(500, 23), XY(800, 90)]),
                True,
                25,
                avoid_orphans,
                align,
                PARAMS,
            )
        )
        linecounts = [len(c.lines) for c in shaped]
        assert linecounts == [0, 1]
        assert plaintext(shaped).strip() == ""

    @pytest.mark.parametrize("avoid_orphans", [True, False])
    @pytest.mark.parametrize("align", [Align.LEFT, Align.JUSTIFY])
    def test_forced_orphan_due_to_short_columns(
        self, avoid_orphans, align, words
    ):
        shaped = list(
            shape(
                iter(words),
                iter([XY(500, 30), XY(800, 90), XY(400, 20), XY(500, 300)]),
                False,
                25,
                avoid_orphans,
                align,
                PARAMS,
            )
        )
        linecounts = [len(c.lines) for c in shaped]
        assert linecounts == [1, 3, 1, 3]
        assert plaintext(shaped).strip() == plaintext(words).strip()

    @pytest.mark.parametrize("align", [Align.LEFT, Align.JUSTIFY])
    def test_prevent_orphaned_first_line(self, align, words):
        shaped = list(
            shape(
                iter(words),
                iter([XY(500, 30), XY(800, 90), XY(650, 300)]),
                allow_empty=True,
                lead=25,
                avoid_orphans=True,
                align=align,
                params=PARAMS,
            )
        )
        linecounts = [len(c.lines) for c in shaped]
        assert linecounts == [0, 3, 4]
        assert plaintext(shaped).strip() == plaintext(words).strip()

    @pytest.mark.parametrize("align", [Align.LEFT, Align.JUSTIFY])
    @pytest.mark.parametrize("allow_empty", [True, False])
    def test_first_line_orphan_not_prevented(self, align, allow_empty, words):
        shaped = list(
            shape(
                iter(words),
                iter([XY(500, 30), XY(800, 90), XY(650, 300)]),
                allow_empty=allow_empty,
                lead=25,
                avoid_orphans=False,
                align=align,
                params=PARAMS,
            )
        )
        linecounts = [len(c.lines) for c in shaped]
        assert linecounts == [1, 3, 3]
        assert plaintext(shaped).strip() == plaintext(words).strip()

    @pytest.mark.parametrize("align", [Align.LEFT, Align.JUSTIFY])
    @pytest.mark.parametrize("allow_empty", [True, False])
    def test_no_prevent_orphaned_last_line(self, allow_empty, align, words):
        shaped = list(
            shape(
                iter(words),
                iter([XY(500, 51), XY(800, 30), XY(500, 153), XY(500, 300)]),
                allow_empty=allow_empty,
                lead=25,
                avoid_orphans=False,
                align=align,
                params=PARAMS,
            )
        )
        linecounts = [len(c.lines) for c in shaped]
        assert linecounts == [2, 1, 6, 1]
        assert plaintext(words).strip() == plaintext(shaped).strip()

    @pytest.mark.parametrize("align", [Align.LEFT, Align.JUSTIFY])
    @pytest.mark.parametrize("allow_empty", [True, False])
    def test_prevent_orphaned_last_line(self, allow_empty, align, words):
        shaped = list(
            shape(
                iter(words),
                iter([XY(500, 51), XY(800, 30), XY(500, 153), XY(500, 300)]),
                allow_empty=allow_empty,
                lead=25,
                avoid_orphans=True,
                align=align,
                params=PARAMS,
            )
        )
        linecounts = [len(c.lines) for c in shaped]
        assert linecounts == [2, 1, 5, 2]
        assert plaintext(words).strip() == plaintext(shaped).strip()

    @pytest.mark.parametrize("allow_empty", [True, False])
    @pytest.mark.parametrize("avoid_orphans", [True, False])
    @pytest.mark.parametrize("align", [Align.LEFT, Align.JUSTIFY])
    def test_last_orphan_not_fixable_because_no_room(
        self, allow_empty, avoid_orphans, align, words
    ):
        shaped = list(
            shape(
                iter(words),
                iter(
                    [
                        XY(500, 51),
                        XY(800, 30),
                        XY(500, 153),
                        # orphan occurs here, but there is not enough space
                        # to add an extra line to this column
                        XY(500, 43),
                        XY(400, 400),
                    ]
                ),
                allow_empty,
                25,
                avoid_orphans,
                align,
                PARAMS,
            )
        )
        linecounts = [len(c.lines) for c in shaped]
        assert linecounts == [2, 1, 6, 1]
        assert plaintext(words).strip() == plaintext(shaped).strip()

    @pytest.mark.parametrize("align", [Align.LEFT, Align.JUSTIFY])
    def test_begin_and_end_orphan_fixable(self, align, words):
        shaped = list(
            shape(
                iter(words),
                iter([XY(3_000, 30), XY(3_000, 500), XY(400, 153)]),
                allow_empty=True,
                lead=25,
                avoid_orphans=True,
                align=align,
                params=PARAMS,
            )
        )
        linecounts = [len(c.lines) for c in shaped]
        assert linecounts == [0, 2]
        assert plaintext(words).strip() == plaintext(shaped).strip()

    @pytest.mark.parametrize("avoid_orphans", [True, False])
    @pytest.mark.parametrize("align", [Align.LEFT, Align.JUSTIFY])
    def test_orphan_not_fixable_because_not_allow_empty(
        self, align, avoid_orphans, words
    ):
        shaped = list(
            shape(
                iter(words),
                iter([XY(3_000, 30), XY(3_000, 500), XY(400, 153)]),
                allow_empty=False,
                lead=25,
                avoid_orphans=avoid_orphans,
                align=align,
                params=PARAMS,
            )
        )
        linecounts = [len(c.lines) for c in shaped]
        assert linecounts == [1, 1]
        assert plaintext(words).strip() == plaintext(shaped).strip()

    @pytest.mark.parametrize("avoid_orphans", [True, False])
    @pytest.mark.parametrize("allow_empty", [True, False])
    @pytest.mark.parametrize("align", [Align.LEFT, Align.JUSTIFY])
    def test_orphan_not_fixable_because_would_create_one_line_column(
        self, align, avoid_orphans, allow_empty, words
    ):
        shaped = list(
            shape(
                iter(words),
                iter(
                    [
                        XY(400, 53),
                        XY(600, 52),
                        XY(10_000, 500),
                        XY(1_000, 1_000),
                    ]
                ),
                allow_empty=allow_empty,
                lead=25,
                avoid_orphans=avoid_orphans,
                align=align,
                params=PARAMS,
            )
        )
        linecounts = [len(c.lines) for c in shaped]
        assert linecounts == [2, 2, 1]
        assert plaintext(words).strip() == plaintext(shaped).strip()

    @pytest.mark.parametrize("avoid_orphans", [True, False])
    @pytest.mark.parametrize("allow_empty", [True, False])
    @pytest.mark.parametrize("align", [Align.LEFT, Align.JUSTIFY])
    def test_fixing_orphan_not_possible_because_last_column_is_very_wide(
        self, align, avoid_orphans, allow_empty, words
    ):
        shaped = list(
            shape(
                iter(words),
                iter([XY(500, 51), XY(600, 76), XY(10_000, 153)]),
                allow_empty=allow_empty,
                lead=25,
                avoid_orphans=avoid_orphans,
                align=align,
                params=PARAMS,
            )
        )
        linecounts = [len(c.lines) for c in shaped]
        assert linecounts == [2, 3, 1]
        assert plaintext(words).strip() == plaintext(shaped).strip()

    @pytest.mark.parametrize("allow_empty", [True, False])
    def test_fixing_orphan_leads_to_many_more_columns(
        self, allow_empty, words
    ):
        shaped = list(
            shape(
                iter(words),
                iter(
                    [
                        XY(500, 51),
                        XY(1_120, 76),
                        # solving an orphan here leads to many more columns
                        # because the previous column is relatively wide
                        XY(210, 76),
                        XY(210, 76),
                        # this in turn creates another fixable orphan here
                        XY(210, 76),
                        XY(210, 76),
                        XY(210, 76),
                        XY(10_000, 10_000),
                    ]
                ),
                allow_empty=allow_empty,
                lead=25,
                avoid_orphans=True,
                align=Align.JUSTIFY,
                params=PARAMS,
            )
        )
        linecounts = [len(c.lines) for c in shaped]
        assert linecounts == [2, 2, 3, 2, 2]
        assert plaintext(words).strip() == plaintext(shaped).strip()


class TestColumnQueue:
    def test_example(self):
        columns = [
            XY(40, 10),  # fits 3 lines
            XY(30, 20),  # fits 6 lines
            XY(25, 1),  # fits 1 line (minimum)
            XY(50, 11),  # fits 3 lines
        ]
        q = ColumnQueue(columns, lead=3, allow_empty=True)
        assert q.line_length(0) == 40
        assert q.line_length(0) == 40
        assert q.line_length(2) == 40
        assert q.line_length(4) == 30
        assert q.line_length(1) == 40
        assert q.line_length(11) == 50
        assert q.line_length(8) == 30
        assert q.line_length(1) == 40
        assert q.line_length(10) == 50
        assert q.line_length(9) == 25

    def test_first_column_allow_empty(self):
        columns = [XY(30, 1), XY(50, 10_000)]
        q = ColumnQueue(columns, lead=3, allow_empty=False)
        assert q.line_length(1) == 50
        assert q.line_length(0) == 30

        q_allows_empty = ColumnQueue(columns, lead=3, allow_empty=True)
        assert q_allows_empty.line_length(1) == 50
        assert q_allows_empty.line_length(0) == 50


def _linewidth(ln: Line) -> float:
    return sum(w.width for w in ln.words)


@plaintext.register
def _(ws: Fragment) -> str:
    return plaintext(ws.txt)
