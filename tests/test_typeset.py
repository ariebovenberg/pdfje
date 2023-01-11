from __future__ import annotations

from dataclasses import dataclass
from unittest import mock

from pdfje.common import Pt
from pdfje.fonts import FontID, Kerned
from pdfje.ops import MultiCommand, SetColor, SetFont
from pdfje.typeset import (
    Box,
    CommandAnd,
    CommandSpan,
    CompoundBox,
    CompoundBoxAnd,
    CompoundBoxSpan,
    Linked,
    SimpleBoxSpan,
    SimpleLine,
    State,
    TextSpan,
    take_line,
    to_boxes,
)


@dataclass(frozen=True, repr=False)
class DummyFont:
    """Helper to create dummy fonts with easily testable metrics"""

    id: FontID
    charwidth: int

    def __repr__(self) -> str:
        return f"DummyFont({self.id.decode()})"

    def width(self, s: str) -> Pt:
        return len(s) * self.charwidth

    def kern(self, s: str) -> Kerned:
        return Kerned((), s)

    def encode(self, s: str) -> bytes:
        raise NotImplementedError()


# simple fonts where the string width is really simple to calculate
FONT_1 = DummyFont(b"Dummy1", charwidth=1)
FONT_2 = DummyFont(b"Dummy2", charwidth=2)


def k(s: str) -> Kerned:
    """Helper to quickly mark a string as minimally kerned"""
    return Kerned((), s)


