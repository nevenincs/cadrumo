"""CLI submission of a guarded profile participation-index replacement."""

from __future__ import annotations

from uuid import UUID

import typer

from ...application.ledger.participation_rebuild_operation import (
    LEDGER_PARTICIPATION_REBUILD_OPERATION_DEFINITION_ID,
    LedgerParticipationRebuildProjection,
    LedgerParticipationRebuildRequest,
)
from ...application.runtime.contracts import RuntimeRefusalCode
from ...core.bucket_pointer import require_active_bucket_id
from ...core.operations import OperationEffect, OperationTerminalCondition, profile_operation_subject
from .runtime_profile_binding import require_profile_client
from .runtime_registered_operation import run_registered_operation, submitted_operation_error


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
        raise submitted_operation_error(
            completed.operation_id,
            RuntimeRefusalCode.INVALID_FRAME.value,
            terminal_condition=OperationTerminalCondition.SUCCEEDED,
            effect=completed.effect,
        )
    return completed.projection
