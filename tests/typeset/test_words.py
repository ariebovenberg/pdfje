from dataclasses import replace
from itertools import cycle, islice
from typing import TYPE_CHECKING, Sequence

import pytest
from hypothesis import given
from hypothesis.strategies import lists, sampled_from

from pdfje import RGB
from pdfje.common import XY
from pdfje.ops import MultiCommand, SetColor, SetFont
from pdfje.typeset import Span
from pdfje.typeset.words import (
    Box,
    EmptyLine,
    Frame,
    Line,
    MixedWord,
    Paragraph,
    Passage,
    Redo,
    SizedMixedWord,
    SizedString,
    SubPassage,
    Words,
    slice_size,
    split,
    typeset,
    wrap,
)

from .common import FONT_1, FONT_2, FONT_3, genreturn, mkstate

if TYPE_CHECKING:
    approx = float.__call__
else:
    from pytest import approx


SPLITS: list[Words] = [
    SetFont(FONT_1, 4),
    Passage("Simple is  better than "),
    SetFont(FONT_3, 5),
    Passage("complex. Complex"),
    SetColor(RGB(0, 1, 0)),
    Passage(" "),
    SetFont(FONT_3, 6),
    Passage(" is better "),
    MultiCommand(
        [
            SetColor(RGB(1, 0, 0)),
            SetFont(FONT_3, 40),
            SetFont(FONT_1, 7),
        ]
    ),
    Passage("than  "),
    MixedWord(
        "com",
        [
            (
                MultiCommand([SetFont(FONT_3, 10), SetFont(FONT_1, 8)]),
                "pli",
            ),
            (SetFont(FONT_1, 9), "cated.  "),
        ],
    ),
    Passage("Flat   is "),
    MixedWord("bet", [(SetFont(FONT_1, 10), "ter  ")]),
    Passage("than nested.    "),
]

PARAGRAPH = Paragraph(
    [
        Line(
            [SizedString("HELLO!", [], 50)],
            20,
            20,
            "!",
            mkstate(FONT_3, 12),
        )
    ],
    mkstate(FONT_3, 10),
)


def _plaintext(x: Paragraph | Line) -> str:
    "Testing helper to get the plain text from various classes"
    if isinstance(x, Paragraph):
        lines = x.lines
    elif isinstance(x, Line):
        lines = [x]

    return "".join(
        item.content
        if isinstance(item, SizedString)
        else (item.head.content + "".join(s.content for _, s in item.segments))
        if isinstance(item, SizedMixedWord)
        else ""
        for ln in lines
        for item in ln.segments
    )


