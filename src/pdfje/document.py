from __future__ import annotations

import os
from dataclasses import dataclass
from itertools import chain, count, islice
from operator import methodcaller
from pathlib import Path
from typing import (
    IO,
    Callable,
    Generator,
    Iterable,
    Iterator,
    Literal,
    Sequence,
    final,
    overload,
)

from . import atoms
from .atoms import OBJ_ID_PAGETREE, OBJ_ID_RESOURCES
from .common import (
    XY,
    Pt,
    Sides,
    SidesLike,
    add_slots,
    always,
    flatten,
    setattr_frozen,
    skips_to_first_yield,
)
from .draw import Drawing
from .fonts.registry import Registry
from .layout import Block, Column, ColumnFill, Paragraph
from .style import Style, StyleFull, StyleLike
from .units import A4, inch

_OBJ_ID_FIRST_PAGE: atoms.ObjectID = OBJ_ID_RESOURCES + 1
_OBJS_PER_PAGE = 2

Rotation = Literal[0, 90, 180, 270]


@add_slots
@dataclass(frozen=True)
class RenderedPage:
    rotate: Rotation
    size: XY
    stream: Iterable[bytes]

    def to_atoms(self, i: atoms.ObjectID) -> Iterable[atoms.Object]:
        yield i, atoms.Dictionary(
            (b"Type", atoms.Name(b"Page")),
            (b"Parent", atoms.Ref(OBJ_ID_PAGETREE)),
            (b"MediaBox", atoms.Array(map(atoms.Real, [0, 0, *self.size]))),
            (b"Contents", atoms.Ref(i + 1)),
            (b"Resources", atoms.Ref(OBJ_ID_RESOURCES)),
            (b"Rotate", atoms.Int(self.rotate)),
        )
        yield i + 1, atoms.Stream(self.stream)


@final
@add_slots
@dataclass(frozen=True, init=False)
class Page:
    """A single page within a document. Contains drawings at given positions.

    Example
    -------

    .. code-block:: python

       from pdfje import Page, Line, Rect, Text, A5
       title_page = Page([
           Text((100, 200), "My awesome story"),
           Line((100, 100), (200, 100)),
           Rect((50, 50), width=200, height=300),
       ], size=A5)

    Parameters
    ----------
    content
        The drawings to render on the page.
    size
        The size of the page in points. Common page sizes are available
        as constants:

        .. code-block:: python

            from pdfje import Page, A4, A5, A6, letter, legal, tabloid

    rotate
        The rotation of the page in degrees.
    margin
        The margin around the page in points, used for layout.
        Can be a single value, or a 2, 3 or 4-tuple following the CSS
        shorthand convention. see https://www.w3schools.com/css/css_margin.asp
    columns
        The columns to use for laying out the content.
        If not given, the content is laid out in a single column
        based on the page size and margin.

    """

    content: Iterable[Drawing]
    size: XY
    rotate: Rotation
    columns: Sequence[Column]

    def __init__(
        self,
        content: Iterable[Drawing] = (),
        size: XY | tuple[Pt, Pt] = A4,
        rotate: Rotation = 0,
        margin: SidesLike = Sides.parse(inch(1)),
        columns: Sequence[Column] = (),
    ) -> None:
        size = XY.parse(size)
        setattr_frozen(self, "content", content)
        setattr_frozen(self, "rotate", rotate)
        setattr_frozen(self, "columns", columns or [_column(size, margin)])
        setattr_frozen(self, "size", size)

    def add(self, d: Drawing, /) -> Page:
        """Create a new page with the given drawing added

        Parameters
        ----------
        d
            The drawing to add to the page
        """
        return Page(
            [*self.content, d], self.size, self.rotate, columns=self.columns
        )

    def generate(
        self, f: Registry, s: StyleFull, pnum: int, /
    ) -> Iterator[RenderedPage]:
        yield RenderedPage(
            self.rotate,
            self.size,
            flatten(map(methodcaller("render", f, s), self.content)),
        )

    def fill(
        self, f: Registry, s: StyleFull, extra: Iterable[bytes]
    ) -> RenderedPage:
        return RenderedPage(
            self.rotate,
            self.size,
            chain(
                flatten(map(methodcaller("render", f, s), self.content)),
                extra,
            ),
        )


def _column(page: XY, margin: SidesLike) -> Column:
    top, right, bottom, left = Sides.parse(margin)
    return Column(
        XY(left, bottom), page.x - left - right, page.y - top - bottom
    )


