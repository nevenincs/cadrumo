"""Repository-backed Renta deductible-expense (gasto) aggregation for Modelo 130.

Loads ledger rows through :class:`TransactionCatalogueRepository`.

Used by: :mod:`~._modelo_bindings` (source mesh) for Modelo 130 casilla 02
("Gastos") aggregation.

This is the OUTGOING sibling of :mod:`~._renta_income_ledger`. Where the income
pipeline accumulates professional-activity revenue into casilla 01, this
pipeline accumulates deductible business expenses into casilla 02 over the same
cumulative year-to-date quarterly window (RD 439/2007 art. 110.2). The two
pipelines share the lightweight ledger-projection mechanism and the cumulative
window; they differ only in flow direction and the casilla they feed.

Cumulative window rule (RD 439/2007 art. 110.2):
  For period Qn in year Y the window is [Jan 1, Y] through [last day of Qn, Y].

Only ACTIVE, EUR-denominated, OUTGOING transactions whose
``business_classification`` is BUSINESS or MIXED are eligible. The deductible
amount is the IVA-exclusive base imponible (``taxable_base``) when the
transaction carries an explicit IVA tagging — IVA soportado is recovered through
Modelo 303 and is not a Renta gasto — falling back to the gross transfer amount
when no base is declared. A MIXED transaction contributes its business fraction.

This module deliberately does NOT reuse the Modelo 100 first-slice expense
pipeline (:mod:`~._renta_ledger`): that path layers invoice-evidence
reconciliation, category-profile deductibility evaluation, and an annual window
that are constraint-shape-divergent from the M130 quarterly cumulative gasto sum.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import date
from decimal import Decimal
from enum import StrEnum
from typing import Self

from pydantic import BaseModel, Field, field_serializer, field_validator, model_validator

from ...core import STRICT_FROZEN_CONFIG as _STRICT_FROZEN
from ...core import Modelo, Period, PeriodKind
from ...domain.transactions import (
    Transaction,
    TransactionCatalogue,
    TransactionCatalogueRepository,
    TransactionCatalogueRepositoryProtocol,
    TransactionDirection,
    TransactionLifecycleState,
)
from . import _shared_issue_reasons
from ._business_proportion import business_proportion
from ._currency_predicates import is_non_eur_without_conversion
from ._errors import AggregationPeriodError, AggregationValidationError, t
from ._models import CasillaAggregation, CasillaProvenance

# The only casilla M130 deductible-expense aggregation feeds: official box 02
# ("Gastos"), bound to the ledger renta gasto aggregation. Operator-supplied
# non-ledger gastos (amortizaciones, the estimación directa simplificada 5%
# gastos de difícil justificación, cash-paid expenses) are a documented
# follow-up (an operator adjustment folded into box 02) — see the F1 finding.
_TARGET_CASILLA_GASTOS = "02"


class RentaGastoLedgerAggregationIssueReason(StrEnum):
    """Machine-readable reasons why a ledger row did not produce a gasto observation.

    Only reasons that represent a *dropped declarable gasto* — a BUSINESS / MIXED
    expense excluded by a downstream gate — are modelled, so every emitted issue
    is a genuine no-silent-under-declaration signal. INCOMING and PERSONAL /
    unclassified OUTGOING rows are skipped silently (they are not deductible
    gastos) and never produce an issue.
    """

    UNSUPPORTED_CURRENCY = _shared_issue_reasons.UNSUPPORTED_CURRENCY
    OUTSIDE_PERIOD = _shared_issue_reasons.OUTSIDE_PERIOD
    # A BUSINESS / MIXED expense with no declared IVA-exclusive base imponible:
    # the gross transfer includes IVA soportado (recovered through Modelo 303),
    # which is NOT a Renta gasto, so it cannot be aggregated IVA-exclusively. The
    # row is surfaced (no silent over-declaration of gastos) rather than
    # gross-folded; the operator tags it with a taxable_base via classify.
    MISSING_TAXABLE_BASE = "missing_taxable_base"


class RentaGastoLedgerAggregationIssue(BaseModel):
    """Traceable exclusion emitted while aggregating gasto ledger rows."""

    model_config = _STRICT_FROZEN

    transaction_id: str = Field(min_length=1, max_length=128)
    reason: RentaGastoLedgerAggregationIssueReason
    detail: str = Field(min_length=1, max_length=512)


class RentaGastoObservation(BaseModel):
    """One eligible OUTGOING deductible-expense ledger row.

    Carries the typed deductible amount and the target casilla it feeds. The
    domain registry resolver matches ``target_casilla`` against the binding
    selector and sums ``deductible_amount`` across all observations for that
    casilla, mirroring the income resolver's casilla-keyed fold.

    ``deductible_amount`` is the IVA-exclusive base imponible
    (``transaction.taxable_base``) when the row carries an explicit IVA tagging,
    falling back to the gross transfer amount when no base is declared, and
    scaled by the business fraction for MIXED transactions.
    """

    model_config = _STRICT_FROZEN

    transaction_id: str = Field(min_length=1, max_length=128)
    target_casilla: str = Field(min_length=2, max_length=8)
    deductible_amount: Decimal = Field(ge=Decimal("0"))
    filing_date: date


class RentaGastoLedgerAggregation(BaseModel):
    """Cumulative deductible-expense observations for one M130 quarter window."""

    model_config = _STRICT_FROZEN

    modelo: str = Field(min_length=1, max_length=16)
    period: Period
    observations: Sequence[RentaGastoObservation] = Field(default_factory=tuple)
    issues: Sequence[RentaGastoLedgerAggregationIssue] = Field(default_factory=tuple)
    casilla_aggregation: CasillaAggregation

    @field_validator("observations")
    @classmethod
    def _freeze_observations(
        cls,
        value: Sequence[RentaGastoObservation],
    ) -> tuple[RentaGastoObservation, ...]:
        return tuple(value)

    @field_validator("issues")
    @classmethod
    def _freeze_issues(
        cls,
        value: Sequence[RentaGastoLedgerAggregationIssue],
    ) -> tuple[RentaGastoLedgerAggregationIssue, ...]:
        return tuple(value)

    @model_validator(mode="after")
    def _validate_casilla_period(self) -> Self:
        if self.casilla_aggregation.modelo != self.modelo:
            raise AggregationValidationError(t("aggregation.renta_ledger.errors.modelo_mismatch"))
        if self.casilla_aggregation.period != self.period:
            raise AggregationValidationError(t("aggregation.renta_ledger.errors.period_mismatch"))
        return self

    @field_serializer("observations")
    def _serialize_observations(
        self,
        value: Sequence[RentaGastoObservation],
    ) -> tuple[RentaGastoObservation, ...]:
        return tuple(value)

    @field_serializer("issues")
    def _serialize_issues(
        self,
        value: Sequence[RentaGastoLedgerAggregationIssue],
    ) -> tuple[RentaGastoLedgerAggregationIssue, ...]:
        return tuple(value)


def aggregate_renta_gasto_ledger_from_repositories(
    *,
    bucket_id: str,
    period: Period,
    transaction_repository: TransactionCatalogueRepositoryProtocol | None = None,
) -> RentaGastoLedgerAggregation:
    """Load the transaction catalogue and aggregate cumulative M130 gastos.

    Returns a :class:`RentaGastoLedgerAggregation`.
    """
    repository = transaction_repository or TransactionCatalogueRepository(bucket_id=bucket_id)
    if repository.bucket_id != bucket_id:
        raise AggregationValidationError(
            t("aggregation.renta_ledger.errors.bucket_mismatch"),
            context={"bucket_id": bucket_id, "repository_bucket_id": repository.bucket_id},
        )
    transactions = repository.load()
    return aggregate_renta_gasto_ledger(transactions, bucket_id=bucket_id, period=period)


def aggregate_renta_gasto_ledger(
    transactions: TransactionCatalogue,
    *,
    bucket_id: str,
    period: Period,
) -> RentaGastoLedgerAggregation:
    """Aggregate OUTGOING deductible-expense transactions into M130 casilla 02.

    Args:
        transactions: The :class:`TransactionCatalogue` of ledger transactions to aggregate.
        bucket_id: Bucket identifier carried through to provenance and audit
            records so the resulting aggregation cannot be silently misattributed.
        period: The quarterly :class:`Period` whose year anchors the cumulative
            window.

    Returns a :class:`RentaGastoLedgerAggregation` covering the cumulative
    fiscal window. ``period`` must be quarterly; the cumulative window extends
    from Jan 1 of the period's year through the last day of the declared quarter
    (RD 439/2007 art. 110.2).
    """
    resolved_period = _resolve_quarterly_period(period)
    cumulative_start = date(resolved_period.year, 1, 1)
    cumulative_end = resolved_period.end_date

    observations: list[RentaGastoObservation] = []
    issues: list[RentaGastoLedgerAggregationIssue] = []

    for transaction in transactions.values():
        if transaction.lifecycle_state is not TransactionLifecycleState.ACTIVE:
            continue
        outcome = _classify_gasto_transaction(
            transaction,
            cumulative_start=cumulative_start,
            cumulative_end=cumulative_end,
        )
        if outcome is None:
            continue
        if isinstance(outcome, RentaGastoLedgerAggregationIssue):
            issues.append(outcome)
        else:
            observations.append(outcome)

    casilla_aggregation = _gasto_casilla_aggregation(resolved_period, observations)
    return RentaGastoLedgerAggregation(
        modelo=Modelo.M130.value,
        period=resolved_period,
        observations=tuple(observations),
        issues=tuple(issues),
        casilla_aggregation=casilla_aggregation,
    )


def _resolve_quarterly_period(period: Period) -> Period:
    if period.kind is not PeriodKind.QUARTERLY:
        raise AggregationPeriodError(
            t("aggregation.renta_ledger.errors.quarterly_period_required"),
            context={"period": str(period)},
        )
    return period


def _classify_gasto_transaction(
    transaction: Transaction,
    *,
    cumulative_start: date,
    cumulative_end: date,
) -> RentaGastoObservation | RentaGastoLedgerAggregationIssue | None:
    """Filter one ledger transaction against the M130 gasto pipeline.

    Returns a :class:`RentaGastoObservation` for an eligible deductible expense,
    a :class:`RentaGastoLedgerAggregationIssue` for an OUTGOING row that fails a
    gate (so the operator sees the dropped expense rather than a silent zero),
    or ``None`` for an INCOMING row that this expense pipeline simply does not
    own (it is the income pipeline's concern, never a gasto issue).
    """
    transaction_id = transaction.transaction_id

    # INCOMING rows belong to the income pipeline; this expense pass skips them
    # without recording an issue so the operator is not shown a spurious gasto
    # advisory for every receipt.
    if transaction.direction is not TransactionDirection.OUTGOING:
        return None

    # PERSONAL / unclassified OUTGOING rows are not deductible gastos (a real
    # taxpayer's groceries and rent). They are correctly excluded and need no
    # advisory — skip them silently. Only a BUSINESS / MIXED expense that should
    # be deductible but is dropped by a downstream gate (currency / period)
    # surfaces an issue (no-silent-under-declaration), so the operator sees a
    # genuinely lost gasto rather than advisory noise on every personal line.
    proportion = business_proportion(transaction.business_classification, transaction.business_pct)
    if proportion is None:
        return None

    if is_non_eur_without_conversion(transaction):
        return RentaGastoLedgerAggregationIssue(
            transaction_id=transaction_id,
            reason=RentaGastoLedgerAggregationIssueReason.UNSUPPORTED_CURRENCY,
            detail=f"transaction currency {transaction.raw.currency!r} is not supported for Renta gastos",
        )

    filing_date = transaction.raw.value_date or transaction.raw.booked_date
    if filing_date is None or not (cumulative_start <= filing_date <= cumulative_end):
        return RentaGastoLedgerAggregationIssue(
            transaction_id=transaction_id,
            reason=RentaGastoLedgerAggregationIssueReason.OUTSIDE_PERIOD,
            detail=f"filing date {filing_date} is outside the cumulative gasto window",
        )

    # A deductible gasto must declare its IVA-exclusive base imponible: the gross
    # transfer carries IVA soportado that is recovered through Modelo 303 and is
    # not a Renta gasto. Without a taxable_base we cannot fold it IVA-exclusively,
    # so surface it (the operator tags it via classify) rather than gross-folding
    # and silently OVER-declaring gastos (which would under-state the pago
    # fraccionado). Preflight already requires taxable_base, so this is a backstop.
    if transaction.taxable_base is None:
        return RentaGastoLedgerAggregationIssue(
            transaction_id=transaction_id,
            reason=RentaGastoLedgerAggregationIssueReason.MISSING_TAXABLE_BASE,
            detail=(
                "OUTGOING business expense carries no taxable_base (IVA-exclusive base imponible); "
                "classify it with --taxable-base so its deductible gasto is aggregated into casilla 02"
            ),
        )

    # taxable_base is non-None here (the MISSING_TAXABLE_BASE guard above returned
    # for the None case). IVA soportado is recovered through Modelo 303, so the
    # IVA-exclusive base imponible is the deductible gasto, scaled by the business
    # fraction (1 for BUSINESS, business_pct for MIXED).
    deductible_amount = transaction.taxable_base * proportion
    return RentaGastoObservation(
        transaction_id=transaction_id,
        target_casilla=_TARGET_CASILLA_GASTOS,
        deductible_amount=deductible_amount,
        filing_date=filing_date,
    )


def _gasto_casilla_aggregation(
    period: Period,
    observations: Sequence[RentaGastoObservation],
) -> CasillaAggregation:
    totals: dict[str, Decimal] = {}
    grouped: dict[str, list[RentaGastoObservation]] = {}
    for observation in observations:
        totals[observation.target_casilla] = (
            totals.get(observation.target_casilla, Decimal("0")) + observation.deductible_amount
        )
        grouped.setdefault(observation.target_casilla, []).append(observation)
    provenance_rows = [
        CasillaProvenance(
            casilla=casilla,
            category_id=None,
            transaction_ids=tuple(sorted(row.transaction_id for row in rows)),
            subtotal=sum((row.deductible_amount for row in rows), start=Decimal("0")),
        )
        for casilla, rows in sorted(grouped.items())
    ]
    return CasillaAggregation(
        modelo=Modelo.M130.value,
        period=period,
        casilla_values=totals,
        provenance=tuple(provenance_rows),
    )


__all__ = [
    "RentaGastoLedgerAggregation",
    "RentaGastoLedgerAggregationIssue",
    "RentaGastoLedgerAggregationIssueReason",
    "RentaGastoObservation",
    "aggregate_renta_gasto_ledger",
    "aggregate_renta_gasto_ledger_from_repositories",
]
