from __future__ import annotations

from typing import Iterable, Sequence

import pytest

from pdfje import RGB, XY, ops
from pdfje.common import PeekableIterator
from pdfje.ops import MultiCommand, SetColor, SetFont
from pdfje.typeset import (
    Boxed,
    Boxes,
    CommandAnd,
    CommandSpan,
    CompoundBoxAnd,
    CompoundBoxSpan,
    CompoundWord,
    Frame,
    Line,
    Linked,
    Span,
    SpanIterator,
    State,
    Word,
    _write_boxes,
    to_graphics,
    to_words,
)

from .common import FONT_1, FONT_2, mkstate, word


class TestLayout:
    def test_empty(self):
        gen = to_graphics(
            as_span_iterator([], mkstate(color=(1, 0, 0))),
        )
        try:
            assert gen.send(Frame(XY(50, 50), 400, 900))
        except StopIteration as e:
            item, frame = e.value
        else:
            pytest.fail("Expected StopIteration, but it was not raised.")

        assert frame == Frame(XY(50, 50), 400, 900)
        assert item is ops.NOTHING

    def test_content_fits_in_one_box(self, spans):
        gen = to_graphics(
            as_span_iterator(spans, mkstate(color=(0, 1, 0))),
        )
        try:
            gen.send(Frame(XY(50, 50), 150, 50_000))
        except StopIteration as e:
            para, frame = e.value
        else:
            pytest.fail("Expected StopIteration, but it was not raised.")

        assert frame == Frame(XY(50, 50), 150, 50_000 - (3 * 25 + 15))
        assert len(para.lines) == 4
        assert para.init == mkstate(color=(0, 1, 0))
        assert para.location == XY(50, 50_050)
        assert para.lines == [
            CommandAnd(
                SetFont(FONT_1, 12),
                Line(
                    [
                        word("aaaa", 15),
                        word("bb", 10),
                        word("aaaa", 15),
                        word("bb", 10),
                        word("aaaa", 15),
                        word("bb", 10),
                        word("aaaa", 15),
                        word("bb", 10),
                        word("aaaa", 15),
                        word("bb", 10),
                        word("aaaa", 15),
                    ],
                    width_left=-1,
                    leading=15,
                    spacewidth=1,
                    spacechar=b" ",
                ),
            ),
            Linked(
                Line(
                    [
                        word("bb", 10),
                        word("aaaa", 15),
                        word("bb", 10),
                        word("aaaa", 15),
                        word("bb", 10),
                        word("aaaa", 15),
                        word("bb", 10),
                        word("aaaa", 15),
                        word("bb", 10),
                    ],
                    width_left=31,
                    leading=15,
                    spacewidth=1,
                    spacechar=b" ",
                ),
                CommandAnd(
                    SetFont(FONT_1, 20),
                    Line(
                        [
                            word("xxxx", 20),
                        ],
                        width_left=10,
                        leading=25,
                        spacewidth=1,
                        spacechar=b" ",
                    ),
                ),
            ),
            Line(
                [
                    word("yyy", 15),
                    word("xxxx", 20),
                    word("yyy", 15),
                    word("xxxx", 20),
                    word("yyy", 15),
                    word("xxxx", 20),
                    word("yyy", 15),
                    word("xxxx", 20),
                ],
                width_left=2,
                leading=25,
                spacewidth=1,
                spacechar=b" ",
            ),
            Linked(
                Line(
                    [
                        word("yyy", 15),
                        word("xxxx", 20),
                        word("yyy", 15),
                    ],
                    width_left=97,
                    leading=25,
                    spacewidth=1,
                    spacechar=b" ",
                ),
                CompoundBoxAnd(
                    CompoundWord(
                        word("A", 3),
                        [
                            (SetFont(FONT_2, 20), word("B", 3)),
                            (SetFont(FONT_2, 15), word("C", 2)),
                            (SetColor(RGB(1, 0, 0)), word("D", 2)),
                        ],
                        leading=25,
                    ),
                    Line(
                        [],
                        width_left=84,
                        leading=18.75,
                        spacewidth=3,
                        spacechar=b" ",
                    ),
                ),
            ),
        ]

    def test_content_fits_in_several_boxes(self, spans):
        gen = to_graphics(
            as_span_iterator(spans, mkstate(color=(0, 0, 1))),
        )

        try:
            para1 = gen.send(Frame(XY(50, 50), 80, 50))
        except StopIteration as e:
            # a common failure case is the generator quitting prematurely
            para = e.value
            assert para is None  # always False
            return

        assert para1.init == mkstate(color=(0, 0, 1))
        assert para1.location == XY(50, 100)
        assert para1.lines == [
            CommandAnd(
                SetFont(FONT_1, 12),
                Line(
                    [
                        word("aaaa", 15),
                        word("bb", 10),
                        word("aaaa", 15),
                        word("bb", 10),
                        word("aaaa", 15),
                        word("bb", 10),
                    ],
                    width_left=-1,
                    leading=15,
                    spacewidth=1,
                    spacechar=b" ",
                ),
            ),
            Line(
                [
                    word("aaaa", 15),
                    word("bb", 10),
                    word("aaaa", 15),
                    word("bb", 10),
                    word("aaaa", 15),
                    word("bb", 10),
                ],
                width_left=-1,
                leading=15,
                spacewidth=1,
                spacechar=b" ",
            ),
            Line(
                [
                    word("aaaa", 15),
                    word("bb", 10),
                    word("aaaa", 15),
                    word("bb", 10),
                    word("aaaa", 15),
                    word("bb", 10),
                ],
                width_left=-1,
                leading=15,
                spacewidth=1,
                spacechar=b" ",
            ),
        ]
        para2 = gen.send(Frame(XY(100, 100), 100, 50))
        assert para2.init == mkstate(FONT_1, 12, (0, 0, 1))
        assert para2.location == XY(100, 150)
        assert para2.lines == [
            Linked(
                Linked(
                    Line(
                        [
                            word("aaaa", 15),
                            word("bb", 10),
                        ],
                        width_left=73,
                        leading=15,
                        spacewidth=1,
                        spacechar=b" ",
                    ),
                    CommandAnd(
                        SetFont(FONT_1, 20),
                        Line(
                            [
                                word("xxxx", 20),
                                word("yyy", 15),
                            ],
                            width_left=36,
                            leading=25,
                            spacewidth=1,
                            spacechar=b" ",
                        ),
                    ),
                ),
                Line(
                    [
                        word("xxxx", 20),
                        word("yyy", 15),
                    ],
                    spacewidth=1,
                    width_left=-1,
                    leading=25,
                    spacechar=b" ",
                ),
            ),
            Line(
                [
                    word("xxxx", 20),
                    word("yyy", 15),
                    word("xxxx", 20),
                    word("yyy", 15),
                    word("xxxx", 20),
                ],
                width_left=5,
                leading=25,
                spacewidth=1,
                spacechar=b" ",
            ),
        ]

        try:
            gen.send(Frame(XY(50, 50), 100, 25))
        except StopIteration as e:
            para3, frame = e.value
        else:
            pytest.fail("Expected StopIteration, but it was not raised.")

        assert frame == Frame(XY(50, 50), 100, 0)
        assert para3.init == mkstate(FONT_1, 20, (0, 0, 1))
        assert para3.location == XY(50, 75)
        assert para3.lines == [
            Linked(
                Line(
                    [
                        word("yyy", 15),
                        word("xxxx", 20),
                        word("yyy", 15),
                    ],
                    width_left=47,
                    leading=25,
                    spacewidth=1,
                    spacechar=b" ",
                ),
                CompoundBoxAnd(
                    CompoundWord(
                        word("A", 3),
                        [
                            (SetFont(FONT_2, 20), word("B", 3)),
                            (SetFont(FONT_2, 15), word("C", 2)),
                            (SetColor(RGB(1, 0, 0)), word("D", 2)),
                        ],
                        leading=25,
                    ),
                    Line(
                        [],
                        width_left=34,
                        leading=18.75,
                        spacewidth=3,
                        spacechar=b" ",
                    ),
                ),
            )
        ]


