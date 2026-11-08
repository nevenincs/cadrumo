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

from collections.abc import Callable, Sequence
from datetime import date
from decimal import Decimal
from typing import NamedTuple

from ...core.aggregation import LedgerWithholdingDerivation
from ...core.casilla_id import CasillaId
from ...core.i18n.translatable import Translatable as tr
from ...core.period import Period, PeriodKind
from ...core.tipos_actividad import TipoActividad
from ...domain.calculations.registry.authority import PinnedAuthorityOperation
from ...domain.invoices.catalogue import InvoiceCatalogue
from ...domain.iva.schema import InvoiceKind
from ...domain.transactions.date_partition import OutOfWindowTransactionSummary
from ...domain.transactions.enums import TransactionLifecycleState
from ...domain.transactions.models import Transaction, TransactionCatalogue
from ..invoices.catalogue_reads_ports import InvoiceCatalogueReadPorts
from .catalogue_read_binding import require_catalogue_reads_bound_to
from .concepto_ingreso_admission import row_counts_toward_volumen_de_ingresos
from .errors import AggregationPeriodError
from .grouping import cumulative_year_to_date_window, fold_casilla_observations
from .invoice_iva_source import with_movement_side_links
from .models import CasillaAggregation, LedgerAggregationResultBase
from .renta_imputation import (
    ImputationCriteria,
    rows_left_out_summary,
    rows_touching_window,
)
from .renta_income_classification import classify_income_transaction
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
    rental_tag_missing: tuple[str, ...] = ()
    """Withholding-bearing activity rows with no tipo de actividad, in a year with a rental activity."""
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


