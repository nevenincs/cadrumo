"""Canonical ledger classify fields for exact-profile classification."""

from __future__ import annotations

from ...application.ledger.classify_operation import (
    LedgerClassifyM210Options,
    LedgerClassifyOperationResult,
    LedgerClassifyPatch,
)
from ...application.ledger.transaction_projection import LedgerM210IncomeProjection, LedgerTransactionProjection
from ...domain.transactions.enums import BusinessClassification


def classification_selected_fields_match(
    *,
    patch: LedgerClassifyPatch,
    fields: tuple[str, ...],
    m210: LedgerClassifyM210Options | None,
    result: LedgerClassifyOperationResult,
) -> bool:
    """Correlate every selected classification fact the canonical action preserves."""
    transaction = result.transaction
    if transaction is None:
        return False
    business_classification = BusinessClassification(transaction.business_classification)
    business_bearing = business_classification in {
        BusinessClassification.BUSINESS,
        BusinessClassification.MIXED,
    }
    for field_name in fields:
        if field_name == "m210_income_classification":
            continue
        if not classification_selected_field_match(field_name, patch, transaction, result, business_bearing):
            return False
    if "m210_income_classification" in fields:
        actual_m210 = transaction.m210_income_classification
        if not business_bearing:
            return actual_m210 is None
        if m210 is None or actual_m210 is None:
            return False
        return classification_m210_fields_match(actual_m210, m210)
    return True


def classification_selected_field_match(
    field_name: str,
    patch: LedgerClassifyPatch,
    transaction: LedgerTransactionProjection,
    result: LedgerClassifyOperationResult,
    business_bearing: bool,
) -> bool:
    """Correlate one selected field using its canonical transaction or result owner."""
    requested = getattr(patch, field_name)
    if field_name in {
        "business_classification",
        "business_pct",
        "iva_category",
        "counterparty_country",
        "counterparty_identification_state",
    }:
        return bool(getattr(transaction, field_name) == requested)
    if field_name == "category_id":
        expected = classification_category_expected(patch, business_bearing)
        return transaction.category_id == expected
    if field_name in {"taxable_base", "iva_rate", "iva_amount", "irpf_category"}:
        expected = requested
        if not business_bearing:
            expected = None
        return bool(getattr(transaction, field_name) == expected)
    if field_name in {"deduction_fact_kind", "investment_asset_id"}:
        return bool(getattr(result, field_name) == requested)
    if field_name == "notes":
        return transaction.notes == (requested or "")
    return True


def classification_m210_fields_match(actual_m210: LedgerM210IncomeProjection, m210: LedgerClassifyM210Options) -> bool:
    """Keep all selected M210 answers and the original absence normalization."""
    expected_code = (m210.tipo_renta_code or "").strip()
    expected_gross = m210.gross_income_amount
    expected_rate = m210.applicable_rate
    expected_payer_mode = m210.payer_mode
    expected_payer_id = m210.payer_id or None
    expected_asset_id = m210.asset_or_right_id or None
    return not (
        actual_m210.official_tipo_renta_code != expected_code
        or actual_m210.gross_income_amount != expected_gross
        or actual_m210.applicable_rate != expected_rate
        or actual_m210.payer_mode != expected_payer_mode
        or actual_m210.payer_id != expected_payer_id
        or actual_m210.asset_or_right_id != expected_asset_id
    )


def classification_category_expected(patch: LedgerClassifyPatch, business_bearing: bool) -> str | None:
    """Normalize an explicitly selected category before excluding personal allocations."""
    category = patch.category_id
    expected = category.strip() or None if category is not None else None
    if not business_bearing:
        expected = None
    return expected
