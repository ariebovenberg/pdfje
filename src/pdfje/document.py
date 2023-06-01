from __future__ import annotations

import os
from dataclasses import dataclass
from itertools import count, islice
from pathlib import Path
from typing import IO, Iterable, Iterator, final, overload

from . import atoms
from .atoms import OBJ_ID_PAGETREE, OBJ_ID_RESOURCES
from .common import add_slots, flatten, setattr_frozen
from .layout import Block, Paragraph
from .layout.pages import AutoPage
from .page import Page
from .resources import Resources
from .style import Style, StyleFull, StyleLike

_OBJ_ID_FIRST_PAGE: atoms.ObjectID = OBJ_ID_RESOURCES + 1
_OBJS_PER_PAGE = 2


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
    res = Resources()
    obj_id = pagenum = 0
    # FUTURE: the scoping of `pagenum` is a bit tricky here. Find a better
    #         way to do this -- or add a specific test.
    for pagenum, obj_id, page in zip(
        count(1),
        count(_OBJ_ID_FIRST_PAGE, step=_OBJS_PER_PAGE),
        flatten(p.render(res, style, pagenum + 1) for p in items),
    ):
        yield from page.to_atoms(obj_id)

    if not pagenum:
        raise RuntimeError(
            "Cannot write PDF document without at least one page"
        )
    first_font_id = obj_id + _OBJS_PER_PAGE

    yield from res.to_objects(first_font_id)
    yield from _write_headers(
        (obj_id - _OBJ_ID_FIRST_PAGE) // _OBJS_PER_PAGE + 1,
        res.to_atoms(first_font_id),
    )


_CATALOG_OBJ = (
    atoms.OBJ_ID_CATALOG,
    atoms.Dictionary(
        (b"Type", atoms.Name(b"Catalog")),
        (b"Pages", atoms.Ref(OBJ_ID_PAGETREE)),
    ),
)


def _write_headers(
    num_pages: int, resources: atoms.Dictionary
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
    yield OBJ_ID_RESOURCES, resources
