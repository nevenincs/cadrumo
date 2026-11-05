"""TOML narrowing used exclusively while compiling authored registry input."""

from __future__ import annotations

from typing import cast


def as_toml_table(value: object) -> dict[str, object] | None:
    """Return ``value`` as a string-keyed table, or ``None`` when it is not one."""
    if not isinstance(value, dict):
        return None
    for key in cast("dict[object, object]", value):
        if not isinstance(key, str):
            return None
    return cast("dict[str, object]", value)