# FUTURE: make tests less sensitive to non-significant whitespace?
class TestWriteBoxes:
    def test_empty(self):
        assert b"".join(_write_boxes([], b" ")) == b""

    def test_no_kerning(self):
        assert (
            b"".join(_write_boxes([word("abc", 20), word("defg", 10)], b" "))
            == b"(abc defg) Tj\n"
        )

    def test_kerning(self):
        assert (
            b"".join(
                _write_boxes(
                    [
                        Word(b"abc", [], 20),
                        Word(b"defg", [(2, -30)], 30),
                        Word(b"hijklmn", [(0, -35), (2, -5), (6, -20)], 45),
                    ],
                    b" ",
                )
            )
            == b"[(abc de) 30 (fg ) 35 (hi) 5 (jklm) 20 (n) ] TJ\n"
        )

    def test_kern_first_char(self):
        assert (
            b"".join(_write_boxes([Word(b"abc", [(0, -20)], 20)], b" "))
            == b"[20 (abc) ] TJ\n"
        )

    def test_kern_last_char(self):
        assert (
            b"".join(_write_boxes([Word(b"abc", [(3, -20)], 20)], b" "))
            == b"[(abc) 20 ] TJ\n"
        )


class TestChainBox:
    def test_empty(self):
        assert list(Word.chain_kerning([], 2)) == []

    def test_one(self):
        assert list(
            Word.chain_kerning(
                [Word(b"hello world", [(0, -10), (2, -20), (11, -30)], 50)], 1
            )
        ) == [(0, -10), (2, -20), (11, -30)]

    def test_multiple(self):
        result = Word.chain_kerning(
            [
                Word(b"hello", [(1, -40)], 60),
                Word(b"blablabla", [], 100),
                Word(b"world", [(3, -10), (5, -20)], 70),
                Word(b"", [], 100),
            ],
            2,
        )
        assert list(result) == [
            (1, -40),
            (21, -10),
            (23, -20),
        ]


