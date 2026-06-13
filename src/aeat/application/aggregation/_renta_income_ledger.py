"""Repository-backed Renta income aggregation for actividad economía (Modelo 130).

Used by: :mod:`~._service` (per-modelo aggregation service) for Modelo 130 income aggregation.

The primary entry point :func:`aggregate_renta_income_ledger_from_repositories`
loads a :class:`~aeat.domain.transactions.TransactionCatalogue` via
:class:`~aeat.domain.transactions.TransactionCatalogueRepository`
from the active bucket and delegates to :func:`aggregate_renta_income_ledger`
for period-scoped aggregation.

Modelo 130 casilla 01 (Ingresos íntegros) accumulates professional-service
revenue from the start of the fiscal year through the end of the declared
quarter. Unlike the expense pipeline, which processes annual periods, the
income pipeline accepts a **quarterly** period token and applies a cumulative
year-to-date window.

Cumulative window rule (RD 439/2007 art. 110.2):
  For period Qn in year Y the window is [Jan 1, Y] through [last day of Qn, Y].
  Q1 covers Jan-Mar; Q2 covers Jan-Jun; Q3 covers Jan-Sep; Q4 covers Jan-Dec.

Only ACTIVE, EUR-denominated, INCOMING transactions whose
``business_classification`` is BUSINESS or MIXED are eligible. Transactions
whose ``value_date`` (or ``booked_date`` if absent) falls outside the
cumulative window are excluded with a traceable issue record.
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
from ._currency_predicates import is_non_eur_without_conversion
from ._errors import AggregationPeriodError, AggregationValidationError, t
from ._models import CasillaAggregation, CasillaProvenance

# The only casilla income aggregation feeds for M130 actividad económica direct estimation.
_TARGET_CASILLA_INGRESOS = "01"


class RentaIncomeLedgerAggregationIssueReason(StrEnum):
    """Machine-readable reasons why a ledger row did not produce an income observation."""

    UNSUPPORTED_DIRECTION = _shared_issue_reasons.UNSUPPORTED_DIRECTION
    UNSUPPORTED_CURRENCY = _shared_issue_reasons.UNSUPPORTED_CURRENCY
    UNCLASSIFIED_BUSINESS_STATE = _shared_issue_reasons.UNCLASSIFIED_BUSINESS_STATE
    PERSONAL_TRANSACTION = _shared_issue_reasons.PERSONAL_TRANSACTION
    OUTSIDE_PERIOD = _shared_issue_reasons.OUTSIDE_PERIOD
    UNSUPPORTED_PERIOD = "unsupported_period"
    # Nómina / trabajo entries declare irpf_category="trabajo" — they
    # belong to IRPF rendimientos del trabajo, not actividad económica,
    # and must not feed M130 casillas.
    TRABAJO_INCOME = "trabajo_income"
    # An OUTGOING business-classified row is a deducible gasto candidate.
    # M130 casilla 02 (Gastos) has no ledger aggregation binding yet, so
    # the expense is NOT folded into the filing; per
    # no-silent-under-declaration the drop must surface loudly in expense
    # vocabulary, never as a generic "not an income flow" exclusion.
    DEDUCIBLE_EXPENSE_NOT_AGGREGATED = "deducible_expense_not_aggregated"


class RentaIncomeLedgerAggregationIssue(BaseModel):
    """Traceable exclusion emitted while aggregating income ledger rows."""

    model_config = _STRICT_FROZEN

    transaction_id: str = Field(min_length=1, max_length=128)
    reason: RentaIncomeLedgerAggregationIssueReason
    detail: str = Field(min_length=1, max_length=512)


class RentaIncomeObservation(BaseModel):
    """One eligible INCOMING professional-income ledger row.

    Carries the typed gross amount and the target casilla it feeds. The
    domain registry resolver matches ``target_casilla`` against the binding
    selector and sums ``gross_amount`` (or ``taxable_base_amount``) across
    all observations for that casilla depending on the declared fact.

    ``taxable_base_amount`` is the IVA-exclusive base imponible from the
    original invoice (``transaction.taxable_base``).  It feeds the
    ``taxable_base_sum`` fact path used by the rendimiento-neto binding
    (casilla 03).  ``None`` when the transaction carries no explicit
    ``taxable_base``.

    ``source_jurisdiction`` propagates the per-transaction ISO 3166-1
    alpha-2 source-jurisdiction provenance from the originating ledger
    row.  LIRPF Art. 8 establishes the universal-base presumption for
    Spanish residents, so M130 / M100 aggregate ALL source jurisdictions
    into the same base — the field is preserved for audit and for
    downstream IRNR / Beckham engines that read foreign-source rows.
    """

    model_config = _STRICT_FROZEN

    transaction_id: str = Field(min_length=1, max_length=128)
    target_casilla: str = Field(min_length=2, max_length=8)
    gross_amount: Decimal = Field(ge=Decimal("0"))
    taxable_base_amount: Decimal | None = Field(default=None, ge=Decimal("0"))
    filing_date: date
    source_jurisdiction: str | None = None


class RentaIncomeLedgerAggregation(BaseModel):
    """Cumulative income observations for one M130 quarter window."""

    model_config = _STRICT_FROZEN

    modelo: str = Field(min_length=1, max_length=16)
    period: Period
    observations: Sequence[RentaIncomeObservation] = Field(default_factory=tuple)
    issues: Sequence[RentaIncomeLedgerAggregationIssue] = Field(default_factory=tuple)
    casilla_aggregation: CasillaAggregation

    @field_validator("observations")
    @classmethod
    def _freeze_observations(
        cls,
        value: Sequence[RentaIncomeObservation],
    ) -> tuple[RentaIncomeObservation, ...]:
        return tuple(value)

    @field_validator("issues")
    @classmethod
    def _freeze_issues(
        cls,
        value: Sequence[RentaIncomeLedgerAggregationIssue],
    ) -> tuple[RentaIncomeLedgerAggregationIssue, ...]:
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
        value: Sequence[RentaIncomeObservation],
    ) -> tuple[RentaIncomeObservation, ...]:
        return tuple(value)

    @field_serializer("issues")
    def _serialize_issues(
        self,
        value: Sequence[RentaIncomeLedgerAggregationIssue],
    ) -> tuple[RentaIncomeLedgerAggregationIssue, ...]:
        return tuple(value)


def aggregate_renta_income_ledger_from_repositories(
    *,
    bucket_id: str,
    period: Period,
    transaction_repository: TransactionCatalogueRepositoryProtocol | None = None,
) -> RentaIncomeLedgerAggregation:
    """Load the transaction catalogue and aggregate cumulative M130 income.

    Returns a :class:`RentaIncomeLedgerAggregation`.
    """
    repository = transaction_repository or TransactionCatalogueRepository(bucket_id=bucket_id)
    if repository.bucket_id != bucket_id:
        raise AggregationValidationError(
            t("aggregation.renta_ledger.errors.bucket_mismatch"),
            context={"bucket_id": bucket_id, "repository_bucket_id": repository.bucket_id},
        )
    transactions = repository.load()
    return aggregate_renta_income_ledger(transactions, bucket_id=bucket_id, period=period)


def aggregate_renta_income_ledger(
    transactions: TransactionCatalogue,
    *,
    bucket_id: str,
    period: Period,
) -> RentaIncomeLedgerAggregation:
    """Aggregate INCOMING professional-income transactions into M130 casilla 01.

    Args:
        transactions: The :class:`TransactionCatalogue` of ledger transactions to aggregate.
        bucket_id: Bucket identifier carried through to provenance and audit
            records so the resulting aggregation cannot be silently misattributed.
        period: The quarterly :class:`Period` whose year anchors the cumulative
            window.

    Returns a :class:`RentaIncomeLedgerAggregation` covering the
    cumulative fiscal window. ``period`` must be quarterly. The cumulative
    window extends from Jan 1 of the
    period's year through the last day of the declared quarter,
    implementing the year-to-date accumulation rule for IRPF pagos
    fraccionados (RD 439/2007 art. 110.2).
    """
    resolved_period = _resolve_quarterly_period(period)
    # Cumulative start: Jan 1 of the fiscal year.
    cumulative_start = date(resolved_period.year, 1, 1)
    # Cumulative end: last day of the declared quarter.
    cumulative_end = resolved_period.end_date

    observations: list[RentaIncomeObservation] = []
    issues: list[RentaIncomeLedgerAggregationIssue] = []

    for transaction in transactions.values():
        if transaction.lifecycle_state is not TransactionLifecycleState.ACTIVE:
            continue
        outcome = _classify_income_transaction(
            transaction,
            cumulative_start=cumulative_start,
            cumulative_end=cumulative_end,
        )
        if isinstance(outcome, RentaIncomeLedgerAggregationIssue):
            issues.append(outcome)
        else:
            observations.append(outcome)

    casilla_aggregation = _income_casilla_aggregation(resolved_period, observations)
    return RentaIncomeLedgerAggregation(
        modelo=Modelo.M130.value,
        period=resolved_period,
        observations=tuple(observations),
        issues=tuple(issues),
        casilla_aggregation=casilla_aggregation,
    )


def _resolve_quarterly_period(period: Period) -> Period:
    resolved = period
    if resolved.kind is not PeriodKind.QUARTERLY:
        raise AggregationPeriodError(
            t("aggregation.renta_ledger.errors.quarterly_period_required"),
            context={"period": str(resolved)},
        )
    return resolved


_IRPF_CATEGORY_ACTIVIDAD_ECONOMICA: str = "actividad_economica"
_IRPF_CATEGORY_TRABAJO: str = "trabajo"


def _classify_income_transaction(
    transaction: Transaction,
    *,
    cumulative_start: date,
    cumulative_end: date,
) -> RentaIncomeObservation | RentaIncomeLedgerAggregationIssue:
    """Filter one ledger transaction against the M130 income pipeline."""
    transaction_id = transaction.transaction_id

    if transaction.direction is not TransactionDirection.INCOMING:
        if transaction.direction is TransactionDirection.OUTGOING and transaction.business_classification in (
            BusinessClassification.BUSINESS,
            BusinessClassification.MIXED,
        ):
            # A business-classified OUTGOING row is a deducible gasto
            # candidate. There is no M130 casilla 02 (Gastos) ledger
            # aggregation binding yet, so this expense will NOT reduce the
            # rendimiento neto unless the operator declares gastos
            # manually. Surface the drop in expense vocabulary so the
            # operator is never left with a silent under-declared expense
            # side (no-silent-under-declaration).
            base = transaction.taxable_base if transaction.taxable_base is not None else abs(transaction.raw.amount)
            category = transaction.category_id or "unclassified"
            return RentaIncomeLedgerAggregationIssue(
                transaction_id=transaction_id,
                reason=RentaIncomeLedgerAggregationIssueReason.DEDUCIBLE_EXPENSE_NOT_AGGREGATED,
                detail=(
                    f"deducible expense (gasto) candidate dropped: OUTGOING business transaction "
                    f"(category {category!r}, base {base}) is not aggregated into Modelo 130 "
                    "casilla 02 (Gastos) — no expense aggregation binding exists yet; declare the "
                    "quarter's gastos manually (e.g. --binding for casilla 02) or the filing "
                    "overstates rendimiento neto"
                ),
            )
        return RentaIncomeLedgerAggregationIssue(
            transaction_id=transaction_id,
            reason=RentaIncomeLedgerAggregationIssueReason.UNSUPPORTED_DIRECTION,
            detail=f"transaction direction {transaction.direction.value!r} is not an income flow",
        )
    if is_non_eur_without_conversion(transaction):
        return RentaIncomeLedgerAggregationIssue(
            transaction_id=transaction_id,
            reason=RentaIncomeLedgerAggregationIssueReason.UNSUPPORTED_CURRENCY,
            detail=f"transaction currency {transaction.raw.currency!r} is not supported for Renta income",
        )

    # Nómina entries (irpf_category="trabajo") belong to rendimientos del
    # trabajo and must not feed M130 actividad-económica casillas.
    if transaction.irpf_category == _IRPF_CATEGORY_TRABAJO:
        return RentaIncomeLedgerAggregationIssue(
            transaction_id=transaction_id,
            reason=RentaIncomeLedgerAggregationIssueReason.TRABAJO_INCOME,
            detail=(
                f"irpf_category {transaction.irpf_category!r} belongs to rendimientos del trabajo, "
                "not actividad económica; excluded from M130"
            ),
        )

    gross_amount = _income_business_amount(transaction)
    if gross_amount is None:
        reason = (
            RentaIncomeLedgerAggregationIssueReason.PERSONAL_TRANSACTION
            if transaction.business_classification is BusinessClassification.PERSONAL
            else RentaIncomeLedgerAggregationIssueReason.UNCLASSIFIED_BUSINESS_STATE
        )
        return RentaIncomeLedgerAggregationIssue(
            transaction_id=transaction_id,
            reason=reason,
            detail=(f"business classification {transaction.business_classification.value!r} cannot feed Renta income"),
        )

    filing_date = transaction.raw.value_date or transaction.raw.booked_date
    if filing_date is None or not (cumulative_start <= filing_date <= cumulative_end):
        return RentaIncomeLedgerAggregationIssue(
            transaction_id=transaction_id,
            reason=RentaIncomeLedgerAggregationIssueReason.OUTSIDE_PERIOD,
            detail=f"filing date {filing_date} is outside the cumulative income window",
        )

    # taxable_base carries the IVA-exclusive base imponible when set; it
    # feeds the taxable_base_sum fact path for the rendimiento-neto binding.
    taxable_base_amount: Decimal | None = None
    if transaction.taxable_base is not None:
        raw_tb = transaction.taxable_base
        if transaction.business_classification is BusinessClassification.MIXED and transaction.business_pct is not None:
            taxable_base_amount = raw_tb * transaction.business_pct
        else:
            taxable_base_amount = raw_tb

    return RentaIncomeObservation(
        transaction_id=transaction_id,
        target_casilla=_TARGET_CASILLA_INGRESOS,
        gross_amount=gross_amount,
        taxable_base_amount=taxable_base_amount,
        filing_date=filing_date,
        source_jurisdiction=transaction.source_jurisdiction,
    )


def _income_business_amount(transaction: Transaction) -> Decimal | None:
    """Return the business-attributed income amount, or None if not eligible.

    When ``irpf_category`` is explicitly set to ``"actividad_economica"`` the
    transaction is already classified as a professional-activity receipt and
    ``business_classification`` is treated as ``BUSINESS`` by definition (the
    category tag is the authoritative signal).  This avoids the common case
    where a transaction is tagged with ``irpf_category=actividad_economica``
    before the broader ``business_classification`` sweep has run.
    """
    amount = abs(transaction.raw.amount)
    if transaction.irpf_category == _IRPF_CATEGORY_ACTIVIDAD_ECONOMICA:
        # The explicit IRPF category is the authoritative M130 eligibility gate.
        return amount
    proportion = business_proportion(transaction.business_classification, transaction.business_pct)
    if proportion is None:
        return None
    return amount * proportion


def _computable_income_amount(observation: RentaIncomeObservation) -> Decimal:
    """Return the fiscally computable ingreso for one observation.

    Mirrors the registry's ``ingresos_integros_sum`` fact: the
    IVA-exclusive ``taxable_base_amount`` when the transaction carries an
    explicit IVA tagging, falling back to ``gross_amount`` when no base is
    declared. IVA repercutido is collected on behalf of Hacienda and is
    not computable income, so the two surfaces (this projection and the
    binding resolver) must agree per the one-aggregation-path discipline.
    """
    if observation.taxable_base_amount is not None:
        return observation.taxable_base_amount
    return observation.gross_amount


def _income_casilla_aggregation(
    period: Period,
    observations: Sequence[RentaIncomeObservation],
) -> CasillaAggregation:
    totals: dict[str, Decimal] = {}
    provenance_rows: list[CasillaProvenance] = []
    grouped: dict[str, list[RentaIncomeObservation]] = {}
    for observation in observations:
        totals[observation.target_casilla] = (
            totals.get(observation.target_casilla, Decimal("0")) + _computable_income_amount(observation)
        )
        grouped.setdefault(observation.target_casilla, []).append(observation)
    for casilla, rows in sorted(grouped.items()):
        provenance_rows.append(
            CasillaProvenance(
                casilla=casilla,
                category_id=None,
                transaction_ids=tuple(sorted(row.transaction_id for row in rows)),
                subtotal=sum((_computable_income_amount(row) for row in rows), start=Decimal("0")),
            ),
        )
    return CasillaAggregation(
        modelo=Modelo.M130.value,
        period=period,
        casilla_values=totals,
        provenance=tuple(provenance_rows),
    )


__all__ = [
    "RentaIncomeLedgerAggregation",
    "RentaIncomeLedgerAggregationIssue",
    "RentaIncomeLedgerAggregationIssueReason",
    "RentaIncomeObservation",
    "aggregate_renta_income_ledger",
    "aggregate_renta_income_ledger_from_repositories",
]
