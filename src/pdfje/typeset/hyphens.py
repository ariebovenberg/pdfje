from functools import partial
from itertools import chain, pairwise, starmap
from typing import TYPE_CHECKING, Callable, Iterable

Hyphenator = Callable[[str], Iterable[str]]
" hyphenation -> hy phen ation "


def never_hyphenate(txt: str) -> Iterable[str]:
    return (txt,)


# The confusing logic here is to avoid importing pyphen if it's not
# installed, and also keeping the type checker happy -- complicated
# by the fact that pyphen has no type annotations.
if TYPE_CHECKING:

    class Pyphen:
        def __init__(self, lang: str) -> None:
            ...

        def positions(self, txt: str) -> Iterable[int]:
            ...

    HAS_PYPHEN = True

    HyphenatorLike = Hyphenator | Pyphen | None

else:
    try:
        from pyphen import Pyphen
    except ImportError:  # pragma: no cover
        HAS_PYPHEN = False
        HyphenatorLike = Hyphenator | None
    else:
        HAS_PYPHEN = True
        HyphenatorLike = Hyphenator | Pyphen | None


if HAS_PYPHEN:

    def parse_hyphenator(p: HyphenatorLike) -> Hyphenator:
        if isinstance(p, Pyphen):
            return partial(_pyphenate, p)
        elif p is None:
            return never_hyphenate
        return p

    def _pyphenate(p: Pyphen, txt: str) -> Iterable[str]:
        return (
            map(
                txt.__getitem__,
                starmap(slice, pairwise(chain((0,), pos, (None,)))),
            )
            if (pos := p.positions(txt))
            else (txt,)
        )

    default_hyphenator: Hyphenator = partial(_pyphenate, Pyphen(lang="en_US"))

else:  # pragma: no cover
    from ..vendor.hyphenate import hyphenate_word

    default_hyphenator = hyphenate_word

    def parse_hyphenator(p: HyphenatorLike) -> Hyphenator:
        return never_hyphenate if p is None else p  # type: ignore
