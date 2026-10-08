"""CLI transaction view through the exact-profile registered operation."""

from __future__ import annotations

from uuid import UUID

import typer

from ...application.ledger.view_operation import (
    LEDGER_VIEW_OPERATION_DEFINITION_ID,
    LedgerViewProjection,
    LedgerViewRequest,
)
from ...core.bucket_pointer import require_active_bucket_id
from .runtime_ledger_prefix import normalise_ledger_transaction_id_prefix
from .runtime_ledger_prefix_read import read_ledger_prefix_projection
from .runtime_profile_binding import require_profile_client


def read_ledger_view_for_cli(ctx: typer.Context, *, transaction_id: str) -> LedgerViewProjection:
    """Resolve the handle inside worker custody and correlate the returned view."""
    client = require_profile_client(ctx, expected_profile_id=UUID(require_active_bucket_id()))
    prefix = normalise_ledger_transaction_id_prefix(transaction_id)
    return read_ledger_prefix_projection(
        client,
        LedgerViewRequest(profile_id=client.profile_id, transaction_prefix=prefix),
        prefix=prefix,
        definition_id=LEDGER_VIEW_OPERATION_DEFINITION_ID,
        result_type=LedgerViewProjection,
    )
