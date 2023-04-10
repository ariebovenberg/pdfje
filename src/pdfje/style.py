from __future__ import annotations

from dataclasses import dataclass, fields, replace
from typing import TYPE_CHECKING, ClassVar, Iterator, TypeGuard, TypeVar

from .common import RGB, HexColor, Pt, add_slots, setattr_frozen
from .fonts.builtins import helvetica
from .fonts.common import BuiltinTypeface, TrueType, Typeface
from .fonts.registry import Registry
from .ops import SetColor, SetFont, SetLineSpacing, State, StateChange


@add_slots
@dataclass(frozen=True, init=False)
class Style:
    """Settings for visual style of text. All parameters are optional.

    The default style is Helvetica (regular) size 12, with line spacing 1.25

    Parameters
    ----------
    font: ~pdfje.TrueType | ~pdfje.BuiltinTypeface
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

    Example
    -------

    Below we can see how to create a style, and how to combine them.

    >>> from pdfje import Style, RGB, times_roman
    >>> body = Style(font=times_roman, size=14, italic=True))
    >>> heading = body | Style(size=24, bold=True, color=RGB(0.5, 0, 0))
    >>> # fonts and colors can be used directly in place of styles
    >>> emphasis = times_roman | "#ff0000"
    """

    font: Typeface | None = None
    size: Pt | None = None
    bold: bool | None = None
    italic: bool | None = None
    color: RGB | None = None
    line_spacing: float | None = None

    def __init__(
        self,
        font: Typeface | None = None,
        size: Pt | None = None,
        bold: bool | None = None,
        italic: bool | None = None,
        color: RGB | tuple[float, float, float] | HexColor | None = None,
        line_spacing: float | None = None,
    ) -> None:
        setattr_frozen(self, "font", font)
        setattr_frozen(self, "size", size)
        setattr_frozen(self, "bold", bold)
        setattr_frozen(self, "italic", italic)
        setattr_frozen(self, "line_spacing", line_spacing)
        setattr_frozen(self, "color", color and RGB.parse(color))

    def __or__(self, other: StyleLike, /) -> Style:
        if isinstance(other, Style):
            return Style(
                other.font or self.font,
                _fallback(other.size, self.size),
                _fallback(other.bold, self.bold),
                _fallback(other.italic, self.italic),
                other.color or self.color,
                _fallback(other.line_spacing, self.line_spacing),
            )
        elif isinstance(other, (TrueType, BuiltinTypeface)):
            return replace(self, font=other)
        elif isinstance(other, str):
            return replace(self, color=RGB.parse(other))
        elif isinstance(other, RGB):
            return replace(self, color=other)
        else:
            return NotImplemented  # type: ignore[unreachable]

    def __ror__(self, other: HexColor, /) -> Style:
        return Style(color=RGB.parse(other)) | self

    def __repr__(self) -> str:
        field_reprs = (
            (f.name, v)
            for f in fields(self)
            if (v := getattr(self, f.name)) is not None
        )
        return f"Style({', '.join(f'{k}={v!r}' for k, v in field_reprs)})"

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

    def diff(self, r: Registry, base: StyleFull) -> Iterator[StateChange]:
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

    def setdefault(self) -> StyleFull:
        return StyleFull.DEFAULT | self

    EMPTY: ClassVar[Style]


StyleLike = Style | RGB | Typeface | HexColor
Style.EMPTY = Style()

bold = Style(bold=True)
italic = Style(italic=True)
regular = Style(bold=False, italic=False)


@add_slots
@dataclass(frozen=True)
class StyleFull:
    font: Typeface
    size: Pt
    bold: bool
    italic: bool
    color: RGB
    line_spacing: float

    def __or__(self, s: Style, /) -> StyleFull:
        return StyleFull(
            s.font or self.font,
            _fallback(s.size, self.size),
            _fallback(s.bold, self.bold),
            _fallback(s.italic, self.italic),
            s.color or self.color,
            _fallback(s.line_spacing, self.line_spacing),
        )

    def as_state(self, fr: Registry) -> State:
        return State(
            fr.font(self.font, self.bold, self.italic),
            self.size,
            self.color,
            self.line_spacing,
        )

    def diff(
        self, registry: Registry, base: StyleFull
    ) -> Iterator[StateChange]:
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

    DEFAULT: ClassVar[StyleFull]


StyleFull.DEFAULT = StyleFull(helvetica, 12, False, False, RGB(0, 0, 0), 1.25)


_T = TypeVar("_T")


def _fallback(a: _T | None, b: _T) -> _T:
    return b if a is None else a


def _differs(a: _T | None, b: _T) -> TypeGuard[_T]:
    return a is not None and a != b


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
