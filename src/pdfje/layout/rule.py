from __future__ import annotations

from dataclasses import dataclass
from typing import Iterator, final

from ..common import (
    RGB,
    XY,
    HexColor,
    Pt,
    Sides,
    SidesLike,
    Streamable,
    add_slots,
    black,
    setattr_frozen,
)
from ..resources import Resources
from ..style import StyleFull
from .common import Block, ColumnFill, Shaped


@final
@add_slots
@dataclass(frozen=True, init=False)
class Rule(Block):
    """A :class:`Block` that draws a horizontal line"""

    color: RGB
    margin: Sides

    def __init__(
        self,
        color: RGB | HexColor = black,
        margin: SidesLike = Sides(6, 0, 6, 0),
    ) -> None:
        setattr_frozen(self, "color", RGB.parse(color))
        setattr_frozen(self, "margin", Sides.parse(margin))

    def into_columns(
        self, _: Resources, __: StyleFull, cs: Iterator[ColumnFill]
    ) -> Iterator[ColumnFill]:
        col = next(cs)
        top, right, bottom, left = self.margin
        if (height := top + bottom) > col.height_free:
            # There is not enough room for the rule in the current column.
            # Yield the column and start a new one.
            yield col
        y = col.box.origin.y + col.height_free - top
        x = col.box.origin.x + left
        yield col.add(
            ShapedRule(
                XY(x, y),
                XY(col.box.origin.x + col.box.width - right, y),
                self.color,
                height,
            ),
        )


@add_slots
@dataclass(frozen=True)
class ShapedRule(Shaped):
    start: XY
    end: XY
    color: RGB
    height: Pt

    def render(self, _: XY, __: Pt) -> Streamable:
        yield b"%g %g m %g %g l %g %g %g RG S\n" % (
            *self.start,
            *self.end,
            *self.color,
        )
