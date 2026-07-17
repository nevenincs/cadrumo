"""Entrypoint-test facade for the canonical CLI envelope decoder.

Envelope-aware CLI commands emit a typed payload shaped as
``{"schema_version": str, "command": str, "status": str,
"result": {...}, "notices": [...]}`` through ``_emit_envelope``. Test
assertions generally target the inner ``result`` mapping; commands that
intentionally exercise a documented bare-payload exemption are passed
through unchanged.

The implementation lives in :mod:`cadrumo.tests.cli_envelope` so tests from
entrypoint, application, and agent packages share one cycle-safe authority.
Entrypoint-local tests retain this narrow facade for concise relative imports.
"""

from __future__ import annotations

from ....tests.cli_envelope import (
    require_schema_envelope,
    unwrap_cli_result,
    unwrap_envelope_notices,
    unwrap_schema_envelope,
)

__all__ = [
    "require_schema_envelope",
    "unwrap_cli_result",
    "unwrap_envelope_notices",
    "unwrap_schema_envelope",
]
