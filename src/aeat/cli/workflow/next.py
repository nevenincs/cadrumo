"""``aeat workflow next`` -- run the read-only workflow for the next obligation.

The command is read-only because live AEAT submission is permanently
forbidden.
"""

from __future__ import annotations

import typer

from ...observability import (
    RunEventKind,
    RunEventPayload,
    WorkflowLinkPayload,
    record_event,
)
from ...workflow import WorkflowResult
from .._observability import cli_run_context
from .._schemas import OutputRootSchema, register_schema
from ._helpers import run_engine_next


@register_schema("workflow next")
class WorkflowNextJson(OutputRootSchema[WorkflowResult]):
    """Schema for ``aeat workflow next --json``."""


def next_cmd(
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
    """Drive the workflow for the next pending obligation.

    Args:
        sync_first: Whether the sync stage should run.
        as_json: When ``True``, print the :class:`WorkflowResult` as JSON.
    """
    arguments = {
        "sync": sync_first,
        "json": as_json,
    }
    with cli_run_context(entrypoint="aeat workflow next", arguments=arguments):
        result = run_engine_next(
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