class TestTypeset:
    def test_no_content_into_empty_frame(self):
        frame = Frame([], Box(XY(50, 50), 200, 400))
        gen = typeset([], mkstate(FONT_3), frame)
        assert genreturn(gen) == frame

    def test_no_content_into_nonempty_frame(self):
        frame = Frame([PARAGRAPH], Box(XY(50, 50), 200, 400))
        gen = typeset([], mkstate(FONT_3), frame)
        assert genreturn(gen) == frame

    def test_content_into_tiny_empty_frame(self):
        box = Box(XY(50, 50), 200, 0.01)
        gen = typeset(SPLITS, mkstate(FONT_3), Frame([], box))
        frame = next(gen)
        [para] = frame.blocks
        assert len(para.lines) == 1
        assert frame.capacity.height == approx(0.01 - para.lines[0].lead)
        assert _plaintext(para) == "Simple is  better than complex. "

        frame = gen.send(box)
        [para] = frame.blocks
        assert len(para.lines) == 1
        assert frame.capacity.height == approx(0.01 - para.lines[0].lead)
        assert _plaintext(para) == "Complex  is better "

        # TODO: continue

    def test_content_into_tiny_nonempty_frame(self):
        frame = Frame([PARAGRAPH], Box(XY(50, 50), 200, 0.01))
        gen = typeset(SPLITS, mkstate(FONT_3), frame)
        new_frame = next(gen)
        assert new_frame == frame
        # TODO: continue

    def test_content_into_very_tall_empty_frame(self):
        frame = Frame([PARAGRAPH], Box(XY(50, 50), 200, 10_000))
        gen = typeset(SPLITS, mkstate(FONT_3), frame)
        new_frame = genreturn(gen)
        [_, paragraph, *other] = new_frame.blocks
        assert not other
        assert new_frame.capacity.height == approx(
            10_000 - sum(n.lead for n in paragraph.lines)
        )
        assert paragraph.lines
        [*_, last_item] = paragraph.lines[-1].segments
        assert isinstance(last_item, SizedString)
        assert last_item.content == "than nested.    "

    def test_content_into_very_wide_empty_frame(self):
        frame = Frame([PARAGRAPH], Box(XY(50, 50), 10_000, 50))
        gen = typeset(SPLITS, mkstate(FONT_3), frame)
        new_frame = genreturn(gen)
        [_, paragraph, *other] = new_frame.blocks
        assert not other
        [line, *other_lines] = paragraph.lines
        assert not other_lines
        [*_, last_item] = line.segments
        assert isinstance(last_item, SizedString)
        assert last_item.content == "than nested.    "
        assert new_frame.capacity.height == approx(50 - line.lead)

    def test_content_into_medium_frames(self):
        box = Box(XY(50, 50), 200, 14)
        frame = Frame([PARAGRAPH], box)
        gen = typeset(SPLITS * 2, mkstate(FONT_3), frame)
        new_frame = next(gen)
        assert new_frame.capacity == Box(XY(50, 50), 200, approx(0.25))
        [_, para] = new_frame.blocks
        assert len(para.lines) == 2
        assert (
            _plaintext(para)
            == "Simple is  better than complex. Complex  is better "
        )

        new_frame = gen.send(Box(XY(30, 30), 200, 40))
        [para] = new_frame.blocks
        assert para.state == mkstate(FONT_1, 7, (1, 0, 0))
        assert len(para.lines) == 3
        assert _plaintext(para) == (
            "than  complicated.  Flat   is better  than nested.    "
            "Simple is  "
        )
        assert new_frame.capacity == Box(
            XY(30, 30), 200, 40 - sum(n.lead for n in para.lines)
        )
        new_frame = genreturn(gen, Box(XY(30, 30), 200, 10_000))
        [para] = new_frame.blocks
        assert para.state == mkstate(FONT_1, 4, (1, 0, 0))
        assert _plaintext(para) == (
            "better than complex. Complex  is "
            "better than  complicated.  Flat   is better  than nested.    "
        )

    # TODO: last line overflows into next frame
    # TODO: exact height

    # def test_frame_no_capacity(self):
    #     gen = Frame.fill(SPLITS, mkstate(FONT_3, 12))
    #     frame = gen.send(Frame([], 200, 0.01, XY(50, 50)))
    #     assert len(frame.blocks) == 1
    #     assert len(frame.blocks[0].lines) == 1
    #     assert frame.height_leftover == approx(-6.24)


class TestSplit:
    def test_no_spans(self):
        assert list(split([])) == []

    def test_one_empty_span(self):
        assert list(split([Span(SetFont(FONT_1, 20), "")])) == [
            SetFont(FONT_1, 20),
            Passage(""),
        ]

    def test_one_span(self):
        assert list(
            split(
                [
                    Span(
                        SetFont(FONT_1, 20),
                        "Explicit is better than implicit. ",
                    )
                ],
            )
        ) == [
            SetFont(FONT_1, 20),
            Passage("Explicit is better than implicit. "),
        ]

    def test_multiple_spans(self):
        assert list(
            split(
                [
                    Span(SetFont(FONT_1, 4), "Simple is  better than "),
                    Span(SetFont(FONT_2, 5), "complex. Complex"),
                    Span(SetColor(RGB(0, 1, 0)), " "),
                    Span(SetFont(FONT_2, 6), " is better "),
                    Span(SetColor(RGB(1, 0, 0)), ""),
                    Span(SetFont(FONT_2, 40), ""),
                    Span(SetFont(FONT_1, 7), "than  com"),
                    Span(SetFont(FONT_2, 10), ""),
                    Span(SetFont(FONT_1, 8), "pli"),
                    Span(SetFont(FONT_1, 9), "cated.  Flat   is bet"),
                    Span(SetFont(FONT_1, 10), "ter  than nested.    "),
                ],
            )
        ) == [
            SetFont(FONT_1, 4),
            Passage("Simple is  better than "),
            SetFont(FONT_2, 5),
            Passage("complex. Complex"),
            SetColor(RGB(0, 1, 0)),
            Passage(" "),
            SetFont(FONT_2, 6),
            Passage(" is better "),
            MultiCommand(
                [
                    SetColor(RGB(1, 0, 0)),
                    SetFont(FONT_2, 40),
                    SetFont(FONT_1, 7),
                ]
            ),
            Passage("than  "),
            MixedWord(
                "com",
                [
                    (
                        MultiCommand(
                            [SetFont(FONT_2, 10), SetFont(FONT_1, 8)]
                        ),
                        "pli",
                    ),
                    (SetFont(FONT_1, 9), "cated.  "),
                ],
            ),
            Passage("Flat   is "),
            MixedWord("bet", [(SetFont(FONT_1, 10), "ter  ")]),
            Passage("than nested.    "),
        ]


