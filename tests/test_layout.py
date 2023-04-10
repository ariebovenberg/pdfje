from pdfje import XY, Column


class TestColumn:
    def test_init(self):
        assert Column((1, 2), 3, 4) == Column(XY(1, 2), 3, 4)
