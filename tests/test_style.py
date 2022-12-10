from pdfje import RGB, Style


def test_parse_rgb():
    assert Style(color=(0, 1, 0)) == Style.DEFAULT.replace(color=RGB(0, 1, 0))
