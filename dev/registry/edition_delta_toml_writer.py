"""Small TOML value rendering primitives for edition delta authorship."""

from __future__ import annotations

from collections.abc import Mapping

from . import edition_delta_errors as _edition_delta_errors
from . import edition_delta_fields as _edition_delta_fields


def toml_string(value: str) -> str:
    """Render ``value`` as a TOML basic string, escaping control characters."""
    escaped = "".join(
        _edition_delta_fields._TOML_ESCAPES.get(
            char, f"\\u{ord(char):04x}" if ord(char) < 0x20 or ord(char) == 0x7F else char
        )
        for char in value
    )
    return f'"{escaped}"'


def toml_value(value: object) -> str:
    """Render a manifest value as inline TOML, refusing a type TOML cannot express."""
    if isinstance(value, str):
        return toml_string(value)
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int | float):
        return str(value)
    if isinstance(value, list | tuple):
        return "[" + ", ".join(toml_value(item) for item in value) + "]"
    if isinstance(value, Mapping):
        return "{ " + ", ".join(f"{key} = {toml_value(item)}" for key, item in value.items()) + " }"
    raise _edition_delta_errors.MigrationRefusedError(f"cannot render {type(value).__name__} as a manifest value")
