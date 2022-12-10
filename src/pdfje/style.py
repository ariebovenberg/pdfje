from __future__ import annotations

from dataclasses import dataclass, replace
from typing import ClassVar

from pdfje.ops import State

from . import fonts
from .common import RGB, Pt, add_slots, setattr_frozen

__all__ = ["Style"]


@add_slots
@dataclass(frozen=True, init=False)
class Style:
    font: fonts.Typeface
    size: Pt
    bold: bool
    italic: bool
    color: RGB
    line_spacing: float

    def __init__(
        self,
        font: fonts.Typeface = fonts.helvetica,
        size: Pt = 12,
        bold: bool = False,
        italic: bool = False,
        color: RGB | tuple[float, float, float] = RGB(0, 0, 0),
        line_spacing: float = 1.25,
    ) -> None:
        setattr_frozen(self, "font", font)
        setattr_frozen(self, "size", size)
        setattr_frozen(self, "bold", bold)
        setattr_frozen(self, "italic", italic)
        setattr_frozen(self, "line_spacing", line_spacing)
        setattr_frozen(
            self, "color", RGB(*color) if isinstance(color, tuple) else color
        )

    replace = replace
    DEFAULT: ClassVar[Style]

    def as_state(self, fr: fonts.Registry) -> State:
        return State(
            fr.font(self.font, self.bold, self.italic),
            self.size,
            self.color,
            self.line_spacing,
        )

    def leading(self) -> Pt:
        return self.size * self.line_spacing


Style.DEFAULT = Style()


# @add_slots
# @dataclass(frozen=True)
# class PartialStyle:
#     ...
