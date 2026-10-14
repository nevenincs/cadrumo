"""Shared JSON-narrowing helper for real-CLI test suites.

``STR_KEYED_MAPPING_ADAPTER.validate_python`` is the canonical core
type-narrowing primitive; this module exists only so test callers share one
thin wrapper instead of each defining their own copy. It carries no ledger,
modelo, or other domain meaning.
"""

from __future__ import annotations

from cadrumo.core.type_adapters import STR_KEYED_MAPPING_ADAPTER


def _json_object(value: object) -> dict[str, object]:
    """Narrow one decoded JSON value to a string-keyed object for typed subscripting."""
    return STR_KEYED_MAPPING_ADAPTER.validate_python(value)


__all__ = ["_json_object"]
