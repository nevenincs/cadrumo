"""Read the closed set of identifiers a destination type alias declares."""

from __future__ import annotations

from typing import TypeAliasType, get_args


def closed_destination_ids(alias: TypeAliasType) -> frozenset[str]:
    """Return the string literals of a ``type`` alias over ``Literal[...]``, read from its declaration.

    Reading the alias itself, rather than a copy of its members, keeps the set
    and its declaration from drifting apart.
    """
    return frozenset(item for item in get_args(alias.__value__) if isinstance(item, str))
