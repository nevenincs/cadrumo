"""Raw typed-value comparison helpers for registry collapse verification."""

from __future__ import annotations

from collections.abc import Mapping


def _same_typed_value(left: object, right: object) -> bool:
    if type(left) is not type(right):
        return False
    if isinstance(left, Mapping) and isinstance(right, Mapping):
        return tuple(left) == tuple(right) and all(_same_typed_value(left[key], right[key]) for key in left)
    if isinstance(left, list | tuple) and isinstance(right, list | tuple):
        return len(left) == len(right) and all(
            _same_typed_value(old, new) for old, new in zip(left, right, strict=True)
        )
    return left == right