class TestSliceSize:
    def test_only_space(self):
        assert slice_size(
            "  ", mkstate(FONT_3, 10), " ", 10_000, 0, True
        ) == SubPassage(SizedString("  ", [], 40), 20, " ", 2)

    def test_fits_fully(self):
        assert slice_size(
            "Now is better\N{NO-BREAK SPACE}than   never. ",
            mkstate(FONT_3, 6),
            " ",
            10_000,
            0,
            True,
        ) == SubPassage(
            SizedString(
                "Now is better\xa0than   never. ",
                [
                    (0, -10),
                    (2, -25),
                    (3, -10),
                    (21, -5),
                    (23, -30),
                    (24, -30),
                    (26, -40),
                    (27, -15),
                ],
                approx((7.955 + 6 + 28 + 13.880) * 6),
            ),
            (2 - 0.015) * 6,
            " ",
            28,
        )

    def test_nonspace_end(self):
        assert slice_size(
            "Now is better\N{NO-BREAK SPACE}than   never.",
            mkstate(FONT_3, 6),
            " ",
            10_000,
            0,
            True,
        ) == SubPassage(
            SizedString(
                "Now is better\xa0than   never.",
                [
                    (0, -10),
                    (2, -25),
                    (3, -10),
                    (21, -5),
                    (23, -30),
                    (24, -30),
                    (26, -40),
                ],
                approx((7.955 + 6 + 28 + 11.895) * 6),
            ),
            0,
            ".",
            27,
        )

    def test_start_index(self):
        sub = slice_size(
            "say: Now is better\N{NO-BREAK SPACE}than   never. ",
            mkstate(FONT_3, 6),
            " ",
            10_000,
            5,
            True,
        )
        assert sub == SubPassage(
            SizedString(
                "Now is better\xa0than   never. ",
                [
                    (0, -10),
                    (2, -25),
                    (3, -10),
                    (21, -5),
                    (23, -30),
                    (24, -30),
                    (26, -40),
                    (27, -15),
                ],
                approx((7.955 + 6 + 28 + 13.880) * 6),
            ),
            (2 - 0.015) * 6,
            " ",
            33,
        )

    def test_partial_fit(self):
        sub = slice_size(
            "Now is better\N{NO-BREAK SPACE}than   never. ",
            mkstate(FONT_3, 6),
            " ",
            40 * 6,
            0,
            True,
        )
        assert sub == SubPassage(
            SizedString(
                "Now is better\xa0than   ",
                [(0, -10), (2, -25), (3, -10)],
                approx((7.955 + 6 + 28) * 6),
            ),
            2 * 6,
            " ",
            21,
        )

    def test_nothing_fits(self):
        sub = slice_size(
            "Now is better\N{NO-BREAK SPACE}than   never. ",
            mkstate(FONT_3, 6),
            " ",
            0.001,
            0,
            True,
        )
        assert sub == SubPassage(SizedString("", [], 0), 0, " ", 0)

    def test_nothing_fits_but_empty_not_allowed(self):
        sub = slice_size(
            "Now is better\N{NO-BREAK SPACE}than   never. ",
            mkstate(FONT_3, 6),
            " ",
            0.001,
            0,
            False,
        )
        assert sub == SubPassage(
            SizedString("Now ", [(0, -10), (2, -25), (3, -10)], approx(47.73)),
            approx(11.94),
            " ",
            4,
        )


