from random import Random

from pdfje.fonts import EmbeddedSubset, utf16be_hex


def _makefont(cidmap) -> EmbeddedSubset:
    return EmbeddedSubset(
        b"F0",
        0,
        NotImplemented,
        NotImplemented,
        NotImplemented,
        cidmap,
        NotImplemented,
    )


class TestEncodeEmbeddedSubset:
    def test_empty(self):
        assert _makefont({}).encode("") == b""

    def test_ascii(self):
        assert (
            _makefont(
                {ord("a"): 1, ord("b"): 4, ord("\n"): 0xFFFE},
            ).encode("ab\n")
            == b"\x00\x01\x00\x04\xff\xfe"
        )

    def test_exotic_unicode(self):
        assert (
            _makefont(
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
        assert len(benchmark(_makefont(cmap).encode, string)) == 2 * len(
            string
        )


class TestUTF16BEHex:
    def test_one_byte(self, benchmark):
        assert benchmark(utf16be_hex, ord("a")) == b"0061"

    def test_two_bytes(self, benchmark):
        assert benchmark(utf16be_hex, ord("∫")) == b"222B"

    def test_four_bytes(self, benchmark):
        assert benchmark(utf16be_hex, ord("🌵")) == b"D83CDF35"
