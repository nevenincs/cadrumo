"""Repository-backed annual and quarterly Renta expense source resolvers.

This module uses :class:`TransactionCatalogue`, the profile's transaction catalogue;
:class:`InvoiceCatalogue`, the profile's invoice catalogue.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import ClassVar, Final, Protocol

from ...core.aggregation import BindingSourceKind, BindingValueOutcome, CalculationSourceLineageRole
from ...core.casilla_id import CasillaId
from ...core.period import Period
from ...domain.calculations.registry.actividad_asset_disposal_bindings import (
    resolve_activity_asset_disposal_binding_values,
    resolve_activity_asset_disposal_element_type_values,
    resolve_activity_asset_disposal_row_values,
)
from ...domain.calculations.registry.binding_terminal_origin import TerminalOriginClass
from ...domain.calculations.registry.errors import RegistryError
from ...domain.calculations.registry.form_codes import form_for_role
from ...domain.calculations.registry.ids import BindingId
from ...domain.calculations.registry.ledger_renta_gastos_estimacion_directa_bindings import (
    RentaGastosEstimacionDirectaObservationProtocol,
    activity_asset_amortization_casillas,
    resolve_ledger_renta_gastos_estimacion_directa_aggregation_binding_values,
    unsupported_ledger_renta_gastos_estimacion_directa_observations,
)
from ...domain.calculations.registry.ledger_renta_gastos_pago_fraccionado_bindings import (
    LedgerRentaGastosPagoFraccionadoProvider,
    RentaGastosPagoFraccionadoObservationProtocol,
    resolve_ledger_renta_gastos_pago_fraccionado_aggregation_binding_values,
    unsupported_ledger_renta_gastos_pago_fraccionado_observations,
)
from ...domain.contribuyente.inventory.closing_foundations import InventoryLedgerError
from ...domain.contribuyente.inventory.ledger_claims import InventoryPurchaseClaim, document_purchase_claims
from ...domain.invoices.catalogue import InvoiceCatalogue
from ...domain.invoices.models import Invoice
from ...domain.iva.schema import InvoiceKind
from ...domain.prorrata_register.protocols import ProrrataRegisterRepositoryProtocol
from ...domain.renta.ledger_expenses import RentaDeductibleExpenseObservation
from ...domain.transactions.enums import TransactionLifecycleState
from ...domain.transactions.models import Transaction, TransactionCatalogue
from ...domain.transactions.protocols import TransactionCatalogueRepositoryProtocol
from ..actividad_asset.history import ActivityAssetHistory
from ..actividad_asset.ports import ActivityAssetHistoryRepository
from ..invoices.catalogue_reads_ports import (
    InvoiceCatalogueReader,
    InvoiceCatalogueReadPersistenceError,
    InvoiceCatalogueReadPorts,
)
from ..invoices.source_observations import is_rectificativa
from ..ledger.usage_ratio_repository import UsageRatioProfileLoader
from ..user_profile.usage_ratio_resolution import resolve_effective_usage_ratios
from .activity_asset_disposal_projection import disposal_row_source_identities
from .activity_asset_expense_reconciliation import (
    LedgerExpenseRegisterClassification,
    LedgerRentaExpenseTreatment,
    RefusedExpenseRow,
    RegisterOwnedAcquisition,
    UnregisteredAmortizationRow,
    amortization_labelled_expense_categories,
    book_claimed_purchase_diagnostics,
    classify_ledger_expenses_against_asset_register,
    dwelling_ownership_share,
    issues_the_register_does_not_answer,
    refused_amortization_rows,
    refused_register_owned_rows,
    register_acquisition_transaction_ids,
    register_owned_acquisition_diagnostics,
    unregistered_amortization_row_diagnostics,
)
from .activity_asset_ledger_reconciliation import (
    activity_asset_ledger_findings,
    capital_good_transaction_ids,
    possibly_durable_expense_findings,
)
from .inventory import InventoryLedgerRepositoryProtocol
from .modelo_bindings import aggregation_period_for_modelo
from .modelo_bindings_actividad_assets import (
    ActivityAssetExpenseObservation,
    ActivityAssetProjection,
    activity_asset_disposal_provenance,
    activity_asset_provenance,
    m100_activity_asset_projection,
    m130_activity_asset_projection,
)
from .modelo_bindings_invoice_iva import out_of_window_summary_diagnostics
from .modelo_bindings_support import (
    STORAGE_DEGRADATION_ERRORS,
    empty_source_resolution,
    revision_has_binding_source,
)
from .renta_gasto_ledger import (
    RentaGastoLedgerAggregation,
    RentaGastoLedgerAggregationIssue,
    RentaGastoLedgerAggregationIssueReason,
    RentaGastoObservation,
    aggregate_renta_gasto_ledger_from_repositories,
)
from .renta_imputation import (
    ActivityImputationCriterion,
    ImputationCriteria,
    ImputationFilingHistory,
    accruing_invoices,
    declared_imputation_criteria,
    imputation_blocking_diagnostics,
    ledger_sum_outcome,
    received_invoice_reference,
)
from .renta_income_diagnostics import received_rectificativa_netting_diagnostics, received_rectificativa_reading
from .renta_income_evidence import taxable_base_comparison
from .renta_ledger import aggregate_renta_ledger_expenses_from_repositories
from .renta_ledger_models import (
    RentaLedgerAggregationIssue,
    RentaLedgerAggregationIssueReason,
    RentaLedgerExpenseAggregation,
)
from .source_mesh import (
    CalculationSourceContext,
    CalculationSourceDiagnostic,
    CalculationSourceProvenance,
    CalculationSourceResolution,
)
from .source_resolution_operations import (
    flatten_source_provenance_for,
    source_context_operation,
    source_issue_diagnostics,
    source_provenance_for,
    storage_degradation_resolution,
)
from .source_resolution_operations import sorted_source_ids as sorted_ids


class _TransactionRow(Protocol):
    @property
    def transaction_id(self) -> str: ...


@dataclass(frozen=True, slots=True)
class _RegisterSplit[IssueT, LedgerT: _TransactionRow, AssetT]:
    """Ledger findings and observations once the asset register has answered its rows."""

    register_owned: tuple[RegisterOwnedAcquisition, ...]
    issues: tuple[IssueT, ...]
    ledger_observations: tuple[LedgerT, ...]
    asset_observations: tuple[AssetT, ...]
    all_observations: tuple[LedgerT | AssetT, ...]


def _split_register_owned[IssueT: RefusedExpenseRow, LedgerT: _TransactionRow, AssetT](
    *,
    aggregation_issues: Sequence[IssueT],
    aggregation_observations: Sequence[LedgerT],
    asset_history: ActivityAssetHistory,
    classification: LedgerExpenseRegisterClassification,
    refused: Sequence[UnregisteredAmortizationRow],
    asset_observations: Sequence[AssetT],
    tax_year: int,
) -> _RegisterSplit[IssueT, LedgerT, AssetT]:
    refused_owned = refused_register_owned_rows(
        aggregation_issues,
        assets=asset_history.revisions,
        tax_year=tax_year,
        effective_date=date(tax_year, 12, 31),
    )
    excluded_transaction_ids = classification.excluded_transaction_ids
    ledger_observations = tuple(
        observation
        for observation in aggregation_observations
        if observation.transaction_id not in excluded_transaction_ids
    )
    assets = tuple(asset_observations)
    return _RegisterSplit(
        register_owned=(*classification.withheld, *refused_owned),
        issues=issues_the_register_does_not_answer(
            aggregation_issues,
            answered=(*refused_owned, *refused, *classification.unregistered),
        ),
        ledger_observations=ledger_observations,
        asset_observations=assets,
        all_observations=(*ledger_observations, *assets),
    )


class LedgerRentaGastosEstimacionDirectaAggregationSourceResolver:
    """Resolve ``ledger_renta_gastos_estimacion_directa_aggregation`` bindings for Renta expenses.

    Owns :attr:`BindingSourceKind.LEDGER_RENTA_GASTOS_ESTIMACION_DIRECTA_AGGREGATION` and folds
    transaction rows plus purchase-invoice evidence through
    :func:`~.renta_ledger.aggregate_renta_ledger_expenses_from_repositories`.
    It reports source issues and unrouted deductible expenses on the returned
    :class:`~.source_mesh.CalculationSourceResolution`.
    """

    resolver_id: ClassVar[str] = "ledger_renta_gastos_estimacion_directa_aggregation"
    owned_sources: ClassVar[tuple[BindingSourceKind, ...]] = (
        BindingSourceKind.LEDGER_RENTA_GASTOS_ESTIMACION_DIRECTA_AGGREGATION,
        BindingSourceKind.ACTIVITY_ASSET_DISPOSAL,
    )

    def __init__(
        self,
        *,
        ports: InvoiceCatalogueReadPorts,
        prorrata_register_repository: ProrrataRegisterRepositoryProtocol,
        usage_ratio_profile_loader: UsageRatioProfileLoader,
        activity_asset_history_repository: ActivityAssetHistoryRepository,
        inventory_repository: InventoryLedgerRepositoryProtocol | None = None,
        imputation_filings: Callable[[CalculationSourceContext], ImputationFilingHistory] | None = None,
    ) -> None:
        """Initialize the resolver with its required catalogue read capabilities.

        ``inventory_repository`` holds the books whose purchases claim ledger rows;
        each claimed row is withheld here, because the book carries the purchase.
        """
        self._ports = ports
        self._prorrata_register_repository = prorrata_register_repository
        self._usage_ratio_profile_loader = usage_ratio_profile_loader
        self._activity_asset_history_repository = activity_asset_history_repository
        self._inventory_repository = inventory_repository
        self._imputation_filings = imputation_filings

    def _inventory_claims(self) -> tuple[InventoryPurchaseClaim, ...]:
        """Every purchase claim of every book; a claim on a row of another year still owns that row."""
        if self._inventory_repository is None:
            return ()
        return document_purchase_claims(self._inventory_repository.load())

    def _aggregate(
        self,
        context: CalculationSourceContext,
        *,
        asset_history: ActivityAssetHistory,
        inventory_claims: tuple[InventoryPurchaseClaim, ...],
    ) -> RentaLedgerExpenseAggregation | CalculationSourceResolution:
        try:
            profile = context.profile
            with source_context_operation(context) as operation:
                usage_ratios = resolve_effective_usage_ratios(
                    bucket_id=context.bucket_id,
                    year=context.filing_year,
                    usage_ratio_profile_loader=self._usage_ratio_profile_loader,
                    operation=operation,
                    profile_record=profile.record if profile is not None else None,
                )
                return aggregate_renta_ledger_expenses_from_repositories(
                    bucket_id=context.bucket_id,
                    period=aggregation_period_for_modelo(
                        filing_year=context.filing_year,
                        code=context.period.registry_token,
                    ),
                    ports=self._ports,
                    profile_year=context.filing_year,
                    usage_ratios=usage_ratios,
                    modelo=context.modelo,
                    profile_record=profile.record if profile is not None else None,
                    prorrata_register_repository=self._prorrata_register_repository,
                    profile_decode_context=profile.profile_decode_context if profile is not None else None,
                    operation=operation,
                    ownership_share=dwelling_ownership_share(asset_history.revisions),
                    register_owned_transaction_ids=register_acquisition_transaction_ids(
                        asset_history.revisions, inventory_claims
                    ),
                    criteria=declared_imputation_criteria(
                        profile.record if profile is not None else None,
                        self._imputation_filings(context) if self._imputation_filings is not None else None,
                    ),
                )
        except (InvoiceCatalogueReadPersistenceError, *STORAGE_DEGRADATION_ERRORS) as exc:
            return storage_degradation_resolution(
                resolver_id=self.resolver_id,
                owned_sources=self.owned_sources,
                source_kinds=self.owned_sources,
                error=exc,
            )

    def _classify_expenses(
        self,
        aggregation: RentaLedgerExpenseAggregation,
        *,
        asset_history: ActivityAssetHistory,
        amortization_boxes: frozenset[CasillaId],
        inventory_claims: tuple[InventoryPurchaseClaim, ...],
    ) -> LedgerExpenseRegisterClassification:
        labelled = amortization_labelled_expense_categories(
            effective_date=date(aggregation.period.filing_year, 12, 31),
        )
        capital_goods = capital_good_transaction_ids(
            (observation.transaction_id for observation in aggregation.observations),
            ledger=self._ports.transaction_reader,
            tax_year=aggregation.period.filing_year,
        )
        return classify_ledger_expenses_against_asset_register(
            asset_history.revisions,
            tuple(
                LedgerRentaExpenseTreatment(
                    transaction_id=observation.transaction_id,
                    category=str(observation.category),
                    tax_year=observation.tax_year,
                    booked_on=observation.operation_date,
                    deductible_amount=observation.deductible_amount,
                    amortization_labelled=(
                        observation.target_casilla_id in amortization_boxes
                        or observation.category.value in labelled
                        or observation.transaction_id in capital_goods
                    ),
                )
                for observation in aggregation.observations
            ),
            inventory_claims=inventory_claims,
        )

    def _diagnostics(
        self,
        context: CalculationSourceContext,
        *,
        aggregation: RentaLedgerExpenseAggregation,
        split: _RegisterSplit[
            RentaLedgerAggregationIssue, RentaDeductibleExpenseObservation, ActivityAssetExpenseObservation
        ],
        asset_history: ActivityAssetHistory,
        asset_projection: ActivityAssetProjection,
        classification: LedgerExpenseRegisterClassification,
        refused: tuple[UnregisteredAmortizationRow, ...],
        may_be_durable: tuple[CalculationSourceDiagnostic, ...],
        unrouted: Sequence[RentaGastosEstimacionDirectaObservationProtocol],
    ) -> tuple[CalculationSourceDiagnostic, ...]:
        return (
            source_issue_diagnostics(
                split.issues,
                source_kind="ledger_renta_gastos_estimacion_directa_aggregation",
                resolver_id=self.resolver_id,
                held_back_reasons=frozenset(
                    {
                        RentaLedgerAggregationIssueReason.MISSING_CATEGORY,
                        RentaLedgerAggregationIssueReason.UNKNOWN_CATEGORY,
                        RentaLedgerAggregationIssueReason.DEFINITIVE_PRORRATA_PENDING,
                    }
                ),
                source_ref=lambda issue: f"transaction:{issue.transaction_id}",
                suppressed_reasons=frozenset({RentaLedgerAggregationIssueReason.IMPUTATION_UNRESOLVED}),
            )
            + _expense_imputation_diagnostics(
                context,
                source_kind="ledger_renta_gastos_estimacion_directa_aggregation",
                resolver_id=self.resolver_id,
                binding_ids=resolve_ledger_renta_gastos_estimacion_directa_aggregation_binding_values(
                    context.revision, split.all_observations
                ),
                unresolved=tuple(
                    issue.detail
                    for issue in split.issues
                    if issue.reason is RentaLedgerAggregationIssueReason.IMPUTATION_UNRESOLVED
                ),
                rows_present=bool(split.ledger_observations),
                period=aggregation.period,
                invoices=self._ports.invoice_reader.load(),
                transactions=self._ports.transaction_reader.load(),
                filings=self._imputation_filings(context) if self._imputation_filings is not None else None,
            )
            + source_issue_diagnostics(
                aggregation.advisories,
                source_kind="ledger_renta_gastos_estimacion_directa_aggregation",
                resolver_id=self.resolver_id,
            )
            + register_owned_acquisition_diagnostics(
                split.register_owned,
                source_kind="ledger_renta_gastos_estimacion_directa_aggregation",
                resolver_id=self.resolver_id,
            )
            + book_claimed_purchase_diagnostics(
                classification.book_claimed,
                source_kind="ledger_renta_gastos_estimacion_directa_aggregation",
                resolver_id=self.resolver_id,
            )
            + unregistered_amortization_row_diagnostics(
                (*classification.unregistered, *refused),
                resolver_id=self.resolver_id,
            )
            + asset_projection.diagnostics
            + activity_asset_ledger_findings(
                asset_history.revisions,
                ledger=self._ports.transaction_reader,
                tax_year=aggregation.period.filing_year,
                source_kind="ledger_renta_gastos_estimacion_directa_aggregation",
                resolver_id=self.resolver_id,
            )
            + may_be_durable
            + _m100_unrouted_diagnostics(context, unrouted, resolver_id=self.resolver_id)
        )

    def _provenance(
        self,
        split: _RegisterSplit[
            RentaLedgerAggregationIssue, RentaDeductibleExpenseObservation, ActivityAssetExpenseObservation
        ],
        asset_projection: ActivityAssetProjection,
    ) -> tuple[CalculationSourceProvenance, ...]:
        return (
            flatten_source_provenance_for(
                split.ledger_observations,
                _renta_observation_provenance,
            )
            + activity_asset_provenance(
                split.asset_observations,
                resolver_id=self.resolver_id,
                resolved_binding_source=BindingSourceKind.LEDGER_RENTA_GASTOS_ESTIMACION_DIRECTA_AGGREGATION,
            )
            + activity_asset_disposal_provenance(
                asset_projection,
                resolver_id=self.resolver_id,
                resolved_binding_source=BindingSourceKind.ACTIVITY_ASSET_DISPOSAL,
            )
        )

    def resolve(self, context: CalculationSourceContext) -> CalculationSourceResolution:
        """Resolve the ledger Renta gastos estimación directa aggregation binding for ``context``.

        Returns:
            An empty resolution when the revision declares no such binding
            source, a degraded resolution on repository failure, or the
            aggregated :class:`~.source_mesh.CalculationSourceResolution`
            with its binding values, diagnostics, and provenance.
        """
        if not revision_has_binding_source(context.revision, "ledger_renta_gastos_estimacion_directa_aggregation"):
            return empty_source_resolution(self.resolver_id, self.owned_sources)

        try:
            asset_history = self._activity_asset_history_repository.load()
            inventory_claims = self._inventory_claims()
        except (InventoryLedgerError, *STORAGE_DEGRADATION_ERRORS) as exc:
            return storage_degradation_resolution(
                resolver_id=self.resolver_id,
                owned_sources=self.owned_sources,
                source_kinds=self.owned_sources,
                error=exc,
            )
        aggregation = self._aggregate(context, asset_history=asset_history, inventory_claims=inventory_claims)
        if isinstance(aggregation, CalculationSourceResolution):
            return aggregation
        with source_context_operation(context) as operation:
            classification = self._classify_expenses(
                aggregation,
                asset_history=asset_history,
                amortization_boxes=frozenset(activity_asset_amortization_casillas(context.revision).values()),
                inventory_claims=inventory_claims,
            )
            refused = refused_amortization_rows(
                aggregation.issues,
                assets=asset_history.revisions,
                tax_year=aggregation.period.filing_year,
                effective_date=date(aggregation.period.filing_year, 12, 31),
            )
            asset_projection = m100_activity_asset_projection(
                asset_history,
                context=context,
                period=aggregation.period,
                operation=operation,
                resolver_id=self.resolver_id,
                transactions=self._ports.transaction_reader,
            )
            may_be_durable = possibly_durable_expense_findings(
                (
                    observation.transaction_id
                    for observation in aggregation.observations
                    if observation.transaction_id not in classification.excluded_transaction_ids
                ),
                revisions=asset_history.revisions,
                ledger=self._ports.transaction_reader,
                invoices=self._ports.invoice_reader,
                tax_year=aggregation.period.filing_year,
                source_kind="ledger_renta_gastos_estimacion_directa_aggregation",
                resolver_id=self.resolver_id,
            )
        split = _split_register_owned(
            aggregation_issues=aggregation.issues,
            aggregation_observations=aggregation.observations,
            asset_history=asset_history,
            classification=classification,
            refused=refused,
            asset_observations=asset_projection.observations,
            tax_year=aggregation.period.filing_year,
        )
        issues = split.issues
        ledger_observations = split.ledger_observations
        all_observations = split.all_observations
        unrouted = unsupported_ledger_renta_gastos_estimacion_directa_observations(context.revision, all_observations)
        element_types, element_types_inapplicable = resolve_activity_asset_disposal_element_type_values(
            context.revision,
            asset_projection.disposal_observations,
        )
        disposal_row_values, disposal_row_identities = resolve_activity_asset_disposal_row_values(
            context.revision,
            asset_projection.disposal_rows,
        )
        return CalculationSourceResolution(
            resolver_id=self.resolver_id,
            owned_sources=self.owned_sources,
            row_binding_values=disposal_row_values,
            row_source_identities=disposal_row_source_identities(
                disposal_row_identities, asset_projection.disposal_rows
            ),
            binding_values={
                **resolve_ledger_renta_gastos_estimacion_directa_aggregation_binding_values(
                    context.revision,
                    all_observations,
                ),
                **resolve_activity_asset_disposal_binding_values(
                    context.revision,
                    asset_projection.disposal_observations,
                ),
            },
            enum_binding_values=element_types,
            inapplicable_binding_ids=element_types_inapplicable,
            value_outcomes=_ledger_expense_value_outcomes(
                context,
                resolve_ledger_renta_gastos_estimacion_directa_aggregation_binding_values(
                    context.revision, all_observations
                ),
                held_back_rows=any(issue.reason.value not in _NOT_AN_EXPENSE_ISSUES for issue in issues),
                period=aggregation.period,
                invoices=self._ports.invoice_reader.load(),
            ),
            source_transaction_ids=sorted_ids(ledger_observations, lambda observation: observation.transaction_id),
            diagnostics=self._diagnostics(
                context,
                aggregation=aggregation,
                split=split,
                asset_history=asset_history,
                asset_projection=asset_projection,
                classification=classification,
                refused=refused,
                may_be_durable=may_be_durable,
                unrouted=unrouted,
            ),
            provenance=self._provenance(split, asset_projection),
        )


_NOT_AN_EXPENSE_ISSUES: Final[frozenset[str]] = frozenset(
    {"personal_transaction", "unsupported_direction", "outside_period"}
)
"""Issues naming a row that is not this window's activity expense, so it says nothing against a zero."""


