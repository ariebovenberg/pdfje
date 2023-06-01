from __future__ import annotations

import abc
from dataclasses import dataclass
from itertools import islice, tee
from typing import Callable, Iterable, Iterator, Sequence

from ..common import XY, Streamable, add_slots, flatten, peek, prepend
from ..page import Column, Page
from ..resources import Resources
from ..style import StyleFull
from ..units import Pt

__all__ = [
    "Block",
]


class Block(abc.ABC):
    """Base class for block elements that can be laid out in a column
    by :class:`~pdfje.AutoPage`.
    """

    __slots__ = ()

    # Fill the given columns with this block's content. It may consume as many
    # columns as it needs to determine how to render itself. It should only
    # yield columns that are actually filled -- which may be fewer than it
    # consumed (e.g. if it needed to look ahead).
    #
    # Why not a generator? Because a block may need to consume multiple
    # columns to render itself, before starting to yield completed columns
    @abc.abstractmethod
    def fill(
        self, res: Resources, style: StyleFull, cs: Iterator[ColumnFill], /
    ) -> Iterator[ColumnFill]:
        ...


@add_slots
@dataclass(frozen=True)
class ColumnFill(Streamable):
    box: Column
    blocks: Sequence[Iterable[bytes]]
    height_free: Pt

    @staticmethod
    def new(col: Column) -> ColumnFill:
        return ColumnFill(col, [], col.height)

    def add(self, e: Iterable[bytes], height: Pt) -> ColumnFill:
        return ColumnFill(
            self.box, (*self.blocks, e), self.height_free - height
        )

    def cursor(self) -> XY:
        return self.box.origin.add_y(self.height_free)

    def __iter__(self) -> Iterator[bytes]:
        yield from flatten(self.blocks)


_ColumnFiller = Callable[[Iterator[ColumnFill]], Iterator[ColumnFill]]


@dataclass(frozen=True)
class PageFill:
    base: Page
    todo: Sequence[ColumnFill]  # in order they will be filled
    done: Sequence[ColumnFill]  # most recently filled last

    def reopen_most_recent_column(self) -> PageFill:
        return PageFill(self.base, (self.done[-1], *self.todo), self.done[:-1])

    @staticmethod
    def new(page: Page) -> PageFill:
        return PageFill(page, list(map(ColumnFill.new, page.columns)), ())


def fill_pages(
    doc: Iterator[PageFill], f: _ColumnFiller
) -> tuple[Iterator[PageFill], Sequence[PageFill]]:
    trunk, branch = tee(doc)
    return _fill_into(  # pragma: no branch
        f(flatten(p.todo for p in branch)), trunk
    )


def _fill_into(
    filled: Iterator[ColumnFill], doc: Iterator[PageFill]
) -> tuple[Iterator[PageFill], Sequence[PageFill]]:
    try:
        _, filled = peek(filled)
    except StopIteration:
        return doc, []  # no content to add

    completed: list[PageFill] = []
    for page in doc:  # pragma: no branch
        page_cols = list(islice(filled, len(page.todo)))
        completed.append(
            PageFill(
                page.base,
                page.todo[len(page_cols) :],  # noqa
                (*page.done, *page_cols),
            )
        )
        try:
            _, filled = peek(filled)
        except StopIteration:
            break  # no more content -- wrap things up

    return prepend(completed.pop().reopen_most_recent_column(), doc), completed
