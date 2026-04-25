"""``aeat workflow next`` -- run the engine for the caller's next obligation.

The command is dry-run-only. The submission engine retains its own
four-factor live-write gate (engine default ``live_transport_supported=False``,
inline ``AeatLiveTransportUnavailableError`` raise, ``AeatAccessGate``
env-var checks, interactive typed-phrase confirmation) but that contract
is not exposed from this default-CLI surface. The 1.0.0 reintroduction
path is the planned ``aeat advanced workflow next --live`` leaf documented
in the controlling Kent-first CLI wireframe ADR.
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
from ._helpers import run_engine_next


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

    The command always runs the workflow in dry-run mode. Live execution
    is not available from this surface; see the 1.0.0 reintroduction
    path documented in the controlling CLI wireframe ADR.

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