def _ledger_expense_value_outcomes(
    context: CalculationSourceContext,
    binding_values: Mapping[BindingId, Decimal],
    *,
    held_back_rows: bool,
    period: Period,
    invoices: InvoiceCatalogue,
) -> dict[BindingId, BindingValueOutcome]:
    """State what each resolved expense box rests on.

    A row a gate held back, or a received invoice accruing in the window, may
    belong in any expense box until it is classified, so either keeps every zero
    from being proven.
    """
    with source_context_operation(context):
        accruing = accruing_invoices(
            invoices.values(),
            kind=InvoiceKind.RECEIVED,
            bucket_id=context.bucket_id,
            start=date(period.filing_year, 1, 1),
            end=period.end_date,
            criteria=declared_imputation_criteria(context.profile.record if context.profile is not None else None),
        )
    return {
        binding_id: ledger_sum_outcome(value, rows_present=held_back_rows, accruing_invoice_present=bool(accruing))
        for binding_id, value in binding_values.items()
    }


def _received_invoice_rows(transactions: TransactionCatalogue) -> dict[str, list[Transaction]]:
    """Group the active ledger rows linked to each purchase invoice, by the catalogue invoice each row names."""
    rows_by_invoice: dict[str, list[Transaction]] = {}
    for row in transactions.values():
        invoice_id = received_invoice_reference(row)
        if invoice_id is not None and row.lifecycle_state is TransactionLifecycleState.ACTIVE:
            rows_by_invoice.setdefault(invoice_id, []).append(row)
    return rows_by_invoice


