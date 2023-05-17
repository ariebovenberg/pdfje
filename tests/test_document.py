from itertools import cycle, islice
from pathlib import Path

import pytest
from hypothesis import given
from hypothesis.strategies import text

from pdfje import XY, AutoPage, Document, Page, blue, lime, red
from pdfje.document import Rotation
from pdfje.draw import Circle, Ellipse, Line, Polyline, Rect, Text
from pdfje.fonts import TrueType, courier, helvetica, times_roman
from pdfje.layout import Block, Column, Paragraph, Rule
from pdfje.style import Span, Style, bold, italic, regular
from pdfje.units import A4, A5, A6, inch, mm

from .common import approx

try:
    import fontTools  # noqa
except ModuleNotFoundError:
    HAS_FONTTOOLS = False
else:
    HAS_FONTTOOLS = True

HERE = Path(__file__).parent
ZALGO = "t̶͈̓̕h̴̩̖͋̈́e̷̛̹ ̴̠͎̋̀p̷̦̔o̴̘͔̓n̸̞̙̐̕y̷̙̠̍ ̶̱̞̃h̶͈̮̅̆ë̸͍̟́̓ ̷̳̜̂c̵̢̡͋o̸̰̫͗̽m̷̨̿̕e̶̛̗̲͆s̸̨̭̐"  # noqa
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


class TestInit:
    def test_empty(self, outfile):
        Document().write(outfile)
        assert Document() == Document([Page()])

    def test_zero_pages(self):
        with pytest.raises(RuntimeError, match="at least one page"):
            list(Document(iter([])).write())

    def test_one_string(self):
        assert Document("hello") == Document([AutoPage("hello")])

    def test_one_block(self):
        assert Document(Rule()) == Document([AutoPage(Rule())])


@pytest.mark.slow
@given(s=text())
def test_exotic_strings(s, dejavu):
    assert b"".join(
        Document(
            [AutoPage([Paragraph(s, Style(font=dejavu)), Paragraph(s)])]
        ).write()
    ).endswith(b"%%EOF\n")


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
        assert p2 == Page([Circle((0, 0), 10)])


class TestAutopage:
    def test_autopage_empty(self):
        assert b"".join(Document([AutoPage([])]).write()).endswith(b"%%EOF\n")

    def test_paragraph_empty(self):
        assert b"".join(Document([AutoPage(Paragraph([]))]).write()).endswith(
            b"%%EOF\n"
        )

    def test_one_template(self, outfile):
        Document(
            [
                AutoPage(
                    LOREM_IPSUM,
                    template=Page(size=A5, margin=(mm(20), mm(20), mm(25))),
                )
            ],
            style=times_roman,
        ).write(outfile)

    def test_template_callable(self, outfile):
        def make_page(num: int) -> Page:
            return Page(
                [Text((A5.x / 2, mm(20)), str(num), italic)],
                size=A5,
                margin=(mm(20), mm(20), mm(25)),
            )

        Document(
            [AutoPage(LOREM_IPSUM * 3, template=make_page)],
            style=times_roman,
        ).write(outfile)

    def test_multistyle_text(self, outfile):
        para = Paragraph(
            [
                "Now is better than never.\n"
                "Although never is often better than ",
                Span("right", Style(bold=True)),
                " now.",
            ]
        )
        Document([AutoPage(para)]).write(outfile)

    def test_multiple_columns(self, outfile):
        two_columns = [
            Column(
                XY(inch(1), inch(1)),
                (A4.x / 2) - inch(1.25),
                A4.y - inch(2),
            ),
            Column(
                XY(A4.x / 2 + inch(0.25), inch(1)),
                (A4.x / 2) - inch(1.25),
                A4.y - inch(2),
            ),
        ]
        pages = cycle(
            [
                Page(
                    [
                        Text(
                            (A4.x / 2, A4.y - inch(0.5)),
                            "Two column page",
                            italic,
                        )
                    ],
                    columns=two_columns,
                ),
                Page(
                    [
                        Text(
                            (A6.x / 2, A6.y - inch(0.2)),
                            "One column page",
                            bold,
                        )
                    ],
                    size=A6,
                    margin=mm(15),
                ),
            ]
        )
        Document(
            [AutoPage(LOREM_IPSUM * 4, template=lambda _: next(pages))],
            style=Style(font=times_roman, line_spacing=1.2),
        ).write(outfile)

    def test_text(self, outfile):
        text: list[Block | str] = [
            LOREM_IPSUM,
            Paragraph(
                LOREM_IPSUM,
                "#770000" | times_roman | italic,
                indent=20,
                align="justify",
            ),
            Rule(),
            Paragraph(
                "\n".join([ZEN_OF_PYTHON] * 4) + "\n",
                Style(
                    size=17,
                    line_spacing=1.1,
                    color="#117700",
                    font=helvetica,
                    italic=True,
                    bold=True,
                    hyphens=None,
                ),
                align="center",
            ),
            *[Rule()] * 6,
            Paragraph(
                list(
                    islice(
                        (
                            Span(ZEN_OF_PYTHON.replace("\n", " ") + " ", s)
                            for s in cycle(
                                [
                                    bold,
                                    italic,
                                    bold | italic,
                                    regular,
                                    Style(size=4, color=blue, hyphens=None),
                                ]
                            )
                        ),
                        20,
                    )
                ),
                Style(size=2, font=times_roman),
                align="right",
            ),
        ]
        Document(
            [
                AutoPage(text),
                AutoPage(
                    [
                        Paragraph(
                            LOREM_IPSUM, Style(line_spacing=3, font=courier)
                        )
                    ]
                ),
            ]
        ).write(outfile)

    def test_extremely_large_text_handled_without_issue(self, outfile):
        Document(
            [
                AutoPage(
                    [
                        Paragraph(
                            LOREM_IPSUM[:200],
                            style=Style(
                                font=times_roman, size=1000, line_spacing=0.9
                            ),
                        ),
                        Paragraph(
                            LOREM_IPSUM[200:],
                            style=Style(size=300, line_spacing=0.9),
                        ),
                    ]
                )
            ],
        ).write(outfile)


