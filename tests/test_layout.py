from pdfje.common import XY
from pdfje.layout import Align, Column, Paragraph
from pdfje.style import Style


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
