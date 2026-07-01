"""Period-scoped Art. 109 activity-income coverage from ledger evidence."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from enum import StrEnum

from ...core._modelo import Modelo
from ...core._period import Period
from ...domain.modelos._work_unit import WorkUnit
from ...domain.transactions._enums import (
    BusinessClassification,
    TransactionDirection,
    TransactionLifecycleState,
)
from ...domain.transactions._irpf_categories import (
    IRPF_CATEGORY_ACTIVIDAD_ECONOMICA,
    IRPF_CATEGORY_TRABAJO,
)
from ...domain.transactions._models import Transaction, TransactionCatalogue
from ...domain.transactions._protocols import TransactionCatalogueRepositoryProtocol
from ...domain.transactions._repository import TransactionCatalogueRepository

_THRESHOLD = Decimal("0.70")
_ZERO = Decimal("0")
_PROVEN_ACTIVITY_STATES = frozenset({BusinessClassification.BUSINESS, BusinessClassification.MIXED})
_UNRESOLVED_ACTIVITY_STATES = frozenset(
    {
        BusinessClassification.NOT_YET_PROCESSED,
        BusinessClassification.PROCESSED_UNCLASSIFIED,
        BusinessClassification.SKIPPED_BY_RULE,
        BusinessClassification.FAILED_VALIDATION,
    },
)


class Art109ActivityIncomeCoverageStatus(StrEnum):
    """Whether current-period ledger evidence proves the Art. 109 threshold."""

    PROVEN = "proven"
    INSUFFICIENT = "insufficient"


@dataclass(frozen=True, slots=True)
class Art109ActivityIncomeCoverage:
    """Period-scoped Art. 109 70 percent activity-income coverage result."""

    status: Art109ActivityIncomeCoverageStatus
    meets_threshold: bool | None
    numerator: Decimal
    denominator: Decimal
    reason: str

    @property
    def is_proven(self) -> bool:
        """Return whether ``meets_threshold`` is backed by sufficient evidence."""
        return self.status is Art109ActivityIncomeCoverageStatus.PROVEN


def derive_art109_activity_income_coverage_for_work_unit(
    work_unit: WorkUnit,
    *,
    transaction_repository: TransactionCatalogueRepositoryProtocol | None,
) -> Art109ActivityIncomeCoverage:
    """Derive the Art. 109 current-payment-period coverage fact for an M130 work unit.

    The returned fact is proven only from current-period ledger rows, not from
    M130 output casillas. A row proves the denominator and withholding status
    only when it carries invoice substrate (``taxable_base`` and ``iva_amount``);
    gross-only bank movements fail closed because they cannot prove whether the
    receipt was subject to withholding.
    """
    if str(work_unit.modelo) != Modelo.M130.value:
        return _insufficient("not_modelo_130")
    period = work_unit.period
    if not period.has_date_span():
        return _insufficient("period_without_date_span")
    repository = transaction_repository or TransactionCatalogueRepository(bucket_id=work_unit.bucket_id)
    if repository.bucket_id != work_unit.bucket_id:
        return _insufficient("repository_bucket_mismatch")
    return derive_art109_activity_income_coverage(repository.load(), period=period)


def derive_art109_activity_income_coverage(
    catalogue: TransactionCatalogue,
    *,
    period: Period,
) -> Art109ActivityIncomeCoverage:
    """Derive Art. 109 current-period activity-income coverage from a transaction catalogue."""
    if not period.has_date_span():
        return _insufficient("period_without_date_span")

    numerator = _ZERO
    denominator = _ZERO
    for transaction in catalogue.values():
        row = _classify_current_period_row(transaction, period=period)
        if row is _RowKind.IGNORE:
            continue
        if row is _RowKind.INSUFFICIENT:
            return _insufficient("current_period_activity_income_unresolved")

        computable_income = _proved_computable_income(transaction)
        if computable_income is None or computable_income <= _ZERO:
            return _insufficient("current_period_activity_income_substrate_incomplete")
        denominator += computable_income
        if _proved_withheld_income(transaction):
            numerator += computable_income

    if denominator <= _ZERO:
        return _insufficient("current_period_activity_income_absent")

    return Art109ActivityIncomeCoverage(
        status=Art109ActivityIncomeCoverageStatus.PROVEN,
        meets_threshold=(numerator / denominator) >= _THRESHOLD,
        numerator=numerator,
        denominator=denominator,
        reason="current_period_activity_income_ratio_proven",
    )


class _RowKind(StrEnum):
    IGNORE = "ignore"
    ACTIVITY_INCOME = "activity_income"
    INSUFFICIENT = "insufficient"


def _classify_current_period_row(transaction: Transaction, *, period: Period) -> _RowKind:
    if transaction.lifecycle_state is not TransactionLifecycleState.ACTIVE:
        return _RowKind.IGNORE
    if transaction.business_classification is BusinessClassification.REVIEWED_EXCLUDED:
        return _RowKind.IGNORE
    if transaction.direction is not TransactionDirection.INCOMING:
        return _RowKind.IGNORE
    filing_date = transaction.raw.value_date or transaction.raw.booked_date
    if filing_date is None:
        return _RowKind.INSUFFICIENT
    if not period.contains(filing_date):
        return _RowKind.IGNORE
    if transaction.irpf_category == IRPF_CATEGORY_TRABAJO:
        return _RowKind.IGNORE
    if transaction.irpf_category == IRPF_CATEGORY_ACTIVIDAD_ECONOMICA:
        return _RowKind.ACTIVITY_INCOME
    if transaction.business_classification is BusinessClassification.PERSONAL:
        return _RowKind.IGNORE
    if transaction.business_classification in _PROVEN_ACTIVITY_STATES:
        return _RowKind.ACTIVITY_INCOME
    if transaction.business_classification in _UNRESOLVED_ACTIVITY_STATES:
        return _RowKind.INSUFFICIENT
    return _RowKind.INSUFFICIENT


def _proved_computable_income(transaction: Transaction) -> Decimal | None:
    if transaction.raw.currency != "EUR":
        return None
    if transaction.taxable_base is None or transaction.iva_amount is None:
        return None
    amount = transaction.taxable_base
    if transaction.business_classification is BusinessClassification.MIXED:
        if transaction.business_pct is None:
            return None
        amount *= transaction.business_pct
    return amount


def _proved_withheld_income(transaction: Transaction) -> bool:
    if transaction.taxable_base is None or transaction.iva_amount is None:
        return False
    invoice_gross = transaction.taxable_base + transaction.iva_amount
    cash_received = abs(transaction.raw.amount)
    return invoice_gross > cash_received


def _insufficient(reason: str) -> Art109ActivityIncomeCoverage:
    return Art109ActivityIncomeCoverage(
        status=Art109ActivityIncomeCoverageStatus.INSUFFICIENT,
        meets_threshold=None,
        numerator=_ZERO,
        denominator=_ZERO,
        reason=reason,
    )


__all__ = [
    "Art109ActivityIncomeCoverage",
    "Art109ActivityIncomeCoverageStatus",
    "derive_art109_activity_income_coverage",
    "derive_art109_activity_income_coverage_for_work_unit",
]