class TestTakeLine:
    def test_empty(self):
        line, spans = take_line(iter([]), width=0)
        assert line is None
        assert next(spans, None) is None

    def test_empty_span(self):
        line, spans = take_line(
            iter(
                [CommandSpan(SetFont(FONT_1, 12), [], spacewidth=1, height=12)]
            ),
            width=10,
        )
        assert line is None
        assert next(spans, None) is None

    def test_at_least_one_box(self):
        line, spans = take_line(
            iter(
                [
                    CommandSpan(
                        SetFont(FONT_1, 12),
                        [Box(k("Hello"), 14), Box(k("World"), 13)],
                        spacewidth=1,
                        height=12,
                    ),
                ]
            ),
            width=2,
        )
        assert line == CommandAnd(
            SetFont(FONT_1, 12),
            SimpleLine([Box(k("Hello"), 14)], width_left=0, height=12),
        )

        remainder = next(spans)
        assert isinstance(remainder, SimpleBoxSpan)
        assert list(remainder.boxes) == [Box(k("World"), 13)]
        assert remainder.spacewidth == 1
        assert remainder.height == 12

    def test_subset_of_one_span(self):
        line, spans = take_line(
            iter(
                [
                    SimpleBoxSpan([], 1, 12),
                    SimpleBoxSpan([], 1, 12),
                    SimpleBoxSpan([], 1, 12),
                    CompoundBoxSpan(
                        CompoundBox(
                            Box(k("Count"), 15),
                            [
                                (SetFont(FONT_2, 20), Box(k("D"), 2)),
                                (SetFont(FONT_2, 15), Box(k("O"), 2)),
                                (SetColor((1, 0, 0)), Box(k("wn"), 2)),
                            ],
                            height=20,
                        ),
                        [
                            Box(k("wait"), 5),
                            Box(k("for"), 3),
                            Box(k("it..."), 5),
                        ],
                        spacewidth=3,
                        tail_height=15,
                    ),
                ]
            ),
            width=30,
        )
        assert line == CompoundBoxAnd(
            CompoundBox(
                Box(k("Count"), 15),
                [
                    (SetFont(FONT_2, 20), Box(k("D"), 2)),
                    (SetFont(FONT_2, 15), Box(k("O"), 2)),
                    (SetColor((1, 0, 0)), Box(k("wn"), 2)),
                ],
                height=20,
            ),
            SimpleLine([Box(k("wait"), 5)], width_left=-2, height=15),
        )

        remainder = next(spans)
        assert isinstance(remainder, SimpleBoxSpan)
        assert list(remainder.boxes) == [
            Box(k("for"), 3),
            Box(k("it..."), 5),
        ]
        assert remainder.spacewidth == 3
        assert remainder.height == 15

    def test_multiple_spans(self):
        line, spans = take_line(
            iter(
                [
                    SimpleBoxSpan(
                        [
                            Box(k("Hello"), 14),
                            Box(k("World"), 10),
                            Box(k("here"), 3),
                            Box(k("I"), 2),
                            Box(k("am."), 3),
                        ],
                        spacewidth=1,
                        height=12,
                    ),
                    CompoundBoxSpan(
                        CompoundBox(
                            Box(k("Count"), 15),
                            [
                                (SetFont(FONT_2, 20), Box(k("D"), 2)),
                                (SetFont(FONT_2, 15), Box(k("O"), 2)),
                                (SetColor((1, 0, 0)), Box(k("wn"), 2)),
                            ],
                            height=20,
                        ),
                        [
                            Box(k("wait"), 5),
                            Box(k("for"), 3),
                            Box(k("it..."), 5),
                        ],
                        spacewidth=3,
                        tail_height=15,
                    ),
                    CommandSpan(
                        SetFont(FONT_1, 11),
                        [
                            Box(k("one"), 6),
                            Box(k("two"), 6),
                            Box(k("three"), 5),
                            Box(k("four"), 5),
                            Box(k("five"), 5),
                        ],
                        spacewidth=2,
                        height=11,
                    ),
                ]
            ),
            width=100,
        )
        assert line == Linked(
            Linked(
                SimpleLine(
                    [
                        Box(k("Hello"), 14),
                        Box(k("World"), 10),
                        Box(k("here"), 3),
                        Box(k("I"), 2),
                        Box(k("am."), 3),
                    ],
                    width_left=mock.ANY,
                    height=12,
                ),
                CompoundBoxAnd(
                    CompoundBox(
                        Box(k("Count"), 15),
                        [
                            (SetFont(FONT_2, 20), Box(k("D"), 2)),
                            (SetFont(FONT_2, 15), Box(k("O"), 2)),
                            (SetColor((1, 0, 0)), Box(k("wn"), 2)),
                        ],
                        height=20,
                    ),
                    SimpleLine(
                        [
                            Box(k("wait"), 5),
                            Box(k("for"), 3),
                            Box(k("it..."), 5),
                        ],
                        width_left=mock.ANY,
                        height=15,
                    ),
                ),
            ),
            CommandAnd(
                SetFont(FONT_1, 11),
                SimpleLine(
                    [Box(k("one"), 6), Box(k("two"), 6)],
                    width_left=1,
                    height=11,
                ),
            ),
        )
        remainder = next(spans)
        assert isinstance(remainder, SimpleBoxSpan)
        assert list(remainder.boxes) == [
            Box(k("three"), 5),
            Box(k("four"), 5),
            Box(k("five"), 5),
        ]
        assert remainder.spacewidth == 2
        assert remainder.height == 11


