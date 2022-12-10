from __future__ import annotations

from dataclasses import dataclass, fields
from functools import wraps
from itertools import chain
from operator import itemgetter
from typing import (
    Any,
    Callable,
    Generic,
    Iterable,
    Iterator,
    Mapping,
    Protocol,
    TypeVar,
    no_type_check,
    overload,
)

__all__ = [
    "Pt",
    "Inch",
    "XY",
    "RGB",
]

Pt = float
Inch = float
Char = str  # 1-character string

flatten = chain.from_iterable
inch: Callable[[Inch], Pt] = (72.0).__mul__
first = itemgetter(0)
second = itemgetter(1)
Ordinal = int  # a unicode code point

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


@add_slots
@dataclass(frozen=True)
class XY:
    x: float
    y: float

    def astuple(self) -> tuple[float, float]:
        return (self.x, self.y)

    @staticmethod
    def parse(v: XY | tuple[float, float], /) -> XY:
        return XY(*v) if isinstance(v, tuple) else v

    def __iter__(self) -> Iterator[float]:
        yield self.x
        yield self.y


@add_slots
@dataclass(frozen=True, repr=False)
class RGB:
    red: float
    green: float
    blue: float

    def astuple(self) -> tuple[float, float, float]:
        return (self.red, self.green, self.blue)

    def __repr__(self) -> str:
        return f"RGB({self.red}, {self.green}, {self.blue})"

    def __iter__(self) -> Iterator[float]:
        yield self.red
        yield self.green
        yield self.blue


@add_slots
@dataclass(init=False)
class PeekableIterator(Iterator[T]):  # where T is never None
    _inner: Iterator[T]
    _next_item: T | None

    def __init__(self, it: Iterable[T] = ()) -> None:
        self._inner = iter(it)
        self._next_item = None

    def __next__(self) -> T:
        if self._next_item is None:
            return next(self._inner)
        else:
            val = self._next_item
            self._next_item = None
            return val

    def peek(self) -> T | None:
        if self._next_item is None:
            self._next_item = next(self._inner, None)
        return self._next_item

    def exhausted(self) -> bool:
        return self.peek() is None


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
