from __future__ import annotations

from typing import Iterable, cast

import pytest

from pdfje import red
from pdfje.common import XY, Align
from pdfje.layout.common import ColumnFill
from pdfje.layout.paragraph import Paragraph, TypesetText
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
        ["Hello world"], style=Style.EMPTY, align=Align.LEFT, indent=0
    )
    assert Paragraph(
        "Hello world", style="#003311", align="center", indent=2
    ) == Paragraph(
        ["Hello world"],
        style=Style(color="#003311"),
        align=Align.CENTER,
        indent=2,
    )


def _plain(cs: Iterable[ColumnFill]) -> str:
    return "".join(
        "".join(map(plaintext, cast(TypesetText, para).lines))[:-1] + "\n"
        for f in cs
        for para in f.blocks
    ).strip()


class TestParagraphFill:
    def test_empty(self, res: Resources):
        cols = [
            ColumnFill(Column(XY(80, 40), 205, 210), (), 105),
            ColumnFill(Column(XY(350, 40), 195, 190), (), 110),
            ColumnFill(Column(XY(350, 40), 200, 200), (), 90),
        ]
        p = Paragraph("")
        filled = list(p.fill(res, STYLE, iter(cols)))
        assert len(filled) == 1
        assert _plain(filled) == ""

    def test_everything_fits_on_one_page(self, res: Resources):
        cols = [
            ColumnFill(Column(XY(80, 40), 400, 800), (), 800),
            ColumnFill(Column(XY(350, 40), 405, 750), (), 750),
            ColumnFill(Column(XY(350, 40), 300, 780), (), 780),
            ColumnFill(Column(XY(350, 40), 300, 780), (), 780),
        ]
        p = Paragraph(LOREM_IPSUM)
        filled = list(p.fill(res, STYLE, iter(cols)))
        assert len(filled) == 1
        assert _plain(filled) == LOREM_IPSUM

    def test_spread_across_pages(self, res: Resources):
        cols = [
            ColumnFill(Column(XY(80, 40), 400, 800), (), 100),
            ColumnFill(Column(XY(350, 40), 150, 50), (), 50),
            ColumnFill(Column(XY(350, 40), 300, 780), (), 780),
            ColumnFill(Column(XY(350, 40), 300, 780), (), 780),
        ]
        p = Paragraph(LOREM_IPSUM)
        filled = list(p.fill(res, STYLE, iter(cols)))
        assert len(filled) == 3
        assert _plain(filled).replace("\n", " ") == LOREM_IPSUM.replace(
            "\n", " "
        )