class TestToBoxes:
    def test_no_spans(self):
        result = to_boxes([], State(FONT_1, 12))
        try:
            next(result)
        except StopIteration as e:
            assert e.value == State(FONT_1, 12)
        else:
            assert False, "StopIteration not raised"

    def test_one_empty_span(self):
        result = to_boxes(
            [TextSpan(SetFont(FONT_1, 20), "")], State(FONT_1, 12)
        )
        span = next(result)
        assert isinstance(span, CommandSpan)
        assert span.command == SetFont(FONT_1, 20)
        assert list(span.boxes) == []
        assert span.spacewidth == 20

        try:
            next(result)
        except StopIteration as e:
            assert e.value == State(FONT_1, 20)
        else:
            assert False, "StopIteration not raised"

    def test_one_span(self):
        result = to_boxes(
            [
                TextSpan(
                    SetFont(FONT_1, 20),
                    "Hello world! Nice to meet you.",
                )
            ],
            State(FONT_1, 12),
        )
        span = next(result)
        assert isinstance(span, CommandSpan)
        assert span.command == SetFont(FONT_1, 20)
        assert list(span.boxes) == [
            Box(k("Hello"), 5 * 20),
            Box(k("world!"), 6 * 20),
            Box(k("Nice"), 4 * 20),
            Box(k("to"), 2 * 20),
            Box(k("meet"), 4 * 20),
            Box(k("you."), 4 * 20),
        ]
        assert span.spacewidth == 20

        try:
            next(result)
        except StopIteration as e:
            assert e.value == State(FONT_1, 20)
        else:
            assert False, "StopIteration not raised"

    def test_multiple_spans(self):
        lazy_result = to_boxes(
            [
                TextSpan(
                    SetFont(FONT_1, 4),
                    "Hello world! ",
                ),
                TextSpan(
                    SetFont(FONT_2, 5),
                    "Nice to",
                ),
                TextSpan(
                    SetColor((0, 1, 0)),
                    " ",
                ),
                TextSpan(
                    SetFont(FONT_2, 6),
                    "meet you. ",
                ),
                TextSpan(
                    SetColor((1, 0, 0)),
                    "",
                ),
                TextSpan(
                    SetFont(FONT_2, 40),
                    "",
                ),
                TextSpan(
                    SetFont(FONT_1, 7),
                    "and Good",
                ),
                TextSpan(
                    SetFont(FONT_2, 10),
                    "",
                ),
                TextSpan(
                    SetFont(FONT_1, 8),
                    "Bye",
                ),
                TextSpan(
                    SetFont(FONT_1, 9),
                    "!!!! also en",
                ),
                TextSpan(
                    SetFont(FONT_1, 10),
                    "d transmission now.",
                ),
            ],
            State(FONT_1, 12),
        )
        span = next(lazy_result)
        assert isinstance(span, CommandSpan)
        assert span.command == SetFont(FONT_1, 4)
        assert span.spacewidth == 4
        assert list(span.boxes) == [
            Box(k("Hello"), 5 * 4),
            Box(k("world!"), 6 * 4),
        ]

        span = next(lazy_result)
        assert isinstance(span, CommandSpan)
        assert span.command == SetFont(FONT_2, 5)
        assert span.spacewidth == 10
        assert list(span.boxes) == [
            Box(k("Nice"), 4 * 5 * 2),
            Box(k("to"), 2 * 5 * 2),
        ]

        span = next(lazy_result)
        assert isinstance(span, CommandSpan)
        assert span.command == SetColor((0, 1, 0))
        assert span.spacewidth == 10
        assert list(span.boxes) == []

        span = next(lazy_result)
        assert isinstance(span, CommandSpan)
        assert span.command == SetFont(FONT_2, 6)
        assert span.spacewidth == 12
        assert list(span.boxes) == [
            Box(k("meet"), 4 * 6 * 2),
            Box(k("you."), 4 * 6 * 2),
        ]

        span = next(lazy_result)
        assert isinstance(span, CommandSpan)
        assert span.command == MultiCommand(
            [
                SetColor((1, 0, 0)),
                SetFont(FONT_2, 40),
                SetFont(FONT_1, 7),
            ]
        )
        assert span.spacewidth == 7
        assert list(span.boxes) == [
            Box(k("and"), 3 * 7),
        ]

        span = next(lazy_result)
        assert isinstance(span, CompoundBoxSpan)
        assert span.head.prefix == Box(k("Good"), 4 * 7)
        assert list(span.head.segments) == [
            (
                MultiCommand(
                    [
                        SetFont(FONT_2, 10),
                        SetFont(FONT_1, 8),
                    ]
                ),
                Box(k("Bye"), 3 * 8),
            ),
            (
                SetFont(FONT_1, 9),
                Box(k("!!!!"), 4 * 9),
            ),
        ]
        assert span.spacewidth == 9
        assert list(span.tail) == [
            Box(k("also"), 4 * 9),
        ]

        span = next(lazy_result)
        assert isinstance(span, CompoundBoxSpan)
        assert span.head.prefix == Box(k("en"), 2 * 9)
        assert list(span.head.segments) == [
            (
                SetFont(FONT_1, 10),
                Box(k("d"), 1 * 10),
            )
        ]
        assert span.spacewidth == 10
        assert list(span.tail) == [
            Box(k("transmission"), 12 * 10),
            Box(k("now."), 4 * 10),
        ]

        try:
            next(lazy_result)
        except StopIteration as e:
            assert e.value == State(FONT_1, 10, color=(1, 0, 0))
        else:
            assert False, "StopIteration not raised"