class TestTakeLine:
    def test_empty(self):
        spans = as_span_iterator([], State.DEFAULT)
        line = spans.take_line(0)
        assert line is None
        assert next(spans, None) is None

    def test_empty_span(self):
        spans = as_span_iterator(
            [
                CommandSpan(
                    SetFont(FONT_1, 12),
                    Boxes(
                        PeekableIterator(),
                        spacewidth=1,
                        leading=15,
                        spacechar=b" ",
                    ),
                )
            ],
            State.DEFAULT,
        )
        line = spans.take_line(10)
        assert line is None
        assert next(spans, None) is None

    def test_at_least_one_box(self):
        spans = as_span_iterator(
            [
                CommandSpan(
                    SetFont(FONT_1, 12),
                    Boxes(
                        PeekableIterator(
                            [word("Hello", 14), word("World", 13)]
                        ),
                        spacewidth=1,
                        leading=15,
                        spacechar=b" ",
                    ),
                ),
            ],
            State.DEFAULT,
        )
        line = spans.take_line(2)
        assert line is not None
        assert line == CommandAnd(
            SetFont(FONT_1, 12),
            Line(
                [word("Hello", 14)],
                width_left=0,
                leading=15,
                spacewidth=1,
                spacechar=b" ",
            ),
        )
        assert line.leading == 15

        remainder = next(spans)
        assert isinstance(remainder, Boxes)
        assert list(remainder.words) == [word("World", 13)]
        assert remainder.spacewidth == 1
        assert remainder.leading == 15

    def test_too_much_room_to_fill(self):
        spans = as_span_iterator(
            [
                CommandSpan(
                    SetFont(FONT_1, 12),
                    Boxes(
                        PeekableIterator(
                            [word("Hello", 14), word("World", 13)]
                        ),
                        spacewidth=1,
                        leading=15,
                        spacechar=b" ",
                    ),
                ),
            ],
            State.DEFAULT,
        )
        line = spans.take_line(10_000)
        assert line is not None
        assert line == CommandAnd(
            SetFont(FONT_1, 12),
            Line(
                [word("Hello", 14), word("World", 13)],
                width_left=9_971,
                leading=15,
                spacewidth=1,
                spacechar=b" ",
            ),
        )
        assert line.leading == 15

        assert next(spans, None) is None

    def test_subset_of_one_span(self):
        spans = as_span_iterator(
            [
                Boxes(PeekableIterator(), 1, 12, b" "),
                Boxes(PeekableIterator(), 1, 12, b" "),
                Boxes(PeekableIterator(), 1, 12, b" "),
                CompoundBoxSpan(
                    CompoundWord(
                        word("Count", 15),
                        [
                            (SetFont(FONT_2, 20), word("D", 2)),
                            (SetFont(FONT_2, 15), word("O", 2)),
                            (SetColor(RGB(1, 0, 0)), word("wn", 2)),
                        ],
                        leading=25,
                    ),
                    Boxes(
                        PeekableIterator(
                            [
                                word("wait", 5),
                                word("for", 3),
                                word("it...", 5),
                            ]
                        ),
                        spacewidth=3,
                        leading=18.75,
                        spacechar=b" ",
                    ),
                ),
            ],
            State.DEFAULT,
        )
        line = spans.take_line(30)
        assert line is not None
        assert line == CompoundBoxAnd(
            CompoundWord(
                word("Count", 15),
                [
                    (SetFont(FONT_2, 20), word("D", 2)),
                    (SetFont(FONT_2, 15), word("O", 2)),
                    (SetColor(RGB(1, 0, 0)), word("wn", 2)),
                ],
                leading=25,
            ),
            Line(
                [word("wait", 5)],
                width_left=-2,
                leading=18.75,
                spacewidth=3,
                spacechar=b" ",
            ),
        )
        assert line.leading == 25

        remainder = next(spans)
        assert isinstance(remainder, Boxes)
        assert list(remainder.words) == [
            word("for", 3),
            word("it...", 5),
        ]
        assert remainder.spacewidth == 3
        assert remainder.leading == 18.75

    def test_multiple_spans(self):
        spans = as_span_iterator(
            [
                Boxes(
                    PeekableIterator(
                        [
                            word("Hello", 14),
                            word("World", 10),
                            word("here", 3),
                            word("I", 2),
                            word("am.", 3),
                        ]
                    ),
                    spacewidth=1,
                    leading=15,
                    spacechar=b" ",
                ),
                CompoundBoxSpan(
                    CompoundWord(
                        word("Count", 15),
                        [
                            (SetFont(FONT_2, 20), word("D", 2)),
                            (SetFont(FONT_2, 15), word("O", 2)),
                            (SetColor(RGB(1, 0, 0)), word("wn", 2)),
                        ],
                        leading=25,
                    ),
                    Boxes(
                        PeekableIterator(
                            [
                                word("wait", 5),
                                word("for", 3),
                                word("it...", 5),
                            ]
                        ),
                        spacewidth=3,
                        leading=18,
                        spacechar=b" ",
                    ),
                ),
                CommandSpan(
                    SetFont(FONT_1, 11),
                    Boxes(
                        PeekableIterator(),
                        spacewidth=2,
                        leading=11,
                        spacechar=b" ",
                    ),
                ),
                CommandSpan(
                    SetFont(FONT_1, 11),
                    Boxes(
                        PeekableIterator(
                            [
                                word("one", 6),
                                word("two", 6),
                                word("three", 5),
                                word("four", 5),
                                word("five", 5),
                            ]
                        ),
                        spacewidth=2,
                        leading=11,
                        spacechar=b" ",
                    ),
                ),
                CommandSpan(
                    SetFont(FONT_1, 20),
                    Boxes(
                        PeekableIterator(
                            [
                                word("LAST", 6),
                            ]
                        ),
                        spacewidth=1,
                        leading=25,
                        spacechar=b" ",
                    ),
                ),
            ],
            State.DEFAULT,
        )
        line = spans.take_line(100)
        assert line is not None
        assert line == Linked(
            Linked(
                Line(
                    [
                        word("Hello", 14),
                        word("World", 10),
                        word("here", 3),
                        word("I", 2),
                        word("am.", 3),
                    ],
                    width_left=63,
                    leading=15,
                    spacewidth=1,
                    spacechar=b" ",
                ),
                CompoundBoxAnd(
                    CompoundWord(
                        word("Count", 15),
                        [
                            (SetFont(FONT_2, 20), word("D", 2)),
                            (SetFont(FONT_2, 15), word("O", 2)),
                            (SetColor(RGB(1, 0, 0)), word("wn", 2)),
                        ],
                        leading=25,
                    ),
                    Line(
                        [
                            word("wait", 5),
                            word("for", 3),
                            word("it...", 5),
                        ],
                        width_left=17,
                        leading=18,
                        spacewidth=3,
                        spacechar=b" ",
                    ),
                ),
            ),
            CommandAnd(
                SetFont(FONT_1, 11),
                Line(
                    [word("one", 6), word("two", 6)],
                    width_left=1,
                    leading=11,
                    spacewidth=2,
                    spacechar=b" ",
                ),
            ),
        )
        assert line.leading == 25

        remainder = next(spans)
        assert isinstance(remainder, Boxes)
        assert list(remainder.words) == [
            word("three", 5),
            word("four", 5),
            word("five", 5),
        ]
        assert remainder.spacewidth == 2
        assert remainder.leading == 11
        assert isinstance(next(spans), CommandSpan)


