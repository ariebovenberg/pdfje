from __future__ import annotations

from pdfje.units import cm, inch, mm, pc, pt

from .common import approx


def test_units():
    assert inch(1) == approx(72)
    assert cm(1) == approx(28.34645669291339)
    assert mm(1) == approx(2.8346456692913386)
    assert pc(1) == approx(12)
    assert pt(1) == 1
