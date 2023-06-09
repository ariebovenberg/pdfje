from __future__ import annotations

import abc
from dataclasses import dataclass
from typing import Callable, Iterable, Iterator, Sequence

from pdfje.typeset.words import WordLike

from ..common import (
    XY,
    Align,
    Pt,
    Streamable,
    add_slots,
    fix_abstract_properties,
)
from ..layout.common import Shaped  # FUTURE: fix this near-circular dependency
from .state import State


@add_slots
@dataclass(frozen=True)
class ShapedText(Shaped):
    lines: Sequence[Line]
    lead: Pt
    align: Align
    height: Pt

    def render(self, pos: XY, width: Pt) -> Iterator[bytes]:
        return render_text(
            pos, self.pre_state(), width, self.lines, self.lead, self.align
        )

    def end_state(self) -> State | None:
        # this slightly convoluted way takes into account that lines
        # may (in rare cases) be empty
        return next(
            (w.state for s in reversed(self.lines) for w in reversed(s.words)),
            None,
        )

    def pre_state(self) -> State | None:
        # this slightly convoluted way takes into account that lines
        # may (in rare cases) be empty
        return next(
            (wd.state for ln in self.lines for wd in ln.words),
            None,
        )


def render_text(
    pos: XY,
    state: State | None,
    prev_width: Pt,
    lines: Iterable[Line],
    lead: Pt,
    align: Align,
) -> Iterator[bytes]:
    yield b"BT\n%g %g Td\n" % pos.astuple()
    yield from state or ()
    yield from _pick_renderer(align.value)(lines, lead, prev_width)
    yield b"ET\n"


@fix_abstract_properties
class Line(Streamable):
    __slots__ = ()

    @property
    @abc.abstractmethod
    def words(self) -> Sequence[WordLike]:
        ...

    @property
    @abc.abstractmethod
    def width(self) -> Pt:
        ...


def _render_left(lines: Iterable[Line], lead: Pt, _: Pt) -> Iterator[bytes]:
    yield b"%g TL\n" % lead
    for ln in lines:
        yield b"T*\n"
        yield from ln


def _render_centered(
    lines: Iterable[Line], lead: Pt, prev_width: Pt
) -> Iterator[bytes]:
    for ln in lines:
        yield b"%g %g TD\n" % ((prev_width - ln.width) / 2, -lead)
        yield from ln
        prev_width = ln.width


def _render_right(
    lines: Iterable[Line], lead: Pt, prev_width: Pt
) -> Iterator[bytes]:
    for ln in lines:
        yield b"%g %g TD\n" % ((prev_width - ln.width), -lead)
        yield from ln
        prev_width = ln.width


_pick_renderer: Callable[
    [int], Callable[[Iterable[Line], Pt, Pt], Iterable[bytes]]
] = [
    _render_left,
    _render_centered,
    _render_right,
    _render_left,  # justified lines are already stretched, so left-align.
].__getitem__
