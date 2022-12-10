from __future__ import annotations

import abc
import os
from dataclasses import dataclass
from functools import partial
from itertools import chain, count, islice, repeat
from pathlib import Path as FilePath
from typing import (
    IO,
    Callable,
    Generator,
    Iterable,
    Iterator,
    Literal,
    Sequence,
    overload,
)

from . import atoms, fonts, ops
from .atoms import OBJ_ID_PAGETREE, OBJ_ID_RESOURCES
from .common import BBox, Pt, add_slots, flatten, inch
from .fonts import (
    Font,
    Typeface,
    courier,
    helvetica,
    symbol,
    times_roman,
    zapf_dingbats,
)
from .style import Style

__all__ = [
    "Document",
    "Page",
    "Text",
    "Typeface",
    "courier",
    "helvetica",
    "times_roman",
    "symbol",
    "zapf_dingbats",
]

_OBJ_ID_FIRST_PAGE: atoms.ObjectID = OBJ_ID_RESOURCES + 1
_OBJS_PER_PAGE = 2
A4_SIZE = (A4_WIDTH, A4_HEIGHT) = (Pt(595), Pt(842))
DEFAULT_MARGIN: Pt = inch(1)
LINE_SPACING = 1.4  # ratio of leading space to font size

Rotation = Literal[0, 90, 180, 270]
_PageIndex = int  # zero-indexed page number
FontName = str


class Block(abc.ABC):
    @property
    @abc.abstractmethod
    def style(self) -> Style:
        ...

    @abc.abstractmethod
    def render(
        self, font: Font, y: Pt, maxwidth: Pt
    ) -> Generator[bytes, None, Pt]:
        ...

    @abc.abstractmethod
    def typeset(
        self, box: BBox, fr: fonts.Registry
    ) -> Generator[Iterable[ops.Operation], BBox, None]:
        ...


@add_slots
@dataclass(frozen=True)
class Text(Block):
    """A paragraph"""

    content: str
    style: Style = Style()

    def typeset(
        self, limit: BBox, fr: fonts.Registry
    ) -> Generator[Iterable[ops.Operation], BBox, None]:
        for segment in self.content.splitlines() or ("",):
            state = yield from typeset.to_boxes(
                [typeset.TextSpan(self.style.as_command(fr), self.content)],
                ops.State.DEFAULT,
            )
        # linebreaker = typeset.to_lines(boxes, limit.width)
        # while True:
        #     overflow = yield from typeset.fill()
        #     if not overflow:
        #         break

        yield []
        return
        # yield next(
        # for line in typeset.to_lines(boxes, bound.width):
        #     ...

    def render(
        self,
        font: Font,
        y: Pt,
        maxwidth: Pt,
    ) -> Generator[bytes, None, Pt]:
        size = self.style.size
        leading = LINE_SPACING * size
        yield b"BT\n%g %g Td\n/%b %g Tf\n%g TL\n" % (
            DEFAULT_MARGIN,
            y,
            font.id,
            size,
            leading,
        )
        # TODO: remove
        # yield b"""
        # 1 0 .5 rg
        # /f0 20 Tf
        # [(hello) 54 (world )] TJ
        # (another) Tj
        # T*
        # (hey!!!!) Tj
        # T*
        # [2 3 (foobar is another word)] TJ
        # """
        num_lines = 0
        for ln in flatten(
            map(
                partial(
                    add_linebreaks,
                    maxwidth,
                    partial(_width, font.width, size),
                    font.width(" ") * size,
                ),
                self.content.splitlines(),
            )
        ):
            yield from atoms.LiteralString(font.encode(ln)).write()
            yield b" '\n"
            num_lines += 1
        yield b"ET\n"

        return num_lines * leading


def _width(swidth: Callable[[str], Pt], size: float, s: str) -> Pt:
    return swidth(s) * size


def add_linebreaks(
    maxwidth: Pt,
    calcwidth: Callable[[str], Pt],
    w_space: Pt,
    s: str,
) -> Iterator[str]:
    # TODO: handling of other unicode whitespace; dashes
    space_left = maxwidth
    buffer = []
    for chunk in s.split():
        w = calcwidth(chunk)
        if w < space_left:
            buffer.append(chunk)
            space_left -= w + w_space
        else:
            yield " ".join(buffer)
            buffer = [chunk]
            # TODO: handle chunks larger than margin size
            space_left = maxwidth - w

    yield " ".join(buffer)


@add_slots
@dataclass(frozen=True)
class Rule(Block):
    """A horizontal rule"""

    style: Style = Style()

    def render(
        self, font: Font, y: Pt, maxwidth: Pt
    ) -> Generator[bytes, None, Pt]:
        height = self.style.size
        yield b"%g %g m %g %g l h S\n" % (
            DEFAULT_MARGIN,
            y - height / 2,
            DEFAULT_MARGIN + maxwidth,
            y - height / 2,
        )
        return height

    def typeset(
        self, box: BBox, fr: fonts.Registry
    ) -> Generator[Iterable[ops.Operation], BBox, None]:
        yield []
        return


