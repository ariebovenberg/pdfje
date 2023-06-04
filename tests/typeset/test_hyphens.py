from __future__ import annotations

import pytest

from pdfje.typeset.hyphens import (
    HAS_PYPHEN,
    default_hyphenator,
    never_hyphenate,
    parse_hyphenator,
)


def test_default_hyphenation():
    assert list(default_hyphenator("beautiful")) == ["beau", "ti", "ful"]


class TestParseHyphenator:
    @pytest.mark.skipif(not HAS_PYPHEN, reason="pyphen not installed")
    def test_pyphen(self):
        from pyphen import Pyphen

        p = Pyphen(lang="nl_NL")
        h = parse_hyphenator(p)
        result = h("beautiful")
        assert hasattr(result, "__iter__")
        assert list(result) == ["beau", "ti", "ful"]

    def test_none(self):
        assert parse_hyphenator(None) is never_hyphenate
