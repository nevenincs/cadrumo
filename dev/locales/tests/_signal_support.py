"""Shared builders for the locale signal tests."""

from __future__ import annotations


def _list(value: object) -> list[object]:
    """Narrow one report payload list for length and member assertions."""
    if not isinstance(value, list):
        raise AssertionError("expected a list payload")
    result: list[object] = []
    result.extend(value)
    return result
