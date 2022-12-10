from random import Random

import pytest

from pdfje.common import dictget
from pdfje.fonts import Subset, kern, utf16be_hex
from pdfje.fonts.common import KerningTable


def _make_subset(cids) -> Subset:
    pytest.importorskip("fontTools")
    return Subset(
        b"F0",
        NotImplemented,
        NotImplemented,
        cids,
        NotImplemented,
        None,
    )


_EXAMPLE_KERNINGTABLE: KerningTable = dictget(
    {
        ("x", "y"): -40,
        ("a", "b"): -60,
        (" ", "a"): -20,
        ("a", " "): -10,
        ("z", " "): -10,
    },
    0,
)


class TestKern:
    def test_empty(self):
        assert list(kern(_EXAMPLE_KERNINGTABLE, "", 1, " ", 0)) == []

    def test_no_kerning_needed(self):
        assert list(kern(_EXAMPLE_KERNINGTABLE, "basdfzyx", 1, " ", 0)) == []

    def test_lots_of_kerning(self):
        assert list(kern(_EXAMPLE_KERNINGTABLE, "aaababaxyz", 1, " ", 0)) == [
            (0, -20),
            (3, -60),
            (5, -60),
            (8, -40),
        ]

    def test_lots_of_kerning_no_init(self):
        assert list(kern(_EXAMPLE_KERNINGTABLE, "aaababaxyz", 1, None, 0)) == [
            (3, -60),
            (5, -60),
            (8, -40),
        ]

    def test_bigger_charsize(self):
        assert list(kern(_EXAMPLE_KERNINGTABLE, "aaababaxyz", 3, " ", 0)) == [
            (0, -20),
            (9, -60),
            (15, -60),
            (24, -40),
        ]

    def test_offset(self):
        assert list(kern(_EXAMPLE_KERNINGTABLE, "aaababaxyz", 3, " ", 4)) == [
            (4, -20),
            (13, -60),
            (19, -60),
            (28, -40),
        ]

    def test_one_letter(self):
        assert list(kern(_EXAMPLE_KERNINGTABLE, "a", 1, " ", 0)) == [
            (0, -20),
        ]


class TestEncodeEmbeddedSubset:
    def test_empty(self):
        assert _make_subset({}).encode("") == b""

    def test_ascii(self):
        assert (
            _make_subset(
                {ord("a"): 1, ord("b"): 4, ord("\n"): 0xFFFE},
            ).encode("ab\n")
            == b"\x00\x01\x00\x04\xff\xfe"
        )

    def test_exotic_unicode(self):
        assert (
            _make_subset(
                {ord("🌵"): 9, ord("𫄸"): 0xD900, ord("𒀗"): 0xFFFE}
            ).encode(
                "🌵𫄸𒀗",
            )
            == b"\x00\x09\xd9\x00\xff\xfe"
        )

    def test_long_string(self, benchmark):
        count = 10_000
        rand = Random(0)
        string = "".join(map(chr, rand.sample(range(0x10FFFF), k=count)))
        cids = list(range(count))
        rand.shuffle(cids)
        cmap = dict(zip(map(ord, string), cids))
        assert len(benchmark(_make_subset(cmap).encode, string)) == 2 * len(
            string
        )


class TestUTF16BEHex:
    def test_one_byte(self, benchmark):
        assert benchmark(utf16be_hex, ord("a")) == b"0061"

    def test_two_bytes(self, benchmark):
        assert benchmark(utf16be_hex, ord("∫")) == b"222B"

    def test_four_bytes(self, benchmark):
        assert benchmark(utf16be_hex, ord("🌵")) == b"D83CDF35"
