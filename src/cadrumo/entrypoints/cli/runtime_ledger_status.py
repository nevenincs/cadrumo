"""Exact-profile CLI ledger status through registered runtime execution."""

from __future__ import annotations

from uuid import UUID

import typer

from ...application.ledger.status_operation import (
    LEDGER_STATUS_OPERATION_DEFINITION_ID,
    LedgerStatusProjection,
    LedgerStatusRequest,
)
from ...application.operations.public_period import PublicPeriod
from ...core.bucket_pointer import require_active_bucket_id
from ...core.operations import OperationEffect, profile_operation_subject
from ...core.period import Period
from .registered_operation_errors import invalid_completion_error
from .runtime_profile_binding import require_profile_client
from .runtime_registered_operation import run_registered_operation


def read_ledger_status_for_cli(ctx: typer.Context, *, period: Period | None) -> LedgerStatusProjection:
    """Read the existing whole-profile report without opening frontend custody."""
    client = require_profile_client(ctx, expected_profile_id=UUID(require_active_bucket_id()))
    target_period = PublicPeriod.from_period(period) if period is not None else None
    completed = run_registered_operation(
        client,
        LedgerStatusRequest(profile_id=client.profile_id, period=target_period),
        definition_id=LEDGER_STATUS_OPERATION_DEFINITION_ID,
        subject_ref=profile_operation_subject(str(client.profile_id)),
        result_type=LedgerStatusProjection,
        request_version=1,
        result_version=1,
        timeout=60,
    )
    result = completed.projection
    if (
        result.profile_id != client.profile_id
        or result.period != target_period
        or completed.effect is not OperationEffect.NONE
    ):
        raise invalid_completion_error(completed)
    return result
