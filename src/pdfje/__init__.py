from __future__ import annotations

import os
from dataclasses import dataclass
from itertools import chain
from pathlib import Path
from typing import Iterable, Iterator, Literal, Mapping, NamedTuple, Sequence

from . import atoms, fonts
from .common import add_slots, flatten
from .fonts import Font

__all__ = ["Document", "Page", "Text", "Font"]

OBJ_ID_PAGETREE = 2
OBJ_ID_RESOURCES = 3
OBJ_ID_FIRST_PAGE = 4
A4_SIZE_IN_PT = (595, 842)
Rotation = Literal[0, 90, 180, 270]


_PageIndex = int  # zero-indexed page number
_PositiveInt = int
_FontMap = Mapping[Font, fonts.IncludedFont]

helvetica = fonts.Builtin(b"Helvetica")
times_roman = fonts.Builtin(b"Times-Roman")
courier = fonts.Builtin(b"Courier")
symbol = fonts.Builtin(b"Symbol")
zapf_dingbats = fonts.Builtin(b"ZapfDingbats")


class Point(NamedTuple):
    x: float
    y: float


@add_slots
@dataclass(frozen=True, init=False)
class Text:
    """text positioned on a page"""

    content: str
    at: Point
    font: Font
    size: _PositiveInt

    def __init__(
        self,
        content: str,
        at: Point | tuple[float, float] = Point(0, 0),
        font: Font = helvetica,
        size: _PositiveInt = 12,
    ):
        object.__setattr__(self, "content", content)
        object.__setattr__(self, "at", Point(*at))
        object.__setattr__(self, "font", font)
        object.__setattr__(self, "size", size)

    def to_stream(self, font: fonts.IncludedFont) -> bytes:
        return b"BT\n/%b %i Tf\n%i %i Td\n%b Tj\nET" % (
            font.id,
            self.size,
            self.at.x,
            self.at.y,
            b"".join(atoms.LiteralString(font.encode(self.content)).write()),
        )


@add_slots
@dataclass(frozen=True)
class Page:
    """a page within a PDF document"""

    content: Sequence[Text] = ()
    rotate: Rotation = 0

    def to_atoms(
        self, i: _PageIndex, fm: _FontMap
    ) -> Iterable[atoms.ObjectWithID]:
        yield i, self._raw_metadata(i + 1)
        yield i + 1, self._raw_content(fm)

    def _raw_metadata(self, content: atoms.ObjectID) -> atoms.Dictionary:
        return atoms.Dictionary(
            (b"Type", atoms.Name(b"Page")),
            (b"Parent", atoms.Ref(OBJ_ID_PAGETREE)),
            (b"Contents", atoms.Ref(content)),
            (b"Resources", atoms.Ref(OBJ_ID_RESOURCES)),
            (b"Rotate", atoms.Int(self.rotate)),
        )

    def _raw_content(self, fm: _FontMap) -> atoms.Stream:
        return atoms.Stream(
            b"\n".join(t.to_stream(fm[t.font]) for t in self.content)
        )


def _id_for_page(i: _PageIndex) -> atoms.ObjectID:
    # We represent pages with two objects:
    # the metadata and the content.
    # Therefore, object ID is enumerated twice as fast as page number.
    return (i * 2) + OBJ_ID_FIRST_PAGE


@add_slots
@dataclass(frozen=True)
class Document:
    """a PDF Document

    .. warning::

       A document must contain at least one page to be valid
    """

    pages: Sequence[Page] = (Page(),)

    def __post_init__(self) -> None:
        assert self.pages, "at least one page required"

    def write(self) -> Iterator[bytes]:
        page_id_limit = _id_for_page(len(self.pages))
        page_ids = range(OBJ_ID_FIRST_PAGE, page_id_limit, 2)
        fonts_used = {
            u.font: u
            for u in fonts.usage(
                ((t.content, t.font) for p in self.pages for t in p.content),
                first_id=page_id_limit,
            )
        }
        return atoms.write(
            chain(
                _write_headers(page_ids, fonts_used.values()),
                flatten(
                    page.to_atoms(i, fonts_used)
                    for i, page in zip(page_ids, self.pages)
                ),
                flatten(f.to_atoms() for f in fonts_used.values()),
            )
        )

    def to_path(self, p: os.PathLike) -> None:
        with Path(p).open("wb") as wfile:
            wfile.writelines(self.write())


_CATALOG_OBJ = (
    atoms.OBJ_ID_CATALOG,
    atoms.Dictionary(
        (b"Type", atoms.Name(b"Catalog")),
        (b"Pages", atoms.Ref(OBJ_ID_PAGETREE)),
    ),
)


def _write_headers(
    pages: Sequence[atoms.ObjectID], fs: Iterable[fonts.IncludedFont]
) -> Iterable[atoms.ObjectWithID]:
    yield _CATALOG_OBJ
    yield (
        OBJ_ID_PAGETREE,
        atoms.Dictionary(
            (b"Type", atoms.Name(b"Pages")),
            (b"Kids", atoms.Array(map(atoms.Ref, pages))),
            (b"Count", atoms.Int(len(pages))),
            (
                b"MediaBox",
                atoms.Array(map(atoms.Int, [0, 0, *A4_SIZE_IN_PT])),
            ),
        ),
    )
    yield (
        OBJ_ID_RESOURCES,
        atoms.Dictionary(
            (
                b"Font",
                atoms.Dictionary(*((u.id, u.to_resource()) for u in fs)),
            ),
        ),
    )