@final
@add_slots
@dataclass(frozen=True, init=False)
class AutoPage:
    """Automatically lays out content on multiple pages.

    Parameters
    ----------
    content: ~typing.Iterable[~pdfje.Block | str] | ~pdfje.Block | str
        The content to lay out on the pages. Can be parsed from single string
        or block.
    template: ~pdfje.Page | ~typing.Callable[[int], ~pdfje.Page]
        A page to use as a template for the layout. If a callable is given,
        it is called with the page number as the only argument to generate
        the page. Defaults to the default :class:`Page`.

    """

    content: Iterable[str | Block]
    template: Callable[[int], Page]

    def __init__(
        self,
        content: str | Block | Iterable[Block | str],
        template: Page | Callable[[int], Page] = always(Page()),
    ) -> None:
        if isinstance(content, str):
            content = [Paragraph(content)]
        elif isinstance(content, Block):
            content = [content]
        setattr_frozen(self, "content", content)

        if isinstance(template, Page):
            template = always(template)
        setattr_frozen(self, "template", template)

    def generate(
        self, fr: Registry, style: StyleFull, pnum: int, /
    ) -> Iterator[RenderedPage]:
        gen = self._chained_blocks_layout(fr, style)
        for page in map(self.template, count(pnum)):  # pragma: no branch
            filled_columns = []
            for col in page.columns:
                try:
                    filled_columns.append(gen.send(col))
                except StopIteration:
                    break
            else:
                yield page.fill(fr, style, flatten(filled_columns))
                continue  # there's still content, so keep on paging

            if filled_columns:
                yield page.fill(fr, style, flatten(filled_columns))
            return

    @skips_to_first_yield
    def _chained_blocks_layout(
        self, r: Registry, s: StyleFull, /
    ) -> Generator[ColumnFill, Column, None]:
        fill = ColumnFill.new((yield))  # type: ignore[misc]
        for b in self.content:
            fill = yield from _as_block(b).layout(r, fill, s)
        yield fill


def _as_block(b: str | Block) -> Block:
    if isinstance(b, str):
        return Paragraph(b)
    return b


@final
@add_slots
@dataclass(frozen=True, init=False)
class Document:
    """a PDF Document

    Parameters
    ----------

    content
        The content of the document.
    style
        Change the default style of the document.

    Examples
    --------

    Below are some examples of creating documents.

    >>> Document()  # the minimal PDF -- one empty page
    >>> Document("hello world")  # a document with pages of text
    >>> Document([  # document with explicit pages
    ...     Page(...),
    ...     AutoPage([LOREM_IPSUM, ZEN_OF_PYTHON]),
    ...     Page(),
    ... ])


    note
    ----
    A document must contain at least one page to be valid
    """

    pages: Iterable[Page | AutoPage]
    style: Style

    def __init__(
        self,
        content: Iterable[Page | AutoPage] | str | Block | None = None,
        style: StyleLike = Style.EMPTY,
    ) -> None:
        if content is None:
            content = [Page()]
        elif isinstance(content, str):
            content = [AutoPage([Paragraph(content)])]
        elif isinstance(content, Block):
            content = [AutoPage([content])]

        setattr_frozen(self, "pages", content)
        setattr_frozen(self, "style", Style.parse(style))

    @overload
    def write(self) -> Iterator[bytes]:
        ...

    @overload
    def write(self, target: os.PathLike[str] | str | IO[bytes]) -> None:
        ...

    def write(  # type: ignore[return]
        self, target: os.PathLike[str] | str | IO[bytes] | None = None
    ) -> Iterator[bytes] | None:
        """Write the document to a given target. If no target is given,
        outputs the binary PDF content iteratively. See examples below.

        Parameters
        ----------
        target: ~os.PathLike | str | ~typing.IO[bytes] | None
            The target to write to. If not given, the PDF content is returned
            as an iterator.

        Returns
        -------
        ~typing.Iterator[bytes] | None

        Examples
        --------

        String, :class:`~pathlib.Path`, or :class:`~os.PathLike` target:

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
        elif isinstance(target, (str, os.PathLike)):
            self._write_to_path(Path(os.fspath(target)))
        else:  # i.e. IO[bytes]
            target.writelines(self._write_iter())

    def _write_iter(self) -> Iterator[bytes]:
        return atoms.write(_doc_objects(self.pages, self.style.setdefault()))

    def _write_to_path(self, p: Path) -> None:
        with p.open("wb") as wfile:
            wfile.writelines(self.write())


def _doc_objects(
    items: Iterable[Page | AutoPage], style: StyleFull
) -> Iterator[atoms.Object]:
    fonts_ = Registry()
    obj_id = pagenum = 0
    for pagenum, obj_id, page in zip(
        count(1),
        count(_OBJ_ID_FIRST_PAGE, step=_OBJS_PER_PAGE),
        flatten(p.generate(fonts_, style, pagenum + 1) for p in items),
    ):
        yield from page.to_atoms(obj_id)

    if not pagenum:
        raise RuntimeError(
            "Cannot write PDF document without at least one page"
        )
    first_font_id = obj_id + _OBJS_PER_PAGE

    yield from fonts_.to_objects(first_font_id)
    yield from _write_headers(
        (obj_id - _OBJ_ID_FIRST_PAGE) // _OBJS_PER_PAGE + 1,
        fonts_.to_resources(first_font_id),
    )


_CATALOG_OBJ = (
    atoms.OBJ_ID_CATALOG,
    atoms.Dictionary(
        (b"Type", atoms.Name(b"Catalog")),
        (b"Pages", atoms.Ref(OBJ_ID_PAGETREE)),
    ),
)


def _write_headers(
    num_pages: int, fonts_: atoms.Dictionary
) -> Iterable[atoms.Object]:
    yield _CATALOG_OBJ
    yield (
        OBJ_ID_PAGETREE,
        atoms.Dictionary(
            (b"Type", atoms.Name(b"Pages")),
            (
                b"Kids",
                atoms.Array(
                    map(
                        atoms.Ref,
                        islice(
                            count(_OBJ_ID_FIRST_PAGE, step=_OBJS_PER_PAGE),
                            num_pages,
                        ),
                    )
                ),
            ),
            (b"Count", atoms.Int(num_pages)),
        ),
    )
    yield OBJ_ID_RESOURCES, atoms.Dictionary((b"Font", fonts_))
