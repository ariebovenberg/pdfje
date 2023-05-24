from __future__ import annotations

from typing import Iterator

import pytest

from pdfje import Page, red
from pdfje.common import XY
from pdfje.layout import (
    Align,
    Column,
    ColumnFill,
    PageFill,
    Paragraph,
    fill_columns,
)
from pdfje.resources import Resources
from pdfje.style import Style
from pdfje.units import A3, A4

STYLE = Style(italic=True, color=red).setdefault()


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


# class TestParagraphFill:
#     def test_empty(self, res: Resources):
#         cols = [
#             ColumnFill(Column(XY(80, 40), 205, 210), (), 105),
#             ColumnFill(Column(XY(350, 40), 195, 190), (), 110),
#             ColumnFill(Column(XY(350, 40), 200, 200), (), 90),
#         ]
#         p = Paragraph("")
#         list(p.fill(res, STYLE, iter(cols)))


class TestColumn:
    def test_init(self):
        assert Column((1, 2), 3, 4) == Column(XY(1, 2), 3, 4)


def test_fill_columns():
    pages = [
        PageFill(
            Page(size=A3),
            (ColumnFill(Column(XY(40, 40), 190, 180), (), 100),),
            (ColumnFill(Column(XY(300, 40), 200, 200), (), 10),),
        ),
        PageFill(Page(size=A4), (), ()),
        PageFill(
            Page(size=A3.flip()),
            (
                ColumnFill(Column(XY(80, 40), 205, 210), (), 100),
                ColumnFill(Column(XY(350, 40), 195, 190), (), 100),
            ),
            (),
        ),
        PageFill(
            Page(size=A4.flip()),
            (
                ColumnFill(Column(XY(40, 40), 210, 170), (), 100),
                ColumnFill(Column(XY(300, 40), 195, 160), (), 100),
            ),
            (),
        ),
    ]

    def dummy_filler(cs: Iterator[ColumnFill]) -> Iterator[ColumnFill]:
        for char in "abc":
            yield next(cs).add([char.encode()], 40)
        next(cs)  # consume one more than needed

    doc, completed = fill_columns(iter(pages), dummy_filler)
    assert list(doc) == pages[3:]
    assert completed == [
        PageFill(
            Page(size=A3),
            (),
            (
                ColumnFill(Column(XY(300, 40), 200, 200), (), 10),
                ColumnFill(Column(XY(40, 40), 190, 180), ([b"a"],), 60),
            ),
        ),
        PageFill(Page(size=A4), (), ()),
        PageFill(
            Page(size=A3.flip()),
            (),
            (
                ColumnFill(Column(XY(80, 40), 205, 210), ([b"b"],), 60),
                ColumnFill(Column(XY(350, 40), 195, 190), ([b"c"],), 60),
            ),
        ),
    ]
