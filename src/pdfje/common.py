from __future__ import annotations

from dataclasses import dataclass, fields
from functools import partial, wraps
from itertools import chain
from operator import itemgetter, mul
from typing import (
    TYPE_CHECKING,
    Any,
    Callable,
    Generic,
    Iterable,
    Iterator,
    Mapping,
    Protocol,
    Sequence,
    TypeVar,
    final,
    no_type_check,
    overload,
)

Pt = float
Char = str  # 1-character string
Pos = int  # position within a string (index)
HexColor = str  # 6-digit hex color, starting with `#`. e.g. #ff0000

flatten = chain.from_iterable
inch: Callable[[float], Pt] = partial(mul, 72)
inch.__doc__ = "Convert inches to points"
cm: Callable[[float], Pt] = partial(mul, 28.346456692913385)
cm.__doc__ = "Convert centimeters to points"
mm: Callable[[float], Pt] = partial(mul, 2.8346456692913385)
mm.__doc__ = "Convert millimeters to points"
pc: Callable[[float], Pt] = partial(mul, 12)
pc.__doc__ = "Convert picas to points"
pt: Callable[[float], Pt] = lambda x: x
pt.__doc__ = "No-op conversion. Can be used to make units explicit."
first = itemgetter(0)
second = itemgetter(1)
Ordinal = int  # a unicode code point
NonEmptySequence = Sequence
NonEmtpyIterator = Iterator

Tclass = TypeVar("Tclass", bound=type)
T = TypeVar("T")
U = TypeVar("U")


def prepend(i: T, it: Iterable[T]) -> Iterator[T]:
    return chain((i,), it)


def always(v: T) -> Callable[..., T]:
    return lambda *_, **__: v


setattr_frozen = object.__setattr__


# adapted from github.com/ericvsmith/dataclasses
# under its Apache 2.0 license.
def add_slots(cls: Tclass) -> Tclass:  # pragma: no cover
    if "__slots__" in cls.__dict__:
        raise TypeError(f"{cls.__name__} already specifies __slots__")
    cls_dict = dict(cls.__dict__)
    field_names = tuple(f.name for f in fields(cls))
    cls_dict["__slots__"] = field_names
    for field_name in field_names:
        # Remove our attributes, if present. They'll still be
        #  available in _MARKER.
        cls_dict.pop(field_name, None)
    # Remove __dict__ itself.
    cls_dict.pop("__dict__", None)
    # And finally create the class.
    qualname = getattr(cls, "__qualname__", None)
    cls = type(cls)(cls.__name__, cls.__bases__, cls_dict)
    if qualname is not None:
        cls.__qualname__ = qualname
    return cls


@final
@add_slots
@dataclass(frozen=True, repr=False)
class XY(Sequence[float]):
    """Represents a point, vector, or size in 2D space.

    This class supports some basic operators:

    .. code-block:: python

        >>> XY(1, 2) + XY(3, 4)
        XY(4, 6)
        # two-tuples are also supported
        >>> XY(1, 2) - (3, 4)
        XY(-2, -2)
        >>> XY(1, 2) / 2
        XY(0.5, 1.0)
        >>> XY(1, 2) * 2
        XY(2, 4)

    It also implements the :class:`~collections.abc.Sequence` protocol:

    .. code-block:: python

        >>> xy = XY(1, 2)
        >>> xy[0]
        1
        >>> x, y = xy
        >>> list(xy)
        [1, 2]

    """

    x: float = 0
    y: float = 0

    def __repr__(self) -> str:
        return f"XY({self.x}, {self.y})"

    def astuple(self) -> tuple[float, float]:
        return (self.x, self.y)

    @staticmethod
    def parse(v: XY | tuple[float, float], /) -> XY:
        return XY(*v) if isinstance(v, tuple) else v

    def __iter__(self) -> Iterator[float]:
        yield self.x
        yield self.y

    # We don't support slices -- which is technically a Sequence protocol
    # violation. But in practice this is not an issue.
    def __getitem__(self, i: int) -> float:  # type: ignore[override]
        if i == 0:
            return self.x
        elif i == 1:
            return self.y
        else:
            raise IndexError(i)

    def __len__(self) -> int:
        return 2

    def __truediv__(self, other: float | int) -> XY:
        if isinstance(other, (float, int)):
            return XY(self.x / other, self.y / other)
        else:
            return NotImplemented  # type: ignore[unreachable]

    def __mul__(self, other: float | int) -> XY:
        if isinstance(other, (float, int)):
            return XY(self.x * other, self.y * other)
        else:
            return NotImplemented  # type: ignore[unreachable]

    def __sub__(self, other: XY | tuple[float, float]) -> XY:
        if isinstance(other, tuple):
            return XY(self.x - other[0], self.y - other[1])
        elif isinstance(other, XY):
            return XY(self.x - other.x, self.y - other.y)
        else:
            return NotImplemented  # type: ignore[unreachable]

    def __add__(self, other: XY | tuple[float, float]) -> XY:
        if isinstance(other, tuple):
            return XY(self.x + other[0], self.y + other[1])
        elif isinstance(other, XY):
            return XY(self.x + other.x, self.y + other.y)
        else:
            return NotImplemented  # type: ignore[unreachable]

    def add_x(self, x: float) -> XY:
        return XY(self.x + x, self.y)

    def add_y(self, y: float) -> XY:
        return XY(self.x, self.y + y)

    def flip(self) -> XY:
        "Return a new XY with x and y swapped"
        return XY(self.y, self.x)


