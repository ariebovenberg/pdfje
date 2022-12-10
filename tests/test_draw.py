from pdfje import XY, Polyline, Rect

NA = NotImplemented


class TestPolyline:
    def test_empty(self):
        assert b"".join(Polyline([]).render(NA, NA)) == b""

    def test_one_point(self):
        assert (
            b"".join(Polyline([(2, 3)]).render(NA, NA))
            == b"2 3 m 0 0 0 RG S\n"
        )

    def test_several_points(self):
        assert (
            b"".join(Polyline([(2, 3), XY(4, 5), (6, 7)]).render(NA, NA))
            == b"2 3 m 4 5 l 6 7 l 0 0 0 RG S\n"
        )

    def test_several_points_closed(self):
        assert (
            b"".join(
                Polyline([(2, 3), XY(4, 5), (6, 7)], close=True).render(NA, NA)
            )
            == b"2 3 m 4 5 l 6 7 l 0 0 0 RG s\n"
        )


class TestRect:
    def test_init(self):
        assert Rect((2, 3), 4, 5).origin == XY(2, 3)
        assert Rect((2, 3), 4, 5).width == 4
        assert Rect((2, 3), 4, 5).height == 5

    def test_render(self):
        assert (
            b"".join(Rect((2, 3), 4, 5).render(NA, NA))
            == b"2 3 4 5 re 0 0 0 RG S\n"
        )

    def test_invisible(self):
        assert (
            b"".join(Rect((2, 3), 4, 5, stroke=None).render(NA, NA))
            == b"2 3 4 5 re n\n"
        )
