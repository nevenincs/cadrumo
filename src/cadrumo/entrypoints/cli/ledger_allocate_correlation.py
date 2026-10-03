"""Exact-profile receipt and selected-field correlation for ledger allocation."""

from __future__ import annotations

from decimal import Decimal
from uuid import UUID

from ...application.ledger.actions_common import display_decimal
from ...application.ledger.allocate_operation import (
    LedgerAllocateOperationResult,
)
from ...core.operations import OperationEffect, OperationTerminalCondition
from ...domain.transactions.enums import BusinessClassification
from ...domain.transactions.model_validation import classification_for_business_share
from .registered_operation_contracts import RegisteredOperationCompletion
from .registered_operation_errors import invalid_completion_error


def allocation_fields_mismatch(
    completed: RegisteredOperationCompletion[LedgerAllocateOperationResult],
    projection: LedgerAllocateOperationResult,
    profile_id: UUID,
    expected_effect: OperationEffect,
    prefix: str,
    expected_classification: BusinessClassification,
    expected_share: str | None,
    category_id: str | None,
    usage_ratio_id: str | None,
    prorrata_reference: str | None,
    expected_category_id: str | None,
    expected_usage_ratio_id: str | None,
    expected_prorrata_reference: str | None,
) -> bool:
    """Allocation fields mismatch."""
    invalid = allocation_receipt_mismatch(completed, profile_id, expected_effect) or (
        not projection.transaction.transaction_id.startswith(prefix)
        or projection.transaction.business_classification != expected_classification.value
        or projection.transaction.business_pct != expected_share
        or (category_id is not None and projection.transaction.category_id != expected_category_id)
        or (usage_ratio_id is not None and projection.transaction.usage_ratio_id != expected_usage_ratio_id)
        or (prorrata_reference is not None and projection.transaction.prorrata_reference != expected_prorrata_reference)
    )
    return invalid


def correlate_ledger_allocation(
    completed: RegisteredOperationCompletion[LedgerAllocateOperationResult],
    profile_id: UUID,
    business_pct: Decimal,
    transaction_id: str,
    category_id: str | None,
    usage_ratio_id: str | None,
    prorrata_reference: str | None,
) -> None:
    """Correlate ledger allocation."""
    projection = completed.projection
    expected_classification = classification_for_business_share(business_pct)
    expected_share = display_decimal(business_pct) if expected_classification is BusinessClassification.MIXED else None
    expected_effect = OperationEffect.UPDATED if projection.bucket_event_ids else OperationEffect.NONE
    expected_usage_ratio_id = allocation_usage_ratio(expected_classification, usage_ratio_id)
    expected_prorrata_reference = allocation_prorrata_reference(expected_classification, prorrata_reference)
    expected_category_id = allocation_category(expected_classification, category_id)
    prefix = transaction_id.strip().lower()
    invalid = allocation_fields_mismatch(
        completed,
        projection,
        profile_id,
        expected_effect,
        prefix,
        expected_classification,
        expected_share,
        category_id,
        usage_ratio_id,
        prorrata_reference,
        expected_category_id,
        expected_usage_ratio_id,
        expected_prorrata_reference,
    )
    if invalid:
        raise invalid_completion_error(completed)


def allocation_usage_ratio(expected_classification: BusinessClassification, usage_ratio_id: str | None) -> str | None:
    """Normalize the requested usage ratio id for the admitted classification."""
    return (
        None
        if expected_classification is not BusinessClassification.MIXED or usage_ratio_id is None
        else usage_ratio_id.strip() or None
    )


def allocation_prorrata_reference(
    expected_classification: BusinessClassification, prorrata_reference: str | None
) -> str | None:
    """Normalize the requested prorrata reference for the admitted classification."""
    return (
        None
        if expected_classification is BusinessClassification.PERSONAL or prorrata_reference is None
        else prorrata_reference.strip() or None
    )


def allocation_category(expected_classification: BusinessClassification, category_id: str | None) -> str | None:
    """Normalize the requested category id for the admitted classification."""
    return (
        None
        if expected_classification is BusinessClassification.PERSONAL or category_id is None
        else category_id.strip()
    )


def allocation_receipt_mismatch(
    completed: RegisteredOperationCompletion[LedgerAllocateOperationResult],
    profile_id: UUID,
    expected_effect: OperationEffect,
) -> bool:
    """Correlate the actual successful receipt to the profile and persisted effect."""
    projection = completed.projection
    return (
        completed.terminal_condition is not OperationTerminalCondition.SUCCEEDED
        or completed.refusal_code is not None
        or completed.effect is not expected_effect
        or projection.profile_id != profile_id
    )
