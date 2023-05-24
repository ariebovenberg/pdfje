"Compatibility layer for various Python versions"
from __future__ import annotations

import sys
from itertools import tee
from typing import TYPE_CHECKING, Iterable, Iterator, TypeVar

__all__ = ["pairwise"]


if sys.version_info < (3, 10) or TYPE_CHECKING:
    T = TypeVar("T")

    def pairwise(i: Iterable[T]) -> Iterator[tuple[T, T]]:
        a, b = tee(i)
        next(b, None)
        return zip(a, b)

else:
    from itertools import pairwise
