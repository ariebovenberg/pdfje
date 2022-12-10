from typing import TYPE_CHECKING, Collection, Iterable, Sequence, TypeVar

from pdfje import Rule

T = TypeVar("T")


# a book is a sequence of chapters, which are sequences of paragraphs
Book = Sequence[Sequence[str | Rule]]


class eq_iter(list[T]):
    """Test helper for comparing iterables."""

    def __eq__(self, other: object) -> bool:
        if isinstance(other, Sequence):
            return list(self) == list(other)
        elif isinstance(other, Collection):
            return set(self) == set(other)
        elif isinstance(other, Iterable):
            return list.__eq__(self, list(other))
        return NotImplemented


if TYPE_CHECKING:
    approx = float.__call__
else:
    from pytest import approx  # noqa
