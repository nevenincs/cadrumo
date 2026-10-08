"""Refusal of a repeated coordinate in a repeating-row channel's list form.

A repeating-row channel (row binding values, row source identities, row casilla
values and their provenance) addresses each row by a coordinate. Its list wire
form can name one coordinate twice; reading that into a mapping would keep
whichever entry came last and drop the other without trace. Every reader of the
list form indexes it here, so a repeated coordinate is refused the same way at
every boundary, while each boundary keeps its own error contract.
"""

from __future__ import annotations

from collections.abc import Callable, Hashable, Iterable


def index_unique_row_coordinates[K: Hashable, V](
    entries: Iterable[tuple[K, V]],
    *,
    duplicate: Callable[[K], Exception],
) -> dict[K, V]:
    """Index ``(coordinate, value)`` entries in order, refusing a repeated coordinate.

    Args:
        entries: The channel's entries, each already keyed by its typed
            coordinate so that two spellings of one coordinate collide.
        duplicate: Builds the owning boundary's refusal for a repeated
            coordinate.

    Raises:
        Exception: The error ``duplicate`` builds, on the first repeated
            coordinate.
    """
    indexed: dict[K, V] = {}
    for coordinate, value in entries:
        if coordinate in indexed:
            raise duplicate(coordinate)
        indexed[coordinate] = value
    return indexed


__all__ = ["index_unique_row_coordinates"]
