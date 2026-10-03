"""Canonical ledger classify inputs for exact-profile classification."""

from __future__ import annotations

from decimal import Decimal
from enum import StrEnum
from typing import cast

from ...application.ledger.actions_common import display_decimal
from ...application.ledger.classify_operation import (
    LedgerClassifyM210Options,
    LedgerClassifyPatchField,
)


def classification_m210_selection(
    patch_fields: tuple[LedgerClassifyPatchField, ...],
    m210_tipo_renta_code: str | None,
    m210_gross_income_amount: Decimal | None,
    m210_applicable_rate: Decimal | None,
    m210_payer_mode: str | None,
    m210_payer_id: str | None,
    m210_asset_or_right_id: str | None,
) -> tuple[LedgerClassifyM210Options | None, tuple[LedgerClassifyPatchField, ...]]:
    """Classification m210 selection."""
    raw_m210 = (
        m210_tipo_renta_code,
        m210_gross_income_amount,
        m210_applicable_rate,
        m210_payer_mode,
        m210_payer_id,
        m210_asset_or_right_id,
    )
    m210 = None
    m210_answers_requested = any(value is not None for value in raw_m210[:4])
    if any(value is not None for value in raw_m210):
        m210 = LedgerClassifyM210Options(
            tipo_renta_code=m210_tipo_renta_code,
            gross_income_amount=(
                display_decimal(m210_gross_income_amount) if m210_gross_income_amount is not None else None
            ),
            applicable_rate=display_decimal(m210_applicable_rate) if m210_applicable_rate is not None else None,
            payer_mode=m210_payer_mode,
            payer_id=m210_payer_id,
            asset_or_right_id=m210_asset_or_right_id,
        )
    selected_fields = set[LedgerClassifyPatchField](patch_fields)
    if m210_answers_requested:
        selected_fields.add(cast(LedgerClassifyPatchField, "m210_income_classification"))
    selected_patch_fields = tuple(sorted(selected_fields))
    return m210, selected_patch_fields


def classification_wire_value(value: object) -> object:
    """Render one validated patch value as bounded canonical JSON text."""
    if value is None:
        return None
    if isinstance(value, Decimal):
        return display_decimal(value)
    if isinstance(value, StrEnum):
        return value.value
    return value
