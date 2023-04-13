from pathlib import Path
from random import Random

import pytest

from pdfje.common import dictget
from pdfje.fonts.common import KerningTable, TrueType, kern
from pdfje.fonts.embed import Subset, _utf16be_hex

try:
    import fontTools  # noqa

    HAS_FONTTOOLS = True
except ImportError:
    HAS_FONTTOOLS = False


def _make_subset(cids) -> Subset:
    pytest.importorskip("fontTools")
    return Subset(
        b"F0",
        NotImplemented,
        lambda _: 1,
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
        assert list(kern(_EXAMPLE_KERNINGTABLE, "", " ", 0)) == []

    def test_no_kerning_needed(self):
        assert list(kern(_EXAMPLE_KERNINGTABLE, "basdfzyx", " ", 0)) == []

    def test_lots_of_kerning(self):
        assert list(kern(_EXAMPLE_KERNINGTABLE, "aaababaxyz", " ", 0)) == [
            (0, -20),
            (3, -60),
            (5, -60),
            (8, -40),
        ]

    def test_lots_of_kerning_no_init(self):
        assert list(kern(_EXAMPLE_KERNINGTABLE, "aaababaxyz", None, 0)) == [
            (3, -60),
            (5, -60),
            (8, -40),
        ]

    def test_offset(self):
        assert list(kern(_EXAMPLE_KERNINGTABLE, "aaababaxyz", " ", 4)) == [
            (4, -20),
            (7, -60),
            (9, -60),
            (12, -40),
        ]

    def test_one_letter(self):
        assert list(kern(_EXAMPLE_KERNINGTABLE, "a", " ", 0)) == [
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


def test_true_type_init():
    t = TrueType(
        Path(__file__).parent / "../resources/fonts/Roboto-Regular.ttf",
        str(Path(__file__).parent / "../resources/fonts/Roboto-Bold.ttf"),
        Path(__file__).parent / "../resources/fonts/Roboto-Italic.ttf",
        Path(__file__).parent / "../resources/fonts/Roboto-BoldItalic.ttf",
    )
    assert isinstance(t.bold, Path)


@pytest.mark.skipif(HAS_FONTTOOLS, reason="fontTools installed")
def test_fonttools_notimplemented():
    with pytest.raises(NotImplementedError):
        _make_subset({}).encode("")


class TestUTF16BEHex:
    def test_one_byte(self, benchmark):
        assert benchmark(_utf16be_hex, ord("a")) == b"0061"

    def test_two_bytes(self, benchmark):
        assert benchmark(_utf16be_hex, ord("∫")) == b"222B"

    def test_four_bytes(self, benchmark):
        assert benchmark(_utf16be_hex, ord("🌵")) == b"D83CDF35"
