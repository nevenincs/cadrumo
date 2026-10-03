"""Exact-period CLI ledger preflight through registered runtime custody."""

from __future__ import annotations

from uuid import UUID

import typer

from ...application.ledger.preflight_operation import (
    LEDGER_PREFLIGHT_OPERATION_DEFINITION_ID,
    LedgerPreflightProjection,
    LedgerPreflightRequest,
)
from ...application.operations.public_period import PublicPeriod
from ...application.runtime.contracts import RuntimeRefusalCode
from ...core.bucket_pointer import require_active_bucket_id
from ...core.operations import OperationEffect, OperationTerminalCondition, profile_operation_subject
from ...core.period import Period
from .runtime_profile_binding import require_profile_client
from .runtime_registered_operation import run_registered_operation, submitted_operation_error


def read_ledger_preflight_for_cli(ctx: typer.Context, *, period: Period) -> LedgerPreflightProjection:
    """Submit one canonical period and correlate all encrypted result facts."""
    client = require_profile_client(ctx, expected_profile_id=UUID(require_active_bucket_id()))
    selected_period = PublicPeriod.from_period(period)
    completed = run_registered_operation(
        client,
        LedgerPreflightRequest(profile_id=client.profile_id, period=selected_period),
        definition_id=LEDGER_PREFLIGHT_OPERATION_DEFINITION_ID,
        subject_ref=profile_operation_subject(str(client.profile_id)),
        result_type=LedgerPreflightProjection,
        request_version=1,
        result_version=1,
        timeout=60,
    )
    result = completed.projection
    if (
        result.profile_id != client.profile_id
        or result.bucket_id != str(client.profile_id)
        or result.period != selected_period
        or completed.effect is not OperationEffect.NONE
    ):
        raise submitted_operation_error(
            completed.operation_id,
            RuntimeRefusalCode.INVALID_FRAME.value,
            terminal_condition=OperationTerminalCondition.SUCCEEDED,
            effect=completed.effect,
        )
    return result
