"""Period-scoped Art. 109 activity-income coverage from ledger evidence.

The coverage helper derives the RIRPF Art. 109 70 percent withholding fact from
current-period ledger rows in a
:class:`~domain.transactions.TransactionCatalogue`. Work-unit consumers use
a bucket-scoped :class:`~adapters.persistence.profile.transactions.TransactionCatalogueRepository`
to load that catalogue before applying the same pure calculation.

The result is intentionally evidence-scoped: the denominator and withholding
status must be proven from invoice-substrate ledger facts, so gross-only bank
movements fail closed instead of fabricating an activity-income ratio.

See Also:
    :func:`derive_art109_activity_income_coverage`
        Pure catalogue-level derivation for already-loaded ledger rows.
    :func:`derive_art109_activity_income_coverage_for_work_unit`
        Work-unit adapter that resolves the matching bucket repository.
    :mod:`application.modelo._verification_actions`
        Verification path that folds a proven coverage fact into the workflow
        profile used for M130 verification.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from enum import StrEnum

from ...adapters.persistence.profile.transactions import TransactionCatalogueRepository
from ...core import Modelo, Period
from ...core.resources import bundled_path
from ...domain.calculations.registry.errors import RegistryValidationError
from ...domain.calculations.registry.formula_runtime_ops import resolve_parameter
from ...domain.calculations.registry.loader import load_registry_tree
from ...domain.calculations.registry.temporal import select_revision
from ...domain.modelos import WorkUnit
from ...domain.transactions import (
    IRPF_CATEGORY_ACTIVIDAD_ECONOMICA,
    IRPF_CATEGORY_TRABAJO,
    BusinessClassification,
    Transaction,
    TransactionCatalogue,
    TransactionCatalogueRepositoryProtocol,
    TransactionDirection,
    TransactionLifecycleState,
)

_ZERO = Decimal("0")
_ART_109_THRESHOLD_PARAMETER_ID = "irpf.art_109_retained_income_exemption_ratio"
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

    The returned :class:`Art109ActivityIncomeCoverage` is proven only from
    current-period ledger rows, not from M130 output casillas. A row proves
    the denominator and withholding status only when it carries invoice
    substrate (``taxable_base`` and ``iva_amount``); gross-only bank
    movements fail closed because they cannot prove whether the receipt was
    subject to withholding.
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


def art_109_retained_income_threshold(*, filing_year: int, period: Period) -> Decimal:
    """Return the Art. 109 retained-income ratio the registry grounds for this filing.

    The ratio is regulatory data, versioned by filing year plus revision, so it
    is read from the Modelo 130 revision that governs ``(filing_year, period)``
    rather than inlined here. RD 439/2007 art. 109 establishes it, and the
    parameter carries that citation.

    Args:
        filing_year: The filing year whose revision declares the parameter.
        period: The filing period, used to resolve the governing revision and
            to date-resolve the parameter value.

    Returns:
        The threshold as a fraction (0.70 for the 70 per 100 the article states).

    Raises:
        RegistryValidationError: When the governing revision declares no Art. 109
            threshold parameter. Refusing is correct: answering from a default
            would apply an ungrounded ratio to a real filing decision.
    """
    modelos, _catalogues = load_registry_tree(bundled_path("registry", "aeat"))
    definition = next(candidate for candidate in modelos if candidate.id == Modelo.M130.value)
    revision = select_revision(definition, filing_year=filing_year, period=period.registry_token)
    for parameter in revision.parameters:
        if parameter.id == _ART_109_THRESHOLD_PARAMETER_ID:
            return resolve_parameter(parameter, {"filing_period": period.end_date})
    raise RegistryValidationError(
        f"modelo 130 revision {revision.id} declares no {_ART_109_THRESHOLD_PARAMETER_ID!r}; "
        "the Art. 109 retained-income threshold has no grounded value to apply",
    )


def derive_art109_activity_income_coverage(
    catalogue: TransactionCatalogue,
    *,
    period: Period,
) -> Art109ActivityIncomeCoverage:
    """Derive Art. 109 current-period coverage from a transaction catalogue.

    Args:
        catalogue: :class:`~domain.transactions.TransactionCatalogue`
            containing the ledger rows to classify for the target period.
        period: Filing period whose date span selects the current-payment rows.

    Returns:
        The proven or insufficient :class:`Art109ActivityIncomeCoverage`.
    """
    if not period.has_date_span():
        return _insufficient("period_without_date_span")

    threshold = art_109_retained_income_threshold(filing_year=period.filing_year, period=period)
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
        meets_threshold=(numerator / denominator) >= threshold,
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
