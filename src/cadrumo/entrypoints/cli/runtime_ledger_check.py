"""Exact-profile CLI ledger check through registered runtime execution."""

from __future__ import annotations

from uuid import UUID

import typer

from ...application.ledger.check_operation import (
    LEDGER_CHECK_OPERATION_DEFINITION_ID,
    LedgerCheckProjection,
    LedgerCheckRequest,
)
from ...application.operations.public_period import PublicPeriod
from ...application.user_profile.access_contracts import AccessDenialCode
from ...core.bucket_pointer import require_active_bucket_id
from ...core.operations import OperationEffect, profile_operation_subject
from ...core.period import Period
from .errors import CliRefusedBoundaryError
from .registered_operation_errors import invalid_completion_error
from .runtime_profile_binding import require_profile_client
from .runtime_registered_operation import run_registered_operation


def read_ledger_check_for_cli(
    ctx: typer.Context, *, period: Period | None, bucket_id_option: str | None = None
) -> LedgerCheckProjection:
    """Correlate the explicit selector, bound profile and encrypted check result."""
    active_profile_id = UUID(require_active_bucket_id())
    if bucket_id_option is not None and bucket_id_option != str(active_profile_id):
        raise CliRefusedBoundaryError(
            AccessDenialCode.PROFILE_MISMATCH.value,
            context={"reason": AccessDenialCode.PROFILE_MISMATCH.value},
        )
    client = require_profile_client(ctx, expected_profile_id=active_profile_id)
    target_period = PublicPeriod.from_period(period) if period is not None else None
    completed = run_registered_operation(
        client,
        LedgerCheckRequest(profile_id=client.profile_id, period=target_period),
        definition_id=LEDGER_CHECK_OPERATION_DEFINITION_ID,
        subject_ref=profile_operation_subject(str(client.profile_id)),
        result_type=LedgerCheckProjection,
        request_version=1,
        result_version=1,
        timeout=60,
    )
    result = completed.projection
    if (
        result.profile_id != client.profile_id
        or result.bucket_id != str(client.profile_id)
        or result.period != target_period
        or completed.effect is not OperationEffect.NONE
    ):
        raise invalid_completion_error(completed)
    return result
