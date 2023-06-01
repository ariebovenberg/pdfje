from __future__ import annotations

import re
from typing import Callable, Iterator, Sequence, Tuple, cast
from unittest.mock import ANY

import pytest

from pdfje import Document, Page
from pdfje.draw import Rect, Text
from pdfje.fonts import times_roman
from pdfje.style import Style
from pdfje.typeset.tex import (
    BIG,
    Box,
    Break,
    NoFeasibleBreaks,
    optimum_fit,
    ratio_justified,
    ratio_ragged,
)

from ..common import approx


def spaced_box(
    measure: float,
    stretch: float = 0,
    shrink: float = 0,
    space: float = 0,
    no_break: bool = False,
):
    return Box(
        measure,
        stretch,
        shrink,
        measure + space,
        incl_hyphen=measure,
        hyphenated=False,
        no_break=no_break,
    )


class TestRatioJustified:
    def test_no_stretch_or_shrink(self):
        assert ratio_justified(
            10,
            3,
            2,
            spaced_box(30, stretch=3, shrink=2, space=5),
            100,
        ) == approx(BIG + (20 / 100))
        assert ratio_justified(
            10, 3, 2, spaced_box(30, space=5, stretch=3, shrink=2), 1
        ) == approx(BIG + 20)

    def test_exact_size(self):
        assert (
            ratio_justified(
                10, 3, 2, spaced_box(30, space=5, stretch=3, shrink=2), 20
            )
            == 0
        )

    def test_needs_shrink(self):
        assert ratio_justified(
            10, 3, 2, spaced_box(30, space=5, stretch=5, shrink=7), 18
        ) == approx(-(20 - 18) / (7 - 2))

    def test_needs_stretch(self):
        assert ratio_justified(
            10, 3, 2, spaced_box(30, space=5, stretch=5, shrink=7), 22
        ) == approx((22 - 20) / (5 - 3))


class TestRatioRagged:
    def test_enough_space(self):
        result = ratio_ragged(
            10,
            3,
            2,
            spaced_box(30, stretch=3, shrink=2, space=5),
            100,
        )
        assert result > 1
        assert result > ratio_ragged(
            10,
            3,
            2,
            spaced_box(30, stretch=3, shrink=2, space=5),
            90,
        )

    def test_exact_size(self):
        assert (
            ratio_ragged(
                10, 3, 2, spaced_box(30, space=5, stretch=3, shrink=2), 20
            )
            == 0
        )

    def test_not_enought_space(self):
        assert (
            ratio_ragged(
                10, 3, 2, spaced_box(30, space=5, stretch=3, shrink=2), 15
            )
            == -BIG
        )