def accrual_coverage_gap(invoice: Invoice, rows: Sequence[Transaction]) -> str | None:
    """Say what of an accruing received invoice its ledger rows leave unclassified, or ``None``."""
    if not rows:
        return f"accrual_unclassified: received invoice {invoice.invoice_number} has no ledger row"
    comparison = taxable_base_comparison(invoice, rows)
    if comparison is None:
        return (
            f"accrual_part_paid: received invoice {invoice.invoice_number} and its ledger rows have no "
            "common currency with a EUR value, so what they cover is not known"
        )
    if comparison.cash < comparison.owed:
        return (
            f"accrual_part_paid: received invoice {invoice.invoice_number} accrues {comparison.owed} "
            f"but its ledger rows state {comparison.cash}; add a row for the rest"
        )
    return None


def _unpaid_received_invoice_details(
    accruing: Iterable[Invoice],
    rows_by_invoice: Mapping[str, Sequence[Transaction]],
    criteria: ImputationCriteria,
    year: int,
) -> tuple[str, ...]:
    """Describe each accruing received invoice whose ledger rows leave part of its base unplaced."""
    if criteria.usable(year) is not ActivityImputationCriterion.DEVENGO:
        return ()
    return tuple(
        detail
        for invoice in accruing
        if not is_rectificativa(invoice)
        and (detail := accrual_coverage_gap(invoice, rows_by_invoice.get(invoice.invoice_id, ()))) is not None
    )


