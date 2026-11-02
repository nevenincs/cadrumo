"""Repository-backed Renta activity-income aggregation.

This module owns the generic ledger projection and period/window mechanics.
The selected filing's model, target casilla, activity selectors, and binding
applicability are supplied by the registry boundary by callers; no filing
declaration is embedded here.

The quarterly entry point :func:`aggregate_renta_income_ledger_from_repositories`
loads a :class:`~domain.transactions.models.TransactionCatalogue` and its linked invoice
catalogue through the application-owned catalogue read capabilities, then
delegates to :func:`aggregate_renta_income_ledger` for period-scoped aggregation.

The annual counterpart uses the same generic projection over its requested
window. A separate caller supplies its target and model identity.

Cumulative window rule (RD 439/2007 art. 110.2):
  For period Qn in year Y the window is [Jan 1, Y] through [last day of Qn, Y].
  Q1 covers Jan-Mar; Q2 covers Jan-Jun; Q3 covers Jan-Sep; Q4 covers Jan-Dec.

Only ACTIVE, EUR-denominated, INCOMING transactions whose
``business_classification`` is BUSINESS or MIXED are eligible. Transactions
whose ``value_date`` (or ``booked_date`` if absent) falls outside the
cumulative window are excluded with a traceable issue record.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from datetime import date
from decimal import Decimal
from typing import NamedTuple

from ...core.aggregation import LedgerIncomeGrounding
from ...core.casilla_id import CasillaId
from ...core.i18n.translatable import Translatable as tr
from ...core.period import Period, PeriodKind
from ...core.tipos_actividad import TipoActividad
from ...domain.calculations.registry.authority import PinnedAuthorityOperation
from ...domain.invoices.catalogue import InvoiceCatalogue
from ...domain.invoices.models import Invoice
from ...domain.iva.schema import InvoiceKind
from ...domain.transactions.date_partition import OutOfWindowTransactionSummary
from ...domain.transactions.enums import BusinessClassification, TransactionDirection, TransactionLifecycleState
from ...domain.transactions.models import Transaction, TransactionCatalogue
from ..invoices.catalogue_reads_ports import InvoiceCatalogueReadPorts
from ..invoices.source_observations import is_rectificativa
from . import _shared_issue_reasons, renta_income_evidence
from ._grouping import cumulative_year_to_date_window, fold_casilla_observations
from ._models import CasillaAggregation, LedgerAggregationResultBase
from ._renta_business_eligibility import is_supplier_refund
from .business_proportion import business_proportion
from .catalogue_read_binding import require_catalogue_reads_bound_to
from .concepto_ingreso_admission import row_counts_toward_volumen_de_ingresos
from .currency_predicates import effective_eur_amount, effective_eur_taxable_base, is_non_eur_without_conversion
from .errors import AggregationPeriodError
from .renta_imputation import (
    ActivityImputationCriterion,
    ImputationCriteria,
    ImputationUnresolved,
    accrual_entry_date,
    impute_ledger_row,
    linked_accrual_date,
    rows_left_out_summary,
    rows_touching_window,
)
from .renta_income_diagnostics import (
    RectificativaReading,
    accrued_unpaid_income,
    accrued_without_eur_value,
    overpaid_invoice_issues,
    rectificativa_reading,
)
from .renta_income_models import (
    AccruedUnpaidIncome,
    RectificativaCorrection,
    RentaIncomeLedgerAggregationIssue,
    RentaIncomeLedgerAggregationIssueReason,
    RentaIncomeObservation,
    UnadmittedActivityIncome,
)

# Registry authority: selected Renta income model, target, selector, and binding
# declarations are consumed through RegistryQueryService


_CAPITAL_SUBSIDY_CONCEPT = "subvencion_capital"


class RentaIncomeLedgerAggregation(
    LedgerAggregationResultBase[RentaIncomeObservation, RentaIncomeLedgerAggregationIssue],
):
    """Cumulative income observations for one selected quarter window.

    ``out_of_window_summary`` is populated by repository-backed date partitions.
    Full-catalogue aggregation keeps row-level issues because every transaction
    is already loaded for classification.

    ``unadmitted_activity_income`` is populated only by a projection that
    NARROWS rows by activity when requested. ``None`` on an un-narrowed path states
    that no narrowing ran, which is
    not the same claim as a narrowing that excluded nothing, and the two must
    stay distinguishable: the second is a fact about this taxpayer's ledger, the
    first is a fact about which projection was asked for.
    """

    out_of_window_summary: OutOfWindowTransactionSummary | None = None
    unadmitted_activity_income: UnadmittedActivityIncome | None = None
    accrued_unpaid: tuple[AccruedUnpaidIncome, ...] = ()
    accrued_without_eur_value: tuple[str, ...] = ()
    """The numbers of the issued invoices that accrue unsettled with no EUR value to count."""
    rectificativa_corrections: tuple[RectificativaCorrection, ...] = ()
    rectificativa_refused: tuple[str, ...] = ()
    """Why each correction accruing in the window could not be placed."""


def _load_income_invoices(
    *,
    ports: InvoiceCatalogueReadPorts,
) -> InvoiceCatalogue:
    """Load the bucket's invoice catalogue for sales-invoice evidence.

    Every repository-backed income entry point calls this, and all must: the
    single production call site chooses between the quarterly and annual
    aggregators, so threading one and not the others would leave the paths
    grounding differently -- the asymmetry this evidence path exists to remove.
    """
    return ports.invoice_reader.load()


def aggregate_renta_income_ledger_from_repositories(
    *,
    bucket_id: str,
    period: Period,
    modelo: str,
    target_casilla_id: CasillaId,
    activity_category_matcher: Callable[[Transaction], bool],
    employment_category_matcher: Callable[[Transaction], bool],
    ports: InvoiceCatalogueReadPorts,
    criteria: ImputationCriteria | None = None,
) -> RentaIncomeLedgerAggregation:
    """Load the transaction catalogue and aggregate a cumulative income window.

    With ``criteria`` a row's date may be its invoice's, so the whole catalogue
    is read; without them the window's bank rows are.

    Returns a :class:`RentaIncomeLedgerAggregation`.
    """
    require_catalogue_reads_bound_to(ports, bucket_id=bucket_id)
    invoices = _load_income_invoices(ports=ports)
    if criteria is not None:
        window = cumulative_year_to_date_window(period)
        whole_catalogue = ports.transaction_reader.load()
        touching = rows_touching_window(
            whole_catalogue,
            invoices,
            kind=InvoiceKind.ISSUED,
            invoice_id_of=lambda row: row.invoice_id,
            start=window.start,
            end=window.end,
            criteria=criteria,
        )
        return aggregate_renta_income_ledger(
            touching,
            invoices,
            bucket_id=bucket_id,
            period=period,
            modelo=modelo,
            target_casilla_id=target_casilla_id,
            activity_category_matcher=activity_category_matcher,
            employment_category_matcher=employment_category_matcher,
            criteria=criteria,
        ).model_copy(update={"out_of_window_summary": rows_left_out_summary(whole_catalogue, touching)})
    # Only the cumulative in-window subset is decrypted and classified. The
    # out-of-window remainder comes from the plaintext date index and is
    # reported uniformly as ``OUTSIDE_PERIOD``.
    window = cumulative_year_to_date_window(period)
    partition = ports.transaction_reader.partition_by_date_range(window.start, window.end)
    result = aggregate_renta_income_ledger(
        partition.in_window,
        invoices,
        bucket_id=bucket_id,
        period=period,
        modelo=modelo,
        target_casilla_id=target_casilla_id,
        activity_category_matcher=activity_category_matcher,
        employment_category_matcher=employment_category_matcher,
    )
    out_of_window_summary = partition.out_of_window_summary or OutOfWindowTransactionSummary.from_index_entries(
        partition.out_of_window,
    )
    return result.model_copy(
        update={"out_of_window_summary": out_of_window_summary},
    )


def aggregate_renta_income_ledger(
    transactions: TransactionCatalogue,
    invoices: InvoiceCatalogue | None = None,
    *,
    bucket_id: str,
    period: Period,
    modelo: str,
    target_casilla_id: CasillaId,
    activity_category_matcher: Callable[[Transaction], bool],
    employment_category_matcher: Callable[[Transaction], bool],
    criteria: ImputationCriteria | None = None,
) -> RentaIncomeLedgerAggregation:
    """Aggregate incoming professional-income transactions into a selected target.

    Args:
        transactions: The :class:`TransactionCatalogue` of ledger transactions to aggregate.
        invoices: The bucket's :class:`~domain.invoices.catalogue.InvoiceCatalogue`, whose
            linked sales invoices supply the base, cuota and retención for rows
            that reference one. Optional so an in-process caller holding no
            invoices need not construct an empty catalogue; the production entry
            point above always loads and passes the real one, so the evidence
            path is wired rather than latent.
        bucket_id: Bucket identifier carried through to provenance and audit
            records so the resulting aggregation cannot be silently misattributed.
        period: The quarterly :class:`Period` whose year anchors the cumulative
            window.
        modelo: Selected model identifier receiving the aggregation.
        target_casilla_id: Registry-selected output casilla for professional income.
        activity_category_matcher: Predicate for activity-category transactions.
        employment_category_matcher: Predicate for employment-category transactions.
        criteria: The dated imputation election that places each row; ``None``
            keeps the bank date, for a caller that does not consult the profile.

    Returns a :class:`RentaIncomeLedgerAggregation` covering the
    cumulative fiscal window. ``period`` must be quarterly. The cumulative
    window extends from Jan 1 of the
    period's year through the last day of the declared quarter,
    implementing the year-to-date accumulation rule for IRPF pagos
    fraccionados (RD 439/2007 art. 110.2).
    """
    window = cumulative_year_to_date_window(period)
    resolved_invoices = invoices if invoices is not None else InvoiceCatalogue()

    observations: list[RentaIncomeObservation] = []
    issues: list[RentaIncomeLedgerAggregationIssue] = []
    receipts_by_invoice = None if criteria is None else _active_receipts_by_invoice(transactions, resolved_invoices)

    for transaction in transactions.values():
        if transaction.lifecycle_state is not TransactionLifecycleState.ACTIVE:
            continue
        outcome = _classify_income_transaction(
            transaction,
            invoices=resolved_invoices,
            receipts_by_invoice=receipts_by_invoice,
            bucket_id=bucket_id,
            cumulative_start=window.start,
            cumulative_end=window.end,
            target_casilla_id=target_casilla_id,
            activity_category_matcher=activity_category_matcher,
            employment_category_matcher=employment_category_matcher,
            criteria=criteria,
        )
        if outcome is None:
            continue
        if isinstance(outcome, RentaIncomeLedgerAggregationIssue):
            issues.append(outcome)
        else:
            observations.append(outcome)

    casilla_aggregation = _income_casilla_aggregation(
        window.period,
        observations,
        modelo=modelo,
    )
    corrected = (
        RectificativaReading()
        if criteria is None
        else rectificativa_reading(
            resolved_invoices,
            transactions,
            bucket_id=bucket_id,
            window_start=window.start,
            window_end=window.end,
            target_casilla_id=target_casilla_id,
            criteria=criteria,
        )
    )
    return RentaIncomeLedgerAggregation(
        rectificativa_corrections=corrected.corrections,
        rectificativa_refused=corrected.refused,
        modelo=modelo,
        period=window.period,
        observations=tuple(observations),
        issues=(
            *issues,
            *(
                ()
                if criteria is None
                else overpaid_invoice_issues(transactions, resolved_invoices, bucket_id=bucket_id)
            ),
        ),
        casilla_aggregation=casilla_aggregation,
        accrued_unpaid=()
        if criteria is None
        else accrued_unpaid_income(
            transactions,
            resolved_invoices,
            bucket_id=bucket_id,
            window_start=window.start,
            window_end=window.end,
            target_casilla_id=target_casilla_id,
            criteria=criteria,
        ),
        accrued_without_eur_value=()
        if criteria is None
        else accrued_without_eur_value(
            transactions,
            resolved_invoices,
            bucket_id=bucket_id,
            window_start=window.start,
            window_end=window.end,
            criteria=criteria,
        ),
    )


def aggregate_renta_m100_income_ledger_from_repositories(
    *,
    bucket_id: str,
    period: Period,
    modelo: str,
    target_casilla_id: CasillaId,
    activity_category_matcher: Callable[[Transaction], bool],
    employment_category_matcher: Callable[[Transaction], bool],
    ports: InvoiceCatalogueReadPorts,
    criteria: ImputationCriteria | None = None,
) -> RentaIncomeLedgerAggregation:
    """Load the catalogue and aggregate an annual activity-income window.

    Returns:
        The :class:`RentaIncomeLedgerAggregation` for the requested annual period.
    """
    require_catalogue_reads_bound_to(ports, bucket_id=bucket_id)
    invoices = _load_income_invoices(ports=ports)
    # Only the in-window ejercicio subset is decrypted and classified. The
    # out-of-window remainder comes from the plaintext date index and is
    # reported uniformly as ``OUTSIDE_PERIOD``. Non-annual periods fall back to
    # the unfiltered load so the aggregation's own period validation still
    # raises the same error.
    if criteria is not None:
        whole_catalogue = ports.transaction_reader.load()
        touching = rows_touching_window(
            whole_catalogue,
            invoices,
            kind=InvoiceKind.ISSUED,
            invoice_id_of=lambda row: row.invoice_id,
            start=date(period.filing_year, 1, 1),
            end=period.end_date,
            criteria=criteria,
        )
        return aggregate_renta_m100_income_ledger(
            touching,
            invoices,
            bucket_id=bucket_id,
            period=period,
            modelo=modelo,
            target_casilla_id=target_casilla_id,
            activity_category_matcher=activity_category_matcher,
            employment_category_matcher=employment_category_matcher,
            criteria=criteria,
        ).model_copy(update={"out_of_window_summary": rows_left_out_summary(whole_catalogue, touching)})
    if period.kind is not PeriodKind.ANNUAL:
        return aggregate_renta_m100_income_ledger(
            ports.transaction_reader.load(),
            invoices,
            bucket_id=bucket_id,
            period=period,
            modelo=modelo,
            target_casilla_id=target_casilla_id,
            activity_category_matcher=activity_category_matcher,
            employment_category_matcher=employment_category_matcher,
            criteria=criteria,
        )
    partition = ports.transaction_reader.partition_by_date_range(period.start_date, period.end_date)
    result = aggregate_renta_m100_income_ledger(
        partition.in_window,
        invoices,
        bucket_id=bucket_id,
        period=period,
        modelo=modelo,
        target_casilla_id=target_casilla_id,
        activity_category_matcher=activity_category_matcher,
        employment_category_matcher=employment_category_matcher,
    )
    out_of_window_summary = partition.out_of_window_summary or OutOfWindowTransactionSummary.from_index_entries(
        partition.out_of_window,
    )
    return result.model_copy(
        update={"out_of_window_summary": out_of_window_summary},
    )


def aggregate_renta_m100_income_ledger(
    transactions: TransactionCatalogue,
    invoices: InvoiceCatalogue | None = None,
    *,
    bucket_id: str,
    period: Period,
    modelo: str,
    target_casilla_id: CasillaId,
    activity_category_matcher: Callable[[Transaction], bool],
    employment_category_matcher: Callable[[Transaction], bool],
    criteria: ImputationCriteria | None = None,
) -> RentaIncomeLedgerAggregation:
    """Aggregate annual activity-income from a :class:`TransactionCatalogue` into a selected target.

    The annual counterpart of :func:`aggregate_renta_income_ledger`: it applies the
    same activity-income eligibility (excluding nómina/trabajo and personal
    flows) over the FULL ejercicio (Jan 1 to Dec 31 of ``period.filing_year``) and
    targets the caller-selected annual casilla. ``period`` must be the annual
    period. The :class:`InvoiceCatalogue`
    passed as ``invoices`` is consulted when classifying each transaction; an
    empty catalogue is used when it is omitted.

    Returns:
        The :class:`RentaIncomeLedgerAggregation` built from eligible transactions.
    """
    if period.kind is not PeriodKind.ANNUAL:
        raise AggregationPeriodError(
            tr("aggregation.renta_ledger.errors.unsupported_period"),
            context={"period": str(period)},
        )
    window_start = date(period.filing_year, 1, 1)
    window_end = date(period.filing_year, 12, 31)
    resolved_invoices = invoices if invoices is not None else InvoiceCatalogue()

    # The classifier is retargeted to the selected annual destination.
    projected = _project_income_onto_casilla(
        transactions,
        invoices=resolved_invoices,
        bucket_id=bucket_id,
        window_start=window_start,
        window_end=window_end,
        target_casilla_id=target_casilla_id,
        activity_category_matcher=activity_category_matcher,
        employment_category_matcher=employment_category_matcher,
        criteria=criteria,
    )
    observations = list(projected.observations)
    issues = list(projected.issues)

    casilla_aggregation = _m100_income_casilla_aggregation(
        period,
        observations,
        modelo=modelo,
    )
    corrected = (
        RectificativaReading()
        if criteria is None
        else rectificativa_reading(
            resolved_invoices,
            transactions,
            bucket_id=bucket_id,
            window_start=window_start,
            window_end=window_end,
            target_casilla_id=target_casilla_id,
            criteria=criteria,
        )
    )
    return RentaIncomeLedgerAggregation(
        rectificativa_corrections=corrected.corrections,
        rectificativa_refused=corrected.refused,
        modelo=modelo,
        period=period,
        observations=tuple(observations),
        issues=(
            *issues,
            *(
                ()
                if criteria is None
                else overpaid_invoice_issues(transactions, resolved_invoices, bucket_id=bucket_id)
            ),
        ),
        casilla_aggregation=casilla_aggregation,
        accrued_unpaid=()
        if criteria is None
        else accrued_unpaid_income(
            transactions,
            resolved_invoices,
            bucket_id=bucket_id,
            window_start=window_start,
            window_end=window_end,
            target_casilla_id=target_casilla_id,
            criteria=criteria,
        ),
        accrued_without_eur_value=()
        if criteria is None
        else accrued_without_eur_value(
            transactions,
            resolved_invoices,
            bucket_id=bucket_id,
            window_start=window_start,
            window_end=window_end,
            criteria=criteria,
        ),
    )


def _m100_income_casilla_aggregation(
    period: Period,
    observations: Sequence[RentaIncomeObservation],
    *,
    modelo: str,
) -> CasillaAggregation:
    return fold_casilla_observations(
        observations,
        modelo=modelo,
        period=period,
        amount_fn=_computable_income_amount,
    )


def aggregate_renta_m131_agrario_income_ledger_from_repositories(
    *,
    bucket_id: str,
    period: Period,
    modelo: str,
    target_casilla_id: CasillaId,
    agrarian_activity_codes: frozenset[TipoActividad],
    activity_category_matcher: Callable[[Transaction], bool],
    employment_category_matcher: Callable[[Transaction], bool],
    ports: InvoiceCatalogueReadPorts,
    operation: PinnedAuthorityOperation,
) -> RentaIncomeLedgerAggregation:
    """Load the catalogue and aggregate a selected activity-narrowed quarter.

    Returns:
        The :class:`RentaIncomeLedgerAggregation` for the requested quarter.
    """
    require_catalogue_reads_bound_to(ports, bucket_id=bucket_id)
    invoices = _load_income_invoices(ports=ports)
    return aggregate_renta_m131_agrario_income_ledger(
        ports.transaction_reader.load(),
        invoices,
        bucket_id=bucket_id,
        period=period,
        modelo=modelo,
        target_casilla_id=target_casilla_id,
        agrarian_activity_codes=agrarian_activity_codes,
        activity_category_matcher=activity_category_matcher,
        employment_category_matcher=employment_category_matcher,
        operation=operation,
    )


def aggregate_renta_m131_agrario_income_ledger(
    transactions: TransactionCatalogue,
    invoices: InvoiceCatalogue | None = None,
    *,
    bucket_id: str,
    period: Period,
    modelo: str,
    target_casilla_id: CasillaId,
    agrarian_activity_codes: frozenset[TipoActividad],
    activity_category_matcher: Callable[[Transaction], bool],
    employment_category_matcher: Callable[[Transaction], bool],
    operation: PinnedAuthorityOperation,
) -> RentaIncomeLedgerAggregation:
    """Aggregate an activity-narrowed quarterly income volume into a target.

    Two filters separate this narrowed projection from an un-narrowed path, and
    both are supplied by the selected registry scope:

    * **Activity.** Only rows whose declared :class:`~core.tipos_actividad.TipoActividad` are in
      the supplied activity-code set contribute. A row with no declared activity
      contributes NOTHING here — the opposite of the concept default below, and
      deliberately so. Silence about activity cannot mean "agrarian": routing an
      undeclared row into an activity-narrowed box would misroute a non-matching
      filer's income, and the same row may be claimed by another projection.
      Under-filling a box the operator can still complete by hand
      is recoverable; mis-routing income between two boxes of one return is not.
    * **Concept.** Rows whose :class:`~core.concepto_ingreso.ConceptoIngreso` art. 110.1.c) excludes —
      subvenciones de capital and indemnizaciones — are dropped. An undeclared
      concept IS included, because an unmarked receipt is far more likely to be
      ordinary income than an exceptional one. A declared concept the pinned
      vocabulary does not list is refused: it can be placed on neither side.

    The window is the quarter itself rather than a cumulative year-to-date window.

    Args:
        transactions: The :class:`TransactionCatalogue` to project.
        invoices: The :class:`InvoiceCatalogue` consulted when classifying; an
            empty catalogue when omitted.
        bucket_id: The active profile bucket.
        period: The quarter being filed.
        modelo: Selected model identifier supplied by the registry boundary.
        target_casilla_id: Selected output target supplied by the registry boundary.
        agrarian_activity_codes: Selected activity-code set supplied by the registry.
        activity_category_matcher: Predicate for activity-category transactions.
        employment_category_matcher: Predicate for employment-category transactions.
        operation: The operation's generation-pinned authority; the concept
            vocabulary and exclusion set are read from it.

    Returns:
        The :class:`RentaIncomeLedgerAggregation` for the selected target.

    Raises:
        AggregationPeriodError: If ``period`` is not a quarter.
        UnacceptedLedgerRegistryValueError: If an agrarian row declares an
            income concept the pinned vocabulary does not list.
    """
    if period.kind is not PeriodKind.QUARTERLY:
        raise AggregationPeriodError(
            tr("aggregation.renta_ledger.errors.unsupported_period"),
            context={"period": str(period)},
        )
    resolved_invoices = invoices if invoices is not None else InvoiceCatalogue()
    projected = _project_income_onto_casilla(
        transactions,
        invoices=resolved_invoices,
        bucket_id=bucket_id,
        window_start=period.start_date,
        window_end=period.end_date,
        target_casilla_id=target_casilla_id,
        activity_category_matcher=activity_category_matcher,
        employment_category_matcher=employment_category_matcher,
        admits=lambda transaction: (
            transaction.tipo_actividad in agrarian_activity_codes
            and row_counts_toward_volumen_de_ingresos(
                transaction,
                effective_date=period.end_date,
                authority=operation,
            )
        ),
    )

    return RentaIncomeLedgerAggregation(
        modelo=modelo,
        period=period,
        observations=projected.observations,
        issues=projected.issues,
        casilla_aggregation=fold_casilla_observations(
            projected.observations,
            modelo=modelo,
            period=period,
            amount_fn=_computable_income_amount,
        ),
        unadmitted_activity_income=_unadmitted_activity_income(
            transactions,
            projected.unadmitted,
            target_casilla_id=target_casilla_id,
        ),
    )


def _unadmitted_activity_income(
    transactions: TransactionCatalogue,
    unadmitted: Sequence[RentaIncomeObservation],
    *,
    target_casilla_id: CasillaId,
) -> UnadmittedActivityIncome:
    """Measure the income the art. 110.1.c) activity narrowing kept out.

    Always returns a value, including the all-zero one. An empty census is a
    positive statement -- the narrowing ran and excluded nothing -- and a
    consumer that had to read ``None`` for it could not tell that apart from a
    projection where no narrowing ran at all.

    The declared-activity predicate reads each excluded row back off the
    catalogue rather than off the observation, because the observation carries no
    activity and must not start to: the activity type has one stored home, and a
    second copy on an aggregation row would be the drift that placement exists to
    avoid. Reading it here is a function-local question about a row already in
    hand, not a new home for the fact.
    """
    if not unadmitted:
        return UnadmittedActivityIncome(target_casilla_id=target_casilla_id)
    by_id = {transaction.transaction_id: transaction for transaction in transactions.values()}
    return UnadmittedActivityIncome(
        target_casilla_id=target_casilla_id,
        row_count=len(unadmitted),
        income_total=sum(
            (_computable_income_amount(observation) for observation in unadmitted),
            start=Decimal("0"),
        ),
        # Indexed rather than searched, and unguarded on purpose: every
        # unadmitted observation was built from a row of this catalogue, so a
        # missing key is a broken invariant worth raising rather than a state to
        # absorb into a quiet ``False``.
        any_activity_declared=any(
            by_id[observation.transaction_id].tipo_actividad is not None for observation in unadmitted
        ),
    )


class _ProjectedIncome(NamedTuple):
    """Observations and issues from one pass over a catalogue.

    ``unadmitted`` carries the observations an ``admits`` narrowing kept OUT.
    They are eligible income by every other rule the pipeline applies -- same
    classifier, same window -- and were excluded solely by the row filter, which
    is what makes them the honest denominator for "this period carries income the
    target casilla did not admit". Empty whenever ``admits`` is ``None``, so the
    Un-narrowed paths carry nothing extra.
    """

    observations: tuple[RentaIncomeObservation, ...]
    issues: tuple[RentaIncomeLedgerAggregationIssue, ...]
    unadmitted: tuple[RentaIncomeObservation, ...] = ()


def _project_income_onto_casilla(
    transactions: TransactionCatalogue,
    *,
    invoices: InvoiceCatalogue,
    bucket_id: str,
    window_start: date,
    window_end: date,
    target_casilla_id: CasillaId,
    activity_category_matcher: Callable[[Transaction], bool],
    employment_category_matcher: Callable[[Transaction], bool],
    admits: Callable[[Transaction], bool] | None = None,
    criteria: ImputationCriteria | None = None,
) -> _ProjectedIncome:
    """Classify a catalogue once and re-target every eligible observation.

    Projection variants differ in three ways and no more: the window, the
    casilla, and whether rows are narrowed before classification. Everything else
    -- the lifecycle skip, the classifier
    call, the issue/observation split -- was written out identically in each, so a
    change to the eligibility contract had to be made in every copy or silently
    hold in only some.

    Args:
        transactions: The catalogue to project.
        invoices: Consulted when classifying each transaction.
        bucket_id: The active profile bucket.
        window_start: First day the classifier treats as in-window.
        window_end: Last day the classifier treats as in-window.
        target_casilla_id: The casilla every eligible observation is re-targeted to.
        activity_category_matcher: Predicate for activity-category transactions.
        employment_category_matcher: Predicate for employment-category transactions.
        admits: Optional row filter deciding which rows reach the casilla.
            ``None`` admits every active row, which is what an un-narrowed path
            wants. A rejected row is still CLASSIFIED, so its income can be
            counted, but it contributes to ``unadmitted`` rather than to
            ``observations``.
        criteria: The dated imputation election that places each row, or
            ``None`` to keep the bank date.

    Returns:
        The projected observations, the issues raised along the way, and the
        eligible income the ``admits`` narrowing kept out.
    """
    observations: list[RentaIncomeObservation] = []
    issues: list[RentaIncomeLedgerAggregationIssue] = []
    unadmitted: list[RentaIncomeObservation] = []
    receipts_by_invoice = None if criteria is None else _active_receipts_by_invoice(transactions, invoices)
    for transaction in transactions.values():
        if transaction.lifecycle_state is not TransactionLifecycleState.ACTIVE:
            continue
        admitted = admits is None or admits(transaction)
        outcome = _classify_income_transaction(
            transaction,
            invoices=invoices,
            receipts_by_invoice=receipts_by_invoice,
            bucket_id=bucket_id,
            cumulative_start=window_start,
            cumulative_end=window_end,
            target_casilla_id=target_casilla_id,
            activity_category_matcher=activity_category_matcher,
            employment_category_matcher=employment_category_matcher,
            criteria=criteria,
        )
        if outcome is None:
            continue
        if isinstance(outcome, RentaIncomeLedgerAggregationIssue):
            # A rejected row's issues are DISCARDED rather than reported. An
            # issue is a traceable exclusion from the casilla this pass feeds,
            # and a row the narrowing already excluded was never a candidate for
            # it -- reporting why it also failed a currency or window gate would
            # describe an exclusion that did not happen. The narrowing's own
            # consequence is reported once, in aggregate, off ``unadmitted``.
            if admitted:
                issues.append(outcome)
            continue
        retargeted = outcome.model_copy(update={"target_casilla_id": target_casilla_id})
        (observations if admitted else unadmitted).append(retargeted)
    return _ProjectedIncome(tuple(observations), tuple(issues), tuple(unadmitted))


def _active_receipts_by_invoice(
    transactions: TransactionCatalogue, invoices: InvoiceCatalogue
) -> dict[str, list[Transaction]]:
    """Group the active rows each issued invoice links back, for what they settle together."""
    grouped: dict[str, list[Transaction]] = {}
    for row in transactions.values():
        invoice = None if row.invoice_id is None else invoices.get(row.invoice_id)
        if (
            invoice is not None
            and row.lifecycle_state is TransactionLifecycleState.ACTIVE
            and row.transaction_id in invoice.linked_transaction_ids
        ):
            grouped.setdefault(invoice.invoice_id, []).append(row)
    return grouped


def _classify_income_transaction(
    transaction: Transaction,
    *,
    invoices: InvoiceCatalogue,
    receipts_by_invoice: Mapping[str, Sequence[Transaction]] | None,
    bucket_id: str,
    cumulative_start: date,
    cumulative_end: date,
    target_casilla_id: CasillaId,
    activity_category_matcher: Callable[[Transaction], bool],
    employment_category_matcher: Callable[[Transaction], bool],
    criteria: ImputationCriteria | None = None,
) -> RentaIncomeObservation | RentaIncomeLedgerAggregationIssue | None:
    """Filter one ledger transaction against the selected income pipeline.

    Returns a :class:`RentaIncomeObservation` for an eligible receipt, a
    :class:`RentaIncomeLedgerAggregationIssue` for an INCOMING row that fails a
    gate, or ``None`` for an OUTGOING row this income pipeline does not own —
    deductible OUTGOING expenses are aggregated by the
    companion ``ledger_renta_gastos_pago_fraccionado_aggregation`` pipeline
    (:mod:`~.renta_gasto_ledger`), so the income pass skips them silently
    rather than emitting a misleading "expense dropped" advisory.
    """
    if _income_transaction_is_out_of_scope(transaction):
        return None
    gate_issue = _income_gate_issue(
        transaction,
        employment_category_matcher=employment_category_matcher,
    )
    if gate_issue is not None:
        return gate_issue
    proportion_or_issue = _income_business_proportion_or_issue(
        transaction,
        activity_category_matcher=activity_category_matcher,
    )
    if isinstance(proportion_or_issue, RentaIncomeLedgerAggregationIssue):
        return proportion_or_issue
    proportion = proportion_or_issue
    # Use the EUR projection after rejecting unconverted non-EUR rows above, so a
    # converted foreign-currency receipt contributes its EUR equivalent while a
    # domestic row retains its raw amount (mirrors the expense pipeline's
    # ``effective_eur_amount`` usage in ``renta_ledger.py``).
    gross_amount = effective_eur_amount(transaction) * proportion

    filing_date_or_issue = (
        _income_filing_date_or_issue(
            transaction,
            cumulative_start=cumulative_start,
            cumulative_end=cumulative_end,
        )
        if criteria is None
        else _imputed_income_date_or_issue(
            transaction,
            invoices=invoices,
            cumulative_start=cumulative_start,
            cumulative_end=cumulative_end,
            criteria=criteria,
        )
    )
    if filing_date_or_issue is None or isinstance(filing_date_or_issue, RentaIncomeLedgerAggregationIssue):
        return filing_date_or_issue
    filing_date = filing_date_or_issue

    return _income_observation(
        transaction,
        invoices=invoices,
        bucket_id=bucket_id,
        proportion=proportion,
        gross_amount=gross_amount,
        filing_date=filing_date,
        target_casilla_id=target_casilla_id,
        receipts_by_invoice=receipts_by_invoice,
    )


def _income_transaction_is_out_of_scope(transaction: Transaction) -> bool:
    """Return whether the income pass must silently skip this transaction."""
    # Operator reviewed and deliberately excluded this row from filing (a final
    # disposition): omit it before the actividad-económica category override can
    # re-admit it. OUTGOING rows belong to the gasto pipeline and are skipped
    # rather than reported as income exclusions. So do a supplier's refunds, which
    # take the expense back there rather than coming in as income here.
    return (
        transaction.business_classification is BusinessClassification.REVIEWED_EXCLUDED
        or transaction.direction is not TransactionDirection.INCOMING
        or is_supplier_refund(transaction)
    )


def _income_gate_issue(
    transaction: Transaction,
    *,
    employment_category_matcher: Callable[[Transaction], bool],
) -> RentaIncomeLedgerAggregationIssue | None:
    """Return the first currency or IRPF-category issue for an income row."""
    transaction_id = transaction.transaction_id
    if is_non_eur_without_conversion(transaction):
        return RentaIncomeLedgerAggregationIssue(
            transaction_id=transaction_id,
            reason=RentaIncomeLedgerAggregationIssueReason.UNSUPPORTED_CURRENCY,
            detail=f"transaction currency {transaction.raw.currency!r} is not supported for Renta income",
        )

    # Nómina entries (irpf_category="trabajo") belong to rendimientos del
    # trabajo and must not feed an activity-income target.
    if employment_category_matcher(transaction):
        return RentaIncomeLedgerAggregationIssue(
            transaction_id=transaction_id,
            reason=RentaIncomeLedgerAggregationIssueReason.TRABAJO_INCOME,
            detail=(
                f"irpf_category {transaction.irpf_category!r} belongs to rendimientos del trabajo, "
                "not actividad económica; excluded from activity income"
            ),
        )
    return None


def _income_business_proportion_or_issue(
    transaction: Transaction,
    *,
    activity_category_matcher: Callable[[Transaction], bool],
) -> Decimal | RentaIncomeLedgerAggregationIssue:
    """Return the business share or the precise classification issue."""
    proportion = _income_business_proportion(
        transaction,
        activity_category_matcher=activity_category_matcher,
    )
    if proportion is not None:
        return proportion
    reason = RentaIncomeLedgerAggregationIssueReason(
        _shared_issue_reasons.business_state_issue_reason(transaction.business_classification)
    )
    return RentaIncomeLedgerAggregationIssue(
        transaction_id=transaction.transaction_id,
        reason=reason,
        detail=f"business classification {transaction.business_classification.value!r} cannot feed Renta income",
    )


def _income_filing_date_or_issue(
    transaction: Transaction,
    *,
    cumulative_start: date,
    cumulative_end: date,
) -> date | RentaIncomeLedgerAggregationIssue:
    """Return the transaction filing date or its cumulative-window issue."""
    filing_date = transaction.raw.value_date or transaction.raw.booked_date
    if cumulative_start <= filing_date <= cumulative_end:
        return filing_date
    return RentaIncomeLedgerAggregationIssue(
        transaction_id=transaction.transaction_id,
        reason=RentaIncomeLedgerAggregationIssueReason.OUTSIDE_PERIOD,
        detail=f"filing date {filing_date} is outside the cumulative income window",
    )


def _receipt_unresolved(
    transaction: Transaction, invoice: Invoice | None, accrual: date | None, criteria: ImputationCriteria
) -> ImputationUnresolved | None:
    """Return the reading a receipt cannot have under the dated election, or ``None`` when it has one."""
    # A capital subsidy follows its asset's amortization under either criterion, and no
    # ledger row carries a schedule: AEAT Manual Renta, ch. 6, citing STS 398/2022.
    if str(transaction.concepto_ingreso) == _CAPITAL_SUBSIDY_CONCEPT:
        return ImputationUnresolved.CAPITAL_SUBSIDY_SCHEDULE_UNKNOWN
    if invoice is None or accrual is None or criteria.usable(accrual.year) is not ActivityImputationCriterion.DEVENGO:
        return None
    # Under accrual a correction reduces the year's income, so money coming in on one has no reading.
    if is_rectificativa(invoice):
        return ImputationUnresolved.RECTIFICATIVA_WITH_RECEIPT
    # A shared receipt of an invoice whose figures cannot be shared out, or a lone receipt
    # above the invoice, stands for nothing known: cash past the invoice is not its income.
    if (
        len(invoice.linked_transaction_ids) != 1 or renta_income_evidence.receipt_overpays_invoice(invoice, transaction)
    ) and renta_income_evidence.part_payment_share(invoice, transaction) is None:
        return ImputationUnresolved.ACCRUAL_UNKNOWN
    return None


def _imputed_income_date_or_issue(
    transaction: Transaction,
    *,
    invoices: InvoiceCatalogue,
    cumulative_start: date,
    cumulative_end: date,
    criteria: ImputationCriteria,
) -> date | RentaIncomeLedgerAggregationIssue | None:
    """Place one receipt by the dated election; a row this window has no claim on returns ``None``."""
    cash = transaction.raw.value_date or transaction.raw.booked_date
    invoice = None if transaction.invoice_id is None else invoices.get(transaction.invoice_id)
    accrual = linked_accrual_date(invoice, kind=InvoiceKind.ISSUED)
    # A row the window has to account for, so a refusal must not read as nothing to place.
    entry = None if accrual is None else accrual_entry_date(accrual, criteria, through_year=cumulative_end.year)
    in_window = any(
        on is not None and cumulative_start <= on <= cumulative_end
        for on in (cash, accrual, transaction.accrual_date, entry)
    )
    imputed = _receipt_unresolved(transaction, invoice, accrual, criteria) or impute_ledger_row(
        transaction, invoice, kind=InvoiceKind.ISSUED, criteria=criteria
    )
    if isinstance(imputed, ImputationUnresolved):
        if not in_window:
            return None
        return RentaIncomeLedgerAggregationIssue(
            transaction_id=transaction.transaction_id,
            reason=RentaIncomeLedgerAggregationIssueReason.IMPUTATION_UNRESOLVED,
            detail=f"{imputed.value}: receipt of {cash} cannot be placed in an ejercicio",
        )
    return imputed if cumulative_start <= imputed <= cumulative_end else None


def _income_observation(
    transaction: Transaction,
    *,
    invoices: InvoiceCatalogue,
    bucket_id: str,
    proportion: Decimal,
    gross_amount: Decimal,
    filing_date: date,
    target_casilla_id: CasillaId,
    receipts_by_invoice: Mapping[str, Sequence[Transaction]] | None = None,
) -> RentaIncomeObservation:
    """Enrich an eligible income row with invoice evidence and withholding."""
    transaction_id = transaction.transaction_id

    # taxable_base carries the IVA-exclusive base imponible when set; it
    # feeds the taxable_base_sum fact path for the rendimiento-neto binding.
    evidence, evidence_refusal = renta_income_evidence.sales_invoice_evidence_payload(
        invoices=invoices,
        bucket_id=bucket_id,
        transaction=transaction,
        receipts_by_invoice=receipts_by_invoice,
    )

    # The linked invoice's own base takes precedence over the transaction's tax
    # substrate, with the transaction field as fallback -- the same ordering the
    # expense pipeline uses. A grounded row therefore also stops reporting
    # CASH_FALLBACK below, correctly: the substrate now genuinely exists.
    # The transaction fallback goes through the EUR-equivalent accessor:
    # ``transaction.taxable_base`` is denominated in the row's native
    # currency (see ``domain.transactions.tests.test_gross_invariant``), so a
    # converted foreign-currency row needs the same fx_rate projection the
    # gross amount above already received.
    declared_base = (
        evidence.taxable_base if evidence.taxable_base is not None else effective_eur_taxable_base(transaction)
    )
    # Scaled by the SAME proportion the gross above carries, never a second
    # decision: the two figures describe one receipt, so a rule that divided one
    # and not the other would declare a fraction of the income while the
    # retención derived from the undivided base stayed whole.
    taxable_base_amount: Decimal | None = None if declared_base is None else declared_base * proportion

    withheld = renta_income_evidence.income_withheld_amount(transaction, evidence=evidence)

    return RentaIncomeObservation(
        transaction_id=transaction_id,
        target_casilla_id=target_casilla_id,
        gross_amount=gross_amount,
        taxable_base_amount=taxable_base_amount,
        withheld_amount=withheld.amount,
        withheld_derivation=withheld.derivation,
        sales_invoice_refusal=evidence_refusal,
        filing_date=filing_date,
        source_jurisdiction=transaction.source_jurisdiction,
        grounding=(
            LedgerIncomeGrounding.SUBSTRATE_DECLARED
            if taxable_base_amount is not None
            else LedgerIncomeGrounding.CASH_FALLBACK
        ),
    )


def _income_business_proportion(
    transaction: Transaction,
    *,
    activity_category_matcher: Callable[[Transaction], bool],
) -> Decimal | None:
    """Return the share of one income row that is activity income, or ``None``.

    The single proportion decision for the row: every money figure the
    observation carries is scaled by this one value, so the gross and the
    taxable base cannot disagree about how much of the receipt is the
    activity's.

    When ``irpf_category`` is explicitly set to ``"actividad_economica"`` the
    transaction is already classified as a professional-activity receipt and
    ``business_classification`` is treated as ``BUSINESS`` by definition (the
    category tag is the authoritative signal). This avoids the common case
    where a transaction is tagged with ``irpf_category=actividad_economica``
    before the broader ``business_classification`` sweep has run.

    That short-circuit is also the legally correct answer to a MIXED
    classification on an activity receipt, not merely a convenience. Partial
    affectation is a property of ASSETS: LIRPF art. 29.2 (Ley 35/2006,
    BOE-A-2006-20764) limits it to "elementos patrimoniales que sirvan sólo
    parcialmente al objeto de la actividad económica", and it reaches the
    rendimiento neto through the deductibility of the gastos those assets
    generate (art. 28.1). Nothing in art. 27-30 divides an INGRESO by a usage
    percentage -- a client's payment for professional services is wholly an
    ingreso íntegro of the activity however the taxpayer's own desk, car or
    flat happens to be split. The retención the payer withholds on it agrees:
    RIRPF art. 95.1 (RD 439/2007) fixes the rate "sobre los ingresos íntegros
    satisfechos", a fact about the payment, carrying no affectation term at
    all. So an activity-tagged row is undivided on every figure, and because
    ``income_withheld_amount`` derives a retención for activity rows only,
    every row that carries one is a row this returns ``1`` for.
    """
    if activity_category_matcher(transaction):
        # The selected activity-category matcher is the authoritative eligibility gate.
        return Decimal("1")
    return business_proportion(transaction.business_classification, transaction.business_pct)


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
    *,
    modelo: str,
) -> CasillaAggregation:
    return fold_casilla_observations(
        observations,
        modelo=modelo,
        period=period,
        amount_fn=_computable_income_amount,
    )


__all__ = [
    "RentaIncomeLedgerAggregation",
    "RentaIncomeLedgerAggregationIssue",
    "RentaIncomeLedgerAggregationIssueReason",
    "RentaIncomeObservation",
    "UnadmittedActivityIncome",
    "aggregate_renta_income_ledger",
    "aggregate_renta_income_ledger_from_repositories",
    "aggregate_renta_m100_income_ledger",
    "aggregate_renta_m100_income_ledger_from_repositories",
]
