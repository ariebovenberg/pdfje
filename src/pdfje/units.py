from functools import partial
from operator import mul
from typing import Callable

from .common import XY, Pt

__all__ = [
    "inch",
    "cm",
    "mm",
    "pc",
    "pt",
]

inch: Callable[[float], Pt] = partial(mul, 72)
inch.__doc__ = "Convert inches to points"
cm: Callable[[float], Pt] = partial(mul, 28.346456692913385)
cm.__doc__ = "Convert centimeters to points"
mm: Callable[[float], Pt] = partial(mul, 2.8346456692913385)
mm.__doc__ = "Convert millimeters to points"
pc: Callable[[float], Pt] = partial(mul, 12)
pc.__doc__ = "Convert picas to points"


def pt(x: float) -> Pt:
    "No-op conversion. Can be used to make units explicit."
    return x


A0 = XY(2380, 3368)
"A0 paper size"
A1 = XY(1684, 2380)
"A1 paper size"
A2 = XY(1190, 1684)
"A2 paper size"
A3 = XY(842, 1190)
"A3 paper size"
A4 = XY(595, 842)
"A4 paper size"
A5 = XY(420, 595)
"A5 paper size"
A6 = XY(297, 420)
"A6 paper size"
letter = XY(612, 792)
"Letter paper size"
legal = XY(612, 1008)
"Legal paper size"
tabloid = XY(792, 1224)
"Tabloid paper size"
ledger = tabloid.flip()
"Ledger paper size, same as tabloid landscape"
