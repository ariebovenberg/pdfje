"Compatibility layer for various Python versions"
from __future__ import annotations

from itertools import tee
from typing import Iterable, Iterator, TypeVar

try:
    from itertools import pairwise
except ImportError:
    T = TypeVar("T")

    def pairwise(i: Iterable[T]) -> Iterator[tuple[T, T]]:
        a, b = tee(i)
        next(b, None)
        return zip(a, b)