def _expense_imputation_diagnostics(
    context: CalculationSourceContext,
    *,
    source_kind: str,
    resolver_id: str,
    binding_ids: Iterable[BindingId],
    unresolved: Sequence[str],
    rows_present: bool,
    period: Period,
    invoices: InvoiceCatalogue,
    transactions: TransactionCatalogue,
    filings: ImputationFilingHistory | None = None,
) -> tuple[CalculationSourceDiagnostic, ...]:
    """Withhold the expense boxes while a row or an unpaid received invoice cannot be placed.

    Under accrual a received invoice with no payment still accrues, but only a
    ledger row carries the category and business share that decide its box, so an
    unpaid invoice, or the unpaid part of one, stays unresolved rather than entering
    a box it was never classified for. A row for that part clears the finding.
    """
    criteria = declared_imputation_criteria(context.profile.record if context.profile is not None else None, filings)
    with source_context_operation(context):
        accruing = accruing_invoices(
            invoices.values(),
            kind=InvoiceKind.RECEIVED,
            bucket_id=context.bucket_id,
            start=date(period.filing_year, 1, 1),
            end=period.end_date,
            criteria=criteria,
        )
    unpaid = _unpaid_received_invoice_details(
        accruing, _received_invoice_rows(transactions), criteria, period.filing_year
    )
    corrected = received_rectificativa_reading(
        invoices,
        transactions,
        bucket_id=context.bucket_id,
        window_start=date(period.filing_year, 1, 1),
        window_end=period.end_date,
        criteria=criteria,
    )
    return received_rectificativa_netting_diagnostics(
        corrected.netted, source_kind=source_kind, resolver_id=resolver_id
    ) + imputation_blocking_diagnostics(
        source_kind=source_kind,
        resolver_id=resolver_id,
        revision=context.revision,
        binding_ids=binding_ids,
        criteria=criteria,
        year=period.filing_year,
        activity_present=bool(rows_present or accruing or unresolved),
        unresolved_details=(*unresolved, *unpaid, *corrected.refused),
    )


