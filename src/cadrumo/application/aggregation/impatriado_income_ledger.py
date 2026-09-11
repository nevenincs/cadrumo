"""Repository-backed impatriado income ledger mechanics.

The module retains transaction filtering, amount projection, period partitioning,
typed issue emission, and aggregation mechanics. Target coordinates, selected
model/revision applicability, source-jurisdiction membership, eligible income
categories, and binding/legal declarations belong to the selected registry
revision.

TODO(fact-relocation): resolve impatriado ledger targets and jurisdiction applicability from selected registry revisions

No target, jurisdiction, category, applicability, or binding identifier is
declared as a Python fallback.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import date
from decimal import Decimal
from enum import StrEnum

from pydantic import BaseModel, Field

from ...adapters.persistence.profile.transactions import TransactionCatalogueRepository
from ...core.casilla_id import CasillaId
from ...core.country_code import CountryCodeAlpha2
from ...core.i18n.translatable import Translatable as t
from ...core.identity.transaction_ids import TransactionId
from ...core.models import STRICT_FROZEN_CONFIG as _STRICT_FROZEN
from ...core.period import Period, PeriodKind
from ...core.prose_elision import IssueDetail
from ...domain.transactions.enums import BusinessClassification, TransactionDirection, TransactionLifecycleState
from ...domain.transactions.models import OutOfWindowTransactionSummary, Transaction, TransactionCatalogue
from ...domain.transactions.protocols import TransactionCatalogueRepositoryProtocol
from . import _shared_issue_reasons
from ._grouping import fold_casilla_observations
from ._models import CasillaAggregation, LedgerAggregationResultBase
from .business_proportion import business_proportion
from .currency_predicates import effective_eur_amount, effective_eur_taxable_base, is_non_eur_without_conversion
from .errors import AggregationPeriodError, AggregationValidationError


class ImpatriadoIncomeLedgerAggregationIssueReason(StrEnum):
    """Machine-readable reasons why a ledger row did not fold into the impatriado base."""

    UNSUPPORTED_DIRECTION = _shared_issue_reasons.UNSUPPORTED_DIRECTION
    UNSUPPORTED_CURRENCY = _shared_issue_reasons.UNSUPPORTED_CURRENCY
    UNCLASSIFIED_BUSINESS_STATE = _shared_issue_reasons.UNCLASSIFIED_BUSINESS_STATE
    PERSONAL_TRANSACTION = _shared_issue_reasons.PERSONAL_TRANSACTION
    OUTSIDE_PERIOD = _shared_issue_reasons.OUTSIDE_PERIOD
    UNSUPPORTED_PERIOD = "unsupported_period"
    # A source-jurisdiction row outside the selected registry scope, or with
    # unresolved provenance, is segregated rather than silently admitted.
    BECKHAM_FOREIGN_SOURCE_SEGREGATED = "beckham_foreign_source_segregated"


#: The traceable-exclusion ``detail`` annotation: elides rather than refusing.
#:
#: These issues explain why a ledger row was excluded, so refusing one over its
#: length would drop the explanation for the exclusion AND fail the aggregation
#: that produced it -- a silent under-declaration dressed as a validation error.
#: Shortening the sentence is strictly the lesser loss.


class ImpatriadoIncomeLedgerAggregationIssue(BaseModel):
    """Traceable exclusion emitted while aggregating impatriado income ledger rows."""

    model_config = _STRICT_FROZEN

    transaction_id: TransactionId
    reason: ImpatriadoIncomeLedgerAggregationIssueReason
    detail: IssueDetail
    # The rejected ISO 3166-1 alpha-2 source-jurisdiction code for a
    # BECKHAM_FOREIGN_SOURCE_SEGREGATED row; ``None`` when the row carried no
    # declared jurisdiction (the unresolved case), so an auditor can tell a
    # foreign-source segregation apart from an unresolved-provenance one.
    rejected_source_jurisdiction: str | None = None


class ImpatriadoIncomeObservation(BaseModel):
    """One eligible INCOMING income ledger row for the selected registry target.

    Carries the typed gross amount and selected target casilla. The registry
    resolver sums the fiscally computable amount (``taxable_base_amount`` when
    the row carries an explicit IVA tagging, else ``gross_amount``) across the
    observations for that target.

    ``source_jurisdiction`` is retained for provenance after source-scope
    membership has been resolved by the selected registry revision.
    """

    model_config = _STRICT_FROZEN

    transaction_id: TransactionId
    target_casilla_id: CasillaId
    gross_amount: Decimal = Field(ge=Decimal("0"))
    taxable_base_amount: Decimal | None = Field(default=None, ge=Decimal("0"))
    filing_date: date
    source_jurisdiction: CountryCodeAlpha2


class ImpatriadoIncomeLedgerAggregation(
    LedgerAggregationResultBase[ImpatriadoIncomeObservation, ImpatriadoIncomeLedgerAggregationIssue],
):
    """Annual income observations for one selected filing revision.

    ``out_of_window_summary`` is populated by repository-backed date partitions.
    Full-catalogue aggregation keeps row-level issues because every transaction
    is already loaded for classification.
    """

    out_of_window_summary: OutOfWindowTransactionSummary | None = None


def aggregate_impatriado_income_ledger_from_repositories(
    *,
    bucket_id: str,
    period: Period,
    modelo: str,
    target_casilla_id: CasillaId,
    source_jurisdictions: frozenset[str],
    eligible_income_categories: frozenset[str],
    transaction_repository: TransactionCatalogueRepositoryProtocol | None = None,
) -> ImpatriadoIncomeLedgerAggregation:
    """Load the transaction catalogue and aggregate annual registry-admitted income.

    When no protocol-compatible repository override is supplied, this loader uses
    :class:`~adapters.persistence.profile.transactions.TransactionCatalogueRepository` scoped to
    ``bucket_id``.

    Returns an :class:`ImpatriadoIncomeLedgerAggregation`.
    """
    repository = transaction_repository or TransactionCatalogueRepository(bucket_id=bucket_id)
    if repository.bucket_id != bucket_id:
        raise AggregationValidationError(
            t("aggregation.renta_ledger.errors.bucket_mismatch"),
            context={"bucket_id": bucket_id, "repository_bucket_id": repository.bucket_id},
        )
    # Only the in-window ejercicio subset is decrypted and classified. The
    # out-of-window remainder comes from the plaintext date index and is
    # reported uniformly as ``OUTSIDE_PERIOD``. Non-annual periods fall back to
    # the unfiltered load so the aggregation's own period validation still
    # raises the same error.
    if period.kind is not PeriodKind.ANNUAL:
        return aggregate_impatriado_income_ledger(
            repository.load(),
            bucket_id=bucket_id,
            period=period,
            modelo=modelo,
            target_casilla_id=target_casilla_id,
            source_jurisdictions=source_jurisdictions,
            eligible_income_categories=eligible_income_categories,
        )
    partition = repository.partition_by_date_range(period.start_date, period.end_date)
    result = aggregate_impatriado_income_ledger(
        partition.in_window,
        bucket_id=bucket_id,
        period=period,
        modelo=modelo,
        target_casilla_id=target_casilla_id,
        source_jurisdictions=source_jurisdictions,
        eligible_income_categories=eligible_income_categories,
    )
    out_of_window_summary = partition.out_of_window_summary or OutOfWindowTransactionSummary.from_index_entries(
        partition.out_of_window,
    )
    return result.model_copy(
        update={"out_of_window_summary": out_of_window_summary},
    )


def aggregate_impatriado_income_ledger(
    transactions: TransactionCatalogue,
    *,
    bucket_id: str,
    period: Period,
    modelo: str,
    target_casilla_id: CasillaId,
    source_jurisdictions: frozenset[str],
    eligible_income_categories: frozenset[str],
) -> ImpatriadoIncomeLedgerAggregation:
    """Aggregate INCOMING income into the selected registry target.

    Applies the selected source scope over the full annual period. Only rows
    admitted by the selected registry jurisdiction and category declarations
    fold into the selected target. Out-of-scope and unresolved rows are
    segregated into typed issues rather than silently entering or disappearing
    from the aggregate.

    Args:
        transactions: The :class:`TransactionCatalogue` to aggregate.
        bucket_id: Bucket identifier carried through to provenance so the
            aggregation cannot be silently misattributed.
        period: The annual :class:`Period` whose year anchors the window.
        modelo: Selected registry model identifier.
        target_casilla_id: Selected registry target identifier.
        source_jurisdictions: Selected registry source-scope membership.
        eligible_income_categories: Selected registry income-category membership.

    Returns an :class:`ImpatriadoIncomeLedgerAggregation` for the ejercicio.
    ``period`` must be the annual period.
    """
    if period.kind is not PeriodKind.ANNUAL:
        raise AggregationPeriodError(
            t("aggregation.renta_ledger.errors.unsupported_period"),
            context={"period": str(period)},
        )
    # The one boundary authority, not a second derivation of it: the repository
    # partition above already selects on ``period.start_date``/``period.end_date``,
    # and this filter re-checks the rows that partition returned. Deriving the
    # same span a second time from the calendar year would make the two agree by
    # coincidence rather than by construction.
    window_start = period.start_date
    window_end = period.end_date

    observations: list[ImpatriadoIncomeObservation] = []
    issues: list[ImpatriadoIncomeLedgerAggregationIssue] = []
    for transaction in transactions.values():
        if transaction.lifecycle_state is not TransactionLifecycleState.ACTIVE:
            continue
        outcome = _classify_impatriado_income_transaction(
            transaction,
            window_start=window_start,
            window_end=window_end,
            target_casilla_id=target_casilla_id,
            source_jurisdictions=source_jurisdictions,
            eligible_income_categories=eligible_income_categories,
        )
        if outcome is None:
            continue
        if isinstance(outcome, ImpatriadoIncomeLedgerAggregationIssue):
            issues.append(outcome)
        else:
            observations.append(outcome)

    casilla_aggregation = _impatriado_base_casilla_aggregation(modelo, period, observations)
    return ImpatriadoIncomeLedgerAggregation(
        modelo=modelo,
        period=period,
        observations=tuple(observations),
        issues=tuple(issues),
        casilla_aggregation=casilla_aggregation,
    )


def _classify_impatriado_income_transaction(
    transaction: Transaction,
    *,
    window_start: date,
    window_end: date,
    target_casilla_id: CasillaId,
    source_jurisdictions: frozenset[str],
    eligible_income_categories: frozenset[str],
) -> ImpatriadoIncomeObservation | ImpatriadoIncomeLedgerAggregationIssue | None:
    """Filter one ledger transaction against the selected registry income scope.

    Returns an :class:`ImpatriadoIncomeObservation` for an admitted receipt, an
    :class:`ImpatriadoIncomeLedgerAggregationIssue` for a row that fails a gate,
    or ``None`` for a row this pipeline does not own.

    The source-jurisdiction gate runs before amount/eligibility gates so an
    out-of-scope or unresolved row is always segregated as a typed issue.
    """
    transaction_id = transaction.transaction_id

    if not _impatriado_transaction_is_in_scope(transaction):
        return None
    if is_non_eur_without_conversion(transaction):
        return ImpatriadoIncomeLedgerAggregationIssue(
            transaction_id=transaction_id,
            reason=ImpatriadoIncomeLedgerAggregationIssueReason.UNSUPPORTED_CURRENCY,
            detail=f"transaction currency {transaction.raw.currency!r} is not supported for impatriado income",
        )

    source_issue = _impatriado_source_issue(
        transaction,
        transaction_id=transaction_id,
        source_jurisdictions=source_jurisdictions,
    )
    if source_issue is not None:
        return source_issue

    proportion = _impatriado_income_proportion(transaction, eligible_income_categories)
    if proportion is None:
        return _impatriado_business_issue(transaction, transaction_id=transaction_id)
    # Use the EUR projection after rejecting unconverted non-EUR rows above, so a
    # converted foreign-currency receipt contributes its EUR equivalent while a
    # domestic row retains its raw amount (mirrors the expense pipeline's
    # ``effective_eur_amount`` usage in ``renta_ledger.py``).
    gross_amount = effective_eur_amount(transaction) * proportion

    filing_date = transaction.raw.value_date or transaction.raw.booked_date
    if not (window_start <= filing_date <= window_end):
        return ImpatriadoIncomeLedgerAggregationIssue(
            transaction_id=transaction_id,
            reason=ImpatriadoIncomeLedgerAggregationIssueReason.OUTSIDE_PERIOD,
            detail=f"filing date {filing_date} is outside the annual impatriado income window",
        )

    # Scaled by the SAME proportion the gross above carries, never a second
    # decision. The two figures describe one receipt, and since
    # ``_computable_impatriado_income_amount`` PREFERS the base when it is
    # present, a rule that divided the base alone would silently declare a
    # fraction of an income the gross reported whole.
    # ``transaction.taxable_base`` is native-currency (see
    # ``domain.transactions.tests.test_gross_invariant``), so the EUR-equivalent
    # accessor applies the same fx_rate projection the gross above received.
    taxable_base_amount: Decimal | None = effective_eur_taxable_base(transaction)
    if taxable_base_amount is not None:
        taxable_base_amount *= proportion

    normalized_jurisdiction = transaction.source_jurisdiction.strip().upper()
    return ImpatriadoIncomeObservation(
        transaction_id=transaction_id,
        target_casilla_id=target_casilla_id,
        gross_amount=gross_amount,
        taxable_base_amount=taxable_base_amount,
        filing_date=filing_date,
        source_jurisdiction=normalized_jurisdiction,
    )


def _impatriado_transaction_is_in_scope(transaction: Transaction) -> bool:
    """Return whether the row is owned by the impatriado income pipeline."""
    if transaction.business_classification is BusinessClassification.REVIEWED_EXCLUDED:
        # Operator reviewed and deliberately excluded this row from filing.
        return False
    # Only INCOMING income folds into the impatriado base. OUTGOING and
    # internal-transfer rows are out of scope for the base.
    return transaction.direction is TransactionDirection.INCOMING


def _impatriado_source_issue(
    transaction: Transaction,
    *,
    transaction_id: str,
    source_jurisdictions: frozenset[str],
) -> ImpatriadoIncomeLedgerAggregationIssue | None:
    """Return the selected-registry source-jurisdiction issue, if any."""
    declared_jurisdiction = transaction.source_jurisdiction
    if declared_jurisdiction is None:
        return ImpatriadoIncomeLedgerAggregationIssue(
            transaction_id=transaction_id,
            reason=ImpatriadoIncomeLedgerAggregationIssueReason.BECKHAM_FOREIGN_SOURCE_SEGREGATED,
            detail=(
                "source_jurisdiction is unresolved (None) on an impatriado income row; "
                "source-scope membership must be resolved from the selected registry revision"
            ),
            rejected_source_jurisdiction=None,
        )
    normalized_jurisdiction = declared_jurisdiction.strip().upper()
    normalized_source_jurisdictions = {value.strip().upper() for value in source_jurisdictions}
    if normalized_jurisdiction in normalized_source_jurisdictions:
        return None
    return ImpatriadoIncomeLedgerAggregationIssue(
        transaction_id=transaction_id,
        reason=ImpatriadoIncomeLedgerAggregationIssueReason.BECKHAM_FOREIGN_SOURCE_SEGREGATED,
        detail=(f"source_jurisdiction {normalized_jurisdiction!r} is outside the selected registry source scope"),
        rejected_source_jurisdiction=normalized_jurisdiction,
    )


def _impatriado_business_issue(
    transaction: Transaction,
    *,
    transaction_id: str,
) -> ImpatriadoIncomeLedgerAggregationIssue:
    """Return the typed issue for an income row without business attribution."""
    reason = (
        ImpatriadoIncomeLedgerAggregationIssueReason.PERSONAL_TRANSACTION
        if transaction.business_classification is BusinessClassification.PERSONAL
        else ImpatriadoIncomeLedgerAggregationIssueReason.UNCLASSIFIED_BUSINESS_STATE
    )
    return ImpatriadoIncomeLedgerAggregationIssue(
        transaction_id=transaction_id,
        reason=reason,
        detail=(
            f"business classification {transaction.business_classification.value!r} cannot feed the selected registry target"
        ),
    )


def _impatriado_income_proportion(
    transaction: Transaction,
    eligible_income_categories: frozenset[str],
) -> Decimal | None:
    """Return the share of one row admitted by the registry, or ``None``.

    The single proportion decision for the row: every money figure the
    observation carries is scaled by this one value, so the gross and the
    taxable base cannot disagree about how much of the receipt the target admits.

    Categories selected by the registry are admitted at full magnitude. Other
    rows are admitted only through their business proportion, so a genuinely
    personal transfer contributes nothing.
    """
    normalized_category = (
        transaction.irpf_category.strip().casefold() if transaction.irpf_category is not None else None
    )
    normalized_eligible_categories = {value.strip().casefold() for value in eligible_income_categories}
    if normalized_category in normalized_eligible_categories:
        return Decimal("1")
    return business_proportion(transaction.business_classification, transaction.business_pct)


def _computable_impatriado_income_amount(observation: ImpatriadoIncomeObservation) -> Decimal:
    """Return the fiscally computable amount for one observation.

    IVA-exclusive ``taxable_base_amount`` when the row carries an explicit IVA
    tagging, falling back to ``gross_amount`` when no base is declared. The
    selected registry binding owns the destination semantics.
    """
    if observation.taxable_base_amount is not None:
        return observation.taxable_base_amount
    return observation.gross_amount


def _impatriado_base_casilla_aggregation(
    modelo: str,
    period: Period,
    observations: Sequence[ImpatriadoIncomeObservation],
) -> CasillaAggregation:
    return fold_casilla_observations(
        observations,
        modelo=modelo,
        period=period,
        amount_fn=_computable_impatriado_income_amount,
    )


__all__ = [
    "ImpatriadoIncomeLedgerAggregation",
    "ImpatriadoIncomeLedgerAggregationIssue",
    "ImpatriadoIncomeLedgerAggregationIssueReason",
    "ImpatriadoIncomeObservation",
    "aggregate_impatriado_income_ledger",
    "aggregate_impatriado_income_ledger_from_repositories",
]
