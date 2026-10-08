"""Import target value sets."""

from __future__ import annotations

import itertools
from collections.abc import Iterable, Sequence
from typing import Final

_MAX_ENUMERATED_VALUES: Final[int] = 128


def combine(left: frozenset[str] | None, right: frozenset[str] | None) -> frozenset[str] | None:
    """Combine finite string alternatives within the enumeration limit."""
    if left is None or right is None:
        return None
    return bounded({a + b for a, b in itertools.product(left, right)})


def products(groups: Sequence[Iterable[str]]) -> tuple[tuple[str, ...], ...]:
    """Return a bounded Cartesian product for finite formatter arguments."""
    products: list[tuple[str, ...]] = [()]
    for group in groups:
        products = [(*prefix, value) for prefix in products for value in group]
        if len(products) > _MAX_ENUMERATED_VALUES:
            return ()
    return tuple(products)


def union(left: frozenset[str] | None, right: frozenset[str] | None) -> frozenset[str] | None:
    """Union finite string alternatives within the enumeration limit."""
    if left is None or right is None:
        return None
    return bounded(set(left) | set(right))


def bounded(values: Iterable[str]) -> frozenset[str] | None:
    """Return finite values only when their count stays within the limit."""
    result = frozenset(values)
    return result if len(result) <= _MAX_ENUMERATED_VALUES else None
