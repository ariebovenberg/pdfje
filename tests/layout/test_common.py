from typing import Iterator

from pdfje import XY, Column, Page
from pdfje.layout.common import ColumnFill, PageFill, fill_pages
from pdfje.units import A3, A4

PAGES = [
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


class TestFillPages:
    def test_empty(self):
        pages, filled = fill_pages(iter(PAGES), lambda _: iter(()))
        assert list(pages) == PAGES
        assert list(filled) == []

    def test_fills_one_page_partially(self):
        def dummy_filler(cs: Iterator[ColumnFill]) -> Iterator[ColumnFill]:
            yield next(cs).add([b"dummy content"], 40)

        pages, filled = fill_pages(iter(PAGES), dummy_filler)
        assert list(pages) == [
            PageFill(
                Page(size=A3),
                (
                    ColumnFill(
                        Column(XY(40, 40), 190, 180), ([b"dummy content"],), 60
                    ),
                ),
                (ColumnFill(Column(XY(300, 40), 200, 200), (), 10),),
            ),
            *PAGES[1:],
        ]
        assert list(filled) == []

    def test_fills_multiple_pages(self):
        def dummy_filler(cs: Iterator[ColumnFill]) -> Iterator[ColumnFill]:
            for char in "abc":
                yield next(cs).add([char.encode()], 40)
            next(cs)  # it's important we test consuming one more than yielded

        pages, filled = fill_pages(iter(PAGES), dummy_filler)
        assert list(pages) == [
            PageFill(
                Page(size=A3.flip()),
                (ColumnFill(Column(XY(350, 40), 195, 190), ([b"c"],), 60),),
                (ColumnFill(Column(XY(80, 40), 205, 210), ([b"b"],), 60),),
            ),
            *PAGES[3:],
        ]
        assert filled == [
            PageFill(
                Page(size=A3),
                (),
                (
                    ColumnFill(Column(XY(300, 40), 200, 200), (), 10),
                    ColumnFill(Column(XY(40, 40), 190, 180), ([b"a"],), 60),
                ),
            ),
            PageFill(Page(size=A4), (), ()),
        ]
