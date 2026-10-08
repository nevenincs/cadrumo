"""CLI transport bridge for worker-owned ledger transaction allocation."""

from __future__ import annotations

from decimal import Decimal

import typer

from ...application.ledger.actions_common import display_decimal
from ...application.ledger.allocate_operation import (
    LEDGER_ALLOCATE_OPERATION_DEFINITION_ID,
    LedgerAllocateOperationResult,
    LedgerAllocateRequest,
)
from ...core.operations import profile_operation_subject
from .ledger_allocate_correlation import correlate_ledger_allocation
from .runtime_profile_binding import bound_profile_client
from .runtime_registered_operation import run_registered_operation


def run_ledger_allocate(
    ctx: typer.Context,
    *,
    transaction_id: str,
    business_pct: Decimal,
    category_id: str | None,
    usage_ratio_id: str | None,
    prorrata_reference: str | None,
    actor: str | None,
) -> LedgerAllocateOperationResult:
    """Run one exact-profile allocation and correlate its typed result and effect."""
    client = bound_profile_client(ctx)
    request = LedgerAllocateRequest(
        profile_id=client.profile_id,
        transaction_id=transaction_id,
        business_pct=display_decimal(business_pct),
        category_id=category_id,
        usage_ratio_id=usage_ratio_id,
        prorrata_reference=prorrata_reference,
        actor=actor if actor else None,
    )
    completed = run_registered_operation(
        client,
        request,
        definition_id=LEDGER_ALLOCATE_OPERATION_DEFINITION_ID,
        subject_ref=profile_operation_subject(str(client.profile_id)),
        result_type=LedgerAllocateOperationResult,
        request_version=1,
        result_version=1,
        timeout=120,
    )
    projection = completed.projection
    correlate_ledger_allocation(
        completed, client.profile_id, business_pct, transaction_id, category_id, usage_ratio_id, prorrata_reference
    )
    return projection