class TestOptimalBreaks:
    def test_empty(self):
        assert optimum_fit([], lambda _: 100, 1) == []

    def test_fits_in_one_line(self):
        boxes = [
            spaced_box(10, space=5, stretch=0, shrink=0),
            spaced_box(45, space=5, stretch=10, shrink=5),
            spaced_box(90, space=0, stretch=20, shrink=10),
        ]
        assert optimum_fit(boxes, lambda _: 100, 1) == [
            Break(3, approx(0), ANY)
        ]

    def test_fits_in_one_line_even_if_way_too_short(self):
        boxes = [
            spaced_box(10, space=5, stretch=0, shrink=0),
            spaced_box(45, space=5, stretch=10, shrink=5),
            spaced_box(90, space=0, stretch=20, shrink=10),
        ]
        assert optimum_fit(boxes, lambda _: 1000, 1) == [
            Break(3, approx(0.0), ANY)
        ]

    def test_fits_in_one_line_after_shrink(self):
        boxes = [
            spaced_box(10, space=5, stretch=0, shrink=0),
            spaced_box(45, space=5, stretch=10, shrink=6),
            spaced_box(90, space=0, stretch=20, shrink=12),
        ]
        assert optimum_fit(boxes, lambda _: 89, 1) == [
            Break(3, approx(-(90 - 89) / 12), ANY)
        ]

    def test_no_breaks_within_tolerance(self):
        boxes = [
            spaced_box(10, space=5, stretch=0, shrink=0),
            spaced_box(90, space=5, stretch=5, shrink=3),
            # -- need a break here, but it's not feasible within tolerance --
            spaced_box(150, space=5, stretch=10, shrink=6),
            spaced_box(200, space=5, stretch=15, shrink=9),
            spaced_box(250, space=5, stretch=20, shrink=12),
        ]
        with pytest.raises(NoFeasibleBreaks):
            optimum_fit(boxes, lambda _: 130, 1)

    def test_nobreak_box(self):
        boxes = [
            spaced_box(10, space=5, stretch=0, shrink=0),
            spaced_box(90, space=5, stretch=5, shrink=3),
            spaced_box(125, space=5, stretch=7, shrink=4, no_break=True),
            # -- need a break here, but it's not feasible because no_break --
            spaced_box(150, space=5, stretch=10, shrink=6),
            spaced_box(200, space=5, stretch=15, shrink=9),
            spaced_box(250, space=5, stretch=20, shrink=12),
        ]
        with pytest.raises(NoFeasibleBreaks):
            optimum_fit(boxes, lambda _: 130, 1)

    def test_one_obvious_optimum(self):
        boxes = [
            spaced_box(10, space=5, stretch=0, shrink=0),
            spaced_box(45, space=5, stretch=10, shrink=6),
            spaced_box(90, space=0, stretch=20, shrink=12),
            # -- expect break here --
            spaced_box(160, space=10, stretch=20, shrink=12),
            Box(
                180,
                stretch=30,
                shrink=18,
                incl_space=180,
                incl_hyphen=180 + 12,
                hyphenated=True,
                no_break=False,
            ),
            # -- expect break here --
            spaced_box(250, space=10, stretch=30, shrink=18),
            spaced_box(295, space=0, stretch=40, shrink=26),
        ]
        assert optimum_fit(boxes, {0: 100, 1: 102, 2: 110}.__getitem__, 1) == [
            Break(3, approx((100 - 90) / 20), ANY),
            Break(5, approx((102 - (180 + 12 - 90)) / (18 - 12)), ANY),
            Break(7, approx((110 - (295 - 180)) / (26 - 18)), ANY),
        ]

    @pytest.mark.parametrize(
        "width, tol, expect",
        [
            (
                22,
                1.5,
                """\
In olden times when wishing still helped one, there
lived a king whose daughters were all beautiful, but the
youngest was so beautiful that the sun itself, which has
seen so much, was astonished whenever it shone in her
face. Close by the king’s castle lay a great dark forest,
and under an old lime-tree in the forest was a well, and
when the day was very warm, the king’s child went out
into the forest and sat down by the side of the cool foun-
tain, and when she was bored she took a golden ball,
and threw it up on high and caught it, and this ball was
her favorite plaything.""",
            ),
            # bigger tolerance yields the same result
            (
                22,
                10,
                """\
In olden times when wishing still helped one, there
lived a king whose daughters were all beautiful, but the
youngest was so beautiful that the sun itself, which has
seen so much, was astonished whenever it shone in her
face. Close by the king’s castle lay a great dark forest,
and under an old lime-tree in the forest was a well, and
when the day was very warm, the king’s child went out
into the forest and sat down by the side of the cool foun-
tain, and when she was bored she took a golden ball,
and threw it up on high and caught it, and this ball was
her favorite plaything.""",
            ),
            # smaller width
            (
                10,
                5,
                """\
In olden times when
wishing still helped one,
there lived a king whose
daughters were all beau-
tiful, but the youngest
was so beautiful that the
sun itself, which has seen
so much, was astonished
whenever it shone in her
face. Close by the king’s
castle lay a great dark
forest, and under an old
lime-tree in the forest
was a well, and when
the day was very warm,
the king’s child went out
into the forest and sat
down by the side of the
cool fountain, and when
she was bored she took a
golden ball, and threw it
up on high and caught it,
and this ball was her favo-
rite plaything.""",
            ),
            # narrow width
            (
                6,
                20,
                """\
In olden times
when wishing
still helped
one, there
lived a king
whose daugh-
ters were all
beautiful, but
the young-
est was so
beautiful that
the sun itself,
which has
seen so much,
was astonished
whenever it
shone in her
face. Close by
the king’s cas-
tle lay a
great dark for-
est, and under
an old lime-
tree in the
forest was a
well, and when
the day was
very warm, the
king’s child
went out into
the forest and
sat down by
the side of the
cool fountain,
and when she
was bored she
took a golden
ball, and threw
it up on high
and caught it,
and this ball
was her favo-
rite plaything.""",
            ),
        ],
    )
    def test_example_text(self, width, tol, expect):
        breaks = optimum_fit(BOXES, lambda _: width, tol=tol)
        lines = _into_lines(breaks, WORDS)
        # printlines(lines)
        # visualize(f"example-wrap-{width}.pdf", lines, width, 12)
        assert "\n".join(ln for ln, _ in lines) == expect

    @pytest.mark.parametrize(
        "width, tol, expect",
        [
            (
                lambda i: 10 + i,
                5,
                """\
In olden times when
wishing still helped one,
there lived a king whose
daughters were all beautiful, but
the youngest was so beautiful that
the sun itself, which has seen so much,
was astonished whenever it shone in her
face. Close by the king’s castle lay a great
dark forest, and under an old lime-tree in the
forest was a well, and when the day was very
warm, the king’s child went out into the forest and
sat down by the side of the cool fountain, and when
she was bored she took a golden ball, and threw it up on
high and caught it, and this ball was her favorite plaything.""",
            ),
            (
                lambda i: 10 if i < 6 else 20,
                5,
                """\
In olden times when
wishing still helped one,
there lived a king whose
daughters were all beauti-
ful, but the youngest was
so beautiful that the sun
itself, which has seen so much, was astonished
whenever it shone in her face. Close by the king’s
castle lay a great dark forest, and under an old lime-
tree in the forest was a well, and when the day was
very warm, the king’s child went out into the forest
and sat down by the side of the cool fountain, and
when she was bored she took a golden ball, and
threw it up on high and caught it, and this ball was
her favorite plaything.""",
            ),
        ],
    )
    def test_variable_line_width(self, width, tol, expect):
        breaks = optimum_fit(BOXES, width, tol=tol)
        lines = _into_lines(breaks, WORDS)
        assert "\n".join(ln for ln, _ in lines) == expect

    def test_width_narrower_than_largest_box(self):
        max_width = max(map(times_roman.regular.width, WORDS))
        breaks = optimum_fit(BOXES, lambda _: max_width, tol=float("inf"))
        lines = _into_lines(breaks, WORDS)
        assert 100 > len(lines) > 90

    def test_ragged(self):
        breaks = optimum_fit(BOXES, lambda _: 25, tol=1, ragged=True)
        lines = _into_lines(breaks, WORDS)
        # printlines(lines)
        # visualize("example-ragged-sqrt.pdf", lines, 25, 12)
        assert (
            "\n".join(ln for ln, _ in lines)
            == """\
In olden times when wishing still helped one, there lived a
king whose daughters were all beautiful, but the youngest was
so beautiful that the sun itself, which has seen so much, was
astonished whenever it shone in her face. Close by the king’s
castle lay a great dark forest, and under an old lime-tree in
the forest was a well, and when the day was very warm, the
king’s child went out into the forest and sat down by the
side of the cool fountain, and when she was bored she took
a golden ball, and threw it up on high and caught it, and this
ball was her favorite plaything."""
        )

    def test_very_narrow_width(self):
        breaks = optimum_fit(BOXES, lambda _: 0.01, tol=float("inf"))
        lines = _into_lines(breaks, WORDS)
        # i.e. every box should get its own line
        # FUTURE: the last box somehow isn't hyphenated.
        #         Low prio bug, since this is a pathological case.
        assert len(lines) == len(BOXES) - 1


