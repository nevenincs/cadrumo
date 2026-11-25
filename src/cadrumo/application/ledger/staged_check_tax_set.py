"""Which tax fields a staged row's writer refuses or drops, so a change set for all leaves them out.

A transfer's writer refuses every tax field a cell can stage; a Personal write
drops the business figures and their share. The staged check serves both the
row-level reason and the exact fields, so no frontend keeps a copy of either rule.
"""

from __future__ import annotations

from typing import Final, TypeIs, get_args

from ...domain.transactions.classification_effects import fields_cleared_by_classification
from ...domain.transactions.enums import BusinessClassification, TransactionDirection
from .staged_check_contracts import StageFieldName, TaxSetSkip

TRANSFER_TAX_FIELDS: Final[tuple[StageFieldName, ...]] = (
    "business_pct",
    "category_id",
    "usage_ratio_id",
    "taxable_base",
    "iva_rate",
    "iva_amount",
    "iva_category",
    "irpf_category",
    "deduction_fact_kind",
    "investment_asset_id",
    "operation_date",
    "accrual_date",
)
"""What ``ManualLedgerTransactionCommand`` refuses on a transfer, of what a cell can stage."""

TRANSFER_LOCKED_FIELDS: Final[tuple[StageFieldName, ...]] = TRANSFER_TAX_FIELDS
"""What cannot be edited on a transfer: the writer refuses every one of them there."""


def tax_set_skip(
    direction: TransactionDirection | None, classification: BusinessClassification | None
) -> TaxSetSkip | None:
    """Why a change set for all leaves this row's tax fields out, if it does."""
    if direction is TransactionDirection.INTERNAL_TRANSFER:
        return "transfer"
    if classification is BusinessClassification.PERSONAL:
        return "personal"
    return None


def _is_stage_field(name: object) -> TypeIs[StageFieldName]:
    return name in get_args(StageFieldName)


def tax_set_skipped_fields(
    direction: TransactionDirection | None, classification: BusinessClassification | None
) -> tuple[StageFieldName, ...]:
    """The fields a change set for all leaves out on this row: what its writer refuses or drops there."""
    if direction is TransactionDirection.INTERNAL_TRANSFER:
        return TRANSFER_LOCKED_FIELDS
    if classification is BusinessClassification.PERSONAL:
        dropped = fields_cleared_by_classification(classification)
        return tuple(field for field in get_args(StageFieldName) if _is_stage_field(field) and field in dropped)
    return ()


__all__ = ["TRANSFER_LOCKED_FIELDS", "TRANSFER_TAX_FIELDS", "tax_set_skip", "tax_set_skipped_fields"]
