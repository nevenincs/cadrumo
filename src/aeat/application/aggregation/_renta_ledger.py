"""Repository-backed Renta expense aggregation from ledger catalogues.

Used by: :mod:`~._service` (per-modelo aggregation service) for Modelo 100 expense aggregation.

The main entry point :func:`aggregate_renta_ledger_expenses_from_repositories`
loads both a :class:`~aeat.domain.transactions.TransactionCatalogue`
via :class:`~aeat.domain.transactions.TransactionCatalogueRepository` and an
:class:`~aeat.domain.invoices.InvoiceCatalogue` via
:class:`~aeat.domain.invoices.InvoiceCatalogueRepository` from the
active bucket and feeds them to :func:`aggregate_renta_ledger_expenses`.

Related: :mod:`~._iva_ledger`, :mod:`~._renta_income_ledger` for similar pipelines.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import date
from decimal import Decimal
from enum import StrEnum
from typing import Self

from pydantic import BaseModel, Field, field_serializer, field_validator, model_validator

from ...core import STRICT_FROZEN_CONFIG as _STRICT_FROZEN
from ...core import Modelo
from ...core.resources import resources
from ...domain.categories import CategoryProfile, SpendingCategory
from ...domain.invoices import (
    InvoiceCatalogue,
    InvoiceCatalogueRepository,
    InvoiceCatalogueRepositoryProtocol,
)
from ...domain.iva import InvoiceKind
from ...domain.renta import (
    RENTA_100_FIRST_SLICE_EXPENSE_CASILLAS,
    RentaDeductibilityContext,
    RentaDeductibilityStatus,
    RentaDeductibleExpenseFact,
    RentaDeductibleExpenseObservation,
    RentaExpenseDirection,
    build_renta_deductible_expense_observation,
    evaluate_renta_deductibility,
    normalize_spending_category,
)
from ...domain.transactions import (
    BusinessClassification,
    Transaction,
    TransactionCatalogue,
    TransactionCatalogueRepository,
    TransactionCatalogueRepositoryProtocol,
    TransactionDirection,
    TransactionLifecycleState,
)
from . import _shared_issue_reasons
from ._business_proportion import business_proportion
from ._currency_predicates import effective_eur_amount, is_non_eur_without_conversion
from ._errors import AggregationPeriodError, AggregationValidationError, t
from ._models import CasillaAggregation, CasillaProvenance, Period, PeriodKind

_LEDGER_CATALOGUE_ID = "ledger"


class RentaLedgerAggregationIssueReason(StrEnum):
    """Machine-readable reasons why a ledger row did not produce an observation.

    The five upstream filter rejections (``UNSUPPORTED_DIRECTION``,
    ``UNSUPPORTED_CURRENCY``, ``UNCLASSIFIED_BUSINESS_STATE``,
    ``PERSONAL_TRANSACTION``, ``OUTSIDE_PERIOD``) are shared with
    :class:`aeat.application.aggregation._iva_ledger.IvaLedgerAggregationIssueReason`
    through :mod:`._shared_issue_reasons`. ``UNSUPPORTED_PERIOD`` is a
    Renta-only refusal raised against quarter-level requests; the
    remaining values describe Renta-specific deductibility checks.
    """

    UNSUPPORTED_PERIOD = "unsupported_period"
    UNSUPPORTED_DIRECTION = _shared_issue_reasons.UNSUPPORTED_DIRECTION
    UNSUPPORTED_CURRENCY = _shared_issue_reasons.UNSUPPORTED_CURRENCY
    UNCLASSIFIED_BUSINESS_STATE = _shared_issue_reasons.UNCLASSIFIED_BUSINESS_STATE
    PERSONAL_TRANSACTION = _shared_issue_reasons.PERSONAL_TRANSACTION
    MISSING_CATEGORY = "missing_category"
    UNKNOWN_CATEGORY = "unknown_category"
    CATEGORY_OUTSIDE_FIRST_SLICE = "category_outside_first_slice"
    MISSING_CATEGORY_PROFILE = "missing_category_profile"
    OUTSIDE_PERIOD = _shared_issue_reasons.OUTSIDE_PERIOD
    MISSING_PURCHASE_INVOICE_EVIDENCE = "missing_purchase_invoice_evidence"
    UNSUPPORTED_PURCHASE_INVOICE_EVIDENCE_KIND = "unsupported_purchase_invoice_evidence_kind"
    PURCHASE_INVOICE_EVIDENCE_BUCKET_MISMATCH = "purchase_invoice_evidence_bucket_mismatch"
    PURCHASE_INVOICE_EVIDENCE_LINK_MISMATCH = "purchase_invoice_evidence_link_mismatch"
    PARTIAL_OR_MULTI_TRANSACTION_PURCHASE_INVOICE_EVIDENCE = "partial_or_multi_transaction_purchase_invoice_evidence"
    AMOUNT_MISMATCH = "amount_mismatch"
    INVALID_LEDGER_FACT = "invalid_ledger_fact"
    INELIGIBLE_DEDUCTIBILITY = "ineligible_deductibility"


class RentaLedgerAggregationIssue(BaseModel):
    """Traceable exclusion emitted while aggregating ledger rows."""

    model_config = _STRICT_FROZEN

    transaction_id: str = Field(min_length=1, max_length=128)
    purchase_invoice_evidence_id: str | None = Field(default=None, min_length=1, max_length=128)
    category_id: str | None = Field(default=None, min_length=1, max_length=128)
    reason: RentaLedgerAggregationIssueReason
    detail: str = Field(min_length=1, max_length=512)


class _PurchaseInvoiceEvidencePayload(BaseModel):
    """Typed enrichment fields copied from a reconciled linked invoice."""

    model_config = _STRICT_FROZEN

    invoice_issue_date: date | None = None
    taxable_base: Decimal | None = None
    iva_amount: Decimal | None = None


class RentaLedgerExpenseAggregation(BaseModel):
    """First-slice Renta observations plus binding-ready casilla totals."""

    model_config = _STRICT_FROZEN

    modelo: str = Field(min_length=1, max_length=16)
    period: Period
    profile_year: int = Field(ge=2000, le=2099)
    observations: Sequence[RentaDeductibleExpenseObservation] = Field(default_factory=tuple)
    issues: Sequence[RentaLedgerAggregationIssue] = Field(default_factory=tuple)
    casilla_aggregation: CasillaAggregation

    @field_validator("observations")
    @classmethod
    def _freeze_observations(
        cls,
        value: Sequence[RentaDeductibleExpenseObservation],
    ) -> tuple[RentaDeductibleExpenseObservation, ...]:
        return tuple(value)

    @field_validator("issues")
    @classmethod
    def _freeze_issues(
        cls,
        value: Sequence[RentaLedgerAggregationIssue],
    ) -> tuple[RentaLedgerAggregationIssue, ...]:
        return tuple(value)

    @model_validator(mode="after")
    def _validate_casilla_period(self) -> Self:
        if self.casilla_aggregation.modelo != self.modelo:
            raise AggregationValidationError(t("aggregation.renta_ledger.errors.modelo_mismatch"))
        if self.casilla_aggregation.period != self.period:
            raise AggregationValidationError(t("aggregation.renta_ledger.errors.period_mismatch"))
        return self

    @property
    def casilla_values(self) -> Mapping[str, Decimal]:
        """Return the frozen mapping of binding-ready casilla totals."""
        return self.casilla_aggregation.casilla_values

    @field_serializer("observations")
    def _serialize_observations(
        self,
        value: Sequence[RentaDeductibleExpenseObservation],
    ) -> tuple[RentaDeductibleExpenseObservation, ...]:
        return tuple(value)

    @field_serializer("issues")
    def _serialize_issues(
        self,
        value: Sequence[RentaLedgerAggregationIssue],
    ) -> tuple[RentaLedgerAggregationIssue, ...]:
        return tuple(value)


def aggregate_renta_ledger_expenses_from_repositories(
    *,
    bucket_id: str,
    period: Period,
    transaction_repository: TransactionCatalogueRepositoryProtocol | None = None,
    invoice_repository: InvoiceCatalogueRepositoryProtocol | None = None,
    profile_year: int | None = None,
    usage_ratios: Mapping[SpendingCategory, Decimal] | None = None,
    activity_key: str = "default",
    modelo: str = Modelo.M100.value,
) -> RentaLedgerExpenseAggregation:
    """Load persisted catalogues and aggregate first-slice Renta expenses.

    Returns a :class:`RentaLedgerExpenseAggregation`.
    """
    repository = transaction_repository or TransactionCatalogueRepository(bucket_id=bucket_id)
    if repository.bucket_id != bucket_id:
        raise AggregationValidationError(
            t("aggregation.renta_ledger.errors.bucket_mismatch"),
            context={"bucket_id": bucket_id, "repository_bucket_id": repository.bucket_id},
        )
    transactions = repository.load()
    invoices_repository = invoice_repository or InvoiceCatalogueRepository(bucket_id=bucket_id)
    if invoices_repository.bucket_id != bucket_id:
        raise AggregationValidationError(
            t("aggregation.renta_ledger.errors.invoice_bucket_mismatch"),
            context={"bucket_id": bucket_id, "repository_bucket_id": invoices_repository.bucket_id},
        )
    invoices = invoices_repository.load()
    return aggregate_renta_ledger_expenses(
        transactions,
        invoices,
        bucket_id=bucket_id,
        period=period,
        profile_year=profile_year,
        usage_ratios=usage_ratios,
        activity_key=activity_key,
        modelo=modelo,
    )


def aggregate_renta_ledger_expenses(
    transactions: TransactionCatalogue,
    invoices: InvoiceCatalogue,
    *,
    bucket_id: str,
    period: Period,
    profile_year: int | None = None,
    usage_ratios: Mapping[SpendingCategory, Decimal] | None = None,
    activity_key: str = "default",
    modelo: str = Modelo.M100.value,
) -> RentaLedgerExpenseAggregation:
    """Aggregate classified ledger transactions into Renta expense observations.

    Args:
        transactions: The :class:`TransactionCatalogue` supplying active ledger entries.
        invoices: The :class:`InvoiceCatalogue` used for invoice-linked deductibility checks.
        bucket_id: Activity bucket identifier for scoping the aggregation.
        period: Filing period as a typed :class:`Period` instance.
        profile_year: Optional category-profile year override; defaults to the
            ``period.year`` when ``None``.
        usage_ratios: Optional per-:class:`SpendingCategory` business-use ratio
            overrides applied before deductibility calculation.
        activity_key: Activity identifier carried through to the produced
            observations' provenance; defaults to ``"default"``.
        modelo: Modelo identifier (``"100"`` IRPF or ``"130"`` pagos
            fraccionados) selecting the per-modelo deductibility rules.

    Returns a :class:`RentaLedgerExpenseAggregation` containing the accepted
    observations, exclusion issues, and binding-ready casilla totals.
    """
    resolved_period = _resolve_annual_period(period)
    resolved_profile_year = profile_year if profile_year is not None else resolved_period.year
    profiles = resources().category_profiles.get(resolved_profile_year)
    context = RentaDeductibilityContext(
        profile_year=resolved_profile_year,
        usage_ratios=dict(usage_ratios or {}),
    )
    observations: list[RentaDeductibleExpenseObservation] = []
    issues: list[RentaLedgerAggregationIssue] = []
    for transaction in transactions.values():
        if transaction.lifecycle_state is not TransactionLifecycleState.ACTIVE:
            continue
        outcome = _classify_renta_transaction(
            transaction,
            invoices=invoices,
            bucket_id=bucket_id,
            resolved_period=resolved_period,
            resolved_profile_year=resolved_profile_year,
            profiles=profiles,
            context=context,
            activity_key=activity_key,
        )
        if isinstance(outcome, RentaLedgerAggregationIssue):
            issues.append(outcome)
        else:
            observations.append(outcome)

    casilla_aggregation = _casilla_aggregation(resolved_period, observations, modelo=modelo)
    return RentaLedgerExpenseAggregation(
        modelo=modelo,
        period=resolved_period,
        profile_year=resolved_profile_year,
        observations=tuple(observations),
        issues=tuple(issues),
        casilla_aggregation=casilla_aggregation,
    )


def _classify_renta_transaction(
    transaction: Transaction,
    *,
    invoices: InvoiceCatalogue,
    bucket_id: str,
    resolved_period: Period,
    resolved_profile_year: int,
    profiles: Mapping[SpendingCategory, CategoryProfile],
    context: RentaDeductibilityContext,
    activity_key: str,
) -> RentaDeductibleExpenseObservation | RentaLedgerAggregationIssue:
    """Filter + classify one ledger transaction against the Renta-expense pipeline.

    Returns either a typed :class:`RentaDeductibleExpenseObservation`
    (the transaction survives every gate and is eligible) or a typed
    :class:`RentaLedgerAggregationIssue` (any gate rejects it). The
    twelve original early-return branches each project to a typed
    issue with their dedicated reason code; the eligible path returns
    the constructed observation.
    """
    transaction_id = transaction.transaction_id
    purchase_invoice_evidence_id = transaction.purchase_invoice_evidence_id
    category_id = transaction.category_id

    direction = _renta_direction_for(transaction.direction, purchase_invoice_evidence_id)
    if direction is None:
        return RentaLedgerAggregationIssue(
            transaction_id=transaction_id,
            purchase_invoice_evidence_id=purchase_invoice_evidence_id,
            category_id=category_id,
            reason=RentaLedgerAggregationIssueReason.UNSUPPORTED_DIRECTION,
            detail=f"transaction direction {transaction.direction.value!r} is not a Renta expense flow",
        )
    if is_non_eur_without_conversion(transaction):
        return RentaLedgerAggregationIssue(
            transaction_id=transaction_id,
            purchase_invoice_evidence_id=purchase_invoice_evidence_id,
            category_id=category_id,
            reason=RentaLedgerAggregationIssueReason.UNSUPPORTED_CURRENCY,
            detail=f"transaction currency {transaction.raw.currency!r} is not supported for Renta expenses",
        )
    # Use the EUR-projected amount for the business gate so a non-EUR row
    # that passed the is_non_eur_without_conversion check (because
    # value_in_eur is set) contributes its pre-converted EUR equivalent
    # rather than its raw foreign-currency amount.  EUR rows are unaffected:
    # their value_in_eur is None and effective_eur_amount falls back to
    # raw.amount.
    eur_amount = effective_eur_amount(transaction)
    business_amount = _business_amount(
        eur_amount,
        transaction.business_classification,
        transaction.business_pct,
    )
    if business_amount is None:
        reason = (
            RentaLedgerAggregationIssueReason.PERSONAL_TRANSACTION
            if transaction.business_classification is BusinessClassification.PERSONAL
            else RentaLedgerAggregationIssueReason.UNCLASSIFIED_BUSINESS_STATE
        )
        return RentaLedgerAggregationIssue(
            transaction_id=transaction_id,
            purchase_invoice_evidence_id=purchase_invoice_evidence_id,
            category_id=category_id,
            reason=reason,
            detail=(
                f"business classification {transaction.business_classification.value!r} cannot feed Renta expenses"
            ),
        )
    if category_id is None:
        return RentaLedgerAggregationIssue(
            transaction_id=transaction_id,
            purchase_invoice_evidence_id=purchase_invoice_evidence_id,
            category_id=category_id,
            reason=RentaLedgerAggregationIssueReason.MISSING_CATEGORY,
            detail="classified expense transaction has no ledger category",
        )
    try:
        category = normalize_spending_category(category_id)
    except ValueError:
        return RentaLedgerAggregationIssue(
            transaction_id=transaction_id,
            purchase_invoice_evidence_id=purchase_invoice_evidence_id,
            category_id=category_id,
            reason=RentaLedgerAggregationIssueReason.UNKNOWN_CATEGORY,
            detail=f"ledger category {category_id!r} is not in the spending taxonomy",
        )
    if category not in RENTA_100_FIRST_SLICE_EXPENSE_CASILLAS:
        return RentaLedgerAggregationIssue(
            transaction_id=transaction_id,
            purchase_invoice_evidence_id=purchase_invoice_evidence_id,
            category_id=category_id,
            reason=RentaLedgerAggregationIssueReason.CATEGORY_OUTSIDE_FIRST_SLICE,
            detail=f"category {category.value!r} has no first-slice Modelo 100 casilla mapping",
        )
    profile = profiles.get(category)
    if profile is None:
        return RentaLedgerAggregationIssue(
            transaction_id=transaction_id,
            purchase_invoice_evidence_id=purchase_invoice_evidence_id,
            category_id=category_id,
            reason=RentaLedgerAggregationIssueReason.MISSING_CATEGORY_PROFILE,
            detail=f"category {category.value!r} has no profile for {resolved_profile_year}",
        )
    evidence_payload = _purchase_invoice_evidence_payload(
        invoices=invoices,
        bucket_id=bucket_id,
        transaction_id=transaction_id,
        purchase_invoice_evidence_id=purchase_invoice_evidence_id,
        category_id=category_id,
        signed_transaction_amount=eur_amount,
    )
    if isinstance(evidence_payload, RentaLedgerAggregationIssue):
        return evidence_payload
    try:
        fact = RentaDeductibleExpenseFact(
            transaction_id=transaction_id,
            invoice_id=purchase_invoice_evidence_id,
            catalogue_id=_LEDGER_CATALOGUE_ID,
            operation_date=transaction.raw.value_date or transaction.raw.booked_date,
            invoice_issue_date=evidence_payload.invoice_issue_date,
            posting_date=transaction.raw.booked_date,
            gross_amount=business_amount,
            taxable_base=_taxable_base_for(transaction, evidence_payload),
            iva_amount=_iva_amount_for(transaction, evidence_payload),
            direction=direction,
            category=category,
            activity_key=activity_key,
        )
    except ValueError as exc:
        return RentaLedgerAggregationIssue(
            transaction_id=transaction_id,
            purchase_invoice_evidence_id=purchase_invoice_evidence_id,
            category_id=category_id,
            reason=RentaLedgerAggregationIssueReason.INVALID_LEDGER_FACT,
            detail=_bounded_detail(str(exc)),
        )
    if not resolved_period.contains(fact.filing_date):
        return RentaLedgerAggregationIssue(
            transaction_id=transaction_id,
            purchase_invoice_evidence_id=purchase_invoice_evidence_id,
            category_id=category_id,
            reason=RentaLedgerAggregationIssueReason.OUTSIDE_PERIOD,
            detail=f"filing date {fact.filing_date.isoformat()} is outside {resolved_period}",
        )
    result = evaluate_renta_deductibility(fact, profile, context)
    if result.status is not RentaDeductibilityStatus.ELIGIBLE:
        return RentaLedgerAggregationIssue(
            transaction_id=transaction_id,
            purchase_invoice_evidence_id=purchase_invoice_evidence_id,
            category_id=category_id,
            reason=RentaLedgerAggregationIssueReason.INELIGIBLE_DEDUCTIBILITY,
            detail=result.reason,
        )
    try:
        return build_renta_deductible_expense_observation(
            fact,
            result,
            tax_year=resolved_period.year,
        )
    except ValueError as exc:
        return RentaLedgerAggregationIssue(
            transaction_id=transaction_id,
            purchase_invoice_evidence_id=purchase_invoice_evidence_id,
            category_id=category_id,
            reason=RentaLedgerAggregationIssueReason.INVALID_LEDGER_FACT,
            detail=_bounded_detail(str(exc)),
        )


def _resolve_annual_period(period: Period) -> Period:
    resolved = period
    if resolved.kind is not PeriodKind.ANNUAL:
        raise AggregationPeriodError(
            t("aggregation.renta_ledger.errors.annual_period_required"),
            context={"period": str(resolved)},
        )
    return resolved


def _renta_direction_for(
    direction: TransactionDirection,
    purchase_invoice_evidence_id: str | None,
) -> RentaExpenseDirection | None:
    if direction is TransactionDirection.OUTGOING:
        return RentaExpenseDirection.OUTGOING_EXPENSE
    if direction is TransactionDirection.INCOMING and purchase_invoice_evidence_id is not None:
        return RentaExpenseDirection.REFUND
    return None


def _business_amount(
    signed_amount: Decimal,
    classification: BusinessClassification,
    business_pct: Decimal | None,
) -> Decimal | None:
    amount = abs(signed_amount)
    proportion = business_proportion(classification, business_pct)
    if proportion is None:
        return None
    return amount * proportion


def _purchase_invoice_evidence_payload(
    *,
    invoices: InvoiceCatalogue,
    bucket_id: str,
    transaction_id: str,
    purchase_invoice_evidence_id: str | None,
    category_id: str | None,
    signed_transaction_amount: Decimal,
) -> _PurchaseInvoiceEvidencePayload | RentaLedgerAggregationIssue:
    if purchase_invoice_evidence_id is None:
        return _PurchaseInvoiceEvidencePayload()
    invoice = invoices.get(purchase_invoice_evidence_id)
    if invoice is None:
        return RentaLedgerAggregationIssue(
            transaction_id=transaction_id,
            purchase_invoice_evidence_id=purchase_invoice_evidence_id,
            category_id=category_id,
            reason=RentaLedgerAggregationIssueReason.MISSING_PURCHASE_INVOICE_EVIDENCE,
            detail="transaction references purchase invoice evidence that is absent from the invoice catalogue",
        )
    if invoice.bucket_id != bucket_id:
        return RentaLedgerAggregationIssue(
            transaction_id=transaction_id,
            purchase_invoice_evidence_id=purchase_invoice_evidence_id,
            category_id=category_id,
            reason=RentaLedgerAggregationIssueReason.PURCHASE_INVOICE_EVIDENCE_BUCKET_MISMATCH,
            detail="transaction references purchase invoice evidence outside the active bucket",
        )
    if invoice.kind is not InvoiceKind.RECEIVED:
        return RentaLedgerAggregationIssue(
            transaction_id=transaction_id,
            purchase_invoice_evidence_id=purchase_invoice_evidence_id,
            category_id=category_id,
            reason=RentaLedgerAggregationIssueReason.UNSUPPORTED_PURCHASE_INVOICE_EVIDENCE_KIND,
            detail=f"purchase invoice evidence kind {invoice.kind.value!r} is not RECEIVED",
        )
    if transaction_id not in invoice.linked_transaction_ids:
        return RentaLedgerAggregationIssue(
            transaction_id=transaction_id,
            purchase_invoice_evidence_id=purchase_invoice_evidence_id,
            category_id=category_id,
            reason=RentaLedgerAggregationIssueReason.PURCHASE_INVOICE_EVIDENCE_LINK_MISMATCH,
            detail="transaction and purchase invoice evidence links are not reciprocal",
        )
    if len(invoice.linked_transaction_ids) != 1:
        return RentaLedgerAggregationIssue(
            transaction_id=transaction_id,
            purchase_invoice_evidence_id=purchase_invoice_evidence_id,
            category_id=category_id,
            reason=RentaLedgerAggregationIssueReason.PARTIAL_OR_MULTI_TRANSACTION_PURCHASE_INVOICE_EVIDENCE,
            detail="first-slice aggregation only accepts one transaction per purchase invoice evidence record",
        )
    if abs(signed_transaction_amount) != invoice.grand_total:
        return RentaLedgerAggregationIssue(
            transaction_id=transaction_id,
            purchase_invoice_evidence_id=purchase_invoice_evidence_id,
            category_id=category_id,
            reason=RentaLedgerAggregationIssueReason.AMOUNT_MISMATCH,
            detail="linked transaction amount does not match invoice grand total",
        )
    return _PurchaseInvoiceEvidencePayload(
        invoice_issue_date=invoice.issued_at,
        taxable_base=invoice.base_total,
        iva_amount=invoice.iva_total,
    )


def _taxable_base_for(transaction: Transaction, evidence_payload: _PurchaseInvoiceEvidencePayload) -> Decimal | None:
    if evidence_payload.taxable_base is not None:
        return evidence_payload.taxable_base
    return transaction.taxable_base


def _iva_amount_for(transaction: Transaction, evidence_payload: _PurchaseInvoiceEvidencePayload) -> Decimal | None:
    if evidence_payload.iva_amount is not None:
        return evidence_payload.iva_amount
    return transaction.iva_amount


def _casilla_aggregation(
    period: Period,
    observations: Sequence[RentaDeductibleExpenseObservation],
    *,
    modelo: str,
) -> CasillaAggregation:
    totals: dict[str, Decimal] = {}
    provenance_rows: list[CasillaProvenance] = []
    grouped: dict[tuple[str, SpendingCategory], list[RentaDeductibleExpenseObservation]] = {}
    for observation in observations:
        totals[observation.target_casilla] = (
            totals.get(observation.target_casilla, Decimal("0")) + observation.deductible_amount
        )
        grouped.setdefault((observation.target_casilla, observation.category), []).append(observation)
    for (casilla, category), rows in sorted(grouped.items()):
        provenance_rows.append(
            CasillaProvenance(
                casilla=casilla,
                category_id=category,
                transaction_ids=tuple(sorted(row.transaction_id for row in rows)),
                subtotal=sum((row.deductible_amount for row in rows), start=Decimal("0")),
            ),
        )
    return CasillaAggregation(
        modelo=modelo,
        period=period,
        casilla_values=totals,
        provenance=tuple(provenance_rows),
    )


def _bounded_detail(detail: str) -> str:
    if len(detail) <= 512:
        return detail
    return f"{detail[:509]}..."


__all__ = [
    "RentaLedgerAggregationIssue",
    "RentaLedgerAggregationIssueReason",
    "RentaLedgerExpenseAggregation",
    "aggregate_renta_ledger_expenses",
    "aggregate_renta_ledger_expenses_from_repositories",
]
