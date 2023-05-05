from dataclasses import replace

from pdfje.atoms import LiteralStr, Real
from pdfje.common import Char
from pdfje.fonts.common import TEXTSPACE_TO_GLYPHSPACE
from pdfje.typeset.common import (
    NO_OP,
    Slug,
    State,
    Stretch,
    _encode_kerning,
    splitlines,
)

from ..common import approx
from .common import BIG, BLUE, FONT, GREEN, RED, STATE


class TestSplitlines:
    def test_empty(self):
        result = splitlines(iter([]))
        assert next(result, None) is None

    def test_no_breaks(self):
        result = splitlines(
            iter(
                [
                    Stretch(RED, "Beautiful "),
                    Stretch(BLUE, "is better "),
                    Stretch(GREEN, "than ugly."),
                ]
            )
        )
        assert list(next(result)) == [
            Stretch(RED, "Beautiful "),
            Stretch(BLUE, "is better "),
            Stretch(GREEN, "than ugly."),
        ]

    def test_breaks(self):
        result = splitlines(
            iter(
                [
                    Stretch(RED, "Beautiful "),
                    Stretch(BLUE, "is better "),
                    Stretch(GREEN, "than\nugly.\r\n\n"),
                    Stretch(RED, "Explicit is "),
                    Stretch(BIG, "better than \nimplicit. \n"),
                ]
            )
        )
        assert list(next(result)) == [
            Stretch(RED, "Beautiful "),
            Stretch(BLUE, "is better "),
            Stretch(GREEN, "than"),
        ]
        assert list(next(result)) == [Stretch(NO_OP, "ugly.")]
        assert list(next(result)) == [Stretch(NO_OP, "")]
        assert list(next(result)) == [
            Stretch(NO_OP, ""),
            Stretch(RED, "Explicit is "),
            Stretch(BIG, "better than "),
        ]
        assert list(next(result)) == [Stretch(NO_OP, "implicit. ")]
        assert list(next(result)) == [Stretch(NO_OP, "")]


class TestEncodeKerning:
    def test_typical(self):
        assert list(
            _encode_kerning("abcdefg", [(1, -20), (2, -30), (6, -40)], FONT)
        ) == [
            LiteralStr(b"a"),
            Real(20),
            LiteralStr(b"b"),
            Real(30),
            LiteralStr(b"cdef"),
            Real(40),
            LiteralStr(b"g"),
        ]

    def test_kern_first_char(self):
        assert list(
            _encode_kerning("abcdefg", [(0, -20), (2, -30)], FONT)
        ) == [
            Real(20),
            LiteralStr(b"ab"),
            Real(30),
            LiteralStr(b"cdefg"),
        ]

    def test_no_kern(self):
        assert list(_encode_kerning("abcdefg", [], FONT)) == [
            LiteralStr(b"abcdefg")
        ]


class TestGaugedString:
    def test_build(self):
        s = g("Complex", STATE, " ")
        assert s.kern == [(0, -15), (3, -10), (6, -20)]
        assert (
            s.width
            == (
                STATE.font.width("Complex")
                + sum(x for _, x in s.kern) / TEXTSPACE_TO_GLYPHSPACE
            )
            * STATE.size
        )


def g(
    s: str, st: State, prev: Char | None = None, approx_: bool = False
) -> Slug:
    """Helper to create a kerned string"""
    assert s
    string = Slug.nonempty(s, st, prev)
    return replace(string, width=approx(string.width)) if approx_ else string
