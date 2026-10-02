"""CLI transaction lineage read under exact-profile runtime authority."""

from __future__ import annotations

from uuid import UUID

import typer

from ...application.ledger.history_operation import (
    LEDGER_HISTORY_OPERATION_DEFINITION_ID,
    LedgerHistoryProjection,
    LedgerHistoryRequest,
)
from ...application.runtime.contracts import RuntimeRefusalCode
from ...core.bucket_pointer import require_active_bucket_id
from ...core.operations import OperationEffect, OperationTerminalCondition, profile_operation_subject
from .errors import CliRefusedBoundaryError
from .runtime_ledger_prefix import attach_submitted_ledger_prefix_verdict, normalise_ledger_transaction_id_prefix
from .runtime_profile_binding import require_profile_client
from .runtime_registered_operation import run_registered_operation, submitted_operation_error


def read_ledger_history_for_cli(
    ctx: typer.Context, *, transaction_id: str, include_split_siblings: bool
) -> LedgerHistoryProjection:
    """Resolve the historical handle in the worker and correlate its result."""
    client = require_profile_client(ctx, expected_profile_id=UUID(require_active_bucket_id()))
    prefix = normalise_ledger_transaction_id_prefix(transaction_id)
    try:
        completed = run_registered_operation(
            client,
            LedgerHistoryRequest(
                profile_id=client.profile_id,
                transaction_prefix=prefix,
                include_split_siblings=include_split_siblings,
            ),
            definition_id=LEDGER_HISTORY_OPERATION_DEFINITION_ID,
            subject_ref=profile_operation_subject(str(client.profile_id)),
            result_type=LedgerHistoryProjection,
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
        or result.include_split_siblings != include_split_siblings
        or completed.effect is not OperationEffect.NONE
    ):
        raise submitted_operation_error(
            completed.operation_id,
            RuntimeRefusalCode.INVALID_FRAME.value,
            terminal_condition=OperationTerminalCondition.SUCCEEDED,
            effect=completed.effect,
        )
    return result
