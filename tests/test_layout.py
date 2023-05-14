import pytest

from pdfje.common import XY
from pdfje.layout import (
    Align,
    Column,
    ColumnFill,
    LineGroup,
    Paragraph,
    layout_par,
)
from pdfje.style import Style
from pdfje.typeset.common import Stretch
from pdfje.typeset.lines import Line, Wrapper

from .common import RED, STATE


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


class TestColumn:
    def test_init(self):
        assert Column((1, 2), 3, 4) == Column(XY(1, 2), 3, 4)


class TestLayoutParagraph:
    def test_empty(self):
        wrap = Wrapper.start([], STATE, 0)
        layout = layout_par(
            wrap,
            ColumnFill(Column(XY(10, 10), 100, 100), [], 30),
            Align.LEFT,
        )
        try:
            next(layout)
        except StopIteration as e:
            assert e.value == ColumnFill(
                Column(XY(10, 10), 100, 100),
                [LineGroup([Line((), 0, 0)], Align.LEFT, 100, STATE.lead)],
                30 - STATE.lead,
            )
        else:
            pytest.fail("Expected StopIteration")

    # def test_enough_space(self):
    #     wrap = Wrapper.start(
    #         [
    #             Stretch(
    #                 RED,
    #                 "Simple is better than complex. "
    #                 "Complex is better than complicated.",
    #             )
    #         ],
    #         STATE,
    #         0,
    #     )
    #     layout = layout_par(
    #         wrap,
    #         ColumnFill(Column(XY(10, 10), 500, 100), [], 30),
    #         0,
    #         Align.LEFT,
    #     )
    #     col = next(layout)
    #     breakpoint()
    #     try:
    #         next(layout)
    #     except StopIteration as e:
    #         assert e.value == ColumnFill(Column(XY(10, 10), 100, 100), [], 30)
    #     else:
    #         pytest.fail("Expected StopIteration")