def test_size_mixed_word():
    state = mkstate(FONT_3, 12)
    word = MixedWord(
        "Com",
        [
            (SetColor(RGB(0, 0, 1)), "pli"),
            (SetFont(FONT_3, 20), "ca"),
            (
                MultiCommand(
                    [
                        SetFont(FONT_3, 12),
                        SetColor(RGB(0, 0, 1)),
                    ]
                ),
                "ted. ",
            ),
        ],
    )
    assert word.size(state, prev=" ") == SizedMixedWord(
        SizedString("Com", [(0, -15)], (3 * 2 - 0.015) * 12),
        [
            (
                SetColor(RGB(0, 0, 1)),
                SizedString("pli", [(0, -10)], (3 * 2 - 0.01) * 12),
            ),
            (SetFont(FONT_3, 20), SizedString("ca", [], 2 * 2 * 20)),
            (
                MultiCommand([SetFont(FONT_3, 12), SetColor(RGB(0, 0, 1))]),
                SizedString("ted. ", [(3, -5), (4, -15)], (5 * 2 - 0.02) * 12),
            ),
        ],
        343.46,
        20 * 1.25,
        mkstate(FONT_3, 12, color=(0, 0, 1)),
        (2 - 0.015) * 12,
    )


class TestWrapMixedWord:
    WORD = MixedWord(
        "Com",
        [
            (SetColor(RGB(0, 0, 1)), "pli"),
            (SetFont(FONT_3, 20), "ca"),
            (
                MultiCommand([SetFont(FONT_3, 12), SetColor(RGB(0, 0, 0))]),
                "ted. ",
            ),
        ],
    )

    def test_new_line_enough_capacity(self):
        state = mkstate(FONT_3, 10)
        gen = self.WORD.wrap(Line([], 10_000, 20, None, state))
        line = genreturn(gen)
        assert line == Line(
            [self.WORD.size(state, None)],
            approx(10_000 - self.WORD.size(state, None).width),
            25,
            " ",
            mkstate(FONT_3, 12),
        )

    def test_new_line_just_enough_capacity_if_space_is_trimmed(self):
        state = mkstate(FONT_3, 10)
        gen = self.WORD.wrap(
            Line([], self.WORD.size(state, None).width - 2, 20, None, state)
        )
        line = genreturn(gen)
        assert line == Line(
            [self.WORD.size(state, None)],
            approx(-2),
            25,
            " ",
            mkstate(FONT_3, 12),
        )

    def test_new_line_not_enough_capacity(self):
        state = mkstate(FONT_3, 10)
        gen = self.WORD.wrap(
            Line([], self.WORD.size(state, None).width - 100, 20, None, state)
        )
        line = genreturn(gen)
        assert line == Line(
            [self.WORD.size(state, None)],
            approx(-100),
            25,
            " ",
            mkstate(FONT_3, 12),
        )

    def test_existing_line_with_enough_capacity(self):
        state = mkstate(FONT_3, 10)
        prev = Line(
            [SizedString("better than  ", [], 300)], 10_000, 20, " ", state
        )
        gen = self.WORD.wrap(prev)
        line = genreturn(gen)
        assert line == Line(
            [
                SizedString("better than  ", [], 300),
                self.WORD.size(state, " "),
            ],
            approx(10_000 - self.WORD.size(state, " ").width),
            25,
            " ",
            mkstate(FONT_3, 12),
        )

    def test_existing_line_with_just_enough_capacity(self):
        state = mkstate(FONT_3, 10)
        prev = Line(
            [SizedString("better than  ", [], 300)],
            self.WORD.size(state, " ").width - 2,
            20,
            " ",
            state,
        )
        gen = self.WORD.wrap(prev)
        line = genreturn(gen)
        assert line == Line(
            [
                SizedString("better than  ", [], 300),
                self.WORD.size(state, " "),
            ],
            approx(-2),
            25,
            " ",
            mkstate(FONT_3, 12),
        )

    def test_existing_line_with_no_capacity(self):
        state = mkstate(FONT_3, 10)
        prev = Line(
            [SizedString("better than  ", [], 300)],
            self.WORD.size(state, " ").width - 80,
            20,
            " ",
            state,
        )
        gen = self.WORD.wrap(prev)
        assert next(gen) == prev
        line = genreturn(gen, 10_000)
        assert line.segments[0].width == approx(
            self.WORD.size(state, None).width
        )
        assert line.space == approx(10_000 - self.WORD.size(state, None).width)
        assert line.lead == 25
        assert line.end == " "
        assert line.state == mkstate(FONT_3, 12)


