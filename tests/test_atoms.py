import pytest

from pdfje.atoms import HexString, escape_string, sanitize_name


@pytest.mark.parametrize(
    "string,expect",
    [
        (b"", b""),
        (
            b"!\"$%&'()*+,-./0123456789:;<=>?@ABCDEFGHIJKLMNOPQRSTU"
            b"VWXYZ[\\]^_`abcdefghijklmnopqrstuvwxyz{|}~",
            b"!\"$%&'()*+,-./0123456789:;<=>?@ABCDEFGHIJKLMNOPQRSTU"
            b"VWXYZ[\\]^_`abcdefghijklmnopqrstuvwxyz{|}~",
        ),
        (b"foo\r# a\x00b\n\tc", b"foo#23#20abc"),
    ],
)
def test_sanitize_name(string, expect):
    assert sanitize_name(string) == expect


@pytest.mark.parametrize(
    "string,expect",
    [
        (b"", b""),
        (b"\x00\x02a9~!kbn[]'/?", b"\x00\x02a9~!kbn[]'/?"),
        (b"a\\b\\", b"a\\\\b\\\\"),
        (b"a\t\nb\f\b", b"a\\t\\nb\\f\\b"),
    ],
)
def test_escape_string(string, expect):
    assert escape_string(string) == expect


@pytest.mark.parametrize(
    "string,expect",
    [
        (b"", b"<>"),
        (b"\x00\xa9b Z", b"<00A962205A>"),
        (b"<>", b"<3C3E>"),
    ],
)
def test_hex_string(string, expect):
    assert b"".join(HexString(string).write()).upper() == expect
