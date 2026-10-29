"""Renta ledger result and refusal models."""

from __future__ import annotations

from collections.abc import Mapping
from decimal import Decimal
from enum import StrEnum

from pydantic import BaseModel, Field

from ...core.casilla_id import CasillaId
from ...core.filing_year import FilingYear
from ...core.identity.transaction_ids import TransactionId
from ...core.models import STRICT_FROZEN_CONFIG as _STRICT_FROZEN
from ...core.prose_elision import IssueDetail
from ...domain.renta.ledger_expenses import (
    RentaDeductibleExpenseObservation,
)
from . import _shared_issue_reasons
from ._models import LedgerAggregationResultBase


class RentaLedgerAggregationIssueReason(StrEnum):
    """Machine-readable reasons why a ledger row did not produce an observation.

    The five upstream filter rejections (``UNSUPPORTED_DIRECTION``,
    ``UNSUPPORTED_CURRENCY``, ``UNCLASSIFIED_BUSINESS_STATE``,
    ``PERSONAL_TRANSACTION``, ``OUTSIDE_PERIOD``) are shared with
    :class:`~application.aggregation.iva_ledger.IvaLedgerAggregationIssueReason`
    through :mod:`._shared_issue_reasons`. ``UNSUPPORTED_PERIOD`` is a
    Renta-only refusal raised against quarter-level requests; the
    remaining values describe Renta-specific deductibility checks.
    """

    UNSUPPORTED_PERIOD = "unsupported_period"
    UNSUPPORTED_DIRECTION = _shared_issue_reasons.UNSUPPORTED_DIRECTION
    UNSUPPORTED_CURRENCY = _shared_issue_reasons.UNSUPPORTED_CURRENCY
    UNCLASSIFIED_BUSINESS_STATE = _shared_issue_reasons.UNCLASSIFIED_BUSINESS_STATE
    ACTIVITY_MARKED_PENDING_ANNUAL_REVIEW = "activity_marked_pending_annual_review"
    """An actividad-marked expense the quarterly M130 accepts but the annual declaration holds for review.

    Narrower than ``UNCLASSIFIED_BUSINESS_STATE``: the row carries an explicit
    ``actividad_economica`` IRPF category, so it is not unclassified -- it is
    awaiting the business-classification review the filing-grade annual
    projection requires. Naming it separately tells the operator that the same
    row already fed a pago fraccionado and what action clears it.
    """
    PERSONAL_TRANSACTION = _shared_issue_reasons.PERSONAL_TRANSACTION
    MISSING_CATEGORY = "missing_category"
    UNKNOWN_CATEGORY = _shared_issue_reasons.UNKNOWN_CATEGORY
    MISSING_CATEGORY_PROFILE = _shared_issue_reasons.MISSING_CATEGORY_PROFILE
    OUTSIDE_PERIOD = _shared_issue_reasons.OUTSIDE_PERIOD
    MISSING_PURCHASE_INVOICE_EVIDENCE = "missing_purchase_invoice_evidence"
    UNSUPPORTED_PURCHASE_INVOICE_EVIDENCE_KIND = "unsupported_purchase_invoice_evidence_kind"
    PURCHASE_INVOICE_EVIDENCE_BUCKET_MISMATCH = "purchase_invoice_evidence_bucket_mismatch"
    PURCHASE_INVOICE_EVIDENCE_LINK_MISMATCH = "purchase_invoice_evidence_link_mismatch"
    PARTIAL_OR_MULTI_TRANSACTION_PURCHASE_INVOICE_EVIDENCE = "partial_or_multi_transaction_purchase_invoice_evidence"
    AMOUNT_MISMATCH = "amount_mismatch"
    INVALID_LEDGER_FACT = _shared_issue_reasons.INVALID_LEDGER_FACT
    INELIGIBLE_DEDUCTIBILITY = _shared_issue_reasons.INELIGIBLE_DEDUCTIBILITY
    EXCLUSIVE_USE_REQUIRED = _shared_issue_reasons.EXCLUSIVE_USE_REQUIRED
    MISSING_OWNERSHIP_SHARE = _shared_issue_reasons.MISSING_OWNERSHIP_SHARE
    ASSET_REGISTER_REQUIRED = _shared_issue_reasons.ASSET_REGISTER_REQUIRED
    REGION_UNDECLARED_FOR_OVERRIDE = _shared_issue_reasons.REGION_UNDECLARED_FOR_OVERRIDE


class RentaLedgerAggregationIssue(BaseModel):
    """Traceable exclusion emitted while aggregating ledger rows."""

    model_config = _STRICT_FROZEN

    transaction_id: TransactionId
    purchase_invoice_evidence_id: str | None = Field(default=None, min_length=1, max_length=128)
    category_id: str | None = Field(default=None, min_length=1, max_length=128)
    reason: RentaLedgerAggregationIssueReason
    detail: IssueDetail


class RentaLedgerExpenseAggregation(
    LedgerAggregationResultBase[RentaDeductibleExpenseObservation, RentaLedgerAggregationIssue],
):
    """First-slice Renta observations plus binding-ready casilla totals.

    Carries no ``out_of_window_summary``: this annual first-slice aggregation
    has no repository-backed date partition, unlike the base's four other
    known subclasses -- deliberately not declared here (see
    :class:`~._models.LedgerAggregationResultBase`).
    """

    profile_year: FilingYear

    @property
    def casilla_values(self) -> Mapping[CasillaId, Decimal]:
        """Return the frozen mapping of binding-ready casilla totals."""
        return self.casilla_aggregation.casilla_values
