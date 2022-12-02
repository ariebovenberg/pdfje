from __future__ import annotations

from dataclasses import dataclass
from itertools import chain
from pathlib import Path
from typing import (
    IO,
    Generator,
    Iterable,
    Iterator,
    Literal,
    Mapping,
    NamedTuple,
    Sequence,
    overload,
)

from . import atoms, fonts
from .common import Pt, add_slots, flatten, inch
from .fonts import Font

__all__ = ["Document", "Page", "Text", "Font"]

OBJ_ID_PAGETREE = 2
OBJ_ID_RESOURCES = 3
OBJ_ID_FIRST_PAGE = 4
A4_SIZE = (A4_WIDTH, A4_HEIGHT) = (Pt(595), Pt(842))
Rotation = Literal[0, 90, 180, 270]
DEFAULT_MARGIN = inch(1)
LEADING_PER_FONTSIZE = 1.4  # ratio of leading space to font size

_PageIndex = int  # zero-indexed page number
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
@dataclass(frozen=True)
class Text:
    """text positioned on a page"""

    content: str
    font: Font = helvetica
    size: float = 12

    def render(
        self, font: fonts.IncludedFont, y: Pt
    ) -> Generator[bytes, None, Pt]:
        leading = LEADING_PER_FONTSIZE * self.size
        yield b"BT\n/%b %g Tf\n%g %g Td\n%g TL\n" % (
            font.id,
            self.size,
            DEFAULT_MARGIN,
            y,
            leading,
        )
        lines = self.content.splitlines()
        for ln in lines:
            yield from atoms.LiteralString(font.encode(ln)).write()
            yield b" '\n"
        yield b"ET\n"

        return len(lines) * leading


@add_slots
@dataclass(frozen=True, init=False)
class Page:
    """a page within a PDF document."""

    content: Iterable[Text]
    rotate: Rotation

    def __init__(
        self, content: str | Iterable[str | Text] = (), rotate: Rotation = 0
    ) -> None:
        if isinstance(content, str):
            content = (Text(content),)
        else:
            content = [Text(s) if isinstance(s, str) else s for s in content]
        object.__setattr__(self, "content", content)
        object.__setattr__(self, "rotate", rotate)

    def to_atoms(
        self, i: _PageIndex, fm: _FontMap
    ) -> Iterable[atoms.ObjectWithID]:
        yield i, self._raw_metadata(i + 1)
        yield i + 1, atoms.Stream(b"".join(self._raw_content(fm)))

    def _raw_metadata(self, content: atoms.ObjectID) -> atoms.Dictionary:
        return atoms.Dictionary(
            (b"Type", atoms.Name(b"Page")),
            (b"Parent", atoms.Ref(OBJ_ID_PAGETREE)),
            (b"Contents", atoms.Ref(content)),
            (b"Resources", atoms.Ref(OBJ_ID_RESOURCES)),
            (b"Rotate", atoms.Int(self.rotate)),
        )

    def _raw_content(self, fm: _FontMap) -> Iterator[bytes]:
        y = A4_HEIGHT - DEFAULT_MARGIN
        for txt in self.content:
            y -= yield from txt.render(fm[txt.font], y)


def _id_for_page(i: _PageIndex) -> atoms.ObjectID:
    # We represent pages with two objects:
    # the metadata and the content.
    # Therefore, object ID is enumerated twice as fast as page number.
    return (i * 2) + OBJ_ID_FIRST_PAGE


@add_slots
@dataclass(frozen=True, init=False)
class Document:
    """a PDF Document according to PDF spec 1.7 (32000-1:2008).

    There are several ways to construct a document:

    >>> Document()  # the minimal PDF -- one empty page
    >>> Document("hello world")  # one-page document with given text
    >>> Document([  # document with explicit pages
    ...     Page(),
    ...     Page(),
    ... ])

    .. note::

       A document must contain at least one page to be valid
    """

    pages: Sequence[Page]

    def __init__(self, content: Sequence[Page] | str | None = None) -> None:
        if content is None:
            pages: Sequence[Page] = (Page(),)
        elif isinstance(content, str):
            pages = (Page([Text(content)]),)
        else:  # sequence of pages
            assert content, "at least one page required"
            pages = content

        object.__setattr__(self, "pages", pages)

    @overload
    def write(self) -> Iterator[bytes]:
        ...

    @overload
    def write(self, target: Path | str | IO[bytes]) -> None:
        ...

    def write(  # type: ignore[return]
        self, target: Path | str | IO[bytes] | None = None
    ) -> Iterator[bytes] | None:
        """Write the document to a given target. If no target is given,
        outputs the binary PDF content iteratively.

        String or :class:`~pathlib.Path` target:

        >>> doc.write("myfolder/foo.pdf")
        >>> doc.write(Path.home() / "documents/foo.pdf")

        Files and file-like objects:

        >>> with open("my/file.pdf", 'wb') as f:
        ...     doc.write(f)
        >>> doc.write(b:= BytesIO())

        Iterator output is useful for streaming PDF contents. Below is
        an example of an HTTP request using the ``httpx`` library.

        >>> httpx.post("https://mysite.foo/upload", content=doc.write(),
        ...            headers={"Content-Type": "application/pdf"})
        """
        if target is None:
            return self._write_iter()
        elif isinstance(target, str):
            self._write_to_path(Path(target))
        elif isinstance(target, Path):
            self._write_to_path(target)
        else:  # i.e. IO[bytes]
            target.writelines(self._write_iter())

    def _write_iter(self) -> Iterator[bytes]:
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

    def _write_to_path(self, p: Path) -> None:
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
                atoms.Array(map(atoms.Real, (0, 0, *A4_SIZE))),
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
