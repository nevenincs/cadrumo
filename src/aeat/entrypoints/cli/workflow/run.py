"""``aeat workflow run`` -- run the read-only workflow for a caller-named target.

The command is read-only because live AEAT submission is permanently
forbidden.
"""

from __future__ import annotations

import typer

from ....application.workflow import WorkflowResult
from ....core.observability import (
    RunEventKind,
    RunEventPayload,
    WorkflowLinkPayload,
    record_event,
)
from .._observability import cli_run_context
from .._schemas import OutputRootSchema, register_schema
from ._helpers import run_engine_for_period


@register_schema("workflow run")
class WorkflowRunJson(OutputRootSchema[WorkflowResult]):
    """Schema for ``aeat workflow run --json``."""


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
