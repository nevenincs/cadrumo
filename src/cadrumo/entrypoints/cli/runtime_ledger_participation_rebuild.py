"""CLI submission of a guarded profile participation-index replacement."""

from __future__ import annotations

from uuid import UUID

import typer

from ...application.ledger.participation_rebuild_operation import (
    LEDGER_PARTICIPATION_REBUILD_OPERATION_DEFINITION_ID,
    LedgerParticipationRebuildProjection,
    LedgerParticipationRebuildRequest,
)
from ...core.bucket_pointer import require_active_bucket_id
from ...core.operations import OperationEffect, profile_operation_subject
from .registered_operation_errors import invalid_completion_error
from .runtime_profile_binding import require_profile_client
from .runtime_registered_operation import run_registered_operation


def rebuild_ledger_participation_for_cli(ctx: typer.Context) -> LedgerParticipationRebuildProjection:
    """Retain the exact worker receipt and never replay an uncertain replacement."""
    client = require_profile_client(ctx, expected_profile_id=UUID(require_active_bucket_id()))
    completed = run_registered_operation(
        client,
        LedgerParticipationRebuildRequest(profile_id=client.profile_id),
        definition_id=LEDGER_PARTICIPATION_REBUILD_OPERATION_DEFINITION_ID,
        subject_ref=profile_operation_subject(str(client.profile_id)),
        result_type=LedgerParticipationRebuildProjection,
        request_version=1,
        result_version=1,
        timeout=60,
    )
    if completed.projection.profile_id != client.profile_id or completed.effect is not OperationEffect.UPDATED:
        raise invalid_completion_error(completed)
    return completed.projection