@add_slots
@dataclass(frozen=True, init=False)
class Page:
    """a page within a PDF document."""

    content: Iterable[Block]
    rotate: Rotation

    def __init__(
        self,
        content: str | Iterable[str | Block] = (),
        rotate: Rotation = 0,
    ) -> None:
        if isinstance(content, str):
            content = (Text(content),)
        else:
            content = [Text(s) if isinstance(s, str) else s for s in content]
        object.__setattr__(self, "content", content)
        object.__setattr__(self, "rotate", rotate)

    def to_atoms(
        self, i: _PageIndex, fr: fonts.Registry
    ) -> Iterable[atoms.Object]:
        yield i, self._raw_metadata(i + 1)
        yield i + 1, atoms.Stream(b"".join(self._raw_content(fr)))

    def _raw_metadata(self, content: atoms.ObjectID) -> atoms.Dictionary:
        return atoms.Dictionary(
            (b"Type", atoms.Name(b"Page")),
            (b"Parent", atoms.Ref(OBJ_ID_PAGETREE)),
            (b"Contents", atoms.Ref(content)),
            (b"Resources", atoms.Ref(OBJ_ID_RESOURCES)),
            (b"Rotate", atoms.Int(self.rotate)),
        )

    def _raw_content(self, fr: fonts.Registry) -> Iterator[bytes]:
        y = A4_HEIGHT - DEFAULT_MARGIN
        for txt in self.content:
            y -= yield from txt.render(
                fr[txt.style.font], y, A4_WIDTH - (DEFAULT_MARGIN * 2)
            )

    # TODO: actually typeset, not just register font use
    def typeset(self, fs: fonts.Registry) -> Iterator[Page]:
        for t in self.content:
            next(
                t.typeset(
                    BBox(
                        A4_HEIGHT - DEFAULT_MARGIN * 2,
                        A4_WIDTH - DEFAULT_MARGIN * 2,
                    ),
                    fs,
                )
            )

            if isinstance(t, Text):
                fs[t.style.font].encode(t.content)
        yield self

    def typeset_until_full(
        self, fs: fonts.Registry, items: Iterable[Block]
    ) -> Generator[Page, None, Iterable[Block]]:
        raise NotImplementedError()


@add_slots
@dataclass(frozen=True, init=False)
class AutoPage:  # pragma: no cover
    content: Iterable[Block]
    template: Iterable[Page]

    def __init__(
        self,
        content: str | Block | Iterable[Block],
        template: Page | Iterable[Page] = Page(),
    ) -> None:
        if isinstance(content, str):
            content = [Text(content)]
        elif isinstance(content, Block):
            content = [content]
        object.__setattr__(self, "content", content)

        if isinstance(template, Page):
            template = repeat(template)
        object.__setattr__(self, "template", template)

    def to_atoms(
        self, i: _PageIndex, fr: fonts.Registry
    ) -> Iterable[atoms.Object]:
        raise NotImplementedError()

    # mutates fonts, but idempotently
    def typeset(self, fs: fonts.Registry) -> Iterator[Page]:
        items_remaining = self.content
        for page in self.template:
            items_remaining = yield from page.typeset_until_full(
                fs, items_remaining
            )
            if not items_remaining:
                break
        else:
            raise RuntimeError("Page templates exhausted but content remains.")

        # in the future, return the result of automatic page breaking:
        # - number of pages
        # - location of labels for ToC


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

    pages: tuple[Page | AutoPage, ...]

    def __init__(
        self, pages: Sequence[Page | AutoPage] | str | None = None
    ) -> None:
        if pages is None:
            pages = (Page(),)
        elif isinstance(pages, str):  # pragma: no cover
            pages = (AutoPage([Text(pages)]),)
        else:  # i.e. a sequence of pages
            assert pages, "at least one page required"

        object.__setattr__(self, "pages", pages)

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
            self._write_to_path(FilePath(os.fspath(target)))
        else:  # i.e. IO[bytes]
            target.writelines(self._write_iter())

    def _write_iter(self) -> Iterator[bytes]:
        fonts_ = fonts.Registry()
        pages = list(flatten(o.typeset(fonts_) for o in self.pages))
        first_font_id = _OBJ_ID_FIRST_PAGE + len(pages) * _OBJS_PER_PAGE
        return atoms.write(
            chain(
                flatten(
                    page.to_atoms(i, fonts_)
                    for page, i in zip(
                        pages, count(_OBJ_ID_FIRST_PAGE, step=_OBJS_PER_PAGE)
                    )
                ),
                fonts_.to_objects(first_font_id),
                _write_headers(len(pages), fonts_.to_resources(first_font_id)),
            )
        )

    def _write_to_path(self, p: FilePath) -> None:
        with p.open("wb") as wfile:
            wfile.writelines(self.write())


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
                atoms.Array(map(atoms.Real, (0, 0, *A4_SIZE))),
            ),
        ),
    )
    yield OBJ_ID_RESOURCES, atoms.Dictionary((b"Font", fonts_))