def _invoices_linked_from_either_side(
    invoices: InvoiceCatalogue | None, *, window: TransactionCatalogue
) -> InvoiceCatalogue:
    """Return the catalogue with each link read from either record, as the invoice IVA source reads it.

    A receipt that names its invoice is that invoice's payment even when the
    invoice does not yet list it back, so the retención and base the invoice
    states reach the receipt either way.
    """
    if invoices is None:
        return InvoiceCatalogue()
    linked = with_movement_side_links(tuple(invoices.values()), window=window)
    return InvoiceCatalogue(invoices={invoice.invoice_id: invoice for invoice in linked})


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
    excluded_activity_codes: frozenset[TipoActividad] = frozenset(),
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
            excluded_activity_codes=excluded_activity_codes,
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
        excluded_activity_codes=excluded_activity_codes,
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
    excluded_activity_codes: frozenset[TipoActividad] = frozenset(),
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
        excluded_activity_codes: Declared activities whose rows belong to another box.
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
    resolved_invoices = _invoices_linked_from_either_side(invoices, window=transactions)

    observations: list[RentaIncomeObservation] = []
    issues: list[RentaIncomeLedgerAggregationIssue] = []
    receipts_by_invoice = None if criteria is None else _active_receipts_by_invoice(transactions, resolved_invoices)

    for transaction in transactions.values():
        if transaction.lifecycle_state is not TransactionLifecycleState.ACTIVE:
            continue
        if transaction.tipo_actividad in excluded_activity_codes:
            continue
        outcome = classify_income_transaction(
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
            observations.append(_held_past_cut_off(outcome, transaction, cut_off=window.end))

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


def _held_past_cut_off(
    observation: RentaIncomeObservation, transaction: Transaction, *, cut_off: date
) -> RentaIncomeObservation:
    """Keep a pago fraccionado from crediting a declared retención its receipt paid after the window.

    Only accrual places a receipt dated after the window inside it, so under cash
    basis no row reaches this. The income still counts in the window it accrues in;
    the retención is held with its figure and reported (RIRPF art. 110.3.a; TEAC
    00/03187/2011).
    """
    paid_on = transaction.raw.value_date or transaction.raw.booked_date
    if (
        paid_on <= cut_off
        or observation.withheld_derivation is not LedgerWithholdingDerivation.DECLARED_ON_LINKED_INVOICE
    ):
        return observation
    return observation.model_copy(update={"withheld_derivation": LedgerWithholdingDerivation.PAID_AFTER_CUT_OFF})


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
    rental: RentalActivityScreen | None = None,
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
            rental=rental,
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
            rental=rental,
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
        rental=rental,
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
    rental: RentalActivityScreen | None = None,
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
    resolved_invoices = _invoices_linked_from_either_side(invoices, window=transactions)

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
    screened = _screen_rental_activity(projected.observations, transactions, rental)
    observations = list(screened.observations)
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
        rental_tag_missing=screened.untagged,
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


def payment_dated_renta_m100_income_observations(
    *,
    bucket_id: str,
    period: Period,
    target_casilla_id: CasillaId,
    activity_category_matcher: Callable[[Transaction], bool],
    employment_category_matcher: Callable[[Transaction], bool],
    ports: InvoiceCatalogueReadPorts,
    rental: RentalActivityScreen | None = None,
) -> tuple[RentaIncomeObservation, ...]:
    """Return the ejercicio's activity receipts placed on the date the payer paid them.

    A payer certifies the retención in the year it pays (DGT V4965-16), so this
    is the ledger figure a certificate is compared with when accrual places some
    receipts in another year. Each receipt keeps its share of a part-paid invoice,
    as it does under an imputation criterion.
    """
    if period.kind is not PeriodKind.ANNUAL:
        raise AggregationPeriodError(
            tr("aggregation.renta_ledger.errors.unsupported_period"),
            context={"period": str(period)},
        )
    require_catalogue_reads_bound_to(ports, bucket_id=bucket_id)
    paid = ports.transaction_reader.partition_by_date_range(period.start_date, period.end_date).in_window
    projected = _project_income_onto_casilla(
        paid,
        invoices=_invoices_linked_from_either_side(_load_income_invoices(ports=ports), window=paid),
        bucket_id=bucket_id,
        window_start=date(period.filing_year, 1, 1),
        window_end=date(period.filing_year, 12, 31),
        target_casilla_id=target_casilla_id,
        activity_category_matcher=activity_category_matcher,
        employment_category_matcher=employment_category_matcher,
        allocate_part_payments=True,
    )
    return _screen_rental_activity(projected.observations, paid, rental).observations


def instalment_basis_observations(
    observations: Sequence[RentaIncomeObservation],
    transactions: TransactionCatalogue,
    *,
    cut_off: date,
) -> tuple[RentaIncomeObservation, ...]:
    """Restate the ejercicio's activity rows as the year's last pago fraccionado credits their retención.

    That pago fraccionado deducts only the retención practised by the window's
    end, and keeps a rental activity's (RIRPF art. 110.3.a), while the annual
    activity credit counts any payment date and leaves the rental's to the
    rental credit. Each row is restated by its own payment date and tipo de
    actividad, so a difference the two credits owe to that itemisation is visible.

    ``transactions`` is the :class:`TransactionCatalogue`, the profile's transaction catalogue.
    """
    restated: list[RentaIncomeObservation] = []
    for observation in observations:
        transaction = transactions.get(observation.transaction_id)
        if transaction is None:
            restated.append(observation)
            continue
        if observation.withheld_derivation is LedgerWithholdingDerivation.RENTAL_ACTIVITY_COMPONENT:
            observation = observation.model_copy(
                update={"withheld_derivation": LedgerWithholdingDerivation.DECLARED_ON_LINKED_INVOICE}
            )
        restated.append(_held_past_cut_off(observation, transaction, cut_off=cut_off))
    return tuple(restated)


class RentalActivityScreen(NamedTuple):
    """Which activity rows the annual activity credit hands to the rental credit.

    ``codes`` are the tipos de actividad whose withholding belongs to the
    rental credit; ``declared`` says the profile declares a rental activity
    for the ejercicio, which a ledger row carrying one of ``codes`` also shows.
    """

    codes: frozenset[str]
    declared: bool


class _ScreenedRentalActivity(NamedTuple):
    observations: tuple[RentaIncomeObservation, ...]
    untagged: tuple[str, ...]


def _bears_withholding(observation: RentaIncomeObservation) -> bool:
    derivation = observation.withheld_derivation
    if derivation in (LedgerWithholdingDerivation.NOT_APPLICABLE, LedgerWithholdingDerivation.NONE_WITHHELD):
        return False
    return derivation is not LedgerWithholdingDerivation.DECLARED_ON_LINKED_INVOICE or observation.withheld_amount != 0


def _screen_rental_activity(
    observations: Sequence[RentaIncomeObservation],
    transactions: TransactionCatalogue,
    rental: RentalActivityScreen | None,
) -> _ScreenedRentalActivity:
    """Hand a rental activity row's declared retención to the rental credit, and name the untagged rows.

    ``tipo_actividad`` is optional on a row, so an untagged row cannot be told
    apart from a rental one. Where the ejercicio shows a rental activity, each
    untagged row bearing a retención is named, and the activity credit is not
    stated until it is tagged; where none is shown, untagged rows are activity rows.
    """
    if rental is None or not rental.codes:
        return _ScreenedRentalActivity(tuple(observations), ())
    screened: list[RentaIncomeObservation] = []
    untagged: list[str] = []
    rental_shown = rental.declared
    for observation in observations:
        transaction = transactions.get(observation.transaction_id)
        tipo = None if transaction is None or transaction.tipo_actividad is None else transaction.tipo_actividad.value
        if tipo in rental.codes:
            rental_shown = True
            if observation.withheld_derivation is LedgerWithholdingDerivation.DECLARED_ON_LINKED_INVOICE and (
                observation.withheld_amount > 0
            ):
                observation = observation.model_copy(
                    update={"withheld_derivation": LedgerWithholdingDerivation.RENTAL_ACTIVITY_COMPONENT}
                )
        elif tipo is None and _bears_withholding(observation):
            untagged.append(observation.transaction_id)
        screened.append(observation)
    return _ScreenedRentalActivity(tuple(screened), tuple(untagged) if rental_shown else ())


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
    criteria: ImputationCriteria | None = None,
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
        criteria=criteria,
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
    criteria: ImputationCriteria | None = None,
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
        criteria: The dated imputation election that places each row, when one is declared.
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
    resolved_invoices = _invoices_linked_from_either_side(invoices, window=transactions)
    projected = _project_income_onto_casilla(
        transactions,
        invoices=resolved_invoices,
        bucket_id=bucket_id,
        window_start=period.start_date,
        window_end=period.end_date,
        target_casilla_id=target_casilla_id,
        activity_category_matcher=activity_category_matcher,
        employment_category_matcher=employment_category_matcher,
        criteria=criteria,
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
    allocate_part_payments: bool | None = None,
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
        allocate_part_payments: Whether a part payment carries its share of
            the invoice; ``None`` allocates exactly when ``criteria`` is given.

    Returns:
        The projected observations, the issues raised along the way, and the
        eligible income the ``admits`` narrowing kept out.
    """
    observations: list[RentaIncomeObservation] = []
    issues: list[RentaIncomeLedgerAggregationIssue] = []
    unadmitted: list[RentaIncomeObservation] = []
    allocates = criteria is not None if allocate_part_payments is None else allocate_part_payments
    receipts_by_invoice = _active_receipts_by_invoice(transactions, invoices) if allocates else None
    for transaction in transactions.values():
        if transaction.lifecycle_state is not TransactionLifecycleState.ACTIVE:
            continue
        admitted = admits is None or admits(transaction)
        outcome = classify_income_transaction(
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
    "RentalActivityScreen",
    "UnadmittedActivityIncome",
    "aggregate_renta_income_ledger",
    "aggregate_renta_income_ledger_from_repositories",
    "aggregate_renta_m100_income_ledger",
    "aggregate_renta_m100_income_ledger_from_repositories",
    "instalment_basis_observations",
    "payment_dated_renta_m100_income_observations",
]