class TestWrapPassage:
    def test_new_line_empty(self):
        state = mkstate(FONT_3, 10)
        txt = Passage(" ")
        gen = txt.wrap(EmptyLine(10_000, state))
        line = genreturn(gen)
        assert line == Line(
            [SizedString(" ", [], 20)], 10_000 - 20, 12.5, " ", state
        )

    def test_new_line_with_just_enough_capacity_if_space_is_trimmed(self):
        state = mkstate(FONT_3, 10)
        txt = Passage("Readability counts. ")
        prev = Line([SetFont(FONT_3, 10)], 221, 12.5, None, state)
        gen = txt.wrap(prev)
        line = next(gen)
        assert line == Line(
            [
                SetFont(FONT_3, 10),
                SizedString("Readability ", [], 240),
            ],
            -19,
            12.5,
            " ",
            state,
        )
        last = genreturn(gen, 10_000)
        assert last == Line(
            [SizedString("counts. ", [(7, -15)], 159.85)],
            9840.15,
            12.5,
            " ",
            state,
        )

    def test_new_line_with_partial_capacity(self):
        state = mkstate(FONT_3, 10)
        txt = Passage("Readability counts. ")
        prev = Line([SetFont(FONT_3, 10)], 250, 12.5, None, state)
        gen = txt.wrap(prev)
        line = next(gen)
        assert line == Line(
            [
                SetFont(FONT_3, 10),
                SizedString("Readability ", [], 240),
            ],
            10,
            12.5,
            " ",
            state,
        )
        last = genreturn(gen, 10_000)
        assert last == Line(
            [SizedString("counts. ", [(7, -15)], 159.85)],
            9840.15,
            12.5,
            " ",
            state,
        )

    def test_new_line_with_full_capacity(self):
        state = mkstate(FONT_3, 10)
        prev = Line([SetFont(FONT_3, 10)], 500, 12.5, None, state)
        txt = Passage("Readability counts. ")
        gen = txt.wrap(prev)
        line = genreturn(gen)
        assert line == Line(
            [
                SetFont(FONT_3, 10),
                SizedString(
                    "Readability counts. ",
                    [(12, -15), (19, -15)],
                    approx(400 - 0.3),
                ),
            ],
            approx(100 + 0.3),
            12.5,
            " ",
            state,
        )

    def test_new_line_with_no_capacity(self):
        state = mkstate(FONT_3, 10)
        prev = Line([SetFont(FONT_3, 10)], 1, 12.5, None, state)
        txt = Passage("Readability counts. ")
        gen = txt.wrap(prev)
        line = next(gen)
        assert line == Line(
            [
                SetFont(FONT_3, 10),
                SizedString("Readability ", [], 240),
            ],
            -239,
            12.5,
            " ",
            state,
        )
        last = genreturn(gen, 10_000)
        assert last == Line(
            [SizedString("counts. ", [(7, -15)], 159.85)],
            9840.15,
            12.5,
            " ",
            state,
        )

    def test_existing_line_empty(self):
        state = mkstate(FONT_3, 10)
        prev = Line(
            [SizedString("better than dense. ", [], 300)], 300, 20, " ", state
        )
        txt = Passage("  ")
        gen = txt.wrap(prev)
        line = genreturn(gen)
        assert line == Line(
            [
                SizedString("better than dense. ", [], 300),
                SizedString("  ", [], 40),
            ],
            260,
            20,
            " ",
            state,
        )

    def test_existing_line_with_partial_capacity(self):
        state = mkstate(FONT_3, 10)
        prev = Line(
            [SizedString("better than dense. ", [], 300)], 300, 20, " ", state
        )
        txt = Passage("Readability counts. ")
        gen = txt.wrap(prev)
        line = next(gen)
        assert line == Line(
            [
                SizedString("better than dense. ", [], 300),
                SizedString("Readability ", [], 240),
            ],
            60,
            20,
            " ",
            state,
        )
        last = genreturn(gen, 10_000)
        assert last == Line(
            [SizedString("counts. ", [(7, -15)], 159.85)],
            9840.15,
            12.5,
            " ",
            state,
        )

    def test_existing_line_with_no_capacity(self):
        state = mkstate(FONT_3, 10)
        prev = Line(
            [SizedString("better than dense. ", [], 300)],
            0.01,
            20,
            " ",
            state,
        )
        txt = Passage("Readability counts. ")
        gen = txt.wrap(prev)
        line = next(gen)
        assert line == prev
        last = genreturn(gen, 10_000)
        assert last == Line(
            [
                SizedString(
                    "Readability counts. ",
                    [(12, -15), (19, -15)],
                    approx(399.7),
                )
            ],
            approx(9600.3),
            12.5,
            " ",
            state,
        )

    def test_existing_line_full_capacity(self):
        state = mkstate(FONT_3, 10)
        txt = Passage("Readability counts. ")
        prev = Line(
            [SizedString("better than dense. ", [], 300)], 700, 20, " ", state
        )
        gen = txt.wrap(prev)
        line = genreturn(gen)
        assert line == Line(
            [
                SizedString("better than dense. ", [], 300),
                SizedString(
                    "Readability counts. ",
                    [(12, -15), (19, -15)],
                    approx(399.7),
                ),
            ],
            approx(300.3),
            20,
            " ",
            state,
        )

    def test_across_multiple_lines(self):
        state = mkstate(FONT_3, 10)
        txt = Passage(
            "Readability counts. "
            "Special cases aren't special enough to break the rules. "
            "Although practicality beats purity. "
        )
        prev = Line(
            [SizedString("better than dense. ", [], 300)], 600, 20, " ", state
        )
        gen = txt.wrap(prev)
        gathered = _plaintext(next(gen))
        for width in cycle([400, 0.01, 600, 200]):
            try:
                gathered += _plaintext(gen.send(width))
            except StopIteration as e:
                gathered += _plaintext(e.value)
                break
        assert gathered == (
            "better than dense. Readability counts. "
            "Special cases aren't special enough to break the rules. "
            "Although practicality beats purity. "
        )

    @pytest.mark.slow
    @given(
        lists(
            sampled_from([0.01, 100, 250, 500, 10_000]),
            min_size=30,
            max_size=30,
        )
    )
    def test_no_content_is_ever_lost(self, widths):
        state = mkstate(FONT_3, 10)
        txt = Passage(
            "Readability counts. "
            "Special cases aren't special enough to break the rules. "
            "Although practicality beats purity. "
        )
        prev = Line(
            [SizedString("better than dense. ", [], 300)], 600, 20, " ", state
        )
        gen = txt.wrap(prev)
        gathered = _plaintext(next(gen))
        for width in widths:
            try:
                gathered += _plaintext(gen.send(width))
            except StopIteration as e:
                gathered += _plaintext(e.value)
                break
        else:
            pytest.fail("Text wrapping did not complete.")
        assert gathered == (
            "better than dense. Readability counts. "
            "Special cases aren't special enough to break the rules. "
            "Although practicality beats purity. "
        )


