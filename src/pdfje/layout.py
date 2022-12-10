from __future__ import annotations

import abc
from dataclasses import dataclass
from typing import Generator, Iterable, Sequence

from .common import XY, Pt, add_slots, flatten, setattr_frozen
from .fonts.registry import Registry
from .ops import Command, into_stream
from .style import StyleFull


@add_slots
@dataclass(frozen=True, init=False)
class Column:
    """A column to lay out block elements in.

    Parameters
    ----------
    origin
        The bottom left corner of the column. Can be parsed from a 2-tuple.
    width
        The width of the column.
    height
        The height of the column.

    """

    origin: XY
    width: Pt
    height: Pt

    def __init__(
        self, origin: XY | tuple[float, float], width: Pt, height: Pt
    ) -> None:
        setattr_frozen(self, "origin", XY.parse(origin))
        setattr_frozen(self, "width", width)
        setattr_frozen(self, "height", height)


@add_slots
@dataclass(frozen=True)
class ColumnFill:
    col: Column
    blocks: Sequence[Command]
    height_free: Pt

    @staticmethod
    def new(col: Column) -> ColumnFill:
        return ColumnFill(col, [], col.height)

    def add(self, p: Command, height_free: Pt) -> ColumnFill:
        return ColumnFill(self.col, [*self.blocks, p], height_free)

    def cursor(self) -> XY:
        return self.col.origin.add_y(self.height_free)

    def into_stream(self) -> Iterable[bytes]:
        yield from flatten(map(into_stream, self.blocks))


class Block(abc.ABC):
    """Base class for block elements that can be laid out in a column
    by :class:`~pdfje.AutoPage`.
    """

    __slots__ = ()

    @abc.abstractmethod
    def layout(
        self, fr: Registry, col: ColumnFill, style: StyleFull
    ) -> Generator[ColumnFill, Column, ColumnFill]:
        ...
