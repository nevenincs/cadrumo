"""Shared TOML-table narrowing helper for the registry loader family.

Kept as the single narrowing helper used by the registry compiler family.
"""

from __future__ import annotations

from typing import cast


def as_toml_table(value: object) -> dict[str, object] | None:
    """Narrow a parsed TOML value to a string-keyed table, or ``None``.

    The original dictionary identity is preserved and every key is validated
    before the deserialization-boundary type is restored.
    """
    if not isinstance(value, dict):
        return None
    # CAST-RATIONALE-TOML-TABLE-KEY-ITERATION: isinstance narrows to dict but
    # not its type parameters; each key is validated as str in the loop below.
    # nosemgrep: no-cast-in-domain-application
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
