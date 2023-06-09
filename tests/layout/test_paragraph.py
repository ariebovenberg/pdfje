from __future__ import annotations

import pytest

from pdfje import red
from pdfje.common import XY, Align
from pdfje.layout.common import ColumnFill
from pdfje.layout.paragraph import LinebreakParams, Paragraph
from pdfje.page import Column
from pdfje.resources import Resources
from pdfje.style import Style
from pdfje.vendor.hyphenate import hyphenate_word

from ..common import LOREM_IPSUM, plaintext

STYLE = Style(italic=True, color=red, hyphens=hyphenate_word).setdefault()


@pytest.fixture
def res() -> Resources:
    return Resources()


def test_paragraph_init():
    assert Paragraph("Hello world") == Paragraph(
        ["Hello world"],
        style=Style.EMPTY,
        align=Align.LEFT,
        indent=0,
        avoid_orphans=True,
        optimal=LinebreakParams(
            tolerance=1,
            hyphen_penalty=1000,
            consecutive_hyphen_penalty=1000,
            fitness_diff_penalty=1000,
        ),
    )
    assert Paragraph(
        "Hello world", style="#003311", align="center", indent=2, optimal=False
    ) == Paragraph(
        ["Hello world"],
        style=Style(color="#003311"),
        align=Align.CENTER,
        indent=2,
        avoid_orphans=True,
        optimal=None,
    )


@plaintext.register
def _(f: ColumnFill) -> str:
    # It isn't always valid to assume a space character between columns, but
    # it's good enough for the test data.
    plain = "".join(plaintext(para) for _, para in f.blocks).strip()
    if plain:
        plain += " "
    return plain


def linecounts(filled: list[ColumnFill]) -> list[int]:
    return [
        sum(len(para.lines) for _, para in f.blocks)  # type: ignore
        for f in filled
    ]


class TestParagraphFill:
    def test_empty(self, res: Resources):
        cols = [
            ColumnFill(Column(XY(80, 40), 205, 210), (), 105),
            ColumnFill(Column(XY(350, 40), 195, 190), (), 110),
            ColumnFill(Column(XY(350, 40), 200, 200), (), 90),
        ]
        p = Paragraph("", optimal=False)
        filled = list(p.into_columns(res, STYLE, iter(cols)))
        assert len(filled) == 1
        assert plaintext(filled) == ""

    def test_everything_fits_on_one_page(self, res: Resources):
        cols = [
            ColumnFill(Column(XY(80, 40), 400, 800), (), 800),
            ColumnFill(Column(XY(350, 40), 405, 750), (), 750),
            ColumnFill(Column(XY(350, 40), 300, 780), (), 780),
            ColumnFill(Column(XY(350, 40), 300, 780), (), 780),
        ]
        p = Paragraph(LOREM_IPSUM, optimal=False)
        filled = list(p.into_columns(res, STYLE, iter(cols)))
        assert len(filled) == 1
        assert plaintext(filled).strip() == LOREM_IPSUM.replace("\n", " ")

    @pytest.mark.parametrize("optimal", [False, True])
    @pytest.mark.parametrize("avoid_orphans", [True, False])
    def test_spread_across_pages(
        self, res: Resources, avoid_orphans: bool, optimal: bool
    ):
        cols = [
            ColumnFill(Column(XY(80, 40), 400, 800), (), 100),
            ColumnFill(Column(XY(350, 40), 150, 50), (), 50),
            ColumnFill(Column(XY(350, 40), 300, 780), (), 780),
            ColumnFill(Column(XY(350, 40), 300, 780), (), 780),
        ]
        p = Paragraph(
            LOREM_IPSUM, avoid_orphans=avoid_orphans, optimal=optimal
        )
        filled = list(p.into_columns(res, STYLE, iter(cols)))
        assert len(filled) == 3
        assert linecounts(filled) == [6, 3, 41]
        assert plaintext(filled).strip() == LOREM_IPSUM.replace("\n", " ")

    def test_column_lookahead(self, res: Resources):
        cols = [
            ColumnFill(Column(XY(80, 40), 400, 800), (), 100),
            ColumnFill(Column(XY(350, 40), 400, 100), (), 100),
            ColumnFill(Column(XY(350, 40), 300, 50), (), 50),
            ColumnFill(Column(XY(350, 40), 320, 32), (), 32),
            ColumnFill(Column(XY(350, 40), 300, 800), (), 800),
        ]
        p = Paragraph(LOREM_IPSUM, optimal=True)
        filled = list(p.into_columns(res, STYLE, iter(cols)))
        assert len(filled) == 5
        assert linecounts(filled) == [6, 6, 3, 2, 29]
