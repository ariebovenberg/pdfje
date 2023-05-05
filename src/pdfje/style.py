from __future__ import annotations

from dataclasses import dataclass, fields
from itertools import chain
from typing import (
    TYPE_CHECKING,
    ClassVar,
    Generator,
    Iterable,
    Iterator,
    TypeGuard,
    TypeVar,
    final,
)

from .common import RGB, HexColor, Pt, add_slots, setattr_frozen
from .fonts.builtins import helvetica
from .fonts.common import BuiltinTypeface, TrueType, Typeface
from .fonts.registry import Registry
from .typeset.common import (
    Chain,
    Command,
    SetColor,
    SetFont,
    SetHyphens,
    SetLineSpacing,
    State,
    Stretch,
)
from .typeset.hyphens import (
    Hyphenator,
    HyphenatorLike,
    default_hyphenator,
    parse_hyphenator,
)

__all__ = ["Style", "Span", "StyleLike"]


class _NOT_SET:
    """Sentinel value for unset style attributes."""

    __slots__ = ()

    def __repr__(self) -> str:
        return "NOT_SET"


_NOTSET = _NOT_SET()


@final
@add_slots
@dataclass(frozen=True, init=False)
class Style:
    """Settings for visual style of text. All parameters are optional.

    The default style is Helvetica (regular) size 12, with line spacing 1.25

    Parameters
    ----------
    font: ~pdfje.fonts.TrueType | ~pdfje.fonts.BuiltinTypeface
        Typeface to use.
    size: float
        Size of the font, in points.
    bold: bool
        Whether to use bold font.
    italic: bool
        Whether to use italic font.
    color: ~pdfje.RGB | str
        Color of the text; can be given as a hex string (e.g. ``#ff0000``)
    line_spacing: float
        Line spacing, as a multiplier of the font size.
    hyphens: ~pyphen.Pyphen | None | ~typing.Callable[[str], ~typing.Iterable[str]]
        Hyphenation algorithm to use. Passing an explicit ``None`` disables
        hyphenation.

    Example
    -------

    Below we can see how to create a style, and how to combine them.

    >>> from pdfje import Style, RGB, times_roman
    >>> body = Style(font=times_roman, size=14, italic=True))
    >>> heading = body | Style(size=24, bold=True, color=RGB(0.5, 0, 0))
    >>> # fonts and colors can be used directly in place of styles
    >>> emphasis = times_roman | "#ff0000"
    """  # noqa: E501

    font: Typeface | None = None
    size: Pt | None = None
    bold: bool | None = None
    italic: bool | None = None
    color: RGB | None = None
    line_spacing: float | None = None
    hyphens: Hyphenator | None = None

    def __init__(
        self,
        font: Typeface | None = None,
        size: Pt | None = None,
        bold: bool | None = None,
        italic: bool | None = None,
        color: RGB | tuple[float, float, float] | HexColor | None = None,
        line_spacing: float | None = None,
        hyphens: HyphenatorLike | _NOT_SET = _NOTSET,
    ) -> None:
        setattr_frozen(self, "font", font)
        setattr_frozen(self, "size", size)
        setattr_frozen(self, "bold", bold)
        setattr_frozen(self, "italic", italic)
        setattr_frozen(self, "line_spacing", line_spacing)
        setattr_frozen(self, "color", color and RGB.parse(color))
        setattr_frozen(
            self,
            "hyphens",
            None
            if isinstance(hyphens, _NOT_SET)
            else parse_hyphenator(hyphens),
        )

    # Use this instead of replace() to avoid triggering __init__.
    def _evolve(self, **kwargs: object) -> Style:
        attrs = {f.name: getattr(self, f.name) for f in fields(self)}
        attrs.update(kwargs)
        new = Style.__new__(Style)
        for k, v in attrs.items():
            setattr_frozen(new, k, v)
        return new

    def __or__(self, other: StyleLike, /) -> Style:
        if isinstance(other, Style):
            return self._evolve(
                font=other.font or self.font,
                size=_fallback(other.size, self.size),
                bold=_fallback(other.bold, self.bold),
                italic=_fallback(other.italic, self.italic),
                color=other.color or self.color,
                line_spacing=_fallback(other.line_spacing, self.line_spacing),
                hyphens=_fallback(other.hyphens, self.hyphens),
            )
        elif isinstance(other, (TrueType, BuiltinTypeface)):
            return self._evolve(font=other)
        elif isinstance(other, str):
            return self._evolve(color=RGB.parse(other))
        elif isinstance(other, RGB):
            return self._evolve(color=other)
        else:
            return NotImplemented  # type: ignore[unreachable]

    def __ror__(self, other: HexColor, /) -> Style:
        return Style(color=RGB.parse(other)) | self

    def __repr__(self) -> str:
        field_reprs = [
            (f.name, v)
            for f in fields(self)
            if (v := getattr(self, f.name)) is not None
        ]
        return (
            f"Style({', '.join(f'{k}={v!r}' for k, v in field_reprs)})"
            if field_reprs
            else "Style.EMPTY"
        )

    @staticmethod
    def parse(s: StyleLike) -> Style:
        if isinstance(s, Style):
            return s
        elif isinstance(s, RGB):
            return Style(color=s)
        elif isinstance(s, (TrueType, BuiltinTypeface)):
            return Style(font=s)
        elif isinstance(s, str) and s.startswith("#"):  # type: ignore
            return Style(color=RGB.parse(s))
        else:
            raise TypeError(f"Cannot parse style from {s!r}")

    def diff(self, r: Registry, base: StyleFull) -> Iterator[Command]:
        if (
            _differs(self.bold, base.bold)
            or _differs(self.italic, base.italic)
            or _differs(self.font, base.font)
            or _differs(self.size, base.size)
        ):
            yield SetFont(
                r.font(
                    self.font or base.font,
                    _fallback(self.bold, base.bold),
                    _fallback(self.italic, base.italic),
                ),
                _fallback(self.size, base.size),
            )
        if _differs(self.color, base.color):
            yield SetColor(self.color)
        if _differs(self.line_spacing, base.line_spacing):
            yield SetLineSpacing(self.line_spacing)
        if _differs(self.hyphens, base.hyphens):
            yield SetHyphens(self.hyphens)

    def setdefault(self) -> StyleFull:
        return StyleFull.DEFAULT | self

    EMPTY: ClassVar[Style]