def _m100_unrouted_diagnostics(
    context: CalculationSourceContext,
    observations: Sequence[RentaGastosEstimacionDirectaObservationProtocol],
    *,
    resolver_id: str,
) -> tuple[CalculationSourceDiagnostic, ...]:
    return tuple(
        CalculationSourceDiagnostic(
            reason="unrouted_observation",
            source_kind="ledger_renta_gastos_estimacion_directa_aggregation",
            resolver_id=resolver_id,
            message=(
                f"declarable renta gastos observation "
                f"(modelo={observation.modelo!r}, period={observation.period!r}, "
                f"target_casilla_id={observation.target_casilla_id!r}, "
                f"deductible_amount={observation.deductible_amount}) is not consumed by any "
                f"ledger_renta_gastos_estimacion_directa_aggregation binding "
                f"on revision {context.revision.id!r}; "
                "its deductible amount is not declared on this calculation"
            ),
        )
        for observation in observations
    )


def _renta_observation_provenance(
    observation: RentaDeductibleExpenseObservation,
) -> tuple[CalculationSourceProvenance, ...]:
    provenance = [
        CalculationSourceProvenance(
            resolver_id=LedgerRentaGastosEstimacionDirectaAggregationSourceResolver.resolver_id,
            resolved_binding_source=BindingSourceKind.LEDGER_RENTA_GASTOS_ESTIMACION_DIRECTA_AGGREGATION,
            contributor_source_kind="ledger_renta_gastos_estimacion_directa_aggregation",
            contributor_binding_source=BindingSourceKind.LEDGER_RENTA_GASTOS_ESTIMACION_DIRECTA_AGGREGATION,
            lineage_role=CalculationSourceLineageRole.PRIMARY,
            source_ref=f"transaction:{observation.transaction_id}",
            parent_source_ref=None,
            terminal_origin=TerminalOriginClass.LEDGER_AGGREGATE,
        ),
    ]
    if observation.invoice_id is not None:
        provenance.append(
            CalculationSourceProvenance(
                resolver_id=LedgerRentaGastosEstimacionDirectaAggregationSourceResolver.resolver_id,
                resolved_binding_source=BindingSourceKind.LEDGER_RENTA_GASTOS_ESTIMACION_DIRECTA_AGGREGATION,
                contributor_source_kind="ledger_renta_gastos_estimacion_directa_aggregation",
                contributor_binding_source=BindingSourceKind.LEDGER_RENTA_GASTOS_ESTIMACION_DIRECTA_AGGREGATION,
                lineage_role=CalculationSourceLineageRole.PRIMARY,
                source_ref=f"purchase-invoice-evidence:{observation.invoice_id}",
                parent_source_ref=None,
                terminal_origin=TerminalOriginClass.LEDGER_AGGREGATE,
            ),
        )
    return tuple(provenance)


