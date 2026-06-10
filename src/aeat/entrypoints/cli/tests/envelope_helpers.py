"""Shared test helper: unwrap the CLI ``--json`` SchemaEnvelope.

Envelope-aware CLI commands emit a typed payload shaped as
``{"schema_version": int, "command": str, "result": {...},
"warnings": [...]}`` through ``_emit_envelope``. Test assertions
generally target the inner ``result`` mapping; commands that return a
plain payload directly are passed through unchanged.

This module is the single source of the helper that multiple test
modules previously duplicated inline under the name ``_payload``
each with the same docstring and body. New tests should import
:func:`unwrap_schema_envelope` from here rather than re-declaring it.
"""

from __future__ import annotations

import json
from typing import Any


def unwrap_schema_envelope(output: str) -> dict[str, Any]:
    """Return the inner ``result`` mapping from a CLI ``--json`` envelope.

    The value type is ``Any`` because the unwrapped payload is decoded
    JSON consumed by test assertions that subscript, iterate, and compare
    nested values directly; a test reading dynamic JSON is the canonical
    place ``Any`` is appropriate (test modules are exempt from the
    production ``Any``-rationale gate).

    Args:
        output: Raw stdout captured from a CLI ``--json`` invocation.

    Returns:
        The decoded inner ``result`` mapping if the payload is a
        SchemaEnvelope; otherwise the parsed top-level mapping
        unchanged.
    """
    raw = json.loads(output)
    if isinstance(raw, dict) and "schema_version" in raw and "result" in raw:
        return raw["result"]
    return raw
