"""Shared real-CLI ledger projections for tests."""

from __future__ import annotations

from typing import Any

from .cli_envelope import require_schema_envelope
from .cli_runner import invoke_cached_cli


def list_ledger_rows_via_cli() -> list[dict[str, Any]]:
    """Return rows from the real registered ``ledger.list`` command."""
    listed = invoke_cached_cli(["--format", "json", "app", "ledger", "list"])
    if listed.exit_code != 0:
        raise AssertionError(listed.output)
    rows = require_schema_envelope(listed.output).get("rows")
    if not isinstance(rows, list):
        raise TypeError("ledger.list result rows must be a list")
    typed_rows: list[dict[str, Any]] = []
    for row in rows:
        if not isinstance(row, dict):
            raise TypeError("ledger.list result rows must contain objects")
        typed_rows.append(row)
    return typed_rows


__all__ = ["list_ledger_rows_via_cli"]