def _renta_gasto_target_casilla(context: CalculationSourceContext) -> CasillaId:
    providers = tuple(
        binding.provider
        for binding in context.revision.bindings
        if isinstance(binding.provider, LedgerRentaGastosPagoFraccionadoProvider)
        and str(binding.provider.modelo) == context.modelo
    )
    targets = {provider.target_casilla_id for provider in providers}
    if len(targets) != 1:
        raise RegistryError(
            "selected revision must declare exactly one renta-gasto aggregation target",
            context={"modelo": context.modelo, "target_count": len(targets)},
        )
    return next(iter(targets))


class LedgerRentaGastosPagoFraccionadoAggregationSourceResolver:
    """Source mesh resolver for repository-backed M130 deductible-expense (gasto) bindings.

    Owns :attr:`BindingSourceKind.LEDGER_RENTA_GASTOS_PAGO_FRACCIONADO_AGGREGATION`. This is the
    OUTGOING sibling of :class:`LedgerRentaIncomeAggregationSourceResolver`: it
    folds deductible business expenses into Modelo 130 casilla 02 over the same
    cumulative year-to-date quarterly window and emits an unrouted-observation
    diagnostic for declarable gastos no binding consumes.
    """

    resolver_id: ClassVar[str] = "ledger_renta_gastos_pago_fraccionado_aggregation"
    owned_sources: ClassVar[tuple[BindingSourceKind, ...]] = (
        BindingSourceKind.LEDGER_RENTA_GASTOS_PAGO_FRACCIONADO_AGGREGATION,
    )

    def __init__(
        self,
        *,
        transaction_repository: TransactionCatalogueRepositoryProtocol,
        invoice_reader: InvoiceCatalogueReader,
        prorrata_register_repository: ProrrataRegisterRepositoryProtocol,
        usage_ratio_profile_loader: UsageRatioProfileLoader,
        activity_asset_history_repository: ActivityAssetHistoryRepository,
        imputation_filings: Callable[[CalculationSourceContext], ImputationFilingHistory] | None = None,
    ) -> None:
        """Bind repositories used to resolve Renta expense sources."""
        self._transaction_repository = transaction_repository
        self._invoice_reader = invoice_reader
        self._prorrata_register_repository = prorrata_register_repository
        self._usage_ratio_profile_loader = usage_ratio_profile_loader
        self._activity_asset_history_repository = activity_asset_history_repository
        self._imputation_filings = imputation_filings

    def _possibly_durable_findings(
        self,
        aggregation: RentaGastoLedgerAggregation,
        asset_history: ActivityAssetHistory,
        excluded_transaction_ids: frozenset[str],
        tax_year: int,
    ) -> tuple[CalculationSourceDiagnostic, ...]:
        return possibly_durable_expense_findings(
            (
                observation.transaction_id
                for observation in aggregation.observations
                if observation.transaction_id not in excluded_transaction_ids
            ),
            revisions=asset_history.revisions,
            ledger=self._transaction_repository,
            invoices=self._invoice_reader,
            tax_year=tax_year,
            source_kind="ledger_renta_gastos_pago_fraccionado_aggregation",
            resolver_id=self.resolver_id,
        )

    def _diagnostics(
        self,
        context: CalculationSourceContext,
        *,
        aggregation: RentaGastoLedgerAggregation,
        split: _RegisterSplit[RentaGastoLedgerAggregationIssue, RentaGastoObservation, ActivityAssetExpenseObservation],
        period: Period,
        invoices: InvoiceCatalogue,
        asset_history: ActivityAssetHistory,
        asset_projection: ActivityAssetProjection,
        classification: LedgerExpenseRegisterClassification,
        refused: tuple[UnregisteredAmortizationRow, ...],
        may_be_durable: tuple[CalculationSourceDiagnostic, ...],
        unrouted: Sequence[RentaGastosPagoFraccionadoObservationProtocol],
    ) -> tuple[CalculationSourceDiagnostic, ...]:
        return (
            out_of_window_summary_diagnostics(
                aggregation.out_of_window_summary,
                source_kind="ledger_renta_gastos_pago_fraccionado_aggregation",
                resolver_id=self.resolver_id,
            )
            + source_issue_diagnostics(
                split.issues,
                source_kind="ledger_renta_gastos_pago_fraccionado_aggregation",
                resolver_id=self.resolver_id,
                held_back_reasons=frozenset(
                    {
                        RentaGastoLedgerAggregationIssueReason.MISSING_TAXABLE_BASE,
                        RentaGastoLedgerAggregationIssueReason.UNSUPPORTED_CURRENCY,
                        RentaGastoLedgerAggregationIssueReason.MISSING_CATEGORY,
                        RentaGastoLedgerAggregationIssueReason.UNKNOWN_CATEGORY,
                    }
                ),
                source_ref=lambda issue: f"transaction:{issue.transaction_id}",
                suppressed_reasons=frozenset({RentaGastoLedgerAggregationIssueReason.IMPUTATION_UNRESOLVED}),
            )
            + _expense_imputation_diagnostics(
                context,
                source_kind="ledger_renta_gastos_pago_fraccionado_aggregation",
                resolver_id=self.resolver_id,
                binding_ids=resolve_ledger_renta_gastos_pago_fraccionado_aggregation_binding_values(
                    context.revision, split.all_observations
                ),
                unresolved=tuple(
                    issue.detail
                    for issue in split.issues
                    if issue.reason is RentaGastoLedgerAggregationIssueReason.IMPUTATION_UNRESOLVED
                ),
                rows_present=bool(split.ledger_observations),
                period=period,
                invoices=invoices,
                transactions=self._transaction_repository.load(),
                filings=self._imputation_filings(context) if self._imputation_filings is not None else None,
            )
            + source_issue_diagnostics(
                aggregation.advisories,
                source_kind="ledger_renta_gastos_pago_fraccionado_aggregation",
                resolver_id=self.resolver_id,
            )
            + register_owned_acquisition_diagnostics(
                split.register_owned,
                source_kind="ledger_renta_gastos_pago_fraccionado_aggregation",
                resolver_id=self.resolver_id,
            )
            + unregistered_amortization_row_diagnostics(
                (*classification.unregistered, *refused),
                resolver_id=self.resolver_id,
            )
            + asset_projection.diagnostics
            + activity_asset_ledger_findings(
                asset_history.revisions,
                ledger=self._transaction_repository,
                tax_year=period.filing_year,
                source_kind="ledger_renta_gastos_pago_fraccionado_aggregation",
                resolver_id=self.resolver_id,
            )
            + may_be_durable
            + _m130_unrouted_diagnostics(context, unrouted, resolver_id=self.resolver_id)
        )

    def _provenance(
        self,
        split: _RegisterSplit[RentaGastoLedgerAggregationIssue, RentaGastoObservation, ActivityAssetExpenseObservation],
        asset_projection: ActivityAssetProjection,
    ) -> tuple[CalculationSourceProvenance, ...]:
        return (
            _m130_ledger_provenance(split.ledger_observations, resolver_id=self.resolver_id)
            + activity_asset_provenance(
                split.asset_observations,
                resolver_id=self.resolver_id,
                resolved_binding_source=BindingSourceKind.LEDGER_RENTA_GASTOS_PAGO_FRACCIONADO_AGGREGATION,
            )
            + activity_asset_disposal_provenance(
                asset_projection,
                resolver_id=self.resolver_id,
                resolved_binding_source=BindingSourceKind.LEDGER_RENTA_GASTOS_PAGO_FRACCIONADO_AGGREGATION,
            )
        )

    def resolve(self, context: CalculationSourceContext) -> CalculationSourceResolution:
        """Resolve Renta expense observations for one calculation context."""
        if not revision_has_binding_source(context.revision, "ledger_renta_gastos_pago_fraccionado_aggregation"):
            return empty_source_resolution(self.resolver_id, self.owned_sources)

        aggregation_period = aggregation_period_for_modelo(
            filing_year=context.filing_year,
            code=context.period.registry_token,
        )
        target_casilla_id = _renta_gasto_target_casilla(context)
        profile_record = context.profile.record if context.profile is not None else None
        try:
            asset_history = self._activity_asset_history_repository.load()
            with source_context_operation(context) as operation:
                invoices = self._invoice_reader.load()
                aggregation = aggregate_renta_gasto_ledger_from_repositories(
                    bucket_id=context.bucket_id,
                    period=aggregation_period,
                    modelo=context.modelo,
                    target_casilla_id=target_casilla_id,
                    accept_activity_marker=context.modelo == form_for_role("renta.direct_instalment"),
                    transaction_repository=self._transaction_repository,
                    usage_ratios=resolve_effective_usage_ratios(
                        bucket_id=context.bucket_id,
                        year=context.filing_year,
                        usage_ratio_profile_loader=self._usage_ratio_profile_loader,
                        operation=operation,
                        profile_record=profile_record,
                    ),
                    profile_record=profile_record,
                    prorrata_register_repository=self._prorrata_register_repository,
                    operation=operation,
                    ownership_share=dwelling_ownership_share(asset_history.revisions),
                    register_owned_transaction_ids=register_acquisition_transaction_ids(asset_history.revisions),
                    criteria=declared_imputation_criteria(
                        profile_record,
                        self._imputation_filings(context) if self._imputation_filings is not None else None,
                    ),
                    invoices=invoices,
                )
                classification = classify_ledger_expenses_against_asset_register(
                    asset_history.revisions,
                    _m130_asset_register_treatments(
                        aggregation.observations,
                        filing_year=aggregation_period.filing_year,
                        capital_goods=capital_good_transaction_ids(
                            (observation.transaction_id for observation in aggregation.observations),
                            ledger=self._transaction_repository,
                            tax_year=aggregation_period.filing_year,
                        ),
                    ),
                )
                refused = refused_amortization_rows(
                    aggregation.issues,
                    assets=asset_history.revisions,
                    tax_year=aggregation_period.filing_year,
                    effective_date=date(aggregation_period.filing_year, 12, 31),
                )
                asset_projection = m130_activity_asset_projection(
                    asset_history,
                    context=context,
                    period=aggregation_period,
                    target_casilla_id=target_casilla_id,
                    transactions=self._transaction_repository,
                    operation=operation,
                    resolver_id=self.resolver_id,
                )
                may_be_durable = self._possibly_durable_findings(
                    aggregation, asset_history, classification.excluded_transaction_ids, aggregation_period.filing_year
                )
        except STORAGE_DEGRADATION_ERRORS as exc:
            return storage_degradation_resolution(
                resolver_id=self.resolver_id,
                owned_sources=self.owned_sources,
                source_kinds=self.owned_sources,
                error=exc,
            )
        split = _split_register_owned(
            aggregation_issues=aggregation.issues,
            aggregation_observations=aggregation.observations,
            asset_history=asset_history,
            classification=classification,
            refused=refused,
            asset_observations=asset_projection.observations,
            tax_year=aggregation_period.filing_year,
        )
        issues = split.issues
        ledger_observations = split.ledger_observations
        all_observations = split.all_observations
        unrouted = unsupported_ledger_renta_gastos_pago_fraccionado_observations(context.revision, all_observations)
        return CalculationSourceResolution(
            resolver_id=self.resolver_id,
            owned_sources=self.owned_sources,
            binding_values=resolve_ledger_renta_gastos_pago_fraccionado_aggregation_binding_values(
                context.revision,
                all_observations,
            ),
            value_outcomes=_ledger_expense_value_outcomes(
                context,
                resolve_ledger_renta_gastos_pago_fraccionado_aggregation_binding_values(
                    context.revision, all_observations
                ),
                held_back_rows=any(issue.reason.value not in _NOT_AN_EXPENSE_ISSUES for issue in issues),
                period=aggregation_period,
                invoices=invoices,
            ),
            source_transaction_ids=sorted_ids(ledger_observations, lambda observation: observation.transaction_id),
            diagnostics=self._diagnostics(
                context,
                aggregation=aggregation,
                split=split,
                period=aggregation_period,
                invoices=invoices,
                asset_history=asset_history,
                asset_projection=asset_projection,
                classification=classification,
                refused=refused,
                may_be_durable=may_be_durable,
                unrouted=unrouted,
            ),
            provenance=self._provenance(split, asset_projection),
        )


