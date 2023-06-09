from __future__ import annotations

from pdfje.atoms import LiteralStr, Real
from pdfje.typeset.state import NO_OP, Passage, splitlines
from pdfje.typeset.words import _encode_kerning

from ..common import BIG, BLUE, FONT, GREEN, RED


class TestSplitlines:
    def test_empty(self):
        result = splitlines(iter([]))
        assert next(result, None) is None

    def test_no_breaks(self):
        result = splitlines(
            iter(
                [
                    Passage(RED, "Beautiful "),
                    Passage(BLUE, "is better "),
                    Passage(GREEN, "than ugly."),
                ]
            )
        )
        assert list(next(result)) == [
            Passage(RED, "Beautiful "),
            Passage(BLUE, "is better "),
            Passage(GREEN, "than ugly."),
        ]

    def test_breaks(self):
        result = splitlines(
            iter(
                [
                    Passage(RED, "Beautiful "),
                    Passage(BLUE, "is better "),
                    Passage(GREEN, "than\nugly.\r\n\n"),
                    Passage(RED, "Explicit is "),
                    Passage(BIG, "better than \nimplicit. \n"),
                ]
            )
        )
        assert list(next(result)) == [
            Passage(RED, "Beautiful "),
            Passage(BLUE, "is better "),
            Passage(GREEN, "than"),
        ]
        assert list(next(result)) == [Passage(NO_OP, "ugly.")]
        assert list(next(result)) == [Passage(NO_OP, "")]
        assert list(next(result)) == [
            Passage(NO_OP, ""),
            Passage(RED, "Explicit is "),
            Passage(BIG, "better than "),
        ]
        assert list(next(result)) == [Passage(NO_OP, "implicit. ")]
        assert list(next(result)) == [Passage(NO_OP, "")]


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
