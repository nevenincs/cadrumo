"""Shared TOML-table narrowing helper for the registry loader family.

Extracted so both :mod:`aeat.domain.calculations.registry._loader` and
:mod:`aeat.domain.calculations.registry._loader_locales` can narrow a parsed
TOML value to a string-keyed table without importing each other (avoiding a
runtime import cycle between the compiler and the locale-merge submodule).
"""

from __future__ import annotations

from typing import cast


def as_toml_table(value: object) -> dict[str, object] | None:
    """Narrow a parsed TOML value to a string-keyed table, or ``None``.

    ``tomllib`` and :func:`aeat.core.freeze_toml` always emit ``str`` keys, so
    a parsed-TOML ``dict`` is genuinely ``dict[str, object]``. The runtime
    ``isinstance`` check loses the key type because TOML payloads flow
    through ``object``; the annotation below re-attaches the known ``str``
    key type at this single TOML deserialization boundary.
    """
    if isinstance(value, dict):
        # CAST-RATIONALE-TOML-STR-KEY-ERASURE: tomllib/freeze_toml always
        # produces str-keyed dicts; isinstance loses the key type annotation.
        return cast("dict[str, object]", value)
    return None