def _m130_unrouted_diagnostics(
    context: CalculationSourceContext,
    observations: Sequence[RentaGastosPagoFraccionadoObservationProtocol],
    *,
    resolver_id: str,
) -> tuple[CalculationSourceDiagnostic, ...]:
    return tuple(
        CalculationSourceDiagnostic(
            reason="unrouted_observation",
            source_kind="ledger_renta_gastos_pago_fraccionado_aggregation",
            resolver_id=resolver_id,
            message=(
                f"declarable renta gasto observation (target_casilla_id="
                f"{observation.target_casilla_id!r}, deductible_amount={observation.deductible_amount}) "
                f"is not consumed by any ledger_renta_gastos_pago_fraccionado_aggregation binding on revision "
                f"{context.revision.id!r}; its deductible expense is not declared on this calculation"
            ),
        )
        for observation in observations
    )


def _m130_ledger_provenance(
    observations: Sequence[RentaGastoObservation], *, resolver_id: str
) -> tuple[CalculationSourceProvenance, ...]:
    return source_provenance_for(
        observations,
        lambda observation: CalculationSourceProvenance(
            resolver_id=resolver_id,
            resolved_binding_source=BindingSourceKind.LEDGER_RENTA_GASTOS_PAGO_FRACCIONADO_AGGREGATION,
            contributor_source_kind="ledger_renta_gastos_pago_fraccionado_aggregation",
            contributor_binding_source=BindingSourceKind.LEDGER_RENTA_GASTOS_PAGO_FRACCIONADO_AGGREGATION,
            lineage_role=CalculationSourceLineageRole.PRIMARY,
            source_ref=f"transaction:{observation.transaction_id}",
            parent_source_ref=None,
            terminal_origin=TerminalOriginClass.LEDGER_AGGREGATE,
        ),
    )


