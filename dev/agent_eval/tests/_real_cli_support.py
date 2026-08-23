"""Shared real-CLI support for agent evaluation tests.

The helpers in this module project the live command-schema registry and invoke
the cached production CLI command tree. They delegate command discovery,
work-unit creation, and envelope decoding to canonical codebase authorities so
eval tests do not grow parallel orchestration logic.
"""

from __future__ import annotations

from cadrumo.entrypoints.cli import command_schema_refs
from cadrumo.tests.modelo_cli import create_modelo_work_unit_via_cli


def valid_cli_commands() -> frozenset[str]:
    """Return command keys projected from the live CLI schema registry."""
    return frozenset(ref.command for ref in command_schema_refs())


def create_m130_work_unit(*, filing_year: int, period: str, revision: str) -> str:
    """Create an M130 work unit through the real cached CLI command tree."""
    return create_modelo_work_unit_via_cli(
        modelo="130",
        filing_year=filing_year,
        period=period,
        revision=revision,
    )
