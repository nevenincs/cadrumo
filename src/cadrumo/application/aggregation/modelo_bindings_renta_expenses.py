"""Repository-backed annual and quarterly Renta expense source resolvers."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import date
from typing import ClassVar

from ...core.aggregation import BindingSourceKind, CalculationSourceLineageRole
from ...core.casilla_id import CasillaId
from ...core.modelo import Modelo
from ...domain.calculations.registry.actividad_asset_disposal_bindings import (
    resolve_activity_asset_disposal_binding_values,
    resolve_activity_asset_disposal_element_type_values,
)
from ...domain.calculations.registry.binding_terminal_origin import TerminalOriginClass
from ...domain.calculations.registry.errors import RegistryError
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
from ...domain.prorrata_register.protocols import ProrrataRegisterRepositoryProtocol
from ...domain.renta.ledger_expenses import RentaDeductibleExpenseObservation
from ...domain.transactions.protocols import TransactionCatalogueRepositoryProtocol
from ..actividad_asset.history import ActivityAssetHistory
from ..actividad_asset.ports import ActivityAssetHistoryRepository
from ..invoices.catalogue_reads_ports import (
    InvoiceCatalogueReader,
    InvoiceCatalogueReadPersistenceError,
    InvoiceCatalogueReadPorts,
)
from ..ledger.usage_ratio_repository import UsageRatioProfileLoader
from ..user_profile.usage_ratio_resolution import resolve_effective_usage_ratios
from ._modelo_bindings_invoice_iva import out_of_window_summary_diagnostics
from ._modelo_bindings_support import (
    STORAGE_DEGRADATION_ERRORS,
    empty_source_resolution,
    revision_has_binding_source,
)
from .activity_asset_expense_reconciliation import (
    LedgerExpenseRegisterClassification,
    LedgerRentaExpenseTreatment,
    amortization_labelled_expense_categories,
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
from .modelo_bindings import aggregation_period_for_modelo
from .modelo_bindings_actividad_assets import (
    activity_asset_disposal_provenance,
    activity_asset_provenance,
    m100_activity_asset_projection,
    m130_activity_asset_projection,
)
from .renta_gasto_ledger import (
    RentaGastoLedgerAggregation,
    RentaGastoLedgerAggregationIssueReason,
    RentaGastoObservation,
    aggregate_renta_gasto_ledger_from_repositories,
)
from .renta_ledger import aggregate_renta_ledger_expenses_from_repositories
from .renta_ledger_models import RentaLedgerExpenseAggregation
from .source_mesh import (
    CalculationSourceContext,
    CalculationSourceDiagnostic,
    CalculationSourceProvenance,
    CalculationSourceResolution,
)
from .source_resolution_operations import (
    flatten_source_provenance_for as _flattened_provenance_for,
)
from .source_resolution_operations import sorted_source_ids as sorted_ids
from .source_resolution_operations import (
    source_context_operation,
    source_issue_diagnostics,
    storage_degradation_resolution,
)
from .source_resolution_operations import source_provenance_for as _provenance_for


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
    ) -> None:
        """Initialize the resolver with its required catalogue read capabilities."""
        self._ports = ports
        self._prorrata_register_repository = prorrata_register_repository
        self._usage_ratio_profile_loader = usage_ratio_profile_loader
        self._activity_asset_history_repository = activity_asset_history_repository

    def _aggregate(
        self,
        context: CalculationSourceContext,
        *,
        asset_history: ActivityAssetHistory,
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
                    register_owned_transaction_ids=register_acquisition_transaction_ids(asset_history.revisions),
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
                    deductible_amount=observation.deductible_amount,
                    amortization_labelled=(
                        observation.target_casilla_id in amortization_boxes
                        or observation.category.value in labelled
                        or observation.transaction_id in capital_goods
                    ),
                )
                for observation in aggregation.observations
            ),
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
        except STORAGE_DEGRADATION_ERRORS as exc:
            return storage_degradation_resolution(
                resolver_id=self.resolver_id,
                owned_sources=self.owned_sources,
                source_kinds=self.owned_sources,
                error=exc,
            )
        aggregation = self._aggregate(context, asset_history=asset_history)
        if isinstance(aggregation, CalculationSourceResolution):
            return aggregation
        with source_context_operation(context) as operation:
            classification = self._classify_expenses(
                aggregation,
                asset_history=asset_history,
                amortization_boxes=frozenset(activity_asset_amortization_casillas(context.revision).values()),
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
        refused_owned = refused_register_owned_rows(
            aggregation.issues,
            assets=asset_history.revisions,
            tax_year=aggregation.period.filing_year,
            effective_date=date(aggregation.period.filing_year, 12, 31),
        )
        register_owned = (*classification.withheld, *refused_owned)
        issues = issues_the_register_does_not_answer(
            aggregation.issues,
            answered=(*refused_owned, *refused, *classification.unregistered),
        )
        excluded_transaction_ids = classification.excluded_transaction_ids
        ledger_observations = tuple(
            observation
            for observation in aggregation.observations
            if observation.transaction_id not in excluded_transaction_ids
        )
        asset_observations = asset_projection.observations
        all_observations = (*ledger_observations, *asset_observations)
        unrouted = unsupported_ledger_renta_gastos_estimacion_directa_observations(context.revision, all_observations)
        element_types, element_types_inapplicable = resolve_activity_asset_disposal_element_type_values(
            context.revision,
            asset_projection.disposal_observations,
        )
        return CalculationSourceResolution(
            resolver_id=self.resolver_id,
            owned_sources=self.owned_sources,
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
            source_transaction_ids=sorted_ids(ledger_observations, lambda observation: observation.transaction_id),
            diagnostics=source_issue_diagnostics(
                issues,
                source_kind="ledger_renta_gastos_estimacion_directa_aggregation",
                resolver_id=self.resolver_id,
            )
            + register_owned_acquisition_diagnostics(
                register_owned,
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
            + _m100_unrouted_diagnostics(context, unrouted, resolver_id=self.resolver_id),
            provenance=_flattened_provenance_for(
                ledger_observations,
                _renta_observation_provenance,
            )
            + activity_asset_provenance(
                asset_observations,
                resolver_id=self.resolver_id,
                resolved_binding_source=BindingSourceKind.LEDGER_RENTA_GASTOS_ESTIMACION_DIRECTA_AGGREGATION,
            )
            + activity_asset_disposal_provenance(
                asset_projection.disposal_revision_ids,
                resolver_id=self.resolver_id,
                resolved_binding_source=BindingSourceKind.ACTIVITY_ASSET_DISPOSAL,
            ),
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
    ) -> None:
        """Bind repositories used to resolve Renta expense sources."""
        self._transaction_repository = transaction_repository
        self._invoice_reader = invoice_reader
        self._prorrata_register_repository = prorrata_register_repository
        self._usage_ratio_profile_loader = usage_ratio_profile_loader
        self._activity_asset_history_repository = activity_asset_history_repository

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
                aggregation = aggregate_renta_gasto_ledger_from_repositories(
                    bucket_id=context.bucket_id,
                    period=aggregation_period,
                    modelo=context.modelo,
                    target_casilla_id=target_casilla_id,
                    accept_activity_marker=context.modelo == Modelo("130").value,
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
        refused_owned = refused_register_owned_rows(
            aggregation.issues,
            assets=asset_history.revisions,
            tax_year=aggregation_period.filing_year,
            effective_date=date(aggregation_period.filing_year, 12, 31),
        )
        register_owned = (*classification.withheld, *refused_owned)
        issues = issues_the_register_does_not_answer(
            aggregation.issues,
            answered=(*refused_owned, *refused, *classification.unregistered),
        )
        excluded_transaction_ids = classification.excluded_transaction_ids
        ledger_observations = tuple(
            observation
            for observation in aggregation.observations
            if observation.transaction_id not in excluded_transaction_ids
        )
        asset_observations = asset_projection.observations
        all_observations = (*ledger_observations, *asset_observations)
        unrouted = unsupported_ledger_renta_gastos_pago_fraccionado_observations(context.revision, all_observations)
        return CalculationSourceResolution(
            resolver_id=self.resolver_id,
            owned_sources=self.owned_sources,
            binding_values=resolve_ledger_renta_gastos_pago_fraccionado_aggregation_binding_values(
                context.revision,
                all_observations,
            ),
            source_transaction_ids=sorted_ids(ledger_observations, lambda observation: observation.transaction_id),
            diagnostics=out_of_window_summary_diagnostics(
                aggregation.out_of_window_summary,
                source_kind="ledger_renta_gastos_pago_fraccionado_aggregation",
                resolver_id=self.resolver_id,
            )
            + source_issue_diagnostics(
                issues,
                source_kind="ledger_renta_gastos_pago_fraccionado_aggregation",
                resolver_id=self.resolver_id,
                held_back_reasons=frozenset(
                    {
                        RentaGastoLedgerAggregationIssueReason.MISSING_TAXABLE_BASE,
                        RentaGastoLedgerAggregationIssueReason.UNSUPPORTED_CURRENCY,
                    }
                ),
                source_ref=lambda issue: f"transaction:{issue.transaction_id}",
            )
            + register_owned_acquisition_diagnostics(
                register_owned,
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
                tax_year=aggregation_period.filing_year,
                source_kind="ledger_renta_gastos_pago_fraccionado_aggregation",
                resolver_id=self.resolver_id,
            )
            + may_be_durable
            + _m130_unrouted_diagnostics(context, unrouted, resolver_id=self.resolver_id),
            provenance=_m130_ledger_provenance(ledger_observations, resolver_id=self.resolver_id)
            + activity_asset_provenance(
                asset_observations,
                resolver_id=self.resolver_id,
                resolved_binding_source=BindingSourceKind.LEDGER_RENTA_GASTOS_PAGO_FRACCIONADO_AGGREGATION,
            )
            + activity_asset_disposal_provenance(
                asset_projection.disposal_revision_ids,
                resolver_id=self.resolver_id,
                resolved_binding_source=BindingSourceKind.LEDGER_RENTA_GASTOS_PAGO_FRACCIONADO_AGGREGATION,
            ),
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
    return _provenance_for(
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
            deductible_amount=observation.deductible_amount,
            amortization_labelled=observation.category_id in labelled or observation.transaction_id in capital_goods,
        )
        for observation in candidates
    )


__all__ = [
    "LedgerRentaGastosEstimacionDirectaAggregationSourceResolver",
    "LedgerRentaGastosPagoFraccionadoAggregationSourceResolver",
]
