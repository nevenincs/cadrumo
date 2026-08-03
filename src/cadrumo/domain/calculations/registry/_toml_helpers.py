"""Shared TOML-table narrowing helper for the registry loader family.

Extracted so both :mod:`~domain.calculations.registry._loader` and
:mod:`~domain.calculations.registry._loader_locales` can narrow a parsed
TOML value to a string-keyed table without importing each other (avoiding a
runtime import cycle between the compiler and the locale-merge submodule).
"""

from __future__ import annotations

from typing import cast


def as_toml_table(value: object) -> dict[str, object] | None:
    """Narrow a parsed TOML value to a string-keyed table, or ``None``.

    The original dictionary identity is preserved because locale-fragment
    merging updates the compiled table in place. Every key is validated
    before the deserialization-boundary type is restored.
    """
    if not isinstance(value, dict):
        return None
    for key in cast("dict[object, object]", value):
        if not isinstance(key, str):
            return None
    # CAST-RATIONALE-TOML-VALIDATED-KEYS-PRESERVE-IDENTITY: every key is
    # runtime-validated as str, but a cast is required to retain the original
    # dict identity used by in-place locale merging.
    return cast(  # nosemgrep: no-cast-in-domain-application reason: validated table identity must survive merging.
        "dict[str, object]",
        value,
    )
