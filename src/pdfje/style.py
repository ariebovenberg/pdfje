from __future__ import annotations

from dataclasses import dataclass

from pdfje.ops import Command, SetFont

from . import fonts
from .common import RGB, Pt, add_slots


@add_slots
@dataclass(frozen=True)
class Style:
    font: fonts.Typeface = fonts.helvetica
    size: Pt = 12
    bold: bool = False  # TODO: actually implement
    color: RGB = (0, 0, 0)

    def as_command(self, fr: fonts.Registry) -> Command:
        return SetFont(fr[self.font], self.size)
