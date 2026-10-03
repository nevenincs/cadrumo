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
from ...application.runtime.contracts import RuntimeRefusalCode
from ...core.operations import OperationEffect, OperationTerminalCondition, profile_operation_subject
from ...domain.transactions.enums import BusinessClassification
from ...domain.transactions.model_validation import classification_for_business_share
from .runtime_profile_binding import bound_profile_client
from .runtime_registered_operation import run_registered_operation, submitted_operation_error


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
    expected_classification = classification_for_business_share(business_pct)
    expected_share = display_decimal(business_pct) if expected_classification is BusinessClassification.MIXED else None
    expected_effect = OperationEffect.UPDATED if projection.bucket_event_ids else OperationEffect.NONE
    expected_usage_ratio_id = (
        None
        if expected_classification is not BusinessClassification.MIXED or usage_ratio_id is None
        else usage_ratio_id.strip() or None
    )
    expected_prorrata_reference = (
        None
        if expected_classification is BusinessClassification.PERSONAL or prorrata_reference is None
        else prorrata_reference.strip() or None
    )
    expected_category_id = (
        None
        if expected_classification is BusinessClassification.PERSONAL or category_id is None
        else category_id.strip()
    )
    prefix = transaction_id.strip().lower()
    invalid = (
        completed.terminal_condition is not OperationTerminalCondition.SUCCEEDED
        or completed.refusal_code is not None
        or completed.effect is not expected_effect
        or projection.profile_id != client.profile_id
        or not projection.transaction.transaction_id.startswith(prefix)
        or projection.transaction.business_classification != expected_classification.value
        or projection.transaction.business_pct != expected_share
        or (category_id is not None and projection.transaction.category_id != expected_category_id)
        or (usage_ratio_id is not None and projection.transaction.usage_ratio_id != expected_usage_ratio_id)
        or (prorrata_reference is not None and projection.transaction.prorrata_reference != expected_prorrata_reference)
    )
    if invalid:
        raise submitted_operation_error(
            completed.operation_id,
            RuntimeRefusalCode.INVALID_FRAME.value,
            terminal_condition=completed.terminal_condition,
            effect=completed.effect,
            refusal_code=completed.refusal_code,
        )
    return projection


__all__ = ["run_ledger_allocate"]
