"""CLI transaction audit lineage through the exact-profile registered operation."""

from __future__ import annotations

from uuid import UUID

import typer

from ...application.ledger.track_operation import (
    LEDGER_TRACK_OPERATION_DEFINITION_ID,
    LedgerTrackProjection,
    LedgerTrackRequest,
)
from ...application.runtime.contracts import RuntimeRefusalCode
from ...core.bucket_pointer import require_active_bucket_id
from ...core.operations import OperationEffect, OperationTerminalCondition, profile_operation_subject
from .errors import CliRefusedBoundaryError
from .runtime_ledger_prefix import attach_submitted_ledger_prefix_verdict, normalise_ledger_transaction_id_prefix
from .runtime_profile_binding import require_profile_client
from .runtime_registered_operation import run_registered_operation, submitted_operation_error


def read_ledger_track_for_cli(ctx: typer.Context, *, transaction_id: str) -> LedgerTrackProjection:
    """Resolve the handle inside worker custody and correlate the returned lineage."""
    client = require_profile_client(ctx, expected_profile_id=UUID(require_active_bucket_id()))
    prefix = normalise_ledger_transaction_id_prefix(transaction_id)
    try:
        completed = run_registered_operation(
            client,
            LedgerTrackRequest(profile_id=client.profile_id, transaction_prefix=prefix),
            definition_id=LEDGER_TRACK_OPERATION_DEFINITION_ID,
            subject_ref=profile_operation_subject(str(client.profile_id)),
            result_type=LedgerTrackProjection,
            request_version=1,
            result_version=1,
            timeout=60,
        )
    except CliRefusedBoundaryError as error:
        attach_submitted_ledger_prefix_verdict(error)
        raise
    result = completed.projection
    if (
        result.profile_id != client.profile_id
        or result.transaction_prefix != prefix
        or completed.effect is not OperationEffect.NONE
    ):
        raise submitted_operation_error(
            completed.operation_id,
            RuntimeRefusalCode.INVALID_FRAME.value,
            terminal_condition=OperationTerminalCondition.SUCCEEDED,
            effect=completed.effect,
        )
    return result
