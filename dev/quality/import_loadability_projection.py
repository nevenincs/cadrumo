"""Import loadability projection."""

from __future__ import annotations

from collections.abc import Iterable
from typing import cast


def loadability_int(loadability: dict[str, object], key: str, default: int = 0) -> int:
    """Read an integer field from the subprocess JSON contract."""
    value = loadability.get(key, default)
    if isinstance(value, int):
        return value
    if isinstance(value, (str, bytes, bytearray, float)):
        return int(value)
    raise TypeError(f"loadability field {key!r} is not integer-compatible")


def loadability_items(loadability: dict[str, object], key: str) -> list[object]:
    """Read an iterable sample from the subprocess JSON contract."""
    value = loadability.get(key, ())
    if isinstance(value, Iterable):
        return list(cast("Iterable[object]", value))
    raise TypeError(f"loadability field {key!r} is not iterable")
