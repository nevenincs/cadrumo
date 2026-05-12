"""Repository-backed Renta expense aggregation from ledger catalogues."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import date
from decimal import Decimal
from enum import StrEnum
from typing import Any, Self

from pydantic import BaseModel, ConfigDict, Field, field_serializer, field_validator, model_validator

from ...domain.categories import SpendingCategory, resolve_category_profiles
from ...domain.invoices import InvoiceCatalogue, InvoiceCatalogueRepository, InvoiceKind
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
from ...domain.transactions import BusinessClassification, TransactionCatalogue, TransactionCatalogueRepository
from ...domain.transactions import TransactionDirection as LedgerTransactionDirection
from ._errors import AggregationPeriodError, AggregationValidationError, t
from ._models import CasillaAggregation, CasillaProvenance, Period, PeriodKind

_STRICT_FROZEN = ConfigDict(strict=True, frozen=True, extra="forbid")
_LEDGER_CATALOGUE_ID = "ledger"


class RentaLedgerAggregationIssueReason(StrEnum):
    """Machine-readable reasons why a ledger row did not produce an observation."""

    UNSUPPORTED_PERIOD = "unsupported_period"
    UNSUPPORTED_DIRECTION = "unsupported_direction"
    UNSUPPORTED_CURRENCY = "unsupported_currency"
    UNCLASSIFIED_BUSINESS_STATE = "unclassified_business_state"
    PERSONAL_TRANSACTION = "personal_transaction"
    MISSING_CATEGORY = "missing_category"
    UNKNOWN_CATEGORY = "unknown_category"
    CATEGORY_OUTSIDE_FIRST_SLICE = "category_outside_first_slice"
    MISSING_CATEGORY_PROFILE = "missing_category_profile"
    OUTSIDE_PERIOD = "outside_period"
    MISSING_LINKED_INVOICE = "missing_linked_invoice"
    UNSUPPORTED_INVOICE_KIND = "unsupported_invoice_kind"
    INVOICE_LINK_MISMATCH = "invoice_link_mismatch"
    PARTIAL_OR_MULTI_TRANSACTION_INVOICE = "partial_or_multi_transaction_invoice"
    AMOUNT_MISMATCH = "amount_mismatch"
    INVALID_LEDGER_FACT = "invalid_ledger_fact"
    INELIGIBLE_DEDUCTIBILITY = "ineligible_deductibility"


class RentaLedgerAggregationIssue(BaseModel):
    """Traceable exclusion emitted while aggregating ledger rows."""

    model_config = _STRICT_FROZEN

    transaction_id: str = Field(min_length=1, max_length=128)
    invoice_id: str | None = Field(default=None, min_length=1, max_length=128)
    category_id: str | None = Field(default=None, min_length=1, max_length=128)
    reason: RentaLedgerAggregationIssueReason
    detail: str = Field(min_length=1, max_length=512)


class _LinkedInvoicePayload(BaseModel):
    """Typed enrichment fields copied from a reconciled linked invoice."""

    model_config = _STRICT_FROZEN

    invoice_issue_date: date | None = None
    taxable_base: Decimal | None = None
    iva_amount: Decimal | None = None


class RentaLedgerExpenseAggregation(BaseModel):
    """First-slice Renta observations plus binding-ready casilla totals."""

    model_config = _STRICT_FROZEN

    modelo: str = Field(default="100", min_length=1, max_length=16)
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
    period: Period | str,
    transaction_repository: TransactionCatalogueRepository | None = None,
    invoice_repository: InvoiceCatalogueRepository | None = None,
    profile_year: int | None = None,
    usage_ratios: Mapping[SpendingCategory, Decimal] | None = None,
    activity_key: str = "default",
) -> RentaLedgerExpenseAggregation:
    """Load persisted catalogues and aggregate first-slice Renta expenses."""

    transactions = (transaction_repository or TransactionCatalogueRepository()).load()
    invoices = (invoice_repository or InvoiceCatalogueRepository()).load()
    return aggregate_renta_ledger_expenses(
        transactions,
        invoices,
        period=period,
        profile_year=profile_year,
        usage_ratios=usage_ratios,
        activity_key=activity_key,
    )


def aggregate_renta_ledger_expenses(
    transactions: TransactionCatalogue,
    invoices: InvoiceCatalogue,
    *,
    period: Period | str,
    profile_year: int | None = None,
    usage_ratios: Mapping[SpendingCategory, Decimal] | None = None,
    activity_key: str = "default",
) -> RentaLedgerExpenseAggregation:
    """Aggregate classified ledger transactions into Renta expense observations."""

    resolved_period = _resolve_annual_period(period)
    resolved_profile_year = profile_year if profile_year is not None else resolved_period.year
    profiles = resolve_category_profiles(resolved_profile_year)
    context = RentaDeductibilityContext(
        profile_year=resolved_profile_year,
        usage_ratios=dict(usage_ratios or {}),
    )
    observations: list[RentaDeductibleExpenseObservation] = []
    issues: list[RentaLedgerAggregationIssue] = []

    for transaction in transactions.values():
        issue_common: dict[str, Any] = {
            "transaction_id": transaction.transaction_id,
            "invoice_id": transaction.invoice_id,
            "category_id": transaction.category_id,
        }
        direction = _renta_direction_for(transaction.direction, transaction.invoice_id)
        if direction is None:
            issues.append(
                RentaLedgerAggregationIssue(
                    **issue_common,
                    reason=RentaLedgerAggregationIssueReason.UNSUPPORTED_DIRECTION,
                    detail=f"transaction direction {transaction.direction.value!r} is not a Renta expense flow",
                )
            )
            continue
        if transaction.raw.currency != "EUR":
            issues.append(
                RentaLedgerAggregationIssue(
                    **issue_common,
                    reason=RentaLedgerAggregationIssueReason.UNSUPPORTED_CURRENCY,
                    detail=f"transaction currency {transaction.raw.currency!r} is not supported for Renta expenses",
                )
            )
            continue

        business_amount = _business_amount(
            transaction.raw.amount,
            transaction.business_classification,
            transaction.business_pct,
        )
        if business_amount is None:
            reason = (
                RentaLedgerAggregationIssueReason.PERSONAL_TRANSACTION
                if transaction.business_classification is BusinessClassification.PERSONAL
                else RentaLedgerAggregationIssueReason.UNCLASSIFIED_BUSINESS_STATE
            )
            issues.append(
                RentaLedgerAggregationIssue(
                    **issue_common,
                    reason=reason,
                    detail=(
                        f"business classification {transaction.business_classification.value!r} "
                        "cannot feed Renta expenses"
                    ),
                )
            )
            continue

        if transaction.category_id is None:
            issues.append(
                RentaLedgerAggregationIssue(
                    **issue_common,
                    reason=RentaLedgerAggregationIssueReason.MISSING_CATEGORY,
                    detail="classified expense transaction has no ledger category",
                )
            )
            continue
        try:
            category = normalize_spending_category(transaction.category_id)
        except ValueError:
            issues.append(
                RentaLedgerAggregationIssue(
                    **issue_common,
                    reason=RentaLedgerAggregationIssueReason.UNKNOWN_CATEGORY,
                    detail=f"ledger category {transaction.category_id!r} is not in the spending taxonomy",
                )
            )
            continue
        if category not in RENTA_100_FIRST_SLICE_EXPENSE_CASILLAS:
            issues.append(
                RentaLedgerAggregationIssue(
                    **issue_common,
                    reason=RentaLedgerAggregationIssueReason.CATEGORY_OUTSIDE_FIRST_SLICE,
                    detail=f"category {category.value!r} has no first-slice Modelo 100 casilla mapping",
                )
            )
            continue
        profile = profiles.get(category)
        if profile is None:
            issues.append(
                RentaLedgerAggregationIssue(
                    **issue_common,
                    reason=RentaLedgerAggregationIssueReason.MISSING_CATEGORY_PROFILE,
                    detail=f"category {category.value!r} has no profile for {resolved_profile_year}",
                )
            )
            continue

        invoice_payload = _linked_invoice_payload(
            invoices=invoices,
            transaction_id=transaction.transaction_id,
            invoice_id=transaction.invoice_id,
            category_id=transaction.category_id,
            signed_transaction_amount=transaction.raw.amount,
        )
        if isinstance(invoice_payload, RentaLedgerAggregationIssue):
            issues.append(invoice_payload)
            continue

        try:
            fact = RentaDeductibleExpenseFact(
                transaction_id=transaction.transaction_id,
                invoice_id=transaction.invoice_id,
                catalogue_id=_LEDGER_CATALOGUE_ID,
                operation_date=transaction.raw.value_date or transaction.raw.booked_date,
                invoice_issue_date=invoice_payload.invoice_issue_date,
                posting_date=transaction.raw.booked_date,
                gross_amount=business_amount,
                taxable_base=invoice_payload.taxable_base,
                iva_amount=invoice_payload.iva_amount,
                direction=direction,
                category=category,
                activity_key=activity_key,
            )
        except ValueError as exc:
            issues.append(
                RentaLedgerAggregationIssue(
                    **issue_common,
                    reason=RentaLedgerAggregationIssueReason.INVALID_LEDGER_FACT,
                    detail=_bounded_detail(str(exc)),
                )
            )
            continue
        if not resolved_period.contains(fact.filing_date):
            issues.append(
                RentaLedgerAggregationIssue(
                    **issue_common,
                    reason=RentaLedgerAggregationIssueReason.OUTSIDE_PERIOD,
                    detail=f"filing date {fact.filing_date.isoformat()} is outside {resolved_period.raw}",
                )
            )
            continue
        result = evaluate_renta_deductibility(fact, profile, context)
        if result.status is not RentaDeductibilityStatus.ELIGIBLE:
            issues.append(
                RentaLedgerAggregationIssue(
                    **issue_common,
                    reason=RentaLedgerAggregationIssueReason.INELIGIBLE_DEDUCTIBILITY,
                    detail=result.reason,
                )
            )
            continue
        try:
            observations.append(
                build_renta_deductible_expense_observation(
                    fact,
                    result,
                    tax_year=resolved_period.year,
                )
            )
        except ValueError as exc:
            issues.append(
                RentaLedgerAggregationIssue(
                    **issue_common,
                    reason=RentaLedgerAggregationIssueReason.INVALID_LEDGER_FACT,
                    detail=_bounded_detail(str(exc)),
                )
            )

    casilla_aggregation = _casilla_aggregation(resolved_period, observations)
    return RentaLedgerExpenseAggregation(
        period=resolved_period,
        profile_year=resolved_profile_year,
        observations=tuple(observations),
        issues=tuple(issues),
        casilla_aggregation=casilla_aggregation,
    )


def _resolve_annual_period(period: Period | str) -> Period:
    resolved = period if isinstance(period, Period) else Period.model_validate(period)
    if resolved.kind is not PeriodKind.ANNUAL:
        raise AggregationPeriodError(
            t("aggregation.renta_ledger.errors.annual_period_required"),
            context={"period": resolved.raw},
        )
    return resolved


def _renta_direction_for(
    direction: LedgerTransactionDirection,
    invoice_id: str | None,
) -> RentaExpenseDirection | None:
    if direction is LedgerTransactionDirection.OUTGOING:
        return RentaExpenseDirection.OUTGOING_EXPENSE
    if direction is LedgerTransactionDirection.INCOMING and invoice_id is not None:
        return RentaExpenseDirection.REFUND
    return None


def _business_amount(
    signed_amount: Decimal,
    classification: BusinessClassification,
    business_pct: Decimal | None,
) -> Decimal | None:
    amount = abs(signed_amount)
    if classification is BusinessClassification.BUSINESS:
        return amount
    if classification is BusinessClassification.MIXED:
        assert business_pct is not None
        return amount * business_pct
    return None


def _linked_invoice_payload(
    *,
    invoices: InvoiceCatalogue,
    transaction_id: str,
    invoice_id: str | None,
    category_id: str | None,
    signed_transaction_amount: Decimal,
) -> _LinkedInvoicePayload | RentaLedgerAggregationIssue:
    if invoice_id is None:
        return _LinkedInvoicePayload()
    issue_common = {"transaction_id": transaction_id, "invoice_id": invoice_id, "category_id": category_id}
    invoice = invoices.get(invoice_id)
    if invoice is None:
        return RentaLedgerAggregationIssue(
            **issue_common,
            reason=RentaLedgerAggregationIssueReason.MISSING_LINKED_INVOICE,
            detail="transaction references an invoice that is absent from the invoice catalogue",
        )
    if invoice.kind is not InvoiceKind.RECEIVED:
        return RentaLedgerAggregationIssue(
            **issue_common,
            reason=RentaLedgerAggregationIssueReason.UNSUPPORTED_INVOICE_KIND,
            detail=f"expense transaction linked invoice kind {invoice.kind.value!r} is not RECEIVED",
        )
    if transaction_id not in invoice.linked_transaction_ids:
        return RentaLedgerAggregationIssue(
            **issue_common,
            reason=RentaLedgerAggregationIssueReason.INVOICE_LINK_MISMATCH,
            detail="transaction and invoice links are not reciprocal",
        )
    if len(invoice.linked_transaction_ids) != 1:
        return RentaLedgerAggregationIssue(
            **issue_common,
            reason=RentaLedgerAggregationIssueReason.PARTIAL_OR_MULTI_TRANSACTION_INVOICE,
            detail="first-slice aggregation only accepts one transaction per linked invoice",
        )
    if abs(signed_transaction_amount) != invoice.grand_total:
        return RentaLedgerAggregationIssue(
            **issue_common,
            reason=RentaLedgerAggregationIssueReason.AMOUNT_MISMATCH,
            detail="linked transaction amount does not match invoice grand total",
        )
    return _LinkedInvoicePayload(
        invoice_issue_date=invoice.issued_at,
        taxable_base=invoice.base_total,
        iva_amount=invoice.iva_total,
    )


def _casilla_aggregation(
    period: Period,
    observations: Sequence[RentaDeductibleExpenseObservation],
) -> CasillaAggregation:
    totals: dict[str, Decimal] = {}
    provenance_rows: list[CasillaProvenance] = []
    grouped: dict[tuple[str, str], list[RentaDeductibleExpenseObservation]] = {}
    for observation in observations:
        totals[observation.target_casilla] = (
            totals.get(observation.target_casilla, Decimal("0")) + observation.deductible_amount
        )
        grouped.setdefault((observation.target_casilla, observation.category.value), []).append(observation)
    for (casilla, category_id), rows in sorted(grouped.items()):
        provenance_rows.append(
            CasillaProvenance(
                casilla=casilla,
                category_id=category_id,
                transaction_ids=tuple(sorted(row.transaction_id for row in rows)),
                subtotal=sum((row.deductible_amount for row in rows), start=Decimal("0")),
            )
        )
    return CasillaAggregation(
        modelo="100",
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
