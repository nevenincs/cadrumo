"""Shared JSON-narrowing helper for real-CLI test suites.

``STR_KEYED_MAPPING_ADAPTER.validate_python`` is the canonical core
type-narrowing primitive; this module exists only so its CLI-test callers
share one thin wrapper instead of each defining their own copy. It carries
no ledger, modelo, or other domain meaning, so it lives at the package root
of ``entrypoints/cli/tests/`` rather than inside a domain-scoped support
module (``_ledger_validation_support.py`` and siblings) whose name would
misdescribe a non-domain consumer importing it.
"""

from __future__ import annotations

from ....core.type_adapters import STR_KEYED_MAPPING_ADAPTER


def _json_object(value: object) -> dict[str, object]:
    """Narrow one decoded JSON value to a string-keyed object for typed subscripting."""
    return STR_KEYED_MAPPING_ADAPTER.validate_python(value)


__all__ = ["_json_object"]
