"""Shared test helper: unwrap the CLI ``--json`` SchemaEnvelope.

Every migrated CLI command emits a typed envelope shaped as
``{"schema_version": int, "command": str, "result": {...},
"warnings": [...]}`` through ``_emit_envelope``. Test assertions
generally target the inner ``result`` mapping; pre-migration
commands emit the bare payload directly.

This module is the single source of the helper that ~12 test
modules previously duplicated inline under the name ``_payload``
each with the same docstring and body. New tests should import
:func:`unwrap_schema_envelope` from here rather than re-declaring it.
"""

from __future__ import annotations

import json


def unwrap_schema_envelope(output: str) -> dict:
    """Return the inner ``result`` mapping from a CLI ``--json`` envelope.

    Args:
        output: Raw stdout captured from a CLI ``--json`` invocation.

    Returns:
        The decoded inner ``result`` mapping if the payload is a
        SchemaEnvelope; otherwise the parsed top-level mapping
        unchanged (pre-migration commands still emit bare payloads).
    """
    raw = json.loads(output)
    if isinstance(raw, dict) and "schema_version" in raw and "result" in raw:
        return raw["result"]
    return raw
