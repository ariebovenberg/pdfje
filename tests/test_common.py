import pytest

from pdfje.common import RGB, XY, Sides, cm, inch, mm, pt

from .common import approx


class TestXY:
    def test_basics(self):
        xy = XY(1, 2)
        assert xy.x == 1
        assert xy.y == 2
        assert xy.astuple() == (1, 2)

    def test_is_sequence(self):
        xy = XY(1, 2)
        assert xy[0] == 1
        assert xy[1] == 2

        with pytest.raises(IndexError):
            xy[2]

        assert list(xy) == [1, 2]
        assert len(xy) == 2
        assert xy.index(1) == 0
        assert 2 in xy
        assert xy.count(1) == 1
        assert list(reversed(xy)) == [2, 1]

    def test_parse(self):
        assert XY.parse((1, 3)) == XY(1, 3)
        assert XY.parse(XY(1, 3)) == XY(1, 3)

    def test_division(self):
        assert XY(1, 2) / 2 == XY(0.5, 1)

        with pytest.raises(TypeError, match="operand"):
            XY(1, 2) / "foo"  # type: ignore[operator]

    def test_flip(self):
        assert XY(1, 2).flip() == XY(2, 1)

    def test_add_coordinates(self):
        assert XY(1, 2).add_x(3) == XY(4, 2)
        assert XY(1, 2).add_y(3) == XY(1, 5)

    def test_subtract(self):
        assert XY(1, 2) - XY(3, 4) == XY(-2, -2)
        assert XY(1, 2) - (3, 4) == XY(-2, -2)

        with pytest.raises(TypeError, match="operand"):
            XY(1, 2) - "foo"  # type: ignore[operator]

    def test_add(self):
        assert XY(1, 2) + XY(3, 4) == XY(4, 6)
        assert XY(1, 2) + (3, 4) == XY(4, 6)

        with pytest.raises(TypeError, match="operand"):
            XY(1, 2) + "foo"  # type: ignore[operator]

    def test_multiply(self):
        assert XY(1, 2) * 3 == XY(3, 6)

        with pytest.raises(TypeError, match="operand"):
            XY(1, 2) * {}  # type: ignore[operator]


class TestRGB:
    def test_basics(self):
        rgb = RGB(1, 0.5, 0)
        assert rgb.red == 1
        assert rgb.green == 0.5
        assert rgb.blue == 0
        assert rgb.astuple() == (1, 0.5, 0)

    def test_is_sequence(self):
        rgb = RGB(1, 0.5, 0)
        assert rgb[0] == 1
        assert rgb[1] == 0.5
        assert rgb[2] == 0

        with pytest.raises(IndexError):
            rgb[3]

        assert list(rgb) == [1, 0.5, 0]
        assert len(rgb) == 3
        assert rgb.index(1) == 0
        assert 0.5 in rgb
        assert rgb.count(1) == 1
        assert list(reversed(rgb)) == [0, 0.5, 1]

    def test_parse(self):
        assert RGB.parse((1, 0.5, 0)) == RGB(1, 0.5, 0)
        parsed = RGB.parse("#a044e9")
        assert parsed.red == approx(160 / 255)
        assert parsed.green == approx(68 / 255)
        assert parsed.blue == approx(233 / 255)

        with pytest.raises(AssertionError, match="RGB"):
            RGB.parse(object())  # type: ignore


class TestSides:
    def test_basics(self):
        sides = Sides(1, 2, 3, 4)
        assert sides.top == 1
        assert sides.right == 2
        assert sides.bottom == 3
        assert sides.left == 4
        assert sides.astuple() == (1, 2, 3, 4)

    def test_is_sequence(self):
        sides = Sides(1, 2, 3, 4)
        assert sides[0] == 1
        assert sides[1] == 2
        assert sides[2] == 3
        assert sides[3] == 4

        with pytest.raises(IndexError):
            sides[4]

        assert list(sides) == [1, 2, 3, 4]
        assert len(sides) == 4
        assert sides.index(1) == 0
        assert 2 in sides
        assert sides.count(1) == 1
        assert list(reversed(sides)) == [4, 3, 2, 1]

    def test_parse(self):
        assert Sides.parse(1) == Sides(1, 1, 1, 1)
        assert Sides.parse((1, 2)) == Sides(1, 2, 1, 2)
        assert Sides.parse((1, 2, 3)) == Sides(1, 2, 3, 2)
        assert Sides.parse((1, 2, 3, 4)) == Sides(1, 2, 3, 4)
        assert Sides.parse(Sides(1, 2, 3, 4)) == Sides(1, 2, 3, 4)

        with pytest.raises(TypeError, match="sides"):
            Sides.parse((20, 30, 25, 35, 40))  # type: ignore[arg-type]

        with pytest.raises(TypeError, match="sides"):
            Sides.parse("foo")  # type: ignore[arg-type]


def test_units():
    assert inch(1) == approx(72)
    assert cm(1) == approx(28.34645669291339)
    assert mm(1) == approx(2.8346456692913386)
    assert pt(1) == 1