class TestToWords:
    def test_no_spans(self):
        result = to_words([], mkstate(FONT_1, 12))
        assert next(result, None) is None

    def test_one_empty_span(self):
        result = to_words([Span(SetFont(FONT_1, 20), "")], mkstate(FONT_1, 12))
        span, state = next(result)
        assert isinstance(span, CommandSpan)
        assert span.command == SetFont(FONT_1, 20)
        assert list(span.tail.words) == []
        assert span.tail.spacewidth == 20

        assert state == mkstate(FONT_1, 20)

    def test_one_span(self):
        result = to_words(
            [
                Span(
                    SetFont(FONT_1, 20),
                    "Hello world! Nice to meet you.",
                )
            ],
            mkstate(FONT_1, 12),
        )
        span, state = next(result)
        assert isinstance(span, CommandSpan)
        assert span.command == SetFont(FONT_1, 20)
        assert list(span.tail.words) == [
            word("Hello", 5 * 20),
            word("world!", 6 * 20),
            word("Nice", 4 * 20),
            word("to", 2 * 20),
            word("meet", 4 * 20),
            word("you.", 4 * 20),
        ]
        assert span.tail.spacewidth == 20
        assert next(result, None) is None
        assert state == mkstate(FONT_1, 20)

    def test_multiple_spans(self):
        lazy_result = to_words(
            [
                Span(
                    SetFont(FONT_1, 4),
                    "Hello world! ",
                ),
                Span(
                    SetFont(FONT_2, 5),
                    "Nice to",
                ),
                Span(
                    SetColor(RGB(0, 1, 0)),
                    " ",
                ),
                Span(
                    SetFont(FONT_2, 6),
                    "meet you. ",
                ),
                Span(
                    SetColor(RGB(1, 0, 0)),
                    "",
                ),
                Span(
                    SetFont(FONT_2, 40),
                    "",
                ),
                Span(
                    SetFont(FONT_1, 7),
                    "and Good",
                ),
                Span(
                    SetFont(FONT_2, 10),
                    "",
                ),
                Span(
                    SetFont(FONT_1, 8),
                    "Bye",
                ),
                Span(
                    SetFont(FONT_1, 9),
                    "!!!! also en",
                ),
                Span(
                    SetFont(FONT_1, 10),
                    "d transmission now.",
                ),
            ],
            mkstate(FONT_1, 12),
        )
        span, state = next(lazy_result)
        assert isinstance(span, CommandSpan)
        assert span.command == SetFont(FONT_1, 4)
        assert span.tail.spacewidth == 4
        assert list(span.tail.words) == [
            word("Hello", 5 * 4),
            word("world!", 6 * 4),
        ]
        assert state == mkstate(FONT_1, 4)

        span, state = next(lazy_result)
        assert isinstance(span, CommandSpan)
        assert span.command == SetFont(FONT_2, 5)
        assert span.tail.spacewidth == 10
        assert list(span.tail.words) == [
            word("Nice", 4 * 5 * 2),
            word("to", 2 * 5 * 2),
        ]
        assert state == mkstate(FONT_2, 5)

        span, state = next(lazy_result)
        assert isinstance(span, CommandSpan)
        assert span.command == SetColor(RGB(0, 1, 0))
        assert span.tail.spacewidth == 10
        assert list(span.tail.words) == []
        assert state == mkstate(FONT_2, 5, color=(0, 1, 0))

        span, state = next(lazy_result)
        assert isinstance(span, CommandSpan)
        assert span.command == SetFont(FONT_2, 6)
        assert span.tail.spacewidth == 12
        assert list(span.tail.words) == [
            word("meet", 4 * 6 * 2),
            word("you.", 4 * 6 * 2),
        ]
        assert state == mkstate(FONT_2, 6, color=(0, 1, 0))

        span, state = next(lazy_result)
        assert isinstance(span, CommandSpan)
        assert span.command == MultiCommand(
            [
                SetColor(RGB(1, 0, 0)),
                SetFont(FONT_2, 40),
                SetFont(FONT_1, 7),
            ]
        )
        assert span.tail.spacewidth == 7
        assert list(span.tail.words) == [
            word("and", 3 * 7),
        ]
        assert state == mkstate(FONT_1, 7, color=(1, 0, 0))

        span, state = next(lazy_result)
        assert isinstance(span, CompoundBoxSpan)
        assert span.head.prefix == word("Good", 4 * 7)
        assert list(span.head.segments) == [
            (
                MultiCommand(
                    [
                        SetFont(FONT_2, 10),
                        SetFont(FONT_1, 8),
                    ]
                ),
                word("Bye", 3 * 8),
            ),
            (
                SetFont(FONT_1, 9),
                word("!!!!", 4 * 9),
            ),
        ]
        assert span.tail.spacewidth == 9
        assert list(span.tail.words) == [
            word("also", 4 * 9),
        ]
        assert state == mkstate(FONT_1, 9, color=(1, 0, 0))

        span, state = next(lazy_result)
        assert isinstance(span, CompoundBoxSpan)
        assert span.head.prefix == word("en", 2 * 9)
        assert list(span.head.segments) == [
            (
                SetFont(FONT_1, 10),
                word("d", 1 * 10),
            )
        ]
        assert span.tail.spacewidth == 10
        assert list(span.tail.words) == [
            word("transmission", 12 * 10),
            word("now.", 4 * 10),
        ]
        assert state == mkstate(FONT_1, 10, color=(1, 0, 0))

        assert next(lazy_result, None) is None


@pytest.fixture
def spans() -> Sequence[Boxed]:
    return [
        CommandSpan(
            SetFont(FONT_1, 12),
            Boxes(
                PeekableIterator([word("aaaa", 15), word("bb", 10)] * 10),
                spacewidth=1,
                leading=15,
                spacechar=b" ",
            ),
        ),
        CommandSpan(
            SetFont(FONT_1, 20),
            Boxes(
                PeekableIterator([word("xxxx", 20), word("yyy", 15)] * 6),
                spacewidth=1,
                leading=25,
                spacechar=b" ",
            ),
        ),
        CompoundBoxSpan(
            CompoundWord(
                word("A", 3),
                [
                    (SetFont(FONT_2, 20), word("B", 3)),
                    (SetFont(FONT_2, 15), word("C", 2)),
                    (SetColor(RGB(1, 0, 0)), word("D", 2)),
                ],
                leading=25,
            ),
            Boxes(
                PeekableIterator(),
                spacewidth=3,
                leading=18.75,
                spacechar=b" ",
            ),
        ),
    ]


def as_span_iterator(items: Iterable[Boxed], init: State) -> SpanIterator:
    return SpanIterator(SpanIterator._add_states(items, init), init)