EXAMPLE = """\
In olden times when wish\u00ading still helped one, there lived a king \
whose daugh\u00adters were all beau\u00adti\u00adful, but the young\u00adest \
was so beau\u00adti\u00adful that the sun it\u00adself, which has seen so \
much, was aston\u00adished when\u00adever it shone in her face. Close by the \
king\u2019s cas\u00adtle lay a great dark for\u00adest, and under an old lime-\
tree in the for\u00adest was a well, and when the day was very warm, the king\
\u2019s child went out into the for\u00adest and sat down by the side of the \
cool foun\u00adtain, and when she was bored she took a golden ball, and threw \
it up on high and caught it, and this ball was her favo\u00adrite play\u00ad\
thing.\
"""


_boxes = re.compile(r"([\w,.:\u2019]+-?)(\u00ad?)([ \\Z]?)").findall


def printlines(ls: Sequence[tuple[str, Break]]) -> None:
    """Print lines with their break information, for debugging."""
    maxlen = max(len(ln) for ln, _ in ls)
    for ln, brk in ls:
        print(f"{ln: <{maxlen+4}} ({brk.adjust:+.3f}) [{brk.demerits:,.0f}]")


def visualize(
    fname: str,
    ls: Sequence[tuple[str, Break]],
    width: float,
    fontsize: float = 10,
) -> None:
    """Visualize the line breaks in a PDF. Useful for debugging how the
    text appears with variable character widths."""
    y = width * fontsize
    Document(
        [
            Page(
                [
                    Rect((50, 720), y, -800),
                    Text(
                        (50, 720),
                        "\n".join(ln for ln, _ in ls),
                        style=Style(font=times_roman, size=fontsize),
                    ),
                    Text(
                        (50 + y + 20, 720),
                        "\n".join(f"{brk.adjust:.3f}" for _, brk in ls),
                        style=times_roman,
                    ),
                ]
            )
        ]
    ).write(fname)


