from __future__ import annotations

import abc
import os
from dataclasses import dataclass, replace
from itertools import chain, count, islice, repeat
from operator import methodcaller
from pathlib import Path
from typing import (
    IO,
    Generator,
    Iterable,
    Iterator,
    Literal,
    Sequence,
    overload,
)

from . import atoms, fonts, ops, typeset
from .atoms import OBJ_ID_PAGETREE, OBJ_ID_RESOURCES
from .common import (
    XY,
    Pt,
    add_slots,
    flatten,
    inch,
    setattr_frozen,
    skips_to_first_yield,
)
from .draw import Drawing
from .fonts import (
    Typeface,
    courier,
    helvetica,
    symbol,
    times_roman,
    zapf_dingbats,
)
from .style import Style

__all__ = [
    "AutoPage",
    "Document",
    "Page",
    "Rotation",
    "Rule",
    "Paragraph",
    "Typeface",
    "courier",
    "helvetica",
    "symbol",
    "times_roman",
    "zapf_dingbats",
]

_OBJ_ID_FIRST_PAGE: atoms.ObjectID = OBJ_ID_RESOURCES + 1
_OBJS_PER_PAGE = 2
_A4_SIZE = (A4_WIDTH, A4_HEIGHT) = (Pt(595), Pt(842))
_DEFAULT_FRAME = typeset.Frame(
    XY(inch(1), inch(1)), A4_WIDTH - inch(2), A4_HEIGHT - inch(2)
)

Rotation = Literal[0, 90, 180, 270]


class Block(abc.ABC):
    __slots__ = ()

    @property
    @abc.abstractmethod
    def style(self) -> Style:
        ...

    @abc.abstractmethod
    @skips_to_first_yield
    def typeset(
        self,
        fr: fonts.Registry,
    ) -> Generator[
        ops.Object, typeset.Frame, tuple[ops.Object, typeset.Frame]
    ]:
        ...


@add_slots
@dataclass(frozen=True)
class Paragraph(Block):
    """A paragraph"""

    content: str
    style: Style = Style()

    @skips_to_first_yield
    def typeset(
        self,
        fr: fonts.Registry,
    ) -> Generator[
        ops.Object, typeset.Frame, tuple[ops.Object, typeset.Frame]
    ]:
        frame = yield  # type: ignore[misc]
        content = []
        state = self.style.as_state(fr)
        for section in self.content.splitlines():
            gen = typeset.to_graphics(
                typeset.SpanIterator(
                    typeset.to_words(
                        [typeset.Span(ops.NOTHING, section)], state
                    ),
                    state,
                ),
            )
            while True:
                try:
                    content.append(gen.send(frame))
                except StopIteration as e:
                    graphic, frame = e.value
                    content.append(graphic)
                    break
                else:
                    frame = yield ops.MultiCommand(content)
                    content = []
        return ops.MultiCommand(content), frame


@add_slots
@dataclass(frozen=True)
class Rule(Block):
    """A horizontal line"""

    style: Style = Style()

    @skips_to_first_yield
    def typeset(
        self, _: fonts.Registry, /
    ) -> Generator[ops.Object, typeset.Frame, tuple[ops.Line, typeset.Frame]]:
        frame = yield  # type: ignore[misc]
        height = self.style.leading()
        if frame.height < height:
            frame = yield ops.NOTHING

        # TODO: how to determine height
        y = frame.bottomleft.y + frame.height - 0.75 * height
        return (
            ops.Line(
                XY(frame.bottomleft.x, y),
                XY(frame.bottomleft.x + frame.width, y),
            )
        ), replace(frame, height=frame.height - height)


@add_slots
@dataclass(frozen=True)
class TypesetPage:
    rotate: Rotation
    stream: Iterable[bytes]

    def to_atoms(self, i: atoms.ObjectID) -> Iterable[atoms.Object]:
        yield i, atoms.Dictionary(
            (b"Type", atoms.Name(b"Page")),
            (b"Parent", atoms.Ref(OBJ_ID_PAGETREE)),
            (b"Contents", atoms.Ref(i + 1)),
            (b"Resources", atoms.Ref(OBJ_ID_RESOURCES)),
            (b"Rotate", atoms.Int(self.rotate)),
        )
        yield i + 1, atoms.Stream(self.stream)


