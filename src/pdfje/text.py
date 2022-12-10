from __future__ import annotations

from dataclasses import dataclass
from itertools import chain
from math import inf
from typing import Generator, Iterable, Iterator, Sequence

from .common import XY, NonEmtpyIterator, add_slots, setattr_frozen
from .draw import Drawing
from .fonts.registry import Registry
from .layout import Block, Column, ColumnFill
from .ops import Chain, Command, State, StateChange
from .style import Style, StyleFull, StyleLike
from .typeset import Line, LineSet, Stretch, WrapDone, Wrapper, splitlines


class _StyledText:
    "A mixin for shared behavior of styled text classes"
    __slots__ = ()
    content: Iterable[str | Span]
    style: Style

    def flatten(
        self,
        r: Registry,
        base: StyleFull,
        todo: Iterator[StateChange] = iter(()),
    ) -> Generator[Stretch, None, Iterator[StateChange]]:
        todo = chain(todo, self.style.diff(r, base))
        newbase = base | self.style
        for item in self.content:
            if isinstance(item, str):
                yield Stretch(Chain.squash(todo), item)
            else:
                todo = yield from item.flatten(r, newbase, todo)
        return chain(todo, base.diff(r, newbase))


@add_slots
@dataclass(frozen=True, init=False)
class Paragraph(Block, _StyledText):
    """A paragraph of text. Can be used as a :class:`~pdfje.Block`.

    Parameters
    ----------
    content: str | Span | ~typing.Iterable[str | Span]
        The text to render. Can be a string, or a nested :class:`~pdfje.Span`.
    style
        The style to render the text with.
        See :ref:`tutorial<style>` for more details.
    """

    content: Iterable[str | Span]
    style: Style

    def __init__(
        self,
        content: str | Span | Iterable[str | Span],
        style: StyleLike = Style.EMPTY,
    ):
        if isinstance(content, (str, Span)):
            content = [content]
        setattr_frozen(self, "content", content)
        setattr_frozen(self, "style", Style.parse(style))

    def layout(
        self, fr: Registry, col: ColumnFill, style: StyleFull
    ) -> Generator[ColumnFill, Column, ColumnFill]:
        style |= self.style
        state = style.as_state(fr)
        for spans in splitlines(self.flatten(fr, style)):
            col, state = yield from _layout_paragraph(spans, state, col)
        return col


@add_slots
@dataclass(frozen=True, init=False)
class Span(_StyledText):
    """A piece of text with a style.

    Parameters
    ----------
    content: str | Span | ~typing.Iterable[str | Span]
        The text to render. Can be a string, or a nested :class:`~pdfje.Span`.
    style
        The style to render the text with.
        See :ref:`tutorial<style>` for more details.
    """

    content: Iterable[str | Span]
    style: Style

    def __init__(
        self,
        content: str | Span | Iterable[str | Span],
        style: StyleLike = Style.EMPTY,
    ):
        if isinstance(content, (str, Span)):
            content = [content]
        setattr_frozen(self, "content", content)
        setattr_frozen(self, "style", Style.parse(style))


@add_slots
@dataclass(frozen=True, init=False)
class Text(Drawing, _StyledText):
    """Draw lines of text at the given location (no text wrapping)."""

    loc: XY
    content: Iterable[str | Span]
    style: Style

    def __init__(
        self,
        loc: XY | tuple[float, float],
        content: str | Span | Iterable[str | Span],
        style: StyleLike = Style.EMPTY,
    ) -> None:
        if isinstance(content, (str, Span)):
            content = [content]
        setattr_frozen(self, "loc", XY.parse(loc))
        setattr_frozen(self, "content", content)
        setattr_frozen(self, "style", Style.parse(style))

    def render(self, r: Registry, s: StyleFull, /) -> Iterable[bytes]:
        state = s.as_state(r)
        loc = self.loc
        for spans in splitlines(self.flatten(r, s)):
            par, init, state = _create_textlines(spans, state)
            yield from Lines(loc, par.lines, init).into_stream()
            loc = loc.add_y(-sum(i.lead for i in par.lines))


def _layout_paragraph(
    spans: Iterable[Stretch], state: State, fill: ColumnFill
) -> Generator[ColumnFill, Column, tuple[ColumnFill, State]]:
    wrap = Wrapper.start(spans, state)
    assert isinstance(wrap, Wrapper)  # spans is non-empty
    state = wrap.state
    par, wrap = wrap.fill(fill.col.width, fill.height_free, bool(fill.blocks))
    while isinstance(wrap, Wrapper):
        col = yield fill.add(
            Lines(fill.cursor(), par.lines, state), par.height_left
        )
        state = wrap.state
        par, wrap = wrap.fill(col.width, col.height, False)
        fill = ColumnFill.new(col)
    return (
        fill.add(Lines(fill.cursor(), par.lines, state), par.height_left),
        wrap.state,
    )


def _create_textlines(
    spans: NonEmtpyIterator[Stretch], state: State
) -> tuple[LineSet, State, State]:
    init = Wrapper.start(spans, state)
    assert isinstance(init, Wrapper)  # at least one span - it's never done
    par, done = init.fill(inf, inf, True)
    assert isinstance(done, WrapDone)  # infinite space - it's always done
    return par, init.state, done.state


@add_slots
@dataclass(frozen=True)
class Lines(Command):
    origin: XY
    lines: Sequence[Line]
    init: State

    def into_stream(self) -> Iterable[bytes]:
        lead = self.init.lead
        yield b"BT\n%g %g Td\n/%b %g Tf\n%g TL\n%g %g %g rg\n" % (
            *self.origin,
            self.init.font.id,
            self.init.size,
            lead,
            *self.init.color,
        )
        for n in self.lines:
            if n.lead == lead:
                yield b"T*\n"
            else:
                lead = n.lead
                yield b"0 %g TD\n" % -n.lead
            yield from n.into_stream()
        yield b"ET\n"
