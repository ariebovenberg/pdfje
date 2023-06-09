"Compatibility layer for various Python versions"
from __future__ import annotations

import sys
from itertools import tee
from typing import TYPE_CHECKING, Callable, Iterable, Iterator, TypeVar

__all__ = ["pairwise", "cache"]


if sys.version_info < (3, 10) or TYPE_CHECKING:  # pragma: no cover
    T = TypeVar("T")

    def pairwise(i: Iterable[T]) -> Iterator[tuple[T, T]]:
        a, b = tee(i)
        next(b, None)
        return zip(a, b)

else:
    from itertools import pairwise


if sys.version_info < (3, 9) or TYPE_CHECKING:  # pragma: no cover
    from functools import lru_cache

    _Tcall = TypeVar("_Tcall", bound=Callable[..., object])

    def cache(func: _Tcall) -> _Tcall:
        return lru_cache(maxsize=None)(func)  # type: ignore

else:
    from functools import cache