def test_draw(outfile):
    Document(
        [
            Page([Text((250, 400), "First!", Style(size=50))]),
            Page([Text((50, 720), ZEN_OF_PYTHON)]),
            Page(
                [
                    Rect((50, 720), 72, -800),
                    Text(
                        (50, 720),
                        """\
In olden times
when wishing
still helped
one, there
lived a king
whose daugh-
ters were all
beautiful, but
the young-
est was so
beautiful that
the sun itself,
which has
seen so much,
was astonished
whenever it
shone in her
face. Close by
the king’s cas-
tle lay a
great dark for-
est, and under
an old lime-
tree in the
forest was a
well, and when
the day was
very warm, the
king’s child
went out into
the forest and
sat down by
the side of the
cool fountain,
and when she
was bored she
took a golden
ball, and threw
it up on high
and caught it,
and this ball
was her favo-
rite plaything.""",
                        style=times_roman,
                    ),
                    Rect((150, 720), 72, -800),
                    Text(
                        (150, 720),
                        """\
In olden times
when wishing
still helped
one, there lived
a king whose
daughters were
all beautiful,
but the young-
est was so
beautiful that
the sun itself,
which has
seen so much,
was astonished
whenever it
shone in her
face. Close by
the king’s cas-
tle lay a great
dark forest, and
under an old
lime-tree in the
forest was a
well, and when
the day was
very warm, the
king’s child
went out into
the forest and
sat down by
the side of the
cool fountain,
and when she
was bored she
took a golden
ball, and threw
it up on high
and caught it,
and this ball
was her favo-
rite plaything.""",
                        style=times_roman,
                    ),
                ]
            ),
            Page(
                [
                    Polyline(
                        [(50, 650), (50, 600), (100, 600)],
                        close=True,
                        stroke=lime,
                    ),
                    Polyline(
                        [(50, 650), (80, 550), (150, 500)],
                        close=False,
                        stroke="#004599",
                    ),
                    Rect((50, 700), 500, 70, fill="#ffaa99"),
                    Line((50, 690), (450, 690), stroke=red),
                    Ellipse((300, 200), 100, 50, fill="#22d388", stroke=None),
                    Circle((100, 100), 200, fill="#ffaa99", stroke=red),
                    Text(
                        (50, 770),
                        "Big red text, and LINES!",
                        Style(size=40, color=red),
                    ),
                    Circle((A4.x / 2, 400), 5, stroke=red),
                    Text(
                        (A4.x / 2, 400),
                        "Centered text\nwith multiple lines that are"
                        "\nalso centered...",
                        Style(size=20, color=blue),
                        align="center",
                    ),
                    Circle((A4.x * 0.8, 200), 5, stroke=red),
                    Text(
                        (A4.x * 0.8, 200),
                        [
                            "right-aligned text\nis ",
                            Span("also\nposs", italic),
                            "ible...",
                        ],
                        Style(size=20, color="#ff0099"),
                        align="right",
                    ),
                ]
            ),
        ]
    ).write(outfile)


def test_rotate(outfile):
    Document(
        [
            Page(
                [
                    Text(
                        A4 / 2,
                        f"rotated {angle}",
                        style=Style(size=60),
                        align="center",
                    )
                ],
                rotate=angle,
            )
            for angle in ALL_ANGLES
        ]
    ).write(outfile)


@pytest.mark.skipif(
    not HAS_FONTTOOLS, reason="fonttools not installed (optional)"
)
def test_fonts(outfile, dejavu: TrueType, crimson: TrueType):
    Document(
        [
            Page(
                [
                    Text(
                        (50, 730),
                        [
                            Span("Cheers, Cour®ier\n", courier),
                            "Hey ",
                            "hélvetica!\n",
                            Span("Ciåo Crîmson...\n", crimson),
                            Span(
                                "Hello 𝌷 agaîn,\nDejaVü! Kerning AWAY! ",
                                dejavu,
                            ),
                            Span(
                                "Good †imes",
                                Style(times_roman, line_spacing=3),
                            ),
                            Span(
                                "\n(check the above text can be copied!)",
                                crimson,
                            ),
                            "\nunknown char (builtin font): ∫",
                            Span("\nunknown char (embedded font): ⟤", dejavu),
                            Span(f"\nzalgo: {ZALGO}", dejavu),
                            Span("\nzero byte: \x00", dejavu),
                        ],
                        Style(size=12, line_spacing=2),
                    )
                ]
            ),
            AutoPage(
                [
                    Paragraph(LOREM_IPSUM, crimson),
                    Paragraph(
                        LOREM_IPSUM,
                        Style(
                            color=(0.5, 0, 0),
                            size=10,
                            font=dejavu,
                            italic=True,
                            bold=True,
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
tristique a ultrices sed, finibus id enim.

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
Namespaces are one honking great idea — let's do more of those!"""
