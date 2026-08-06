"""Shared real modelo CLI orchestration for tests.

This module owns the common transport-only path for creating a modelo work
unit through the cached production CLI. Test packages supply scenario data;
the helper performs no calculation, persistence, or selection policy itself.
"""

from __future__ import annotations

from .cli_envelope import require_schema_envelope
from .cli_runner import invoke_cached_cli


def create_modelo_work_unit_via_cli(
    *,
    modelo: str,
    filing_year: int | str,
    period: str,
    revision: str,
) -> str:
    """Create a real modelo work unit and return its validated envelope id."""
    result = invoke_cached_cli(
        [
            "--format",
            "json",
            "app",
            "modelo",
            "work",
            "create",
            "--modelo",
            modelo,
            "--year",
            str(filing_year),
            "--period",
            period,
            "--revision",
            revision,
        ],
    )
    assert result.exit_code == 0, result.output
    payload = require_schema_envelope(result.output)
    work_unit_id = payload.get("work_unit_id")
    assert isinstance(work_unit_id, str) and work_unit_id, result.output
    return work_unit_id
