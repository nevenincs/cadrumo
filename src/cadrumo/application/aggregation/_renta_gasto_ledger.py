"""Repository-backed Renta deductible-expense (gasto) aggregation for Modelo 130.

Loads ledger rows through
:class:`~adapters.persistence.profile.transactions.TransactionCatalogueRepository`.

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

Only ACTIVE, EUR-denominated, OUTGOING transactions whose explicit
``irpf_category`` marks ``actividad_economica`` or whose
``business_classification`` is BUSINESS or MIXED are eligible. The deductible
amount is the IVA-exclusive base imponible (``taxable_base``), plus the
non-recoverable share of ``iva_amount`` when the activity's IVA-deduction ratio
(:func:`~._renta_ledger._resolve_iva_deduction_ratio` -- the SAME resolver the
M100 annual first slice uses, for the SAME ejercicio, so the two filings cannot
diverge) is less than full: IVA soportado a taxpayer cannot recover through
Modelo 303 is PGC NRV 12.ª acquisition cost, same as the M100 side (LIRPF arts.
28-30 base-imponible deductibility governs the pago fraccionado's gasto
determination identically to the annual declaration). A declarable expense
without ``taxable_base`` is surfaced as ``missing_taxable_base`` instead of being
gross-folded into casilla 02. A MIXED transaction contributes its business
fraction.

This module deliberately does NOT reuse the Modelo 100 first-slice expense
pipeline (:mod:`~._renta_ledger`): that path layers invoice-evidence
reconciliation, category-profile deductibility evaluation, and an annual window
that are constraint-shape-divergent from the M130 quarterly cumulative gasto sum.
It DOES share that module's single IVA-deduction-ratio resolver
(:func:`~._renta_ledger._resolve_iva_deduction_ratio`), the one taxpayer-fact
lookup the two constraint-shapes have no reason to diverge on.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import date
from decimal import Decimal
from enum import StrEnum
from typing import Annotated

from pydantic import BaseModel, Field

from ...adapters.persistence.profile.transactions import TransactionCatalogueRepository
from ...core import STRICT_FROZEN_CONFIG as _STRICT_FROZEN
from ...core import Modelo, Period
from ...core.casilla_id import CasillaId, validated_casilla_id
from ...core.prose_elision import ElidedProse
from ...core.identity import TransactionId
from ...domain.prorrata_register import ProrrataRegisterRepositoryProtocol
from ...domain.transactions.enums import BusinessClassification, TransactionDirection, TransactionLifecycleState
from ...domain.transactions.models import OutOfWindowTransactionSummary, Transaction, TransactionCatalogue
from ...domain.transactions.protocols import TransactionCatalogueRepositoryProtocol
from ...domain.user_profile.values import UserProfileRecord
from . import _shared_issue_reasons
from ._currency_predicates import (
    effective_eur_iva_amount,
    effective_eur_taxable_base,
    is_non_eur_without_conversion,
)
from ._grouping import cumulative_year_to_date_window, fold_casilla_observations
from ._models import CasillaAggregation, LedgerAggregationResultBase
from ._renta_business_eligibility import renta_expense_business_proportion

# Intra-package reuse of the sibling ledger's ratio resolver, permitted by the
# architecture rule; the cross-package boundary is enforced elsewhere.
from ._renta_ledger import _resolve_iva_deduction_ratio  # pyright: ignore[reportPrivateUsage]
from .errors import AggregationValidationError, t

# The only casilla M130 deductible-expense aggregation feeds: official box 02
# ("Gastos"), bound to the ledger renta gasto aggregation. Operator-supplied
# non-ledger gastos (amortizaciones, the estimación directa simplificada 5%
# gastos de difícil justificación, cash-paid expenses) are a documented
# follow-up (an operator adjustment folded into box 02) — see the F1 finding.
_TARGET_CASILLA_GASTOS: CasillaId = validated_casilla_id("02", surface="_TARGET_CASILLA_GASTOS")


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


#: The traceable-exclusion ``detail`` annotation: elides rather than refusing.
#:
#: These issues explain why a ledger row was excluded, so refusing one over its
#: length would drop the explanation for the exclusion AND fail the aggregation
#: that produced it -- a silent under-declaration dressed as a validation error.
#: Shortening the sentence is strictly the lesser loss.
_IssueDetail = Annotated[str, ElidedProse(512)]


class RentaGastoLedgerAggregationIssue(BaseModel):
    """Traceable exclusion emitted while aggregating gasto ledger rows."""

    model_config = _STRICT_FROZEN

    transaction_id: TransactionId
    reason: RentaGastoLedgerAggregationIssueReason
    detail: _IssueDetail


class RentaGastoObservation(BaseModel):
    """One eligible OUTGOING deductible-expense ledger row.

    Carries the typed deductible amount and the target casilla id it feeds. The
    domain registry resolver matches ``target_casilla_id`` against the binding
    selector and sums ``deductible_amount`` across all observations for that
    casilla, mirroring the income resolver's casilla-keyed fold.

    ``deductible_amount`` is the IVA-exclusive base imponible
    (``transaction.taxable_base``) when the row carries an explicit IVA tagging,
    falling back to the gross transfer amount when no base is declared, and
    scaled by the business fraction for MIXED transactions.
    """

    model_config = _STRICT_FROZEN

    transaction_id: TransactionId
    target_casilla_id: CasillaId
    deductible_amount: Decimal = Field(ge=Decimal("0"))
    filing_date: date


class RentaGastoLedgerAggregation(
    LedgerAggregationResultBase[RentaGastoObservation, RentaGastoLedgerAggregationIssue],
):
    """Cumulative deductible-expense observations for one M130 quarter window.

    ``out_of_window_summary`` is populated by repository-backed date partitions.
    Full-catalogue aggregation keeps row-level issues because every transaction
    is already loaded for classification.
    """

    out_of_window_summary: OutOfWindowTransactionSummary | None = None


def aggregate_renta_gasto_ledger_from_repositories(
    *,
    bucket_id: str,
    period: Period,
    transaction_repository: TransactionCatalogueRepositoryProtocol | None = None,
    profile_record: UserProfileRecord | None = None,
    prorrata_register_repository: ProrrataRegisterRepositoryProtocol,
) -> RentaGastoLedgerAggregation:
    """Load the transaction catalogue and aggregate cumulative M130 gastos.

    Derives the activity's IVA-deduction ratio through
    :func:`~._renta_ledger._resolve_iva_deduction_ratio` -- the SAME resolver the
    M100 annual first slice uses, for the SAME ejercicio (``period.filing_year``),
    so the two filings cannot diverge on it. ``profile_record`` (a
    :class:`UserProfileRecord`) and ``prorrata_register_repository`` supply the
    profile and canonical register directly.

    Returns a :class:`RentaGastoLedgerAggregation`.
    """
    repository = transaction_repository or TransactionCatalogueRepository(bucket_id=bucket_id)
    if repository.bucket_id != bucket_id:
        raise AggregationValidationError(
            t("aggregation.renta_ledger.errors.bucket_mismatch"),
            context={"bucket_id": bucket_id, "repository_bucket_id": repository.bucket_id},
        )
    # Only the cumulative in-window subset is decrypted and classified. The
    # out-of-window remainder comes from the plaintext date index and is
    # reported uniformly as ``OUTSIDE_PERIOD``.
    window = cumulative_year_to_date_window(period)
    partition = repository.partition_by_date_range(window.start, window.end)
    iva_deduction_ratio = _resolve_iva_deduction_ratio(
        bucket_id=bucket_id,
        ejercicio=period.filing_year,
        profile_record=profile_record,
        prorrata_register_repository=prorrata_register_repository,
    )
    result = aggregate_renta_gasto_ledger(
        partition.in_window,
        bucket_id=bucket_id,
        period=period,
        iva_deduction_ratio=iva_deduction_ratio,
    )
    out_of_window_summary = partition.out_of_window_summary or OutOfWindowTransactionSummary.from_index_entries(
        partition.out_of_window,
    )
    return result.model_copy(
        update={"out_of_window_summary": out_of_window_summary},
    )


def aggregate_renta_gasto_ledger(
    transactions: TransactionCatalogue,
    *,
    bucket_id: str,
    period: Period,
    iva_deduction_ratio: Decimal | None = None,
) -> RentaGastoLedgerAggregation:
    """Aggregate OUTGOING deductible-expense transactions into M130 casilla 02.

    Args:
        transactions: The :class:`TransactionCatalogue` of ledger transactions to aggregate.
        bucket_id: Bucket identifier carried through to provenance and audit
            records so the resulting aggregation cannot be silently misattributed.
        period: The quarterly :class:`Period` whose year anchors the cumulative
            window.
        iva_deduction_ratio: Optional activity-wide IVA-deduction fraction (LIVA
            arts. 94/104), joining the non-recoverable share of a row's
            ``iva_amount`` to its deductible base (PGC NRV 12.ª). ``None`` (the
            default) preserves the historic base-only behaviour.

    Returns a :class:`RentaGastoLedgerAggregation` covering the cumulative
    fiscal window. ``period`` must be quarterly; the cumulative window extends
    from Jan 1 of the period's year through the last day of the declared quarter
    (RD 439/2007 art. 110.2).
    """
    window = cumulative_year_to_date_window(period)

    observations: list[RentaGastoObservation] = []
    issues: list[RentaGastoLedgerAggregationIssue] = []

    for transaction in transactions.values():
        if transaction.lifecycle_state is not TransactionLifecycleState.ACTIVE:
            continue
        outcome = _classify_gasto_transaction(
            transaction,
            cumulative_start=window.start,
            cumulative_end=window.end,
            iva_deduction_ratio=iva_deduction_ratio,
        )
        if outcome is None:
            continue
        if isinstance(outcome, RentaGastoLedgerAggregationIssue):
            issues.append(outcome)
        else:
            observations.append(outcome)

    casilla_aggregation = _gasto_casilla_aggregation(window.period, observations)
    return RentaGastoLedgerAggregation(
        modelo=Modelo.M130.value,
        period=window.period,
        observations=tuple(observations),
        issues=tuple(issues),
        casilla_aggregation=casilla_aggregation,
    )


def _classify_gasto_transaction(
    transaction: Transaction,
    *,
    cumulative_start: date,
    cumulative_end: date,
    iva_deduction_ratio: Decimal | None = None,
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

    if transaction.business_classification is BusinessClassification.REVIEWED_EXCLUDED:
        # Operator reviewed and deliberately excluded this row from filing. Keep
        # that final disposition stronger than the actividad category tag.
        return None

    # PERSONAL / unclassified OUTGOING rows are not deductible gastos unless an
    # explicit actividad-economica IRPF category already marks the row as part of
    # the M130 activity set. Only rows that should be deductible but are dropped
    # by a downstream gate (currency / period / missing taxable_base) surface an
    # issue, so the operator sees a genuinely lost gasto rather than advisory
    # noise on every personal line.
    proportion = _gasto_business_proportion(transaction)
    if proportion is None:
        return None

    if is_non_eur_without_conversion(transaction):
        return RentaGastoLedgerAggregationIssue(
            transaction_id=transaction_id,
            reason=RentaGastoLedgerAggregationIssueReason.UNSUPPORTED_CURRENCY,
            detail=f"transaction currency {transaction.raw.currency!r} is not supported for Renta gastos",
        )

    filing_date = transaction.raw.value_date or transaction.raw.booked_date
    if not (cumulative_start <= filing_date <= cumulative_end):
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
    # for the None case). IVA soportado recovered through Modelo 303 is not a
    # Renta gasto, so the IVA-exclusive base imponible is the deductible gasto by
    # default. When the activity's IVA-deduction ratio is known and less than
    # full, the non-recoverable share of iva_amount joins the base (PGC NRV
    # 12.ª) -- mirroring domain.renta._ledger_expenses._deductible_basis_amount
    # on the M100 side exactly: only when BOTH iva_amount and the ratio are
    # known, else the historic base-only figure stands. The whole sum is then
    # scaled by the business fraction (1 for BUSINESS, business_pct for MIXED).
    #
    # Both taxable_base and iva_amount are denominated in the row's NATIVE
    # currency (see domain.transactions.tests.test_gross_invariant), so a
    # converted foreign-currency row must go through the EUR-equivalent
    # accessors -- summing them raw would fold a native-currency figure into
    # a EUR-denominated casilla 02 total.
    deductible_base = effective_eur_taxable_base(transaction)
    # taxable_base is non-None here (the MISSING_TAXABLE_BASE guard above
    # returned for the None case), so the EUR-equivalent accessor cannot
    # return None either -- it is None only when its input is.
    assert deductible_base is not None
    eur_iva_amount = effective_eur_iva_amount(transaction)
    if eur_iva_amount is not None and iva_deduction_ratio is not None:
        deductible_base += eur_iva_amount * (Decimal("1") - iva_deduction_ratio)
    deductible_amount = deductible_base * proportion
    return RentaGastoObservation(
        transaction_id=transaction_id,
        target_casilla_id=_TARGET_CASILLA_GASTOS,
        deductible_amount=deductible_amount,
        filing_date=filing_date,
    )


def _gasto_business_proportion(transaction: Transaction) -> Decimal | None:
    """Return the business-attributed gasto proportion, or None if not eligible.

    Thin adapter over the shared
    :func:`~._renta_business_eligibility.renta_expense_business_proportion`
    predicate, requested with ``accept_activity_marker=True``: the M130 pago
    fraccionado is a provisional self-assessment, so an explicit
    ``actividad_economica`` IRPF category establishes full business attribution
    before the broader business-classification sweep has resolved the row. The
    annual Modelo 100 projection consumes the SAME predicate with the marker
    refused, so the two pipelines can no longer drift apart. Reviewed
    exclusions are short-circuited by the caller before reaching this helper.
    """
    return renta_expense_business_proportion(transaction, accept_activity_marker=True)


def _gasto_casilla_aggregation(
    period: Period,
    observations: Sequence[RentaGastoObservation],
) -> CasillaAggregation:
    return fold_casilla_observations(
        observations,
        modelo=Modelo.M130.value,
        period=period,
        amount_fn=lambda observation: observation.deductible_amount,
    )


__all__ = [
    "RentaGastoLedgerAggregation",
    "RentaGastoLedgerAggregationIssue",
    "RentaGastoLedgerAggregationIssueReason",
    "RentaGastoObservation",
    "aggregate_renta_gasto_ledger",
    "aggregate_renta_gasto_ledger_from_repositories",
]