@add_slots
@dataclass(frozen=True)
class Sides(Sequence[float]):
    """Represents a set of four sides. Used for padding and margins."""

    top: Pt = 0
    right: Pt = 0
    bottom: Pt = 0
    left: Pt = 0

    def __iter__(self) -> Iterator[Pt]:
        yield self.top
        yield self.right
        yield self.bottom
        yield self.left

    def astuple(self) -> tuple[Pt, Pt, Pt, Pt]:
        return (self.top, self.right, self.bottom, self.left)

    # We don't support slices -- which is technically a Sequence protocol
    # violation. But in practice this is not an issue.
    def __getitem__(self, i: int) -> Pt:  # type: ignore[override]
        if i == 0:
            return self.top
        elif i == 1:
            return self.right
        elif i == 2:
            return self.bottom
        elif i == 3:
            return self.left
        else:
            raise IndexError(i)

    def __len__(self) -> int:
        return 4

    @staticmethod
    def parse(v: SidesLike, /) -> Sides:
        if isinstance(v, Sides):
            return v
        elif isinstance(v, tuple):
            if len(v) == 4:
                return Sides(*v)
            elif len(v) == 3:
                return Sides(v[0], v[1], v[2], v[1])  # type: ignore[misc]
            elif len(v) == 2:
                return Sides(v[0], v[1], v[0], v[1])
            else:
                raise TypeError(f"Cannot parse {v} as sides")
        elif isinstance(v, (float, int)):
            return Sides(v, v, v, v)
        else:
            raise TypeError(f"Cannot parse {v} as sides")


SidesLike = (
    Sides | tuple[Pt, Pt, Pt, Pt] | tuple[Pt, Pt, Pt] | tuple[Pt, Pt] | Pt
)


A0 = XY(2380, 3368)
A1 = XY(1684, 2380)
A2 = XY(1190, 1684)
A3 = XY(842, 1190)
A4 = XY(595, 842)
A5 = XY(420, 595)
A6 = XY(297, 420)
A7 = XY(210, 297)
A8 = XY(148, 210)
A0_landscape = A0.flip()
A1_landscape = A1.flip()
A2_landscape = A2.flip()
A3_landscape = A3.flip()
A4_landscape = A4.flip()
A5_landscape = A5.flip()
A6_landscape = A6.flip()
A7_landscape = A7.flip()
A8_landscape = A8.flip()
letter = XY(612, 792)
letter_landscape = letter.flip()
legal = XY(612, 1008)
legal_landscape = legal.flip()
tabloid = XY(792, 1224)
ledger = tabloid_landscape = tabloid.flip()


@final
@add_slots
@dataclass(frozen=True, repr=False)
class RGB(Sequence[float]):
    """Represents a color in RGB space, with values between 0 and 1.

    Common colors are available as constants:

    .. code-block:: python

        from pdfje import red, lime, blue, black, white, yellow, cyan, magenta

    Note
    ----

    In most cases where you would use a color, you can use a string
    of the form ``#RRGGBB`` or instead, e.g. ``#fa9225``

    """

    red: float = 0
    green: float = 0
    blue: float = 0

    def __post_init__(self) -> None:
        assert (
            self.red <= 1 and self.green <= 1 and self.blue <= 1
        ), "RGB values too large. They should be between 0 and 1"

    # We don't support slices -- which is technically a Sequence protocol
    # violation. But in practice this is not an issue.
    def __getitem__(self, i: int) -> float:  # type: ignore[override]
        if i == 0:
            return self.red
        elif i == 1:
            return self.green
        elif i == 2:
            return self.blue
        else:
            raise IndexError(i)

    def __len__(self) -> int:
        return 3

    @staticmethod
    def parse(v: RGB | tuple[float, float, float] | str, /) -> RGB:
        if isinstance(v, tuple):
            assert len(v) == 3, "RGB tuple must have 3 values"
            return RGB(*v)
        elif isinstance(v, str):
            assert v.startswith("#"), "RGB string must start with #"
            assert len(v) == 7, "RGB string must have 7 characters"
            return RGB(
                int(v[1:3], 16) / 255,
                int(v[3:5], 16) / 255,
                int(v[5:7], 16) / 255,
            )
        else:
            assert isinstance(v, RGB), "invalid RGB value"
            return v

    def astuple(self) -> tuple[float, float, float]:
        return (self.red, self.green, self.blue)

    def __repr__(self) -> str:
        return f"RGB({self.red:.3f}, {self.green:.3f}, {self.blue:.3f})"

    # This method cannot be defined in the class body, as it would cause a
    # circular import. The implementation is patched into the class
    # in the `style` module.
    if TYPE_CHECKING:  # pragma: no cover
        from .style import Style, StyleLike

        def __or__(self, _: StyleLike, /) -> Style:
            ...

        def __ror__(self, _: HexColor, /) -> Style:
            ...

    def __iter__(self) -> Iterator[float]:
        yield self.red
        yield self.green
        yield self.blue


