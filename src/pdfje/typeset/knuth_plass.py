"""Knuth-Plass line breaking algorithm.

Changes from the original algorithm:
- Instead of generic glue and penalty, we use explicit spaces and hyphenation.
- We don't allow for forced breaks within a paragraph -- only at the end.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from operator import attrgetter
from typing import Callable, Iterable, Literal, Sequence

from ..common import add_slots, peek
from ..compat import pairwise

Pos = int  # position in the list of boxes
LineNum = int  # zero-based line number
# As recommended in the paper, we store most widths cumulatively
# to prevent summing over and over
CumulativeWidth = float
# The adjustment ratio to justify the line, where -1 is
# fully shrunk and 1 is fully stretched. Note that stretch > 1 is possible
# (if potentially ugly), but additional shrink is not
# because words would be too close together.
Ratio = float
BIG: Ratio = 100
# Tight, loose, very tight, very loose
Fitness = Literal[0, 1, 2, 3]


@add_slots
@dataclass(frozen=True)
class Box:
    measure: CumulativeWidth
    stretch: CumulativeWidth
    shrink: CumulativeWidth
    incl_space: CumulativeWidth

    incl_hyphen: CumulativeWidth
    hyphenated: bool
    no_break: bool


def optimum_fit(
    bs: Iterable[Box],
    width: Callable[[LineNum], float],
    tol: float,
    hyphen_penalty: float = 100,
    consecutive_hyphen_penalty: float = 3000,
    fit_diff_penalty: float = 100,
    ragged: bool = False,
) -> Sequence[Break]:
    """Return the optimal break points for justifying the given boxes.

    Optimal means:
    - Minimizing the total stretch/shrink of lines
    - Avoiding hyphens if possible
    - Avoiding consecutive hyphens if possible
    - Avoiding very tight and very loose lines from following each other

    Parameters
    ----------
    bs
        The boxes to break.
    width
        A function that returns the width of the line at the given line number.
        Line numbers start at 0.
    tol
        The tolerance for the adjustment ratio. If no feasible breaks are found
        for the given tolerance, a `NoFeasibleBreaks` exception is raised.
        A higher tolerance will still produce an optimal result,
        but it will take longer to compute and may contain
        more 'ugly' lines (if this causes the overall result to be better).
    hyphen_penalty
        The penalty for a hyphen at the end of a line.
    consecutive_hyphen_penalty
        The penalty for consecutive hyphens.
    fit_diff_penalty
        The penalty for a difference in fitness between two consecutive breaks.
        (for example a very loose line followed by a tight line)
    ragged
        The algorithm is slightly different depending on whether you need
        ragged or justified text.
        If `ragged` is `False` (i.e. justtified), lines are penalized
        for stretching/shrinking of space *between* words.
        If `ragged` is `True`, lines are penalized for unused space,
        regardless of how many spaces are available between words.

        Note
        ----

        If ragged is set to `True`, the `stretch` value of the boxes
        should all be the same, and the `shrink` value should be 0.
        A good value for `stretch` is 3 times the space width.
        (This is derived from the approach in the paper)
    """
    # FUTURE: The ragged case probably be optimized further -- by eliminating
    #         the fitness difference penalty, for example.
    ratio = ratio_ragged if ragged else ratio_justified
    g = _BreakNetwork()

    try:
        box_next, bs = peek(iter(bs))
    except StopIteration:
        return ()

    pos = 0
    for pos, (box, box_next) in enumerate(pairwise(bs), start=1):
        if box.no_break:
            continue
        if g.is_empty():
            # Breaking here saves us time needlessly looping over the boxes
            # once we know there are no feasible breaks
            raise NoFeasibleBreaks()

        for node in list(g.nodes()):
            r = ratio(
                node.measure, node.stretch, node.shrink, box, width(node.line)
            )
            if r < -1:
                # This break is no longer feasible, because the line
                # would have to shrink too much to accomodate the content.
                # Thus, we remove it.
                g.remove(node)
            elif r <= tol:
                fit = _fitness(r)
                g.add(
                    _BreakNode(
                        pos,
                        node.line + 1,
                        r,
                        fit,
                        (
                            _main_demerit(hyphen_penalty * box.hyphenated, r)
                            + (
                                consecutive_hyphen_penalty
                                * box.hyphenated
                                * node.hyphenated
                            )
                            + (abs(fit - node.fitness) > 1) * fit_diff_penalty
                            + node.demerits
                        ),
                        box.incl_space,
                        box_next.stretch,
                        box_next.shrink,
                        box.hyphenated,
                        node,
                    )
                )

    return _optimal_end(
        g.nodes(), box_next, pos + 1, width, fit_diff_penalty, ratio
    ).unroll()


@add_slots
@dataclass(frozen=True)
class Break:
    pos: Pos
    adjust: Ratio
    demerits: float
    width: float


class NoFeasibleBreaks(Exception):
    "Raised when there are no feasible breaks for the given tolerance."


def _optimal_end(
    nodes: Iterable[_BreakNode],
    box: Box,
    pos: int,
    width: Callable[[LineNum], float],
    fit_diff_penalty: float,
    ratio: Callable[
        [CumulativeWidth, CumulativeWidth, CumulativeWidth, Box, float], Ratio
    ],
) -> _EndNode:
    options = (
        _EndNode(
            pos,
            r,
            _main_demerit(0, r)
            + (abs(_fitness(r) - n.fitness) > 1) * fit_diff_penalty
            + n.demerits,
            box.incl_space,
            n,
        )
        for n in nodes
        if (
            r := min(
                ratio(n.measure, n.stretch, n.shrink, box, width(n.line)), 0
            )
        )
        > -1
        # We don't need to check for r <= tol,
        # because the last line doesn't need to stretch
    )

    try:
        return min(options, key=_demerits)
    except ValueError:  # i.e. options is empty
        raise NoFeasibleBreaks()


def _fitness(r: Ratio) -> Fitness:
    return 0 if r < -0.5 else 1 if r <= 0.5 else 2 if r <= 1 else 3


_demerits: Callable[[_EndNode], float] = attrgetter("demerits")


def ratio_justified(
    measure: CumulativeWidth,
    stretch: CumulativeWidth,
    shrink: CumulativeWidth,
    b: Box,
    space: float,
) -> Ratio:
    length = b.incl_hyphen - measure
    try:
        return (space - length) / (
            (b.stretch - stretch) if length < space else (b.shrink - shrink)
        )
    except ZeroDivisionError:
        return (BIG + length / space) if length != space else 0


def ratio_ragged(
    measure: CumulativeWidth,
    _: CumulativeWidth,
    __: CumulativeWidth,
    b: Box,
    space: float,
) -> Ratio:
    leftover = space - b.incl_hyphen + measure
    if leftover >= 0:
        return leftover / b.stretch
    else:
        # If there is not enough space, returning anything smaller than -1
        # will cause the break to be discarded.
        return -2


def _main_demerit(penalty: float, r: Ratio) -> float:
    return (1 + 100 * abs(r) ** 3 + penalty) ** 2


@add_slots
@dataclass(frozen=True)
class _EndNode:
    pos: Pos
    ratio: Ratio
    demerits: float
    measure: float
    prev: _BreakNode = field(repr=False)

    def unroll(self) -> Sequence[Break]:
        node: _BreakNode | _EndNode = self
        result: list[Break] = []
        while node is not _ROOT:
            result.append(
                Break(
                    node.pos,
                    node.ratio,
                    node.demerits - node.prev.demerits,
                    node.measure - node.prev.measure,
                )
            )
            node = node.prev
        result.reverse()
        return result


@add_slots
@dataclass(frozen=True)
class _BreakNode:
    pos: Pos
    line: LineNum
    ratio: Ratio
    fitness: Fitness
    demerits: float

    measure: CumulativeWidth
    stretch: CumulativeWidth
    shrink: CumulativeWidth

    hyphenated: bool

    prev: _BreakNode = field(repr=False)


_ROOT = _BreakNode(0, 0, 0, 1, 0, 0, 0, 0, False, NotImplemented)


class _BreakNetwork:
    "A directed acyclic graph of possible breaks."
    __slots__ = ("_inner",)

    def __init__(self) -> None:
        self._inner: dict[tuple[LineNum, Pos, Fitness], _BreakNode] = {
            (0, 0, 1): _ROOT
        }

    # FUTURE: does the sorting of the output matter?
    def nodes(self) -> Iterable[_BreakNode]:
        return self._inner.values()

    def add(self, n: _BreakNode) -> None:
        key = (n.line, n.pos, n.fitness)
        # OPTIMIZE: from the paper: "we need not remember the Class 0
        # possibility if its total demerits exceed those of the Class 2 break
        # plus the demerits for contrasting lines, since the Class 0
        # breakpoint will never be optimum in such a case."
        old = self._inner.get(key)
        if old is None or n.demerits < old.demerits:
            self._inner[key] = n

    def is_empty(self) -> bool:
        return not self._inner

    def remove(self, n: _BreakNode) -> None:
        self._inner.pop((n.line, n.pos, n.fitness))
