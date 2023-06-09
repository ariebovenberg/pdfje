from __future__ import annotations

import pytest

from pdfje import XY
from pdfje.layout import Rule
from pdfje.layout.common import ColumnFill
from pdfje.page import Column
from pdfje.resources import Resources
from pdfje.style import StyleFull

STYLE = StyleFull.DEFAULT

COLUMNS = [
    col := ColumnFill(Column(XY(80, 40), 205, 210), (), 20),
    ColumnFill(Column(XY(350, 40), 195, 190), (), 110),
    ColumnFill(Column(XY(350, 40), 200, 200), (), 90),
]


@pytest.mark.skip(reason="not yet implemented")
def test_into_columns_skipped_because_of_break():
    r = Rule(margin=(12, 0, 10, 0))
    filled = list(r.into_columns(Resources(), STYLE, iter(COLUMNS)))
    assert len(filled) == 1
    assert filled[0] is COLUMNS[0]
