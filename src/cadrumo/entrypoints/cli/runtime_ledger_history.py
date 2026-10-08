"""CLI transaction lineage read under exact-profile runtime authority."""

from __future__ import annotations

from uuid import UUID

import typer

from ...application.ledger.history_operation import (
    LEDGER_HISTORY_OPERATION_DEFINITION_ID,
    LedgerHistoryProjection,
    LedgerHistoryRequest,
)
from ...core.bucket_pointer import require_active_bucket_id
from .runtime_ledger_prefix import normalise_ledger_transaction_id_prefix
from .runtime_ledger_prefix_read import read_ledger_prefix_projection
from .runtime_profile_binding import require_profile_client


def read_ledger_history_for_cli(
    ctx: typer.Context, *, transaction_id: str, include_split_siblings: bool
) -> LedgerHistoryProjection:
    """Resolve the historical handle in the worker and correlate its result."""
    client = require_profile_client(ctx, expected_profile_id=UUID(require_active_bucket_id()))
    prefix = normalise_ledger_transaction_id_prefix(transaction_id)
    return read_ledger_prefix_projection(
        client,
        LedgerHistoryRequest(
            profile_id=client.profile_id,
            transaction_prefix=prefix,
            include_split_siblings=include_split_siblings,
        ),
        prefix=prefix,
        definition_id=LEDGER_HISTORY_OPERATION_DEFINITION_ID,
        result_type=LedgerHistoryProjection,
        extra_matches=lambda result: result.include_split_siblings == include_split_siblings,
    )
