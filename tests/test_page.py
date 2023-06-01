from pdfje import XY, Column, Page
from pdfje.draw import Circle
from pdfje.units import A5

from .common import approx


class TestPage:
    def test_default_column(self):
        p = Page(size=A5)
        assert len(p.columns) == 1
        assert p.columns[0].width < A5.x
        assert p.columns[0].height < A5.y

    def test_one_column_by_margins(self):
        [column] = Page(size=A5, margin=(20, 30)).columns
        assert column.origin.x == approx(30)
        assert column.origin.y == approx(20)
        assert column.width == approx(A5.x - 60)
        assert column.height == approx(A5.y - 40)

    def test_add(self):
        p = Page()
        p2 = p.add(Circle((0, 0), 10))
        assert p == Page()
        assert p2 == Page((Circle((0, 0), 10),))


class TestColumn:
    def test_init(self):
        assert Column((1, 2), 3, 4) == Column(XY(1, 2), 3, 4)
