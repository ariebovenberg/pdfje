from pathlib import Path

import pytest

from pdfje import (
    AutoPage,
    Document,
    Page,
    Paragraph,
    Rotation,
    Rule,
    Style,
    courier,
    helvetica,
    times_roman,
)
from pdfje.draw import Box, Line, Polyline, String
from pdfje.fonts.common import TrueType

try:
    import fontTools  # noqa
except ModuleNotFoundError:
    HAS_FONTTOOLS = False
else:
    HAS_FONTTOOLS = True

HERE = Path(__file__).parent
ZALGO = "t̶͈̓̕h̴̩̖͋̈́e̷̛̹ ̴̠͎̋̀p̷̦̔o̴̘͔̓n̸̞̙̐̕y̷̙̠̍ ̶̱̞̃h̶͈̮̅̆ë̸͍̟́̓ ̷̳̜̂c̵̢̡͋o̸̰̫͗̽m̷̨̿̕e̶̛̗̲͆s̸̨̭̐"  # noqa
DEJAVU = TrueType(
    HERE / "resources/DejaVuSansCondensed.ttf",
    HERE / "resources/DejaVuSansCondensed-Bold.ttf",
    HERE / "resources/DejaVuSansCondensed-Oblique.ttf",
    HERE / "resources/DejaVuSansCondensed-BoldOblique.ttf",
)
ROBOTO = TrueType(
    HERE / "resources/Roboto-Regular.ttf",
    HERE / "resources/Roboto-Bold.ttf",
    HERE / "resources/Roboto-Italic.ttf",
    HERE / "resources/Roboto-BoldItalic.ttf",
)
ALL_ANGLES: list[Rotation] = [0, 90, 180, 270]


class TestWrite:
    def test_no_arguments(self):
        output = Document().write()
        assert isinstance(next(output), bytes)
        assert b"".join(output).endswith(b"%%EOF\n")

    def test_string(self, tmpdir):
        loc = str(tmpdir / "foo.pdf")
        Document().write(loc)
        assert Path(loc).read_bytes().endswith(b"%%EOF\n")

    def test_path(self, tmpdir):
        loc = Path(tmpdir / "foo.pdf")
        Document().write(loc)
        assert loc.read_bytes().endswith(b"%%EOF\n")

    def test_fileobj(self, tmpdir):
        loc = Path(tmpdir / "foo.pdf")
        with loc.open(mode="wb") as f:
            Document().write(f)
        assert loc.read_bytes().endswith(b"%%EOF\n")


def test_empty(outfile):
    Document().write(outfile)
    assert Document() == Document([Page()])


def test_one_string():
    assert Document("hello") == Document([AutoPage("hello")])


# TODO: test weird control characters


def test_autopage(outfile):
    Document(
        [
            AutoPage(
                [
                    Paragraph(LOREM_IPSUM),
                    Paragraph(
                        # TODO make this work
                        LOREM_IPSUM.replace("\n", "\n\n"),
                        Style(
                            color=(0.5, 0, 0), font=times_roman, italic=True
                        ),
                    ),
                    Rule(),
                    Paragraph(
                        ZEN_OF_PYTHON * 4,
                        Style(
                            size=17,
                            line_spacing=1.1,
                            color=(0, 0.5, 0),
                            font=helvetica,
                            bold=True,
                        ),
                    ),
                    Rule(),
                    Paragraph(
                        ZEN_OF_PYTHON.replace("\n", " ") * 20,
                        Style(size=2, font=times_roman),
                    ),
                ]
            ),
            AutoPage(
                [Paragraph(LOREM_IPSUM, Style(line_spacing=3, font=courier))]
            ),
        ]
    ).write(outfile)


def test_drawing_on_pages(outfile):
    Document(
        [
            Page([String("First!", (250, 400), Style(size=50))]),
            Page([String(ZEN_OF_PYTHON, (50, 720), Style(size=16))]),
            Page(
                [
                    Polyline([(50, 650), (50, 600), (100, 600)], closed=True),
                    Box((50, 700), 500, 70),
                    Line((50, 690), (450, 690)),
                    String(
                        "Big red text, and LINES!",
                        (50, 710),
                        Style(size=40, color=(1, 0, 0)),
                    ),
                ]
            ),
        ]
    ).write(outfile)


def test_rotate(outfile):
    Document(
        [
            Page(
                [String(f"rotated {angle}", (150, 400), style=Style(size=60))],
                rotate=angle,
            )
            for angle in ALL_ANGLES
        ]
    ).write(outfile)