@add_slots
@dataclass(frozen=True)
class Page:
    """a page within a PDF document."""

    content: Iterable[Drawing] = ()
    rotate: Rotation = 0
    frame: typeset.Frame = _DEFAULT_FRAME

    def typeset(self, f: fonts.Registry, /) -> Iterator[TypesetPage]:
        yield TypesetPage(
            self.rotate,
            flatten(map(methodcaller("into_stream", f), self.content)),
        )

    def typeset_with(
        self,
        f: fonts.Registry,
        extra: Iterable[ops.Object],
    ) -> TypesetPage:
        return TypesetPage(
            self.rotate,
            chain(
                flatten(map(methodcaller("into_stream", f), self.content)),
                flatten(map(methodcaller("into_stream"), extra)),
            ),
        )


@add_slots
@dataclass(frozen=True, init=False)
class AutoPage:
    content: Iterable[Block]
    template: Iterable[Page]

    def __init__(
        self,
        content: str | Block | Iterable[Block],
        template: Page | Iterable[Page] = repeat(Page()),
    ) -> None:
        if isinstance(content, str):
            content = [Paragraph(content)]
        elif isinstance(content, Block):
            content = [content]
        setattr_frozen(self, "content", content)

        if isinstance(template, Page):
            template = repeat(template)
        setattr_frozen(self, "template", template)

    def typeset(self, fr: fonts.Registry, /) -> Iterator[TypesetPage]:
        nextpage = iter(self.template).__next__
        page = nextpage()
        frame = page.frame
        content: list[ops.Object] = []

        for block in self.content:
            gen = block.typeset(fr)
            while True:
                try:
                    content.append(gen.send(frame))
                except StopIteration as e:
                    graphic, frame = e.value
                    content.append(graphic)
                    break
                else:
                    yield page.typeset_with(fr, content)
                    content = []
                    page = nextpage()
                    frame = page.frame

        yield page.typeset_with(fr, content)


@add_slots
@dataclass(frozen=True, init=False)
class Document:
    """a PDF Document according to PDF spec 1.7 (32000-1:2008).

    There are several ways to construct a document:

    >>> Document()  # the minimal PDF -- one empty page
    >>> Document("hello world")  # Document with given text
    >>> Document([  # document with explicit pages
    ...     Page(),
    ...     Page(),
    ... ])

    .. note::

       A document must contain at least one page to be valid
    """

    pages: tuple[Page | AutoPage, ...]

    def __init__(
        self, pages: Sequence[Page | AutoPage] | str | None = None
    ) -> None:
        if pages is None:
            pages = [Page()]
        elif isinstance(pages, str):
            pages = [AutoPage([Paragraph(pages)])]
        else:  # i.e. a sequence of pages
            assert pages, "at least one page required"

        setattr_frozen(self, "pages", pages)

    @overload
    def write(self) -> Iterator[bytes]:
        ...

    @overload
    def write(self, target: os.PathLike | str | IO[bytes]) -> None:
        ...

    def write(  # type: ignore[return]
        self, target: os.PathLike | str | IO[bytes] | None = None
    ) -> Iterator[bytes] | None:
        """Write the document to a given target. If no target is given,
        outputs the binary PDF content iteratively.

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
        return atoms.write(_doc_objects(self.pages))

    def _write_to_path(self, p: Path) -> None:
        with p.open("wb") as wfile:
            wfile.writelines(self.write())


def _doc_objects(
    items: Iterable[Page | AutoPage],
) -> Iterator[atoms.Object]:
    fonts_ = fonts.Registry()
    for id_, page in zip(
        count(_OBJ_ID_FIRST_PAGE, step=_OBJS_PER_PAGE),
        flatten(map(methodcaller("typeset", fonts_), items)),
    ):
        yield from page.to_atoms(id_)

    try:
        first_font_id = id_ + _OBJS_PER_PAGE
    except UnboundLocalError:  # i.e. `id_` was not set by the for-loop
        raise RuntimeError(
            "Cannot write PDF document without at least one page"
        )

    yield from fonts_.to_objects(first_font_id)
    yield from _write_headers(
        (id_ - _OBJ_ID_FIRST_PAGE) // _OBJS_PER_PAGE + 1,
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
            (
                b"MediaBox",
                atoms.Array(map(atoms.Real, (0, 0, *_A4_SIZE))),
            ),
        ),
    )
    yield OBJ_ID_RESOURCES, atoms.Dictionary((b"Font", fonts_))
