"""Size checks for wire collections whose schema bound would otherwise be a literal.

A request that needs at least two members, or exactly two, states that as arithmetic
here rather than as a length bound the schema carries.
"""

from __future__ import annotations

from collections.abc import Sized


def at_least_two[SizedT: Sized](value: SizedT) -> SizedT:
    """Return ``value`` when it holds two or more members."""
    if len(value) < 2:
        raise ValueError("at least two members are required")
    return value


def exactly_two[SizedT: Sized](value: SizedT) -> SizedT:
    """Return ``value`` when it holds exactly two members."""
    if len(value) != 2:
        raise ValueError("exactly two members are required")
    return value


__all__ = ["at_least_two", "exactly_two"]