red = RGB(1, 0, 0)
lime = RGB(0, 1, 0)
blue = RGB(0, 0, 1)
black = RGB(0, 0, 0)
white = RGB(1, 1, 1)
yellow = RGB(1, 1, 0)
magenta = RGB(1, 0, 1)
cyan = RGB(0, 1, 1)


# This makes the generator function behave like a "classic coroutine"
# as described in fluentpython.com/extra/classic-coroutines.
# Such a coroutine doesn't output anything on the first `yield`.
# This allows the caller to use the `.send()` method immediately.
@no_type_check
def skips_to_first_yield(func: T, /) -> T:
    """Decorator which primes a generator func by calling the first next()"""

    @wraps(func)
    def primer(*args, **kwargs):
        gen = func(*args, **kwargs)
        next(gen)
        return gen

    return primer


@add_slots
@dataclass(frozen=True)
class dictget(Generic[T, U]):
    _map: Mapping[T, U]
    default: U

    def __call__(self, k: T) -> U:
        try:
            return self._map[k]
        except KeyError:
            return self.default


# The copious overloads are to enable mypy to
# deduce the proper callable types -- up to a limit.


T1 = TypeVar("T1")
T2 = TypeVar("T2")
T3 = TypeVar("T3")
T4 = TypeVar("T4")
T5 = TypeVar("T5")
T6 = TypeVar("T6")
T7 = TypeVar("T7")
T8 = TypeVar("T8")
T9 = TypeVar("T9")


@overload
def pipe() -> Callable[[T1], T1]:
    ...


@overload  # noqa: F811
def pipe(__f1: Callable[[T1], T2]) -> Callable[[T1], T2]:
    ...


@overload  # noqa: F811
def pipe(
    __f1: Callable[[T1], T2], __f2: Callable[[T2], T3]
) -> Callable[[T1], T3]:
    ...


@overload  # noqa: F811
def pipe(
    __f1: Callable[[T1], T2],
    __f2: Callable[[T2], T3],
    __f3: Callable[[T3], T4],
) -> Callable[[T1], T4]:
    ...


@overload  # noqa: F811
def pipe(
    __f1: Callable[[T1], T2],
    __f2: Callable[[T2], T3],
    __f3: Callable[[T3], T4],
    __f4: Callable[[T4], T5],
) -> Callable[[T1], T5]:
    ...


@overload  # noqa: F811
def pipe(
    __f1: Callable[[T1], T2],
    __f2: Callable[[T2], T3],
    __f3: Callable[[T3], T4],
    __f4: Callable[[T4], T5],
    __f5: Callable[[T5], T6],
) -> Callable[[T1], T6]:
    ...


@overload  # noqa: F811
def pipe(
    __f1: Callable[[T1], T2],
    __f2: Callable[[T2], T3],
    __f3: Callable[[T3], T4],
    __f4: Callable[[T4], T5],
    __f5: Callable[[T5], T6],
    __f6: Callable[[T6], T7],
) -> Callable[[T1], T7]:
    ...


@overload  # noqa: F811
def pipe(
    __f1: Callable[[T1], T2],
    __f2: Callable[[T2], T3],
    __f3: Callable[[T3], T4],
    __f4: Callable[[T4], T5],
    __f5: Callable[[T5], T6],
    __f6: Callable[[T6], T7],
    __f7: Callable[[T7], T8],
) -> Callable[[T1], T8]:
    ...


@overload  # noqa: F811
def pipe(
    __f1: Callable,
    __f2: Callable,
    __f3: Callable,
    __f4: Callable,
    __f5: Callable,
    __f6: Callable,
    __f7: Callable,
    *__fn: Callable,
) -> Callable:
    ...


def pipe(*__fs: Any) -> Any:  # noqa: F811
    """Create a new callable by piping several in succession
    Example
    -------
    >>> fn = pipe(float, lambda x: x / 4, int)
    >>> fn('9.3')
    2
    Note
    ----
    * Type checking is supported up to 7 functions,
      due to limitations of the Python type system.
    """
    return __pipe(__fs)


@dataclass(frozen=True, repr=False)
class __pipe:
    __slots__ = ("_functions",)
    _functions: tuple[Callable[[Any], Any], ...]

    def __call__(self, value: Any) -> Any:
        for f in self._functions:
            value = f(value)
        return value


T_contra = TypeVar("T_contra", contravariant=True)
T_co = TypeVar("T_co", covariant=True)


# shortcut for Callable[[T_contra], T_co]. Necessary for typing
# dataclass fields, as Callable is interpreted incorrectly.
class Func(Protocol[T_contra, T_co]):
    def __call__(self, __value: T_contra) -> T_co:
        ...
