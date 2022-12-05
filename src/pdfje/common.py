from dataclasses import dataclass, fields
from itertools import chain
from typing import Any, Callable, TypeVar, overload

Pt = float
Inch = float
flatten = chain.from_iterable
Tclass = TypeVar("Tclass", bound=type)


inch: Callable[[Inch], Pt] = (72.0).__mul__


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
