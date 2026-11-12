"""Whether a settled classification kept what its request selected.

The classification writer drops what the resulting classification does not keep,
so a correlation reads that from the same owner the writer does. Every frontend
that submits a classification correlates its settled result here.
"""

from __future__ import annotations

from ...domain.transactions.classification_effects import fields_cleared_by_classification
from ...domain.transactions.enums import BusinessClassification, takes_business_share
from .classify_requests import LedgerClassifyM210Options, LedgerClassifyPatch
from .classify_result_contracts import LedgerClassifyOperationResult
from .transaction_projection import LedgerM210IncomeProjection

_RESULT_ONLY_FIELDS = frozenset({"deduction_fact_kind", "exemption_article", "investment_asset_id", "iva_vehicle_use"})


def _expected_value(field_name: str, patch: LedgerClassifyPatch, cleared: frozenset[str]) -> object:
    """Return what the writer stores for one selected field of ``patch``."""
    if field_name in cleared:
        return None
    requested = getattr(patch, field_name)
    if field_name == "category_id":
        return (requested.strip() or None) if requested is not None else None
    if field_name == "notes":
        return requested or ""
    return requested


def _m210_fields_match(actual: LedgerM210IncomeProjection, m210: LedgerClassifyM210Options) -> bool:
    return (
        actual.official_tipo_renta_code == (m210.tipo_renta_code or "").strip()
        and actual.gross_income_amount == m210.gross_income_amount
        and actual.applicable_rate == m210.applicable_rate
        and actual.payer_mode == m210.payer_mode
        and actual.payer_id == (m210.payer_id or None)
        and actual.asset_or_right_id == (m210.asset_or_right_id or None)
    )


def _plain_fields_match(
    *,
    patch: LedgerClassifyPatch,
    fields: tuple[str, ...],
    result: LedgerClassifyOperationResult,
    cleared: frozenset[str],
) -> bool:
    """Return whether each selected field, other than the M210 income, holds what the writer stores."""
    transaction = result.transaction
    for field_name in fields:
        if field_name == "m210_income_classification":
            continue
        owner = result if field_name in _RESULT_ONLY_FIELDS else transaction
        if getattr(owner, field_name) != _expected_value(field_name, patch, cleared):
            return False
    return True


def classification_selected_fields_match(
    *,
    patch: LedgerClassifyPatch,
    fields: tuple[str, ...],
    m210: LedgerClassifyM210Options | None,
    result: LedgerClassifyOperationResult,
) -> bool:
    """Return whether the settled row carries every selected fact the writer keeps."""
    transaction = result.transaction
    if transaction is None:
        return False
    classification = BusinessClassification(transaction.business_classification)
    cleared = fields_cleared_by_classification(classification)
    expected_share = patch.business_pct if takes_business_share(classification) else None
    if transaction.business_pct != expected_share:
        return False
    if not _plain_fields_match(patch=patch, fields=fields, result=result, cleared=cleared):
        return False
    if "m210_income_classification" not in fields:
        return True
    actual_m210 = transaction.m210_income_classification
    if "m210_income_classification" in cleared:
        return actual_m210 is None
    return m210 is not None and actual_m210 is not None and _m210_fields_match(actual_m210, m210)


__all__ = ["classification_selected_fields_match"]
