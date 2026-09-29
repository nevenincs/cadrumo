"""Closed registered-operation projections of canonical ledger read facts."""

from __future__ import annotations

from decimal import Decimal, InvalidOperation

from pydantic import BaseModel, Field, field_validator

from ...core.identity.transaction_ids import TransactionId
from ...core.models import STRICT_FROZEN_HIDDEN_INPUT_CONFIG
from ..review.filter import LedgerReviewStatus
from .models import LedgerTransactionPayload


class LedgerM210IncomeProjection(BaseModel):
    """Already-admitted M210 facts without frontend registry revalidation."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    official_tipo_renta_code: str = Field(min_length=2, max_length=2)
    gross_income_amount: str
    applicable_rate: str
    payer_mode: str
    payer_id: str | None
    asset_or_right_id: str | None

    @field_validator("gross_income_amount", "applicable_rate")
    @classmethod
    def _finite_decimal(cls, value: str) -> str:
        try:
            parsed = Decimal(value)
        except InvalidOperation:
            raise ValueError("income projection requires a finite decimal string") from None
        if not parsed.is_finite():
            raise ValueError("income projection requires a finite decimal string")
        return value


class LedgerTransactionProjection(BaseModel):
    """The existing transaction payload with a strict JSON-stable M210 projection.

    Financial values are copied from canonical read facts, never recomputed.
    Domain reconstruction and registry validation remain inside the worker;
    frontends receive only the admitted display and audit facts.
    """

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    transaction_id: TransactionId
    date: str
    booked_date: str
    value_date: str | None
    amount: str
    currency: str
    direction: str
    counterparty: str
    description: str
    business_classification: str
    business_pct: str | None
    category_id: str | None
    taxable_base: str | None
    iva_rate: str | None
    iva_amount: str | None
    iva_category: str | None
    counterparty_country: str | None
    counterparty_identification_state: str | None
    irpf_category: str | None
    m210_income_classification: LedgerM210IncomeProjection | None
    usage_ratio_id: str | None
    prorrata_reference: str | None
    purchase_invoice_evidence_id: str | None
    invoice_id: str | None
    attachment_ids: tuple[str, ...]
    notes: str
    lifecycle_state: str
    classified_by: str
    classified_at: str | None
    classification_reason: str
    classification_confidence: str | None
    source_jurisdiction: str | None
    value_in_eur: str | None
    fx_rate: str | None
    created_at: str
    modified_at: str

    @classmethod
    def from_payload(cls, payload: LedgerTransactionPayload) -> LedgerTransactionProjection:
        """Copy the canonical JSON meaning, preserving absence and decimal text."""
        return cls.model_validate_json(payload.model_dump_json())


class LedgerTransactionReviewProjection(BaseModel):
    """A reviewed transaction with the group used by canonical list ordering."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    transaction: LedgerTransactionProjection
    review_status: LedgerReviewStatus
    group_label: str | None
