"""``aeat workflow run`` -- run the engine for a caller-named target.

The command is dry-run-only. The 1.0.0 reintroduction path for live
submission is the planned ``aeat advanced workflow run --live`` leaf
documented in the controlling Kent-first CLI wireframe ADR; it is not
reachable from this default-CLI surface.
"""

from __future__ import annotations

import typer

from ...observability import (
    RunEventKind,
    RunEventPayload,
    WorkflowLinkPayload,
    record_event,
)
from .._observability import cli_run_context
from ._helpers import run_engine_for_period


def run_cmd(
    modelo: str = typer.Option(..., "--modelo", help="Modelo identifier (e.g. 130)."),
    period: str = typer.Option(..., "--period", help="Period identifier (e.g. 2026Q1)."),
    sync_first: bool = typer.Option(
        True,
        "--sync/--no-sync",
        help="Run the self-healing sync before the deadline stage (default: on).",
    ),
    as_json: bool = typer.Option(
        False,
        "--json",
        help="Emit the WorkflowResult as JSON on stdout.",
    ),
) -> None:
    """Drive the workflow for a named ``(modelo, period)`` target.

    The command always runs the workflow in dry-run mode. Live execution
    is not available from this surface; see the 1.0.0 reintroduction
    path documented in the controlling CLI wireframe ADR.

    Args:
        modelo: Target modelo identifier.
        period: Target period identifier.
        sync_first: Whether the sync stage should run.
        as_json: When ``True``, print the :class:`WorkflowResult` as JSON.
    """
    arguments = {
        "modelo": modelo,
        "period": period,
        "sync": sync_first,
        "json": as_json,
    }
    with cli_run_context(entrypoint="aeat workflow run", arguments=arguments):
        result = run_engine_for_period(
            modelo=modelo,
            period=period,
            dry_run=True,
            sync_first=sync_first,
            as_json=as_json,
        )
        record_event(
            RunEventKind.WORKFLOW_STARTED,
            payload=RunEventPayload(workflow_link=WorkflowLinkPayload(workflow_run_id=result.run_id)),
        )
        record_event(
            RunEventKind.WORKFLOW_COMPLETED,
            payload=RunEventPayload(workflow_link=WorkflowLinkPayload(workflow_run_id=result.run_id)),
        )