StyleLike = Style | RGB | Typeface | HexColor
Style.EMPTY = Style()

bold = Style(bold=True)
"""Shortcut for bold style."""
italic = Style(italic=True)
"""Shortcut for italic style."""
regular = Style(bold=False, italic=False)
"""Shortcut for regular (non-bold or italic) style."""


@add_slots
@dataclass(frozen=True)
class StyleFull:
    font: Typeface
    size: Pt
    bold: bool
    italic: bool
    color: RGB
    line_spacing: float
    hyphens: Hyphenator

    def __or__(self, s: Style, /) -> StyleFull:
        return StyleFull(
            s.font or self.font,
            _fallback(s.size, self.size),
            _fallback(s.bold, self.bold),
            _fallback(s.italic, self.italic),
            s.color or self.color,
            _fallback(s.line_spacing, self.line_spacing),
            s.hyphens or self.hyphens,
        )

    def as_state(self, fr: Registry) -> State:
        return State(
            fr.font(self.font, self.bold, self.italic),
            self.size,
            self.color,
            self.line_spacing,
            self.hyphens,
        )

    def diff(self, registry: Registry, base: StyleFull) -> Iterator[Command]:
        if not (
            self.bold == base.bold
            and self.italic == base.italic
            and self.font == base.font
            and self.size == base.size
        ):
            yield SetFont(
                registry.font(self.font, self.bold, self.italic),
                self.size,
            )
        if self.color != base.color:
            yield SetColor(self.color)

        if self.line_spacing != base.line_spacing:
            yield SetLineSpacing(self.line_spacing)

        if self.hyphens != base.hyphens:
            yield SetHyphens(self.hyphens)

    DEFAULT: ClassVar[StyleFull]


StyleFull.DEFAULT = StyleFull(
    helvetica, 12, False, False, RGB(0, 0, 0), 1.25, default_hyphenator
)


_T = TypeVar("_T")


def _fallback(a: _T | None, b: _T) -> _T:
    return b if a is None else a


def _differs(a: _T | None, b: _T) -> TypeGuard[_T]:
    return a is not None and a != b


class StyledMixin:
    "A mixin for shared behavior of styled text classes"
    __slots__ = ()
    content: Iterable[str | Span]
    style: Style

    def flatten(
        self,
        r: Registry,
        base: StyleFull,
        todo: Iterator[Command] = iter(()),
    ) -> Generator[Stretch, None, Iterator[Command]]:
        todo = chain(todo, self.style.diff(r, base))
        newbase = base | self.style
        for item in self.content:
            if isinstance(item, str):
                yield Stretch(Chain.squash(todo), item)
            else:
                todo = yield from item.flatten(r, newbase, todo)
        return chain(todo, base.diff(r, newbase))


@final
@add_slots
@dataclass(frozen=True, init=False)
class Span(StyledMixin):
    """A fragment of text with a style.

    Parameters
    ----------
    content: str | Span | ~typing.Iterable[str | Span]
        The text to render. Can be a string, or a nested :class:`~pdfje.Span`.
    style
        The style to render the text with.
        See :ref:`tutorial<style>` for more details.

    Examples
    --------

    .. code-block:: python

        from pdfje.style import Span, Style, bold
        from pdfje.fonts import times_roman

        # A simple span
        Span("Hello, world!", Style(size=24, color="#ff0000"))
        # A nested span
        Span([
            "Beautiful is ",
            Span("better", helvetica | bold),
            " than ugly.",
        ], style=times_roman)
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


# The implementation of these operators are patched onto existing classes here
# to avoid circular imports.
if not TYPE_CHECKING:  # pragma: no branch

    def _typeface__or__(self, other: StyleLike, /) -> Style:
        return Style(font=self) | other

    def _typeface__ror__(self, other: HexColor, /) -> Style:
        return Style(font=self) | RGB.parse(other)

    BuiltinTypeface.__or__ = _typeface__or__
    BuiltinTypeface.__ror__ = _typeface__ror__
    TrueType.__or__ = _typeface__or__
    TrueType.__ror__ = _typeface__ror__

    def _rgb__or__(self, other: StyleLike, /) -> Style:
        return Style(color=self) | other

    def _rgb__ror__(self, other: HexColor, /) -> Style:
        return Style(color=self)

    RGB.__or__ = _rgb__or__
    RGB.__ror__ = _rgb__ror__
