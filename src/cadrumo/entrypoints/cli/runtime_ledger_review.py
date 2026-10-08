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
from ...core.bucket_pointer import require_active_bucket_id
from .runtime_ledger_prefix import normalise_ledger_transaction_id_prefix
from .runtime_ledger_prefix_read import read_ledger_prefix_projection
from .runtime_profile_binding import require_profile_client


def read_ledger_review_for_cli(
    ctx: typer.Context,
    *,
    spec: LedgerReviewFilterSpec,
    record_id: str | None,
) -> LedgerReviewProjection:
    """Retain canonical filter meaning, prefix refusal policy and the exact operation receipt."""
    client = require_profile_client(ctx, expected_profile_id=UUID(require_active_bucket_id()))
    prefix = normalise_ledger_transaction_id_prefix(record_id) if record_id is not None else None
    return read_ledger_prefix_projection(
        client,
        LedgerReviewRequest(
            profile_id=client.profile_id,
            filters=tuple(f"{clause.key}={clause.value}" for clause in spec.clauses),
            transaction_prefix=prefix,
        ),
        prefix=prefix,
        definition_id=LEDGER_REVIEW_OPERATION_DEFINITION_ID,
        result_type=LedgerReviewProjection,
    )