@pytest.mark.skipif(
    not HAS_FONTTOOLS, reason="fonttools not installed (optional)"
)
def test_fonts(outfile):
    Document(
        [
            # Page(
            #     String(
            #         [
            #             Span("Cheers, Cour®ier\n", courier),
            #             Span("Hey hélvetica!\n", helvetica),
            #             Span("Hí RobotὍ...\n", ROBOTO),
            #             Span("Hello 𝌷 agaîn,\nDejaVü! Kerning AWAY!\n", DEJAVU,
            #             Span("Good †imes", times_roman),
            #             Span("(check the above text can be copied!)", ROBOTO),
            #             Span("unknown char (builtin font): ∫", helvetica),
            #             Span("unknown char (embedded font): ⟤", DEJAVU),
            #             Span(f"zalgo: {ZALGO}", DEJAVU),
            #             Span("zero byte: \x00", DEJAVU),
            #         ]
            #     )
            # ),
            Page(
                String(
                    txt,
                    (50, 730 - i * 35 + 50),
                    Style(font=typeface),  # type: ignore[arg-type]
                )
                for i, (txt, typeface) in enumerate(
                    [
                        ("Cheers, Cour®ier", courier),
                        ("Hey hélvetica!", helvetica),
                        ("Hí RobotὍ... ", ROBOTO),
                        ("Hello 𝌷 agaîn,\nDejaVü! Kerning AWAY!", DEJAVU),
                        ("Good †imes", times_roman),
                        ("(check the above text can be copied!)", ROBOTO),
                        ("unknown char (builtin font): ∫", helvetica),
                        ("unknown char (embedded font): ⟤", DEJAVU),
                        (f"zalgo: {ZALGO}", DEJAVU),
                        ("zero byte: \x00", DEJAVU),
                    ]
                )
            ),
            AutoPage(
                [
                    Paragraph(LOREM_IPSUM, Style(font=ROBOTO)),
                    Paragraph(
                        LOREM_IPSUM,
                        Style(
                            color=(0.5, 0, 0),
                            size=10,
                            font=DEJAVU,
                            italic=True,
                        ),
                    ),
                ]
            ),
        ],
    ).write(outfile)


LOREM_IPSUM = """\
Lorem ipsum dolor sit amet, consectetur adipiscing elit. \
Integer sed aliquet justo. Donec eu ultricies velit, porta pharetra massa. \
Ut non augue a urna iaculis vulputate ut sit amet sem. \
Nullam lectus felis, rhoncus sed convallis a, egestas semper risus. \
Fusce gravida metus non vulputate vestibulum. \
Vestibulum ante ipsum primis in faucibus orci luctus et ultrices posuere \
cubilia curae; Donec placerat suscipit velit. \
Mauris tincidunt lorem a eros eleifend tincidunt. \
Maecenas faucibus imperdiet massa quis pretium. Integer in lobortis nisi. \
Mauris at odio nec sem volutpat aliquam. Aliquam erat volutpat. \

Fusce at vehicula justo. Vestibulum eget viverra velit. \
Vivamus et nisi pulvinar, elementum lorem nec, volutpat leo. \
Aliquam erat volutpat. Sed tristique quis arcu vitae vehicula. \
Morbi egestas vel diam eget dapibus. Donec sit amet lorem turpis. \
Maecenas ultrices nunc vitae enim scelerisque tempus. \
Maecenas aliquet dui non hendrerit viverra. \
Aliquam fringilla, est sit amet gravida convallis, elit ipsum efficitur orci, \
eget convallis neque nunc nec lorem. Nam nisl sem, \
tristique a ultrices sed, finibus id enim. \

Etiam vel dolor ultricies, gravida felis in, vestibulum magna. \
In diam ex, elementum ut massa a, facilisis sollicitudin lacus. \
Integer lacus ante, ullamcorper ac mauris eget, rutrum facilisis velit. \
Mauris eu enim efficitur, malesuada ipsum nec, sodales enim. \
Nam ac tortor velit. Suspendisse ut leo a felis aliquam dapibus ut a justo. \
Vestibulum sed commodo tortor. Sed vitae enim ipsum. \
Duis pellentesque dui et ipsum suscipit, in semper odio dictum. \

Sed in fermentum leo. Donec maximus suscipit metus. \
Nulla convallis tortor mollis urna maximus mattis. \
Sed aliquet leo ac sem aliquam, et ultricies mauris maximus. \
Cras orci ex, fermentum nec purus non, molestie venenatis odio. \
Etiam vitae sollicitudin nisl. Sed a ullamcorper velit. \

Aliquam congue aliquet eros scelerisque hendrerit. Vestibulum quis ante ex. \
Fusce venenatis mauris dolor, nec mattis libero pharetra feugiat. \
Pellentesque habitant morbi tristique senectus et netus et malesuada \
fames ac turpis egestas. Cras vitae nisl molestie augue finibus lobortis. \
In hac habitasse platea dictumst. Maecenas rutrum interdum urna, \
ut finibus tortor facilisis ac. Donec in fringilla mi. \
Sed molestie accumsan nisi at mattis. \
Integer eget orci nec urna finibus porta. \
Sed eu dui vel lacus pulvinar blandit sed a urna. \
Quisque lacus arcu, mattis vel rhoncus hendrerit, dapibus sed massa. \
Vivamus sed massa est. In hac habitasse platea dictumst. \
Nullam volutpat sapien quis tincidunt sagittis. \
"""

ZEN_OF_PYTHON = """\
Beautiful is better than ugly.
Explicit is better than implicit.
Simple is better than complex.
Complex is better than complicated.
Flat is better than nested.
Sparse is better than dense.
Readability counts.
Special cases aren't special enough to break the rules.
Although practicality beats purity.
Errors should never pass silently.
Unless explicitly silenced.
In the face of ambiguity, refuse the temptation to guess.
There should be one — and preferably only one — obvious way to do it.
Although that way may not be obvious at first unless you're Dutch.
Now is better than never.
Although never is often better than *right* now.
If the implementation is hard to explain, it's a bad idea.
If the implementation is easy to explain, it may be a good idea.
Namespaces are one honking great idea — let's do more of those!
"""