@pytest.fixture
def words() -> Sequence[Words]:
    return [
        Passage("Beautiful is   better than ugly. "),
        SetFont(FONT_3, 12),
        Passage("Explicit is better than implicit. "),
        Passage("Simple is better than complex. "),
        SetColor(RGB(0, 0.2, 0)),
        MixedWord("Com", [(SetColor(RGB(1, 0, 0)), "plex")]),
        SetColor(RGB(0, 0, 0)),
        Passage(" is better than "),
        MixedWord(
            "Com",
            [
                (SetColor(RGB(0, 0, 1)), "pli"),
                (SetFont(FONT_3, 20), "ca"),
                (
                    MultiCommand(
                        [
                            SetFont(FONT_3, 12),
                            SetColor(RGB(0, 0, 0)),
                        ]
                    ),
                    "ted. ",
                ),
            ],
        ),
        Passage("Flat is better than nested."),
    ]


class TestRewrap:
    def test_no_difference(self, words):
        state = mkstate(FONT_3, 10)
        wrapper = wrap(words, state)
        line = wrapper.send(2500)
        assert _plaintext(line) == (
            "Beautiful is   better than ugly. Explicit is better "
            "than implicit. Simple is better than complex. Complex is "
        )
        assert wrapper.throw(Redo(0)) == line
        assert _plaintext(wrapper.send(800)) == (
            "better than Complicated. Flat is "
        )

    def test_tiny_difference(self, words):
        state = mkstate(FONT_3, 10)
        wrapper = wrap(words, state)
        line = wrapper.send(2500)
        assert _plaintext(line) == (
            "Beautiful is   better than ugly. Explicit is better "
            "than implicit. Simple is better than complex. Complex is "
        )
        assert line.space > 0.02
        assert wrapper.throw(Redo(-0.01)) == replace(
            line, space=approx(line.space - 0.01)
        )
        assert wrapper.throw(Redo(-0.01)) == replace(
            line, space=approx(line.space - 0.02)
        )
        assert _plaintext(wrapper.send(800)) == (
            "better than Complicated. Flat is "
        )

    def test_within_passage_trimmable_space(self, words):
        state = mkstate(FONT_3, 10)
        wrapper = wrap(words, state)
        line = wrapper.send(2500)
        assert _plaintext(line) == (
            "Beautiful is   better than ugly. Explicit is better "
            "than implicit. Simple is better than complex. Complex is "
        )
        assert wrapper.throw(Redo(-30)) == replace(
            line, space=approx(line.space - 30)
        )
        assert wrapper.throw(Redo(-1)) == replace(
            line, space=approx(line.space - 31)
        )
        assert _plaintext(wrapper.send(850)) == (
            "better than Complicated. Flat is "
        )
        # Ensure we can do it again so long we stay within trim space
        assert _plaintext(wrapper.throw(Redo(-30))) == (
            "better than Complicated. Flat is "
        )
        assert _plaintext(wrapper.throw(Redo(-2))) == (
            "better than Complicated. Flat is "
        )

    def test_within_mixedword(self, words):
        state = mkstate(FONT_3, 10)
        wrapper = wrap(words, state)
        line = wrapper.send(2200)
        assert _plaintext(line) == (
            "Beautiful is   better than ugly. Explicit is better "
            "than implicit. Simple is better than complex. "
        )
        assert wrapper.throw(Redo(0)) == line
        assert wrapper.throw(Redo(-0.01)) == replace(
            line, space=approx(line.space - 0.01)
        )
        assert _plaintext(wrapper.send(1100)) == (
            "Complex is better than Complicated. Flat is "
        )

        # reverse back into another mixed word
        assert _plaintext(wrapper.throw(Redo(-400))) == (
            "Complex is better than "
        )
        # reverse into previous line segments
        assert _plaintext(wrapper.throw(Redo(-200))) == "Complex is better "

    def test_requires_shortening_passage_just_started(self, words):
        state = mkstate(FONT_3, 10)
        gen = wrap(words, state)
        line = gen.send(2000)
        assert _plaintext(line) == (
            "Beautiful is   better than ugly. Explicit is better "
            "than implicit. Simple is better than "
        )
        redone_line = gen.throw(Redo(-200))
        assert _plaintext(redone_line) == (
            "Beautiful is   better than ugly. Explicit is better "
            "than implicit. Simple is "
        )
        redone_line = gen.throw(Redo(-130))
        assert _plaintext(redone_line) == (
            "Beautiful is   better than ugly. Explicit is better "
            "than implicit. Simple "
        )

    def test_requires_shortening_passage_in_progress(self, words):
        state = mkstate(FONT_3, 10)
        gen = wrap(words, state)
        line = gen.send(1800)
        assert _plaintext(line) == (
            "Beautiful is   better than ugly. Explicit is better "
            "than implicit. Simple is "
        )
        line = gen.send(300)
        assert _plaintext(line) == "better than "
        # small adjustment -- same result
        redone_line = gen.throw(Redo(-20))
        assert _plaintext(redone_line) == "better than "
        # larger adjustment
        redone_line = gen.throw(Redo(-50))
        assert _plaintext(redone_line) == "better "

    def test_requires_longer_width(self, words):
        state = mkstate(FONT_3, 10)
        gen = wrap(words, state)
        line = gen.send(1800)
        assert _plaintext(line) == (
            "Beautiful is   better than ugly. Explicit is better "
            "than implicit. Simple is "
        )
        line = gen.send(200)
        assert _plaintext(line) == "better "
        # small adjustment -- same result
        redone_line = gen.throw(Redo(20))
        assert _plaintext(redone_line) == "better "
        # larger adjustment
        redone_line = gen.throw(Redo(200))
        assert _plaintext(redone_line) == "better than "
        # consume further
        redone_line = gen.throw(Redo(1_200))
        assert _plaintext(redone_line) == (
            "better than complex. "
            "Complex is better than Complicated. "
            "Flat is "
        )
        # consume all
        redone_line = gen.throw(Redo(10_000))
        assert _plaintext(redone_line) == (
            "better than complex. "
            "Complex is better than Complicated. "
            "Flat is better than nested."
        )
        assert next(gen, None) is None

    def test_requires_more_than_one_segment_redo_from_segment(self, words):
        state = mkstate(FONT_3, 10)
        gen = wrap(words, state)
        line = gen.send(2000)
        assert _plaintext(line) == (
            "Beautiful is   better than ugly. Explicit is better "
            "than implicit. Simple is better than "
        )
        redone = gen.throw(Redo(-600))
        assert _plaintext(redone) == (
            "Beautiful is   better than ugly. Explicit is better than "
        )
        assert redone.state == mkstate(FONT_3, 12)
        redone = gen.throw(Redo(600))
        assert _plaintext(redone) == (
            "Beautiful is   better than ugly. Explicit is better "
            "than implicit. Simple is better than "
        )
        redone = gen.throw(Redo(-1400))
        assert _plaintext(redone) == "Beautiful is   better than "
        assert redone.state == mkstate(FONT_3, 10)
        line = gen.send(400)
        assert _plaintext(line) == "ugly. Explicit is "
        assert line.state == mkstate(FONT_3, 12)

    def test_no_recursion_issues(self, words):
        state = mkstate(FONT_3, 10)
        gen = wrap(words, state)
        gen.send(2000)
        for diff in islice(
            cycle([-500, 20, 400, 100, -20, -1500, 1500]), 2000
        ):
            gen.throw(Redo(diff))


