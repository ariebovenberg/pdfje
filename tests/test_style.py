from __future__ import annotations

import pytest

from pdfje import RGB, XY
from pdfje.draw import Text
from pdfje.fonts import helvetica, times_roman
from pdfje.layout import Paragraph
from pdfje.resources import Resources
from pdfje.style import Span, Style
from pdfje.typeset.common import (
    NO_OP,
    Chain,
    Passage,
    SetColor,
    SetFont,
    SetHyphens,
    SetLineSpacing,
)
from pdfje.typeset.hyphens import default_hyphenator, never_hyphenate
from tests.common import eq_iter


def test_parse_rgb():
    assert Style(color=(0, 1, 0)) == Style(color=RGB(0, 1, 0))


RED = RGB(1, 0, 0)
GREEN = RGB(0, 1, 0)
BLUE = RGB(0, 0, 1)
STYLE = Style(italic=True, color=RED).setdefault()


@pytest.fixture
def res() -> Resources:
    return Resources()


class TestStyle:
    def test_repr(self):
        rep = repr(Style(italic=True, color=RED))
        assert "color" in rep
        assert "italic" in rep
        assert "bold" not in rep

    def test_parse(self):
        assert Style.parse(helvetica) == Style(font=helvetica)
        assert Style.parse(RED) == Style(color=RED)
        assert Style.parse("#4591BB") == Style(color="#4591BB")
        with pytest.raises(TypeError):
            Style.parse(1)  # type: ignore

    def test_init(self):
        s = Style(italic=True, color=RED)
        assert s.line_spacing is None
        assert s.font is None
        assert s.hyphens is None


class TestStyleLikeUnion:
    def test_style_and_other(self):
        assert Style(italic=True) | Style(color=RED) == Style(
            italic=True, color=RED
        )
        assert Style(italic=True, bold=True) | Style(
            color=RED, bold=False
        ) == Style(italic=True, color=RED, bold=False)
        assert Style(italic=True) | times_roman == Style(
            italic=True, font=times_roman
        )
        assert Style(italic=True) | "#4591BB" == Style(
            italic=True, color="#4591BB"
        )
        assert Style(italic=True) | RGB(1, 0, 0) == Style(
            italic=True, color=RGB(1, 0, 0)
        )
        with pytest.raises(TypeError, match="operand"):
            Style(italic=True) | 1  # type: ignore[operator]

    def test_font_and_other(self):
        assert times_roman | Style(italic=True) == Style(
            italic=True, font=times_roman
        )
        assert times_roman | Style(font=helvetica) == Style(font=helvetica)
        assert times_roman | times_roman == Style(font=times_roman)
        assert times_roman | "#4591BB" == Style(
            color="#4591BB", font=times_roman
        )
        assert times_roman | RGB(1, 0, 0) == Style(
            color=RGB(1, 0, 0), font=times_roman
        )
        with pytest.raises(TypeError, match="operand"):
            times_roman | 1  # type: ignore[operator]

    def test_color_and_other(self):
        assert RED | Style(italic=True) == Style(italic=True, color=RED)
        assert RED | Style(color=GREEN) == Style(color=GREEN)
        assert RED | times_roman == Style(color=RED, font=times_roman)
        assert RED | "#4591BB" == Style(color="#4591BB")
        assert RED | RGB(1, 0, 0) == Style(color=RGB(1, 0, 0))

        with pytest.raises(TypeError, match="operand"):
            RED | 1  # type: ignore[operator]

    def test_hexcolor_and_other(self):
        assert "#4591BB" | Style(italic=True) == Style(
            italic=True, color="#4591BB"
        )
        assert "#4591BB" | Style(color=GREEN) == Style(color=GREEN)
        assert "#4591BB" | times_roman == Style(
            color="#4591BB", font=times_roman
        )
        assert "#4591BB" | RGB(1, 0, 0) == Style(color=RGB(1, 0, 0))

        with pytest.raises(TypeError, match="operand"):
            "#4591BB" | 1  # type: ignore[operator]


