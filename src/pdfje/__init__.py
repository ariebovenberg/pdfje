import os
from dataclasses import dataclass
from itertools import chain
from pathlib import Path
from typing import Iterable, Iterator, Sequence

from . import raw

__all__ = ["Document", "Page", "Text"]

OBJ_ID_PAGETREE = 2
OBJ_ID_RESOURCES = 3
OBJ_ID_FIRST_PAGE = 4
A4_SIZE_IN_PT = (595, 842)
DEFAULT_FONT_NAME = "F1"
DEFAULT_FONT_SIZE = 14
MAX_STRING_LENGTH = 65535

PageIndex = int
"""Zero-indexed page number"""


@dataclass(frozen=True)
class Point:
    x: float
    y: float

    def __iter__(self) -> Iterator[float]:
        yield self.x
        yield self.y


@dataclass(frozen=True, init=False)
class Text:
    content: str
    at: Point

    def __init__(self, content: str, at: Point | tuple[float, float]):
        object.__setattr__(self, "content", content)
        object.__setattr__(self, "at", Point(*at))

    def __post_init__(self) -> None:
        try:
            self.content.encode("ascii")
        except UnicodeEncodeError:
            raise NotImplementedError("only ASCII for now")

        assert len(self.content) < MAX_STRING_LENGTH, "text too long!"

    def to_stream(self) -> bytes:
        return f"""\
  BT
    /{DEFAULT_FONT_NAME} {DEFAULT_FONT_SIZE} Tf
    {self.at.x} {self.at.y} Td
    ({self.content}) Tj
  ET
""".encode(
            "ascii"
        )


@dataclass(frozen=True)
class Page:
    content: Sequence[Text] = ()

    def raw_objects(
        self, index: PageIndex
    ) -> Iterable[tuple[raw.ObjectID, raw.Object]]:
        return [
            (index, self.raw_metadata(index + 1)),
            (index + 1, self.raw_content()),
        ]

    def raw_metadata(self, content: raw.ObjectID, /) -> raw.Dictionary:
        return raw.Dictionary(
            {
                "Type": raw.Name("Page"),
                "Parent": raw.Ref(OBJ_ID_PAGETREE),
                "Contents": raw.Ref(content),
                "Resources": raw.Ref(OBJ_ID_RESOURCES),
            },
        )

    def raw_content(self) -> raw.Stream:
        content = b"\n".join(item.to_stream() for item in self.content)
        return raw.Stream({"Length": raw.Int(len(content) - 1)}, content)


def id_for_page(i: PageIndex) -> raw.ObjectID:
    # For now, we represent pages with two objects:
    # the metadata and the content.
    # Therefore, object ID is enumerated twice as fast as page number.
    return (i * 2) + OBJ_ID_FIRST_PAGE


@dataclass(frozen=True)
class Document:
    pages: Sequence[Page]

    def __post_init__(self) -> None:
        assert self.pages, "at least one page required"

    def to_path(self, p: os.PathLike, /) -> None:
        page_ids = range(OBJ_ID_FIRST_PAGE, id_for_page(len(self.pages)), 2)
        headers: list[tuple[raw.ObjectID, raw.Object]] = [
            (
                raw.OBJ_ID_CATALOG,
                raw.Dictionary(
                    {
                        "Type": raw.Name("Catalog"),
                        "Pages": raw.Ref(OBJ_ID_PAGETREE),
                    }
                ),
            ),
            (
                OBJ_ID_PAGETREE,
                raw.Dictionary(
                    {
                        "Type": raw.Name("Pages"),
                        "Kids": raw.Array(
                            tuple(
                                map(
                                    raw.Ref,
                                    page_ids,
                                )
                            )
                        ),
                        "Count": raw.Int(len(self.pages)),
                        "MediaBox": raw.Array(
                            tuple(map(raw.Int, [0, 0, *A4_SIZE_IN_PT]))
                        ),
                    }
                ),
            ),
            (
                OBJ_ID_RESOURCES,
                raw.Dictionary(
                    {
                        "Font": raw.Dictionary(
                            {
                                DEFAULT_FONT_NAME: raw.Dictionary(
                                    {
                                        "Type": raw.Name("Font"),
                                        "Subtype": raw.Name("Type1"),
                                        "BaseFont": raw.Name("Times-Roman"),
                                    }
                                ),
                            }
                        ),
                    }
                ),
            ),
        ]
        Path(p).write_bytes(
            raw.write(
                chain(
                    headers,
                    chain.from_iterable(
                        page.raw_objects(i)
                        for i, page in zip(page_ids, self.pages)
                    ),
                )
            )
        )
