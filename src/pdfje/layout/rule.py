from __future__ import annotations

from dataclasses import dataclass
from typing import Iterator, final

from ..common import (
    RGB,
    XY,
    HexColor,
    Sides,
    SidesLike,
    Streamable,
    add_slots,
    black,
    setattr_frozen,
)
from ..resources import Resources
from ..style import StyleFull
from .common import Block, ColumnFill


@final
@add_slots
@dataclass(frozen=True, init=False)
class Rule(Block):
    """A :class:`Block` that draws a horizontal line as a section break.

    i.e. if the rule would coincide with a page or column break,
    it is not drawn.
    """

    color: RGB
    margin: Sides

    def __init__(
        self,
        color: RGB | HexColor = black,
        margin: SidesLike = Sides(6, 0, 6, 0),
    ) -> None:
        setattr_frozen(self, "color", RGB.parse(color))
        setattr_frozen(self, "margin", Sides.parse(margin))

    def fill(
        self, _: Resources, __: StyleFull, cs: Iterator[ColumnFill]
    ) -> Iterator[ColumnFill]:
        col = next(cs)
        top, right, bottom, left = self.margin
        if (height := top + bottom) > col.height_free:
            # There is not enough room for the rule in the current column.
            # Yield the column and start a new one.
            # Because the column already serves as a separator, we don't
            # need to draw the rule.
            yield col
        else:
            y = col.box.origin.y + col.height_free - top
            x = col.box.origin.x + left
            yield col.add(
                _render_line(
                    XY(x, y),
                    XY(col.box.origin.x + col.box.width - right, y),
                    self.color,
                ),
                height,
            )


def _render_line(start: XY, end: XY, color: RGB) -> Streamable:
    yield b"%g %g m %g %g l %g %g %g RG S\n" % (*start, *end, *color)
