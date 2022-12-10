from __future__ import annotations

import abc
from dataclasses import dataclass
from typing import Collection, Iterable, Sequence

from . import atoms, fonts
from .common import XY, Pt, add_slots, setattr_frozen
from .style import Style


class Drawing(abc.ABC):
    __slots__ = ()

    @abc.abstractmethod
    def into_stream(self, f: fonts.Registry, /) -> Iterable[bytes]:
        ...

    def combine(self, other: Drawing) -> Drawing:
        return Compound((self, other))


@add_slots
@dataclass(frozen=True)
class _Nothing(Drawing):
    style: Style = Style.DEFAULT

    def into_stream(self, _: fonts.Registry, /) -> Iterable[bytes]:
        return ()

    def combine(self, other: Drawing) -> Drawing:
        return other

    def __bool__(self) -> bool:
        return False


NOTHING = _Nothing()


@add_slots
@dataclass(frozen=True)
class Compound(Drawing):
    items: Collection[Drawing]
    style: Style = Style.DEFAULT

    def into_stream(self, f: fonts.Registry, /) -> Iterable[bytes]:
        for i in self.items:
            yield from i.into_stream(f)

    def combine(self, other: Drawing) -> Drawing:
        return Compound((other, *self.items))


@add_slots
@dataclass(frozen=True, init=False)
class String(Drawing):
    content: str
    loc: XY
    style: Style

    def __init__(
        self,
        content: str,
        loc: XY | tuple[float, float],
        style: Style = Style.DEFAULT,
    ) -> None:
        setattr_frozen(self, "content", content)
        setattr_frozen(self, "loc", XY.parse(loc))
        setattr_frozen(self, "style", style)

    def into_stream(self, f: fonts.Registry, /) -> Iterable[bytes]:
        font = f.font(self.style.font, self.style.bold, self.style.italic)
        size = self.style.size
        leading = self.style.line_spacing * size
        yield b"BT\n%g %g Td\n/%b %g Tf\n%g TL\n%g %g %g rg\n" % (
            *self.loc.astuple(),
            font.id,
            size,
            leading,
            *self.style.color.astuple(),
        )
        for ln in self.content.splitlines():
            yield b"["
            txt = font.encode(ln)
            # TODO: use common logic
            index_prev = index = 0
            for index, space in font.kern(ln, " ", 0):
                yield from atoms.LiteralString(txt[index_prev:index]).write()
                yield b" %g " % -space
                index_prev = index

            if index != len(txt):
                yield from atoms.LiteralString(txt[index:]).write()

            yield b"] TJ\nT*\n"
        yield b"ET\n"


@add_slots
@dataclass(frozen=True, init=False)
class Line(Drawing):
    start: XY
    end: XY
    style: Style

    def __init__(
        self,
        start: XY | tuple[float, float],
        end: XY | tuple[float, float],
        style: Style = Style.DEFAULT,
    ) -> None:
        setattr_frozen(self, "start", XY.parse(start))
        setattr_frozen(self, "end", XY.parse(end))
        setattr_frozen(self, "style", style)

    def into_stream(self, _: fonts.Registry, /) -> Iterable[bytes]:
        yield b"%g %g m %g %g l S\n" % (
            *self.start.astuple(),
            *self.end.astuple(),
        )


@add_slots
@dataclass(frozen=True, init=False)
class Box(Drawing):
    origin: XY
    width: Pt
    height: Pt
    style: Style = Style.DEFAULT

    def __init__(
        self,
        origin: XY | tuple[float, float],
        width: Pt,
        height: Pt,
        style: Style = Style.DEFAULT,
    ) -> None:
        setattr_frozen(self, "origin", XY.parse(origin))
        setattr_frozen(self, "width", width)
        setattr_frozen(self, "height", height)
        setattr_frozen(self, "style", style)

    def into_stream(self, _: fonts.Registry, /) -> Iterable[bytes]:
        yield b"%g %g %g %g re S\n" % (
            *self.origin,
            self.width,
            self.height,
        )


@add_slots
@dataclass(frozen=True)
class Polyline(Drawing):
    points: Iterable[XY | tuple[float, float]]
    closed: bool = False
    style: Style = Style.DEFAULT

    def into_stream(self, _: fonts.Registry, /) -> Iterable[bytes]:
        it = iter(self.points)
        try:
            yield b"%g %g m " % next(it)
        except StopIteration:
            return
        yield from map(b"%g %g l ".__mod__, it)
        if self.closed:
            yield b"h "
        yield b"S\n"
