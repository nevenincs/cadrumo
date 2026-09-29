"""CLI review queries through the encrypted exact-profile operation boundary."""

from __future__ import annotations

from uuid import UUID

import typer

from ...application.ledger.review_operation import (
    LEDGER_REVIEW_OPERATION_DEFINITION_ID,
    LedgerReviewProjection,
    LedgerReviewRequest,
)
from ...application.review.filter import LedgerReviewFilterSpec
from ...application.runtime.contracts import RuntimeRefusalCode
from ...core.bucket_pointer import require_active_bucket_id
from ...core.operations import OperationEffect, OperationTerminalCondition, profile_operation_subject
from .errors import CliRefusedBoundaryError
from .runtime_ledger_prefix import attach_submitted_ledger_prefix_verdict, normalise_ledger_transaction_id_prefix
from .runtime_profile_binding import require_profile_client
from .runtime_registered_operation import run_registered_operation, submitted_operation_error


def read_ledger_review_for_cli(
    ctx: typer.Context,
    *,
    spec: LedgerReviewFilterSpec,
    record_id: str | None,
) -> LedgerReviewProjection:
    """Retain canonical filter meaning, prefix refusal policy and the exact operation receipt."""
    client = require_profile_client(ctx, expected_profile_id=UUID(require_active_bucket_id()))
    prefix = normalise_ledger_transaction_id_prefix(record_id) if record_id is not None else None
    try:
        completed = run_registered_operation(
            client,
            LedgerReviewRequest(
                profile_id=client.profile_id,
                filters=tuple(f"{clause.key}={clause.value}" for clause in spec.clauses),
                transaction_prefix=prefix,
            ),
            definition_id=LEDGER_REVIEW_OPERATION_DEFINITION_ID,
            subject_ref=profile_operation_subject(str(client.profile_id)),
            result_type=LedgerReviewProjection,
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