class TestStyleDiff:
    def test_empty(self, res: Resources):
        assert list(Style.EMPTY.diff(res, STYLE)) == []

    def test_no_changes(self, res: Resources):
        assert (
            list(
                Style(
                    italic=STYLE.italic,
                    bold=STYLE.bold,
                    font=STYLE.font,
                    color=STYLE.color,
                    size=STYLE.size,
                    line_spacing=STYLE.line_spacing,
                    hyphens=STYLE.hyphens,
                ).diff(res, STYLE)
            )
            == []
        )

    def test_font_change(self, res):
        assert list(Style(bold=True).diff(res, STYLE)) == [
            SetFont(helvetica.bold_italic, 12)
        ]
        assert list(Style(size=4).diff(res, STYLE)) == [
            SetFont(helvetica.italic, 4)
        ]
        assert list(Style(font=times_roman).diff(res, STYLE)) == [
            SetFont(res.font(times_roman, False, True), 12)
        ]
        assert list(Style(italic=False).diff(res, STYLE)) == [
            SetFont(helvetica.regular, 12)
        ]

        # several relative changes
        assert list(
            Style(bold=True, italic=False, size=15).diff(res, STYLE)
        ) == [SetFont(helvetica.bold, 15)]
        assert list(Style(italic=False).diff(res, STYLE)) == [
            SetFont(helvetica.regular, 12)
        ]
        assert list(
            Style(font=times_roman, italic=False).diff(res, STYLE)
        ) == [SetFont(res.font(times_roman, False, False), 12)]

    def test_color_change(self, res: Resources):
        assert list(Style(color=STYLE.color).diff(res, STYLE)) == []
        assert list(Style(color=GREEN).diff(res, STYLE)) == [SetColor(GREEN)]

    def test_line_spacing_change(self, res: Resources):
        assert list(Style(line_spacing=1.25).diff(res, STYLE)) == []
        assert list(Style(line_spacing=1.5).diff(res, STYLE)) == [
            SetLineSpacing(1.5)
        ]

    def test_hyphens_change(self, res: Resources):
        assert list(Style(hyphens=default_hyphenator).diff(res, STYLE)) == []
        assert list(Style(hyphens=never_hyphenate).diff(res, STYLE)) == [
            SetHyphens(never_hyphenate)
        ]
        assert list(
            Style(hyphens=default_hyphenator).diff(
                res, STYLE | Style(hyphens=never_hyphenate)
            )
        ) == [SetHyphens(default_hyphenator)]

    def test_combined_change(self, res: Resources):
        assert list(Style(font=times_roman, color=GREEN).diff(res, STYLE)) == [
            SetFont(res.font(times_roman, False, True), 12),
            SetColor(GREEN),
        ]


class TestFlatten:
    def test_empty(self, res: Resources):
        assert list(Paragraph([], Style(color=BLUE)).flatten(res, STYLE)) == []

    def test_already_flat(self, res: Resources):
        result = list(
            Paragraph(
                ["Beautiful is ", "better", " than ugly."],
                Style(bold=True, size=14, color=GREEN),
            ).flatten(res, STYLE)
        )
        assert result == [
            Passage(
                Chain(
                    eq_iter(
                        [
                            SetFont(helvetica.bold_italic, 14),
                            SetColor(GREEN),
                        ]
                    )
                ),
                "Beautiful is ",
            ),
            Passage(NO_OP, "better"),
            Passage(NO_OP, " than ugly."),
        ]

    def test_hyphenate_toggle(self, res: Resources):
        par = Paragraph(
            [
                "Beautiful is better than ",
                Span(" ugly.", Style(hyphens=None)),
                " Explicit is better than implicit.",
            ]
        )
        result = list(par.flatten(res, STYLE))
        assert result == [
            Passage(NO_OP, "Beautiful is better than "),
            Passage(
                SetHyphens(never_hyphenate),
                " ugly.",
            ),
            Passage(
                SetHyphens(default_hyphenator),
                " Explicit is better than implicit.",
            ),
        ]

    def test_nested(self, res: Resources):
        result = list(
            Paragraph(
                [
                    "Beautiful is better than ",
                    Span(" ugly.", Style(color=GREEN, hyphens=None)),
                    Span(
                        [
                            " Explicit is better ",
                            Span(
                                Span(
                                    "than", Style(font=times_roman, color=BLUE)
                                ),
                                style=Style(bold=False, line_spacing=2),
                            ),
                            " implicit",
                            Span(".", Style(color=GREEN)),
                        ],
                        Style(bold=True, size=20),
                    ),
                    " Simple is better than complex.",
                    Span(" Complex is better than complicated.", Style.EMPTY),
                ],
                Style(size=14),
            ).flatten(res, STYLE)
        )
        assert result == [
            Passage(
                SetFont(helvetica.italic, 14), "Beautiful is better than "
            ),
            Passage(
                Chain(eq_iter([SetColor(GREEN), SetHyphens(never_hyphenate)])),
                " ugly.",
            ),
            Passage(
                Chain(
                    eq_iter(
                        [
                            SetColor(RED),
                            SetHyphens(default_hyphenator),
                            SetFont(helvetica.bold_italic, 20),
                        ]
                    )
                ),
                " Explicit is better ",
            ),
            Passage(
                Chain(
                    eq_iter(
                        [
                            SetFont(res.font(times_roman, False, True), 20),
                            SetColor(BLUE),
                            SetLineSpacing(2),
                        ]
                    )
                ),
                "than",
            ),
            Passage(
                Chain(
                    eq_iter(
                        [
                            SetLineSpacing(1.25),
                            SetColor(RED),
                            SetFont(helvetica.bold_italic, 20),
                        ]
                    )
                ),
                " implicit",
            ),
            Passage(SetColor(GREEN), "."),
            Passage(
                Chain(eq_iter([SetColor(RED), SetFont(helvetica.italic, 14)])),
                " Simple is better than complex.",
            ),
            Passage(NO_OP, " Complex is better than complicated."),
        ]


def test_text_init():
    t = Text((1, 2), "hello", "#ff0000")
    assert t == Text(XY(1, 2), ["hello"], Style(color="#ff0000"))