def _into_lines(
    bs: Sequence[Break], ws: Sequence[str]
) -> list[tuple[str, Break]]:
    lines = []
    prev = 0
    for brk in bs:
        ln = list(ws[prev : brk.pos])  # noqa
        if ln[-1].endswith(" "):
            ln[-1] = ln[-1].rstrip()
        elif not ln[-1].endswith("-"):
            ln[-1] += "-"
        lines.append("".join(ln))
        prev = brk.pos
    lines[-1] = lines[-1].rstrip("-")
    return list(zip(lines, bs))


def _into_boxes(
    s: str, width_of: Callable[[str], float]
) -> Iterator[tuple[str, Box]]:
    width = 0.0
    shrink = 0.0
    stretch = 0.0
    for word, hyphen, space in _boxes(s):
        width += width_of(word)
        if hyphen:
            yield (
                word,
                Box(
                    width,
                    stretch=stretch,
                    shrink=shrink,
                    incl_space=width,
                    incl_hyphen=width + width_of("-"),
                    hyphenated=True,
                    no_break=False,
                ),
            )
        elif space:
            width += width_of(space)
            yield (
                word + space,
                spaced_box(width, stretch, shrink, space=width_of(space)),
            )
            shrink += width_of(space) * 0.35
            stretch += width_of(space) * 0.5
        else:
            yield (word, spaced_box(width, stretch, shrink, space=0))


WORDS, BOXES = cast(
    Tuple[Tuple[str, ...], Tuple[Box, ...]],
    zip(*_into_boxes(EXAMPLE, times_roman.regular.width)),
)
