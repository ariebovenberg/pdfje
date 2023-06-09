from __future__ import annotations

from dataclasses import dataclass
from functools import partial
from itertools import chain, count
from typing import Callable, Iterable, Iterator, final

from ..common import add_slots, always, flatten, setattr_frozen
from ..page import Page, RenderedPage
from ..resources import Resources
from ..style import StyleFull
from .common import Block, PageFill, fill_pages
from .paragraph import Paragraph


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

    def render(
        self, r: Resources, s: StyleFull, pnum: int, /
    ) -> Iterator[RenderedPage]:
        pages: Iterator[PageFill] = map(
            PageFill.new, map(self.template, count(pnum))
        )
        for block in map(_as_block, self.content):
            pages, filled = fill_pages(
                pages, partial(block.into_columns, r, s)
            )
            for p in filled:
                yield p.base.fill(r, s, flatten(p.done))

        last = next(pages)
        yield last.base.fill(r, s, flatten(chain(last.done, last.todo)))


def _as_block(b: str | Block) -> Block:
    return Paragraph(b) if isinstance(b, str) else b