class TestWrap:
    def test_empty(self):
        state = mkstate(FONT_3, 10)
        gen = wrap([], state)
        assert genreturn(gen, 10_000) is None

    def test_everything_fits(self, words):
        state = mkstate(FONT_3, 10)
        gen = wrap(words, state)
        line = gen.send(10_000)
        assert line.lead == 25
        assert len(line.segments) == len(words)
        assert line.space == approx(
            10_000 - sum(w.width for w in line.segments)
        )
        assert genreturn(gen, 1) is None

    def test_not_everything_fits(self, words):
        state = mkstate(FONT_3, 10)
        gen = wrap(words, state)
        line = gen.send(0.001)
        assert line == Line(
            [SizedString("Beautiful ", [], 200)],
            -199.999,
            12.5,
            " ",
            state,
        )
        line = gen.send(0.001)
        assert line == Line(
            [SizedString("is   ", [], 100)],
            -99.999,
            12.5,
            " ",
            state,
        )
        line = gen.send(17 * 2 * 10)
        assert line == Line(
            [
                SizedString("better than ugly. ", [(17, -15)], 359.85),
                words[1],
            ],
            approx(-19.85),
            12.5,
            " ",
            replace(state, size=12),
        )
        line = gen.send(1200)
        assert line == Line(
            [
                SizedString(
                    "Explicit is better than implicit. ",
                    [(5, -10), (26, -10), (29, -10), (33, -15)],
                    approx(815.46),
                ),
                SizedString(
                    "Simple is better ",
                    [(3, -10)],
                    approx(407.88),
                ),
            ],
            approx(-23.34),
            15.0,
            " ",
            replace(state, size=12),
        )
        line = gen.send(600)
        assert line == Line(
            [
                SizedString(
                    "than complex. ",
                    [(5, -15), (8, -10), (11, -20), (13, -15)],
                    approx(335.28),
                ),
                SetColor(RGB(0, 0.2, 0)),
                SizedMixedWord(
                    SizedString("Com", [(0, -15)], approx(71.82)),
                    [
                        (
                            SetColor(RGB(1, 0, 0)),
                            SizedString("plex", [(0, -10), (3, -20)], 95.64),
                        )
                    ],
                    167.46,
                    15.0,
                    replace(state, color=RGB(1, 0, 0), size=12),
                    0,
                ),
                SetColor(RGB(0, 0, 0)),
                SizedString(" is ", [], 96.0),
            ],
            approx(1.26),
            15.0,
            " ",
            replace(state, size=12),
        )
        line = gen.send(1400)
        assert line == Line(
            [
                SizedString("better than ", [], 288.0),
                SizedMixedWord(
                    SizedString("Com", [(0, -15)], approx(71.82)),
                    [
                        (
                            SetColor(RGB(0, 0, 1)),
                            SizedString("pli", [(0, -10)], 71.88),
                        ),
                        (SetFont(FONT_3, 20), SizedString("ca", [], 80.0)),
                        (
                            MultiCommand(
                                [SetFont(FONT_3, 12), SetColor(RGB(0, 0, 0))]
                            ),
                            SizedString("ted. ", [(3, -5), (4, -15)], 119.76),
                        ),
                    ],
                    343.46,
                    25.0,
                    replace(state, size=12),
                    23.82,
                ),
                SizedString(
                    "Flat is better than nested.",
                    [(20, -5), (26, -5)],
                    approx(647.88),
                ),
            ],
            approx(120.66),
            25.0,
            ".",
            replace(state, size=12),
        )
        assert genreturn(gen, 1) is None