def _m130_asset_register_treatments(
    observations: Sequence[RentaGastoObservation],
    *,
    filing_year: int,
    capital_goods: frozenset[str],
) -> tuple[LedgerRentaExpenseTreatment, ...]:
    """Weigh the quarterly gasto rows against the activity-asset register.

    Every quarterly gasto shares one target casilla, so a row's category is the
    only thing that can label it an amortization. The categories are resolved once
    for the filing year, because the first-slice route is declared per annual
    Modelo 100 revision and does not vary inside a year.

    Returns:
        One treatment per gasto row.
    """
    candidates = tuple(observations)
    if not candidates:
        return ()
    labelled = amortization_labelled_expense_categories(effective_date=date(filing_year, 12, 31))
    return tuple(
        LedgerRentaExpenseTreatment(
            transaction_id=observation.transaction_id,
            category=observation.category_id,
            tax_year=observation.filing_date.year,
            booked_on=observation.filing_date,
            deductible_amount=observation.deductible_amount,
            amortization_labelled=observation.category_id in labelled or observation.transaction_id in capital_goods,
        )
        for observation in candidates
    )


__all__ = [
    "LedgerRentaGastosEstimacionDirectaAggregationSourceResolver",
    "LedgerRentaGastosPagoFraccionadoAggregationSourceResolver",
]
