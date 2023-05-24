from __future__ import annotations

from dataclasses import dataclass, field
from itertools import chain, count
from typing import Iterable, Iterator

from . import atoms
from .atoms import ASCII
from .common import add_slots
from .fonts import BuiltinTypeface, TrueType
from .fonts.common import BuiltinFont, Font, Typeface
from .fonts.embed import OBJS_PER_EMBEDDED_FONT, Subset


@add_slots
@dataclass(frozen=True, eq=False)
class Resources:
    """Keeps track of PDF resources within a document, such as fonts"""

    _builtins: dict[tuple[ASCII, bool, bool], BuiltinFont] = field(
        default_factory=dict
    )
    _subsets: dict[tuple[TrueType, bool, bool], Subset] = field(
        default_factory=dict
    )
    _next_subset_index: Iterator[int] = field(default_factory=count.__call__)

    def to_objects(self, first_id: atoms.ObjectID) -> Iterable[atoms.Object]:
        for sub, i in zip(
            self._subsets.values(),
            count(first_id, step=OBJS_PER_EMBEDDED_FONT),
        ):
            yield from sub.to_objects(i)

    def to_atoms(self, first_id: atoms.ObjectID) -> atoms.Dictionary:
        return atoms.Dictionary(
            (
                b"Font",
                atoms.Dictionary(
                    *chain(
                        (
                            (b.id, b.to_resource())
                            for b in self._builtins.values()
                        ),
                        (
                            (s.id, atoms.Ref(obj_id))
                            for s, obj_id in zip(
                                self._subsets.values(),
                                count(first_id, step=OBJS_PER_EMBEDDED_FONT),
                            )
                        ),
                    )
                ),
            )
        )

    def font(self, f: Typeface, bold: bool, italic: bool) -> Font:
        if isinstance(f, BuiltinTypeface):
            return self._builtins.setdefault(
                (f.regular.name, bold, italic), f.font(bold, italic)
            )
        else:
            try:
                return self._subsets[(f, bold, italic)]
            except KeyError:
                new_subset = self._subsets[(f, bold, italic)] = Subset.new(
                    b"F%i" % next(self._next_subset_index),
                    f.font(bold, italic),
                )
                return new_subset
